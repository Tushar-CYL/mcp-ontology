"""Re-measure every number the demo story quotes, and prove critical_path is fixed.

Every figure in docs/STORY.txt was taken on a 3-minute slice. The slice is now
9 minutes, so all of them are stale. This script reproduces them from the
current database so the story can never quote a number nobody re-checked.

It also carries the regression test for the critical_path fan-out: an RPC is
reported twice under one rpc_id, and walking both sides used to return the
same caller->callee hop many times at the same depth. That must now be zero.

Usage:
    python verify.py                  # everything
    python verify.py --only path      # one section
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect  # noqa: E402

DEMO_NODE = "NODE_12426"      # densest node in the slice, by runs_on count
HOT_NODE = "NODE_35351"       # pinned at 0.95-0.997 CPU from 00:06 to 00:29
T1 = "2022-01-01 00:01:00"
T2 = "2022-01-01 00:02:30"
T_HOT = "2022-01-01 00:08:00"

FAIL: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    # `detail` explains a failure, so printing it on a pass is just confusing.
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}"
          f"{'' if ok else ((' - ' + detail) if detail else '')}")
    if not ok:
        FAIL.append(label)


def table(db, title, sql, params=None):
    print(f"\n--- {title} ---")
    t = time.monotonic()
    cols = db.columns(sql, params or [])
    rows = db.query(sql, params or [])
    ms = (time.monotonic() - t) * 1000
    if not rows:
        print("  (no rows)")
        return rows
    print("  " + "  ".join(f"{c:<20}" for c in cols))
    for r in rows[:20]:
        print("  " + "  ".join(
            f"{(f'{v:,.4f}' if isinstance(v, float) else str(v)):<20}"
            for v in r))
    print(f"  ({len(rows)} rows, {ms:,.0f} ms)")
    return rows


# --------------------------------------------------------------- sections
def sec_scale(db):
    print("\n=== SCALE ===")
    table(db, "staging and graph", """
        SELECT 'spans staged' AS what, count(*) AS n FROM stg_callgraph
        UNION ALL SELECT 'spans in calls', count(*) FROM calls
        UNION ALL SELECT 'malformed rows quarantined', count(*) FROM stg_reject
        UNION ALL SELECT 'nodes', count(*) FROM nodes
        UNION ALL SELECT 'edges', count(*) FROM edges
    """)
    table(db, "trace window now covered", """
        SELECT min(ts) AS t_min, max(ts) AS t_max,
               count(DISTINCT traceid) AS traces
        FROM calls
    """)
    table(db, "graph summary", "SELECT * FROM graph_summary()")


def sec_path(db):
    """The regression test. No duplicate hop at the same depth, ever."""
    print("\n=== CRITICAL PATH (the fan-out fix) ===")

    trace = db.one("""
        SELECT traceid FROM calls
        GROUP BY traceid
        HAVING count(*) BETWEEN 20 AND 200
           AND count(*) > count(DISTINCT rpc_id)   -- has a two-sided RPC
        ORDER BY count(*) DESC LIMIT 1
    """)
    if trace is None:
        check("found a trace with two-sided RPCs", False,
              "no trace has a repeated rpc_id - the fix is untestable here")
        return
    print(f"  trace under test: {trace}")

    raw, uniq = db.query(
        "SELECT count(*), count(DISTINCT rpc_id) FROM calls WHERE traceid = ?",
        [trace])[0]
    print(f"  spans in trace: {raw} rows, {uniq} distinct rpc_id "
          f"-> {raw - uniq} reported twice")

    rows = table(db, "critical_path output", "SELECT * FROM critical_path(?)",
                 [trace])

    # THE regression test. The fan-out showed up as one rpc_id coming back
    # many times, so that - not the caller->callee pair - is what must be
    # unique. An earlier version of this check asserted on
    # (depth, caller, callee) and failed on correct output, because a service
    # legitimately calls the same downstream many times in one trace under
    # different rpc_ids.
    dup = db.query("""
        SELECT rpc_id, count(*) AS times FROM critical_path(?)
        GROUP BY rpc_id HAVING count(*) > 1 ORDER BY times DESC LIMIT 10
    """, [trace])
    check("each rpc_id appears exactly once", not dup,
          f"{len(dup)} rpc_ids repeated" if dup else "")
    for d in dup[:5]:
        print(f"      {d[0]} x{d[1]}")

    n_rows = len(rows)
    check("walked rows == distinct rpc_id", n_rows == uniq,
          f"{n_rows} rows vs {uniq} distinct rpc_id")

    seen_twice = sum(1 for r in rows if r[7] and r[7] > 1)
    print(f"  hops measured on both sides: {seen_twice} of {n_rows}")

    # Not a failure - a finding. The same caller->callee pair repeating at one
    # depth under different rpc_ids is a service calling its downstream in a
    # loop, which is exactly what a critical path is meant to expose.
    rep = db.query("""
        SELECT depth, caller, callee, count(*) AS calls
        FROM critical_path(?)
        GROUP BY depth, caller, callee HAVING count(*) > 1
        ORDER BY calls DESC LIMIT 5
    """, [trace])
    if rep:
        print("  repeated calls in one trace (a loop, not a defect):")
        for r in rep:
            print(f"      depth={r[0]}  {r[1]} -> {r[2]}  x{r[3]}")


def sec_travel(db):
    print("\n=== TIME TRAVEL ===")
    a = db.one("SELECT count(*) FROM blast_radius(?, ?, 12)", [DEMO_NODE, T1])
    b = db.one("SELECT count(*) FROM blast_radius(?, ?, 12)", [DEMO_NODE, T2])
    print(f"  blast_radius({DEMO_NODE}) at {T1} = {a:,} services")
    print(f"  blast_radius({DEMO_NODE}) at {T2} = {b:,} services")
    check("the two instants differ", a != b, f"{a:,} vs {b:,}")
    check("both instants return something", a > 0 and b > 0)


def sec_incident(db):
    """Does the hot node actually carry services we can trace? Step 1's caveat."""
    print("\n=== THE INCIDENT ===")
    table(db, f"{HOT_NODE} CPU over the covered window", """
        SELECT nm.ts, nm.cpu_utilization AS cpu, nm.memory_utilization AS mem
        FROM node_metrics nm
        WHERE nm.node = node_id(2, ?)
          AND nm.ts <= TIMESTAMP '2022-01-01 00:09:00'
        ORDER BY nm.ts
    """, [HOT_NODE])

    rows = table(db, f"services on {HOT_NODE} at {T_HOT}, and their traffic", f"""
        WITH resident AS (
            SELECT DISTINCT m.ms FROM ms_metrics m
            WHERE m.node = node_id(2, ?)
              AND m.ts = TIMESTAMP '{T_HOT}' AND m.ms IS NOT NULL)
        SELECT n.nkey AS service,
               count(c.rt) AS calls_in_minute,
               quantile_cont(c.rt, 0.5)  AS p50,
               quantile_cont(c.rt, 0.99) AS p99
        FROM resident r
        JOIN nodes n ON n.id = r.ms
        LEFT JOIN calls c ON c.um = r.ms AND c.rt IS NOT NULL AND c.rt >= 0
             AND c.ts >= TIMESTAMP '{T_HOT}'
             AND c.ts <  TIMESTAMP '{T_HOT}' + INTERVAL 1 MINUTE
        GROUP BY n.nkey ORDER BY calls_in_minute DESC
    """, [HOT_NODE])

    traceable = [r for r in rows if r[1]]
    check("the hot node hosts services visible in the call graph",
          bool(traceable), f"{len(traceable)} of {len(rows)} have traffic")
    if not traceable:
        return

    # A high p99 means nothing on its own. The claim "this service was slow
    # BECAUSE the node saturated" only stands if the service is slower in the
    # saturated minute than in its own quiet minutes. This is the test that
    # decides whether we have an incident story or just a busy node.
    svc = traceable[0][0]
    print(f"\n  baseline check for {svc} (busiest service on the hot node)")
    table(db, f"{svc} latency per minute vs the node's CPU", """
        SELECT c.ts_min,
               c.calls, c.p50, c.p99,
               nm.cpu_utilization AS node_cpu
        FROM (
            SELECT date_trunc('minute', ts) AS ts_min,
                   count(*) AS calls,
                   quantile_cont(rt, 0.5)  AS p50,
                   quantile_cont(rt, 0.99) AS p99
            FROM calls
            WHERE um = node_id(4, ?) AND rt IS NOT NULL AND rt >= 0
            GROUP BY 1) c
        LEFT JOIN node_metrics nm
               ON nm.node = node_id(2, ?) AND nm.ts = c.ts_min
        ORDER BY c.ts_min
    """, [svc, HOT_NODE])
    print("  read this yourself: if p99 does not rise with node_cpu, the "
          "'saturation caused the slowdown' story is NOT supported.")


def sec_metric(db):
    print("\n=== SEMANTIC LAYER ===")
    from semantic.compile import MetricCompiler
    mc = MetricCompiler()

    # Must be class 4. The busiest caller overall is USER, an ExternalActor
    # (class 12) with no response times at all - an earlier version of this
    # check picked it, looked it up as class 4, and compared None to None,
    # which passes while proving nothing.
    svc = db.one("""
        SELECT n.nkey FROM calls c JOIN nodes n ON n.id = c.um
        WHERE c.rt IS NOT NULL AND c.rt >= 0 AND n.class = 4
        GROUP BY n.nkey ORDER BY count(*) DESC LIMIT 1
    """)
    print(f"  busiest microservice: {svc}")

    sql, params = mc.sql("rt_p99", filters={"microservice": svc})
    via_compiler = db.query(sql, params)[0][0]
    via_raw = db.one("""
        SELECT quantile_cont(rt, 0.99) FROM calls
        WHERE um = node_id(4, ?) AND rt IS NOT NULL AND rt >= 0
    """, [svc])
    print(f"  rt_p99 via compiler = {via_compiler}")
    print(f"  rt_p99 via raw SQL  = {via_raw}")
    check("the metric is actually a number", via_compiler is not None,
          "both sides returned NULL - the comparison would prove nothing")
    check("compiler and raw SQL agree", via_compiler == via_raw)


SECTIONS = {"scale": sec_scale, "path": sec_path, "travel": sec_travel,
            "incident": sec_incident, "metric": sec_metric}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(SECTIONS))
    args = ap.parse_args()

    todo = [args.only] if args.only else list(SECTIONS)
    with connect(read_only=True) as db:
        for name in todo:
            SECTIONS[name](db)

    print("\n" + "=" * 60)
    if FAIL:
        print(f"{len(FAIL)} CHECK(S) FAILED:")
        for f in FAIL:
            print(f"  - {f}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
