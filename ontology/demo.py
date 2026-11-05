"""The BI/MDM demo: generate the scenario, load it as five sources, create the
ontology from its intake. Used by the API ("Load the demo") and the tests."""

from __future__ import annotations

from pathlib import Path

from datasets.generate_bi_mdm import generate
from ontology import registry as reg

SOURCES = {
    "crm": ("source_system", "Sales Ops", 1),
    "erp": ("source_system", "Finance IT", 1),
    "billing": ("source_system", "Billing", 1),
    "mdm": ("mdm_hub", "Data Governance", 7),
    "mart": ("data_mart", "BI Team", 7),
}
INTAKE = {
    "name": "Sales reporting",
    "problem": ("Monthly sales reports are late and disagree with finance. "
                "CRM, ERP and billing each hold customers under different ids, "
                "the MDM hub runs behind, and nobody is sure which of the many "
                "amount columns is net revenue."),
    "domain": "Sales / order-to-cash",
    "questions": ["What is net revenue by region per month?",
                  "Which customers are mastered twice?",
                  "Is the data mart's revenue the same number finance reports?"],
}
DEMO_ID = "sales"


def intake_sources(prefix: str = "bi_") -> list[dict]:
    return [{"source_id": f"{prefix}{name}", "role": role, "owner_team": team,
             "cadence_days": cadence}
            for name, (role, team, cadence) in SOURCES.items()]


def load_demo(add_source, graph, folder, customers: int = 300, seed: int = 7,
              ontology_id: str = DEMO_ID, progress=None) -> dict:
    """`add_source(path, name, progress)` loads one source (the platform's or
    the service's). Creates the ontology unless it already exists."""
    say = progress or (lambda _line: None)
    say("generating the BI/MDM scenario (CRM, ERP, billing, MDM hub, data mart)")
    root = generate(Path(folder), seed=seed, customers=customers)
    for name in SOURCES:
        say(f"loading {name}")
        add_source(str(root / name), f"bi_{name}", say)
    if not any(o["id"] == ontology_id for o in reg.list_ontologies(graph)):
        reg.create(graph, ontology_id, **INTAKE, sources=intake_sources())
        say(f"created ontology {ontology_id!r} from the intake")
    return {"ontology": ontology_id, "folder": str(root),
            "sources": [f"bi_{n}" for n in SOURCES]}
