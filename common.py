"""Ontology loading helpers, and which domain we are working in.

Database access lives in db.py; this file must never import a driver. The
split matters because the ontology is the one artefact shared unchanged
between the DuckDB build and the Postgres build.

A DOMAIN is a dataset plus the YAML that describes it. The engine - this
file, db.py, validate.py, compile.py, show.py, verify.py - is identical for
every domain; only domains/<name>/ changes. That is the product claim, and
having two domains is how we find out whether it is true.

Each domain gets its OWN database file. Class codes are per-ontology, so
Microservice=4 in one domain and Route=4 in another would silently collide
in a shared `nodes` table.

    OKG_DOMAIN=alibaba   microservice traces (the original)
    OKG_DOMAIN=flights   airports, airlines, routes, real flights
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOMAIN = os.environ.get("OKG_DOMAIN", "flights").lower()
DOMAIN_DIR = ROOT / "domains" / DOMAIN


def _require(p: Path) -> Path:
    if not p.exists():
        have = sorted(d.name for d in (ROOT / "domains").iterdir()
                      if d.is_dir()) if (ROOT / "domains").exists() else []
        raise SystemExit(
            f"domain {DOMAIN!r} has no {p.name}\n"
            f"  looked in: {p.parent}\n"
            f"  domains available: {', '.join(have) or '(none)'}\n"
            f"  set one with:  $env:OKG_DOMAIN = \"alibaba\"")
    return p


def ontology_path() -> Path:
    return _require(DOMAIN_DIR / "ontology.yaml")


def metrics_path() -> Path:
    return _require(DOMAIN_DIR / "metrics.yaml")


def load_ontology() -> dict:
    import yaml
    with ontology_path().open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_metrics() -> dict:
    import yaml
    with metrics_path().open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def ontology_sha() -> str:
    return hashlib.sha256(ontology_path().read_bytes()).hexdigest()[:16]


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
