"""Business semantic layer: approved metric definitions.

A business metric is not a column guess. It has an owner, a definition, a
governed calculation, declared dimensions, a time grain and caveats. Every
surface (UI, API, agent, context builder) evaluates the same SQL.

Definitions can be simple aggregates (`SUM(revenue)`) or ratios
(`SUM(refunded) / SUM(gross)`), because `value_expr` is evaluated over the
base query. Metadata such as currency, precision and direction is carried with
the definition so a consumer never has to guess how to render or compare it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone

from knowledge_graph.build import qi, table_ref

_DEF_COLUMNS = ("id", "source", "name", "title", "description", "unit",
                "base_sql", "value_expr", "time_column", "dimensions",
                "format", "precision", "higher_is_better", "caveats",
                "owner", "status", "version", "created_at")
_DEF_SELECT = ("id, source_id AS source, name, title, description, unit, "
               "base_sql, value_expr, time_column, dimensions, format, "
               "precision, higher_is_better, caveats, owner, status, version, "
               "created_at")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(source: str, name: str) -> str:
    return hashlib.sha256(f"{source}|{name}".encode()).hexdigest()[:20]


def _row_to_dict(row) -> dict:
    item = dict(zip(_DEF_COLUMNS, row))
    item["dimensions"] = json.loads(item["dimensions"] or "[]")
    item["higher_is_better"] = (True if item["higher_is_better"] is None
                                else bool(item["higher_is_better"]))
    item["precision"] = int(item["precision"] or 2)
    item["format"] = item["format"] or "number"
    return item


def upsert_metric(graph, source: str, name: str, title: str,
                  base_sql: str, value_expr: str,
                  description: str = "", unit: str = "",
                  time_column: str | None = None,
                  dimensions: list[str] | None = None,
                  owner: str = "", status: str = "approved",
                  format: str = "number", precision: int = 2,
                  higher_is_better: bool = True,
                  caveats: str = "") -> dict:
    """Create or update a governed metric definition for one source."""
    metric_id = _id(source, name)
    dimensions = list(dimensions or [])
    with graph.lock:
        graph.con.execute(
            "DELETE FROM metric_definitions WHERE id = ?", [metric_id])
        graph.con.execute(
            "INSERT INTO metric_definitions(id, source_id, name, title,"
            " description, unit, base_sql, value_expr, time_column, dimensions,"
            " format, precision, higher_is_better, caveats, owner, status,"
            " version, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [metric_id, source, name, title, description, unit, base_sql,
             value_expr, time_column, json.dumps(dimensions), format,
             int(precision), bool(higher_is_better), caveats, owner, status,
             1, _now()])
    return get_definition(graph, name, source)


# ------------------------------------------------------------- synonyms
# Kept in their own table: upsert_metric deletes and re-inserts the definition
# row on every re-seed, which would silently wipe a synonyms column.
SYNONYM_MAX = 20
SYNONYM_MAX_LEN = 60


def _ensure_synonyms(graph) -> None:
    with graph.lock:
        graph.con.execute(
            "CREATE TABLE IF NOT EXISTS metric_synonyms ("
            " source_id TEXT NOT NULL, name TEXT NOT NULL, synonyms TEXT,"
            " updated_at TEXT, PRIMARY KEY (source_id, name))")


def _synonym_map(graph, source: str | None) -> dict[tuple[str, str], list[str]]:
    _ensure_synonyms(graph)
    if source:
        rows = graph.sql("SELECT source_id, name, synonyms FROM metric_synonyms"
                         " WHERE source_id = ?", [source])
    else:
        rows = graph.sql("SELECT source_id, name, synonyms FROM metric_synonyms")
    return {(r[0], r[1]): json.loads(r[2] or "[]") for r in rows}


def _with_synonyms(graph, items: list[dict], source: str | None) -> list[dict]:
    mapping = _synonym_map(graph, source)
    for item in items:
        item["synonyms"] = list(mapping.get((item["source"], item["name"]), []))
    return items


def _norm_term(text: str) -> str:
    return " ".join(str(text or "").replace("_", " ").lower().split())


def set_synonyms(graph, name: str, source: str, synonyms) -> list[str]:
    """Replace a metric's synonyms. A synonym must not be another metric's
    name, title or synonym, so a word always resolves to one metric."""
    definition = get_definition(graph, name, source)
    if definition is None:
        raise KeyError(f"no metric {name!r} in source {source!r}")
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in synonyms or []:
        text = " ".join(str(value or "").split())
        if not text:
            continue
        if len(text) > SYNONYM_MAX_LEN:
            raise ValueError(f"synonym {text[:20]!r}... is too long "
                             f"(max {SYNONYM_MAX_LEN} characters)")
        key = _norm_term(text)
        if key not in seen:
            seen.add(key)
            cleaned.append(text)
    if len(cleaned) > SYNONYM_MAX:
        raise ValueError(f"a metric may have at most {SYNONYM_MAX} synonyms")
    others = [m for m in list_definitions(graph, source) if m["name"] != name]
    for other in others:
        taken = {_norm_term(other["name"]), _norm_term(other["title"]),
                 *(_norm_term(x) for x in other.get("synonyms") or [])}
        for text in cleaned:
            if _norm_term(text) in taken:
                raise ValueError(f"{text!r} already means metric "
                                 f"{other['name']!r}")
    with graph.lock:
        graph.con.execute(
            "DELETE FROM metric_synonyms WHERE source_id = ? AND name = ?",
            [source, name])
        graph.con.execute(
            "INSERT INTO metric_synonyms(source_id, name, synonyms, updated_at)"
            " VALUES (?, ?, ?, ?)", [source, name, json.dumps(cleaned), _now()])
    return cleaned


def add_synonym(graph, name: str, source: str, synonym: str) -> list[str]:
    definition = get_definition(graph, name, source)
    if definition is None:
        raise KeyError(f"no metric {name!r} in source {source!r}")
    current = list(definition.get("synonyms") or [])
    if _norm_term(synonym) in {_norm_term(x) for x in current}:
        return current
    return set_synonyms(graph, name, source, [*current, synonym])


STATUSES = ("draft", "approved", "deprecated")


def set_status(graph, name: str, source: str, status: str) -> dict:
    """Approve, return to draft or deprecate one metric (a person's decision)."""
    if status not in STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATUSES)}")
    if get_definition(graph, name, source) is None:
        raise KeyError(f"no metric {name!r} in source {source!r}")
    with graph.lock:
        graph.con.execute(
            "UPDATE metric_definitions SET status = ?, version = version + 1"
            " WHERE source_id = ? AND name = ?", [status, source, name])
    return get_definition(graph, name, source)


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
    if not rows:
        return None
    return _with_synonyms(graph, [_row_to_dict(rows[0])], source)[0]


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
    return _with_synonyms(graph, [_row_to_dict(row) for row in rows], source)


def _assert_dimensions(definition: dict, filters: dict | None,
                       group_by: str | None) -> None:
    allowed = set(definition["dimensions"])
    if definition["time_column"]:
        allowed.add(definition["time_column"])
    used = list((filters or {}).keys()) + ([group_by] if group_by else [])
    for column in used:
        if column not in allowed:
            raise KeyError(
                f"metric {definition['name']!r} has no dimension {column!r}; "
                f"available: {', '.join(sorted(allowed))}")


def _run(graph, definition: dict, filters: dict | None,
         group_by: str | None, time_from: str | None, time_to: str | None,
         limit: int) -> tuple[list, list, str, list]:
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
    if time_from and definition.get("time_column"):
        where.append(f"{qi(definition['time_column'])} >= ?")
        params.append(time_from)
    if time_to and definition.get("time_column"):
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
    return [list(row) for row in rows], columns, statement, params


def _previous_window(time_from: str | None,
                     time_to: str | None) -> tuple[str, str] | None:
    if not time_from or not time_to:
        return None
    try:
        start = date.fromisoformat(str(time_from)[:10])
        end = date.fromisoformat(str(time_to)[:10])
    except ValueError:
        return None
    span = end - start
    if span.days <= 0:
        return None
    return ((start - span).isoformat(), start.isoformat())


def evaluate_definition(graph, name: str, source: str | None = None,
                        filters: dict | None = None,
                        group_by: str | None = None,
                        time_from: str | None = None,
                        time_to: str | None = None,
                        limit: int = 1000,
                        compare_previous: bool = False,
                        allow_draft: bool = False) -> dict:
    """Run an approved definition and return the value, SQL and comparison.

    `allow_draft` is for a person previewing a proposed metric before
    approving it; agents and the API's default path never set it.
    """
    definition = get_definition(graph, name, source)
    if definition is None:
        raise KeyError(f"no approved metric {name!r}")
    if definition["status"] != "approved" and not (
            allow_draft and definition["status"] == "draft"):
        raise KeyError(
            f"metric {name!r} is {definition['status']!r} and cannot be served")
    _assert_dimensions(definition, filters, group_by)

    rows, columns, sql, params = _run(
        graph, definition, filters, group_by, time_from, time_to, limit)
    result = {
        "metric": name,
        "source": definition["source"],
        "status": definition["status"],
        "columns": columns,
        "rows": rows,
        "sql": sql,
        "params": params,
        "window": {"from": time_from, "to": time_to},
        "definition": definition,
        "formatted": [_format_value(row[-1], definition) for row in rows],
    }
    if compare_previous and not group_by:
        previous = _previous_window(time_from, time_to)
        if previous is not None:
            prior_rows, _, prior_sql, prior_params = _run(
                graph, definition, filters, None, previous[0], previous[1], 1)
            prior = prior_rows[0][0] if prior_rows else None
            current = rows[0][0] if rows else None
            change = None
            change_pct = None
            if current is not None and prior is not None:
                change = current - prior
                if prior not in (0, None):
                    change_pct = change / prior * 100
            result.update({
                "prior": prior,
                "change": change,
                "change_pct": change_pct,
                "prior_window": {"from": previous[0], "to": previous[1]},
                "prior_sql": prior_sql,
                "prior_params": prior_params,
                "direction": ("up" if change is not None and change > 0
                              else "down" if change is not None and change < 0
                              else "flat"),
            })
    if group_by and time_from and time_to:
        previous = _previous_window(time_from, time_to)
        if previous is not None:
            prior_rows, prior_columns, _, _ = _run(
                graph, definition, filters, group_by, previous[0],
                previous[1], limit)
            result.update({"prior_rows": prior_rows,
                           "prior_columns": prior_columns,
                           "prior_window": {"from": previous[0],
                                            "to": previous[1]}})
    return result


def _format_value(value, definition: dict) -> str:
    if value is None:
        return "—"
    precision = int(definition.get("precision") or 2)
    kind = definition.get("format") or "number"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if kind == "currency":
        return f"${number:,.{precision}f}"
    if kind == "percent":
        return f"{number * 100:,.{precision}f}%"
    if kind == "integer":
        return f"{number:,.0f}"
    return f"{number:,.{precision}f}"


def metric_health(graph, name: str, source: str | None = None) -> dict:
    """Profile the base data behind a metric. This is not a quality guess."""
    definition = get_definition(graph, name, source)
    if definition is None:
        raise KeyError(f"no approved metric {name!r}")
    base = definition["base_sql"]
    checks = []
    rows = int(graph.sql(f"SELECT count(*) FROM ({base}) AS fact")[0][0] or 0)
    checks.append({"name": "Rows available", "passed": rows > 0,
                   "detail": f"{rows:,} base rows"})
    time_col = definition.get("time_column")
    time_min = time_max = None
    if time_col:
        date_row = graph.sql(
            f"SELECT min({qi(time_col)}), max({qi(time_col)})"
            f" FROM ({base}) AS fact")[0]
        time_min, time_max = date_row[0], date_row[1]
        checks.append({
            "name": "Time coverage", "passed": date_row[0] is not None,
            "detail": f"{date_row[0]} to {date_row[1]}"})
        nulls = int(graph.sql(
            f"SELECT count(*) FROM ({base}) AS fact"
            f" WHERE {qi(time_col)} IS NULL")[0][0] or 0)
        checks.append({
            "name": "No missing dates", "passed": nulls == 0,
            "detail": f"{nulls:,} rows without a date", "severity": "warning"})
    dimensions = definition.get("dimensions") or []
    if dimensions:
        details = []
        for dimension in dimensions:
            try:
                distinct = graph.sql(
                    f"SELECT count(DISTINCT {qi(dimension)})"
                    f" FROM ({base}) AS fact")[0][0]
                details.append(f"{dimension}: {int(distinct):,}")
            except Exception:                      # noqa: BLE001
                details.append(f"{dimension}: unavailable")
        checks.append({"name": "Dimensions available", "passed": True,
                       "detail": "; ".join(details)})
    score = round(100 * sum(1 for check in checks if check["passed"])
                  / max(1, len(checks)), 1)
    return {"metric": name, "source": definition["source"], "score": score,
            "checks": checks, "definition": definition,
            "time_min": str(time_min) if time_min is not None else None,
            "time_max": str(time_max) if time_max is not None else None,
            "generated_at": _now()}


TREND_POINTS = 24
GRAINS = ("day", "week", "month", "quarter", "year")


def auto_grain(span_days: float) -> str:
    """The time grain that gives a readable trend for this span of data."""
    if span_days <= 31:
        return "day"
    if span_days <= 180:
        return "week"
    if span_days <= 1100:
        return "month"
    if span_days <= 3000:
        return "quarter"
    return "year"


def metric_time_range(graph, definition: dict) -> tuple:
    """(first, last) date this metric has data for, from the data itself."""
    column = definition.get("time_column")
    if not column:
        return None, None
    row = graph.sql(
        f"SELECT CAST(min({qi(column)}) AS DATE), CAST(max({qi(column)}) AS DATE)"
        f" FROM ({definition['base_sql']}) AS fact")[0]
    return row[0], row[1]


def metric_trend(graph, definition: dict, filters: dict | None = None,
                 time_to: str | None = None, points: int = TREND_POINTS,
                 grain: str = "month") -> list[dict]:
    """Values per period over the data's own history, in ONE grouped query.

    Up to `points` most recent periods that have data, ending before
    `time_to` when given. One scan instead of one query per period matters on
    large sources (500k+ fact rows).
    """
    column = definition.get("time_column")
    if not column:
        return []
    if grain not in GRAINS:
        raise ValueError(f"grain must be one of {', '.join(GRAINS)}")
    where = [f"{qi(column)} IS NOT NULL"]
    params: list = []
    for key, value in (filters or {}).items():
        where.append(f"{qi(key)} = ?")
        params.append(value)
    if time_to:
        where.append(f"{qi(column)} < ?")
        params.append(time_to)
    sql = (f"SELECT CAST(date_trunc('{grain}', CAST({qi(column)} AS TIMESTAMP))"
           f" AS DATE) AS period, {definition['value_expr']} AS value"
           f" FROM ({definition['base_sql']}) AS fact"
           f" WHERE {' AND '.join(where)} GROUP BY 1 ORDER BY 1 DESC"
           f" LIMIT {int(points)}")
    rows = graph.sql(sql, params)
    return [{"period": str(period), "value": value}
            for period, value in reversed(rows)]


def metric_insights(graph, name: str, source: str | None = None,
                    filters: dict | None = None,
                    time_from: str | None = None, time_to: str | None = None,
                    group_by: str | None = None,
                    allow_draft: bool = False,
                    grain: str | None = None) -> dict:
    """Trend, period comparison and contributor analysis in one response.

    Without a period, the comparison is the latest month that has data
    against the month before it.
    """
    definition = get_definition(graph, name, source)
    if definition is None:
        raise KeyError(f"no approved metric {name!r}")
    if not time_from and not time_to and definition.get("time_column"):
        latest = graph.sql(
            f"SELECT CAST(max({qi(definition['time_column'])}) AS DATE)"
            f" FROM ({definition['base_sql']}) AS fact")[0][0]
        if latest is not None:
            start = date(latest.year, latest.month, 1)
            time_from = start.isoformat()
            time_to = date(start.year + (start.month == 12),
                           start.month % 12 + 1, 1).isoformat()
    current = evaluate_definition(
        graph, name, source, allow_draft=allow_draft, filters=filters, time_from=time_from,
        time_to=time_to, compare_previous=False)
    comparison = evaluate_definition(
        graph, name, source, allow_draft=allow_draft, filters=filters, time_from=time_from,
        time_to=time_to, compare_previous=True)
    first, last = metric_time_range(graph, definition)
    if grain is not None and grain not in GRAINS:
        raise ValueError(f"grain must be one of {', '.join(GRAINS)}")
    if grain is None:
        span = (last - first).days if first and last else 0
        grain = auto_grain(span)
    trend_rows = metric_trend(graph, definition, filters=filters,
                              time_to=time_to, grain=grain)
    contributors = []
    dimension = group_by or next(
        (dim for dim in (definition.get("dimensions") or [])
         if dim in ("segment", "region", "category", "channel")),
        (definition.get("dimensions") or [None])[0])
    if dimension:
        grouped = evaluate_definition(
            graph, name, source, allow_draft=allow_draft, filters=filters, group_by=dimension,
            time_from=time_from, time_to=time_to, compare_previous=True)
        prior_map = {}
        if grouped.get("prior_rows"):
            for row in grouped["prior_rows"]:
                prior_map[str(row[0])] = row[1]
        total_change = comparison.get("change")
        for row in grouped["rows"]:
            key, value = str(row[0]), row[1]
            prior = prior_map.get(key)
            change = (value - prior
                      if value is not None and prior is not None else None)
            contributors.append({
                "key": key, "value": value, "prior": prior,
                "change": change,
                "change_pct": (change / prior * 100
                               if change is not None and prior not in (None, 0)
                               else None),
                "contribution_pct": (change / total_change * 100
                                     if change is not None and total_change
                                     not in (None, 0) else None),
            })
        contributors.sort(key=lambda item: (item["change"] is None,
                                            item["change"] or 0))
    return {"metric": name, "definition": definition,
            "current": current, "comparison": comparison,
            "trend": trend_rows, "contributors": contributors,
            "dimension": dimension, "grain": grain,
            "time_range": {"min": str(first) if first else None,
                           "max": str(last) if last else None},
            "generated_at": _now()}


def seed_metric_catalog(graph, schema, onto, source: str,
                        owner: str = "finance") -> list[dict]:
    """Seed the governed metrics needed for a revenue-trust story."""
    orders = table_ref(graph, schema, "orders", source=source)
    lines = table_ref(graph, schema, "order_lines", source=source)
    products = table_ref(graph, schema, "products", source=source)
    join = (f"FROM {lines} l JOIN {orders} o ON CAST(o.order_id AS VARCHAR) ="
            f" CAST(l.order_id AS VARCHAR) JOIN {products} p ON"
            f" CAST(p.product_id AS VARCHAR) = CAST(l.product_id AS VARCHAR)")
    base_dims = ("o.region AS region, o.segment AS segment,"
                 " o.channel AS channel, p.category AS category,"
                 " CAST(o.order_date AS DATE) AS order_date")
    revenue_base = (f"SELECT {base_dims}, o.customer_id AS customer_id,"
                    f" l.line_revenue AS revenue {join}"
                    f" WHERE o.status = 'completed'")
    order_base = (f"SELECT {base_dims}, o.order_id AS order_id,"
                  f" o.customer_id AS customer_id {join}"
                  f" WHERE o.status = 'completed'")
    enriched = (f"SELECT {base_dims}, o.order_id AS order_id,"
                f" o.customer_id AS customer_id,"
                f" SUM(l.line_revenue) AS revenue {join}"
                f" WHERE o.status = 'completed'"
                f" GROUP BY o.region, o.segment, o.channel, p.category,"
                f" CAST(o.order_date AS DATE), o.order_id, o.customer_id")
    refund_base = (f"SELECT {base_dims}, o.order_id AS order_id,"
                   f" SUM(l.line_revenue) AS gross,"
                   f" SUM(CASE WHEN o.status = 'refunded' THEN l.line_revenue"
                   f" ELSE 0 END) AS refunded {join}"
                   f" WHERE o.status IN ('completed','refunded')"
                   f" GROUP BY o.region, o.segment, o.channel, p.category,"
                   f" CAST(o.order_date AS DATE), o.order_id")
    definitions = [
        ("revenue", "Revenue", "Net revenue from completed orders; refunded "
         "and cancelled orders are excluded.", "USD", "SUM(revenue)",
         revenue_base, "currency", 2, True,
         "Excludes refunded and cancelled orders."),
        ("order_volume", "Order volume", "Number of completed orders.",
         "orders", "COUNT(DISTINCT order_id)", order_base, "integer", 0, True,
         "One order is counted once even when it has several lines."),
        ("average_order_value", "Average order value",
         "Revenue divided by completed orders.", "USD",
         "SUM(revenue) / NULLIF(COUNT(DISTINCT order_id), 0)",
         enriched, "currency", 2, True,
         "Sensitive to large orders; inspect the order distribution."),
        ("refund_rate", "Refund rate",
         "Refunded revenue divided by gross revenue.", "%",
         "SUM(refunded) / NULLIF(SUM(gross), 0)", refund_base, "percent", 2,
         False, "Lower is better."),
        ("customer_count", "Customer count",
         "Distinct customers with at least one completed order.", "customers",
         "COUNT(DISTINCT customer_id)", order_base, "integer", 0, True,
         "A customer is counted once per period."),
    ]
    out = []
    for (name, title, description, unit, expr, base, fmt, precision,
         higher, caveats) in definitions:
        out.append(upsert_metric(
            graph, source=source, name=name, title=title,
            description=description, unit=unit, base_sql=base,
            value_expr=expr, time_column="order_date",
            dimensions=["region", "segment", "channel", "category"],
            owner=owner, format=fmt, precision=precision,
            higher_is_better=higher, caveats=caveats))
    return out


def seed_revenue_metric(graph, schema, onto, source: str,
                        owner: str = "finance") -> dict:
    """Backwards-compatible single-metric seed; also seeds the catalog."""
    catalog = seed_metric_catalog(graph, schema, onto, source, owner)
    return next(item for item in catalog if item["name"] == "revenue")
