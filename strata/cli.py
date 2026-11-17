"""The `strata` command: any one layer from a terminal, a script or CI.

    strata connect data/shop/ --name shop
    strata build "Shop" --source shop                       # from the data (AI if configured)
    strata build "Mine" --source shop --model my.json       # your ontology, exactly
    strata build "Keys" --source shop --keys-only           # no AI at all
    strata list
    strata export ontology shop -o shop.strata-model.json   # Strata Model v1
    strata export graph shop --format rdf -o shop.nt        # rdf | json | neo4j
    strata export semantic shop --format metricflow -o metrics.yml   # sql | metricflow
    strata metrics shop                                     # governed metrics and values
    strata certify shop total_payment_value --owner Finance
    strata context shop "revenue by payment type"           # Context Pack (JSON)
    strata health shop                                      # is each layer ready?
    strata serve --layers semantic,context --port 8000      # API + MCP (+ web app)
    strata bundle -o strata-semantic.zip --layers semantic --ontology shop
                                                            # zip for another team: unzip, start.bat

Every command takes --db (default: ./strata.duckdb, or STRATA_DB).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _out(data, path: str | None) -> None:
    text = data if isinstance(data, str) else json.dumps(data, indent=2, default=str, ensure_ascii=False)
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text, encoding="utf-8")
        print(f"wrote {path}", file=sys.stderr)
    else:
        print(text)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="strata", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=os.environ.get("STRATA_DB", "strata.duckdb"),
                   help="the registry file (default ./strata.duckdb)")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("connect", help="connect files, a database file or a URL")
    c.add_argument("origin")
    c.add_argument("--name")

    b = sub.add_parser("build", help="build an ontology")
    b.add_argument("name")
    b.add_argument("--source", action="append", default=[], help="a connected source id (repeat)")
    b.add_argument("--path", action="append", default=[], help="connect and use this path (repeat)")
    b.add_argument("--model", help="use your ontology file exactly (Strata Model, Ossie, dbt, dictionary)")
    b.add_argument("--metadata", action="append", default=[], help="metadata hints (repeat)")
    b.add_argument("--keys-only", action="store_true", help="names from columns and keys; no AI")
    b.add_argument("--no-ai", action="store_true", help="do not call the AI")
    b.add_argument("--domain", default="")

    sub.add_parser("list", help="ontologies and sources in this registry")

    e = sub.add_parser("export", help="a layer in an open format")
    e.add_argument("layer", choices=["ontology", "graph", "semantic"])
    e.add_argument("ontology")
    e.add_argument("--format", "-f", help="graph: rdf|json|neo4j; semantic: sql|metricflow")
    e.add_argument("--all", action="store_true", help="semantic: proposed metrics too")
    e.add_argument("-o", "--out")

    m = sub.add_parser("metrics", help="governed metrics with their values")
    m.add_argument("ontology")

    ce = sub.add_parser("certify", help="certify a metric")
    ce.add_argument("ontology")
    ce.add_argument("metric")
    ce.add_argument("--owner", default="")

    x = sub.add_parser("context", help="the Context Pack for a question")
    x.add_argument("ontology")
    x.add_argument("question")
    x.add_argument("--answer", action="store_true", help="also let the configured AI answer")
    x.add_argument("--budget", type=int, default=2000)
    x.add_argument("-o", "--out")

    h = sub.add_parser("health", help="is each layer ready for an ontology?")
    h.add_argument("ontology", nargs="?")

    bu = sub.add_parser("bundle", help="a ready-to-copy zip for another team (Python only)")
    bu.add_argument("-o", "--out", required=True, help="the zip to write, e.g. strata-semantic.zip")
    bu.add_argument("--layers", default="", help="layers to switch on (default all)")
    bu.add_argument("--ontology", help="include this ontology as a Strata Model to start from")
    bu.add_argument("--no-ui", action="store_true", help="API and MCP only")

    s = sub.add_parser("serve", help="run the API, MCP and web app")
    s.add_argument("--layers", default=os.environ.get("STRATA_LAYERS", ""))
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--no-ui", action="store_true")
    return p


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "serve":
        os.environ["MIDDLE_LAYER_GRAPH"] = str(Path(args.db).resolve())
        import run_server
        extra = ["--host", args.host, "--port", str(args.port)]
        if args.layers:
            extra += ["--layers", args.layers]
        if args.no_ui:
            extra.append("--no-ui")
        return run_server.main(extra)

    if args.cmd == "bundle" and not args.ontology:
        from strata.bundle import make_bundle
        print(f"wrote {make_bundle(args.out, args.layers, include_ui=not args.no_ui)}")
        return 0

    import strata
    from ontology.metadata import MetadataError
    try:
        with strata.open(args.db) as s:
            return _run(s, args)
    except (KeyError, ValueError, MetadataError, FileNotFoundError) as exc:
        print(f"strata: {str(exc).strip(chr(39))}", file=sys.stderr)
        return 2


def _run(s, args) -> int:
    if args.cmd == "connect":
        print(s.connect(args.origin, args.name))
    elif args.cmd == "build":
        sources = list(args.source) + [s.connect(p) for p in args.path]
        oid = s.build(args.name, sources, model=args.model, metadata=args.metadata,
                      keys_only=args.keys_only, use_ai=not args.no_ai, domain=args.domain)
        v = s.ontology(oid)
        print(f"{oid}: {v['summary']['things']} things, {v['summary']['fields']} fields, "
              f"{v['summary']['links']} links, {v['summary']['confirmed_pct']}% confirmed by the data")
    elif args.cmd == "list":
        _out({"ontologies": s.ontologies(),
              "sources": [{"id": x["source_id"], "origin": x["origin"]} for x in s.sources()]}, None)
    elif args.cmd == "export":
        if args.layer == "ontology":
            _out(s.contract(args.ontology), args.out)
        elif args.layer == "graph":
            fmt = args.format or "rdf"
            dest = args.out or f"{args.ontology}.{ {'rdf': 'nt', 'json': 'json', 'neo4j': 'zip'}.get(fmt, fmt)}"
            print(f"wrote {s.export_graph(args.ontology, fmt, dest)}", file=sys.stderr)
        else:
            _out(s.export_metrics(args.ontology, args.format or "sql",
                                  status="all" if args.all else "certified"), args.out)
    elif args.cmd == "metrics":
        for mt in s.metrics(args.ontology):
            value = mt["value"]
            shown = f"{value:,.2f}" if isinstance(value, (int, float)) else str(value)
            print(f"{mt['status']:9s}  {mt['name']:40s} {shown:>18s}  {mt['title']}")
    elif args.cmd == "certify":
        c = s.certify(args.ontology, args.metric, owner=args.owner)
        print(f"certified {c['title']} = {c['value']}")
    elif args.cmd == "context":
        _out(s.context(args.ontology, args.question, answer=args.answer, budget_chars=args.budget),
             args.out)
    elif args.cmd == "bundle":
        from strata.bundle import make_bundle
        print(f"wrote {make_bundle(args.out, args.layers, ontology=s.contract(args.ontology), include_ui=not args.no_ui)}")
    elif args.cmd == "health":
        from api.layer_health import report
        if args.ontology:
            s._ready(args.ontology)
        for row in report(s.layer, args.ontology)["layers"]:
            print(f"{row['layer']:9s} {row['status']:16s} {row['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
