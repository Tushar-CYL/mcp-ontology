"""Apply the engine's schema and project ontology.yaml into the registries.

The ontology file is the source of truth. This loads it into the database so
every row of the graph can be traced back to a versioned class or relation,
and so a rename in the YAML cannot silently diverge from what is stored.

Engine comes from OKG_ENGINE (duckdb | postgres); the SQL is read from
sql/<engine>/schema.sql. Everything in this file is engine-agnostic.

Usage:
    python graph/apply_schema.py
    python graph/apply_schema.py --reset       # drop everything first
    OKG_ENGINE=postgres python graph/apply_schema.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import as_list, load_ontology, ontology_sha  # noqa: E402
from db import connect  # noqa: E402

DROP_TABLES = [
    "validation_findings", "validation_run", "ingest_log",
    "node_alias", "edges", "nodes", "calls",
    "stg_callgraph", "stg_msmetrics", "stg_nodemetrics", "stg_msrtmcr",
    "node_metrics", "ms_metrics", "ms_rt_mcr",
    "rule_registry", "relation_registry", "class_registry",
    "ontology_version", "meta",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true",
                    help="drop all objects before applying (destroys data)")
    args = ap.parse_args()

    onto = load_ontology()
    ver = onto["version"]
    sha = ontology_sha()

    with connect() as db:
        if args.reset:
            print("resetting schema (dropping all objects)")
            for t in DROP_TABLES:
                db.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
            db.execute("DROP SEQUENCE IF EXISTS validation_run_seq")

        schema = db.sql_dir() / "schema.sql"
        db.script(schema)
        print(f"applied {db.engine}/{schema.name}")

        db.execute("DELETE FROM ontology_version WHERE version = ?", [ver])
        db.execute(
            "INSERT INTO ontology_version(version, dataset, source_sha) "
            "VALUES (?, ?, ?)", [ver, onto["dataset"], sha])

        # Replace rather than upsert: the registries are a projection of the
        # YAML, so the YAML winning outright is the correct semantics.
        db.execute("DELETE FROM class_registry")
        for name, c in onto["classes"].items():
            db.execute(
                "INSERT INTO class_registry"
                "(code, name, provenance, key_spec, description, version) "
                "VALUES (?,?,?,?,?,?)",
                [c["code"], name, c["provenance"], c.get("key"),
                 (c.get("description") or "").strip(), ver])

        db.execute("DELETE FROM relation_registry")
        for name, r in onto["relations"].items():
            db.execute(
                "INSERT INTO relation_registry"
                "(code, name, domain, range, temporal, transitive,"
                " provenance, description, version) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [r["code"], name, as_list(r["domain"]), as_list(r["range"]),
                 bool(r.get("temporal")), bool(r.get("transitive")),
                 r["provenance"], (r.get("description") or "").strip(), ver])

        db.execute("DELETE FROM rule_registry")
        for rule in onto["rules"]:
            db.execute(
                "INSERT INTO rule_registry"
                "(id, severity, applies_to, repair, description, version) "
                "VALUES (?,?,?,?,?,?)",
                [rule["id"], rule["severity"], rule["applies_to"],
                 rule["repair"], (rule.get("description") or "").strip(), ver])

        nc = db.one("SELECT count(*) FROM class_registry")
        nr = db.one("SELECT count(*) FROM relation_registry")
        nu = db.one("SELECT count(*) FROM rule_registry")
        assert nc == len(onto["classes"]), f"{nc} classes != yaml"
        assert nr == len(onto["relations"]), f"{nr} relations != yaml"
        assert nu == len(onto["rules"]), f"{nu} rules != yaml"

        # The id macro must be deterministic, and the name lookups must
        # resolve -- both are relied on by every later build step.
        a = db.one("SELECT node_id(4, 'checkout')")
        b = db.one("SELECT node_id(4, 'checkout')")
        assert a == b and a is not None, "node_id is not deterministic"
        assert db.one("SELECT rel_code('calls')") == \
            onto["relations"]["calls"]["code"], "rel_code lookup broken"
        assert db.one("SELECT valid_at(TIMESTAMP '2022-01-01', NULL, "
                      "TIMESTAMP '2022-06-01')"), "valid_at broken"

        print(f"ontology v{ver} (sha {sha}) loaded: "
              f"{nc} classes, {nr} relations, {nu} rules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
