"""Strata as a Python library: any one layer, in your own code, on your data.

    import strata

    s = strata.open("work.duckdb")                 # a local registry file
    shop = s.connect("data/shop/")                 # files, a .db, or a URL
    oid = s.build("Shop", [shop])                  # Ontology (AI names, data checks)
    oid = s.build("Mine", [shop], model="my-ontology.json")   # or yours, exactly
    s.ontology(oid)                                # the ontology in plain words
    s.contract(oid)                                # ... as Strata Model v1 JSON
    s.search(oid, "sao paulo")                     # Knowledge graph
    s.metrics(oid)                                 # Semantic: governed metrics
    s.certify(oid, "total_gross_amount", owner="Finance")
    s.export_metrics(oid, "metricflow")            # ... for dbt / your warehouse
    s.context(oid, "revenue by payment type")      # Context Pack for any AI

Each method is a thin call into the same code the web app and the MCP server
use, so the numbers are the same everywhere.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["Strata", "open"]
__version__ = "1.0.0"


class Strata:
    """One registry (a DuckDB file) and everything built in it."""

    def __init__(self, path: str | Path = "strata.duckdb"):
        from api.service import MiddleLayer
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.layer = MiddleLayer(self.path)

    # ------------------------------------------------------------ helpers
    @property
    def graph(self):
        return self.layer.graph

    def _ai(self, use_ai: bool):
        if not use_ai:
            return None
        from agent.llm import EYQClient
        return EYQClient()

    def _ready(self, ontology_id: str) -> str:
        """Re-open the sources an ontology reads (a new process knows only
        their address, not their tables)."""
        from ontology import registry as reg
        onto = reg.get(self.graph, ontology_id)
        loaded = {b.source for b in self.layer.bundles}
        origins = {s["source_id"]: s.get("origin") for s in self.graph.sources()}
        for s in onto["sources"]:
            sid = s["source_id"]
            if sid not in loaded and origins.get(sid):
                self.layer.add_source(origins[sid], source=sid)
        return ontology_id

    def _proposed(self, ontology_id: str) -> str:
        """Metrics exist once proposed (the Semantic page does it on open)."""
        from semantic import definitions as defs
        from semantic import model as sem
        self._ready(ontology_id)
        if not defs.list_definitions(self.graph, sem.source_of(ontology_id)):
            sem.propose(self.layer, ontology_id)
        return ontology_id

    def close(self) -> None:
        self.layer.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------ sources
    def connect(self, origin: str, name: str | None = None) -> str:
        """Connect files, a database file or a URL; returns its source id."""
        return self.layer.add_source(str(origin), source=name)["source"]

    def sources(self) -> list[dict]:
        return self.graph.sources()

    # ----------------------------------------------------------- ontology
    def build(self, name: str, sources: list[str], model: str | None = None,
              metadata: list[str] | None = None, keys_only: bool = False,
              use_ai: bool = True, domain: str = "") -> str:
        """Build an ontology. `model=` uses your ontology file exactly (Strata
        Model JSON, Ossie, dbt, dictionary); `keys_only=True` never uses AI."""
        from ontology import simple
        files = list(metadata or []) + ([str(model)] if model else [])
        mode = "model" if model else "keys" if keys_only else "data"
        return simple.create_and_build(self.layer, name, list(sources), metadata=files or None,
                                       domain=domain, client=self._ai(use_ai and mode == "data"),
                                       mode=mode)["ontology"]

    def ontologies(self) -> list[str]:
        from ontology import registry as reg
        return [o["id"] for o in reg.list_ontologies(self.graph)]

    def ontology(self, ontology_id: str) -> dict:
        from ontology import simple
        return simple.view(self.graph, ontology_id)

    def contract(self, ontology_id: str, version: int | None = None) -> dict:
        from ontology import contract
        return contract.to_contract(self.graph, ontology_id, version)

    def add_note(self, ontology_id: str, text: str, use_ai: bool = False) -> dict:
        from ontology import simple
        return simple.add_context(self.layer, ontology_id, text, client=self._ai(use_ai))

    def ask(self, ontology_id: str, question: str) -> dict:
        from ontology import ask
        self._ready(ontology_id)
        return ask.ask(self.layer, ontology_id, question, client=self._ai(True))

    # ---------------------------------------------------- knowledge graph
    def search(self, ontology_id: str, text: str, thing: str | None = None) -> list[dict]:
        from knowledge_graph import explore as kg
        self._ready(ontology_id)
        return kg.search(self.layer, ontology_id, text, thing=thing)["results"]

    def record(self, ontology_id: str, set_name: str, key: str) -> dict:
        from knowledge_graph import explore as kg
        self._ready(ontology_id)
        return kg.entity(self.layer, ontology_id, set_name, key)

    def export_graph(self, ontology_id: str, fmt: str, dest: str | Path) -> Path:
        """fmt: rdf (N-Triples), json, or neo4j (zip of CSVs)."""
        import json
        from knowledge_graph import explore as kg
        self._ready(ontology_id)
        dest = Path(dest)
        if fmt == "rdf":
            return kg.export_rdf(self.layer, ontology_id, dest)
        if fmt == "json":
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(kg.export_json_graph(self.layer, ontology_id), default=str),
                            encoding="utf-8")
            return dest
        if fmt == "neo4j":
            return kg.export_neo4j(self.layer, ontology_id, dest.with_suffix(""))
        raise ValueError("graph formats: rdf, json, neo4j")

    # ----------------------------------------------------------- semantic
    def metrics(self, ontology_id: str) -> list[dict]:
        from semantic import model as sem
        self._ready(ontology_id)
        return sem.overview(self.layer, ontology_id)["metrics"]

    def metric(self, ontology_id: str, name: str, by: str | None = None) -> dict:
        from semantic import model as sem
        self._proposed(ontology_id)
        return sem.value(self.layer, ontology_id, name, by=by)

    def certify(self, ontology_id: str, name: str, owner: str = "", by: str = "you") -> dict:
        from semantic import model as sem
        self._proposed(ontology_id)
        return sem.certify(self.layer, ontology_id, name, by=by, owner=owner)

    def export_metrics(self, ontology_id: str, fmt: str = "sql", status: str = "certified") -> str:
        """fmt: sql (CREATE VIEW per metric) or metricflow (dbt YAML)."""
        from semantic import export
        self._ready(ontology_id)
        if fmt == "sql":
            return export.sql_views(self.layer, ontology_id, status=status)
        if fmt == "metricflow":
            return export.metricflow(self.layer, ontology_id, status=status)
        raise ValueError("metric formats: sql, metricflow")

    # ------------------------------------------------------------ context
    def context(self, ontology_id: str, question: str, answer: bool = False,
                budget_chars: int = 2000) -> dict:
        """The Context Pack for a question (open format). With answer=True the
        configured AI also writes the answer from it."""
        from context import engine as ctx
        self._ready(ontology_id)
        out = ctx.build(self.layer, ontology_id, question, budget_chars=budget_chars,
                        client=self._ai(answer))
        pack = ctx.to_pack(out)
        if answer:
            pack["answer"] = out["steps"]["answer"]
        return pack


def open(path: str | Path = "strata.duckdb") -> Strata:  # noqa: A001 - like io.open
    return Strata(path)
