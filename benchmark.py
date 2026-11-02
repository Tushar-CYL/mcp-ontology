"""Baseline benchmark for the current middle layer.

Measures what one source actually costs through all four layers, using only
the public APIs the application itself uses. It changes nothing: it opens a
separate graph file under data/bench_graphs/ and removes it before a cold
build.

    python benchmark.py --source data\\example.db
    python benchmark.py --fixture lake100 --json out.json --md out.md

Stages measured
---------------
connect()            read the source into one Schema
discover()           Schema -> Ontology (classes, keys, relations)
graph build (cold)   rows -> nodes + time-stamped edges, from an empty file
graph reopen (warm)  open the same file again; is_current() must be True
metrics discovered   semantic.discover_metrics()
metrics compiled     semantic.compile_compile_metric() over every metric
metrics executed     a bounded sample actually run against the graph
sample query         p50/p95 latency over ~20 runs of one representative metric
context pack         context.budget.fit() + render() on one real node
total wall time      and the graph file size

Failures are recorded, not raised: a benchmark that dies on the first bad
source cannot report that the failure is the finding. Exit code is 0 when the
whole run completed, 1 when a stage failed (the report is still written).
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from context.budget import Fact, fit, render                      # noqa: E402
from knowledge_graph.build import (build, is_current, row_for,   # noqa: E402
                                   table_ref)
from knowledge_graph.store import open_graph                     # noqa: E402
from ontology.connect import SourceError, connect                # noqa: E402
from ontology.discover import discover                           # noqa: E402
from semantic.compile import compile_metric                      # noqa: E402
from semantic.discover import discover_metrics                   # noqa: E402

GRAPH_DIR = ROOT / "data" / "bench_graphs"
FIXTURES = {"lake100": ROOT / "data" / "fixtures" / "lake100"}
QUERY_RUNS = 20
QUERY_WARMUP = 3
EXECUTE_LIMIT = 25
CONTEXT_BUDGET = 900


# ------------------------------------------------------------------- timing
def _timed(fn):
    """Run fn, return (result, seconds, error-or-None). Never raises."""
    start = time.perf_counter()
    try:
        return fn(), time.perf_counter() - start, None
    except Exception as exc:                     # noqa: BLE001 - report it
        return None, time.perf_counter() - start, _describe(exc)


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    low, high = math.floor(pos), math.ceil(pos)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - pos) + ordered[high] * (pos - low)


def _ms(seconds: float | None) -> float | None:
    return None if seconds is None else round(seconds * 1000.0, 3)


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


# ------------------------------------------------------------------- source
def _resolve_source(args) -> tuple[str, str | None, bool]:
    """Return (source, fixture-name-or-None, generated-fixture?)."""
    if args.source:
        return str(Path(args.source)), None, False
    name = args.fixture or "lake100"
    folder = FIXTURES.get(name)
    if folder is None:
        raise SystemExit(f"unknown fixture {name!r}; known: {', '.join(FIXTURES)}")
    generated = False
    if not folder.exists():
        from benchmarks.fixture_lake100 import generate
        print(f"  fixture {name} not found - generating it first")
        generate(folder, truth_path=None, quiet=True)
        generated = True
    return str(folder), name, generated


def _graph_path(source: str) -> Path:
    slug = "".join(c if c.isalnum() else "_" for c in source)[-60:]
    return GRAPH_DIR / f"bench_{slug}.duckdb"


def _reset_graph(path: Path) -> None:
    for candidate in (path, Path(f"{path}.wal"), Path(f"{path}.tmp")):
        if candidate.exists():
            candidate.unlink()


def _file_bytes(path: Path) -> int:
    total = 0
    for candidate in (path, Path(f"{path}.wal")):
        if candidate.exists():
            total += candidate.stat().st_size
    return total


def _format_counts(schema) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in schema.tables:
        # readers hold SQL like "<reader>('<path>')"; fall back to the reader name
        ref = schema.readers.get(table.name.lower())
        kind = "database"
        if ref:
            if "read_csv" in ref:
                kind = "csv"
            elif "read_parquet" in ref:
                kind = "parquet"
            elif "read_json" in ref:
                kind = "json"
            elif "read_xlsx" in ref:
                kind = "excel"
        counts[kind] = counts.get(kind, 0) + 1
    return counts


# ---------------------------------------------------------------- benchmark
def run(source: str, fixture: str | None, generated: bool) -> dict:
    report: dict = {
        "tool": "benchmark.py",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "fixture": fixture,
        "fixture_generated": generated,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "stages": {},
        "errors": [],
        "findings": [],
        "limits": {"query_runs": QUERY_RUNS, "query_warmup": QUERY_WARMUP,
                   "execute_limit": EXECUTE_LIMIT,
                   "context_budget_chars": CONTEXT_BUDGET},
    }
    try:
        import duckdb
        report["duckdb"] = duckdb.__version__
    except Exception:                             # noqa: BLE001
        report["duckdb"] = None

    started = time.perf_counter()
    stages = report["stages"]

    def fail(stage: str, err: str) -> None:
        report["errors"].append({"stage": stage, "error": err})

    # ------------------------------------------------------------ connect
    schema, seconds, err = _timed(lambda: connect(source))
    connect_stage = {"ok": err is None, "seconds": round(seconds, 6)}
    if err:
        connect_stage["error"] = err
        fail("connect", err)
        stages["connect"] = connect_stage
        report["total_seconds"] = round(time.perf_counter() - started, 6)
        return report
    connect_stage.update({
        "tables": len(schema.tables),
        "rows": sum(t.row_count or 0 for t in schema.tables),
        "formats": _format_counts(schema),
        "name": schema.name,
    })
    stages["connect"] = connect_stage

    # ----------------------------------------------------------- discover
    onto, seconds, err = _timed(lambda: discover(schema))
    discover_stage = {"ok": err is None, "seconds": round(seconds, 6)}
    if err:
        discover_stage["error"] = err
        fail("discover", err)
        stages["discover"] = discover_stage
        report["total_seconds"] = round(time.perf_counter() - started, 6)
        return report
    discover_stage.update({
        "classes": len(onto.classes),
        "relations": len(onto.relations),
        "measured_relations": sum(1 for r in onto.relations.values()
                                  if r.provenance == "measured"),
        "derived_relations": sum(1 for r in onto.relations.values()
                                 if r.provenance != "measured"),
        "renamed_classes": 0,
    })
    stages["discover"] = discover_stage

    # -------------------------------------------------------- graph build
    graph_file = _graph_path(source)
    graph_file.parent.mkdir(parents=True, exist_ok=True)
    _reset_graph(graph_file)

    graph, open_s, err = _timed(lambda: open_graph(graph_file))
    graph_stage: dict = {"ok": err is None, "open_seconds": round(open_s, 6)}
    graph_stats = {"nodes": None, "edges": None, "skipped_edges": None}
    stages["graph"] = graph_stage
    if err:
        graph_stage["error"] = err
        fail("graph open", err)
        report["total_seconds"] = round(time.perf_counter() - started, 6)
        return report

    try:
        graph_stats, build_s, err = _timed(
            lambda: build(graph, schema, onto))
        graph_stage["cold_build_seconds"] = round(build_s, 6)
        if err:
            graph_stage["ok"] = False
            graph_stage["error"] = err
            fail("graph build", err)
            try:                     # a partial graph must not hide the rest
                graph.close()
            except Exception:        # noqa: BLE001
                pass
            graph = open_graph(graph_file)
        else:
            graph_stage["nodes"] = graph_stats.get("nodes")
            graph_stage["edges"] = graph_stats.get("edges")
            graph_stage["skipped_edges"] = graph_stats.get("skipped_edges")
            dangling, dangling_s, dangling_err = _timed(graph.dangling_edges)
            graph_stage["dangling_edges"] = dangling
            graph_stage["dangling_check_seconds"] = round(dangling_s, 6)
            if dangling_err:
                graph_stage["dangling_error"] = dangling_err
                fail("dangling check", dangling_err)
            graph_stage["findings"] = graph.one(
                "SELECT count(*) FROM findings") or 0
            # Keep this handle open for the semantic and context stages: the
            # source is attached to THIS connection by build(). That is the
            # path run.py and the app take on a cold run, so the benchmark
            # must measure the same one.
    except Exception as exc:                    # noqa: BLE001 - never crash
        graph_stage["ok"] = False
        graph_stage["error"] = _describe(exc)
        fail("graph", graph_stage["error"])
        try:
            graph.close()
        except Exception:                       # noqa: BLE001
            pass
        report["total_seconds"] = round(time.perf_counter() - started, 6)
        return report

    # ----------------------------------------------------------- semantic
    metrics, metrics_s, metrics_err = _timed(lambda: discover_metrics(onto))
    semantic: dict = {
        "ok": metrics_err is None,
        "discover_seconds": round(metrics_s, 6),
    }
    stages["semantic"] = semantic
    if metrics_err:
        semantic["error"] = metrics_err
        fail("semantic discover", metrics_err)
        metrics = []

    compiled: list[tuple[object, str, list]] = []
    compile_errors: list[str] = []

    def _compile_all():
        out = []
        for metric in metrics:
            try:
                sql, params = compile_metric(
                    metric, table_sql=table_ref(graph, schema, metric.table))
                out.append((metric, sql, params))
            except Exception as exc:             # noqa: BLE001 - count it
                compile_errors.append(f"{metric.name}: {_describe(exc)}")
        return out

    compiled, compile_s, compile_err = _timed(_compile_all)
    if compile_err:
        compile_errors.append(compile_err)
    semantic["discovered"] = len(metrics)
    semantic["compile_seconds"] = round(compile_s, 6)
    semantic["compiled"] = len(compiled or [])
    semantic["compile_failures"] = len(compile_errors)
    if compile_errors:
        semantic["compile_error_sample"] = compile_errors[:5]

    # Execute a bounded, deterministic slice.
    executed, execute_errors = 0, []
    sample = compiled or []
    for metric, sql, params in sample[:EXECUTE_LIMIT]:
        try:
            graph.sql(sql, params)
            executed += 1
        except Exception as exc:                 # noqa: BLE001 - count it
            execute_errors.append(f"{metric.name}: {_describe(exc)}")
    semantic["executed"] = executed
    semantic["execute_failures"] = len(execute_errors)
    if execute_errors:
        semantic["execute_error_sample"] = execute_errors[:5]

    # One representative metric, timed over ~20 runs.
    sample_sql: str | None = None
    sample_params: list | None = None
    sample_metric = next(
        (c for c in sample
         if c[0].column and c[0].agg in ("sum", "avg", "min", "max")),
        sample[0] if sample else None)
    if sample_metric:
        metric, sql, params = sample_metric
        rows = 0
        try:
            for _ in range(QUERY_WARMUP):
                rows = len(graph.sql(sql, params))
            latencies = []
            for _ in range(QUERY_RUNS):
                t0 = time.perf_counter()
                rows = len(graph.sql(sql, params))
                latencies.append(time.perf_counter() - t0)
            semantic["sample_metric"] = metric.name
            semantic["sample_metric_title"] = metric.title
            semantic["sample_rows"] = rows
            semantic["query_runs"] = len(latencies)
            semantic["query_p50_ms"] = _ms(statistics.median(latencies))
            semantic["query_p95_ms"] = _ms(_percentile(latencies, 0.95))
            semantic["query_min_ms"] = _ms(min(latencies))
            semantic["query_max_ms"] = _ms(max(latencies))
            semantic["sample_sql"] = sql
            sample_sql, sample_params = sql, params
        except Exception as exc:                 # noqa: BLE001 - report it
            semantic["sample_error"] = _describe(exc)
            fail("sample query", semantic["sample_error"])

    # ------------------------------------------------------------ context
    def _pack_context():
        cls = next(iter(onto.classes.values()))
        keys = sorted(graph.keys_of(cls.name, limit=1))
        facts = [Fact(f"{cls.name} exists in {schema.name}.", "measured", 10)]
        if keys:
            key = keys[0]
            for name, value in list(
                    row_for(graph, schema, onto, cls.name, key).items())[:8]:
                if value not in (None, ""):
                    facts.append(Fact(f"Its {name} is {value}.", "measured", 5))
            for reachable in sorted(
                    graph.reach(cls.name, key, None, depth=2))[:12]:
                kind, which = reachable.split(":", 1)
                relation = next(
                    (r for r in onto.relations.values()
                     if kind in (r.range, r.domain)), None)
                facts.append(Fact(
                    f"It connects to {kind} {which}.",
                    relation.provenance if relation else "derived", 3))
        kept = fit(facts, CONTEXT_BUDGET)
        text = render(kept)
        return {
            "class": cls.name,
            "key": keys[0] if keys else None,
            "facts_gathered": len(facts),
            "facts_kept": len(kept),
            "chars": len(text),
        }

    context, context_s, context_err = _timed(_pack_context)
    context_stage: dict = {"ok": context_err is None,
                           "seconds": round(context_s, 6)}
    if context:
        context_stage.update(context)
    if context_err:
        context_stage["error"] = context_err
        fail("context", context_err)
    stages["context"] = context_stage

    # ------------------------------------------------------ warm reopen probe
    try:
        graph.close()
    except Exception:                             # noqa: BLE001
        pass
    graph_stage["file_bytes"] = _file_bytes(graph_file)
    graph_stage["file_mib"] = round(
        graph_stage["file_bytes"] / (1024 * 1024), 3)
    graph_stage["path"] = _rel(graph_file)

    def _warm_probe():
        """Open the graph in a fresh connection, exactly as the app would.

        `is_current` must be True and one metric should execute without a
        rebuild. For a database source the source is attached only by
        build(); a fresh connection has nothing attached, so this probe
        reports that honestly instead of hiding it.
        """
        warm = open_graph(graph_file)
        try:
            current = is_current(warm, schema, onto)
            nodes = warm.one("SELECT count(*) FROM nodes") or 0
            edges = warm.one("SELECT count(*) FROM edges") or 0
            query_ok, query_error = None, None
            if sample_sql is not None:
                try:
                    warm.sql(sample_sql, sample_params or [])
                    query_ok = True
                except Exception as exc:         # noqa: BLE001 - report it
                    query_ok = False
                    query_error = _describe(exc)
            return {"is_current": bool(current), "nodes": nodes,
                    "edges": edges, "query_ok": query_ok,
                    "query_error": query_error}
        finally:
            warm.close()

    probe, warm_s, warm_err = _timed(_warm_probe)
    graph_stage["warm_reopen_seconds"] = round(warm_s, 6)
    if warm_err:
        graph_stage["warm_error"] = warm_err
        fail("graph warm reopen", warm_err)
    else:
        graph_stage["is_current_warm"] = probe["is_current"]
        graph_stage["warm_nodes"] = probe["nodes"]
        graph_stage["warm_edges"] = probe["edges"]
        graph_stage["warm_query_ok"] = probe["query_ok"]
        if probe["query_ok"] is False:
            graph_stage["warm_query_error"] = probe["query_error"]
            report["findings"].append({
                "stage": "warm reopen",
                "finding": (
                    "is_current() is True, but the sample metric cannot run "
                    "on the reopened graph without rebuilding: the source is "
                    "not re-attached to the new connection. This is the "
                    "cached path a second app/run.py process takes."),
                "error": probe["query_error"],
            })

    report["total_seconds"] = round(time.perf_counter() - started, 6)
    return report


# ------------------------------------------------------------------ output
def print_report(report: dict) -> None:
    stages = report["stages"]
    width = 74
    label = report.get("fixture") or report["source"]
    print()
    print("=" * width)
    print(f"  BENCHMARK  {label}")
    print(f"  source: {report['source']}")
    print("=" * width)
    print(f"  {'stage':<26}{'seconds':>10}   detail")
    print(f"  {'-' * 26}{'-' * 10}   {'-' * 30}")

    def row(name: str, seconds, detail: str) -> None:
        secs = "-" if seconds is None else f"{seconds:.4f}"
        print(f"  {name:<26}{secs:>10}   {detail}")

    c = stages.get("connect", {})
    row("connect", c.get("seconds"),
        f"{c.get('tables', '?')} tables, {c.get('rows', 0):,} rows"
        if c.get("ok") else f"FAILED: {c.get('error', '')[:40]}")
    if "discover" not in stages:
        row("discover", None, "not attempted (no readable source)")
    else:
        d = stages["discover"]
        row("discover", d.get("seconds"),
            f"{d.get('classes', '?')} classes, "
            f"{d.get('relations', '?')} relations"
            if d.get("ok") else f"FAILED: {d.get('error', '')[:40]}")
    g = stages.get("graph", {})
    if g.get("ok"):
        row("graph build (cold)", g.get("cold_build_seconds"),
            f"{g.get('nodes')} nodes, {g.get('edges')} edges, "
            f"{g.get('dangling_edges')} dangling")
        row("graph reopen (warm)", g.get("warm_reopen_seconds"),
            f"is_current={g.get('is_current_warm')}, "
            f"sample query runs={g.get('warm_query_ok')}, "
            f"file {g.get('file_mib')} MiB")
    elif "graph" in stages:
        row("graph", None, f"FAILED: {str(g.get('error', ''))[:40]}")
    else:
        row("graph", None, "not attempted")
    s = stages.get("semantic", {})
    if s:
        row("metrics discovered", s.get("discover_seconds"),
            f"{s.get('discovered', 0)} metrics")
        row("metrics compiled", s.get("compile_seconds"),
            f"{s.get('compiled', 0)} ok, {s.get('compile_failures', 0)} failed")
        row("metrics executed", None,
            f"{s.get('executed', 0)} ok, "
            f"{s.get('execute_failures', 0)} failed")
        if s.get("query_p50_ms") is not None:
            row("sample query", (s.get("query_p50_ms", 0) or 0) / 1000,
                f"p50 {s.get('query_p50_ms')} ms, "
                f"p95 {s.get('query_p95_ms')} ms ({s.get('query_runs')} runs)")
    else:
        row("semantic", None, "not attempted")
    x = stages.get("context", {})
    if x:
        row("context pack", x.get("seconds"),
            f"{x.get('facts_kept', '?')} of {x.get('facts_gathered', '?')} "
            f"facts, {x.get('chars', '?')} chars")
    else:
        row("context pack", None, "not attempted")
    print(f"  {'-' * 26}{'-' * 10}   {'-' * 30}")
    row("TOTAL WALL TIME", report.get("total_seconds"), "")
    if report.get("errors"):
        print()
        print(f"  ERRORS ({len(report['errors'])}):")
        for item in report["errors"][:10]:
            print(f"    - {item['stage']}: {item['error'][:60]}")
    if report.get("findings"):
        print()
        print(f"  FINDINGS ({len(report['findings'])}):")
        for item in report["findings"][:6]:
            print(f"    - {item['stage']}: {item['finding'][:66]}")
            print(f"      {str(item.get('error', ''))[:66]}")
    print("=" * width)
    print()


def write_json(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _md_escape(text: str) -> str:
    return str(text).replace("|", r"\|")


def render_markdown(report: dict) -> str:
    stages = report["stages"]
    label = report.get("fixture") or report["source"]
    lines = [f"# Baseline benchmark - {label}", ""]
    lines.append(f"- **Generated:** {report['generated_at']}")
    lines.append(f"- **Source:** `{report['source']}`")
    if report.get("fixture"):
        lines.append(f"- **Fixture:** `{report['fixture']}`"
                     + (" (generated during this run)"
                        if report.get("fixture_generated") else ""))
    lines.append(f"- **Environment:** Python {report.get('python')}, "
                 f"DuckDB {report.get('duckdb')}, {report.get('platform')}")
    lines.append("- **Method:** cold graph build from an empty file; the "
                 "semantic and context stages run on that same connection "
                 "(the path the app takes on its first run); a final warm "
                 "reopen checks `is_current()` and re-runs one metric on a "
                 f"fresh connection. Sample query: first numeric metric, "
                 f"{report['limits']['query_runs']} runs after "
                 f"{report['limits']['query_warmup']} warm-ups.")
    lines += ["", "## Stages", "",
              "| Stage | Seconds | Detail |", "|---|---:|---|"]

    def add(name: str, seconds, detail: str) -> None:
        lines.append(f"| {name} | "
                     f"{'' if seconds is None else f'{seconds:.4f}'} | "
                     f"{_md_escape(detail)} |")

    c = stages.get("connect", {})
    add("connect", c.get("seconds"),
        f"{c.get('tables', '?')} tables, {c.get('rows', 0):,} rows, "
        f"formats {c.get('formats', {})}" if c.get("ok")
        else f"FAILED: {c.get('error', '')}")
    if "discover" not in stages:
        add("discover", None, "not attempted (no readable source)")
    else:
        d = stages["discover"]
        add("discover", d.get("seconds"),
            f"{d.get('classes', '?')} classes, "
            f"{d.get('relations', '?')} relations"
            if d.get("ok") else f"FAILED: {d.get('error', '')}")
    g = stages.get("graph", {})
    if g.get("ok"):
        add("graph build (cold)", g.get("cold_build_seconds"),
            f"{g.get('nodes')} nodes, {g.get('edges')} edges, "
            f"{g.get('skipped_edges')} skipped edges, "
            f"{g.get('dangling_edges')} dangling")
        add("graph reopen (warm)", g.get("warm_reopen_seconds"),
            f"is_current={g.get('is_current_warm')}; sample query runs="
            f"{g.get('warm_query_ok')}; file "
            f"{g.get('file_bytes'):,} bytes ({g.get('file_mib')} MiB)")
    elif "graph" in stages:
        add("graph", None, f"FAILED: {g.get('error', '')}")
    else:
        add("graph", None, "not attempted")
    s = stages.get("semantic", {})
    if s:
        add("metrics discovered", s.get("discover_seconds"),
            f"{s.get('discovered', 0)} metrics")
        add("metrics compiled", s.get("compile_seconds"),
            f"{s.get('compiled', 0)} ok, "
            f"{s.get('compile_failures', 0)} failed")
        add("metrics executed", None,
            f"{s.get('executed', 0)} ok, "
            f"{s.get('execute_failures', 0)} failed "
            f"(first {report['limits']['execute_limit']})")
        if s.get("query_p50_ms") is not None:
            add("sample query (p50)", (s.get("query_p50_ms") or 0) / 1000,
                f"p95 {s.get('query_p95_ms')} ms over "
                f"{s.get('query_runs')} runs")
    else:
        add("semantic", None, "not attempted")
    x = stages.get("context", {})
    if x:
        add("context pack", x.get("seconds"),
            f"{x.get('facts_kept', '?')} of "
            f"{x.get('facts_gathered', '?')} facts, "
            f"{x.get('chars', '?')} chars")
    else:
        add("context pack", None, "not attempted")
    add("**total wall time**", report.get("total_seconds"),
        f"graph file: {g.get('file_bytes', 0):,} bytes" if g.get("ok") else "")

    if s.get("sample_metric"):
        lines += ["", "## Sample query", "",
                  f"- Metric: `{s.get('sample_metric')}` "
                  f"({s.get('sample_metric_title')})",
                  f"- Latency: p50 **{s.get('query_p50_ms')} ms**, "
                  f"p95 **{s.get('query_p95_ms')} ms**, "
                  f"min {s.get('query_min_ms')} ms, "
                  f"max {s.get('query_max_ms')} ms",
                  f"- Runs: {s.get('query_runs')} after "
                  f"{report['limits']['query_warmup']} warm-ups; "
                  f"rows returned: {s.get('sample_rows')}",
                  "", "```sql", str(s.get("sample_sql", "")), "```"]

    if report.get("errors"):
        lines += ["", "## Errors", ""]
        lines += [f"- **{e['stage']}**: {e['error']}" for e in report["errors"]]
    else:
        lines += ["", "## Errors", "", "None. Every stage completed."]

    if report.get("findings"):
        lines += ["", "## Findings", ""]
        for item in report["findings"]:
            lines.append(f"- **{item['stage']}:** {item['finding']}")
            if item.get("error"):
                lines.append(f"  - observed error: `{item['error']}`")
    else:
        lines += ["", "## Findings", "", "None."]

    lines += ["", "## Notes", "",
              "- The graph is deleted before the cold build, so the cold "
              "number always pays the full build.",
              "- The warm number is a fresh process-local reopen of the same "
              "file; `is_current()` compares the source/ontology signature.",
              "- Query latency is the same metric executed repeatedly; it "
              "measures the query path, not discovery.",
              "- The benchmark never modifies application code or the source."]
    if report.get("fixture") == "lake100":
        lines.append("- lake100 is synthetic and deterministic: it is an "
                     "obstacle course for code paths, not a scale claim.")
    return "\n".join(lines) + "\n"


def write_markdown(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(report), encoding="utf-8")


# -------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure the current middle layer on a source or a fixture.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", help="a file, a folder or a database URL")
    group.add_argument("--fixture", help="a built-in fixture, e.g. lake100")
    parser.add_argument("--json", metavar="PATH", help="write the report as JSON")
    parser.add_argument("--md", metavar="PATH", help="write the report as Markdown")
    parser.add_argument("--quiet", action="store_true",
                        help="do not print the table")
    args = parser.parse_args(argv)

    source, fixture, generated = _resolve_source(args)
    report = run(source, fixture, generated)

    if not args.quiet:
        print_report(report)
    if args.json:
        write_json(report, Path(args.json))
        print(f"  wrote {args.json}")
    if args.md:
        write_markdown(report, Path(args.md))
        print(f"  wrote {args.md}")
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
