"""Run all four layers and print what they found.

    python run.py                     a built-in example, made for you
    python run.py mydata.db           your own database
    python run.py path\\to\\csv_folder  a folder of CSV files
    python run.py postgres://user:pass@host/dbname

No virtual environment, no launcher, no extra tools. If `python` works,
this works. With no arguments it builds a small example first, so a fresh
copy of the project always has something to show.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _check_packages() -> None:
    """Say what to run, rather than showing a traceback.

    This is the very first thing a new person hits, and
    "ModuleNotFoundError: No module named 'duckdb'" reads as a crash in
    the program rather than a step not done yet.
    """
    missing = []
    for mod, why in (("duckdb", "reading data"),):
        try:
            __import__(mod)
        except ImportError:
            missing.append(f"{mod} ({why})")
    if missing:
        print()
        print("  The packages are not installed yet.")
        print()
        print("  Run this first, in this folder:")
        print()
        print("      python -m pip install -r requirements.txt")
        print()
        print(f"  Missing: {', '.join(missing)}")
        print()
        raise SystemExit(1)


_check_packages()

from context.budget import Fact, fit, render           # noqa: E402
from knowledge_graph.build import (build, is_current, row_for,  # noqa: E402
                                   table_ref)
from knowledge_graph.store import open_graph           # noqa: E402
from ontology.connect import SourceError, connect      # noqa: E402
from ontology.discover import discover                 # noqa: E402
from semantic.compile import compile_metric            # noqa: E402
from semantic.discover import discover_metrics         # noqa: E402

W = 72


# ----------------------------------------------------------- printing
def _unicode_ok() -> bool:
    """Windows consoles are cp1252 and cannot encode box characters at
    all - printing one raises and kills the program. Test, then adapt."""
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


def rows(headers, data, widths) -> None:
    print("  " + "  ".join(h[:w].ljust(w) for h, w in zip(headers, widths)))
    print("  " + "  ".join("-" * w for w in widths))
    for r in data:
        print("  " + "  ".join(
            (f"{v:,}" if isinstance(v, int) else str(v if v is not None
                                                     else ""))[:w].ljust(w)
            for v, w in zip(r, widths)))


# -------------------------------------------------------- example data
def make_example() -> str:
    """A small shop, built on the spot.

    A fresh clone has no data - it is all gitignored - so with no argument
    there would be nothing to show and the first run would look broken.
    """
    import sqlite3
    path = HERE / "data" / "example.db"
    if path.exists():
        return str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY, name TEXT, city TEXT, country TEXT);
        CREATE TABLE products (
            id INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL);
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(id),
            placed_at TIMESTAMP, status TEXT);
        CREATE TABLE order_lines (
            id INTEGER PRIMARY KEY,
            order_id INTEGER REFERENCES orders(id),
            product_id INTEGER REFERENCES products(id),
            quantity INTEGER, line_total REAL);
        INSERT INTO customers VALUES
            (1,'Ada','London','UK'),(2,'Grace','New York','US'),
            (3,'Alan','Manchester','UK'),(4,'Katherine','Hampton','US');
        INSERT INTO products VALUES
            (1,'Notebook','Stationery',4.50),(2,'Pen','Stationery',1.20),
            (3,'Lamp','Home',22.00),(4,'Mug','Home',8.75);
        INSERT INTO orders VALUES
            (1,1,'2024-01-05 10:00:00','paid'),
            (2,1,'2024-02-11 14:30:00','paid'),
            (3,2,'2024-02-14 09:15:00','refunded'),
            (4,3,'2024-03-02 16:45:00','paid'),
            (5,4,'2024-03-20 11:05:00','paid');
        INSERT INTO order_lines VALUES
            (1,1,1,2,9.00),(2,1,2,5,6.00),(3,2,3,1,22.00),
            (4,3,4,2,17.50),(5,4,1,1,4.50),(6,4,3,2,44.00),
            (7,5,2,10,12.00),(8,5,4,1,8.75);
    """)
    con.commit()
    con.close()
    return str(path)


# ----------------------------------------------------------------- main
def _unique_source_name(schema, used: set[str]) -> str:
    """A source id for display and storage. Two folders called `data` are two
    sources, not one overwriting the other."""
    base = schema.name or "source"
    name, i = base, 2
    while name in used:
        name = f"{base}_{i}"
        i += 1
    used.add(name)
    return name


def _graph_name(sources: list[str]) -> str:
    if len(sources) == 1:
        return "".join(c if c.isalnum() else "_" for c in sources[0])[-60:]
    import hashlib
    digest = hashlib.sha1("|".join(sorted(sources)).encode()).hexdigest()[:12]
    return f"multi_{digest}"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Read any source and show all four layers. Several sources "
                    "can be built into one graph.")
    parser.add_argument("sources", nargs="*", metavar="SOURCE",
                        help="a database file, a folder, a single file, or a "
                             "postgres:// / mysql:// URL")
    parser.add_argument("--source", action="append", default=[],
                        metavar="SOURCE", dest="extra",
                        help="another source (repeatable)")
    args = parser.parse_args()
    sources = list(args.extra) + list(args.sources)
    if not sources:
        sources = [make_example()]
        print("\n  No data source given, so here is a small example.")
        print("  Run `python run.py <your file or folder>` for your own.")

    bundles = []
    used_names: set[str] = set()
    for source in sources:
        print(f"\n  source: {source}")
        try:
            schema = connect(source)
        except SourceError as e:
            print(f"\n  Could not read that source.\n\n{e}\n", file=sys.stderr)
            continue
        for warning in schema.warnings[:5]:
            print(f"  warning: {warning}")
        if len(schema.warnings) > 5:
            print(f"  ... and {len(schema.warnings) - 5} more warnings")
        onto = discover(schema)
        bundles.append((_unique_source_name(schema, used_names),
                        source, schema, onto))
    if not bundles:
        return 1
    if len(sources) > 1:
        print("\n  Several sources requested: building them into one graph.")
        print("  Queries are per source; nothing is merged silently.")

    gdir = HERE / "data" / "graphs"
    gdir.mkdir(parents=True, exist_ok=True)
    graph = open_graph(gdir / f"{_graph_name(sources)}.duckdb")

    # ----------------------------------------------------- 2 (build first)
    print()
    for name, source, schema, onto in bundles:
        if is_current(graph, schema, onto, source=name):
            print(f"  [{name}] already built for this source - opening it.")
            continue
        print(f"  [{name}] building...")
        build(graph, schema, onto, source=name,
              progress=lambda m: print(m, flush=True))

    node_counts = {name: graph.one(
        "SELECT count(*) FROM nodes WHERE source_id = ?", [name]) or 0
        for name, *_ in bundles}
    edge_counts = {name: graph.one(
        "SELECT count(*) FROM edges WHERE source_id = ?", [name]) or 0
        for name, *_ in bundles}

    # ----------------------------------------------------------- 1
    head("1", "ONTOLOGY", "what exists here, and what is allowed")
    for name, source, schema, onto in bundles:
        print(f"\n  SOURCE: {name}   ({schema.origin})")
        print("\n  WHAT KINDS OF THING EXIST")
        print("  Worked out from the source. Nothing was configured.\n")
        rows(["thing", "from table", "identified by", "dated by", "rows"],
             [(c.name, c.table,
               c.key + (" (made up)" if c.key_is_synthetic else ""),
               c.time_column or "-",
               (schema.table(c.table).row_count
                if schema.table(c.table) else 0))
              for c in onto.classes.values()], [16, 18, 18, 14, 8])

        print("\n  WHAT CONNECTS TO WHAT")
        print("  'stated'  = the source declares it")
        print("  'guessed' = we worked it out from the column names, and it is")
        print("              never shown as a fact\n")
        if onto.relations:
            rows(["link", "from", "to", "how", "sure"],
                 [(r.name, r.domain, r.range,
                   "stated" if r.provenance == "measured" else "guessed",
                   f"{r.confidence:.0%}") for r in onto.relations.values()],
                 [20, 16, 16, 9, 5])
        else:
            print("  (none: no foreign keys, and no columns named after tables)")

    # ----------------------------------------------------------- 2 report
    head("2", "KNOWLEDGE GRAPH", "what connects to what, over time")
    print()
    for name, source, schema, onto in bundles:
        rows(["source", "things", "links"], [(name, node_counts[name],
                                              edge_counts[name])],
             [16, 12, 12])
    print()
    rows(["kind", "name", "how", "count"],
         [(k, n, "stated" if p == "measured" else "guessed", c)
          for k, n, p, c in graph.summary() if c], [10, 24, 9, 10])

    bad = graph.dangling_edges()
    box("CHECKED", [
        f"things built        {sum(node_counts.values()):,}",
        f"links built         {sum(edge_counts.values()):,}",
        f"links pointing at nothing  {bad}   "
        + ("<-- our build is wrong" if bad else "(good)")])

    nodes, edges = graph.subgraph(limit=120)
    if edges:
        busiest = max(nodes, key=lambda n: n["degree"])
        print(f"\n  Busiest thing in a sample of {len(edges)} links:")
        box(f"{busiest['class']} {busiest['key']}",
            [f"{busiest['degree']} links"]
            + [f"{ARROW} {e['relation']} {ARROW} {e['target']}"
               for e in edges if e["source"] == busiest["id"]][:6])

    # ----------------------------------------------------------- 3
    # Metrics and the answer sample come from the FIRST source. Multi-source
    # metric routing is part of the cross-source work, not a silent guess.
    name, source, schema, onto = bundles[0]
    head("3", "SEMANTIC", "the numbers, defined once"
         + (f"  (source: {name})" if len(bundles) > 1 else ""))
    metrics = discover_metrics(onto)
    print(f"\n  {len(metrics)} metrics, every one from a column that is")
    print("  actually there. Nothing is invented.\n")
    rows(["metric", "what it does", "on"],
         [(m.name, m.title[:34], m.table) for m in metrics[:12]],
         [24, 36, 18])
    if len(metrics) > 12:
        print(f"  ... and {len(metrics) - 12} more")

    numeric = [m for m in metrics if m.column and m.agg == "sum"]
    if numeric:
        m = numeric[0]
        sql, params = compile_metric(
            m, table_sql=table_ref(graph, schema, m.table, source=name))
        got = graph.sql(sql, params)
        box(f"EXAMPLE:  {m.name}",
            [f"{m.title}", "",
             f"answer: {got[0][0] if got and got[0][0] is not None else 'no data'}",
             "", "the SQL it wrote:"] + sql.splitlines())

    # ----------------------------------------------------------- 4
    head("4", "CONTEXT", "the packed answer"
         + (f"  (source: {name})" if len(bundles) > 1 else ""))
    first = next(iter(onto.classes))
    keys = sorted(graph.keys_of(first, limit=1, source=name))
    if keys:
        key = keys[0]
        facts = [Fact(f"{first} {key} exists in {schema.name}.", "measured", 10)]
        for k, v in list(row_for(graph, schema, onto, first, key,
                                 source=name).items())[:6]:
            if v not in (None, ""):
                facts.append(Fact(f"Its {k} is {v}.", "measured", 5))
        for r in sorted(graph.reach(first, key, None, depth=2,
                                    source=name))[:8]:
            kind, which = r.split(":", 1)
            rel = next((x for x in onto.relations.values()
                        if kind in (x.range, x.domain)), None)
            facts.append(Fact(f"It connects to {kind} {which}.",
                              rel.provenance if rel else "derived", 3))
        kept = fit(facts, 900)
        print(f"\n  Everything known about one {first}, cut to 900 characters.")
        print("  Every line says where it came from.\n")
        print(render(kept))
        print(f"\n  {len(kept)} of {len(facts)} facts fit. When something must")
        print("  go, a guess is dropped before a measurement.")

    print(f"\n{'=' * W}")
    print("  1 what exists   2 how it connects   3 what to measure"
          "   4 the answer")
    print("  For the same thing on a screen:   python ui.py")
    print("=" * W + "\n")
    graph.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

