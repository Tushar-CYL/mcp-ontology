"""Business semantic layer: approved metric definitions.

The auto-proposed metrics in `semantic/discover.py` are column aggregates. A
**business metric** is different: an owner signs off a definition, it may join
several tables, and every consumer (UI, API, agent) evaluates the same SQL.

A definition stores a `base_sql` that must return:
  * every declared dimension as a column,
  * the time column,
  * a value column used by `value_expr` (normally `SUM(value)`).

Evaluation wraps the base query with filters and grouping. SQL text is stored,
not rebuilt from prose, so what the reviewer approved is exactly what runs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from knowledge_graph.build import ql, qi, table_ref

_DEF_COLUMNS = ("id", "source", "name", "title", "description", "unit",
                "base_sql", "value_expr", "time_column", "dimensions",
                "owner", "status", "version", "created_at")
_DEF_SELECT = ("id, source_id AS source, name, title, description, unit, "
               "base_sql, value_expr, time_column, dimensions, owner, "
               "status, version, created_at")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(source: str, name: str) -> str:
    return hashlib.sha256(f"{source}|{name}".encode()).hexdigest()[:20]


def _row_to_dict(row) -> dict:
    item = dict(zip(_DEF_COLUMNS, row))
    item["dimensions"] = json.loads(item["dimensions"] or "[]")
    return item


def upsert_metric(graph, source: str, name: str, title: str,
                  base_sql: str, value_expr: str,
                  description: str = "", unit: str = "",
                  time_column: str | None = None,
                  dimensions: list[str] | None = None,
                  owner: str = "", status: str = "approved") -> dict:
    """Create or update an approved metric definition for one source."""
    metric_id = _id(source, name)
    dimensions = list(dimensions or [])
    graph.con.execute(
        "DELETE FROM metric_definitions WHERE id = ?", [metric_id])
    graph.con.execute(
        "INSERT INTO metric_definitions(id, source_id, name, title,"
        " description, unit, base_sql, value_expr, time_column, dimensions,"
        " owner, status, version, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [metric_id, source, name, title, description, unit, base_sql,
         value_expr, time_column, json.dumps(dimensions), owner, status, 1,
         _now()])
    return get_definition(graph, name, source)


def list_definitions(graph, source: str | None = None) -> list[dict]:
    if source:
        rows = graph.sql(
            f"SELECT {_DEF_SELECT}" +
            " FROM metric_definitions WHERE source_id = ? ORDER BY name",
            [source])
    else:
        rows = graph.sql(
            f"SELECT {_DEF_SELECT}" +
            " FROM metric_definitions ORDER BY source_id, name")
    return [_row_to_dict(row) for row in rows]


def get_definition(graph, name: str, source: str | None = None) -> dict | None:
    if source:
        rows = graph.sql(
            f"SELECT {_DEF_SELECT}" +
            " FROM metric_definitions WHERE source_id = ? AND name = ?",
            [source, name])
    else:
        rows = graph.sql(
            f"SELECT {_DEF_SELECT}" +
            " FROM metric_definitions WHERE name = ?", [name])
        if len(rows) > 1:
            raise KeyError(
                f"metric {name!r} exists in several sources; pass source")
    return _row_to_dict(rows[0]) if rows else None


def evaluate_definition(graph, name: str, source: str | None = None,
                        filters: dict | None = None,
                        group_by: str | None = None,
                        time_from: str | None = None,
                        time_to: str | None = None,
                        limit: int = 1000) -> dict:
    """Run an approved definition and return columns, rows and the SQL used.

    Filters are bound parameters. A dimension that is not declared is refused
    rather than silently ignored, for the same reason the column compiler
    refuses it: a number from an unnamed column cannot be explained.
    """
    definition = get_definition(graph, name, source)
    if definition is None:
        raise KeyError(f"no approved metric {name!r}")
    if definition["status"] != "approved":
        raise KeyError(
            f"metric {name!r} is {definition['status']!r} and cannot be served")
    allowed = set(definition["dimensions"])
    if definition["time_column"]:
        allowed.add(definition["time_column"])
    for column in [c for c in [group_by] if c] + list((filters or {}).keys()):
        if column not in allowed:
            raise KeyError(
                f"metric {name!r} has no dimension {column!r}; "
                f"available: {', '.join(sorted(allowed))}")

    select = []
    if group_by:
        select.append(f"{qi(group_by)} AS {qi(group_by)}")
    select.append(f"{definition['value_expr']} AS value")
    sql = [f"SELECT {', '.join(select)}",
           f"FROM ({definition['base_sql']}) AS fact"]
    params: list = []
    where = []
    for column, value in (filters or {}).items():
        where.append(f"{qi(column)} = ?")
        params.append(value)
    if time_from:
        where.append(f"{qi(definition['time_column'])} >= ?")
        params.append(time_from)
    if time_to:
        where.append(f"{qi(definition['time_column'])} < ?")
        params.append(time_to)
    if where:
        sql.append("WHERE " + " AND ".join(where))
    if group_by:
        sql.append(f"GROUP BY {qi(group_by)}")
        sql.append("ORDER BY value DESC NULLS LAST")
    sql.append(f"LIMIT {int(limit)}")
    statement = "\n".join(sql)
    rows = graph.sql(statement, params)
    columns = ([group_by] if group_by else []) + ["value"]
    return {"metric": name, "source": definition["source"],
            "columns": columns, "rows": [list(r) for r in rows],
            "sql": statement, "params": params,
            "definition": definition}


def seed_revenue_metric(graph, schema, onto, source: str,
                        owner: str = "finance") -> dict:
    """Create the one business metric this demo story needs.

    Revenue = sum of completed order-line revenue. Refunded and cancelled
    orders are excluded in the base query, and the filters are dimensions, not
    free text.
    """
    orders = table_ref(graph, schema, "orders", source=source)
    lines = table_ref(graph, schema, "order_lines", source=source)
    products = table_ref(graph, schema, "products", source=source)
    base_sql = f"""
        SELECT o.region AS region,
               o.segment AS segment,
               o.channel AS channel,
               p.category AS category,
               CAST(o.order_date AS DATE) AS order_date,
               l.line_revenue AS revenue
        FROM {lines} l
        JOIN {orders} o ON CAST(o.order_id AS VARCHAR) =
                            CAST(l.order_id AS VARCHAR)
        JOIN {products} p ON CAST(p.product_id AS VARCHAR) =
                              CAST(l.product_id AS VARCHAR)
        WHERE o.status = 'completed'
    """
    return upsert_metric(
        graph, source=source, name="revenue", title="Revenue",
        description="Net revenue from completed orders; refunded and "
                    "cancelled orders are excluded.",
        unit="USD", base_sql=base_sql, value_expr="SUM(revenue)",
        time_column="order_date",
        dimensions=["region", "segment", "channel", "category"],
        owner=owner)
