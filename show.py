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
from common import DOMAIN  # noqa: E402
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
def disp(db) -> dict:
    """The domain's own vocabulary, from its ontology.

    The engine must not know that one dataset is about microservices and
    another about aeroplanes. Everything this function returns is read from
    domains/<name>/ontology.yaml, which is what lets the same code draw
    both.
    """
    from common import load_ontology
    d = dict(load_ontology().get("display") or {})
    d.setdefault("focus_class", "Microservice")
    d.setdefault("focus_relation", "calls")
    d.setdefault("upstream_label", "what points at")
    d.setdefault("downstream_label", "what it points at")
    return d


def pick_focus(db, d: dict) -> str:
    """A node with traffic in BOTH directions - a leaf teaches nothing."""
    if d.get("example"):
        return d["example"]
    return db.one(f"""
        SELECT n.nkey FROM nodes n
        WHERE n.class = class_code('{d["focus_class"]}')
          AND EXISTS (SELECT 1 FROM edges e WHERE e.dst = n.id
                      AND e.rel = rel_code('{d["focus_relation"]}'))
          AND EXISTS (SELECT 1 FROM edges e WHERE e.src = n.id
                      AND e.rel = rel_code('{d["focus_relation"]}'))
        ORDER BY (SELECT count(*) FROM edges e WHERE e.src = n.id
                  AND e.rel = rel_code('{d["focus_relation"]}')) DESC
        LIMIT 1
    """)


def layer_graph(db, focus: str, at: str, d: dict) -> None:
    banner("2", "KNOWLEDGE GRAPH", "the connections, drawn around one real node")

    cls, rel = d["focus_class"], d["focus_relation"]
    row = db.query(f"""
        SELECT n.id, c.name FROM nodes n
        JOIN class_registry c ON c.code = n.class
        WHERE n.nkey = ? AND n.class = class_code('{cls}')
    """, [focus])
    if not row:
        print(f"\nno {cls} called {focus!r}")
        return
    nid, cname = row[0]

    print(f"\nFocus: {focus}   as of {at}")
    print("  Every line below carries a time window. This is the graph AT")
    print("  THAT INSTANT, not a summary of everything that ever happened.\n")

    up = db.query(f"""
        SELECT n.nkey, coalesce(e.weight, 0), coalesce(e.tag, '-')
        FROM edges e JOIN nodes n ON n.id = e.src
        WHERE e.dst = ? AND e.rel = rel_code('{rel}')
          AND valid_at(e.valid_from, e.valid_to, CAST(? AS TIMESTAMP))
        ORDER BY e.weight DESC NULLS LAST LIMIT 6
    """, [nid, at])
    box(f"UPSTREAM - {d['upstream_label']} {focus}",
        [f"{k:<22} {w:>9,}   {t}" for k, w, t in up])

    print(" " * 38 + V)
    print(" " * 38 + DOWN)
    inner = W - 8
    print("  " + DTL + DH * (W - 4) + DTR)
    for ln in (f"{focus:<24} class: {cname}",
               f"id {nid:<21} provenance: measured"):
        print(f"  {DV}  {ln[:inner].ljust(inner)}  {DV}")
    print("  " + DBL + DH * (W - 4) + DBR)
    print(" " * 38 + V)
    print(" " * 38 + DOWN)

    down = db.query(f"""
        SELECT n.nkey, coalesce(e.weight, 0), coalesce(e.tag, '-'), e.stat_p99
        FROM edges e JOIN nodes n ON n.id = e.dst
        WHERE e.src = ? AND e.rel = rel_code('{rel}')
          AND valid_at(e.valid_from, e.valid_to, CAST(? AS TIMESTAMP))
        ORDER BY e.weight DESC NULLS LAST LIMIT 6
    """, [nid, at])
    box(f"DOWNSTREAM - {d['downstream_label']} {focus}",
        [f"{k:<22} {w:>9,}   {t:<8} p99 "
         f"{('%.0f' % p) if p is not None else '-'}"
         for k, w, t, p in down])

    other = db.query(f"""
        SELECT r.name, n.nkey
        FROM edges e
        JOIN relation_registry r ON r.code = e.rel
        JOIN nodes n ON n.id = e.dst
        WHERE e.src = ? AND e.rel <> rel_code('{rel}')
          AND valid_at(e.valid_from, e.valid_to, CAST(? AS TIMESTAMP))
        LIMIT 6
    """, [nid, at])
    if other:
        box("OTHER THINGS IT CONNECTS TO",
            [f"{r:<14} {ARROW} {k}" for r, k in other])

    inbound = db.query(f"""
        SELECT r.name, n.nkey, n.class
        FROM edges e
        JOIN relation_registry r ON r.code = e.rel
        JOIN nodes n ON n.id = e.src
        WHERE e.dst = ? AND e.rel <> rel_code('{rel}')
          AND valid_at(e.valid_from, e.valid_to, CAST(? AS TIMESTAMP))
        LIMIT 6
    """, [nid, at])
    if inbound:
        prov = db.query("SELECT name, provenance FROM relation_registry")
        pmap = dict(prov)
        box("WHAT POINTS AT IT",
            [f"{k:<20} {ARROW} {r:<14} "
             f"{'DERIVED - an inference' if pmap.get(r) == 'derived' else ''}"
             for r, k, _ in inbound])

    print("\nSAME QUESTION, DIFFERENT MOMENT")
    print("  This is what a time-stamped graph buys you, and what no")
    print("  dashboard can do: it can only ever show you NOW.\n")
    for t in (d.get("default_as_of", at), d.get("alt_as_of", at)):
        n = db.one(f"""SELECT count(*) FROM edges
                       WHERE src = ? AND rel = rel_code('{rel}')
                         AND valid_at(valid_from, valid_to,
                                      CAST(? AS TIMESTAMP))""", [nid, t])
        print(f"      at {t:<22} {focus} connects to {n}")


# ------------------------------------------------------------------ layer 3
def layer_semantic(db, svc: str, d: dict) -> None:
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

    # Trace whichever metric THIS domain leads with. Naming one here
    # ('rt_p99') tied the shared tool to a single dataset's vocabulary, and
    # the second domain found it immediately.
    cls = d["focus_class"]
    name = next((n for n in mc.names() if n in mc.metrics
                 and cls in (mc.sources[mc.metrics[n]["source"]]
                             .get("refs", {}).values())), None)
    if not name:
        box("no metric to trace",
            [f"no metric in this domain is dimensioned by {cls}"])
        return
    m = mc.describe(name)
    print(f"\n  ONE METRIC, END TO END:  {name}   ({m['title']})\n")
    box("1. WHAT YAML SAYS",
        [f"expr:   {m['expr']}", f"filter: {m.get('filter', '-')}",
         f"unit:   {m.get('unit')}        provenance: {m['provenance']}"])

    src = mc.sources[m["source"]]
    dim = next(k for k, v in src.get("refs", {}).items() if v == cls)
    sql, params = mc.sql(name, filters={dim: svc})
    box("2. THE SQL IT GENERATES", sql.splitlines() + [f"params: {params}"])

    val = db.query(sql, params)
    got = val[0][0] if val else None
    box("3. THE ANSWER",
        [f"{name} for {svc} = {got:,.2f} {m.get('unit','')}"
         if got is not None
         else f"{name} for {svc} = no measurement (correctly NULL, not 0)"])

    print("\n  WHAT THE CATALOGUE DECIDES ONCE")
    box("what this dataset can and cannot support",
        [f"{len(mc.metrics)} fact metrics, {len(mc.graph_metrics)} graph "
         f"metrics, all defined in metrics.yaml.",
         "",
         "Compare the two domains: the flights data records a cancellation",
         "flag on every row, so cancel_rate is real. The microservice data",
         "has no status codes at all, so it has NO error_rate - inventing",
         "one would be a fabricated number wearing a real metric's name.",
         "That is a property of the data, decided here once, rather than",
         "argued about per dashboard.",
         "",
         "(original note, microservice domain:)",
         "slow_call_rate is the honest substitute, with the threshold as",
         "an explicit parameter rather than hidden in the definition."])


# ------------------------------------------------------------------ layer 4
def layer_context(db, svc: str, at: str, d: dict) -> None:
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
    ap.add_argument("--service", help="node to focus on")
    ap.add_argument("--at", help="timestamp; default comes from the domain")
    ap.add_argument("--layer", choices=list(LAYERS))
    args = ap.parse_args()

    want = {LAYERS[args.layer]} if args.layer else {1, 2, 3, 4}

    with connect(read_only=True) as db:
        d = disp(db)
        svc = args.service or pick_focus(db, d)
        at = args.at or d.get("default_as_of") or DEFAULT_AT
        if not svc:
            raise SystemExit(
                f"no {d['focus_class']} has edges yet - build the graph first")
        if not db.one("SELECT count(*) FROM nodes WHERE nkey = ?", [svc]):
            raise SystemExit(f"no such node: {svc}")

        print(f"\ndomain: {DOMAIN}")
        if 1 in want:
            layer_ontology(db)
        if 2 in want:
            layer_graph(db, svc, at, d)
        if 3 in want:
            layer_semantic(db, svc, d)
        if 4 in want:
            layer_context(db, svc, at, d)

    print()
    print("=" * W)
    print("  1 rules   2 connections   3 numbers   4 the packed answer")
    print("  Layers 1-3 are built. Layer 4 is next.")
    print("=" * W)
    return 0


if __name__ == "__main__":
    sys.exit(main())
