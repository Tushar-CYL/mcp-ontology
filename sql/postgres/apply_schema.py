"""Apply graph/schema.sql and project ontology.yaml into the registry tables.

The ontology file is the source of truth. This loads it into the database so
every row of the graph can be traced back to a versioned class or relation,
and so a rename in the YAML cannot silently diverge from what is stored.

Usage:
    python graph/apply_schema.py            # idempotent
    python graph/apply_schema.py --reset    # DROP everything first
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, connect, load_ontology  # noqa: E402

DROP = """
DROP TABLE IF EXISTS validation_findings, validation_run, ingest_log,
     node_alias, edges, nodes, calls,
     stg_callgraph, stg_msmetrics, stg_nodemetrics, stg_msrtmcr,
     rule_registry, relation_registry, class_registry, ontology_version,
     meta CASCADE;
DROP FUNCTION IF EXISTS node_id(smallint, text),
     ensure_calls_partition(timestamptz), tms(bigint), trace_epoch() CASCADE;
"""


def as_list(v) -> list[str]:
    return v if isinstance(v, list) else [v]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true",
                    help="drop all objects before applying (destroys data)")
    args = ap.parse_args()

    sql_path = ROOT / "graph" / "schema.sql"
    sql = sql_path.read_text(encoding="utf-8")
    onto = load_ontology()
    ver = onto["version"]
    sha = hashlib.sha256(
        (ROOT / "ontology" / "ontology.yaml").read_bytes()).hexdigest()[:16]

    with connect() as conn:
        with conn.cursor() as cur:
            if args.reset:
                print("resetting schema (dropping all objects)")
                cur.execute(DROP)
                conn.commit()

            cur.execute(sql)
            conn.commit()
            print(f"applied {sql_path.name}")

            cur.execute(
                "INSERT INTO ontology_version(version, dataset, source_sha) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (version) DO UPDATE SET source_sha = EXCLUDED.source_sha",
                (ver, onto["dataset"], sha))

            for name, c in onto["classes"].items():
                cur.execute(
                    "INSERT INTO class_registry"
                    "(code, name, provenance, key_spec, description, version) "
                    "VALUES (%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (code) DO UPDATE SET "
                    "name=EXCLUDED.name, provenance=EXCLUDED.provenance, "
                    "key_spec=EXCLUDED.key_spec, description=EXCLUDED.description, "
                    "version=EXCLUDED.version",
                    (c["code"], name, c["provenance"], c.get("key"),
                     (c.get("description") or "").strip(), ver))

            for name, r in onto["relations"].items():
                cur.execute(
                    "INSERT INTO relation_registry"
                    "(code, name, domain, range, temporal, transitive,"
                    " provenance, description, version) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (code) DO UPDATE SET "
                    "name=EXCLUDED.name, domain=EXCLUDED.domain, "
                    "range=EXCLUDED.range, temporal=EXCLUDED.temporal, "
                    "transitive=EXCLUDED.transitive, provenance=EXCLUDED.provenance, "
                    "description=EXCLUDED.description, version=EXCLUDED.version",
                    (r["code"], name, as_list(r["domain"]), as_list(r["range"]),
                     bool(r.get("temporal")), bool(r.get("transitive")),
                     r["provenance"], (r.get("description") or "").strip(), ver))

            for rule in onto["rules"]:
                cur.execute(
                    "INSERT INTO rule_registry"
                    "(id, severity, applies_to, repair, description, version) "
                    "VALUES (%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (id) DO UPDATE SET "
                    "severity=EXCLUDED.severity, applies_to=EXCLUDED.applies_to, "
                    "repair=EXCLUDED.repair, description=EXCLUDED.description, "
                    "version=EXCLUDED.version",
                    (rule["id"], rule["severity"], rule["applies_to"],
                     rule["repair"], (rule.get("description") or "").strip(), ver))

            conn.commit()

            # Sanity: the registry must agree with the YAML, and node_id must
            # be stable and collision-free for the keys we are about to use.
            cur.execute("SELECT count(*) FROM class_registry WHERE version=%s", (ver,))
            nc = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM relation_registry WHERE version=%s", (ver,))
            nr = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM rule_registry WHERE version=%s", (ver,))
            nu = cur.fetchone()[0]
            cur.execute("SELECT node_id(4::smallint, 'checkout') = "
                        "node_id(4::smallint, 'checkout')")
            assert cur.fetchone()[0], "node_id is not deterministic"

            print(f"ontology v{ver} (sha {sha}) loaded: "
                  f"{nc} classes, {nr} relations, {nu} rules")
            assert nc == len(onto["classes"]) and nr == len(onto["relations"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
