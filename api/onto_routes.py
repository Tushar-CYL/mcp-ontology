"""REST API for the simple ontology flow (``/api/onto/...``).

Three screens, three groups of routes:

1. Connect   POST /api/onto/build        data (+ metadata) -> ontology (a job)
2. Ontology  GET  /api/onto/{id}          things, fields, links in plain words
             POST /api/onto/{id}/context  a person's note, applied
             PUT  /api/onto/{id}/fields   / things: direct corrections
3. Use it    GET  /api/onto/{id}/nexus    flat tables for Nexus / Excel (JSON)
             GET  /api/onto/{id}/excel    the same as an .xlsx workbook
             GET  /api/onto/{id}/use      every way to consume it, with links

Everything published is also served to agents over MCP (``get_ontology``).
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from ontology import meaning as mn
from ontology import metadata as md
from ontology import registry as reg
from ontology import simple


def ai_client():
    """The configured model; offline (mock) when no endpoint/key is set.
    Tests replace this function."""
    from agent.llm import EYQClient
    return EYQClient()


class PathSource(BaseModel):
    path: str
    name: str | None = None


class BuildRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    sources: list[str] = Field(default_factory=list)
    paths: list[PathSource] = Field(default_factory=list)
    metadata: list[str] = Field(default_factory=list)
    domain: str = ""
    problem: str = ""


class ContextRequest(BaseModel):
    text: str = Field(..., max_length=4000)
    by: str = "you"


class FieldEdit(BaseModel):
    key: str
    label: str | None = None
    meaning: str | None = None
    role: str | None = None
    unit: str | None = None
    by: str = "you"


class ThingEdit(BaseModel):
    key: str
    name: str | None = None
    description: str | None = None
    by: str = "you"


class MetadataRequest(BaseModel):
    path: str


def register(app, platform, error) -> None:

    def guard(fn):
        try:
            return fn()
        except PermissionError as exc:
            raise error(403, "Forbidden", str(exc)) from exc
        except KeyError as exc:
            raise error(404, "NotFound", str(exc).strip("'\"")) from exc
        except md.MetadataError as exc:
            raise error(400, "MetadataError", str(exc)) from exc
        except ValueError as exc:
            raise error(400, "BadRequest", str(exc)) from exc

    def ai_status() -> dict:
        client = ai_client()
        return {"configured": not client.mock and mn.ai_enabled(), "model": client.model,
                "samples_per_column": mn.sample_count()}

    def summary(graph, oid: str) -> dict:
        v = simple.view(graph, oid)
        return {k: v[k] for k in ("id", "name", "domain", "sources", "metadata", "version",
                                  "published_at", "summary", "created_at")}

    def full_view(graph, oid: str) -> dict:
        """What the screen needs after any change: the view plus AI status and
        the role list (every response that returns the ontology uses this)."""
        return {**simple.view(graph, oid), "ai": ai_status(), "roles": mn.ROLES}

    @app.get("/api/onto")
    def onto_list(request: Request):
        g = platform(request).layer.graph
        return {"ontologies": [summary(g, o["id"]) for o in reg.list_ontologies(g)],
                "ai": ai_status(), "roles": mn.ROLES}

    @app.post("/api/onto/build")
    def onto_build(request: Request, body: BuildRequest):
        state = platform(request)
        if not body.sources and not body.paths and not body.metadata:
            raise error(400, "BadRequest", "connect at least one data source or give a "
                        "semantic model / data dictionary")
        loaded = set(state.layer.graph.source_ids())
        missing = [x for x in body.sources if x not in loaded]
        if missing:
            raise error(400, "BadRequest", "these sources are not loaded: "
                        + ", ".join(missing))
        from api import paths
        for item in body.paths:                    # STRATA_DATA_ROOTS, when set
            guard(lambda: paths.check(item.path))
        for path in body.metadata:                 # fail fast, before any job
            guard(lambda: paths.check(path))
            guard(lambda: md.parse(path))

        def work(say):
            sources = list(body.sources)
            for item in body.paths:
                say(f"Connecting {item.path}")
                loaded = state.add_source(item.path, item.name, progress=say)
                sources.append(loaded["id"])
            return simple.create_and_build(
                state.layer, body.name, sources, metadata=body.metadata,
                domain=body.domain, problem=body.problem, client=ai_client(),
                progress=say)

        job_id = state.start_job(work, label="build ontology")
        return JSONResponse(status_code=202, content={"job_id": job_id,
                                                      "status": "running"})

    @app.get("/api/onto/{oid}")
    def onto_view(oid: str, request: Request):
        g = platform(request).layer.graph
        return guard(lambda: full_view(g, oid))

    @app.post("/api/onto/{oid}/rebuild")
    def onto_rebuild(oid: str, request: Request):
        state = platform(request)
        guard(lambda: reg.get(state.layer.graph, oid))
        job_id = state.start_job(
            lambda say: simple.build(state.layer, oid, client=ai_client(), progress=say),
            label=f"rebuild {oid}")
        return JSONResponse(status_code=202, content={"job_id": job_id,
                                                      "status": "running"})

    @app.post("/api/onto/{oid}/metadata")
    def onto_metadata(oid: str, request: Request, body: MetadataRequest):
        state = platform(request)
        guard(lambda: reg.get(state.layer.graph, oid))
        from api import paths
        guard(lambda: paths.check(body.path))
        meta = guard(lambda: simple.add_metadata(state.layer.graph, oid, body.path))
        job_id = state.start_job(
            lambda say: simple.build(state.layer, oid, client=ai_client(), progress=say),
            label=f"rebuild {oid}")
        return JSONResponse(status_code=202, content={
            "job_id": job_id, "status": "running", "file": meta["file"],
            "tables": len(meta["tables"])})

    @app.post("/api/onto/{oid}/context")
    def onto_context(oid: str, request: Request, body: ContextRequest):
        layer = platform(request).layer
        out = guard(lambda: simple.add_context(layer, oid, body.text, client=ai_client(),
                                               by=body.by or "you"))
        return {**out, "ontology": full_view(layer.graph, oid)}

    @app.put("/api/onto/{oid}/fields")
    def onto_field(oid: str, request: Request, body: FieldEdit):
        layer = platform(request).layer
        guard(lambda: simple.edit_field(layer, oid, body.key, by=body.by or "you",
                                        label=body.label, meaning=body.meaning,
                                        role=body.role, unit=body.unit))
        return full_view(layer.graph, oid)

    @app.put("/api/onto/{oid}/things")
    def onto_thing(oid: str, request: Request, body: ThingEdit):
        layer = platform(request).layer
        guard(lambda: simple.edit_thing(layer, oid, body.key, by=body.by or "you",
                                        name=body.name, description=body.description))
        return full_view(layer.graph, oid)

    @app.delete("/api/onto/{oid}")
    def onto_delete(oid: str, request: Request):
        guard(lambda: reg.delete_ontology(platform(request).layer.graph, oid))
        return {"deleted": oid}

    @app.get("/api/onto/{oid}/nexus")
    def onto_nexus(oid: str, request: Request, version: int | None = None):
        return guard(lambda: simple.for_excel(platform(request).layer.graph, oid, version))

    @app.get("/api/onto/{oid}/excel")
    def onto_excel(oid: str, request: Request, version: int | None = None):
        data = guard(lambda: simple.to_xlsx(platform(request).layer.graph, oid, version))
        return Response(data, media_type="application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet", headers={
                            "Content-Disposition": f'attachment; filename="{oid}-ontology.xlsx"'})

    @app.get("/api/onto/{oid}/use")
    def onto_use(oid: str, request: Request):
        g = platform(request).layer.graph
        v = guard(lambda: simple.view(g, oid))
        base = str(request.base_url).rstrip("/")
        mcp = f"{base}/mcp"
        return {
            "ontology": oid, "version": v["version"],
            "nexus": {"url": f"{base}/api/onto/{oid}/nexus",
                      "excel": f"{base}/api/onto/{oid}/excel",
                      "tables": ["things", "fields", "links", "calculations"]},
            "agents": {"mcp_url": mcp, "tool": "get_ontology",
                       "arguments": {"ontology": oid},
                       "claude_code": f"claude mcp add --transport http strata {mcp} "
                                      '--header "Authorization: Bearer <YOUR_KEY>"',
                       "keys": "Create a key on the Agents page; a key is scoped to "
                               "sources, so pick the sources of this ontology."},
            "files": {"json": f"{base}/api/onto/{oid}/nexus",
                      "owl": f"{base}/api/eo/{oid}/export/turtle",
                      "shacl": f"{base}/api/eo/{oid}/export/shacl",
                      "git_zip": f"{base}/api/eo/{oid}/export/zip"},
        }
