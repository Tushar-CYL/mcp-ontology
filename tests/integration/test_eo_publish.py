"""Step 9: governance and publishing - where the ontology lives.

* Ownership (maturity L2): a concept shared across systems is CORE and owned
  by the governance team; a single-system concept is an EXTENSION owned by
  that system's team. Approvals are restricted to approvers once roles exist.
* Publishing (L3/L4): approved items freeze into a numbered version with data
  contracts per source table, a diff against the previous version, and
  exports - OWL/Turtle, SHACL shapes, JSON - written as an ontology-as-code
  folder for the customer's own Git repo.
* Access: MCP tools read a PINNED version, so every agent and tool sees the
  same definitions.
"""

from __future__ import annotations

import json

import pytest

from api import mcp_server
from ontology import publish as pub
from ontology import registry as reg
from tests.integration.eo_fixtures import load_scenario, run_steps

rdflib = pytest.importorskip("rdflib")
KINDS = ("concept", "member", "property", "mapping", "relationship", "hierarchy",
         "identity", "survivorship", "rule", "action")


def _approve_everything(graph, by="ana"):
    for kind in KINDS:
        reg.approve_all(graph, "sales", kind=kind, by=by)


@pytest.fixture(scope="module")
def published(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("pub")
    layer, truth, _ = load_scenario(tmp)
    run_steps(layer, upto="rules")
    pub.assign_owners(layer.graph, "sales")
    _approve_everything(layer.graph)
    v1 = pub.publish_version(layer, "sales", by="ana", notes="first release")
    reg.decide(layer.graph, "sales", "mapping", "bi_erp.sales_orders.FRACHT", "edited",
               by="ana", payload={**reg.get_item(layer.graph, "sales", "mapping",
                                                 "bi_erp.sales_orders.FRACHT")["payload"],
                                  "definition": "Freight billed to the customer."})
    v2 = pub.publish_version(layer, "sales", by="ana", notes="clarify freight")
    folder = pub.export_folder(layer.graph, "sales", tmp / "repo")
    yield layer, truth, v1, v2, folder
    layer.close()


# --------------------------------------------------------------- owners
def test_shared_concepts_are_core_and_owned_by_governance(published):
    layer, _, _, _, _ = published
    customer = reg.get_item(layer.graph, "sales", "concept", "Customer")
    assert customer["owner"] == "Data Governance"
    assert customer["payload"]["tier"] == "core"
    order = reg.get_item(layer.graph, "sales", "concept", "SalesOrder")
    assert order["owner"] == "Finance IT"
    assert order["payload"]["tier"] == "extension"
    net = reg.get_item(layer.graph, "sales", "mapping", "bi_erp.sales_orders.NETWR")
    assert net["owner"] == "Finance IT"


def test_only_approvers_may_decide_once_roles_exist(tmp_path):
    from knowledge_graph.store import open_graph
    g = open_graph(str(tmp_path / "r.duckdb"))
    reg.create(g, "o", name="o")
    reg.put(g, "o", "concept", "A", {})
    reg.decide(g, "o", "concept", "A", "approved", by="anyone")      # bootstrap: no roles
    reg.put(g, "o", "concept", "B", {})
    reg.grant(g, "o", "ana", "approver")
    reg.grant(g, "o", "bob", "editor")
    with pytest.raises(PermissionError):
        reg.decide(g, "o", "concept", "B", "approved", by="bob")
    reg.decide(g, "o", "concept", "B", "approved", by="ana")
    with pytest.raises(PermissionError):
        reg.publish(g, "o", by="bob")
    with pytest.raises(ValueError):
        reg.grant(g, "o", "eve", "emperor")
    assert {r["user"]: r["role"] for r in reg.roles(g, "o")} == {"ana": "approver",
                                                                 "bob": "editor"}
    g.close()


# ------------------------------------------------------------- versions
def test_versions_and_diff(published):
    layer, _, v1, v2, _ = published
    assert (v1["version"], v2["version"]) == (1, 2)
    diff = reg.diff(layer.graph, "sales", 1, 2)
    assert {"kind": "mapping", "key": "bi_erp.sales_orders.FRACHT"} in diff["changed"]
    assert diff["added"] == [] and diff["removed"] == []


def test_versions_contain_contracts_per_source_table(published):
    _, truth, v1, _, _ = published
    contracts = {i["key"]: i["payload"] for i in v1["items"] if i["kind"] == "contract"}
    orders = contracts["bi_erp.sales_orders"]
    assert orders["key"] == "VBELN"
    assert {c["name"] for c in orders["columns"]} >= {"NETWR", "BRTWR", "WAERK"}
    assert orders["freshness_sla_days"] == 1
    assert orders["rows"] == truth["customers"] * 10
    assert contracts["bi_mdm.golden_customers"]["freshness_sla_days"] == 7


# -------------------------------------------------------------- exports
def test_turtle_parses_and_holds_the_ontology(published):
    layer, _, _, _, _ = published
    ttl = pub.to_turtle(layer.graph, "sales")
    g = rdflib.Graph().parse(data=ttl, format="turtle")
    OWL, RDF, RDFS = rdflib.OWL, rdflib.RDF, rdflib.RDFS
    classes = {str(g.value(s, RDFS.label)) for s in g.subjects(RDF.type, OWL.Class)}
    assert {"Customer", "SalesOrder", "Invoice", "SalesMonthly"} <= classes
    comments = " ".join(str(o) for o in g.objects(None, RDFS.comment))
    assert "Value after discounts" in comments
    assert "Freight billed to the customer." in comments          # v2 edit
    assert any(g.subjects(RDF.type, OWL.ObjectProperty))
    skos = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")
    assert any(g.subjects(skos.broader, None))                   # region > country


def test_shacl_shapes_parse_and_constrain_values(published):
    layer, _, _, _, _ = published
    ttl = pub.to_shacl(layer.graph, "sales")
    g = rdflib.Graph().parse(data=ttl, format="turtle")
    sh = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    shapes = list(g.subjects(rdflib.RDF.type, sh.NodeShape))
    assert len(shapes) >= 4
    values = {str(v) for v in g.objects(None, rdflib.RDF.first)}
    assert {"EUR", "USD", "GBP"} <= values                      # currency sh:in list


def test_the_git_folder_is_complete(published):
    _, _, _, _, folder = published
    names = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
    assert {"README.md", "ontology.ttl", "shapes.ttl", "ontology.json",
            "CHANGELOG.md"} <= names
    assert any(n.startswith("concepts/") for n in names)
    assert any(n.startswith("contracts/") for n in names)
    changelog = (folder / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "Version 2" in changelog and "bi_erp.sales_orders.FRACHT" in changelog
    doc = json.loads((folder / "ontology.json").read_text(encoding="utf-8"))
    assert doc["version"] == 2


# ------------------------------------------------------------------ MCP
def _call(layer, name, args=None, scope=None):
    response = mcp_server.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": name, "arguments": args or {}}}, layer, scope=scope)
    if "error" in response:
        return response["error"]
    return json.loads(response["result"]["content"][0]["text"])


def test_mcp_lists_the_ontology_tools():
    names = {t["name"] for t in mcp_server.TOOLS}
    assert {"list_concepts", "get_concept", "map_column", "resolve_entity",
            "get_contract", "validate_rules", "ontology_version"} <= names


def test_mcp_map_column_answers_what_a_column_means(published):
    layer, _, _, _, _ = published
    got = _call(layer, "map_column", {"column": "bi_erp.sales_orders.NETWR"})
    assert got["property"] == "net_amount"
    assert "Value after discounts" in got["definition"]
    assert got["version"] == 2
    mart = _call(layer, "map_column", {"column": "bi_mart.sales_monthly.revenue"})
    assert mart["property"] == "gross_amount"
    assert any(f["type"] == "wrong_amount_column" for f in mart["findings"])


def test_mcp_reads_a_pinned_version(published):
    layer, _, _, _, _ = published
    v1 = _call(layer, "map_column", {"column": "bi_erp.sales_orders.FRACHT", "version": 1})
    v2 = _call(layer, "map_column", {"column": "bi_erp.sales_orders.FRACHT"})
    assert v1["definition"] != v2["definition"]
    assert v2["definition"] == "Freight billed to the customer."


def test_mcp_concepts_entities_contracts_rules(published):
    layer, truth, _, _, _ = published
    concepts = _call(layer, "list_concepts")
    assert {c["name"] for c in concepts["concepts"]} >= {"Customer", "SalesOrder"}
    customer = _call(layer, "get_concept", {"concept": "Customer"})
    assert customer["master"] == "bi_mdm.golden_customers"
    assert customer["properties"] and customer["relationships"]
    e = truth["identity"][3]
    entity = _call(layer, "resolve_entity", {"value": e["billing_ref"]})
    assert entity["entity_id"] == e["mdm_id"]
    assert entity["golden"]["customer_name"]["value"]
    contract = _call(layer, "get_contract", {"table": "bi_erp.sales_orders"})
    assert contract["key"] == "VBELN"
    rules = _call(layer, "validate_rules")
    assert any(r["violations"] for r in rules["rules"])
    version = _call(layer, "ontology_version")
    assert version["version"] == 2 and version["published_by"] == "ana"


def test_mcp_respects_the_agent_scope(published):
    layer, _, _, _, _ = published
    scope = {"agent_id": "x", "sources": ["somewhere_else"], "metrics": [],
             "tools": ["list_concepts"]}
    got = _call(layer, "list_concepts", scope=scope)
    assert got["code"] == mcp_server.FORBIDDEN
    scope["sources"] = ["bi_erp"]
    assert _call(layer, "list_concepts", scope=scope)["concepts"]
