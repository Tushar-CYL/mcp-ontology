"""QA data matrix: every kind of data through the whole Ontology journey.

    python scripts/qa_data_matrix.py              edge cases (generated)
    python scripts/qa_data_matrix.py --real       plus the real datasets on disk
    python scripts/qa_data_matrix.py --ai         use the configured AI model

Each case runs in its own scratch database (never the main graph):
load -> build -> view -> invariants -> Excel -> MCP get_ontology -> context
note -> field edit -> rebuild keeps the edit -> delete leaves nothing.
Writes a JSON result file and prints a table. Exit code 1 if any case fails.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REAL = {
    "real_olist_csv_1_5M_rows": ROOT / "data/raw/kaggledata",
    "real_revenue_parquet": ROOT / "data/raw/revenue_huge",
    "real_hospital_sqlite": ROOT / "data/hospital.db",
    "real_example_sqlite": ROOT / "data/example.db",
    "real_cskg_sup_10": ROOT / "data/raw/benchmark/cskg_dataset_sup_10",
    "real_cskg_sup_5": ROOT / "data/raw/benchmark/cskg_dataset_sup_5",
    "real_cskg_sup_3": ROOT / "data/raw/benchmark/cskg_dataset_sup_3",
    "real_salt_sap_parquet": Path(r"C:/Users/tusha/Downloads/salt-kg-main/salt-kg-main/data/salt"),
}


def check(cond, message, problems):
    if not cond:
        problems.append(message)


def invariants(v: dict, problems: list) -> None:
    from ontology import meaning as mn
    json.dumps(v)                                             # must serialise
    names = [t["name"] for t in v["things"]]
    check(len(names) == len(set(n.lower() for n in names)), f"duplicate thing names {names}", problems)
    check(v["summary"]["things"] == len(v["things"]), "summary.things mismatch", problems)
    nfields = sum(len(t["fields"]) for t in v["things"])
    check(v["summary"]["fields"] == nfields, "summary.fields mismatch", problems)
    check(v["summary"]["links"] == len(v["links"]), "summary.links mismatch", problems)
    check(sum(v["summary"]["checks"].values()) == nfields, "check counts do not add up", problems)
    for t in v["things"]:
        check(bool(t["name"].strip()), "empty thing name", problems)
        check(bool(t["description"].strip()), f"{t['name']}: empty description", problems)
        check(t["records"] >= 0, f"{t['name']}: negative records", problems)
        for f in t["fields"]:
            where = f"{t['name']}.{f['column']}"
            check(bool(str(f["label"]).strip()), f"{where}: empty label", problems)
            check(bool(str(f["meaning"]).strip()), f"{where}: empty meaning", problems)
            check(f["role"] in mn.ROLES, f"{where}: bad role {f['role']}", problems)
            check(f["check"] in ("verified", "conflict", "unchecked"), f"{where}: bad check", problems)
            check(0 <= float(f["confidence"] or 0) <= 1, f"{where}: confidence out of range", problems)
            if f["links_to"]:
                check(f["links_to"] in names, f"{where}: links_to unknown thing", problems)
    for link in v["links"]:
        check(link["from_thing"] in names and link["to_thing"] in names,
              f"link to unknown thing: {link['label']}", problems)


def run_case(name: str, path: str, expect: str, client, work: Path) -> dict:
    from api import mcp_server
    from api.service import MiddleLayer
    from ontology import registry as reg
    from ontology import simple
    out = {"case": name, "expect": expect, "status": "?", "problems": [], "timings": {}}
    problems = out["problems"]
    layer = MiddleLayer(str(work / "qa.duckdb"))
    try:
        t0 = time.perf_counter()
        try:
            layer.add_source(path, source="src")
        except Exception as exc:                  # noqa: BLE001 - classified below
            out["timings"]["load"] = round(time.perf_counter() - t0, 2)
            message = str(exc).strip().splitlines()[0][:200] if str(exc).strip() else ""
            clean = type(exc).__name__ in ("SourceError", "FileNotFoundError", "ValueError") \
                and len(message) > 10
            out["load_error"] = f"{type(exc).__name__}: {message}"
            if expect in ("reject", "reject_or_ok") and clean:
                out["status"] = "pass (rejected cleanly)"
            else:
                problems.append(f"load failed: {out['load_error']}")
                out["status"] = "FAIL"
            return out
        out["timings"]["load"] = round(time.perf_counter() - t0, 2)
        if expect == "reject":
            problems.append("loaded although it should have been rejected")
        t0 = time.perf_counter()
        built = simple.create_and_build(layer, f"QA {name}", ["src"], client=client)
        out["timings"]["build"] = round(time.perf_counter() - t0, 2)
        oid = built["ontology"]
        v = simple.view(layer.graph, oid)
        out["summary"] = v["summary"]
        out["things"] = [t["name"] for t in v["things"]][:12]
        invariants(v, problems)
        check(v["summary"]["things"] >= 1, "no business things found", problems)

        data = simple.for_excel(layer.graph, oid)
        check(len(data["fields"]) == v["summary"]["fields"], "Excel field rows mismatch", problems)
        blob = simple.to_xlsx(layer.graph, oid)
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            for part in z.namelist():
                ElementTree.fromstring(z.read(part))

        reply = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                   "params": {"name": "get_ontology",
                                              "arguments": {"ontology": oid}}}, layer)
        check("result" in reply, f"MCP get_ontology failed: {reply.get('error')}", problems)

        first = next((f for t in v["things"] for f in t["fields"]), None)
        if first:
            note = f"{first['column']} = QA label ✓"
            res = simple.add_context(layer, oid, note)
            check(res["changes"], f"context note changed nothing: {note!r}", problems)
            simple.edit_field(layer, oid, first["key"], meaning="Set by QA 🚀 <b>not html</b>")
            t0 = time.perf_counter()
            simple.build(layer, oid, client=client)
            out["timings"]["rebuild"] = round(time.perf_counter() - t0, 2)
            again = next((f for t in simple.view(layer.graph, oid)["things"]
                          for f in t["fields"] if f["key"] == first["key"]), None)
            check(again is not None and again["meaning"] == "Set by QA 🚀 <b>not html</b>",
                  "edit lost on rebuild", problems)
            invariants(simple.view(layer.graph, oid), problems)

        reg.delete_ontology(layer.graph, oid)
        left = sum(int(layer.graph.one(f'SELECT count(*) FROM "{t}" WHERE ontology_id = ?', [oid]))
                   for (t,) in layer.graph.sql(
                       "SELECT DISTINCT table_name FROM information_schema.columns"
                       " WHERE column_name = 'ontology_id' AND table_name LIKE 'eo_%'"))
        check(left == 0, f"{left} rows left after delete", problems)
        out["status"] = "FAIL" if problems else "pass"
    except Exception as exc:                      # noqa: BLE001 - recorded
        problems.append(f"crash: {type(exc).__name__}: {str(exc)[:300]}")
        out["trace"] = traceback.format_exc()[-2500:]
        out["status"] = "FAIL"
    finally:
        try:
            layer.close()
        except Exception:                         # noqa: BLE001
            pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--ai", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=str(ROOT / "docs" / "qa-data-matrix.json"))
    args = ap.parse_args()
    client = None
    if args.ai:
        import run_server
        run_server.load_env()
        from agent.llm import EYQClient
        client = EYQClient()
    from scripts.qa_datasets import make_all
    base = Path(tempfile.mkdtemp(prefix="strata_qa_"))
    cases = {k: (p, e) for k, (p, e) in make_all(base / "data").items()}
    if args.real:
        cases.update({k: (str(p), "ok") for k, p in REAL.items() if p.exists()})
    if args.only:
        cases = {k: v for k, v in cases.items() if args.only in k}
    results = []
    for name, (path, expect) in cases.items():
        work = base / "work" / name
        work.mkdir(parents=True)
        r = run_case(name, path, expect, client, work)
        results.append(r)
        t = r["timings"]
        print(f"{r['status']:<26} {name:<30} load {t.get('load', '-'):>6}  build {t.get('build', '-'):>6}"
              f"  {('; '.join(r['problems']))[:150]}", flush=True)
        shutil.rmtree(work, ignore_errors=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    passed = sum(1 for r in results if r["status"].startswith("pass"))
    print(f"\n{passed}/{len(results)} passed ({100 * passed / max(1, len(results)):.1f}%)")
    shutil.rmtree(base, ignore_errors=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
