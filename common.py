"""Ontology loading helpers. Engine-independent by construction.

Database access lives in db.py; this file must never import a driver. The
split matters because the ontology is the one artefact shared unchanged
between the DuckDB build and the Postgres build.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ONTOLOGY_PATH = ROOT / "ontology" / "ontology.yaml"
METRICS_PATH = ROOT / "semantic" / "metrics.yaml"


def load_ontology() -> dict:
    import yaml
    with ONTOLOGY_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_metrics() -> dict:
    import yaml
    with METRICS_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def ontology_sha() -> str:
    return hashlib.sha256(ONTOLOGY_PATH.read_bytes()).hexdigest()[:16]


def class_codes() -> dict[str, int]:
    return {n: c["code"] for n, c in load_ontology()["classes"].items()}


def relation_codes() -> dict[str, int]:
    return {n: r["code"] for n, r in load_ontology()["relations"].items()}


def as_list(v) -> list[str]:
    return v if isinstance(v, list) else [v]


# Note on where work happens:
# Python never computes node ids. The division of labour is
#
#   Python : extract the tar member, hand the CSV path to the engine.
#   SQL    : canonicalise, resolve entities, build nodes/edges/calls as
#            set-based statements using the node_id() macro.
#
# That keeps the heavy work inside the engine, which is parallel and can
# spill to disk, instead of in a single-threaded Python loop.
