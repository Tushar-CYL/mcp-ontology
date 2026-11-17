"""REST API for the Knowledge graph tool (``/api/kg/{ontology}/...``).

The graph is the ontology's data: every record an entity, every proven link
a connection, read live (see knowledge_graph/explore.py).

  GET  /api/kg/{id}/overview   counts and graph health in plain words
  GET  /api/kg/{id}/search     find an entity by id or name   (?q=&thing=)
  GET  /api/kg/{id}/entity     one entity's 360                (?set=&key=)
  GET  /api/kg/{id}/path       how two entities are connected  (?from_set=&from_key=&to_set=&to_key=)
  GET  /api/kg/{id}/neo4j      Neo4j import files (zip)
  GET  /api/kg/{id}/rdf        RDF N-Triples, for any triple store
  GET  /api/kg/{id}/graph.json plain JSON nodes and edges
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import Query, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from knowledge_graph import explore as kg


def register(app, platform, error) -> None:

    def guard(fn):
        try:
            return fn()
        except kg.GraphError as exc:
            raise error(400, "GraphError", str(exc)) from exc
        except KeyError as exc:
            raise error(404, "NotFound", str(exc).strip("'\"")) from exc

    @app.get("/api/kg/{oid}/overview")
    def kg_overview(oid: str, request: Request):
        return guard(lambda: kg.overview(platform(request).layer, oid))

    @app.get("/api/kg/{oid}/search")
    def kg_search(oid: str, request: Request, q: str = Query("", max_length=200),
                  thing: str | None = None, limit: int = Query(kg.SEARCH_LIMIT, ge=1, le=100)):
        return guard(lambda: kg.search(platform(request).layer, oid, q, thing=thing, limit=limit))

    @app.get("/api/kg/{oid}/entity")
    def kg_entity(oid: str, request: Request, set: str = Query(..., max_length=300),  # noqa: A002
                  key: str = Query(..., max_length=500),
                  sample: int = Query(kg.SAMPLE, ge=1, le=50)):
        return guard(lambda: kg.entity(platform(request).layer, oid, set, key, sample=sample))

    @app.get("/api/kg/{oid}/path")
    def kg_path(oid: str, request: Request,
                from_set: str = Query(..., max_length=300), from_key: str = Query(..., max_length=500),
                to_set: str = Query(..., max_length=300), to_key: str = Query(..., max_length=500),
                max_hops: int = Query(kg.PATH_MAX_HOPS, ge=1, le=6)):
        return guard(lambda: kg.path(platform(request).layer, oid, (from_set, from_key),
                                     (to_set, to_key), max_hops=max_hops))

    @app.get("/api/kg/{oid}/sample")
    def kg_sample(oid: str, request: Request):
        return guard(lambda: kg.sample(platform(request).layer, oid))

    @app.get("/api/kg/{oid}/expand")
    def kg_expand(oid: str, request: Request, set: str = Query(..., max_length=300),  # noqa: A002
                  key: str = Query(..., max_length=500),
                  limit: int = Query(kg.EXPAND_LIMIT, ge=1, le=50)):
        return guard(lambda: kg.expand(platform(request).layer, oid, set, key, limit=limit))

    @app.get("/api/kg/{oid}/rdf")
    def kg_rdf(oid: str, request: Request):
        """The graph as RDF N-Triples, for any triple store."""
        work = Path(tempfile.mkdtemp(prefix="strata_rdf_"))
        try:
            out = guard(lambda: kg.export_rdf(platform(request).layer, oid, work / f"{oid}.nt"))
        except Exception:
            shutil.rmtree(work, ignore_errors=True)
            raise
        return FileResponse(out, media_type="application/n-triples", filename=f"{oid}-knowledge-graph.nt",
                            background=BackgroundTask(shutil.rmtree, work, ignore_errors=True))

    @app.get("/api/kg/{oid}/graph.json")
    def kg_json(oid: str, request: Request, limit: int = Query(100_000, ge=1, le=1_000_000)):
        """The graph as plain JSON {nodes, edges} (Cytoscape, D3, NetworkX)."""
        return guard(lambda: kg.export_json_graph(platform(request).layer, oid, limit=limit))

    @app.get("/api/kg/{oid}/neo4j")
    def kg_neo4j(oid: str, request: Request):
        work = Path(tempfile.mkdtemp(prefix="strata_neo4j_"))
        try:
            out = guard(lambda: kg.export_neo4j(platform(request).layer, oid, work / "graph"))
        except Exception:
            shutil.rmtree(work, ignore_errors=True)
            raise
        return FileResponse(out, media_type="application/zip",
                            filename=f"{oid}-knowledge-graph-neo4j.zip",
                            background=BackgroundTask(shutil.rmtree, work, ignore_errors=True))
