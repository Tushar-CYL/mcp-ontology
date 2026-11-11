"""Agent presets: six agent types, one runtime.

Every vendor in the research (Snowflake Cortex Agents, Fabric data agents,
Databricks Agent Bricks, Palantir AIP) runs ONE orchestrating agent over a
few typed tools; none sells separate "graph" or "guide" agents, and Databricks
now calls its multi-agent Supervisor "legacy". So Strata's agent types are
presets: a least-privilege tool subset, a job, guardrails and an output
template. The same subset is the agent's MCP scope for external clients.

See docs/research/2026/05_agents.md and REPORT.md ("Agent types Strata
should offer").
"""

from __future__ import annotations

_GENERAL = ["list_sources", "check_readiness", "search"]

PRESETS: dict[str, dict] = {
    "data_guide": {
        "id": "data_guide",
        "title": "Data Guide",
        "job": "Explains what data exists and what it means: the kinds of "
               "thing, how they link, which metrics are approved.",
        "layers": ["ontology", "semantic"],
        "tools": [*_GENERAL, "list_entities", "describe_table", "list_metrics",
                  "get_ontology", "list_concepts", "get_concept", "map_column", "ontology_version", "ask_question"],
        "guardrails": ["Reads metadata only; never returns data rows or "
                       "numbers", "Personal-data columns are flagged"],
        "output": "Plain explanation of the entity or source, its links and "
                  "the metrics built on it.",
        "examples": ["What data do we have?", "What is an Order?",
                     "How do orders link to customers?"],
    },
    "metric": {
        "id": "metric",
        "title": "Metric Analyst",
        "job": "Gives the governed number: an approved metric for a period, "
               "compared with the previous one, optionally split by a "
               "dimension.",
        "layers": ["semantic"],
        "tools": [*_GENERAL, "list_metrics", "get_metric", "evaluate_metric",
                  "validate_sql", "check_answerable"],
        "guardrails": ["Approved metrics in scope only", "Refuses and names "
                       "the nearest approved metric otherwise",
                       "Checks hand-written SQL with validate_sql"],
        "output": "The number, the prior period, the change and the SQL it "
                  "came from.",
        "examples": ["What was revenue last month?",
                     "Revenue by region compared with the previous month",
                     "What were West sales in October 2026?"],
    },
    "entity": {
        "id": "entity",
        "title": "Entity Investigator",
        "job": "Tells you everything about one thing, like a customer or an "
               "order: what it is linked to and the evidence behind it.",
        "layers": ["graph", "ontology", "context"],
        "tools": [*_GENERAL, "list_entities", "describe_table",
                  "graph_neighbours", "get_entity_context", "resolve_entity"],
        "guardrails": ["One source only", "At most 2 hops and 25 listed "
                       "links per relation", "Personal data removed"],
        "output": "What the entity is, what it links to, and cited facts.",
        "examples": ["Tell me about customer c1", "What is order o2 linked to?",
                     "Show product p1 and its orders"],
    },
    "insight": {
        "id": "insight",
        "title": "Insight Analyst",
        "job": "Answers why something changed and whether you can trust it, "
               "using all four layers. This is the orchestrator the other "
               "presets are subsets of.",
        "layers": ["ontology", "graph", "semantic", "context"],
        "tools": [*_GENERAL, "list_entities", "describe_table",
                  "graph_neighbours", "get_entity_context", "list_metrics",
                  "get_metric", "evaluate_metric", "validate_sql",
                  "check_answerable", "get_context", "explain_citation",
                  "get_ontology", "list_concepts", "get_concept", "map_column", "resolve_entity",
                  "get_contract", "validate_rules", "ontology_version", "ask_question"],
        "guardrails": ["Every number comes from an approved metric",
                       "Answers only when the evidence is sufficient; says "
                       "so plainly otherwise", "Read-only"],
        "output": "Cause, impact and next step, each backed by cited "
                  "evidence, plus a confidence label.",
        "examples": ["Why did West revenue fall in October 2026, and can I "
                     "trust it?", "Which segment drove the revenue change?",
                     "Why did sales drop last month?"],
    },
    "trust": {
        "id": "trust",
        "title": "Trust Checker",
        "job": "Answers 'can I trust this number?': metric health, "
               "freshness, caveats, certification and evidence coverage.",
        "layers": ["semantic", "context", "ontology"],
        "tools": [*_GENERAL, "list_metrics", "get_metric", "check_answerable",
                  "explain_citation", "validate_rules", "get_contract",
                  "map_column"],
        "guardrails": ["Read-only", "Reports problems instead of fixing them",
                       "Never computes a new number"],
        "output": "A trust verdict with the checks that passed and failed.",
        "examples": ["Can I trust the revenue number?",
                     "Is order volume data fresh?",
                     "What caveats apply to revenue?"],
    },
    "steward": {
        "id": "steward",
        "title": "Steward",
        "job": "Suggests improvements, such as a synonym for a metric, and "
               "files them for a person to approve. It never changes "
               "anything itself.",
        "layers": ["semantic", "ontology"],
        "tools": ["list_sources", "search", "list_entities", "list_metrics",
                  "get_metric", "propose_change", "get_ontology", "list_concepts", "get_concept",
                  "map_column", "resolve_entity", "get_contract", "validate_rules",
                  "ontology_version", "ask_question"],
        "guardrails": ["Proposal only: a person must approve every change",
                       "Every proposal is audited"],
        "output": "The proposal as filed, waiting for approval.",
        "examples": ['"sales" means revenue',
                     "add synonym orders count for order volume",
                     "Customers should be linked to regions"],
    },
}

DEFAULT_PRESET = "insight"


def get_preset(preset_id: str | None) -> dict:
    preset_id = (preset_id or "").strip() or DEFAULT_PRESET
    if preset_id not in PRESETS:
        raise ValueError(f"unknown agent type {preset_id!r}; choose one of "
                         + ", ".join(PRESETS))
    return PRESETS[preset_id]


def tools_for(preset_id: str | None) -> list[str]:
    return list(get_preset(preset_id)["tools"])
