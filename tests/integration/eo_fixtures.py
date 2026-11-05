"""Shared setup for the Ontology Accelerator tests: the BI/MDM scenario loaded
as five Strata sources, plus an ontology created from the intake."""

from __future__ import annotations

import json

from api.service import MiddleLayer
from datasets.generate_bi_mdm import generate
from ontology import registry as reg

from ontology.demo import INTAKE, SOURCES  # noqa: E402,F401 - one definition


def load_scenario(tmp_path, customers: int = 300, seed: int = 7,
                  ontology_id: str = "sales", mutate=None):
    """`mutate(root, truth)` may rewrite the files before they are loaded
    (e.g. strip meaningful column names) and must return the updated truth."""
    root = generate(tmp_path / "scenario", seed=seed, customers=customers)
    truth = json.loads((root / "ground_truth.json").read_text(encoding="utf-8"))
    if mutate is not None:
        truth = mutate(root, truth)
    layer = MiddleLayer(str(tmp_path / "eo.duckdb"))
    for name in SOURCES:
        layer.add_source(str(root / name), source=f"bi_{name}")
    reg.create(layer.graph, ontology_id, **INTAKE, sources=[
        {"source_id": f"bi_{name}", "role": role, "owner_team": team,
         "cadence_days": cadence}
        for name, (role, team, cadence) in SOURCES.items()])
    return layer, truth, root


def run_steps(layer, ontology_id: str = "sales", upto: str = "mapping") -> dict:
    """Run the journey's steps in order up to and including `upto`."""
    from importlib import import_module
    steps = [("profile", "ontology.profile", "profile_ontology"),
             ("concepts", "ontology.concepts", "propose_concepts"),
             ("mapping", "ontology.mapping", "map_properties"),
             ("structure", "ontology.structure", "propose_structure"),
             ("identity", "ontology.identity", "resolve_identities"),
             ("survivorship", "ontology.survivorship", "assess"),
             ("rules", "ontology.rules", "propose_rules")]
    out = {}
    for name, module, func in steps:
        out[name] = getattr(import_module(module), func)(layer, ontology_id)
        if name == upto:
            return out
    raise ValueError(f"unknown step {upto!r}")
