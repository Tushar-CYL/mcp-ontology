"""Validate agent-written SQL against the certified definition.

An agent that writes its own SQL can drop the rule that makes a number
trustworthy. Certified Revenue only counts completed orders; a plain
``SUM(line_revenue)`` does not, and the two numbers differ. This module says
**pass / warn / fail**, gives the reason, and points to the certified
alternative.

Checks:

* read-only single query (fail): no writes, no second statement;
* known tables only (fail);
* no PII columns (fail), using the same policy as the agent guardrails;
* certified filters applied (warn): every predicate in the definition's
  WHERE clause must appear in the agent's SQL;
* certified measure used (warn): the column behind the definition's value;
* compiles against the source (fail): ``EXPLAIN`` on the rewritten SQL. Only
  run once the query is known to be read-only, so a write is never executed.

The analysis is deliberately conservative text matching, not a SQL parser:
it can warn about a correct query written differently, never silently pass a
query that drops a certified filter.
"""

from __future__ import annotations

import re

from agent.guardrails import is_pii_column

# The query must already be one statement starting with SELECT/WITH; these
# words catch data-changing clauses smuggled inside it. Words that are also
# common column names (set, load, merge) are left out on purpose.
_WRITE_WORDS = ("insert", "update", "delete", "drop", "alter", "create",
                "attach", "detach", "copy", "pragma", "install", "truncate",
                "grant", "revoke")
_SQL_WORDS = {"sum", "count", "distinct", "nullif", "avg", "min", "max",
              "cast", "as", "case", "when", "then", "else", "end", "and",
              "or", "not", "null", "in", "is", "date", "varchar", "coalesce",
              "round", "abs", "over", "partition", "by"}


def _strip(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return sql.strip().rstrip(";").strip()


def _no_literals(sql: str) -> str:
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def _norm(text: str) -> str:
    text = re.sub(r"\b[a-z_][a-z0-9_]*\.", "", text.lower())
    return re.sub(r"\s+", "", text)


def _identifiers(sql: str) -> set[str]:
    return {m.lower() for m in re.findall(r"[A-Za-z_][A-Za-z0-9_]*",
                                         _no_literals(sql))}


def _cte_names(sql: str) -> set[str]:
    return {m.lower() for m in re.findall(
        r"(?:\bwith|,)\s*([A-Za-z_]\w*)\s+as\s*\(", sql, flags=re.I)}


def _tables(sql: str) -> list[str]:
    found = re.findall(r"\b(?:from|join)\s+(\"[^\"]+\"|[A-Za-z_][\w.]*)",
                       _no_literals(sql), flags=re.I)
    ctes = _cte_names(sql)
    out = []
    for name in found:
        name = name.strip('"').split(".")[-1]
        if name.lower() not in ctes and name not in out:
            out.append(name)
    return out


def _split_top(text: str, sep_pattern: str) -> list[str]:
    """Split on a separator only at parenthesis depth 0."""
    parts, depth, start = [], 0, 0
    i = 0
    pattern = re.compile(sep_pattern, re.I)
    while i < len(text):
        char = text[i]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0:
            match = pattern.match(text, i)
            if match:
                parts.append(text[start:i])
                start = i = match.end()
                continue
        i += 1
    parts.append(text[start:])
    return [p.strip() for p in parts if p.strip()]


def certified_filters(base_sql: str) -> list[str]:
    """The predicates in the definition's outermost WHERE clause."""
    match = re.search(r"\bwhere\b(.*?)(?:\bgroup\s+by\b|\border\s+by\b|$)",
                      base_sql, flags=re.I | re.S)
    if not match:
        return []
    return _split_top(match.group(1), r"\s+and\s+")


def certified_measures(base_sql: str, value_expr: str) -> list[str]:
    """Physical columns behind the aliases a definition's value uses."""
    select = re.search(r"\bselect\b(.*?)\bfrom\b", base_sql, flags=re.I | re.S)
    if not select:
        return []
    aliases: dict[str, str] = {}
    for item in _split_top(select.group(1), r","):
        parts = re.split(r"\s+as\s+", item, flags=re.I)
        if len(parts) >= 2:
            aliases[parts[-1].strip().lower()] = " as ".join(parts[:-1])
    used = [w for w in _identifiers(value_expr) if w not in _SQL_WORDS]
    columns: list[str] = []
    for alias in used:
        expr = aliases.get(alias)
        if expr is None:
            continue
        for word in _identifiers(re.sub(r"\b[a-z_]\w*\.", "", expr, flags=re.I)):
            if word not in _SQL_WORDS and word not in columns:
                columns.append(word)
    # Keys such as order_id only count rows; the measure is what is summed.
    return [c for c in columns if not c.endswith("_id")] or columns


def _check(name: str, passed: bool, detail: str, severity: str) -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail,
            "severity": "ok" if passed else severity}


def analyse_sql(sql: str, tables: dict[str, list[str]],
                definition: dict | None) -> dict:
    """Structural and certified-definition checks, without touching data."""
    text = _strip(sql or "")
    checks: list[dict] = []
    bare = _no_literals(text).lower()
    words = set(re.findall(r"[a-z_]+", bare))
    writes = sorted(w for w in _WRITE_WORDS if w in words)
    read_only = (bool(text) and ";" not in bare
                 and re.match(r"\s*(select|with)\b", bare) is not None
                 and not writes)
    detail = ("one SELECT/WITH query" if read_only else
              "empty query" if not text else
              "more than one statement" if ";" in bare else
              f"not read-only: {', '.join(writes)}" if writes else
              "must start with SELECT or WITH")
    checks.append(_check("Read-only single query", read_only, detail, "error"))

    used = _tables(text) if text else []
    known = {name.lower(): name for name in tables}
    unknown = [t for t in used if t.lower() not in known]
    real = sorted(known[t.lower()] for t in used if t.lower() in known)
    checks.append(_check(
        "Known tables only", not unknown,
        f"unknown: {', '.join(unknown)}" if unknown else
        (", ".join(real) or "no tables"), "error"))

    idents = _identifiers(text)
    pii = sorted({c for t in tables.values() for c in t
                  if c.lower() in idents and is_pii_column(c)})
    checks.append(_check("No PII columns", not pii,
                         f"selects personal data: {', '.join(pii)}" if pii
                         else "no personal data referenced", "error"))

    certified = None
    if definition:
        filters = certified_filters(definition.get("base_sql") or "")
        flat = _norm(text)
        missing = [f for f in filters if _norm(f) not in flat]
        checks.append(_check(
            "Certified filters applied", not missing,
            ("missing: " + "; ".join(f.strip() for f in missing) +
             f" (certified {definition['name']} requires it)") if missing
            else "; ".join(filters) or "no filters in the definition",
            "warning"))
        measures = certified_measures(definition.get("base_sql") or "",
                                      definition.get("value_expr") or "")
        absent = [m for m in measures if m not in idents]
        checks.append(_check(
            "Certified measure used", not absent,
            (f"certified {definition['name']} measures "
             f"{', '.join(measures)}; this query does not use "
             f"{', '.join(absent)}") if absent else ", ".join(measures),
            "warning"))
        certified = {"metric": definition["name"],
                     "value_expr": definition.get("value_expr"),
                     "filters": filters, "measures": measures}

    status = _status(checks)
    suggestion = ""
    if definition and status != "pass":
        suggestion = (f"Use evaluate_metric('{definition['name']}') for the "
                      f"certified number: {definition.get('value_expr')} over "
                      "the governed base query.")
    return {"status": status, "checks": checks, "tables": real,
            "metric": definition["name"] if definition else None,
            "certified": certified, "suggestion": suggestion}


def _status(checks: list[dict]) -> str:
    if any(not c["passed"] and c["severity"] == "error" for c in checks):
        return "fail"
    if any(not c["passed"] for c in checks):
        return "warn"
    return "pass"


def validate_sql(graph, schema, source: str, sql: str,
                 definition: dict | None = None) -> dict:
    """`analyse_sql` plus a compile check against the materialised source."""
    from knowledge_graph.build import table_ref
    tables = {t.name: [c.name for c in t.columns] for t in schema.tables}
    result = analyse_sql(sql, tables, definition)
    structural = {c["name"]: c["passed"] for c in result["checks"]}
    if not (structural["Read-only single query"] and structural["Known tables only"]):
        return result
    text = _strip(sql)
    for name in tables:
        ref = table_ref(graph, schema, name, source=source)
        text = re.sub(r"(\b(?:from|join)\s+)\"?" + re.escape(name) + r"\"?\b",
                      lambda m, ref=ref: m.group(1) + ref, text, flags=re.I)
    try:
        graph.sql("EXPLAIN " + text)
        check = _check("Compiles against the source", True,
                       "the query binds to real tables and columns", "error")
    except Exception as exc:                       # noqa: BLE001 - reported
        message = str(exc).splitlines()[0][:240]
        check = _check("Compiles against the source", False, message, "error")
    result["checks"].append(check)
    result["status"] = _status(result["checks"])
    if definition and result["status"] != "pass" and not result["suggestion"]:
        result["suggestion"] = (f"Use evaluate_metric('{definition['name']}') "
                                "for the certified number.")
    return result
