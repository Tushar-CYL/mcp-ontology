"""Run the ontology shapes and record every violation.

This is the step that makes the ontology more than a YAML file. Each rule in
ontology.yaml has a shape in sql/<engine>/shapes.sql; this runs them, counts
violations exactly, stores a bounded sample of each, and prints a report.

Violations are EXPECTED. The source is real production telemetry with
documented defects, and the point is to measure them rather than let a
loader quietly skip them.

Severity decides what a violation MEANS:
    1  our derivation is broken      -> fails the build
    2  the source is wrong, repaired -> counted, repair policy recorded
    3  worth knowing                 -> counted only

Usage:
    python ontology/validate.py --stage staging
    python ontology/validate.py --stage graph
    python ontology/validate.py --report <run_id>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import load_ontology  # noqa: E402
from db import connect  # noqa: E402

MARKER = re.compile(r"^--\s*@rule:\s*(\S+)\s*$", re.M)
STAGE = re.compile(r"^--\s*@stage:\s*(\S+)\s*$", re.M)


def parse_shapes(path: Path) -> dict[str, tuple[str, str]]:
    """Split shapes.sql into {rule_id: (stage, sql_body)}."""
    text = path.read_text(encoding="utf-8")
    hits = list(MARKER.finditer(text))
    if not hits:
        raise RuntimeError(f"no '-- @rule:' markers in {path}")
    out: dict[str, tuple[str, str]] = {}
    for i, m in enumerate(hits):
        start = m.end()
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        body = text[start:end]
        sm = STAGE.search(body)
        stage = sm.group(1) if sm else "staging"
        body = STAGE.sub("", body).strip().rstrip(";")
        out[m.group(1)] = (stage, body)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["staging", "graph"], default="staging")
    ap.add_argument("--sample", type=int, default=25,
                    help="violating rows stored per rule")
    ap.add_argument("--only", action="append", help="run only these rule ids")
    ap.add_argument("--report", type=int, help="reprint a previous run")
    args = ap.parse_args()

    onto = load_ontology()
    rules = {r["id"]: r for r in onto["rules"]}

    with connect() as db:
        if args.report:
            return print_report(db, args.report)

        shapes = parse_shapes(db.sql_dir() / "shapes.sql")
        missing = set(rules) - set(shapes)
        orphan = set(shapes) - set(rules)
        if missing:
            raise SystemExit(f"rules with no shape: {sorted(missing)}")
        if orphan:
            raise SystemExit(f"shapes with no rule: {sorted(orphan)}")

        db.execute("INSERT INTO validation_run(ontology_ver, stage) "
                   "VALUES (?, ?)", [onto["version"], args.stage])
        run_id = db.one("SELECT max(run_id) FROM validation_run")

        todo = [r for r in rules
                if shapes[r][0] == args.stage
                and (not args.only or r in args.only)]
        other = len(rules) - len(todo)

        print(f"\nvalidation run {run_id}  stage={args.stage}  "
              f"ontology v{onto['version']}  engine={db.engine}")
        print(f"{len(todo)} rule(s) to run, {other} for another stage\n")

        summary: dict[str, dict] = {}
        failed_hard: list[str] = []

        for rule_id in todo:
            body = shapes[rule_id][1]
            sev = rules[rule_id]["severity"]
            print(f"  {rule_id} (sev {sev}) ...", end="", flush=True)
            t0 = time.monotonic()
            try:
                n = db.one(f"SELECT count(*) FROM ({body}) v") or 0
                if n:
                    db.execute(
                        "INSERT INTO validation_findings"
                        "(run_id, rule_id, severity, row_key, detail) "
                        f"SELECT {run_id}, '{rule_id}', {sev}, "
                        f"v.row_key, v.detail FROM ({body}) v LIMIT ?",
                        [args.sample])
            except Exception as e:                            # noqa: BLE001
                msg = str(e).splitlines()[0]
                print(f" ERROR: {msg}")
                summary[rule_id] = {"error": msg}
                continue

            el = time.monotonic() - t0
            summary[rule_id] = {"violations": n, "severity": sev,
                                "seconds": round(el, 1),
                                "repair": rules[rule_id]["repair"]}
            flag = "   <-- BLOCKS BUILD" if (n and sev == 1) else ""
            print(f" {n:,} violations  [{el:,.1f}s]{flag}")
            if n and sev == 1:
                failed_hard.append(rule_id)

        db.execute("UPDATE validation_run SET finished_at = now(), "
                   "summary = ? WHERE run_id = ?",
                   [json.dumps(summary), run_id])

        print_report(db, run_id)

        if failed_hard:
            print(f"\nFAILED: severity-1 rules violated: {failed_hard}")
            print("These mean OUR derivation is wrong, not that the source "
                  "is messy. Fix the deriver before building further.")
            return 1
    return 0


def print_report(db, run_id: int) -> int:
    row = db.query("SELECT stage, ontology_ver, summary "
                   "FROM validation_run WHERE run_id = ?", [run_id])
    if not row:
        print(f"no such run: {run_id}")
        return 1
    stage, ver, summary = row[0]
    summary = json.loads(summary) if isinstance(summary, str) else (summary or {})

    print(f"\n{'=' * 78}")
    print(f"VALIDATION REPORT  run {run_id}  stage={stage}  ontology v{ver}")
    print(f"{'=' * 78}")
    print(f"{'rule':<28}{'sev':>4}{'violations':>14}{'secs':>7}  repair")
    print("-" * 78)
    total = 0
    for rule_id, s in sorted(summary.items(),
                             key=lambda kv: -(kv[1].get("violations") or 0)):
        if "error" in s:
            print(f"{rule_id:<28}{'-':>4}{'ERROR':>14}{'-':>7}  {s['error'][:22]}")
            continue
        n = s.get("violations", 0)
        total += n
        print(f"{rule_id:<28}{s['severity']:>4}{n:>14,}"
              f"{s['seconds']:>7,.1f}  {s.get('repair', '')}")
    print("-" * 78)
    print(f"{'TOTAL':<28}{'':>4}{total:>14,}")

    rows = db.query(
        "SELECT rule_id, row_key, CAST(detail AS VARCHAR) "
        "FROM validation_findings WHERE run_id = ? "
        "ORDER BY rule_id LIMIT 6", [run_id])
    if rows:
        print("\nsample violations:")
        for rule_id, key, detail in rows:
            print(f"  [{rule_id}] {key}")
            print(f"      {detail[:150]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
