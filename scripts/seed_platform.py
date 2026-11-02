"""Seed the platform graph for the production demo.

    python scripts/seed_platform.py --data data/raw/revenue_huge \
        --graph data/graphs/platform.duckdb

Connects/builds the revenue source, defines the approved Revenue metric, and
creates (or updates) a published "Revenue Analyst" agent. Safe to re-run: the
build is skipped when the source signature is current, metric definitions are
upserted, and the agent is matched by name.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.service import MiddleLayer                      # noqa: E402
from semantic import definitions as metric_defs          # noqa: E402

DEFAULT_AGENT = {
    "name": "Revenue Analyst",
    "purpose": "Explain revenue changes and show the evidence behind the "
               "number.",
    "problem_statement": "Why did West revenue fall this month, which "
                         "segments drove it, and can I trust the number?",
    "instructions": (
        "You are a finance analyst for the West region. Explain revenue "
        "changes using only approved metrics and cited evidence. Always say "
        "whether the number can be trusted and what to inspect next."),
    "metrics": ["revenue"],
    "skills": ["explain_metric", "compare_periods", "breakdown_by",
               "graph_context", "evidence_search"],
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/raw/revenue_huge")
    parser.add_argument("--graph", default="data/graphs/platform.duckdb")
    parser.add_argument("--source", default="revenue")
    parser.add_argument("--no-agent", action="store_true")
    args = parser.parse_args(argv)

    layer = MiddleLayer(args.graph)
    summary = layer.add_source(args.data, source=args.source)
    print(json.dumps({"source": summary}, indent=2, default=str))

    bundle = layer._bundle(args.source)
    definition = metric_defs.get_definition(
        layer.graph, "revenue", args.source)
    if definition is None:
        definition = metric_defs.seed_revenue_metric(
            layer.graph, bundle.schema, bundle.onto, args.source)
    print(json.dumps({"metric": definition["name"],
                      "status": definition["status"],
                      "unit": definition["unit"]}, indent=2))

    if not args.no_agent:
        from agent.runtime import AgentRuntime
        runtime = AgentRuntime(
            layer.graph,
            [(b.source, b.schema, b.onto) for b in layer.bundles])
        existing = next((agent for agent in runtime.list_agents()
                         if agent["name"] == DEFAULT_AGENT["name"]), None)
        payload = dict(DEFAULT_AGENT)
        payload["source_id"] = args.source
        if existing:
            agent = runtime.update_agent(existing["id"], payload)
        else:
            agent = runtime.create_agent(payload)
        if agent["status"] != "published":
            agent = runtime.publish_agent(agent["id"])
        print(json.dumps({"agent": {"id": agent["id"],
                                    "name": agent["name"],
                                    "status": agent["status"]}},
                         indent=2))
    layer.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
