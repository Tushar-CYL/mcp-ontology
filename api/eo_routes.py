"""REST API for the Ontology Accelerator (``/api/eo/...``).

The same registry and read functions back these routes and the MCP tools,
so the UI, an external tool and an agent all see one ontology.

Errors keep the server's envelope: KeyError -> 404, ValueError -> 400,
PermissionError -> 403.
"""

from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from ontology import accelerator, drift, identity, maturity
from ontology import publish as pub
from ontology import registry as reg
from ontology import survivorship


class IntakeSource(BaseModel):
    source_id: str
    role: str = "source_system"
    owner_team: str = ""
    cadence_days: int = 1


class IntakeRequest(BaseModel):
    id: str
    name: str
    problem: str = ""
    domain: str = ""
    questions: list[str] = Field(default_factory=list)
    sources: list[IntakeSource] = Field(default_factory=list)


class RunRequest(BaseModel):
    upto: str | None = None


class DecideRequest(BaseModel):
    kind: str
    key: str
    decision: str
    by: str
    payload: dict | None = None
    note: str = ""


class ApproveAllRequest(BaseModel):
    kind: str
    by: str
    min_confidence: float = 0.0


class PublishRequest(BaseModel):
    by: str
    notes: str = ""


class RoleRequest(BaseModel):
    user: str
    role: str


class DemoRequest(BaseModel):
    customers: int = Field(300, ge=50, le=20000)
    run: bool = True


def register(app, platform, error) -> None:
    """Attach the routes. `platform(request)` returns the Platform; `error`
    builds the server's HTTPException."""

    def guard(fn):
        try:
            return fn()
        except PermissionError as exc:
            raise error(403, "Forbidden", str(exc)) from exc
        except KeyError as exc:
            raise error(404, "NotFound", str(exc).strip("'\"")) from exc
        except ValueError as exc:
            raise error(400, "BadRequest", str(exc)) from exc

    def graph(request):
        return platform(request).layer.graph

    @app.get("/api/eo/steps")
    def eo_steps():
        return {"steps": [{k: s[k] for k in ("id", "title", "level", "what")}
                          for s in accelerator.STEPS]}

    @app.get("/api/eo/ontologies")
    def eo_list(request: Request):
        g = graph(request)
        out = []
        for o in reg.list_ontologies(g):
            versions = reg.versions(g, o["id"])
            out.append({**o, "version": versions[-1]["version"] if versions else None,
                        "maturity": maturity.score(g, o["id"])["level"]})
        return {"ontologies": out}

    @app.post("/api/eo/ontologies")
    def eo_create(request: Request, body: IntakeRequest):
        loaded = {b.source for b in platform(request).layer.bundles}
        missing = [s.source_id for s in body.sources if s.source_id not in loaded]
        if missing:
            raise error(400, "BadRequest", "these sources are not loaded: "
                        + ", ".join(missing))
        return guard(lambda: reg.create(
            graph(request), body.id, name=body.name, problem=body.problem,
            domain=body.domain, questions=body.questions,
            sources=[s.model_dump() for s in body.sources]))

    @app.post("/api/eo/demo")
    def eo_demo(request: Request, body: DemoRequest):
        from ontology import demo
        state = platform(request)
        folder = Path(state.graph_path).resolve().parent / "scenarios" / "bi_mdm"

        def work(say):
            loaded = demo.load_demo(
                lambda path, name, p: state.add_source(path, name, progress=p),
                state.layer.graph, folder, customers=body.customers, progress=say)
            if body.run:
                loaded["run"] = accelerator.run(state.layer, loaded["ontology"],
                                                progress=say)
            return loaded

        job_id = state.start_job(work, label="demo")
        return JSONResponse(status_code=202, content={"job_id": job_id,
                                                      "status": "running"})

    @app.get("/api/eo/{oid}")
    def eo_state(oid: str, request: Request):
        return guard(lambda: accelerator.state(graph(request), oid))

    @app.post("/api/eo/{oid}/run")
    def eo_run(oid: str, request: Request, body: RunRequest):
        state = platform(request)
        guard(lambda: reg.get(state.layer.graph, oid))
        job_id = state.start_job(
            lambda say: accelerator.run(state.layer, oid, upto=body.upto, progress=say),
            label=f"run {oid}")
        return JSONResponse(status_code=202, content={"job_id": job_id,
                                                      "status": "running"})

    @app.get("/api/eo/{oid}/items")
    def eo_items(oid: str, request: Request, kind: str | None = None,
                 status: str | None = None):
        return guard(lambda: {"items": reg.items(graph(request), oid, kind=kind,
                                                 status=status)})

    @app.post("/api/eo/{oid}/decide")
    def eo_decide(oid: str, request: Request, body: DecideRequest):
        return guard(lambda: reg.decide(graph(request), oid, body.kind, body.key,
                                        body.decision, by=body.by, payload=body.payload,
                                        note=body.note))

    @app.post("/api/eo/{oid}/approve-all")
    def eo_approve_all(oid: str, request: Request, body: ApproveAllRequest):
        return guard(lambda: {"approved": reg.approve_all(
            graph(request), oid, kind=body.kind, by=body.by,
            min_confidence=body.min_confidence)})

    @app.post("/api/eo/{oid}/owners")
    def eo_owners(oid: str, request: Request):
        return guard(lambda: {"owners": pub.assign_owners(graph(request), oid)})

    @app.post("/api/eo/{oid}/roles")
    def eo_roles(oid: str, request: Request, body: RoleRequest):
        def go():
            reg.grant(graph(request), oid, body.user, body.role)
            return {"roles": reg.roles(graph(request), oid)}
        return guard(go)

    @app.post("/api/eo/{oid}/publish")
    def eo_publish(oid: str, request: Request, body: PublishRequest):
        layer = platform(request).layer
        return guard(lambda: pub.version_info(
            layer.graph, oid,
            pub.publish_version(layer, oid, by=body.by, notes=body.notes)["version"]))

    @app.get("/api/eo/{oid}/versions")
    def eo_versions(oid: str, request: Request):
        return guard(lambda: {"versions": reg.versions(graph(request), oid)})

    @app.get("/api/eo/{oid}/diff")
    def eo_diff(oid: str, a: int, b: int, request: Request):
        return guard(lambda: reg.diff(graph(request), oid, a, b))

    @app.get("/api/eo/{oid}/audit")
    def eo_audit(oid: str, request: Request):
        return guard(lambda: {"audit": reg.audit(graph(request), oid)})

    @app.get("/api/eo/{oid}/maturity")
    def eo_maturity(oid: str, request: Request):
        return guard(lambda: maturity.score(graph(request), oid))

    @app.get("/api/eo/{oid}/map")
    def eo_map(oid: str, request: Request):
        return guard(lambda: accelerator.knowledge_map(graph(request), oid))

    @app.post("/api/eo/{oid}/drift")
    def eo_drift(oid: str, request: Request):
        return guard(lambda: drift.check_drift(platform(request).layer, oid))

    @app.get("/api/eo/{oid}/resolve")
    def eo_resolve(oid: str, value: str, request: Request):
        layer = platform(request).layer

        def go():
            found = identity.resolve_entity(layer.graph, oid, value)
            if found is None:
                raise KeyError(f"no system holds the id {value!r}")
            return {**found, "golden": survivorship.golden_record(
                layer, oid, found["concept"], found["entity_id"])}
        return guard(go)

    @app.get("/api/eo/{oid}/column")
    def eo_column(oid: str, column: str, request: Request, version: int | None = None):
        return guard(lambda: pub.map_column(graph(request), oid, column, version))

    @app.get("/api/eo/{oid}/export/turtle")
    def eo_turtle(oid: str, request: Request, version: int | None = None):
        text = guard(lambda: pub.to_turtle(graph(request), oid, version))
        return PlainTextResponse(text, media_type="text/turtle")

    @app.get("/api/eo/{oid}/export/shacl")
    def eo_shacl(oid: str, request: Request, version: int | None = None):
        text = guard(lambda: pub.to_shacl(graph(request), oid, version))
        return PlainTextResponse(text, media_type="text/turtle")

    @app.get("/api/eo/{oid}/export/zip")
    def eo_zip(oid: str, request: Request, version: int | None = None):
        g = graph(request)

        def go():
            with tempfile.TemporaryDirectory() as tmp:
                root = pub.export_folder(g, oid, Path(tmp) / oid, version)
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
                    for path in sorted(root.rglob("*")):
                        if path.is_file():
                            z.write(path, path.relative_to(root.parent).as_posix())
                return buffer.getvalue()
        data = guard(go)
        return Response(data, media_type="application/zip", headers={
            "Content-Disposition": f'attachment; filename="{oid}-ontology.zip"'})
