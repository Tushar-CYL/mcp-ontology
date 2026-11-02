"""FastAPI server for the Middle Layer platform.

This is the production transport for the TypeScript UI:

* onboarding (connect/build a source),
* the four layers,
* approved metric evaluation,
* agent CRUD, preview, publish, ask, and run trace.

It reuses the same Graph / MiddleLayer / AgentRuntime as every other surface, so
there is no second implementation of a metric or a context pack.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent import certification as certification_mod
from agent import skills as skill_defs
from api.service import MiddleLayer
from ontology.connect import SourceError
from semantic import definitions as metric_defs

logger = logging.getLogger("middle_layer.api")

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = ROOT / "frontend" / "dist"
DEFAULT_GRAPH = os.environ.get(
    "MIDDLE_LAYER_GRAPH", str(ROOT / "data" / "graphs" / "platform.duckdb"))
ALLOWED_ORIGINS = [origin.strip() for origin in os.environ.get(
    "MIDDLE_LAYER_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:3000,http://127.0.0.1:3000").split(",") if origin.strip()]

DEFAULT_SKILLS = [
    {"id": "explain_metric", "label": "Explain a metric",
     "description": "Definition, SQL and current value from the semantic layer."},
    {"id": "compare_periods", "label": "Compare periods",
     "description": "Current vs prior period change, with the exact numbers."},
    {"id": "breakdown_by", "label": "Break down a metric",
     "description": "Top and bottom contributors by a declared dimension."},
    {"id": "graph_context", "label": "Graph context",
     "description": "Entities and relationships around the question."},
    {"id": "evidence_search", "label": "Evidence search",
     "description": "Pack the relevant facts, citations and caveats."},
]
DEFAULT_GUARDRAILS = [
    {"id": "approved_metrics", "label": "Approved metrics only",
     "instruction": "Answer only with metrics that have an approved definition.",
     "enabled": True, "source": "default"},
    {"id": "cite_evidence", "label": "Every number needs a citation",
     "instruction": "Never state a number that is not present in tool evidence.",
     "enabled": True, "source": "default"},
    {"id": "read_only", "label": "Read-only data access",
     "instruction": "Do not modify, export or delete source data.",
     "enabled": True, "source": "default"},
    {"id": "no_pii", "label": "No PII in answers",
     "instruction": "Do not expose email, phone, SSN or card data.",
     "enabled": True, "source": "default"},
]


class SourceRequest(BaseModel):
    path: str = Field(min_length=1)
    name: str | None = None


class AgentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    purpose: str = ""
    problem_statement: str = ""
    instructions: str = ""
    source_id: str = ""
    sources: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=lambda: ["revenue"])
    skills: list[str] = Field(
        default_factory=lambda: [skill["id"] for skill in DEFAULT_SKILLS])
    guardrails: list[Any] = Field(default_factory=lambda: list(DEFAULT_GUARDRAILS))


class SkillRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    source_id: str
    kind: str = "metric_focus"
    metric: str = ""
    dimension: str = ""
    owner: str = "workspace"


class SourceGuardrailRequest(BaseModel):
    rules: list[Any] = Field(default_factory=list)


class GuardrailSuggestRequest(BaseModel):
    problem_statement: str = ""
    source_id: str | None = None
    metrics: list[str] = Field(default_factory=list)


class PreviewRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class AskRequest(PreviewRequest):
    pass


class MetricEvalRequest(BaseModel):
    source: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    group_by: str | None = None
    time_from: str | None = None
    time_to: str | None = None
    limit: int = 1000


class Platform:
    """Mutable application state held by the FastAPI lifespan."""

    def __init__(self, graph_path: str | Path):
        self.graph_path = str(graph_path)
        self.layer = MiddleLayer(self.graph_path)
        self.warm_errors: list[dict] = []
        self._runtime = None

    def warm(self) -> None:
        """Reopen sources recorded in the graph after a server restart.

        The graph stores data and ontology, but not Python Schema objects; a
        warm start re-reads the source metadata (connect/discover) and skips the
        build because the signature is current.
        """
        configured = {name.strip() for name in os.environ.get(
            "MIDDLE_LAYER_WARM_SOURCES", "").split(",") if name.strip()}
        for source in self.layer.graph.sources():
            origin = source.get("origin")
            if not origin:
                continue
            if configured and source["source_id"] not in configured:
                continue
            try:
                self.layer.add_source(origin, source=source["source_id"])
            except Exception as exc:              # noqa: BLE001 - keep serving
                logger.warning("could not warm source %s: %s",
                               source["source_id"], exc)
                self.warm_errors.append(
                    {"source": source["source_id"], "error": str(exc)})
        # A graph built by an older process may predate the approved metric
        # seed; make sure the revenue-shaped source has one.
        for bundle in self.layer.bundles:
            try:
                if metric_defs.get_definition(self.layer.graph, "revenue",
                                              bundle.source) is not None:
                    continue
                names = {t.name for t in bundle.schema.tables}
                if {"orders", "order_lines", "products"} <= names:
                    metric_defs.seed_revenue_metric(
                        self.layer.graph, bundle.schema, bundle.onto,
                        bundle.source)
            except Exception as exc:              # noqa: BLE001
                logger.warning("could not seed revenue metric for %s: %s",
                               bundle.source, exc)
        self._refresh_runtime()

    def _refresh_runtime(self) -> None:
        from agent.runtime import AgentRuntime
        bundles = [(b.source, b.schema, b.onto) for b in self.layer.bundles]
        self._runtime = AgentRuntime(self.layer.graph, bundles)

    @property
    def runtime(self):
        if self._runtime is None:
            self._refresh_runtime()
        return self._runtime

    def add_source(self, path: str, name: str | None = None) -> dict:
        if not Path(path).exists() and not path.lower().startswith(
                ("postgres://", "mysql://", "snowflake://", "databricks://",
                 "http://", "https://")):
            raise FileNotFoundError(path)
        summary = self.layer.add_source(path, source=name)
        source_id = summary["source"]
        definition = metric_defs.get_definition(self.layer.graph, "revenue",
                                                source_id)
        if definition is None:
            schema = self.layer._bundle(source_id).schema
            onto = self.layer._bundle(source_id).onto
            names = {t.name for t in schema.tables}
            if {"orders", "order_lines", "products"} <= names:
                try:
                    metric_defs.seed_revenue_metric(
                        self.layer.graph, schema, onto, source_id)
                    logger.info("seeded approved revenue metric for %s",
                                source_id)
                except Exception as exc:          # noqa: BLE001 - non-fatal
                    logger.warning("could not seed revenue metric: %s", exc)
        self._refresh_runtime()
        return _source_payload(self, source_id, summary)


def _source_payload(state: Platform, source_id: str,
                    summary: dict | None = None) -> dict:
    """One source in the TypeScript contract shape (id/name/counts/warnings)."""
    row = next((dict(item) for item in state.layer.graph.sources()
                if item["source_id"] == source_id), {})
    bundle = next((item for item in state.layer.bundles
                   if item.source == source_id), None)
    warnings = list(bundle.schema.warnings) if bundle else []
    return {
        "id": source_id,
        "name": row.get("name") or source_id,
        "origin": row.get("origin") or "",
        "tables": int(row.get("tables") or 0),
        "classes": len(bundle.onto.classes) if bundle else 0,
        "relations": len(bundle.onto.relations) if bundle else 0,
        "nodes": state.layer.graph.one(
            "SELECT count(*) FROM nodes WHERE source_id = ?", [source_id]) or 0,
        "edges": state.layer.graph.one(
            "SELECT count(*) FROM edges WHERE source_id = ?", [source_id]) or 0,
        "status": row.get("status") or "ready",
        "warnings": warnings,
        "summary": summary or {},
    }


def _agent_payload(body: AgentRequest) -> dict:
    """Accept the UI shape (sources, string guardrails) and the stored shape."""
    data = body.model_dump()
    source = data.get("source_id") or next(iter(data.get("sources") or []), "")
    data["source_id"] = source
    data.pop("sources", None)
    normalized = []
    for guardrail in data.get("guardrails") or []:
        if isinstance(guardrail, str):
            text = guardrail.strip()
            if not text:
                continue
            normalized.append({
                "id": "user_" + "".join(
                    c if c.isalnum() else "_" for c in text.lower())[:32],
                "label": text[:100], "instruction": text,
                "enabled": True, "source": "user"})
        elif isinstance(guardrail, dict) and guardrail.get("instruction"):
            normalized.append(guardrail)
    data["guardrails"] = normalized or list(DEFAULT_GUARDRAILS)
    data["metrics"] = data.get("metrics") or ["revenue"]
    return data


def _error(status: int, kind: str, message: str) -> HTTPException:
    return HTTPException(status_code=status,
                         detail={"error": {"type": kind,
                                           "message": message}})


def _layer_source(platform: Platform, source: str | None):
    if source:
        return source
    ids = platform.layer.graph.source_ids()
    if len(ids) == 1:
        return ids[0]
    return None


def create_app(graph_path: str | Path | None = None,
               warm: bool = True) -> FastAPI:
    graph_path = graph_path or DEFAULT_GRAPH

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        platform = Platform(graph_path)
        if warm:
            platform.warm()
        app.state.platform = platform
        yield
        platform.layer.close()

    app = FastAPI(title="The Middle Layer", version="1.0",
                  description="Governed ontology, graph, metrics and agent "
                              "evidence over any data source.",
                  lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=ALLOWED_ORIGINS or ["*"],
        allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

    # ---------------------------------------------------------- errors
    @app.exception_handler(KeyError)
    def key_error(_: Request, exc: KeyError):
        return JSONResponse(status_code=404, content={
            "error": {"type": "KeyError", "message": str(exc).strip("'")}})

    @app.exception_handler(ValueError)
    def value_error(_: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={
            "error": {"type": "ValueError", "message": str(exc)}})

    @app.exception_handler(SourceError)
    def source_error(_: Request, exc: SourceError):
        return JSONResponse(status_code=400, content={
            "error": {"type": "SourceError", "message": str(exc)}})

    @app.exception_handler(FileNotFoundError)
    def not_found(_: Request, exc: FileNotFoundError):
        return JSONResponse(status_code=400, content={
            "error": {"type": "FileNotFoundError",
                      "message": f"path not found: {exc}"}})

    @app.exception_handler(HTTPException)
    def http_error(_: Request, exc: HTTPException):
        """Keep the public error envelope `{error:{type,message}}` uniform.

        Without this, FastAPI would wrap our detail in `{"detail": {...}}`, and
        the TypeScript client would have two error shapes to understand.
        """
        detail = exc.detail
        if isinstance(detail, dict) and isinstance(detail.get("error"), dict):
            content = detail
        else:
            content = {"error": {"type": "HttpError",
                                 "message": str(detail)}}
        return JSONResponse(status_code=exc.status_code, content=content)

    def platform(request: Request) -> Platform:
        return request.app.state.platform

    # ---------------------------------------------------------- health
    @app.get("/api/health")
    def health(request: Request):
        state = platform(request)
        configured = bool(os.environ.get("EYQ_INCUBATOR_ENDPOINT")
                          and os.environ.get("EYQ_INCUBATOR_KEY"))
        return {"status": "ok", "graph": state.graph_path,
                "sources": state.layer.graph.source_ids(),
                "llm": {"configured": configured,
                        "model": os.environ.get("EYQ_MODEL", "gpt-5.2")},
                "warm_errors": state.warm_errors}

    # --------------------------------------------------------- sources
    @app.get("/api/sources")
    def sources(request: Request):
        state = platform(request)
        loaded = {bundle.source for bundle in state.layer.bundles}
        return {"sources": [_source_payload(state, row["source_id"])
                            for row in state.layer.graph.sources()
                            if row["source_id"] in loaded]}

    @app.post("/api/sources")
    def add_source(request: Request, body: SourceRequest):
        try:
            return platform(request).add_source(body.path, body.name)
        except SourceError as exc:
            raise _error(400, "SourceError", str(exc)) from exc
        except FileNotFoundError as exc:
            raise _error(400, "FileNotFoundError",
                         f"path not found: {body.path}") from exc
        except Exception as exc:                  # noqa: BLE001
            logger.exception("source add failed")
            raise _error(500, type(exc).__name__, str(exc)) from exc

    # ------------------------------------------------ source guardrails
    @app.get("/api/sources/{source_id}/guardrails")
    def get_source_guardrails(source_id: str, request: Request):
        state = platform(request)
        if source_id not in {bundle.source for bundle in state.layer.bundles}:
            raise _error(404, "SourceError", f"source {source_id!r} is not loaded")
        return {"source_id": source_id,
                "rules": state.runtime.source_guardrails(source_id)}

    @app.put("/api/sources/{source_id}/guardrails")
    def save_source_guardrails(source_id: str, request: Request,
                               body: SourceGuardrailRequest):
        state = platform(request)
        if source_id not in {bundle.source for bundle in state.layer.bundles}:
            raise _error(404, "SourceError", f"source {source_id!r} is not loaded")
        return {"source_id": source_id,
                "rules": state.runtime.save_source_guardrails(
                    source_id, body.rules)}

    # ---------------------------------------------------------- layers
    @app.get("/api/layers/ontology")
    def ontology(request: Request, source: str | None = None):
        state = platform(request)
        source = _layer_source(state, source)
        try:
            return state.layer.ontology(source)
        except KeyError as exc:
            raise _error(409, "SourceRequired", str(exc)) from exc

    @app.get("/api/layers/graph")
    @app.get("/api/graph/subgraph")
    def graph_layer(request: Request, source: str | None = None,
                    limit: int = Query(300, ge=20, le=1200),
                    relation: str | None = None):
        state = platform(request)
        source = _layer_source(state, source)
        try:
            nodes, edges = state.layer.graph.subgraph(
                limit=limit, relation=relation, source=source)
        except KeyError as exc:
            raise _error(409, "SourceRequired", str(exc)) from exc
        return {"source": source, "nodes": nodes, "edges": edges,
                "limit": limit}

    # --------------------------------------------------------- metrics
    @app.get("/api/metrics")
    def metrics(request: Request, source: str | None = None):
        state = platform(request)
        source = _layer_source(state, source)
        return {"metrics": metric_defs.list_definitions(
            state.layer.graph, source)}

    @app.post("/api/metrics/{name}/evaluate")
    def evaluate(name: str, request: Request, body: MetricEvalRequest):
        state = platform(request)
        source = body.source or _layer_source(state, None)
        try:
            return metric_defs.evaluate_definition(
                state.layer.graph, name, source, filters=body.filters,
                group_by=body.group_by, time_from=body.time_from,
                time_to=body.time_to, limit=body.limit)
        except KeyError as exc:
            raise _error(404, "MetricError", str(exc)) from exc

    # --------------------------------------------------------- context
    @app.get("/api/context")
    def context(request: Request, source: str | None = None,
                class_name: str = Query("", alias="class"),
                key: str = "", budget_chars: int = 1200):
        state = platform(request)
        source = _layer_source(state, source)
        if not source or not class_name or not key:
            raise _error(400, "BadRequest",
                         "source, class and key are required")
        try:
            return state.layer.context(entity=(source, class_name, key),
                                       budget_chars=budget_chars)
        except ValueError as exc:
            raise _error(404, "NotFound", str(exc)) from exc

    # ----------------------------------------------------------- skills
    @app.get("/api/skills")
    def skills(request: Request, source: str | None = None):
        state = platform(request)
        source = _layer_source(state, source)
        return {"skills": skill_defs.list_all_skills(state.layer.graph, source)}

    @app.post("/api/skills")
    def create_skill(request: Request, body: SkillRequest):
        state = platform(request)
        try:
            return skill_defs.create_custom_skill(
                state.layer.graph, body.model_dump())
        except ValueError as exc:
            raise _error(400, "SkillError", str(exc)) from exc

    @app.delete("/api/skills/{skill_id}")
    def delete_skill(skill_id: str, request: Request):
        state = platform(request)
        if not skill_id.startswith("skill_"):
            raise _error(400, "SkillError", "built-in skills cannot be deleted")
        skill_defs.delete_custom_skill(state.layer.graph, skill_id)
        return {"deleted": skill_id}

    @app.get("/api/certification")
    def certification(request: Request, source: str | None = None):
        state = platform(request)
        source = _layer_source(state, source)
        if not source:
            raise _error(409, "SourceRequired", "select a source first")
        try:
            return certification_mod.certify_source(state.layer, source)
        except KeyError as exc:
            raise _error(404, "CertificationError", str(exc)) from exc

    # ----------------------------------------------------------- tools
    @app.get("/api/tools")
    def tools():
        return {"tools": DEFAULT_SKILLS}

    @app.post("/api/agents/suggest-guardrails")
    def suggest_guardrails(request: Request, body: GuardrailSuggestRequest):
        state = platform(request)
        source = body.source_id or _layer_source(state, None)
        try:
            suggestions = state.runtime.suggest_guardrails(
                body.problem_statement, source, body.metrics)
        except Exception as exc:                  # noqa: BLE001
            raise _error(400, "SuggestionError", str(exc)) from exc
        return {"guardrails": suggestions,
                "configured": bool(os.environ.get("EYQ_INCUBATOR_ENDPOINT")
                                    and os.environ.get("EYQ_INCUBATOR_KEY"))}

    # ---------------------------------------------------------- agents
    @app.get("/api/agents")
    def agents(request: Request):
        return {"agents": platform(request).runtime.list_agents()}

    @app.post("/api/agents")
    def create_agent(request: Request, body: AgentRequest):
        try:
            return platform(request).runtime.create_agent(_agent_payload(body))
        except ValueError as exc:
            raise _error(400, "AgentError", str(exc)) from exc

    @app.get("/api/agents/{agent_id}")
    def get_agent(agent_id: str, request: Request):
        return platform(request).runtime.get_agent(agent_id)

    @app.put("/api/agents/{agent_id}")
    def update_agent(agent_id: str, request: Request, body: AgentRequest):
        return platform(request).runtime.update_agent(
            agent_id, _agent_payload(body))

    @app.post("/api/agents/{agent_id}/publish")
    def publish_agent(agent_id: str, request: Request):
        agent = platform(request).runtime.publish_agent(agent_id)
        return {"status": agent.get("status", "published"), "agent": agent}

    @app.post("/api/agents/{agent_id}/preview")
    def preview(agent_id: str, request: Request, body: PreviewRequest):
        try:
            return platform(request).runtime.preview(agent_id, body.question)
        except (KeyError, ValueError) as exc:
            raise _error(400, "AgentError", str(exc)) from exc

    @app.post("/api/agents/{agent_id}/ask")
    def ask(agent_id: str, request: Request, body: AskRequest):
        try:
            return platform(request).runtime.ask(agent_id, body.question)
        except (KeyError, ValueError) as exc:
            raise _error(400, "AgentError", str(exc)) from exc

    @app.get("/api/runs/{run_id}")
    def run(run_id: str, request: Request):
        return platform(request).runtime.get_run(run_id)

    # --------------------------------------------------------- static
    if FRONTEND_DIST.exists():
        assets = FRONTEND_DIST / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=str(assets)),
                      name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            if path.startswith("api/"):
                raise _error(404, "NotFound", f"no route /{path}")
            candidate = FRONTEND_DIST / path
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
