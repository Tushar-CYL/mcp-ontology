"""Review gate CLI — what a person runs after a build.

    python -m review.cli --graph data/graphs/shop.duckdb list
    python -m review.cli --graph data/graphs/shop.duckdb list --kind relation
    python -m review.cli --graph data/graphs/shop.duckdb seed-relations --source shop
    python -m review.cli --graph data/graphs/shop.duckdb approve <item-id> --reviewer arun
    python -m review.cli --graph data/graphs/shop.duckdb reject <item-id> --rationale "not a KPI"
    python -m review.cli --graph data/graphs/shop.duckdb publish semantic --source shop
    python -m review.cli --graph data/graphs/shop.duckdb audit <item-id>

The same gate is used by the UI and the API; this is the headless path for a
locked-down machine or a scheduled job.
"""

from __future__ import annotations

import argparse
import json

from knowledge_graph.store import open_graph
from review import store as review


def _list(graph, args) -> int:
    items = review.pending(graph, kind=args.kind, source=args.source)
    if not items:
        print("no pending review items")
        return 0
    print(f"{len(items)} pending item(s)")
    for item in items:
        confidence = ("-" if item["confidence"] is None
                      else f"{item['confidence']:.2f}")
        print(f"  {item['item_id']}  {item['kind']:<9} "
              f"{item['source']:<10} {item['subject']:<28} {confidence}")
    return 0


def _decide(graph, args, decision: str) -> int:
    item = review.decide(graph, args.item, decision,
                         reviewer=args.reviewer, rationale=args.rationale)
    print(f"{item['item_id']}: {item['status']}")
    return 0


def _publish(graph, args) -> int:
    try:
        state = review.publish(graph, args.artifact, source=args.source,
                               reviewer=args.reviewer)
    except KeyError as exc:
        print(f"cannot publish: {exc}")
        return 1
    print(json.dumps(state, indent=2))
    return 0


def _seed(graph, args) -> int:
    ids = review.seed_from_relations(graph, args.source)
    print(f"{len(ids)} relation proposal(s) queued for {args.source}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Human review gate for the "
                                                 "middle layer.")
    parser.add_argument("--graph", required=True, help="graph database file")
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list", help="show pending proposals")
    listing.add_argument("--kind", choices=review.KINDS)
    listing.add_argument("--source")
    listing.set_defaults(func=_list)

    approve = sub.add_parser("approve", help="approve one proposal")
    approve.add_argument("item")
    approve.add_argument("--reviewer", default="human")
    approve.add_argument("--rationale", default="")
    approve.set_defaults(func=lambda g, a: _decide(g, a, "approved"))

    reject = sub.add_parser("reject", help="reject one proposal")
    reject.add_argument("item")
    reject.add_argument("--reviewer", default="human")
    reject.add_argument("--rationale", default="")
    reject.set_defaults(func=lambda g, a: _decide(g, a, "rejected"))

    audit = sub.add_parser("audit", help="show the decision history")
    audit.add_argument("item")
    audit.set_defaults(
        func=lambda g, a: [print(json.dumps(row, indent=2))
                           for row in review.audit(g, a.item)] and 0)

    publish = sub.add_parser("publish", help="publish an artifact once clear")
    publish.add_argument("artifact", choices=review.KINDS)
    publish.add_argument("--source", default="")
    publish.add_argument("--reviewer", default="human")
    publish.set_defaults(func=_publish)

    seed = sub.add_parser("seed-relations",
                          help="queue inferred relations for review")
    seed.add_argument("--source", required=True)
    seed.set_defaults(func=_seed)

    args = parser.parse_args(argv)
    graph = open_graph(args.graph)
    try:
        return args.func(graph, args)
    finally:
        graph.close()


if __name__ == "__main__":
    raise SystemExit(main())

