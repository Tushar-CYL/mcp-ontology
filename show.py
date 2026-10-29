"""Connect to anything, print what the four layers found.

    python show.py shop.db
    python show.py data/                 a folder of CSVs
    python show.py sales.csv
    python show.py postgres://user@host/db

Nothing here is specific to any dataset. The same command reads a shop, a
library or a warehouse, because every layer works from what the source
itself declares.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from knowledge_graph.build import build
from knowledge_graph.store import open_graph
from ontology.connect import SourceError, connect
from ontology.discover import discover

W = 72


def _unicode_ok() -> bool:
    """Windows consoles are cp1252 and cannot encode box characters at all -
    printing one raises and kills the program. Test, then fall back."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        "┌─│→".encode(sys.stdout.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


UNI = _unicode_ok()
TL, TR, BL, BR, H, V = ("┌", "┐", "└", "┘", "─", "│") if UNI else \
                       ("+", "+", "+", "+", "-", "|")
ARROW = "→" if UNI else "->"


def head(n: str, title: str, sub: str) -> None:
    print(f"\n{'=' * W}\n  LAYER {n}  {title}\n           {sub}\n{'=' * W}")


def box(title: str, lines: list[str]) -> None:
    inner = W - 6
    bar = f"{TL}{H} {title} "
    print("  " + bar + H * max(0, inner + 3 - len(bar)) + TR)
    for ln in lines or ["(none)"]:
        print(f"  {V} {str(ln)[:inner].ljust(inner)} {V}")
    print("  " + BL + H * (inner + 2) + BR)


def table(headers, rows, widths) -> None:
    print("  " + "  ".join(h[:w].ljust(w) for h, w in zip(headers, widths)))
    print("  " + "  ".join("-" * w for w in widths))
    for r in rows:
        print("  " + "  ".join(
            (f"{v:,}" if isinstance(v, int) else str(v or ""))[:w].ljust(w)
            for v, w in zip(r, widths)))


# ------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="file, folder, or database URL")
    ap.add_argument("--graph", default="data/graph.duckdb")
    ap.add_argument("--name", action="append", default=[],
                    help="rename a table's class: --name customers=Buyer")
    args = ap.parse_args()

    names = dict(n.split("=", 1) for n in args.name if "=" in n)

    try:
        schema = connect(args.source)
    except SourceError as e:
        print(f"\nCould not read the source.\n\n{e}\n", file=sys.stderr)
        return 1

    print(f"\n  source: {args.source}")
    print(f"  tables: {len(schema.tables)}")

    # -------------------------------------------------------- LAYER 1
    head("1", "ONTOLOGY", "what exists here, and what is allowed")
    onto = discover(schema, names=names)

    print("\n  WHAT KINDS OF THINGS EXIST")
    print("  Worked out from the source. Nothing was configured.\n")
    table(["thing", "from table", "key", "when", "rows"],
          [(c.name, c.table, c.key + (" (made up)" if c.key_is_synthetic else ""),
            c.time_column or "-",
            (schema.table(c.table).row_count if schema.table(c.table) else 0))
           for c in onto.classes.values()],
          [18, 16, 16, 12, 8])

    print("\n  WHAT CONNECTS TO WHAT")
    print("  'stated' = the source declares it. 'guessed' = we worked it")
    print("  out from the column names, and it is never shown as a fact.\n")
    table(["link", "from", "to", "how", "sure"],
          [(r.name, r.domain, r.range,
            "stated" if r.provenance == "measured" else "guessed",
            f"{r.confidence:.0%}") for r in onto.relations.values()],
          [18, 16, 16, 9, 6])

    # -------------------------------------------------------- LAYER 2
    head("2", "KNOWLEDGE GRAPH", "the connections, with time on them")
    g = open_graph(args.graph)
    print()
    stats = build(g, schema, onto, progress=lambda m: print(m, flush=True))

    print()
    table(["kind", "name", "how", "count"],
          [(k, n, "stated" if p == "measured" else "guessed", c)
           for k, n, p, c in g.summary() if c],
          [10, 22, 9, 10])

    bad = g.dangling_edges()
    box("CHECKED", [
        f"links built          {stats['edges']:,}",
        f"things built         {stats['nodes']:,}",
        f"links pointing at nothing   {bad}   "
        + ("<-- our build is wrong" if bad else "(good)"),
        f"rows whose link had no match  {stats['skipped_edges']:,}"
        + ("   <-- a fact about the data, not an error"
           if stats['skipped_edges'] else ""),
    ])

    # One real example, so the graph is something you look at rather than
    # a row count you take on trust.
    if onto.relations:
        rel = next(iter(onto.relations.values()))
        start = g.one("SELECT nkey FROM nodes WHERE class = ? LIMIT 1",
                      [onto.classes[rel.domain].code])
        if start:
            print(f"\n  AN EXAMPLE: one {rel.domain}, and what it reaches\n")
            box(f"{rel.domain} {start}",
                [f"{ARROW} {x}" for x in
                 sorted(g.reach(rel.domain, start, None, depth=3))[:10]]
                or ["(connected to nothing)"])

    # -------------------------------------------------------- LAYER 3/4
    head("3", "SEMANTIC", "the numbers, defined once  -  NOT BUILT YET")
    print("\n  Found while reading the source, ready to become metrics:\n")
    table(["thing", "numbers you could measure", "ways to group them"],
          [(c.name, ", ".join(c.measures[:4]) or "-",
            ", ".join(c.dimensions[:4]) or "-")
           for c in onto.classes.values()], [16, 30, 20])

    head("4", "CONTEXT", "the packed answer  -  NOT BUILT YET")
    print("\n  Will assemble the three above into one small, labelled")
    print("  bundle an AI can use, inside a hard size limit.\n")

    print("=" * W)
    print("  1 rules   2 connections   3 numbers   4 the answer")
    print(f"  Layers 1 and 2 work on any source. Graph: {args.graph}")
    print("=" * W)
    g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
