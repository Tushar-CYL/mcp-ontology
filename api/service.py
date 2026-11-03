"""The API surface: one service used by HTTP, MCP and the UI.

Everything above `Graph` is opinionated about honesty, so the service is where
that shows up as a contract:

* every answer is an envelope with provenance on each fact;
* context answers say what was dropped;
* a source must be named when the graph has several (the graph already refuses
  to guess; the service surfaces that as an actionable error);
* metrics compile from the same definition everywhere.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from context.assemble import build_context
from knowledge_graph.build import build, is_current, rejected_links, table_ref
from knowledge_graph.resolve import candidates as identity_candidates
from knowledge_graph.resolve import explain as explain_entity
from knowledge_graph.resolve import resolve as resolve_links
from knowledge_graph.store import open_graph
from ontology.connect import connect
from ontology.copies import hide_copies
from ontology.discover import discover
from semantic.compile import compile_metric
from semantic.discover import discover_metrics


@dataclass
class SourceBundle:
    source: str
    schema: object
    onto: object


# Certification scans every node and edge (about two minutes on a 12M-edge
# graph). Its result only changes when a source is rebuilt, so it is cached
# per source and dropped whenever that source is (re)loaded.
READINESS_MAX_AGE = 15 * 60


class MiddleLayer:
    """A graph plus the sources it was built from. One object, no globals."""

    def __init__(self, graph_path: str | None = None):
        self.graph = open_graph(graph_path)
        self.bundles: list[SourceBundle] = []
        self._readiness: dict[str, tuple[float, dict]] = {}
        self._readiness_lock = threading.Lock()
        self._clock = time.monotonic

    # ---------------------------------------------------------- sources
    def add_source(self, origin: str, source: str | None = None,
                   rebuild: bool = False, progress=None) -> dict:
        """Connect a source and build it if the graph is not current.

        Copies (ML splits, exact duplicates) are kept out of the graph, and
        guessed links the build found not to match the data are removed from
        the ontology, now and on every later start.
        """
        say = progress or (lambda _line: None)
        say("reading the source")
        schema = connect(origin)
        hidden = hide_copies(schema)
        if hidden:
            say(f"kept {len(hidden)} copies out of the graph")
        onto = discover(schema)
        name = source or schema.name
        say(f"found {len(onto.classes)} kinds of thing and "
            f"{len(onto.relations)} candidate links")
        if rebuild or not is_current(self.graph, schema, onto, source=name):
            build(self.graph, schema, onto, source=name, progress=say)
        else:
            say("graph already up to date")
        rejected = rejected_links(self.graph, name)
        for rel_name in rejected:
            onto.relations.pop(rel_name, None)
        self._remember(SourceBundle(name, schema, onto))
        return {
            "source": name, "origin": schema.origin,
            "tables": len(schema.tables),
            "classes": len(onto.classes),
            "relations": len(onto.relations),
            "warnings": list(schema.warnings),
            "rejected_links": rejected,
            "hidden_copies": hidden,
            "nodes": self.graph.one(
                "SELECT count(*) FROM nodes WHERE source_id = ?", [name]) or 0,
            "edges": self.graph.one(
                "SELECT count(*) FROM edges WHERE source_id = ?", [name]) or 0,
        }

    def _remember(self, bundle: SourceBundle) -> None:
        self.bundles = [b for b in self.bundles if b.source != bundle.source]
        self.bundles.append(bundle)
        self._readiness.pop(bundle.source, None)

    # -------------------------------------------------------- readiness
    def readiness(self, source: str, refresh: bool = False,
                  max_age: float = READINESS_MAX_AGE) -> dict:
        """The certification report for a source, cached per source.

        `cached` and `checked_at` say how old the answer is, so a caller
        never mistakes a cached result for a fresh one.
        """
        from agent import certification
        with self._readiness_lock:
            hit = self._readiness.get(source)
            if hit and not refresh and self._clock() - hit[0] <= max_age:
                return {**hit[1], "cached": True}
            report = certification.certify_source(self, source)
            report = {**report, "checked_at": datetime.now(timezone.utc)
                      .isoformat(timespec="seconds")}
            self._readiness[source] = (self._clock(), report)
            return {**report, "cached": False}

    def _bundle(self, source: str | None) -> SourceBundle:
        if source is None:
            source = self.graph.resolve_source(None)
        for bundle in self.bundles:
            if bundle.source == source:
                return bundle
        # The graph may have been opened without its sources (a warm process).
        raise KeyError(
            f"source {source!r} is not loaded in this service; call "
            f"add_source({source!r}, origin) first")

    def sources(self) -> list[dict]:
        return self.graph.sources()

    # --------------------------------------------------------- ontology
    def ontology(self, source: str | None = None) -> dict:
        if source is None and len(self.graph.source_ids()) > 1:
            return {"sources": [self.ontology(s) for s in
                                self.graph.source_ids()]}
        bundle = self._bundle(source)
        return {
            "source": bundle.source,
            "classes": [
                {"name": c.name, "table": c.table, "key": c.key,
                 "key_is_synthetic": c.key_is_synthetic,
                 "time_column": c.time_column,
                 "measures": list(c.measures),
                 "dimensions": list(c.dimensions),
                 "count": self.graph.count_class(c.name, bundle.source)}
                for c in bundle.onto.classes.values()
            ],
            "relations": [
                {"name": r.name, "domain": r.domain, "range": r.range,
                 "provenance": r.provenance, "confidence": r.confidence,
                 "count": self.graph.count_relation(r.name, bundle.source)}
                for r in bundle.onto.relations.values()
            ],
        }

    def describe(self, cls: str, source: str | None = None) -> dict:
        bundle = self._bundle(source)
        found = bundle.onto.classes.get(cls)
        if found is None:
            raise KeyError(f"no class {cls!r} in source {bundle.source!r}")
        keys = sorted(self.graph.keys_of(cls, limit=5, source=bundle.source))
        return {
            "source": bundle.source, "class": found.name,
            "table": found.table, "key": found.key,
            "key_is_synthetic": found.key_is_synthetic,
            "time_column": found.time_column,
            "measures": list(found.measures),
            "dimensions": list(found.dimensions),
            "count": self.graph.count_class(cls, bundle.source),
            "sample_keys": keys,
        }

    # ------------------------------------------------------------ graph
    def neighbours(self, cls: str, key: str, relation: str | None = None,
                   source: str | None = None, depth: int = 1,
                   as_of: str | None = None) -> dict:
        bundle = self._bundle(source)
        out = []
        if depth <= 1:
            for rel in bundle.onto.relations.values():
                if rel.domain != cls:
                    continue
                if relation and rel.name != relation:
                    continue
                for other, when in self.graph.neighbours(
                        cls, key, rel.name, source=bundle.source).items():
                    out.append({"relation": rel.name,
                                "target_class": rel.range,
                                "target_key": other,
                                "provenance": rel.provenance,
                                "valid_from": str(when) if when else None})
        else:
            for item in sorted(self.graph.reach(
                    cls, key, relation, depth=depth, as_of=as_of,
                    source=bundle.source)):
                target_class, target_key = item.split(":", 1)
                out.append({"relation": relation,
                            "target_class": target_class,
                            "target_key": target_key,
                            "provenance": "derived"})
        return {"source": bundle.source, "class": cls, "key": key,
                "neighbours": out}

    # ---------------------------------------------------------- metrics
    def metric(self, name: str, source: str | None = None,
               group_by: str | None = None, limit: int = 100) -> dict:
        bundle = self._bundle(source)
        metrics = discover_metrics(bundle.onto)
        metric = next((m for m in metrics if m.name == name), None)
        if metric is None:
            raise KeyError(f"no metric {name!r} in source {bundle.source!r}")
        sql, params = compile_metric(
            metric, group_by=group_by,
            table_sql=table_ref(self.graph, bundle.schema, metric.table,
                                source=bundle.source))
        rows = self.graph.sql(sql, params)
        return {"source": bundle.source, "metric": metric.name,
                "title": metric.title, "definition": {
                    "table": metric.table, "column": metric.column,
                    "agg": metric.agg, "time_column": metric.time_column,
                    "dimensions": list(metric.dimensions)},
                "sql": sql, "params": params,
                "rows": [list(r) for r in rows], "limit": limit}

    # ---------------------------------------------------------- context
    def context(self, task: str = "",
                entity: tuple[str, str, str] | dict | None = None,
                budget_chars: int = 1200,
                as_of: str | None = None) -> dict:
        bundles = [(b.source, b.schema, b.onto) for b in self.bundles]
        if not bundles:
            raise KeyError("no sources loaded; call add_source() first")
        if isinstance(entity, dict):
            entity = (entity.get("source"), entity.get("class"),
                      entity.get("key"))
        return build_context(self.graph, bundles, task=task, entity=entity,
                             budget_chars=budget_chars, as_of=as_of)

    # -------------------------------------------------------- resolution
    def resolve(self) -> list[dict]:
        found = resolve_links(self.graph)
        return [c.__dict__ for c in found]

    def identity_candidates(self) -> list[dict]:
        return identity_candidates(self.graph)

    def explain_entity(self, source: str, cls: str, key: str) -> dict:
        return explain_entity(self.graph, source, cls, key)

    # -------------------------------------------------------- provenance
    def provenance(self, citation: str) -> dict:
        """Explain a citation id without pretending to know more than we do."""
        if not citation:
            raise KeyError("a citation is required")
        kind = citation.split(":", 1)[0]
        return {
            "citation": citation,
            "kind": kind,
            "note": {
                "edge": "a link in the graph; its provenance is on the edge",
                "entity_links": "a proposed cross-source identity; check status",
                "findings": "a data-quality finding recorded at build time",
                "review": "a human review queue reference",
            }.get(kind, "a source row, column or graph node"),
            "review_pending": {
                "semantic": len(self._pending("semantic")),
                "context": len(self._pending("context")),
            },
        }

    def _pending(self, kind: str) -> list:
        from review import store as review
        bundle = None
        sources = self.graph.source_ids()
        if len(sources) == 1:
            bundle = sources[0]
        return review.pending(self.graph, kind=kind, source=bundle)

    def close(self) -> None:
        self.graph.close()
