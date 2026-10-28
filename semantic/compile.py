"""Compile semantic/metrics.yaml into SQL.

One definition, every consumer. The notebooks, the FastAPI service, the
visualisation and the agent all call MetricCompiler.sql() rather than
writing their own aggregate, which is what stops "latency" meaning three
different things in three places.

The compiler is deliberately small and refuses rather than guesses:
  * an unknown metric, dimension or filter key raises
  * a dimension not declared for the metric's source raises, instead of
    compiling against a column that happens to share a name
  * filter VALUES are always bound as parameters, never interpolated

Dimension names are resolved per source, and `refs` dimensions accept a
human name ('MS_12345') which is translated through node_id() so no caller
ever handles an internal id.

Usage:
    from semantic.compile import MetricCompiler
    mc = MetricCompiler()
    sql, params = mc.sql("rt_p99", group_by=["microservice"],
                         filters={"rpctype": "rpc"}, limit=10)

CLI:
    python semantic/compile.py --list
    python semantic/compile.py rt_p99 --by microservice --limit 5
    python semantic/compile.py slow_call_rate --by microservice --slow-ms 200
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import load_metrics  # noqa: E402
from db import connect  # noqa: E402

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class MetricCompiler:
    def __init__(self) -> None:
        self.spec = load_metrics()
        self.sources = self.spec["sources"]
        self.metrics = {m["name"]: m for m in self.spec["metrics"]}
        self.graph_metrics = {m["name"]: m
                              for m in self.spec.get("graph_metrics", [])}
        self.params = self.spec.get("parameters", {})

    # ------------------------------------------------------------- lookup
    def names(self) -> list[str]:
        return sorted(list(self.metrics) + list(self.graph_metrics))

    def describe(self, name: str) -> dict:
        m = self.metrics.get(name) or self.graph_metrics.get(name)
        if not m:
            raise KeyError(f"unknown metric {name!r}; "
                           f"known: {', '.join(self.names())}")
        return m

    # ------------------------------------------------------------ compile
    def sql(self, name: str, *,
            group_by: list[str] | None = None,
            filters: dict[str, Any] | None = None,
            t_from: str | None = None,
            t_to: str | None = None,
            bucket: str | None = None,
            as_of: str | None = None,
            limit: int = 100,
            slow_ms: int | None = None) -> tuple[str, list]:
        if name in self.graph_metrics:
            return self._graph_sql(name, as_of=as_of, limit=limit)

        m = self.describe(name)
        src = self.sources[m["source"]]
        table, tcol = src["table"], src["time"]
        dims, refs = src["dimensions"], src.get("refs", {})
        group_by = group_by or []
        filters = filters or {}

        for d in list(group_by) + list(filters):
            if d not in dims and d != "time_bucket":
                raise KeyError(
                    f"metric {name!r} reads {m['source']!r}, which has no "
                    f"dimension {d!r}; available: {', '.join(sorted(dims))}")

        bucket_sql = bucket or "1 minute"
        bucket_seconds = _interval_seconds(bucket_sql)
        slow = slow_ms if slow_ms is not None else \
            self.params.get("slow_ms", {}).get("default", 500)

        expr = (m["expr"]
                .replace("{bucket_seconds}", str(bucket_seconds))
                .replace("{slow_ms}", str(int(slow))))

        select, groups = [], []
        for d in group_by:
            if d == "time_bucket":
                select.append(f"time_bucket(INTERVAL '{bucket_sql}', "
                              f"t.{tcol}, TIMESTAMP '2022-01-01 00:00:00') "
                              f"AS time_bucket")
                groups.append("time_bucket")
            elif d in refs:
                # Present the human-readable key, never the internal id.
                select.append(f"n_{d}.nkey AS {d}")
                groups.append(f"n_{d}.nkey")
            else:
                select.append(f"t.{dims[d]} AS {d}")
                groups.append(f"t.{dims[d]}")
        select.append(f"{expr} AS value")

        joins = [f"LEFT JOIN nodes n_{d} ON n_{d}.id = t.{dims[d]}"
                 for d in group_by if d in refs]

        where, params = [], []
        if m.get("filter"):
            where.append(f"({m['filter']})")
        for d, v in filters.items():
            col = f"t.{dims[d]}"
            if d in refs:
                where.append(f"{col} = node_id({_class_code_sql(refs[d])}, ?)")
            else:
                where.append(f"{col} = ?")
            params.append(v)
        if t_from:
            where.append(f"t.{tcol} >= ?")
            params.append(t_from)
        if t_to:
            where.append(f"t.{tcol} < ?")
            params.append(t_to)

        q = [f"SELECT {', '.join(select)}", f"FROM {table} t"]
        q += joins
        if where:
            q.append("WHERE " + " AND ".join(where))
        if groups:
            q.append("GROUP BY " + ", ".join(groups))
            q.append("ORDER BY value DESC NULLS LAST")
        q.append(f"LIMIT {int(limit)}")
        return "\n".join(q), params

    def _graph_sql(self, name: str, *, as_of: str | None,
                   limit: int) -> tuple[str, list]:
        m = self.graph_metrics[name]
        if not as_of:
            raise ValueError(f"graph metric {name!r} requires as_of")
        sql = (m["sql"]
               .replace("{as_of}", f"TIMESTAMP '{as_of}'")
               .replace("{limit}", str(int(limit))))
        return sql.strip(), []

    # --------------------------------------------------------------- run
    def run(self, db, name: str, **kw) -> tuple[list[str], list[tuple]]:
        sql, params = self.sql(name, **kw)
        cols = db.columns(sql, params)
        return cols, db.query(sql, params)


def _class_code_sql(cls: str) -> str:
    if not IDENT.match(cls):
        raise ValueError(f"bad class name {cls!r}")
    return f"class_code('{cls}')"


def _interval_seconds(s: str) -> int:
    m = re.match(r"^\s*(\d+)\s*(second|minute|hour|day)s?\s*$", s, re.I)
    if not m:
        raise ValueError(f"cannot parse bucket {s!r}")
    n, unit = int(m.group(1)), m.group(2).lower()
    return n * {"second": 1, "minute": 60, "hour": 3600, "day": 86400}[unit]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("metric", nargs="?")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--by", action="append", default=[], help="group by (repeatable)")
    ap.add_argument("--where", action="append", default=[],
                    help="dim=value filter (repeatable)")
    ap.add_argument("--as-of", help="timestamp, required for graph metrics")
    ap.add_argument("--bucket", default="1 minute")
    ap.add_argument("--slow-ms", type=int)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--show-sql", action="store_true")
    args = ap.parse_args()

    mc = MetricCompiler()

    if args.list or not args.metric:
        print(f"{'metric':<24}{'prov':<10}{'unit':<12}source")
        print("-" * 68)
        for n in mc.names():
            m = mc.describe(n)
            print(f"{n:<24}{m['provenance']:<10}{m.get('unit', ''):<12}"
                  f"{m.get('source', 'graph')}")
        return 0

    filters = {}
    for w in args.where:
        k, _, v = w.partition("=")
        filters[k] = v

    with connect(read_only=True) as db:
        sql, params = mc.sql(args.metric, group_by=args.by, filters=filters,
                             as_of=args.as_of, bucket=args.bucket,
                             limit=args.limit, slow_ms=args.slow_ms)
        if args.show_sql:
            print(sql, "\n-- params:", params, "\n")
        cols = db.columns(sql, params)
        rows = db.query(sql, params)
        print("  ".join(f"{c:<22}" for c in cols))
        print("-" * (24 * len(cols)))
        for r in rows:
            print("  ".join(
                f"{(f'{v:,.4f}' if isinstance(v, float) else str(v)):<22}"
                for v in r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
