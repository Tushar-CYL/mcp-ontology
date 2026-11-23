"""Report check: numbers from the client's own reports, asked of Strata and
scored the industry way (result matches to the report's precision, units
checked apart, refusals scored, silent wrong numbers counted)."""

from __future__ import annotations

import base64
import io
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from api import ctx_routes
from api.server import create_app
from api.service import MiddleLayer
from context import report_check as rc
from ontology import registry as reg
from ontology import simple
from semantic import model as sem
from tests.integration.test_semantic_model import make_amounts


# ---------------------------------------------------------------- pieces
@pytest.mark.parametrize("text,want", [
    ("1,466,849", 1466849), ("1.5M", 1.5e6), ("63 %", 63), ("(120)", -120), ("€ 4.2k", 4200),
    ("2 billion", 2e9), (12, 12.0), ("", None), ("n/a", None)])
def test_report_numbers_are_read_the_way_reports_write_them(text, want):
    assert rc._number(text) == want


def test_four_significant_digits_by_default():
    assert rc.close(1_466_849, 1_467_000, 4)          # a report rounds to 1,467,000
    assert not rc.close(1_466_849, 1_468_000, 4)
    assert rc.close(0.6324, 0.632, 3) and not rc.close(0.64, 0.632, 3)
    assert rc.close(0, 0, 4) and not rc.close(1, 0, 4)


def test_a_rounded_report_number_is_compared_at_its_own_precision():
    """Live: a report saying 1.79M matched 1,788,887 only to 3 digits, and the
    4-digit default called it a different number."""
    assert rc.written_digits("1.79M") == 3 and rc.written_digits("500.9k") == 4
    assert rc.written_digits("2 billion") == 1 and rc.written_digits("400") is None
    assert rc._clean({"question": "q", "expected": "1.79M"})["digits"] == 3
    assert rc._clean({"question": "q", "expected": "1,466,849"})["digits"] == 4
    assert rc._clean({"question": "q", "expected": "1.2345678M"})["digits"] == 4     # never stricter than 4
    assert rc._clean({"question": "q", "expected": "1.79M", "digits": 6})["digits"] == 6
    assert rc.close(1_788_887, 1.79e6, 3) and not rc.close(1_788_887, 1.79e6, 4)


def test_a_thousand_times_off_is_a_unit_problem_not_just_wrong():
    assert rc.unit_off(1_466.849, 1_466_849, 4) == -3     # answer in thousands, report in units
    assert rc.unit_off(63.0, 0.63, 4) == 2                 # a percent vs a share
    assert rc.unit_off(1_234, 9_999, 4) is None


def test_the_number_is_read_from_the_named_row_or_the_only_row():
    table = {"columns": ["Status", "Total"], "rows": [["paid", 10.5], ["shipped", 3]]}
    assert rc.pick(table, "Paid") == (10.5, "row Paid")
    assert rc.pick(table, None)[0] is None and "2 rows" in rc.pick(table, None)[1]
    assert rc.pick(table, "lost")[0] is None
    assert rc.pick({"columns": ["n"], "rows": [[400]]}, None) == (400.0, "the only row")
    assert rc.pick(None, None) == (None, "no result table")


def test_checks_come_from_csv_or_excel():
    csv_text = ("Question,Expected,Row,Unit,Should refuse,Other phrasings,Source\n"
                "How many orders?,400,,orders,,Number of orders|Count of orders,Q3 report p.2\n"
                "What is the weather?,,,,yes,,\n")
    rows = rc.parse_file("checks.csv", csv_text)
    assert rows[0]["question"] == "How many orders?" and rows[0]["expected"] == "400"
    assert rows[0]["phrasings"] == "Number of orders|Count of orders"
    assert rows[1]["refuse"] == "yes"
    from openpyxl import Workbook
    wb = Workbook()
    wb.active.append(["question", "number", "row label"])
    wb.active.append(["Total gross by status", "1.2M", "paid"])
    buf = io.BytesIO()
    wb.save(buf)
    rows = rc.parse_file("r.xlsx", base64.b64encode(buf.getvalue()).decode())
    assert rows == [{"question": "Total gross by status", "expected": "1.2M", "row_label": "paid"}]
    with pytest.raises(rc.CheckError, match="question"):
        rc.parse_file("x.csv", "a,b\n1,2\n")
    with pytest.raises(rc.CheckError, match="header row"):
        rc.parse_file("x.csv", "question\n")


# ------------------------------------------------------------------ runs
@pytest.fixture(scope="module")
def shop(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("report-check")
    db = make_amounts(tmp / "amounts.db")
    layer = MiddleLayer(str(tmp / "g.duckdb"))
    layer.add_source(str(db), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    sem.propose(layer, oid)
    sem.certify(layer, oid, "total_gross_amount", owner="Finance")
    return layer, oid, db


def truth(db, sql):
    con = sqlite3.connect(db)
    try:
        return con.execute(sql).fetchone()[0]
    finally:
        con.close()


def test_a_bad_check_names_its_row_and_saves_nothing(shop):
    layer, oid, _ = shop
    with pytest.raises(rc.CheckError, match="row 2: say the number"):
        rc.add(layer.graph, oid, [{"question": "How many orders?", "expected": 400},
                                  {"question": "How many lines?"}])
    assert rc.checks(layer.graph, oid) == []
    with pytest.raises(KeyError):
        rc.add(layer.graph, "nope", [{"question": "x", "expected": 1}])


def test_a_run_scores_every_check_and_counts_silent_wrong_numbers(shop):
    layer, oid, db = shop
    paid = truth(db, "select sum(gross_amount) from orders where status = 'paid'")
    rc.add(layer.graph, oid, [
        {"question": "total Gross Amount by Status", "row_label": "paid", "expected": paid,
         "source": "Finance pack p.4"},                                     # certified metric
        {"question": "How many orders?", "expected": 400,
         "phrasings": ["Number of orders", "Count of orders"]},             # Strata's own query
        {"question": "How many orders?", "expected": "400k"},              # report in units of 1,000
        {"question": "How many orders?", "expected": 401},                 # the report says otherwise
        {"question": "What is the weather in Paris?", "refuse": True},
        {"question": "How many orders?", "refuse": True},
    ])
    out = rc.run(layer, oid)
    r = {(x["question"], x["expected"], x["refuse"]): x for x in out["results"]}
    gross = r[("total Gross Amount by Status", paid, False)]["answers"][0]
    assert gross["verdict"] == "pass" and gross["certified"] and gross["got"] == pytest.approx(paid)
    orders = r[("How many orders?", 400, False)]
    assert [a["verdict"] for a in orders["answers"]] == ["pass", "pass", "pass"] and orders["agree"]
    assert not orders["answers"][0]["certified"]
    assert r[("How many orders?", 400_000, False)]["answers"][0]["verdict"] == "unit"
    wrong = r[("How many orders?", 401, False)]["answers"][0]
    assert wrong["verdict"] == "wrong" and wrong["silent"] and wrong["got"] == 400
    assert r[("What is the weather in Paris?", None, True)]["answers"][0]["verdict"] == "refused_ok"
    assert r[("How many orders?", None, True)]["answers"][0]["verdict"] == "should_refuse"

    s = out["summary"]
    assert s["checks"] == 6 and s["asked"] == 8 and s["passed"] == 3
    assert s["accuracy_pct"] == round(100 * 4 / 6)            # 4 of 6 number answers match
    assert s["certified"] == {"asked": 1, "pct": 100}
    assert s["other"] == {"asked": 5, "pct": 60}
    assert s["refusals"] == {"asked": 2, "pct": 50}
    assert s["agreement_pct"] == 100
    assert s["silent_wrong"] == 3                              # unit, wrong, should-refuse
    # Saved, and the checks never became notes or verified questions.
    assert rc.last_run(layer.graph, oid)["summary"] == s
    assert not simple.view(layer.graph, oid)["notes"]
    assert not reg.items(layer.graph, oid, kind="verified")


def test_removing_a_check(shop):
    layer, oid, _ = shop
    first = rc.checks(layer.graph, oid)[0]
    left = rc.remove(layer.graph, oid, first["id"])
    assert first["id"] not in {c["id"] for c in left}
    with pytest.raises(KeyError):
        rc.remove(layer.graph, oid, first["id"])


# ------------------------------------------------------------------- API
def test_report_check_through_the_api(tmp_path, monkeypatch):
    monkeypatch.setattr(ctx_routes, "ai_client", lambda: None)
    db = make_amounts(tmp_path / "amounts.db")
    app = create_app(tmp_path / "graphs" / "g.duckdb", warm=False)
    with TestClient(app) as c:
        layer = c.app.state.platform.layer
        layer.add_source(str(db), source="shop")
        oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
        assert c.post(f"/api/ctx/{oid}/checks/run").status_code == 400      # nothing to run yet
        csv_text = "question,expected\nHow many orders?,400\n"
        r = c.post(f"/api/ctx/{oid}/checks", json={"file_name": "r.csv", "file_content": csv_text,
                                                   "checks": [{"question": "How many customers?",
                                                               "expected": 60}]})
        assert r.status_code == 200, r.text
        assert len(r.json()["checks"]) == 2 and r.json()["last_run"] is None
        assert c.post(f"/api/ctx/{oid}/checks", json={"checks": [{"question": "x"}]}).status_code == 400
        job = c.post(f"/api/ctx/{oid}/checks/run").json()["job_id"]
        for _ in range(300):
            state = c.get(f"/api/jobs/{job}").json()
            if state["status"] != "running":
                break
            time.sleep(0.2)
        assert state["status"] == "done", state
        assert state["result"]["summary"]["passed"] == 2
        over = c.get(f"/api/ctx/{oid}/checks").json()
        assert over["last_run"]["summary"]["accuracy_pct"] == 100 and len(over["history"]) == 1
        gone = over["checks"][0]["id"]
        assert len(c.delete(f"/api/ctx/{oid}/checks/{gone}").json()["checks"]) == 1
        assert c.delete(f"/api/ctx/{oid}/checks/{gone}").status_code == 404
        assert c.get("/api/ctx/nope/checks").status_code == 404
