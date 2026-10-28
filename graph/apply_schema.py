"""Apply the engine's schema and project ontology.yaml into the registries.

The ontology file is the source of truth. This loads it into the database so
every row of the graph can be traced back to a versioned class or relation,
and so a rename in the YAML cannot silently diverge from what is stored.

Engine comes from OKG_ENGINE (duckdb | postgres); the SQL is read from
sql/<engine>/core.sql plus domains/<domain>/sql/<engine>/staging.sql.

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
from common import DOMAIN, as_list, load_ontology, ontology_sha  # noqa: E402
from db import connect  # noqa: E402

def user_tables(db) -> list[str]:
    """Every table in this database, discovered rather than listed.

    An earlier version hard-coded the table names, which meant --reset
    silently left a second domain's tables standing - and a stale staging
    table that nothing rebuilds is worse than one that was never created,
    because every later query still finds it. Each domain has its own
    database file, so dropping everything here is correct.
    """
    if db.engine == "duckdb":
        return [r[0] for r in db.query(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_type = 'BASE TABLE'")]
    return [r[0] for r in db.query(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")]


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
            tables = user_tables(db)
            print(f"resetting schema for domain {DOMAIN!r} "
                  f"({len(tables)} table(s))")
            for t in tables:
                db.execute(f'DROP TABLE IF EXISTS "{t}" CASCADE')
            db.execute("DROP SEQUENCE IF EXISTS validation_run_seq")

        # Core first - nodes, edges, registries, validation, the macros every
        # domain relies on - then this domain's staging tables. The order
        # matters: staging is free to reference a core macro, never the
        # reverse. If it ever needs to, the core was not general enough.
        core = db.core_sql_dir() / "core.sql"
        db.script(core)
        print(f"applied {db.engine}/core.sql")

        staging = db.sql_dir() / "staging.sql"
        if staging.exists():
            db.script(staging)
            print(f"applied {DOMAIN}/{db.engine}/staging.sql")

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
        # Check a relation this domain actually declares. Naming one here
        # ('calls') tied the shared driver to a single domain's vocabulary -
        # the first thing the second domain tripped over.
        probe = next(iter(onto["relations"]))
        assert db.one("SELECT rel_code(?)", [probe]) == \
            onto["relations"][probe]["code"], f"rel_code({probe}) broken"
        probe_c = next(iter(onto["classes"]))
        assert db.one("SELECT class_code(?)", [probe_c]) == \
            onto["classes"][probe_c]["code"], f"class_code({probe_c}) broken"
        assert db.one("SELECT valid_at(TIMESTAMP '2022-01-01', NULL, "
                      "TIMESTAMP '2022-06-01')"), "valid_at broken"

        print(f"ontology v{ver} (sha {sha}) loaded: "
              f"{nc} classes, {nr} relations, {nu} rules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
