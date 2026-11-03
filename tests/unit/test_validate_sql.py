"""Phase 5 (Validate): agent-written SQL against the certified definition.

An agent that writes its own SQL can quietly drop the rule that makes a
number trustworthy (here: only completed orders count as revenue). The
validator says pass / warn / fail with the reason and the certified
alternative, instead of letting the agent publish a different number.
"""

from __future__ import annotations

import pytest

from semantic.validate import analyse_sql

TABLES = {
    "orders": ["order_id", "customer_id", "region", "status", "order_date"],
    "order_lines": ["order_id", "line_no", "line_revenue", "quantity"],
    "customers": ["customer_id", "name", "email"],
}
REVENUE = {
    "name": "revenue",
    "value_expr": "SUM(revenue)",
    "base_sql": ('SELECT o.region AS region, l.line_revenue AS revenue '
                 'FROM "src_shop__order_lines" l JOIN "src_shop__orders" o '
                 "ON o.order_id = l.order_id WHERE o.status = 'completed'"),
}
GOOD = ("SELECT o.region, SUM(l.line_revenue) FROM order_lines l "
        "JOIN orders o ON o.order_id = l.order_id "
        "WHERE o.status = 'completed' GROUP BY o.region")


def _check(result, name):
    return next(c for c in result["checks"] if c["name"] == name)


def test_sql_that_follows_the_definition_passes():
    result = analyse_sql(GOOD, TABLES, REVENUE)
    assert result["status"] == "pass", result["checks"]
    assert result["tables"] == ["order_lines", "orders"]
    assert all(c["passed"] for c in result["checks"])


def test_missing_certified_filter_is_a_warning_with_the_reason():
    sql = "SELECT SUM(line_revenue) FROM order_lines"
    result = analyse_sql(sql, TABLES, REVENUE)
    assert result["status"] == "warn"
    check = _check(result, "Certified filters applied")
    assert not check["passed"]
    assert "status = 'completed'" in check["detail"]
    assert "evaluate_metric" in result["suggestion"]


def test_a_different_measure_is_a_warning():
    sql = ("SELECT SUM(quantity) FROM order_lines l JOIN orders o "
           "ON o.order_id = l.order_id WHERE o.status = 'completed'")
    result = analyse_sql(sql, TABLES, REVENUE)
    assert result["status"] == "warn"
    assert "line_revenue" in _check(result, "Certified measure used")["detail"]


def test_filter_matching_ignores_aliases_spacing_and_case():
    sql = ("select sum(x.line_revenue) from order_lines x join orders ord "
           "on ord.order_id = x.order_id where ORD.STATUS='completed'")
    assert analyse_sql(sql, TABLES, REVENUE)["status"] == "pass"


@pytest.mark.parametrize("sql", [
    "DELETE FROM orders",
    "UPDATE orders SET status = 'x'",
    "DROP TABLE orders",
    "SELECT 1; DROP TABLE orders",
    "ATTACH 'x.db' AS x",
    "COPY orders TO 'out.csv'",
])
def test_anything_but_one_read_only_query_fails(sql):
    result = analyse_sql(sql, TABLES, REVENUE)
    assert result["status"] == "fail"
    assert not _check(result, "Read-only single query")["passed"]


def test_a_cte_is_still_read_only():
    sql = ("WITH c AS (SELECT * FROM orders WHERE status = 'completed') "
           "SELECT SUM(l.line_revenue) FROM order_lines l JOIN c "
           "ON c.order_id = l.order_id")
    result = analyse_sql(sql, TABLES, REVENUE)
    assert _check(result, "Read-only single query")["passed"]
    assert result["tables"] == ["order_lines", "orders"]     # CTE name ignored


def test_unknown_tables_fail():
    result = analyse_sql("SELECT * FROM invoices", TABLES, None)
    assert result["status"] == "fail"
    assert "invoices" in _check(result, "Known tables only")["detail"]


def test_selecting_pii_fails():
    result = analyse_sql("SELECT email FROM customers", TABLES, None)
    assert result["status"] == "fail"
    assert "email" in _check(result, "No PII columns")["detail"]


def test_without_a_metric_only_structure_is_checked():
    result = analyse_sql("SELECT region FROM orders", TABLES, None)
    assert result["status"] == "pass"
    names = {c["name"] for c in result["checks"]}
    assert "Certified filters applied" not in names
    assert result["metric"] is None


def test_empty_sql_fails_cleanly():
    assert analyse_sql("   ", TABLES, None)["status"] == "fail"


def test_column_names_that_look_like_keywords_are_fine():
    tables = {"jobs": ["job_id", "load", "set_size"]}
    result = analyse_sql("SELECT load, set_size FROM jobs", tables, None)
    assert result["status"] == "pass", result["checks"]
