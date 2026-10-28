"""Show what each layer actually produces, in readable form.

Four layers are easy to describe and hard to picture. This prints the real
output of each one, from the real database, so you can see what the layer
IS rather than what it is for:

    LAYER 1  ONTOLOGY          the rules - what may exist, what may connect
    LAYER 2  KNOWLEDGE GRAPH   the connections - drawn around one real node
    LAYER 3  SEMANTIC          the numbers - one definition, one meaning
    LAYER 4  CONTEXT           the packed answer

Usage:
    python show.py                      everything, picks a good example
    python show.py --service MS_51052   focus on one microservice
    python show.py --layer graph        one layer only
    python show.py --at "2022-01-01 00:02:30"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect  # noqa: E402

W = 74
DEFAULT_AT = "2022-01-01 00:01:00"


def _unicode_ok() -> bool:
    """Can this console actually print box-drawing characters?

    A Windows console defaults to cp1252, which cannot encode them at all -
    printing one raises UnicodeEncodeError and kills the program. Dying on a
    decoration is absurd, so: try to upgrade stdout to UTF-8, then TEST the
    result rather than assume it worked, and fall back to ASCII if not.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        "┌─│╔═║▼▸".encode(
            sys.stdout.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


UNI = _unicode_ok()
if UNI:
    TL, TR, BL, BR, H, V = "┌", "┐", "└", "┘", "─", "│"
    DTL, DTR, DBL, DBR, DH, DV = "╔", "╗", "╚", "╝", "═", "║"
    DOWN, ARROW = "▼", "▸"
else:
    TL = TR = BL = BR = DTL = DTR = DBL = DBR = "+"
    H, V, DH, DV = "-", "|", "=", "|"
    DOWN, ARROW = "v", ">"


# ------------------------------------------------------------------ drawing
def banner(n: str, title: str, subtitle: str) -> None:
    print()
    print("=" * W)
    print(f"  LAYER {n}   {title}")
    print(f"            {subtitle}")
    print("=" * W)


def box(title: str, lines: list[str]) -> None:
    # A content row renders as: V + space + inner + space + V, so every
    # other row must come to inner + 4 as well. Deriving the padding from
    # the rendered header rather than from len(title) keeps the right edge
    # aligned whatever the title is.
    inner = W - 6
    head = f"{TL}{H} {title} "
    print("  " + head + H * max(0, inner + 3 - len(head)) + TR)
    for ln in lines or ["(none)"]:
        print(f"  {V} {ln[:inner].ljust(inner)} {V}")
    print("  " + BL + H * (inner + 2) + BR)


def rows(headers: list[str], data: list[tuple], widths: list[int]) -> None:
    print("  " + "  ".join(h[:w].ljust(w) for h, w in zip(headers, widths)))
    print("  " + "  ".join("-" * w for w in widths))
    for r in data:
        cells = []
        for v, w in zip(r, widths):
            s = f"{v:,}" if isinstance(v, int) else ("" if v is None else str(v))
            cells.append(s[:w].ljust(w))
        print("  " + "  ".join(cells))


# ------------------------------------------------------------------ layer 1
def layer_ontology(db) -> None:
    banner("1", "ONTOLOGY", "the rules: what may exist, and what may connect")

    print("\n  WHAT KINDS OF THINGS MAY EXIST")
    print("  (count = how many are actually in the graph right now)\n")
    rows(["class", "provenance", "key", "count"],
         db.query("""
            SELECT c.name, c.provenance, coalesce(c.key_spec, ''),
                   coalesce(n.cnt, 0)
            FROM class_registry c
            LEFT JOIN (SELECT class, count(*) cnt FROM nodes GROUP BY class) n
                   ON n.class = c.code
            ORDER BY coalesce(n.cnt, 0) DESC, c.name
         """), [16, 11, 18, 12])

    print("\n  WHAT CONNECTIONS ARE ALLOWED")
    print("  Declared BEFORE any data is loaded. An edge that breaks one of")
    print("  these is rejected - it is not a suggestion.\n")
    rows(["relation", "from", "to", "time?", "count"],
         db.query("""
            SELECT r.name,
                   array_to_string(r.domain, '/'),
                   array_to_string(r.range, '/'),
                   CASE WHEN r.temporal THEN 'yes' ELSE '-' END,
                   coalesce(e.cnt, 0)
            FROM relation_registry r
            LEFT JOIN (SELECT rel, count(*) cnt FROM edges GROUP BY rel) e
                   ON e.rel = r.code
            ORDER BY coalesce(e.cnt, 0) DESC, r.name
         """), [14, 14, 16, 5, 11])

    print("\n  WHAT IS ENFORCED")
    print("  severity 1 = our builder is broken, STOPS THE BUILD")
    print("  severity 2 = the source data contradicts itself, repaired")
    print("  severity 3 = worth recording, reported only\n")
    rows(["rule", "sev", "stage", "repair"],
         db.query("""SELECT id, severity, applies_to, repair
                     FROM rule_registry ORDER BY severity, id"""),
         [30, 4, 10, 24])

    # Per-rule counts live in validation_run.summary as JSON, not in their
    # own table, so this reads the most recent run of each stage.
    import json
    runs = db.query("""
        SELECT stage, run_id, summary FROM validation_run v
        WHERE summary IS NOT NULL
          AND run_id = (SELECT max(run_id) FROM validation_run w
                        WHERE w.stage = v.stage AND w.summary IS NOT NULL)
        ORDER BY stage
    """)
    if runs:
        print("\n  LAST CHECK")
        lines = []
        for stage, run_id, blob in runs:
            s = json.loads(blob) if isinstance(blob, str) else (blob or {})
            lines.append(f"stage={stage}  (run {run_id})")
            for rid, d in sorted(s.items(),
                                 key=lambda kv: -kv[1].get("violations", 0)):
                n = d.get("violations", 0)
                lines.append(f"   {rid:<32} sev {d.get('severity','?')}  "
                             f"{n:>10,} violations")
            lines.append("")
        box("result", lines)
    else:
        box("result", ["no validation run recorded yet - run:",
                       "  python ontology/validate.py --stage graph"])


# ------------------------------------------------------------------ layer 2
def pick_service(db) -> str:
    """A service with traffic in both directions - a dull node teaches nothing."""
    return db.one("""
        SELECT n.nkey
        FROM nodes n
        WHERE n.class = class_code('Microservice')
          AND EXISTS (SELECT 1 FROM edges e
                      WHERE e.dst = n.id AND e.rel = rel_code('calls'))
          AND EXISTS (SELECT 1 FROM edges e
                      WHERE e.src = n.id AND e.rel = rel_code('calls'))
        ORDER BY (SELECT count(*) FROM edges e
                  WHERE e.src = n.id AND e.rel = rel_code('calls')) DESC
        LIMIT 1
    """)


def layer_graph(db, svc: str, at: str) -> None:
    banner("2", "KNOWLEDGE GRAPH", "the connections, drawn around one real node")

    nid, cls = db.query("""
        SELECT n.id, c.name FROM nodes n
        JOIN class_registry c ON c.code = n.class
        WHERE n.nkey = ? AND n.class = class_code('Microservice')
    """, [svc])[0]

    print(f"\n  Focus: {svc}   as of {at}")
    print("  Every line below carries a time window. This is the graph AT")
    print("  THAT INSTANT, not a summary of everything that ever happened.\n")

    up = db.query("""
        SELECT n.nkey, coalesce(e.weight, 0), coalesce(e.tag, '-')
        FROM edges e JOIN nodes n ON n.id = e.src
        WHERE e.dst = ? AND e.rel = rel_code('calls')
          AND valid_at(e.valid_from, e.valid_to, CAST(? AS TIMESTAMP))
        ORDER BY e.weight DESC NULLS LAST LIMIT 6
    """, [nid, at])
    box(f"UPSTREAM - who calls {svc}",
        [f"{k:<22} {w:>9,} calls   {t}" for k, w, t in up])

    print(" " * 38 + V)
    print(" " * 38 + DOWN)
    inner = W - 8
    print("  " + DTL + DH * (W - 4) + DTR)
    for ln in (f"{svc:<24} class: {cls}",
               f"id {nid:<21} provenance: measured"):
        print(f"  {DV}  {ln[:inner].ljust(inner)}  {DV}")
    print("  " + DBL + DH * (W - 4) + DBR)
    print(" " * 38 + V)
    print(" " * 38 + DOWN)

    down = db.query("""
        SELECT n.nkey, coalesce(e.weight, 0), coalesce(e.tag, '-'),
               e.stat_p99
        FROM edges e JOIN nodes n ON n.id = e.dst
        WHERE e.src = ? AND e.rel = rel_code('calls')
          AND valid_at(e.valid_from, e.valid_to, CAST(? AS TIMESTAMP))
        ORDER BY e.weight DESC NULLS LAST LIMIT 6
    """, [nid, at])
    box(f"DOWNSTREAM - what {svc} calls",
        [f"{k:<22} {w:>9,} calls   {t:<6} p99 "
         f"{('%.0f ms' % p) if p is not None else '-'}"
         for k, w, t, p in down])

    other = db.query("""
        SELECT r.name, n.nkey
        FROM edges e
        JOIN relation_registry r ON r.code = e.rel
        JOIN nodes n ON n.id = e.dst
        WHERE e.src = ? AND e.rel <> rel_code('calls')
          AND valid_at(e.valid_from, e.valid_to, CAST(? AS TIMESTAMP))
        LIMIT 6
    """, [nid, at])
    if other:
        box("OTHER THINGS IT TOUCHES",
            [f"{rel:<14} {ARROW} {k}" for rel, k in other])

    place = db.query("""
        SELECT ct.nkey, nd.nkey, e2.valid_from, e2.valid_to
        FROM edges e1
        JOIN nodes ct ON ct.id = e1.src
        JOIN edges e2 ON e2.src = e1.src AND e2.rel = rel_code('runs_on')
        JOIN nodes nd ON nd.id = e2.dst
        WHERE e1.dst = ? AND e1.rel = rel_code('instance_of')
          AND valid_at(e2.valid_from, e2.valid_to, CAST(? AS TIMESTAMP))
        LIMIT 5
    """, [nid, at])
    box(f"WHERE IT RUNS   (container {ARROW} runs_on {ARROW} machine)",
        [f"{c:<26} {ARROW} {nd:<12} {str(vf)[11:19]} .. "
         f"{str(vt)[11:19] if vt else 'open'}" for c, nd, vf, vt in place]
        or ["no container of this service reported its machine at this",
            "instant. Only ~6,663 of the 17,656 services in the call graph",
            "also appear in the resource data, so placement is often",
            "unknown. Saying so beats inventing a machine."])

    team = db.query("""
        SELECT t.nkey FROM edges e JOIN nodes t ON t.id = e.src
        WHERE e.dst = ? AND e.rel = rel_code('owns')
          AND valid_at(e.valid_from, e.valid_to, CAST(? AS TIMESTAMP))
    """, [nid, at])
    box("WHO OWNS IT",
        [f"{t[0]:<20}  DERIVED - inferred from the call pattern." for t in team]
        + ["                      There is no org chart in this data."])

    print("\n  SAME QUESTION, DIFFERENT MOMENT")
    print("  This is what a time-stamped graph buys you, and what no")
    print("  dashboard can do: it can only ever show you NOW.\n")
    for t in (DEFAULT_AT, "2022-01-01 00:02:30"):
        n = db.one("""SELECT count(*) FROM edges
                      WHERE src = ? AND rel = rel_code('calls')
                        AND valid_at(valid_from, valid_to, CAST(? AS TIMESTAMP))""",
                   [nid, t])
        print(f"      at {t}   {svc} calls {n} services")


# ------------------------------------------------------------------ layer 3
def layer_semantic(db, svc: str) -> None:
    banner("3", "SEMANTIC LAYER", "the numbers: one definition, one meaning")

    from semantic.compile import MetricCompiler
    mc = MetricCompiler()

    print("\n  THE CATALOGUE - every metric defined ONCE, in metrics.yaml")
    print("  The API, the dashboard and the agent all compile from this file,")
    print("  so 'latency' cannot mean three things in three places.\n")
    rows(["metric", "provenance", "unit", "reads"],
         [(n, m["provenance"], m.get("unit", ""), m.get("source", "the graph"))
          for n in mc.names() for m in [mc.describe(n)]],
         [24, 11, 12, 14])

    m = mc.describe("rt_p99")
    print(f"\n  ONE METRIC, END TO END:  rt_p99   ({m['title']})\n")
    box("1. WHAT YAML SAYS",
        [f"expr:   {m['expr']}", f"filter: {m.get('filter', '-')}",
         f"unit:   {m.get('unit')}        provenance: {m['provenance']}"])

    sql, params = mc.sql("rt_p99", filters={"microservice": svc})
    box("2. THE SQL IT GENERATES", sql.splitlines() + [f"params: {params}"])

    val = db.query(sql, params)
    box("3. THE ANSWER",
        [f"rt_p99 for {svc} = {val[0][0]:,.1f} ms" if val and val[0][0] is not None
         else f"rt_p99 for {svc} = no usable response times"])

    print("\n  WHAT IS DELIBERATELY MISSING")
    box("no error_rate",
        ["This dataset carries no status codes, so an error rate cannot",
         "be computed from it. Defining one anyway would be a fabricated",
         "number wearing a real metric's name.",
         "slow_call_rate is the honest substitute, with the threshold as",
         "an explicit parameter rather than hidden in the definition."])


# ------------------------------------------------------------------ layer 4
def layer_context(db, svc: str, at: str) -> None:
    banner("4", "CONTEXT LAYER", "the packed answer  -  NOT BUILT YET")

    print("\n  This layer assembles the three below into one small bundle an")
    print("  AI can use, inside a hard size limit, with every fact labelled.")
    print("  It is the next thing to build. Shown here is the SHAPE it will")
    print("  produce, filled with real values from the layers that exist.\n")

    nid = db.one("SELECT id FROM nodes WHERE nkey = ? AND class = class_code('Microservice')", [svc])
    fan = db.one("""SELECT count(*) FROM edges WHERE src = ?
                    AND rel = rel_code('calls')
                    AND valid_at(valid_from, valid_to, CAST(? AS TIMESTAMP))""",
                 [nid, at])
    team = db.one("""SELECT t.nkey FROM edges e JOIN nodes t ON t.id = e.src
                     WHERE e.dst = ? AND e.rel = rel_code('owns') LIMIT 1""", [nid])
    p99 = db.one("""SELECT quantile_cont(rt, 0.99) FROM calls
                    WHERE um = ? AND rt IS NOT NULL AND rt >= 0""", [nid])

    box(f"QUESTION:  why was {svc} slow at {at}?",
        ["",
         f"- {svc} calls {fan} services at that instant",
         f"      measured   from the call graph, valid at {at}",
         "",
         f"- its p99 response time is {p99:,.0f} ms" if p99 else "- no response times",
         "      measured   rt_p99, defined in metrics.yaml",
         "",
         f"- {team or 'no team'} owns it",
         "      DERIVED    inferred from the call pattern, not a fact",
         "",
         "- [ a matching past incident report ]",
         "      external   NEEDS LAYER 3b - semantic search",
         "",
         "within a hard token budget, every line carrying its source"])

    print("\n  Each label matters. A reader can tell a measurement from an")
    print("  inference without asking, which is what makes the answer safe")
    print("  to act on at 3am.")


# ------------------------------------------------------------------ main
LAYERS = {"ontology": 1, "graph": 2, "semantic": 3, "context": 4}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--service", help="microservice to focus on")
    ap.add_argument("--at", default=DEFAULT_AT)
    ap.add_argument("--layer", choices=list(LAYERS))
    args = ap.parse_args()

    want = {LAYERS[args.layer]} if args.layer else {1, 2, 3, 4}

    with connect(read_only=True) as db:
        svc = args.service or pick_service(db)
        if not db.one("SELECT count(*) FROM nodes WHERE nkey = ?", [svc]):
            raise SystemExit(f"no such node: {svc}")

        if 1 in want:
            layer_ontology(db)
        if 2 in want:
            layer_graph(db, svc, args.at)
        if 3 in want:
            layer_semantic(db, svc)
        if 4 in want:
            layer_context(db, svc, args.at)

    print()
    print("=" * W)
    print("  1 rules   2 connections   3 numbers   4 the packed answer")
    print("  Layers 1-3 are built. Layer 4 is next.")
    print("=" * W)
    return 0


if __name__ == "__main__":
    sys.exit(main())
