"""The agent's read-only toolbelt: every number in an answer starts here.

An agent may not query the warehouse in prose. It asks a tool, the tool runs
an approved metric definition or a bounded graph/source read, and the tool
returns the number *and* the citation that explains where it came from. A
language model is never trusted to compute anything.

Each tool returns the same envelope:

    {"tool", "args", "result", "evidence": [
        {"text", "provenance", "citation", "value"?}], "sql"?, "latency_ms"}

`provenance` is "measured" when the number comes straight out of an approved
definition or a source row, and "derived" when it is arithmetic over measured
facts (a change, a percentage, a comparison).

The registry is bound to exactly one source, so a tool cannot wander outside
the agent's scope even if a prompt asks it to. The tools are read-only by
construction: metric definitions are checked for write/DDL keywords before
their SQL is wrapped, and the only direct SQL built here is SELECT.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from agent.guardrails import is_pii_column
from knowledge_graph.build import qi, source_rows as _build_source_rows, source_slug, table_ref
from semantic import definitions as metric_defs

TOOL_NAMES = (
    "metric_value",
    "metric_breakdown",
    "metric_compare",
    "metric_trend",
    "graph_neighbours",
    "source_rows",
    "context_pack",
    "row_count",
    "row_count_compare",
    "metric_latest_period",
)

TOOL_DESCRIPTIONS = {
    "metric_value": "One approved metric value for a time window, with the "
                    "definition and SQL it came from.",
    "metric_breakdown": "An approved metric split by a declared dimension.",
    "metric_compare": "An approved metric in two windows, by dimension, with "
                      "the change and percentage change.",
    "metric_trend": "An approved metric over time at a chosen grain.",
    "graph_neighbours": "Links and neighbours of one entity in the graph.",
    "source_rows": "A small sample of the real source rows behind a table.",
    "context_pack": "The cited, budgeted context pack for one entity.",
    "row_count": "How many source rows match a time window and filters.",
    "row_count_compare": "Row count in two windows, with the change.",
    "metric_latest_period": "Latest period boundaries for an approved metric.",
}

# The only SQL this module builds directly is read-only. The keyword guard is
# for an approved definition's stored base SQL: approval is human review, not
# a licence to run a DELETE.
_WRITE_KEYWORD = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|export|"
    r"import|pragma|call|truncate|grant|revoke)\b", re.I)

_GRAINS = ("day", "week", "month", "quarter", "year")


class ToolError(RuntimeError):
    """A tool refused the request, with a message a person can act on."""

    def __init__(self, message: str, tool: str | None = None) -> None:
        super().__init__(message)
        self.tool = tool

    def as_dict(self) -> dict:
        return {"type": type(self).__name__, "tool": self.tool,
                "message": str(self)}


# --------------------------------------------------------------- helpers
def jsonable(value: Any) -> Any:
    """DuckDB types -> JSON-safe values, recursively.

    A Decimal that reaches `json.dumps` without this crashed the API on a
    SUM over a DECIMAL column; dates had the same problem one layer later.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        as_float = float(value)
        return int(value) if as_float.is_integer() and abs(as_float) < 1e15 \
            else as_float
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(jsonable(item) for item in value)
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def numeric(value: Any) -> float | None:
    """A real number or None. Booleans are not numbers here."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    return None


def format_value(value: Any, unit: str = "") -> str:
    """A human answer string. The same number, written the same way, always."""
    number = numeric(value)
    if number is None:
        return "no value"
    unit = str(unit or "").strip()
    if unit.lower() in ("count", "counts", "rows", "orders", "items"):
        return f"{number:,.0f} {unit}"
    text = f"{number:,.2f}" if abs(number) >= 1000 else f"{number:.2f}"
    if unit.upper() in ("USD", "US$", "$", "DOLLAR", "DOLLARS"):
        return "$" + text
    return f"{text} {unit}".strip()


def _format_signed(value: float) -> str:
    return f"{value:+,.2f}" if abs(value) >= 1000 else f"{value:+.2f}"


def _format_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.1f}%"


def _to_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _shift_months(day: date, months: int) -> date:
    index = day.year * 12 + (day.month - 1) + months
    year, month = divmod(index, 12)
    return date(year, month + 1, 1)


def shift_period(day: date, grain: str, steps: int) -> date:
    """Move one whole period forward/backward, so windows never drift."""
    grain = grain if grain in _GRAINS else "month"
    if grain == "day":
        return day + timedelta(days=steps)
    if grain == "week":
        return day + timedelta(days=7 * steps)
    if grain == "month":
        return _shift_months(day, steps)
    if grain == "quarter":
        return _shift_months(day, 3 * steps)
    return date(day.year + steps, day.month, 1)


def period_bounds(latest: date, grain: str = "month") -> dict:
    """The current and prior period around the newest data.

    Anchoring on the newest datum, not on wall-clock today, is what makes the
    demo question work on a dataset whose month is 2026-10 while today is
    2026-11 - and what makes the answer reproducible next month.
    """
    grain = grain if grain in _GRAINS else "month"
    if grain == "week":
        current_from = latest - timedelta(days=latest.weekday())
        current_to = current_from + timedelta(days=7)
        prior_from = current_from - timedelta(days=7)
        prior_to = current_from
    elif grain == "day":
        current_from = latest
        current_to = latest + timedelta(days=1)
        prior_from = latest - timedelta(days=1)
        prior_to = current_from
    elif grain == "quarter":
        quarter_month = ((latest.month - 1) // 3) * 3 + 1
        current_from = date(latest.year, quarter_month, 1)
        current_to = _shift_months(current_from, 3)
        prior_from = _shift_months(current_from, -3)
        prior_to = current_from
    elif grain == "year":
        current_from = date(latest.year, 1, 1)
        current_to = date(latest.year + 1, 1, 1)
        prior_from = date(latest.year - 1, 1, 1)
        prior_to = current_from
    else:
        current_from = date(latest.year, latest.month, 1)
        current_to = _shift_months(current_from, 1)
        prior_from = _shift_months(current_from, -1)
        prior_to = current_from
    return {
        "grain": grain,
        "latest": latest.isoformat(),
        "current_from": current_from.isoformat(),
        "current_to": current_to.isoformat(),
        "prior_from": prior_from.isoformat(),
        "prior_to": prior_to.isoformat(),
        "current_label": f"{current_from.isoformat()}..{current_to.isoformat()}",
        "prior_label": f"{prior_from.isoformat()}..{prior_to.isoformat()}",
    }


def _read_only_sql(sql: str) -> None:
    text = str(sql or "")
    if not text.strip():
        raise ToolError("the metric definition has no base SQL")
    stripped = text.strip()
    if stripped.endswith(";"):
        stripped = stripped[:-1]
    if ";" in stripped:
        raise ToolError("a metric base SQL must be a single SELECT, not "
                        "several statements")
    match = _WRITE_KEYWORD.search(stripped)
    if match:
        raise ToolError("the metric base SQL contains a write/DDL keyword "
                        f"({match.group(1)!r}); refusing to run it")


def _window_label(time_from: str | None, time_to: str | None) -> str:
    if not time_from and not time_to:
        return "all time"
    return f"{time_from or 'beginning'} to {time_to or 'latest'}"


def _filter_label(filters: dict | None) -> str:
    if not filters:
        return ""
    return ", ".join(f"{key} = {value}" for key, value in sorted(filters.items()))


def _filter_citation(filters: dict | None) -> str:
    if not filters:
        return ""
    parts = [f"{key}={str(value).replace(' ', '_')}"
             for key, value in sorted(filters.items())]
    return ":" + ",".join(parts)


def _normalise_filters(filters: Any) -> dict:
    if filters in (None, {}):
        return {}
    if not isinstance(filters, dict):
        raise ToolError("filters must be an object of dimension -> value")
    out: dict[str, Any] = {}
    for key, value in filters.items():
        column = str(key)
        if is_pii_column(column):
            raise ToolError(f"filter on PII column {column!r} is refused")
        if isinstance(value, (dict, list, tuple, set)):
            raise ToolError(f"filter value for {column!r} must be a single "
                            "value")
        out[column] = jsonable(value)
    return out


def _normalise_bundles(bundles) -> list[tuple[str, Any, Any]]:
    """Accept (source, schema, onto) tuples, dicts or SourceBundle objects."""
    out: list[tuple[str, Any, Any]] = []
    for item in bundles or []:
        if isinstance(item, dict):
            out.append((str(item.get("source") or ""), item.get("schema"),
                        item.get("onto")))
        elif isinstance(item, (tuple, list)) and len(item) >= 3:
            out.append((str(item[0]), item[1], item[2]))
        else:
            source = getattr(item, "source", None)
            schema = getattr(item, "schema", None)
            onto = getattr(item, "onto", None)
            if source and schema is not None:
                out.append((str(source), schema, onto))
    return out


def _table_name(value: Any) -> str:
    return str(getattr(value, "name", value))


class ToolRegistry:
    """The read-only tools, bound to one graph and one source.

    `bundles` gives the registry the schema and ontology of the source, which
    `source_rows` and `context_pack` need. Metric tools work from the stored
    approved definitions alone, so a runtime may pass no bundles and still
    answer metric questions.
    """

    def __init__(self, graph, source_id: str, bundles=None) -> None:
        if not source_id:
            raise ToolError("ToolRegistry needs a source id")
        self.graph = graph
        self.source_id = str(source_id)
        self.bundles = _normalise_bundles(bundles)
        self.schema = SimpleNamespace(name=self.source_id, tables=[])
        self.onto = None
        self._columns_cache: dict[str, dict[str, str]] = {}
        for source, schema, onto in self.bundles:
            if source == self.source_id:
                self.schema, self.onto = schema, onto
                break

    # ---------------------------------------------------------- metadata
    def available(self) -> list[dict]:
        return [{"name": name, "description": TOOL_DESCRIPTIONS[name]}
                for name in TOOL_NAMES]

    def call(self, tool: str, **kwargs) -> dict:
        """Dispatch by name, so the runtime's trace and here agree."""
        if tool not in TOOL_NAMES:
            raise ToolError(f"unknown tool {tool!r}; available: "
                            + ", ".join(TOOL_NAMES))
        return getattr(self, tool)(**kwargs)

    def _envelope(self, tool: str, args: dict, result: dict, evidence: list,
                  started: float, sql: str | None = None) -> dict:
        return {
            "tool": tool,
            "args": jsonable(args),
            "result": jsonable(result),
            "evidence": [jsonable(fact) for fact in evidence],
            "sql": sql,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    def _approved(self, metric: str) -> dict:
        definition = metric_defs.get_definition(
            self.graph, str(metric), self.source_id)
        if definition is None:
            names = [d["name"] for d in
                     metric_defs.list_definitions(self.graph, self.source_id)]
            raise ToolError(
                f"no approved metric {metric!r} in source "
                f"{self.source_id!r}; available: {', '.join(names) or 'none'}",
                tool="metric")
        if definition.get("status") != "approved":
            raise ToolError(
                f"metric {metric!r} is {definition.get('status')!r} and "
                "cannot be served; only approved definitions may answer",
                tool="metric")
        _read_only_sql(definition["base_sql"])
        return definition

    def _check_dimension(self, definition: dict, dimension: str) -> str:
        dimension = str(dimension or "")
        allowed = set(definition.get("dimensions") or [])
        if definition.get("time_column"):
            allowed.add(str(definition["time_column"]))
        if dimension not in allowed:
            raise ToolError(
                f"metric {definition['name']!r} has no dimension "
                f"{dimension!r}; available: "
                + (", ".join(sorted(allowed)) or "none"), tool="metric")
        if is_pii_column(dimension):
            raise ToolError(f"dimension {dimension!r} is PII and cannot be "
                            "broken down", tool="metric")
        return dimension

    def _time_column(self, definition: dict) -> str:
        column = str(definition.get("time_column") or "")
        if not column:
            raise ToolError(
                f"metric {definition['name']!r} has no time column, so it "
                "cannot be compared or trended", tool="metric")
        return column

    def _evaluate(self, metric: str, filters: dict | None = None,
                  group_by: str | None = None,
                  time_from: str | None = None,
                  time_to: str | None = None,
                  limit: int = 1000) -> dict:
        try:
            return metric_defs.evaluate_definition(
                self.graph, str(metric), self.source_id,
                filters=filters or {}, group_by=group_by,
                time_from=time_from, time_to=time_to, limit=limit)
        except KeyError as exc:
            raise ToolError(str(exc).strip("'"), tool="metric") from exc

    def _value(self, metric: str, filters: dict | None = None,
               time_from: str | None = None,
               time_to: str | None = None) -> tuple[float | None, dict]:
        out = self._evaluate(metric, filters=filters, time_from=time_from,
                             time_to=time_to, limit=1)
        rows = out.get("rows") or []
        return numeric(rows[0][0]) if rows else None, out

    def _breakdown(self, metric: str, dimension: str,
                   filters: dict | None = None,
                   time_from: str | None = None,
                   time_to: str | None = None,
                   limit: int = 500) -> tuple[dict[str, float | None], dict]:
        out = self._evaluate(metric, filters=filters, group_by=dimension,
                             time_from=time_from, time_to=time_to, limit=limit)
        pairs: dict[str, float | None] = {}
        for row in out.get("rows") or []:
            pairs[str(row[0])] = numeric(row[1])
        return pairs, out

    def _definition_summary(self, definition: dict) -> dict:
        return {
            "name": definition["name"],
            "title": definition["title"],
            "description": definition.get("description") or "",
            "unit": definition.get("unit") or "",
            "value_expr": definition.get("value_expr"),
            "time_column": definition.get("time_column"),
            "dimensions": list(definition.get("dimensions") or []),
            "owner": definition.get("owner") or "",
            "status": definition.get("status"),
            "version": definition.get("version"),
        }

    def _definition_fact(self, definition: dict) -> dict:
        unit = definition.get("unit") or ""
        expression = definition.get("value_expr") or "value"
        text = (f"{definition['title']} is an approved metric: "
                f"{expression} over the {definition.get('description') or 'source data'}"
                f"{(' Unit: ' + unit + '.') if unit else ''}")
        return {"text": text, "provenance": "declared",
                "citation": f"metric_definition:{definition['name']}"}

    # ------------------------------------------------------ metric tools
    def metric_value(self, metric: str, filters: dict | None = None,
                     time_from: str | None = None,
                     time_to: str | None = None) -> dict:
        """One approved metric value, with the SQL that produced it."""
        started = time.perf_counter()
        definition = self._approved(metric)
        filters = _normalise_filters(filters)
        value, out = self._value(metric, filters, time_from, time_to)
        window = _window_label(time_from, time_to)
        title = definition["title"]
        unit = definition.get("unit") or ""
        evidence = [self._definition_fact(definition)]
        if filters:
            evidence.append({
                "text": "The question was read with filters: "
                        + _filter_label(filters) + ".",
                "provenance": "derived",
                "citation": "filter" + _filter_citation(filters)})
        citation = (f"metric:{definition['name']}:value:"
                    f"{time_from or 'start'}..{time_to or 'latest'}"
                    + _filter_citation(filters))
        if value is None:
            evidence.append({
                "text": f"{title}: no rows matched {window}"
                        + (f" and {_filter_label(filters)}" if filters else "")
                        + ".",
                "provenance": "measured", "citation": citation})
        else:
            evidence.append({
                "text": f"{title} was {format_value(value, unit)} for {window}"
                        + (f" with {_filter_label(filters)}" if filters else "")
                        + ".",
                "provenance": "measured", "citation": citation,
                "value": value})
        result = {
            "metric": definition["name"],
            "title": title,
            "unit": unit,
            "value": value,
            "time_from": time_from,
            "time_to": time_to,
            "filters": filters,
            "window": window,
            "definition": self._definition_summary(definition),
            "rows": out.get("rows"),
        }
        return self._envelope("metric_value",
                              {"metric": metric, "filters": filters,
                               "time_from": time_from, "time_to": time_to},
                              result, evidence, started, sql=out.get("sql"))

    def metric_breakdown(self, metric: str, dimension: str,
                         filters: dict | None = None,
                         time_from: str | None = None,
                         time_to: str | None = None,
                         limit: int = 50) -> dict:
        """One approved metric split by a declared dimension."""
        started = time.perf_counter()
        definition = self._approved(metric)
        filters = _normalise_filters(filters)
        dimension = self._check_dimension(definition, dimension)
        limit = max(1, min(int(limit or 50), 500))
        pairs, out = self._breakdown(metric, dimension, filters, time_from,
                                     time_to, limit=limit)
        title = definition["title"]
        unit = definition.get("unit") or ""
        window = _window_label(time_from, time_to)
        total = sum(value for value in pairs.values() if value is not None)
        evidence = [self._definition_fact(definition)]
        citation_base = (f"metric:{definition['name']}:breakdown:{dimension}:"
                         f"{time_from or 'start'}..{time_to or 'latest'}"
                         + _filter_citation(filters))
        evidence.append({
            "text": f"{title} by {dimension} for {window}"
                    + (f" ({_filter_label(filters)})" if filters else "")
                    + f" totals {format_value(total, unit)} across "
                      f"{len(pairs)} {dimension} values.",
            "provenance": "measured", "citation": citation_base + ":total",
            "value": total})
        for key, value in list(pairs.items())[:25]:
            if value is None:
                continue
            evidence.append({
                "text": f"{title} for {dimension} {key} was "
                        f"{format_value(value, unit)} ({window}).",
                "provenance": "measured",
                "citation": f"{citation_base}:{key}", "value": value})
        rows = [{"key": key, "value": value}
                for key, value in pairs.items()]
        result = {
            "metric": definition["name"], "title": title,
            "dimension": dimension, "unit": unit, "rows": rows,
            "total": total, "time_from": time_from, "time_to": time_to,
            "filters": filters, "window": window,
            "truncated": len(rows) >= limit,
            "definition": self._definition_summary(definition),
        }
        return self._envelope(
            "metric_breakdown",
            {"metric": metric, "dimension": dimension, "filters": filters,
             "time_from": time_from, "time_to": time_to, "limit": limit},
            result, evidence, started, sql=out.get("sql"))

    def metric_compare(self, metric: str, dimension: str,
                       current_from: str, current_to: str,
                       prior_from: str, prior_to: str,
                       filters: dict | None = None) -> dict:
        """Current vs prior period, by dimension. One call, both windows.

        This is the tool the demo question needs: it produces the total change
        and the per-segment contribution in a single auditable step.
        """
        started = time.perf_counter()
        definition = self._approved(metric)
        filters = _normalise_filters(filters)
        dimension = self._check_dimension(definition, dimension)
        title = definition["title"]
        unit = definition.get("unit") or ""
        current_total, current_sql = self._value(
            metric, filters, current_from, current_to)
        prior_total, prior_sql = self._value(
            metric, filters, prior_from, prior_to)
        current_rows, cur_break = self._breakdown(
            metric, dimension, filters, current_from, current_to)
        prior_rows, pri_break = self._breakdown(
            metric, dimension, filters, prior_from, prior_to)

        rows = []
        for key in sorted(set(current_rows) | set(prior_rows), key=str):
            current = current_rows.get(key)
            prior = prior_rows.get(key)
            change = None
            change_pct = None
            if current is not None and prior is not None:
                change = current - prior
                if prior not in (0, 0.0):
                    change_pct = change / prior * 100
            rows.append({
                "key": key, dimension: key,
                "current": current, "prior": prior,
                "change": change, "change_pct": change_pct,
                "direction": ("down" if change is not None and change < 0
                              else "up" if change is not None and change > 0
                              else "flat" if change is not None else "unknown"),
                "citation": (f"metric:{definition['name']}:compare:{dimension}"
                             f"={key}:{current_from}..{current_to}|"
                             f"{prior_from}..{prior_to}"
                             + _filter_citation(filters)),
            })
        rows.sort(key=lambda row: (row["change"] is None,
                                   row["change"] if row["change"] is not None
                                   else 0.0))

        total_change = None
        total_pct = None
        if current_total is not None and prior_total is not None:
            total_change = current_total - prior_total
            if prior_total not in (0, 0.0):
                total_pct = total_change / prior_total * 100

        citation = (f"metric:{definition['name']}:compare:"
                    f"{current_from}..{current_to}|{prior_from}..{prior_to}"
                    + _filter_citation(filters))
        evidence = [self._definition_fact(definition)]
        if filters:
            evidence.append({
                "text": "The question was read with filters: "
                        + _filter_label(filters) + ".",
                "provenance": "derived",
                "citation": "filter" + _filter_citation(filters)})
        evidence.append({
            "text": f"{title} was {format_value(current_total, unit)} for "
                    f"{current_from}..{current_to}"
                    + (f" ({_filter_label(filters)})" if filters else "") + ".",
            "provenance": "measured", "citation": citation + ":current",
            "value": current_total})
        evidence.append({
            "text": f"{title} was {format_value(prior_total, unit)} for "
                    f"{prior_from}..{prior_to}"
                    + (f" ({_filter_label(filters)})" if filters else "") + ".",
            "provenance": "measured", "citation": citation + ":prior",
            "value": prior_total})
        if total_change is not None:
            evidence.append({
                "text": (f"{title} changed by "
                         f"{_format_signed(total_change)} "
                         f"({_format_pct(total_pct)}) between the prior period "
                         f"and the current period."),
                "provenance": "derived", "citation": citation,
                "value": total_change})
        for row in rows[:8]:
            if row["change"] is None:
                continue
            evidence.append({
                "text": (f"{dimension} {row['key']}: {title} moved from "
                         f"{format_value(row['prior'], unit)} to "
                         f"{format_value(row['current'], unit)} "
                         f"({_format_signed(row['change'])}, "
                         f"{_format_pct(row['change_pct'])})."),
                "provenance": "derived", "citation": row["citation"],
                "value": row["change"]})
        result = {
            "metric": definition["name"], "title": title, "unit": unit,
            "dimension": dimension, "rows": rows,
            "current": current_total, "prior": prior_total,
            "change": total_change, "change_pct": total_pct,
            "declining": [row for row in rows
                          if row["change"] is not None and row["change"] < 0][:5],
            "current_from": current_from, "current_to": current_to,
            "prior_from": prior_from, "prior_to": prior_to,
            "filters": filters,
            "definition": self._definition_summary(definition),
        }
        sql = "\n\n".join(statement for statement in (
            current_sql.get("sql"), prior_sql.get("sql"),
            cur_break.get("sql"), pri_break.get("sql")) if statement)
        return self._envelope(
            "metric_compare",
            {"metric": metric, "dimension": dimension,
             "current_from": current_from, "current_to": current_to,
             "prior_from": prior_from, "prior_to": prior_to,
             "filters": filters},
            result, evidence, started, sql=sql)

    def metric_trend(self, metric: str, time_from: str, time_to: str,
                     grain: str = "month", filters: dict | None = None) -> dict:
        """An approved metric over time, at one grain.

        `evaluate_definition` groups by a declared column, not by a time
        bucket, so the trend is the one place this module writes the SELECT
        itself - wrapping the same approved base SQL and value expression.
        """
        started = time.perf_counter()
        definition = self._approved(metric)
        filters = _normalise_filters(filters)
        grain = str(grain or "month").lower()
        if grain not in _GRAINS:
            raise ToolError(f"unknown grain {grain!r}; available: "
                            + ", ".join(_GRAINS), tool="metric_trend")
        time_column = self._time_column(definition)
        where = [f"{qi(time_column)} >= ?", f"{qi(time_column)} < ?"]
        params: list = [time_from, time_to]
        for column, value in filters.items():
            where.append(f"{qi(column)} = ?")
            params.append(value)
        statement = "\n".join([
            f"SELECT date_trunc('{grain}', {qi(time_column)}) AS period, "
            f"{definition['value_expr']} AS value",
            f"FROM ({definition['base_sql']}) AS fact",
            "WHERE " + " AND ".join(where),
            "GROUP BY 1 ORDER BY 1",
        ])
        try:
            rows = self.graph.sql(statement, params)
        except Exception as exc:                      # noqa: BLE001 - clean
            raise ToolError(f"the trend query failed: {exc}",
                            tool="metric_trend") from exc
        title = definition["title"]
        unit = definition.get("unit") or ""
        points = [{"period": _period_text(row[0]),
                   "value": numeric(row[1])} for row in rows]
        evidence = [self._definition_fact(definition)]
        citation_base = (f"metric:{definition['name']}:trend:{grain}:"
                         f"{time_from}..{time_to}" + _filter_citation(filters))
        for point in points[:24]:
            evidence.append({
                "text": f"{title} in {point['period']} was "
                        f"{format_value(point['value'], unit)}.",
                "provenance": "measured",
                "citation": f"{citation_base}:{point['period']}",
                "value": point["value"]})
        result = {"metric": definition["name"], "title": title,
                  "unit": unit, "grain": grain, "points": points,
                  "time_from": time_from, "time_to": time_to,
                  "filters": filters,
                  "definition": self._definition_summary(definition)}
        return self._envelope(
            "metric_trend",
            {"metric": metric, "time_from": time_from, "time_to": time_to,
             "grain": grain, "filters": filters},
            result, evidence, started, sql=statement)

    def metric_latest_period(self, metric: str, filters: dict | None = None,
                             grain: str = "month") -> dict:
        """Where the data actually ends, so "this month" is measured.

        This is a planner primitive, not a claim shown to the user: the
        runtime records it in the plan step. Deriving the window from the
        newest datum is what keeps the demo honest on last month's export.
        """
        started = time.perf_counter()
        definition = self._approved(metric)
        filters = _normalise_filters(filters)
        time_column = self._time_column(definition)
        where = []
        params: list = []
        for column, value in filters.items():
            where.append(f"{qi(column)} = ?")
            params.append(value)
        statement = (f"SELECT max({qi(time_column)}) FROM "
                     f"({definition['base_sql']}) AS fact"
                     + (" WHERE " + " AND ".join(where) if where else ""))
        try:
            latest_raw = self.graph.one(statement, params)
        except Exception as exc:                      # noqa: BLE001 - clean
            raise ToolError(f"could not find the latest period: {exc}",
                            tool="metric_latest_period") from exc
        latest = _to_date(latest_raw)
        if latest is None:
            raise ToolError(
                f"metric {definition['name']!r} has no data for source "
                f"{self.source_id!r}", tool="metric_latest_period")
        bounds = period_bounds(latest, str(grain or "month").lower())
        evidence = [{
            "text": (f"The newest {time_column} in {definition['title']} "
                     f"evidence is {latest.isoformat()}; the current period "
                     f"is {bounds['current_label']}."),
            "provenance": "measured",
            "citation": f"metric:{definition['name']}:latest:{latest.isoformat()}",
        }]
        result = {"metric": definition["name"], **bounds, "filters": filters}
        return self._envelope(
            "metric_latest_period",
            {"metric": metric, "filters": filters, "grain": grain},
            result, evidence, started, sql=statement)

    # -------------------------------------------------------- graph tool
    def graph_neighbours(self, cls: str, key: str,
                         relation: str | None = None,
                         depth: int = 1) -> dict:
        """Outgoing and incoming links of one node, with each edge's provenance.

        Both directions are included because "which orders does this customer
        have" is as much a graph question as the forward link. Every entry
        says which direction it came from, so an answer never claims a reverse
        relationship is the one the source declared.
        """
        started = time.perf_counter()
        cls = str(cls or "")
        key = str(key or "")
        try:
            depth = int(depth)
        except (TypeError, ValueError):
            raise ToolError("depth must be a whole number",
                            tool="graph_neighbours") from None
        if depth < 1:
            raise ToolError("depth must be at least 1", tool="graph_neighbours")
        try:
            code = self.graph.class_code(cls, self.source_id)
        except KeyError as exc:
            raise ToolError(str(exc).strip("'"),
                            tool="graph_neighbours") from exc
        if code is None:
            raise ToolError(
                f"no class {cls!r} in source {self.source_id!r}; available: "
                + ", ".join(self._class_names()), tool="graph_neighbours")
        node = self.graph.node_id(cls, key, self.source_id)
        if node is None:
            raise ToolError(
                f"no {cls} {key!r} in source {self.source_id!r}",
                tool="graph_neighbours")
        relations = self._relation_names(cls, direction="out")
        incoming = self._relation_names(cls, direction="in")
        if relation:
            if relation not in relations and relation not in incoming:
                raise ToolError(
                    f"no relation {relation!r} touches class {cls!r}; "
                    "available: "
                    + ", ".join(sorted(set(relations) | set(incoming))),
                    tool="graph_neighbours")

        neighbours: list[dict] = []
        evidence: list[dict] = []
        sql_parts: list[str] = []
        if depth <= 1:
            for name in relations:
                if relation and name != relation:
                    continue
                for other, valid_from in self.graph.neighbours(
                        cls, key, name, source=self.source_id).items():
                    neighbours.append({
                        "relation": name, "direction": "out",
                        "target_class": self._relation_range(name),
                        "target_key": other,
                        "provenance": self._relation_provenance(name),
                        "valid_from": str(valid_from) if valid_from else None})
            for name in incoming:
                if relation and name != relation:
                    continue
                rel_code = self.graph.relation_code(name, self.source_id)
                rows = self.graph.sql("""
                    SELECT n.nkey, c.name, r.provenance, e.valid_from
                    FROM edges e
                    JOIN nodes n ON n.id = e.src
                    JOIN classes c ON c.code = n.class
                                  AND c.source_id = e.source_id
                    JOIN relations r ON r.code = e.rel
                                    AND r.source_id = e.source_id
                    WHERE e.dst = ? AND e.rel = ? AND e.source_id = ?
                    ORDER BY n.nkey LIMIT 50""",
                    [node, rel_code, self.source_id])
                for other, other_class, provenance, valid_from in rows:
                    neighbours.append({
                        "relation": name, "direction": "in",
                        "target_class": other_class, "target_key": other,
                        "provenance": provenance,
                        "valid_from": str(valid_from) if valid_from else None})
            neighbours.sort(key=lambda item: (item["direction"],
                                               item["relation"],
                                               str(item["target_key"])))
        else:
            for item in sorted(self.graph.reach(
                    cls, key, relation, depth=depth,
                    source=self.source_id)):
                target_class, target_key = item.split(":", 1)
                neighbours.append({
                    "relation": relation, "direction": "out",
                    "target_class": target_class, "target_key": target_key,
                    "provenance": "derived", "valid_from": None})

        for item in neighbours[:50]:
            evidence.append({
                "text": (f"{cls} {key} links {item['direction']} to "
                         f"{item['target_class']} {item['target_key']} via "
                         f"'{item['relation']}' ({item['provenance']})."),
                "provenance": item["provenance"],
                "citation": f"edge:{item['relation']}:{item['target_key']}"})
        result = {"class": cls, "key": key, "relation": relation,
                  "depth": depth, "neighbours": neighbours,
                  "count": len(neighbours)}
        return self._envelope(
            "graph_neighbours",
            {"class": cls, "key": key, "relation": relation, "depth": depth},
            result, evidence, started,
            sql="\n\n".join(sql_parts) or None)

    def _class_names(self) -> list[str]:
        rows = self.graph.sql(
            "SELECT name FROM classes WHERE source_id = ? ORDER BY name",
            [self.source_id])
        return [row[0] for row in rows]

    def _relation_names(self, cls: str, direction: str) -> list[str]:
        if self.onto is not None:
            return [name for name, rel in self.onto.relations.items()
                    if (rel.domain if direction == "out" else rel.range) == cls]
        rows = self.graph.sql(
            "SELECT name FROM relations WHERE source_id = ? AND "
            + ("domain" if direction == "out" else "range") + " = ? "
            "ORDER BY name", [self.source_id, cls])
        return [row[0] for row in rows]

    def _relation_range(self, name: str) -> str:
        if self.onto is not None and name in self.onto.relations:
            return self.onto.relations[name].range
        row = self.graph.one(
            "SELECT range FROM relations WHERE source_id = ? AND name = ?",
            [self.source_id, name])
        return str(row or "")

    def _relation_provenance(self, name: str) -> str:
        if self.onto is not None and name in self.onto.relations:
            return self.onto.relations[name].provenance
        row = self.graph.one(
            "SELECT provenance FROM relations WHERE source_id = ? AND name = ?",
            [self.source_id, name])
        return str(row or "measured")

    # ------------------------------------------------------- source rows
    def _source_tables(self) -> list[str]:
        tables = [str(getattr(t, "name", t))
                  for t in getattr(self.schema, "tables", []) or []]
        if tables:
            return sorted(tables)
        prefix = f"src_{source_slug(self.source_id)}__"
        keyed = f"keyed_{source_slug(self.source_id)}__"
        names = []
        for row in self.graph.sql(
                "SELECT table_name FROM duckdb_tables() ORDER BY table_name"):
            name = str(row[0])
            if name.startswith(prefix):
                names.append(name[len(prefix):])
            elif name.startswith(keyed):
                names.append(name[len(keyed):])
        return sorted(set(names))

    def _source_ref(self, table: str) -> str:
        return table_ref(self.graph, self.schema, table, source=self.source_id)

    def _columns(self, table: str) -> dict[str, str]:
        if table in self._columns_cache:
            return self._columns_cache[table]
        ref = self._source_ref(table)
        try:
            rows = self.graph.sql(f"DESCRIBE {ref}")
        except Exception as exc:                      # noqa: BLE001 - clean
            raise ToolError(f"cannot inspect table {table!r}: {exc}",
                            tool="source") from exc
        columns = {str(row[0]): str(row[1]).upper() for row in rows}
        self._columns_cache[table] = columns
        return columns

    def source_rows(self, table: str, limit: int = 5) -> dict:
        """A small sample of the real rows. PII columns are dropped."""
        started = time.perf_counter()
        table = str(table or "")
        available = self._source_tables()
        if table not in available:
            raise ToolError(
                f"no table {table!r} in source {self.source_id!r}; "
                f"available: {', '.join(available) or 'none'}",
                tool="source_rows")
        limit = max(1, min(int(limit or 5), 50))
        columns, rows = _build_source_rows(
            self.graph, self.schema, table, limit=limit,
            source=self.source_id)
        redacted = [column for column in columns if is_pii_column(column)]
        keep = [index for index, column in enumerate(columns)
                if not is_pii_column(column)]
        kept_columns = [columns[index] for index in keep]
        records = [{columns[index]: jsonable(row[index]) for index in keep}
                   for row in rows]
        evidence: list[dict] = []
        if redacted:
            evidence.append({
                "text": (f"PII columns were withheld by guardrail from "
                         f"'{table}': {', '.join(redacted)}."),
                "provenance": "derived",
                "citation": f"guardrail:pii:{table}"})
        for index, record in enumerate(records[:limit]):
            preview = ", ".join(f"{key}={value}"
                                for key, value in list(record.items())[:8])
            evidence.append({
                "text": f"Sample row {index + 1} of '{table}': "
                        f"{preview[:320]}",
                "provenance": "measured",
                "citation": f"row:{table}:{index + 1}"})
        ref = self._source_ref(table)
        result = {"table": table, "columns": kept_columns,
                  "rows": records, "row_count": len(records),
                  "redacted_columns": redacted}
        return self._envelope("source_rows",
                              {"table": table, "limit": limit},
                              result, evidence, started,
                              sql=f"SELECT * FROM {ref} LIMIT {limit}")

    # ------------------------------------------------------------ context
    def context_pack(self, cls: str, key: str, budget_chars: int = 1200) -> dict:
        """The cited context pack for one entity, from layer 4 itself."""
        started = time.perf_counter()
        if not self.bundles:
            raise ToolError(
                "context_pack needs the source schema and ontology; construct "
                "ToolRegistry with bundles=[(source, schema, ontology)]",
                tool="context_pack")
        from context.assemble import build_context
        try:
            pack = build_context(self.graph, self.bundles,
                                 entity=(self.source_id, str(cls), str(key)),
                                 budget_chars=max(200, int(budget_chars)))
        except (ValueError, KeyError) as exc:
            raise ToolError(str(exc).strip("'"),
                            tool="context_pack") from exc
        evidence = [{"text": fact["text"],
                     "provenance": fact.get("provenance") or "measured",
                     "citation": fact.get("citation") or "",
                     "value": fact.get("value")}
                    for fact in pack.get("facts") or []]
        result = jsonable(pack)
        return self._envelope("context_pack",
                              {"class": cls, "key": key,
                               "budget_chars": budget_chars},
                              result, evidence, started, sql=None)

    # ---------------------------------------------------------- row counts
    def _row_count(self, table: str, time_from: str | None = None,
                   time_to: str | None = None,
                   filters: dict | None = None) -> tuple[int, dict, str]:
        available = self._source_tables()
        if table not in available:
            raise ToolError(
                f"no table {table!r} in source {self.source_id!r}; "
                f"available: {', '.join(available) or 'none'}",
                tool="row_count")
        columns = self._columns(table)
        filters = _normalise_filters(filters)
        unknown = [column for column in filters if column not in columns]
        if unknown:
            raise ToolError(
                f"table {table!r} has no column(s) "
                + ", ".join(repr(column) for column in unknown),
                tool="row_count")
        where = []
        params: list = []
        time_column = self._time_column_for(table, columns)
        if time_from or time_to:
            if not time_column:
                raise ToolError(
                    f"table {table!r} has no time column, so a time window "
                    "cannot be counted", tool="row_count")
            if time_from:
                where.append(f"{qi(time_column)} >= ?")
                params.append(time_from)
            if time_to:
                where.append(f"{qi(time_column)} < ?")
                params.append(time_to)
        for column, value in filters.items():
            where.append(f"{qi(column)} = ?")
            params.append(value)
        ref = self._source_ref(table)
        statement = f"SELECT count(*) FROM {ref}"
        if where:
            statement += " WHERE " + " AND ".join(where)
        count = int(self.graph.one(statement, params) or 0)
        return count, {"table": table, "time_from": time_from,
                       "time_to": time_to, "filters": filters,
                       "window": _window_label(time_from, time_to)}, statement

    def _time_column_for(self, table: str,
                         columns: dict[str, str] | None = None) -> str | None:
        if self.onto is not None:
            for cls in self.onto.classes.values():
                if str(getattr(cls, "table", "")) == table and cls.time_column:
                    return str(cls.time_column)
        columns = columns or self._columns(table)
        for column, kind in columns.items():
            if "TIMESTAMP" in kind or "DATE" in kind:
                return column
        return None

    def row_count(self, table: str, time_from: str | None = None,
                  time_to: str | None = None,
                  filters: dict | None = None) -> dict:
        """How many source rows exist in a window. A count, not a metric."""
        started = time.perf_counter()
        count, result, statement = self._row_count(
            table, time_from, time_to, filters)
        citation = (f"row_count:{table}:{time_from or 'start'}.."
                    f"{time_to or 'latest'}" + _filter_citation(result["filters"]))
        evidence = [{
            "text": (f"Table '{table}' has {count:,} rows for "
                     f"{result['window']}"
                     + (f" ({_filter_label(result['filters'])})"
                        if result["filters"] else "") + "."),
            "provenance": "measured", "citation": citation, "value": count}]
        return self._envelope("row_count",
                              {"table": table, "time_from": time_from,
                               "time_to": time_to,
                               "filters": result["filters"]},
                              result, evidence, started, sql=statement)

    def row_count_compare(self, table: str, current_from: str,
                          current_to: str, prior_from: str,
                          prior_to: str,
                          filters: dict | None = None) -> dict:
        """Row count in two windows. The order-volume leg of the demo story."""
        started = time.perf_counter()
        current, current_result, current_sql = self._row_count(
            table, current_from, current_to, filters)
        prior, prior_result, prior_sql = self._row_count(
            table, prior_from, prior_to, filters)
        change = current - prior
        change_pct = (change / prior * 100) if prior else None
        citation = (f"row_count:{table}:{current_from}..{current_to}|"
                    f"{prior_from}..{prior_to}"
                    + _filter_citation(current_result["filters"]))
        label = _filter_label(current_result["filters"])
        evidence = [
            {"text": (f"Table '{table}' had {current:,} rows for "
                      f"{current_from}..{current_to}"
                      + (f" ({label})" if label else "") + "."),
             "provenance": "measured", "citation": citation + ":current",
             "value": current},
            {"text": (f"Table '{table}' had {prior:,} rows for "
                      f"{prior_from}..{prior_to}"
                      + (f" ({label})" if label else "") + "."),
             "provenance": "measured", "citation": citation + ":prior",
             "value": prior},
            {"text": (f"Row volume in '{table}' changed by "
                      f"{change:+,} ({_format_pct(change_pct)})."),
             "provenance": "derived", "citation": citation, "value": change},
        ]
        result = {"table": table, "current": current, "prior": prior,
                  "change": change, "change_pct": change_pct,
                  "current_from": current_from, "current_to": current_to,
                  "prior_from": prior_from, "prior_to": prior_to,
                  "filters": current_result["filters"]}
        return self._envelope(
            "row_count_compare",
            {"table": table, "current_from": current_from,
             "current_to": current_to, "prior_from": prior_from,
             "prior_to": prior_to, "filters": current_result["filters"]},
            result, evidence, started,
            sql=current_sql + "\n-- prior --\n" + prior_sql)


def trend_window(bounds: dict, periods_back: int = 6) -> tuple[str, str]:
    """The trend window: `periods_back` periods ending with the current one."""
    grain = bounds.get("grain") or "month"
    start = _to_date(bounds["current_from"]) or date.today()
    for _ in range(max(0, int(periods_back) - 1)):
        start = shift_period(start, grain, -1)
    return start.isoformat(), bounds["current_to"]


def _period_text(value: Any) -> str:
    day = _to_date(value)
    return day.isoformat() if day else str(value)


def tool_catalogue() -> list[dict]:
    """The public tool list, for `/api/tools` and agent documentation."""
    return [{"name": name, "description": TOOL_DESCRIPTIONS[name]}
            for name in TOOL_NAMES]
