"""Evidence API - unified evidence drawer for any fact."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from knowledge_graph.build import qi, table_ref, source_name, source_slug
from review import store as review_store
from ontology import business_rules


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_evidence_for_fact(
    graph,
    schema,
    onto,
    source: str,
    fact: dict
) -> dict:
    """Get complete evidence drawer data for a fact."""
    evidence = {
        "text": fact.get("text", ""),
        "provenance": fact.get("provenance", "unknown"),
        "citation": fact.get("citation", ""),
        "as_of": fact.get("as_of"),
        "confidence": fact.get("confidence", 1.0),
    }
    
    # Try to enrich with source info
    citation = fact.get("citation", "")
    if citation.startswith("row:"):
        # Source row evidence
        table_name = citation.split(":")[1]
        evidence["source"] = f"Source table: {table_name}"
        evidence["check"] = "Direct source row"
        evidence["count"] = 1
    elif citation.startswith("metric:"):
        evidence["source"] = "Metric definition"
        evidence["check"] = "Approved metric definition"
    elif citation.startswith("metric_") or citation.startswith("context_") or citation.startswith("relationship:"):
        evidence["source"] = "System derivation"
    
    # Check for review status
    try:
        pending = review_store.pending_items_for_fact(fact)
        if pending:
            evidence["approver"] = "Pending review"
            evidence["agreed_by"] = len(pending)
    except Exception:
        pass
    
    # Check business rules
    try:
        rule = business_rules.get_applicable_rule(fact)
        if rule:
            evidence["check"] = f"Business rule: {rule.name}"
            evidence["approver"] = rule.get("owner", "System")
    except Exception:
        pass
    
    return evidence