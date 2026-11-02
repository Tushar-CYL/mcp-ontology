"""Run three deliberately different datasets through the four-layer engine.

One script, one code path: connect -> discover -> graph build, with a compact
report per dataset. The point is to prove the engine is general, not tuned to
one source:

    revenue_huge    5 Parquet files, ~7.6M rows, synthetic warehouse export
    kaggle_olist    9 messy CSVs, ~1.55M rows, real public marketplace data
    cskg_sup_10     a triple-store folder (entities/relations/splits)

Each dataset gets its own graph file under data/graphs so nothing is merged
silently. The revenue dataset is additionally verified with SQL against the
Parquet files themselves, independently of the graph, and its measured 8.4%
West-revenue drop compared with _ground_truth.json.

    python scripts/validate_datasets.py
    python scripts/validate_datasets.py --only revenue_huge
    python scripts/validate_datasets.py --skip-existing
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from knowledge_graph.build import build, is_current          # noqa: E402
from knowledge_graph.store import open_graph                 # noqa: E402
from ontology.connect import connect                         # noqa: E402
from ontology.discover import discover                       # noqa: E402

ROOT = HERE
DEFAULT_GRAPHS = ROOT / "data" / "graphs"
DEFAULT_REPORT = ROOT / "data" / "reports" / "validate_datasets.json"
SPILL_DIR = ROOT / "data" / "tmp" / "validate_duckdb"

PRIOR_MONTH = "2026-09"
CURRENT_MONTH = "2026-10"
TARGET_DROP_PCT = 8.4


@dataclass(frozen=True)
class Dataset:
    name: str
    path: str
    graph: str
    source: str


DATASETS: list[Dataset] = [
    Dataset("revenue_huge", "data/raw/revenue_huge",
            "validate_revenue_huge.duckdb", "revenue_huge"),
    Dataset("kaggle_olist", "data/raw/kaggledata",
            "validate_kaggle_olist.duckdb", "kaggle_olist"),
    Dataset("cskg_sup_10", "data/raw/benchmark/cskg_dataset_sup_10",
            "validate_cskg_sup_10.duckdb", "cskg_sup_10"),
]


# ------------------------------------------------------------------ helpers
def _open_graph(path: Path, memory_limit: str):
    """Open a graph and keep DuckDB inside the machine's memory.

    A revenue-sized build exceeds free RAM on a small machine. A memory limit
    plus a temp directory turns a hard out-of-memory failure into a slower
    build, which is the only useful behaviour for a validation run.
    """
    SPILL_DIR.mkdir(parents=True, exist_ok=True)
    graph = open_graph(path)
    for statement in (f"SET memory_limit = '{memory_limit}'",
                      f"SET temp_directory = '{SPILL_DIR.as_posix()}'"):
        try:
            graph.con.execute(statement)
        except Exception:                          # noqa: BLE001 - optional
            pass
    return graph


def _visible_tables(schema) -> list[tuple[str, int]]:
    """Source tables that became classes, in engine order."""
    return [(t.name, int(t.row_count or 0)) for t in schema.tables
            if not getattr(t, "hidden", False)]


def _graph_counts(graph, source: str) -> tuple[int, int, int]:
    nodes = int(graph.one(
        "SELECT count(*) FROM nodes WHERE source_id = ?", [source]) or 0)
    edges = int(graph.one(
        "SELECT count(*) FROM edges WHERE source_id = ?", [source]) or 0)
    return nodes, edges, int(graph.dangling_edges() or 0)


def _fmt(rows: int | None) -> str:
    return "?" if rows is None else f"{int(rows):,}"


# ------------------------------------------------------- revenue verification
def _verify_revenue(folder: Path) -> dict:
    """Recompute the headline number from Parquet, with no graph involved.

    Completed orders only, `sum(line_revenue)`, exactly as the property is
    defined. The unfiltered sum is also measured, because the semantic layer
    discovers `sum(OrderLine.line_revenue)` with no status filter - a caveat
    that has to be reported rather than hidden.
    """
    import duckdb

    orders = (folder / "orders.parquet").as_posix()
    lines = (folder / "order_lines.parquet").as_posix()
    base = f"""
        SELECT strftime(o.order_date, '%Y-%m') AS ym, o.segment,
               sum(l.line_revenue) AS revenue,
               count(DISTINCT o.order_id) AS orders
        FROM read_parquet('{orders}') o
        JOIN read_parquet('{lines}') l ON l.order_id = o.order_id
        WHERE o.region = 'West'
          AND o.order_date >= DATE '{PRIOR_MONTH}-01'
          AND o.order_date <  DATE '{CURRENT_MONTH}-01' + INTERVAL 1 MONTH
          {{status}}
        GROUP BY 1, 2"""

    con = duckdb.connect(":memory:")
    try:
        con.execute("SET enable_progress_bar = false")
        con.execute(f"SET memory_limit = '{_MEMORY_LIMIT}'")
        completed = con.execute(base.format(
            status="AND o.status = 'completed'")).fetchall()
        every = con.execute(base.format(status="")).fetchall()
    finally:
        con.close()

    def by_segment(rows) -> dict:
        out: dict = {PRIOR_MONTH: {}, CURRENT_MONTH: {}}
        for ym, segment, revenue, orders in rows:
            out[ym][segment] = {"revenue": float(revenue or 0.0),
                                "orders": int(orders or 0)}
        return out

    completed_map = by_segment(completed)
    every_map = by_segment(every)

    def totals(month_map: dict, month: str) -> tuple[float, int]:
        values = month_map[month].values()
        return (sum(v["revenue"] for v in values),
                sum(v["orders"] for v in values))

    prior, prior_orders = totals(completed_map, PRIOR_MONTH)
    current, current_orders = totals(completed_map, CURRENT_MONTH)
    drop = 100.0 * (1.0 - current / prior) if prior else 0.0

    naive_prior, _ = totals(every_map, PRIOR_MONTH)
    naive_current, _ = totals(every_map, CURRENT_MONTH)
    naive_drop = (100.0 * (1.0 - naive_current / naive_prior)
                  if naive_prior else 0.0)

    segments = []
    for segment in sorted(completed_map[CURRENT_MONTH]):
        p = completed_map[PRIOR_MONTH].get(segment, {"revenue": 0.0, "orders": 0})
        c = completed_map[CURRENT_MONTH][segment]
        contribution = (100.0 * (p["revenue"] - c["revenue"]) / prior
                        if prior else 0.0)
        segments.append({
            "segment": segment,
            "prior_revenue": round(p["revenue"], 2),
            "current_revenue": round(c["revenue"], 2),
            "delta_revenue": round(c["revenue"] - p["revenue"], 2),
            "contribution_to_drop_pct": round(contribution, 4),
            "prior_orders": p["orders"],
            "current_orders": c["orders"],
            "order_change_pct": (round(100.0 * (c["orders"] - p["orders"])
                                       / p["orders"], 2)
                                 if p["orders"] else 0.0),
        })
    segments.sort(key=lambda s: s["delta_revenue"])

    truth_path = folder / "_ground_truth.json"
    if not truth_path.exists():
        truth_path = folder.parent.parent / "ground_truth" / f"{folder.name}.json"
    truth = None
    if truth_path.exists():
        try:
            truth = json.loads(truth_path.read_text(encoding="utf-8"))
        except ValueError:
            truth = None

    return {
        "prior_month": PRIOR_MONTH,
        "current_month": CURRENT_MONTH,
        "prior_revenue": round(prior, 2),
        "current_revenue": round(current, 2),
        "drop_pct_exact": round(drop, 6),
        "drop_pct": round(drop, 1),
        "target_drop_pct": TARGET_DROP_PCT,
        "property_holds": round(drop, 1) == TARGET_DROP_PCT,
        "prior_completed_orders": prior_orders,
        "current_completed_orders": current_orders,
        "order_change_pct": (round(100.0 * (current_orders - prior_orders)
                                   / prior_orders, 2)
                             if prior_orders else 0.0),
        "segments_by_decline": segments,
        "naive_drop_pct": round(naive_drop, 4),
        "naive_drop_note": ("sum(OrderLine.line_revenue) with no status filter, "
                            "which is what the semantic layer discovers on "
                            "OrderLine; the property is defined on completed "
                            "orders only"),
        "naive_prior_revenue": round(naive_prior, 2),
        "naive_current_revenue": round(naive_current, 2),
        "ground_truth": truth,
        "ground_truth_matches": bool(
            truth and round(drop, 1) == truth.get("drop_pct")),
    }


# -------------------------------------------------------------- one dataset
def run_dataset(dataset: Dataset, graphs_dir: Path, skip_existing: bool,
                memory_limit: str) -> dict:
    """Connect, discover and build one dataset; return its report row."""
    source_path = ROOT / dataset.path
    result: dict = {"name": dataset.name, "source_path": str(source_path),
                    "source_id": dataset.source,
                    "build_skipped": False, "error": None}

    t0 = time.monotonic()
    schema = connect(str(source_path))
    result["connect_seconds"] = round(time.monotonic() - t0, 2)
    result["tables"] = [{"table": name, "rows": rows}
                        for name, rows in _visible_tables(schema)]
    result["rows"] = sum(rows for _, rows in _visible_tables(schema))
    result["warnings"] = list(schema.warnings)

    t0 = time.monotonic()
    onto = discover(schema)
    result["discover_seconds"] = round(time.monotonic() - t0, 2)
    result["classes"] = sorted(c.name for c in onto.classes.values())
    result["relations"] = sorted(onto.relations)
    result["class_count"] = len(result["classes"])
    result["relation_count"] = len(result["relations"])

    graph_path = graphs_dir / dataset.graph
    result["graph"] = str(graph_path)

    graph = None
    if skip_existing and graph_path.exists():
        graph = _open_graph(graph_path, memory_limit)
        if is_current(graph, schema, onto, source=dataset.source):
            nodes, edges, dangling = _graph_counts(graph, dataset.source)
            graph.close()
            graph = None
            result.update(nodes=nodes, edges=edges, dangling_edges=dangling,
                          build_seconds=None, build_skipped=True)
            result["graph_bytes"] = graph_path.stat().st_size
            return result
        graph.close()
        graph = None
        graph_path.unlink()

    if graph_path.exists():
        graph_path.unlink()                        # force a real cold build

    t0 = time.monotonic()
    graph = _open_graph(graph_path, memory_limit)

    def progress(line: str) -> None:
        # The build prints one line per class and per relation; on a large
        # source this is the difference between "working" and "hung".
        print(f"      {line}", flush=True)

    try:
        stats = build(graph, schema, onto, source=dataset.source,
                      progress=progress)
    finally:
        result["build_seconds"] = round(time.monotonic() - t0, 2)
    nodes, edges, dangling = _graph_counts(graph, dataset.source)
    graph.close()
    result.update(nodes=nodes, edges=edges, dangling_edges=dangling,
                  skipped_edges=int(stats.get("skipped_edges", 0)),
                  build_seconds=result["build_seconds"])
    result["graph_bytes"] = graph_path.stat().st_size
    return result


# ------------------------------------------------------------------ printing
def print_dataset_report(result: dict) -> None:
    name = result["name"]
    print()
    print("=" * 78)
    print(f"[{name}]  {result['source_path']}")
    print("=" * 78)
    if result.get("error"):
        print(f"  FAILED: {result['error']}")
        return

    print(f"  connect   {result['connect_seconds']:>7.2f}s   "
          f"tables {len(result['tables'])}, rows {_fmt(result['rows'])}")
    for table in result["tables"]:
        print(f"      {table['table']:<36}{_fmt(table['rows']):>12}")
    for warning in result["warnings"][:3]:
        print(f"      warning: {warning[:150]}")

    print(f"  discover  {result['discover_seconds']:>7.2f}s   "
          f"classes {result['class_count']}, relations {result['relation_count']}")
    print(f"      classes:   {', '.join(result['classes'])}")
    print(f"      relations: {', '.join(result['relations']) or '(none)'}")

    if result["build_skipped"]:
        print(f"  build     skipped (graph is already current for this source)")
    else:
        print(f"  build     {result['build_seconds']:>7.2f}s   "
              f"(cold, empty graph)")
    print(f"      nodes {_fmt(result['nodes'])}   edges {_fmt(result['edges'])}"
          f"   dangling edges {_fmt(result['dangling_edges'])}"
          + (f"   unmatched refs {_fmt(result.get('skipped_edges'))}"
             if result.get("skipped_edges") else ""))
    size = result.get("graph_bytes")
    print(f"      graph {result['graph']}"
          + (f"  ({size / 1e6:,.1f} MB)" if size else ""))

    verification = result.get("verification")
    if verification:
        v = verification
        print()
        print(f"  verify    West revenue, completed orders, sum(line_revenue)")
        print(f"      {v['prior_month']}  {v['prior_revenue']:>18,.2f}")
        print(f"      {v['current_month']}  {v['current_revenue']:>18,.2f}")
        verdict = "OK" if v["property_holds"] else "MISMATCH"
        print(f"      drop {v['drop_pct_exact']:.4f}%  ->  {v['drop_pct']}%"
              f"   (target {v['target_drop_pct']}%)  [{verdict}]")
        print(f"      West completed orders {v['prior_completed_orders']:,} -> "
              f"{v['current_completed_orders']:,} "
              f"({v['order_change_pct']:+.1f}%)")
        print("      segments by decline (prior -> current, orders):")
        for s in v["segments_by_decline"]:
            print(f"        {s['segment']}  {s['prior_revenue']:>16,.2f} -> "
                  f"{s['current_revenue']:>16,.2f}  "
                  f"{s['delta_revenue']:>+16,.2f}  "
                  f"contrib {s['contribution_to_drop_pct']:+6.2f}pp  "
                  f"orders {s['prior_orders']:>7,} -> {s['current_orders']:>7,} "
                  f"({s['order_change_pct']:+.1f}%)")
        truth = v.get("ground_truth") or {}
        print(f"      ground truth file: drop {truth.get('drop_pct')}% "
              f"(exact {truth.get('drop_pct_exact')}%), matches: "
              f"{v['ground_truth_matches']}")
        print(f"      caveat: unfiltered sum(line_revenue) drop is "
              f"{v['naive_drop_pct']:.4f}% and the level is "
              f"{v['naive_prior_revenue']:,.0f} vs "
              f"{v['prior_revenue']:,.0f} completed-only")


# -------------------------------------------------------------------- main
_MEMORY_LIMIT = "2GB"


def main(argv: list[str] | None = None) -> int:
    global _MEMORY_LIMIT
    parser = argparse.ArgumentParser(
        description="Run connect -> discover -> build on three datasets.")
    parser.add_argument("--only", action="append", default=[],
                        metavar="NAME",
                        help=f"run just these datasets: "
                             f"{', '.join(d.name for d in DATASETS)}")
    parser.add_argument("--skip-existing", action="store_true",
                        help="reuse a graph whose stored signature matches")
    parser.add_argument("--graphs-dir", default=str(DEFAULT_GRAPHS),
                        help="where graph files are written")
    parser.add_argument("--report", default=str(DEFAULT_REPORT),
                        help="JSON report path")
    parser.add_argument("--memory-limit", default="2GB",
                        help="DuckDB memory limit for the graph build")
    args = parser.parse_args(argv)
    _MEMORY_LIMIT = args.memory_limit

    known = {d.name for d in DATASETS}
    unknown = [name for name in args.only if name not in known]
    if unknown:
        parser.error(f"unknown dataset(s): {', '.join(unknown)}; "
                     f"choose from {', '.join(sorted(known))}")
    selected = [d for d in DATASETS if not args.only or d.name in args.only]

    graphs_dir = Path(args.graphs_dir).resolve()
    graphs_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    results: list[dict] = []
    for dataset in selected:
        print(f"\n  reading {dataset.name} from {dataset.path} ...", flush=True)
        try:
            result = run_dataset(dataset, graphs_dir, args.skip_existing,
                                 args.memory_limit)
            if dataset.name == "revenue_huge":
                try:
                    result["verification"] = _verify_revenue(ROOT / dataset.path)
                except Exception as exc:           # noqa: BLE001 - report it
                    result["verification_error"] = (
                        f"{type(exc).__name__}: {exc}")
        except Exception as exc:                   # noqa: BLE001 - one dataset
            result = {"name": dataset.name,
                      "source_path": str(ROOT / dataset.path),
                      "source_id": dataset.source,
                      "error": f"{type(exc).__name__}: {exc}"}
            traceback.print_exc()
        results.append(result)
        print_dataset_report(result)

    elapsed = time.monotonic() - started
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_seconds": round(elapsed, 2),
        "graphs_dir": str(graphs_dir),
        "datasets": results,
        "failures": [r["name"] for r in results
                     if r.get("error")
                     or r.get("verification", {}).get("property_holds") is False],
    }

    report_path = Path(args.report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, indent=2, default=str) + "\n",
                           encoding="utf-8")

    print()
    print("=" * 78)
    for result in results:
        if result.get("error"):
            status = "FAILED"
        elif result.get("build_skipped"):
            status = "ok (cached)"
        else:
            status = "ok"
        extra = ""
        verification = result.get("verification")
        if verification:
            extra = f"   drop {verification['drop_pct']}% " + (
                "OK" if verification["property_holds"] else "MISMATCH")
        print(f"  {result['name']:<16}{status:<14}"
              f"build {result.get('build_seconds') or 0:>8.1f}s"
              f"   nodes {_fmt(result.get('nodes'))}"
              f"   edges {_fmt(result.get('edges'))}{extra}")
    print(f"  total {elapsed:,.1f}s   report {report_path}")
    print("=" * 78)
    return 0 if not summary["failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
