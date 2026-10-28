"""Derive team ownership by community detection over the real call graph.

The trace carries no ownership data at all. Rather than invent an org chart,
teams are inferred from structure that IS measured: services that call each
other constantly are far more likely to belong together than services that
never interact. Conway's law, read backwards.

This is an INFERENCE and the graph says so. Every Team node and every
`owns` edge is tagged provenance=derived in the registry, and who_pages()
returns that provenance to the caller. An on-call rota guessed from a call
graph is a plausible hypothesis, not a fact, and anyone acting on it has to
be told which it is.

Method: Louvain community detection on the undirected, call-count-weighted
projection of the microservice graph. Seeded, so repeated runs over
identical input produce identical teams - without that, the graph would
differ between rebuilds and nothing downstream would be reproducible.

Microservices with no call edges in the slice get a singleton team, which
is the `assign_singleton_team` repair declared for the every_ms_has_team
rule.

Usage:
    python ingest/derive_teams.py
    python ingest/derive_teams.py --resolution 1.4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import connect  # noqa: E402

TEAM_CLASS = 22
OWNS_REL = 10
SEED = 20260101


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolution", type=float, default=1.0,
                    help="Louvain resolution; higher gives more, smaller teams")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    import networkx as nx

    with connect() as db:
        lo, hi = db.query(
            "SELECT min(valid_from), max(coalesce(valid_to, valid_from)) "
            "FROM edges WHERE rel = rel_code('calls')")[0]
        if lo is None:
            print("no calls edges; build the graph first")
            return 1

        edges = db.query(
            "SELECT src, dst, sum(weight) FROM edges "
            "WHERE rel = rel_code('calls') AND src <> dst "
            "GROUP BY src, dst")
        services = [r[0] for r in db.query(
            "SELECT id FROM nodes WHERE class = class_code('Microservice')")]

        print(f"{len(services):,} microservices, {len(edges):,} distinct "
              f"call pairs (self-calls excluded)")

        # Undirected weighted projection. Direction does not matter for
        # ownership: A calling B is as much evidence of a shared boundary
        # as B calling A.
        g = nx.Graph()
        g.add_nodes_from(services)
        for src, dst, w in edges:
            if g.has_edge(src, dst):
                g[src][dst]["weight"] += float(w or 1)
            else:
                g.add_edge(src, dst, weight=float(w or 1))

        communities = nx.community.louvain_communities(
            g, weight="weight", resolution=args.resolution, seed=args.seed)
        # Sort by size so team numbering is stable across runs.
        communities = sorted(communities, key=lambda c: (-len(c), min(c)))

        sizes = [len(c) for c in communities]
        singles = sum(1 for s in sizes if s == 1)
        print(f"{len(communities):,} communities  "
              f"largest={max(sizes):,}  median={sorted(sizes)[len(sizes)//2]}  "
              f"singletons={singles:,}")

        db.execute("DELETE FROM edges WHERE rel = ?", [OWNS_REL])
        db.execute("DELETE FROM nodes WHERE class = ?", [TEAM_CLASS])

        team_rows, owns_rows = [], []
        for i, members in enumerate(communities, start=1):
            key = f"TEAM_{i:04d}"
            team_rows.append((key, len(members)))
            for ms in members:
                owns_rows.append((key, ms))

        db.execute("CREATE OR REPLACE TEMP TABLE _teams"
                   "(team VARCHAR, size BIGINT)")
        db.raw.executemany("INSERT INTO _teams VALUES (?, ?)", team_rows)
        db.execute("CREATE OR REPLACE TEMP TABLE _owns"
                   "(team VARCHAR, ms BIGINT)")
        db.raw.executemany("INSERT INTO _owns VALUES (?, ?)", owns_rows)

        db.execute(
            "INSERT INTO nodes (id, class, nkey, props) "
            "SELECT node_id(?, team), ?, team, "
            "       json_object('size', size, 'method', 'louvain', "
            "                   'provenance', 'derived') "
            "FROM _teams", [TEAM_CLASS, TEAM_CLASS])

        db.execute(
            "INSERT INTO edges (src, rel, dst, valid_from, valid_to) "
            "SELECT node_id(?, team), ?, ms, ?, ? FROM _owns",
            [TEAM_CLASS, OWNS_REL, lo, hi])

        nt = db.one("SELECT count(*) FROM nodes WHERE class = ?", [TEAM_CLASS])
        no = db.one("SELECT count(*) FROM edges WHERE rel = ?", [OWNS_REL])
        orphan = db.one(
            "SELECT count(*) FROM nodes n WHERE n.class = "
            "class_code('Microservice') AND NOT EXISTS (SELECT 1 FROM edges e "
            "WHERE e.dst = n.id AND e.rel = rel_code('owns'))")
        print(f"\nwrote {nt:,} Team nodes, {no:,} owns edges  "
              f"(provenance=derived)")
        print(f"microservices with no owning team: {orphan}")

        print("\nlargest teams:")
        for key, size in db.query(
                "SELECT nkey, CAST(json_extract(props,'$.size') AS BIGINT) s "
                "FROM nodes WHERE class = ? ORDER BY s DESC LIMIT 5",
                [TEAM_CLASS]):
            print(f"  {key}  {size:,} services")
    return 0


if __name__ == "__main__":
    sys.exit(main())
