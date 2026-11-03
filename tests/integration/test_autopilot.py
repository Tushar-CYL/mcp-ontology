"""Semantic autopilot: propose governed metrics for ANY dataset.

The curated revenue catalog only fits order/line/product data, so a real
enterprise source (e.g. SAP SALT: sales documents, items, customers, no money
columns) got zero metrics and an empty Semantic page. Like Snowflake's
Semantic View Autopilot and Databricks metric views, Strata now proposes
metrics from the data itself, as DRAFTS a person approves:

* a record count per entity, dated by its own time column or its parent's;
* items-per-parent ratios along each many-to-one link;
* distinct counts of high-cardinality reference columns (products, parties);
* totals and averages of real numeric measures;
* low-cardinality columns become dimensions; technical columns
  (``__index_level_0__``) and duplicate split tables (``_train``) are ignored.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from api.service import MiddleLayer
from semantic import autopilot
from semantic import definitions as metric_defs


def _write_salt_like(folder, train_copy=True):
    folder.mkdir(parents=True)
    rnd = random.Random(7)
    docs = ["SALESDOCUMENT,SALESOFFICE,DISTRIBUTIONCHANNEL,CREATIONDATE,__index_level_0__"]
    items = ["SALESDOCUMENT,SALESDOCUMENTITEM,PLANT,PRODUCT,__index_level_0__"]
    start = date(2024, 2, 1)
    n_items = 0
    for i in range(120):
        day = start + timedelta(days=(i * 3) // 4)     # 1 Feb - 30 Apr 2024
        docs.append(f"D{i:04d},O{i % 3},C{i % 2},{day.isoformat()},{i}")
        for j in range(1 + i % 3):
            items.append(f"D{i:04d},{10 * (j + 1)},P{i % 2},M{rnd.randint(0, 99):03d},{n_items}")
            n_items += 1
    (folder / "sales_documents.csv").write_text("\n".join(docs) + "\n", encoding="utf-8")
    (folder / "sales_document_items.csv").write_text("\n".join(items) + "\n", encoding="utf-8")
    if train_copy:
        (folder / "sales_documents_train.csv").write_text(
            "\n".join(docs[:60]) + "\n", encoding="utf-8")
    (folder / "customers.csv").write_text(
        "CUSTOMER,ADDRESSID\n" + "\n".join(f"K{i},A{i}" for i in range(30)) + "\n",
        encoding="utf-8")
    return n_items


@pytest.fixture
def salt(tmp_path):
    folder = tmp_path / "salt"
    n_items = _write_salt_like(folder)
    layer = MiddleLayer(str(tmp_path / "salt.duckdb"))
    layer.add_source(str(folder), source="salt")
    bundle = layer._bundle("salt")
    yield layer, bundle, n_items
    layer.close()


def _by_kind(proposals, kind):
    return [p for p in proposals if p["kind"] == kind]


def test_every_entity_gets_a_record_count(salt):
    layer, bundle, _ = salt
    proposals = autopilot.propose_metrics(layer.graph, bundle.schema, bundle.onto, "salt")
    counted = {p["entity"] for p in _by_kind(proposals, "count")}
    assert {"Document", "DocumentItem", "Customer"} <= counted, counted


def test_split_copies_are_not_proposed_twice(salt):
    layer, bundle, _ = salt
    proposals = autopilot.propose_metrics(layer.graph, bundle.schema, bundle.onto, "salt")
    assert not [p for p in proposals if "train" in p["name"].lower()]


def test_technical_columns_are_never_measures_or_dimensions(salt):
    layer, bundle, _ = salt
    proposals = autopilot.propose_metrics(layer.graph, bundle.schema, bundle.onto, "salt")
    for p in proposals:
        assert "__index_level_0__" not in p["value_expr"]
        assert "__index_level_0__" not in p["dimensions"]


def test_dated_entity_uses_its_time_column_and_low_card_dimensions(salt):
    layer, bundle, _ = salt
    proposals = autopilot.propose_metrics(layer.graph, bundle.schema, bundle.onto, "salt")
    docs = next(p for p in _by_kind(proposals, "count") if p["entity"] == "Document")
    assert docs["time_column"] == "CREATIONDATE"
    assert {"SALESOFFICE", "DISTRIBUTIONCHANNEL"} <= set(docs["dimensions"])
    assert docs["format"] == "integer"


def test_undated_child_borrows_time_and_dimensions_from_its_parent(salt):
    layer, bundle, _ = salt
    proposals = autopilot.propose_metrics(layer.graph, bundle.schema, bundle.onto, "salt")
    items = next(p for p in _by_kind(proposals, "count") if p["entity"] == "DocumentItem")
    assert items["time_column"] == "CREATIONDATE"
    assert {"PLANT", "SALESOFFICE"} <= set(items["dimensions"])


def test_items_per_parent_ratio_is_proposed(salt):
    layer, bundle, _ = salt
    proposals = autopilot.propose_metrics(layer.graph, bundle.schema, bundle.onto, "salt")
    ratios = _by_kind(proposals, "ratio")
    assert any(p["entity"] == "DocumentItem" and "per sales document" in p["title"]
               for p in ratios), [p["title"] for p in ratios]


def test_high_cardinality_references_get_distinct_counts(salt):
    layer, bundle, _ = salt
    proposals = autopilot.propose_metrics(layer.graph, bundle.schema, bundle.onto, "salt")
    assert any("PRODUCT" in p["value_expr"] for p in _by_kind(proposals, "distinct"))


def test_no_sums_are_invented_when_there_are_no_numeric_measures(salt):
    layer, bundle, _ = salt
    proposals = autopilot.propose_metrics(layer.graph, bundle.schema, bundle.onto, "salt")
    assert not _by_kind(proposals, "total")


def test_seeding_saves_once_and_never_overwrites(salt):
    layer, bundle, _ = salt
    created = autopilot.seed_proposals(layer.graph, bundle.schema, bundle.onto, "salt")
    assert created
    defs = {d["name"]: d for d in metric_defs.list_definitions(layer.graph, "salt")}
    # SALT-shaped data has only exact facts (counts, ratios), all approved.
    assert all(defs[name]["status"] == "approved" for name in created)
    assert all(defs[name]["owner"] == "Strata autopilot" for name in created)
    assert all("approved automatically" in defs[name]["caveats"] for name in created)
    again = autopilot.seed_proposals(layer.graph, bundle.schema, bundle.onto, "salt")
    assert again == []                           # idempotent
    metric_defs.set_status(layer.graph, created[0], "salt", "draft")
    autopilot.seed_proposals(layer.graph, bundle.schema, bundle.onto, "salt")
    assert metric_defs.get_definition(layer.graph, created[0], "salt")["status"] == "draft"


def test_every_proposal_evaluates_and_counts_are_exact(salt):
    layer, bundle, n_items = salt
    names = autopilot.seed_proposals(layer.graph, bundle.schema, bundle.onto, "salt")
    for name in names:
        result = metric_defs.evaluate_definition(layer.graph, name, "salt",
                                                 allow_draft=True)
        assert result["rows"], name
    items = next(d for d in metric_defs.list_definitions(layer.graph, "salt")
                 if d["name"] == "sales_document_items_count")
    value = metric_defs.evaluate_definition(layer.graph, items["name"], "salt",
                                            allow_draft=True)["rows"][0][0]
    assert value == n_items


def test_drafts_are_never_served_without_preview(salt):
    layer, bundle, _ = salt
    name = autopilot.seed_proposals(layer.graph, bundle.schema, bundle.onto, "salt")[0]
    metric_defs.set_status(layer.graph, name, "salt", "draft")
    with pytest.raises(KeyError, match="draft"):
        metric_defs.evaluate_definition(layer.graph, name, "salt")


def test_numeric_measures_get_totals_and_averages(tmp_path):
    folder = tmp_path / "billing"
    folder.mkdir()
    rows = ["invoice_id,region,amount,issued_on"]
    for i in range(200):
        rows.append(f"I{i},{'NSEW'[i % 4]},{(i * 37) % 900 + 0.5},2025-0{1 + i % 6}-15")
    (folder / "invoices.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    layer = MiddleLayer(str(tmp_path / "b.duckdb"))
    try:
        layer.add_source(str(folder), source="billing")
        bundle = layer._bundle("billing")
        proposals = autopilot.propose_metrics(layer.graph, bundle.schema,
                                              bundle.onto, "billing")
        totals = {p["value_expr"] for p in _by_kind(proposals, "total")}
        averages = {p["value_expr"] for p in _by_kind(proposals, "average")}
        assert 'SUM("amount")' in totals
        assert 'AVG("amount")' in averages
        count = next(p for p in _by_kind(proposals, "count"))
        assert count["time_column"] == "issued_on"
        assert "region" in count["dimensions"]
    finally:
        layer.close()


def test_the_curated_revenue_catalog_is_left_alone(tmp_path):
    from tests.integration.test_semantic_context_intelligence import _write_source
    folder = tmp_path / "revenue"
    _write_source(folder)
    with TestClient(create_app(tmp_path / "r.duckdb", warm=False)) as client:
        client.post("/api/sources", json={"path": str(folder), "name": "revenue"})
        metrics = client.get("/api/metrics", params={"source": "revenue"}).json()["metrics"]
        assert all(m["owner"] != "Strata autopilot" for m in metrics)


# ---------------------------------------------------------------- over HTTP
@pytest.fixture
def client(tmp_path):
    folder = tmp_path / "salt"
    _write_salt_like(folder)
    with TestClient(create_app(tmp_path / "api.duckdb", warm=False)) as test_client:
        response = test_client.post("/api/sources", json={"path": str(folder), "name": "salt"})
        assert response.status_code == 200, response.text
        yield test_client


def test_a_new_source_shows_metrics_immediately(client):
    metrics = client.get("/api/metrics", params={"source": "salt"}).json()["metrics"]
    assert len(metrics) >= 5
    assert {m["status"] for m in metrics} == {"approved"}   # exact facts


def test_drafts_can_be_previewed_but_not_served(client):
    name = client.get("/api/metrics", params={"source": "salt"}).json()["metrics"][0]["name"]
    client.post(f"/api/metrics/{name}/status", json={"source": "salt", "status": "draft"})
    served = client.post(f"/api/metrics/{name}/evaluate", json={"source": "salt"})
    assert served.status_code == 404
    preview = client.post(f"/api/metrics/{name}/evaluate",
                          json={"source": "salt", "preview_draft": True})
    assert preview.status_code == 200 and preview.json()["rows"]
    assert preview.json()["status"] == "draft"


def test_approving_a_metric_makes_it_servable(client):
    approved = client.post("/api/metrics/sales_documents_count/status",
                           json={"source": "salt", "status": "approved"})
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    served = client.post("/api/metrics/sales_documents_count/evaluate", json={"source": "salt"})
    assert served.status_code == 200


def test_bad_status_and_unknown_metric_are_rejected(client):
    assert client.post("/api/metrics/sales_documents_count/status",
                       json={"source": "salt", "status": "nonsense"}).status_code == 400
    assert client.post("/api/metrics/nope/status",
                       json={"source": "salt", "status": "approved"}).status_code == 404


def _all_to_draft(client):
    for metric in client.get("/api/metrics", params={"source": "salt"}).json()["metrics"]:
        client.post(f"/api/metrics/{metric['name']}/status",
                    json={"source": "salt", "status": "draft"})


def test_approve_all_proposed(client):
    _all_to_draft(client)
    result = client.post("/api/metrics/approve-proposed", json={"source": "salt"}).json()
    assert result["approved"]
    metrics = client.get("/api/metrics", params={"source": "salt"}).json()["metrics"]
    assert {m["status"] for m in metrics} == {"approved"}


def test_insights_preview_gives_a_trend_for_drafts(client):
    insights = client.get("/api/metrics/sales_documents_count/insights", params={
        "source": "salt", "preview_draft": "true", "grain": "month"}).json()
    periods = [point["period"][:7] for point in insights["trend"]]
    assert periods[-3:] == ["2024-02", "2024-03", "2024-04"]


# ----------------------------------------------------- context suggestions
def test_context_suggestions_come_from_this_dataset(client):
    client.post("/api/metrics/approve-proposed", json={"source": "salt"})
    suggestions = client.get("/api/context/suggestions",
                             params={"source": "salt"}).json()["questions"]
    texts = [s["text"] for s in suggestions]
    assert len(texts) >= 4
    blob = " ".join(texts)
    assert "April 2024" in blob                     # the latest month in the data
    assert "sales documents" in blob.lower()
    assert "revenue" not in blob.lower()             # nothing from another dataset
    assert all(s["preset"] for s in suggestions)


def test_a_suggested_question_is_answerable(client):
    client.post("/api/metrics/approve-proposed", json={"source": "salt"})
    question = client.get("/api/context/suggestions",
                          params={"source": "salt"}).json()["questions"][0]["text"]
    pack = client.get("/api/context", params={
        "source": "salt", "question": question, "budget_chars": 4000}).json()
    assert pack["answerable"]["verdict"] in ("yes", "partial")
    assert pack["facts"]


def test_suggestions_before_any_approval_say_so(client):
    _all_to_draft(client)
    suggestions = client.get("/api/context/suggestions",
                             params={"source": "salt"}).json()
    assert suggestions["note"]
    assert "approve" in suggestions["note"].lower()


def test_context_honours_the_month_named_in_the_question(client):
    client.post("/api/metrics/approve-proposed", json={"source": "salt"})
    pack = client.get("/api/context", params={
        "source": "salt", "budget_chars": 4000,
        "question": "How did the number of sales documents change in March 2024?"}).json()
    assert pack["period"]["label"] == "2024-03"


def test_context_pack_carries_chart_series(client):
    client.post("/api/metrics/approve-proposed", json={"source": "salt"})
    pack = client.get("/api/context", params={
        "source": "salt", "budget_chars": 4000,
        "question": "How did the number of sales documents change in April 2024?"}).json()
    charts = pack["charts"]
    assert [p["period"][:7] for p in charts["trend"]][-2:] == ["2024-03", "2024-04"]
    assert charts["breakdown"]["dimension"]
    assert charts["breakdown"]["rows"]


# ------------------------------------------- lessons from the real SALT data
@pytest.mark.parametrize("table, words", [
    ("i_salesdocumentitem", "sales document item"),
    ("i_addrorgnamepostaladdress", "addr org name postal address"),
    ("sales_documents", "sales documents"),
    ("customer", "customer"),
    ("xqzvb", "xqzvb"),                        # nothing to segment: unchanged
])
def test_run_together_table_names_become_words(table, words):
    assert autopilot._noun(table) == words


def test_ml_split_tables_are_skipped_even_without_a_base_table(tmp_path):
    folder = tmp_path / "ml"
    _write_salt_like(folder, train_copy=False)
    (folder / "joined_tables_train.csv").write_text(
        "SALESDOCUMENT,PLANT,CREATIONDATE\nD0001,P1,2024-02-01\nD0002,P0,2024-03-01\n",
        encoding="utf-8")
    layer = MiddleLayer(str(tmp_path / "ml.duckdb"))
    try:
        layer.add_source(str(folder), source="ml")
        bundle = layer._bundle("ml")
        proposals = autopilot.propose_metrics(layer.graph, bundle.schema, bundle.onto, "ml")
        assert not [p for p in proposals if "train" in p["name"]]
        assert proposals                         # the real tables still count
    finally:
        layer.close()


def test_near_unique_identifiers_are_not_distinct_count_metrics(tmp_path):
    folder = tmp_path / "addr"
    folder.mkdir()
    rows = ["ADDRESSID,ALTID,COUNTRY,REGION"]
    for i in range(500):
        rows.append(f"A{i},X{i if i % 50 else 0},C{i % 7},R{i % 90}")
    (folder / "addresses.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    layer = MiddleLayer(str(tmp_path / "a.duckdb"))
    try:
        layer.add_source(str(folder), source="addr")
        bundle = layer._bundle("addr")
        exprs = [p["value_expr"] for p in autopilot.propose_metrics(
            layer.graph, bundle.schema, bundle.onto, "addr")]
        assert not any("ADDRESSID" in e or "ALTID" in e for e in exprs), exprs
        assert any("REGION" in e for e in exprs)
    finally:
        layer.close()


def test_time_of_day_columns_are_never_references():
    from types import SimpleNamespace as NS
    assert autopilot._is_temporal(NS(name="CREATIONTIME", type="TIME WITH TIME ZONE"))
    assert autopilot._is_temporal(NS(name="d", type="TIMESTAMP_NS"))
    assert autopilot._is_temporal(NS(name="d", type="DATE"))
    assert not autopilot._is_temporal(NS(name="TIMEZONE_NAME", type="VARCHAR"))


@pytest.mark.parametrize("column, words", [
    ("SHIPTOPARTY", "ship to party"),
    ("CUSTOMERPAYMENTTERMS", "customer payment terms"),
    ("line_revenue", "line revenue"),
    ("zzqx", "zzqx"),
])
def test_column_labels_become_words(column, words):
    assert autopilot._human(column) == words


def test_insights_without_a_period_compare_the_latest_month(client):
    insights = client.get("/api/metrics/sales_documents_count/insights", params={
        "source": "salt", "preview_draft": "true"}).json()
    assert insights["dimension"]                       # first dimension is used
    assert insights["contributors"]
    assert insights["comparison"]["prior"] is not None  # April vs March


# ------------------------------------------------------- time intelligence
def test_insights_report_the_datas_own_time_range_and_grain(client):
    insights = client.get("/api/metrics/sales_documents_count/insights", params={
        "source": "salt", "preview_draft": "true"}).json()
    assert insights["time_range"]["min"].startswith("2024-02-01")
    assert insights["time_range"]["max"].startswith("2024-04-30")
    assert insights["grain"] == "week"           # 3 months of data: weekly points


@pytest.mark.parametrize("grain, first", [
    ("month", "2024-02"), ("quarter", "2024-01"), ("year", "2024-01"),
])
def test_trend_can_be_asked_for_at_any_grain(client, grain, first):
    insights = client.get("/api/metrics/sales_documents_count/insights", params={
        "source": "salt", "preview_draft": "true", "grain": grain}).json()
    assert insights["grain"] == grain
    assert insights["trend"][0]["period"].startswith(first)
    assert sum(p["value"] for p in insights["trend"]) == 120   # every document counted


def test_an_unknown_grain_is_rejected(client):
    response = client.get("/api/metrics/sales_documents_count/insights", params={
        "source": "salt", "preview_draft": "true", "grain": "fortnight"})
    assert response.status_code == 400


@pytest.mark.parametrize("days, grain", [
    (20, "day"), (90, "week"), (700, "month"), (2000, "quarter"), (5000, "year"),
])
def test_grain_is_chosen_from_the_span_of_the_data(days, grain):
    assert metric_defs.auto_grain(days) == grain
