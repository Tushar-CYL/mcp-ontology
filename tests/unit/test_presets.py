"""Agent presets: one orchestrator, six small read-mostly tool bundles.

Research (docs/research/2026/05_agents.md): Snowflake, Fabric, Databricks and
Palantir all run one orchestrating agent over typed tools; none sells
separate "graph" or "guide" agents. Strata's six agent types are presets of
one runtime, each a least-privilege tool subset that maps to an MCP scope.
"""

from __future__ import annotations

import pytest

from agent.presets import PRESETS, get_preset, tools_for
from api.mcp_server import TOOLS

ALL_TOOLS = {tool["name"] for tool in TOOLS}
LAYERS = {"ontology", "graph", "semantic", "context"}


def test_the_six_presets_exist_in_display_order():
    assert list(PRESETS) == ["data_guide", "metric", "entity", "insight",
                             "trust", "steward"]


@pytest.mark.parametrize("preset_id", list(PRESETS))
def test_every_preset_is_complete(preset_id):
    p = PRESETS[preset_id]
    assert p["id"] == preset_id
    assert p["title"] and p["job"] and p["output"]
    assert set(p["layers"]) <= LAYERS and p["layers"]
    assert p["guardrails"]
    assert len(p["examples"]) == 3
    assert set(p["tools"]) <= ALL_TOOLS, set(p["tools"]) - ALL_TOOLS
    assert "list_sources" in p["tools"]          # every agent can orient itself


def test_only_the_steward_can_propose_changes():
    writers = [pid for pid, p in PRESETS.items() if "propose_change" in p["tools"]]
    assert writers == ["steward"]


def test_the_data_guide_never_touches_rows_or_numbers():
    tools = set(PRESETS["data_guide"]["tools"])
    assert not tools & {"evaluate_metric", "get_context", "get_entity_context",
                        "graph_neighbours"}


def test_the_metric_analyst_checks_its_own_sql():
    assert "validate_sql" in PRESETS["metric"]["tools"]
    assert "evaluate_metric" in PRESETS["metric"]["tools"]


def test_the_entity_investigator_uses_the_graph():
    assert {"graph_neighbours", "get_entity_context"} <= set(PRESETS["entity"]["tools"])
    assert PRESETS["entity"]["layers"][0] == "graph"


def test_the_insight_analyst_is_the_orchestrator_over_all_four_layers():
    insight = PRESETS["insight"]
    assert set(insight["layers"]) == LAYERS
    assert set(insight["tools"]) == ALL_TOOLS - {"propose_change"}


def test_the_trust_checker_is_read_only_and_cannot_compute_new_numbers():
    tools = set(PRESETS["trust"]["tools"])
    assert "check_readiness" in tools and "propose_change" not in tools
    assert "evaluate_metric" not in tools


def test_get_preset_defaults_and_rejects_unknown():
    assert get_preset(None)["id"] == "insight"
    assert get_preset("")["id"] == "insight"
    assert get_preset("metric")["id"] == "metric"
    with pytest.raises(ValueError, match="unknown agent type"):
        get_preset("hacker")


def test_tools_for_returns_a_copy():
    tools = tools_for("metric")
    tools.append("propose_change")
    assert "propose_change" not in tools_for("metric")
