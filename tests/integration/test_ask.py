"""ask_question: a plain question -> the relevant things -> AI-written SQL,
checked and run -> rows + SQL + the fields used. The AI never writes a
number, and a query that fails the safety checks is never run."""

from __future__ import annotations

import json

import pytest

from api import mcp_server
from ontology import ask, simple
from tests.integration.simple_fixtures import FakeAI, load


class SqlAI:
    """Answers the SQL prompt with scripted replies, in order."""

    mock = False
    model = "fake-sql"

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def complete(self, messages, max_tokens=0):
        self.prompts.append(json.loads(messages[-1]["content"]))
        reply = self.replies.pop(0)
        return json.dumps(reply if isinstance(reply, dict) else {"sql": reply, "explanation": "ok"})


def build_iot(tmp_path, meanings=True):
    layer = load(tmp_path, ["iot", "clinic"])
    oid = simple.create_and_build(layer, "Sensors", ["iot"], client=FakeAI() if meanings else None)["ontology"]
    return layer, oid


def refs(layer, oid, question):
    view = simple.view(layer.graph, oid, published=True)
    cat = ask.catalogue(layer, view, [t["name"] for t in ask.pick(view, question)["things"]])
    return {t["table"]: t["sql_name"] for t in cat["tables"]}


def test_pick_finds_the_things_and_measures_coverage(tmp_path):
    layer, oid = build_iot(tmp_path)
    view = simple.view(layer.graph, oid, published=True)
    p = ask.pick(view, "What is the average temperature per site?")
    names = [t["name"] for t in p["things"]]
    assert {"Sensor Reading", "Site"} <= set(names)
    assert p["coverage"] == 1.0 and p["unmatched"] == []
    p = ask.pick(view, "quarterly revenue by salesperson")
    assert p["things"] == [] and p["coverage"] == 0.0
    p = ask.pick(view, "battery level and zorblax per device")
    assert "zorblax" in p["unmatched"] and 0 < p["coverage"] < 1


def test_without_a_model_the_catalogue_is_returned_honestly(tmp_path):
    layer, oid = build_iot(tmp_path)
    out = ask.ask(layer, oid, "average temperature per site")
    assert out["answerable"] is False and out["sql"] is None and out["rows"] == []
    assert "No AI model" in out["note"]
    tables = {t["table"]: t for t in out["catalogue"]["tables"]}
    assert {"iot.readings", "iot.sites"} <= set(tables)
    assert tables["iot.readings"]["sql_name"].startswith('"')
    joins = {(j["from"].split(".")[-1], j["to"].split(".")[-1]) for j in out["catalogue"]["joins"]}
    assert ("device_id", "device_id") in joins and ("site_id", "site_id") in joins


def test_a_good_query_runs_and_every_number_comes_from_the_data(tmp_path):
    layer, oid = build_iot(tmp_path)
    r = refs(layer, oid, "average temperature per site")
    sql = (f"SELECT s.site_name, round(avg(r.temp_c), 2) AS avg_temp, count(*) AS readings "
           f"FROM {r['iot.readings']} r JOIN {r['iot.devices']} d ON d.device_id = r.device_id "
           f"JOIN {r['iot.sites']} s ON s.site_id = d.site_id GROUP BY 1 ORDER BY 2 DESC LIMIT 10")
    ai = SqlAI([{"sql": sql, "explanation": "Average temperature of readings per site.",
                 "columns_used": ["iot.readings.temp_c"]}])
    out = ask.ask(layer, oid, "average temperature per site", client=ai)
    assert out["answerable"] is True and out["repaired"] is False
    assert out["columns"] == ["site_name", "avg_temp", "readings"]
    assert 0 < out["row_count"] <= 6 and all(len(row) == 3 for row in out["rows"])
    # The numbers match the database, not the model.
    expected = layer.graph.sql(f"SELECT count(*) FROM {r['iot.readings']}")[0][0]
    assert sum(row[2] for row in out["rows"]) == expected
    used = {f["column"]: f for f in out["fields_used"]}
    assert used["iot.readings.temp_c"]["check"] == "verified"
    assert used["iot.readings.temp_c"]["unit"] == "°C"
    assert out["version"] == 1 and "wrote the query" in out["note"]
    # The prompt carried the catalogue, not whole tables.
    prompt = ai.prompts[0]
    assert prompt["question"].startswith("average temperature")
    assert all("rows" not in t or isinstance(t["records"], int) for t in prompt["catalogue"]["tables"])


def test_a_broken_query_is_repaired_once(tmp_path):
    layer, oid = build_iot(tmp_path)
    r = refs(layer, oid, "how many readings per device model")
    bad = f"SELECT d.modell, count(*) FROM {r['iot.readings']} r JOIN {r['iot.devices']} d ON d.device_id = r.device_id GROUP BY 1 LIMIT 20"
    good = f"SELECT d.model, count(*) AS n FROM {r['iot.readings']} r JOIN {r['iot.devices']} d ON d.device_id = r.device_id GROUP BY 1 LIMIT 20"
    ai = SqlAI([bad, good])
    out = ask.ask(layer, oid, "how many readings per device model", client=ai)
    assert out["answerable"] is True and out["repaired"] is True
    assert "modell" in ai.prompts[1]["problem_with_previous_sql"]
    assert out["row_count"] == 4


@pytest.mark.parametrize("sql", [
    "DELETE FROM {readings}",
    "SELECT 1; DROP TABLE {readings}",
    "SELECT * FROM eo_items LIMIT 5",
    "INSERT INTO {readings} SELECT * FROM {readings}",
])
def test_unsafe_queries_are_never_run(tmp_path, sql):
    layer, oid = build_iot(tmp_path)
    r = refs(layer, oid, "readings")
    before = layer.graph.sql(f"SELECT count(*) FROM {r['iot.readings']}")[0][0]
    text = sql.format(readings=r["iot.readings"])
    out = ask.ask(layer, oid, "readings", client=SqlAI([text, text]))
    assert out["answerable"] is False and out["rows"] == []
    assert "not run" in out["note"] or "could not" in out["note"].lower()
    assert layer.graph.sql(f"SELECT count(*) FROM {r['iot.readings']}")[0][0] == before
    assert layer.graph.one("SELECT count(*) FROM eo_items WHERE ontology_id = ?", [oid]) > 0


def test_personal_data_columns_are_refused(tmp_path):
    from api.service import MiddleLayer
    from tests.integration.simple_fixtures import write_csv
    folder = tmp_path / "crm"
    write_csv(folder / "contacts.csv", [{"contact_id": i, "email": f"p{i}@x.org", "city": "Pune"}
                                        for i in range(40)])
    layer = MiddleLayer(str(tmp_path / "crm.duckdb"))
    layer.add_source(str(folder), source="crm")
    oid = simple.create_and_build(layer, "CRM", ["crm"])["ontology"]
    r = refs(layer, oid, "list contacts and their city")
    pii = f"SELECT email, city FROM {r['crm.contacts']} LIMIT 10"
    out = ask.ask(layer, oid, "list contacts and their city", client=SqlAI([pii, pii]))
    assert out["answerable"] is False and out["rows"] == []
    assert any(c["name"] == "No PII columns" and not c["passed"] for c in out["checks"])


def test_the_model_may_decline(tmp_path):
    layer, oid = build_iot(tmp_path)
    out = ask.ask(layer, oid, "temperature of the moon", client=SqlAI([
        {"sql": None, "explanation": "No field holds lunar data."}]))
    assert out["answerable"] is False and "lunar" in out["note"]


def test_nothing_matching_is_said_plainly(tmp_path):
    layer, oid = build_iot(tmp_path)
    out = ask.ask(layer, oid, "quarterly revenue by salesperson", client=SqlAI(["SELECT 1"]))
    assert out["answerable"] is False and out["coverage"] == 0.0 and "No business thing" in out["note"]


def test_row_and_time_limits(tmp_path):
    layer, oid = build_iot(tmp_path)
    r = refs(layer, oid, "readings")
    out = ask.run(layer.graph, f"SELECT * FROM {r['iot.readings']}", limit=5)
    assert out["row_count"] == 5 and out["truncated"] is True
    with pytest.raises(Exception):
        ask.run(layer.graph, f"SELECT count(*) FROM {r['iot.readings']} a, {r['iot.readings']} b, "
                             f"{r['iot.readings']} c", limit=5, time_limit=0.05)
    # The connection is still usable after an interrupt.
    assert layer.graph.sql("SELECT 1")[0][0] == 1


def test_ask_over_mcp_and_scope(tmp_path, monkeypatch):
    layer, oid = build_iot(tmp_path)
    r = refs(layer, oid, "readings per site")
    sql = (f"SELECT s.site_name, count(*) AS n FROM {r['iot.readings']} x JOIN {r['iot.devices']} d "
           f"ON d.device_id = x.device_id JOIN {r['iot.sites']} s ON s.site_id = d.site_id GROUP BY 1 LIMIT 10")
    monkeypatch.setattr(mcp_server, "_ask_client", lambda: SqlAI([sql]))

    def call(args, scope=None):
        reply = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                   "params": {"name": "ask_question", "arguments": args}}, layer, scope=scope)
        return reply.get("error") or json.loads(reply["result"]["content"][0]["text"])
    out = call({"ontology": oid, "question": "readings per site"})
    assert out["answerable"] is True and out["row_count"] > 0
    denied = call({"ontology": oid, "question": "readings per site"},
                  scope={"sources": ["clinic"], "metrics": [], "agent_id": "a"})
    assert "forbidden" in json.dumps(denied).lower()
    assert "ask_question" in {t["name"] for t in mcp_server.TOOLS}
