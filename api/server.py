"""FastAPI server for Strata.

This is the production transport for the TypeScript UI and for external
agents:

* onboarding (connect/build a source),
* the four layers,
* approved metric evaluation,
* agent connections: register an agent, issue keys, see its usage,
* ``POST /mcp``: MCP over HTTP for external agents, scoped by key.

It reuses the same Graph / MiddleLayer / AgentRuntime as every other surface, so
there is no second implementation of a metric or a context pack.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent import connections
from agent import preset_runner
from agent.presets import PRESETS, get_preset, tools_for
from context.question import build_question_context
from api import mcp_server
from api.service import MiddleLayer
from ontology.connect import SourceError
from context.suggest import suggest_questions
from semantic import autopilot
from semantic import definitions as metric_defs
from semantic import feedback as feedback_mod
from semantic.validate import validate_sql

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
    # Load in the background and report progress at /api/jobs/{id}, so a big
    # source never ties up a request (or the UI) for minutes.
    background: bool = False


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
    preset: str = "insight"


class MetricStatusRequest(BaseModel):
    source: str | None = None
    status: str


class SourceOnlyRequest(BaseModel):
    source: str | None = None


class SynonymsRequest(BaseModel):
    source: str | None = None
    synonyms: list[str] = Field(default_factory=list)


class KeyRequest(BaseModel):
    label: str = Field(default="", max_length=120)


class ValidateRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=20_000)
    source: str | None = None
    metric: str | None = None


class FeedbackRequest(BaseModel):
    source: str | None = None
    question: str = ""
    correction: str = ""
    kind: str = "other"
    answer: str = ""
    metric: str | None = None
    agent_id: str | None = None


class DecisionRequest(BaseModel):
    decision: str
    note: str = ""


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
    compare_previous: bool = False
    # A person previewing a proposed (draft) metric before approving it.
    preview_draft: bool = False


class Platform:
    """Mutable application state held by the FastAPI lifespan."""

    def __init__(self, graph_path: str | Path):
        self.graph_path = str(graph_path)
        self.layer = MiddleLayer(self.graph_path)
        self.warm_errors: list[dict] = []
        self.jobs: dict[str, dict] = {}
        self.warming = False
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
        # Make sure the governed metric catalog exists for revenue-shaped
        # sources. This is idempotent and also upgrades older graphs.
        for bundle in self.layer.bundles:
            self._propose_metrics(bundle.source)
        for bundle in self.layer.bundles:
            try:
                names = {t.name for t in bundle.schema.tables}
                if {"orders", "order_lines", "products"} <= names:
                    metric_defs.seed_metric_catalog(
                        self.layer.graph, bundle.schema, bundle.onto,
                        bundle.source)
            except Exception as exc:              # noqa: BLE001
                logger.warning("could not seed metric catalog for %s: %s",
                               bundle.source, exc)
        self._refresh_runtime()

    def _propose_metrics(self, source_id: str) -> None:
        """Draft metrics for any dataset (skipped when it already has some)."""
        try:
            bundle = self.layer._bundle(source_id)
            created = autopilot.seed_proposals(
                self.layer.graph, bundle.schema, bundle.onto, source_id)
            upgraded = autopilot.upgrade_mechanical(self.layer.graph, source_id)
            if created or upgraded:
                logger.info("metrics for %s: %d proposed, %d exact ones "
                            "approved", source_id, len(created), len(upgraded))
                # The cached health report predates these metrics.
                self.layer._readiness.pop(source_id, None)
        except Exception as exc:                  # noqa: BLE001 - non-fatal
            logger.warning("could not propose metrics for %s: %s",
                           source_id, exc)

    def _refresh_runtime(self) -> None:
        from agent.runtime import AgentRuntime
        bundles = [(b.source, b.schema, b.onto) for b in self.layer.bundles]
        self._runtime = AgentRuntime(self.layer.graph, bundles)

    @property
    def runtime(self):
        if self._runtime is None:
            self._refresh_runtime()
        return self._runtime

    def start_load(self, path: str, name: str | None = None) -> str:
        """Load a source on a background thread; return the job id."""
        job_id = "job_" + uuid.uuid4().hex[:12]
        job = {"id": job_id, "status": "running", "path": path, "name": name,
               "steps": [], "result": None, "error": None,
               "started": time.time(), "finished": None}
        self.jobs[job_id] = job

        def step(line: str) -> None:
            job["steps"].append({"t": round(time.time() - job["started"], 1),
                                 "text": str(line).strip()})

        def run() -> None:
            try:
                job["result"] = self.add_source(path, name, progress=step)
                job["status"] = "done"
            except FileNotFoundError:
                job["error"] = f"path not found: {path}"
                job["status"] = "failed"
            except Exception as exc:              # noqa: BLE001 - reported
                logger.exception("background load failed")
                job["error"] = f"{type(exc).__name__}: {exc}"
                job["status"] = "failed"
            finally:
                job["finished"] = time.time()
                step("finished" if job["status"] == "done" else "failed")

        threading.Thread(target=run, name=job_id, daemon=True).start()
        return job_id

    def job_view(self, job_id: str) -> dict:
        job = self.jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        end = job["finished"] or time.time()
        return {**{k: v for k, v in job.items() if k not in ("started", "finished")},
                "elapsed_s": round(end - job["started"], 1)}

    def add_source(self, path: str, name: str | None = None,
                   progress=None) -> dict:
        if not Path(path).exists() and not path.lower().startswith(
                ("postgres://", "mysql://", "snowflake://", "databricks://",
                 "http://", "https://")):
            raise FileNotFoundError(path)
        say = progress or (lambda _line: None)
        summary = self.layer.add_source(path, source=name, progress=say)
        source_id = summary["source"]
        schema = self.layer._bundle(source_id).schema
        onto = self.layer._bundle(source_id).onto
        names = {t.name for t in schema.tables}
        if {"orders", "order_lines", "products"} <= names:
            try:
                metric_defs.seed_metric_catalog(
                    self.layer.graph, schema, onto, source_id)
                logger.info("seeded governed metric catalog for %s",
                            source_id)
            except Exception as exc:              # noqa: BLE001 - non-fatal
                logger.warning("could not seed metric catalog: %s", exc)
        self._propose_metrics(source_id)
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


def _request_key(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.headers.get("x-api-key")


def _call_summary(arguments: dict) -> str:
    for field in ("question", "metric", "query", "table", "name",
                  "citation", "class"):
        if arguments.get(field):
            return str(arguments[field])
    return ""


def _call_metric(params: dict, response: dict | None) -> str | None:
    """Which governed metric a tool call consumed, for usage reporting."""
    arguments = params.get("arguments") or {}
    if arguments.get("metric"):
        return str(arguments["metric"])
    if params.get("name") not in ("get_context", "check_answerable"):
        return None
    try:
        payload = json.loads(response["result"]["content"][0]["text"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    metric = payload.get("metric")
    if isinstance(metric, dict):
        metric = metric.get("name")
    return str(metric) if metric else None


def _connection_details(agent: dict, base: str) -> dict:
    """Copy-paste configuration for the common agent hosts. No secret."""
    mcp_url = f"{base}/mcp"
    server = "strata-" + "".join(
        c if c.isalnum() else "-" for c in agent["name"].lower()).strip("-")
    auth = "Authorization: Bearer <YOUR_KEY>"
    claude = {"mcpServers": {server: {
        "command": "npx",
        "args": ["-y", "mcp-remote", mcp_url, "--header", auth]}}}
    cursor = {"mcpServers": {server: {
        "url": mcp_url, "headers": {"Authorization": "Bearer <YOUR_KEY>"}}}}
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "get_context", "arguments": {
                           "question": "Why did revenue fall last month?"}}})
    curl = (f'curl -s {mcp_url} -H "{auth}" '
            f"-H \"Content-Type: application/json\" -d '{body}'")
    # Windows PowerShell 5.1 aliases `curl` to Invoke-WebRequest, which takes
    # different arguments, so Windows users get native cmdlets instead.
    powershell = "\n".join([
        '$key = "<YOUR_KEY>"',
        "$body = @{",
        '  jsonrpc = "2.0"; id = 1; method = "tools/call"',
        "  params  = @{",
        '    name      = "get_context"',
        '    arguments = @{ question = "Why did revenue fall last month?" }',
        "  }",
        "} | ConvertTo-Json -Depth 6",
        f'$r = Invoke-RestMethod -Uri "{mcp_url}" -Method Post `',
        '  -Headers @{ Authorization = "Bearer $key" } `',
        '  -ContentType "application/json" -Body $body -TimeoutSec 600',
        "# The tool result is JSON text inside the MCP envelope:",
        "$r.result.content[0].text | ConvertFrom-Json | Select-Object answer, coverage",
    ])
    return {"agent_id": agent["id"], "name": agent["name"],
            "mcp_url": mcp_url, "server_name": server,
            "scope": {"sources": [agent["source_id"]] if agent.get("source_id")
                      else [], "metrics": list(agent.get("metrics") or [])},
            "preset": agent.get("preset") or "insight",
            "tools": tools_for(agent.get("preset")),
            "snippets": {"claude_desktop": json.dumps(claude, indent=2),
                         "cursor": json.dumps(cursor, indent=2),
                         "curl": curl, "powershell": powershell,
                         "claude_code": (
                             f"claude mcp add --transport http {server} "
                             f'{mcp_url} --header "{auth}"')}}


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
            # Re-opening every saved source can take minutes (and a rebuild
            # after an upgrade longer). The API answers at once; sources
            # appear as they finish, and /api/health says it is warming.
            platform.warming = True

            def warm_in_background() -> None:
                try:
                    platform.warm()
                except Exception:                 # noqa: BLE001 - logged
                    logger.exception("warm start failed")
                finally:
                    platform.warming = False

            threading.Thread(target=warm_in_background, name="warm",
                             daemon=True).start()
        app.state.platform = platform
        yield
        platform.layer.close()

    app = FastAPI(title="Strata", version="1.0",
                  description="Governed reference content - ontology, graph, "
                              "metrics and cited context - for any AI agent.",
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
                "warm_errors": state.warm_errors,
                "warming": state.warming}

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
        if body.background:
            job_id = platform(request).start_load(body.path, body.name)
            return JSONResponse(status_code=202, content={
                "job_id": job_id, "status": "running"})
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

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str, request: Request):
        try:
            return platform(request).job_view(job_id)
        except KeyError as exc:
            raise _error(404, "NotFound", f"no job {job_id!r}") from exc

    # ---------------------------------------------------------- layers
    @app.get("/api/layers/ontology")
    def ontology(request: Request, source: str | None = None):
        state = platform(request)
        source = _layer_source(state, source)
        try:
            return state.layer.ontology(source)
        except KeyError as exc:
            raise _error(409, "SourceRequired", str(exc)) from exc

    @app.get("/api/entities")
    def entities(request: Request, source: str | None = None,
                 class_name: str = Query("", alias="class"), q: str = "",
                 limit: int = Query(50, ge=1)):
        """Real keys of one kind, for picking an entity to inspect."""
        state = platform(request)
        source = _layer_source(state, source)
        if not source or not class_name:
            raise _error(400, "BadRequest", "source and class are required")
        try:
            keys, total = state.layer.graph.search_keys(
                class_name, q.strip()[:100], limit, source=source)
        except KeyError as exc:
            raise _error(404, "NotFound", str(exc).strip("'")) from exc
        return {"source": source, "class": class_name, "query": q,
                "keys": keys, "total": total}

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
                time_to=body.time_to, limit=body.limit,
                compare_previous=body.compare_previous,
                allow_draft=body.preview_draft)
        except KeyError as exc:
            raise _error(404, "MetricError", str(exc)) from exc

    @app.post("/api/metrics/approve-proposed")
    def approve_proposed(request: Request, body: SourceOnlyRequest):
        """A person accepting every autopilot proposal at once."""
        state = platform(request)
        source = _layer_source(state, body.source)
        if not source:
            raise _error(409, "SourceRequired", "select a source first")
        approved = []
        for definition in metric_defs.list_definitions(state.layer.graph, source):
            if definition["status"] == "draft" and \
                    definition.get("owner") == autopilot.OWNER:
                metric_defs.set_status(state.layer.graph, definition["name"],
                                       source, "approved")
                approved.append(definition["name"])
        return {"source": source, "approved": approved}

    @app.post("/api/metrics/{name}/status")
    def metric_status(name: str, request: Request, body: MetricStatusRequest):
        state = platform(request)
        source = _layer_source(state, body.source)
        if not source:
            raise _error(409, "SourceRequired", "select a source first")
        try:
            return metric_defs.set_status(state.layer.graph, name, source,
                                          body.status)
        except KeyError as exc:
            raise _error(404, "MetricError", str(exc).strip("'")) from exc
        except ValueError as exc:
            raise _error(400, "MetricError", str(exc)) from exc

    @app.put("/api/metrics/{name}/synonyms")
    def metric_synonyms(name: str, request: Request, body: SynonymsRequest):
        state = platform(request)
        source = _layer_source(state, body.source)
        if not source:
            raise _error(409, "SourceRequired", "select a source first")
        try:
            saved = metric_defs.set_synonyms(state.layer.graph, name, source,
                                             body.synonyms)
        except KeyError as exc:
            raise _error(404, "MetricError", str(exc).strip("'")) from exc
        except ValueError as exc:
            raise _error(400, "MetricError", str(exc)) from exc
        return {"metric": name, "source": source, "synonyms": saved}

    @app.get("/api/metrics/{name}/health")
    def metric_health(name: str, request: Request,
                      source: str | None = None):
        state = platform(request)
        return metric_defs.metric_health(
            state.layer.graph, name, _layer_source(state, source))

    @app.get("/api/metrics/{name}/insights")
    def metric_insights(name: str, request: Request,
                        source: str | None = None,
                        group_by: str | None = None,
                        time_from: str | None = None,
                        time_to: str | None = None,
                        preview_draft: bool = False,
                        grain: str | None = None):
        state = platform(request)
        try:
            return metric_defs.metric_insights(
                state.layer.graph, name, _layer_source(state, source),
                group_by=group_by, time_from=time_from, time_to=time_to,
                allow_draft=preview_draft, grain=grain)
        except KeyError as exc:
            raise _error(404, "MetricError", str(exc)) from exc

    # --------------------------------------------------------- context
    @app.get("/api/context/suggestions")
    def context_suggestions(request: Request, source: str | None = None):
        state = platform(request)
        source = _layer_source(state, source)
        if not source:
            raise _error(409, "SourceRequired", "select a source first")
        return suggest_questions(state.layer.graph, state.layer, source)

    @app.get("/api/context")
    def context(request: Request, source: str | None = None,
                class_name: str = Query("", alias="class"),
                key: str = "", budget_chars: int = 1200,
                question: str = "", metric: str | None = None):
        state = platform(request)
        source = _layer_source(state, source)
        if question:
            if not source:
                raise _error(409, "SourceRequired", "select a source first")
            bundles = [(bundle.source, bundle.schema, bundle.onto)
                       for bundle in state.layer.bundles]
            try:
                return build_question_context(
                    state.layer.graph, bundles, question, source=source,
                    metric=metric, budget_chars=budget_chars)
            except (KeyError, ValueError) as exc:
                raise _error(400, "ContextError", str(exc)) from exc
        if not source or not class_name or not key:
            raise _error(400, "BadRequest",
                         "source, class and key are required")
        try:
            return state.layer.context(entity=(source, class_name, key),
                                       budget_chars=budget_chars)
        except ValueError as exc:
            raise _error(404, "NotFound", str(exc)) from exc

    @app.get("/api/certification")
    def certification(request: Request, source: str | None = None,
                      refresh: bool = False):
        state = platform(request)
        source = _layer_source(state, source)
        if not source:
            raise _error(409, "SourceRequired", "select a source first")
        try:
            return state.layer.readiness(source, refresh=refresh)
        except KeyError as exc:
            raise _error(404, "CertificationError", str(exc)) from exc

    # ---------------------------------------------------------- agents
    @app.get("/api/agents")
    def agents(request: Request):
        return {"agents": platform(request).runtime.list_agents()}

    @app.get("/api/agent-presets")
    def agent_presets():
        return {"presets": list(PRESETS.values())}

    @app.post("/api/agents")
    def create_agent(request: Request, body: AgentRequest):
        try:
            get_preset(body.preset)
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

    def _run_agent(request: Request, agent_id: str, question: str,
                   persist: bool) -> dict:
        state = platform(request)
        try:
            agent = state.runtime.get_agent(agent_id)
            return preset_runner.run(state.layer, state.runtime, agent,
                                     question, persist=persist)
        except (KeyError, ValueError) as exc:
            raise _error(400, "AgentError", str(exc)) from exc

    @app.post("/api/agents/{agent_id}/preview")
    def preview(agent_id: str, request: Request, body: PreviewRequest):
        return _run_agent(request, agent_id, body.question, persist=False)

    @app.post("/api/agents/{agent_id}/ask")
    def ask(agent_id: str, request: Request, body: AskRequest):
        return _run_agent(request, agent_id, body.question, persist=True)

    @app.get("/api/runs/{run_id}")
    def run(run_id: str, request: Request):
        return platform(request).runtime.get_run(run_id)

    # ------------------------------------------------- agent connections
    def _agent(state: Platform, agent_id: str) -> dict:
        try:
            return state.runtime.get_agent(agent_id)
        except KeyError as exc:
            raise _error(404, "AgentError", f"no agent {agent_id!r}") from exc

    @app.delete("/api/agents/{agent_id}")
    def delete_agent(agent_id: str, request: Request):
        state = platform(request)
        _agent(state, agent_id)
        connections.forget_agent(state.layer.graph, agent_id)
        state.runtime.delete_agent(agent_id)
        return {"deleted": agent_id}

    @app.get("/api/agents/{agent_id}/keys")
    def list_agent_keys(agent_id: str, request: Request):
        state = platform(request)
        _agent(state, agent_id)
        return {"keys": connections.list_keys(state.layer.graph, agent_id)}

    @app.post("/api/agents/{agent_id}/keys")
    def issue_agent_key(agent_id: str, request: Request, body: KeyRequest):
        state = platform(request)
        _agent(state, agent_id)
        return connections.issue_key(state.layer.graph, agent_id, body.label)

    @app.delete("/api/agents/{agent_id}/keys/{key_id}")
    def revoke_agent_key(agent_id: str, key_id: str, request: Request):
        state = platform(request)
        if not connections.revoke_key(state.layer.graph, agent_id, key_id):
            raise _error(404, "KeyError", f"no live key {key_id!r}")
        return {"revoked": key_id}

    @app.get("/api/agents/{agent_id}/usage")
    def agent_usage(agent_id: str, request: Request,
                    limit: int = Query(50, ge=1, le=500)):
        state = platform(request)
        _agent(state, agent_id)
        return {"calls": connections.usage(state.layer.graph, agent_id, limit)}

    @app.get("/api/agents/{agent_id}/connection")
    def agent_connection(agent_id: str, request: Request):
        state = platform(request)
        agent = _agent(state, agent_id)
        return _connection_details(agent, str(request.base_url).rstrip("/"))

    # ------------------------------------------------- Phase 5: validate
    @app.post("/api/validate/sql")
    def validate_sql_endpoint(request: Request, body: ValidateRequest):
        state = platform(request)
        source = _layer_source(state, body.source)
        if not source:
            raise _error(409, "SourceRequired", "select a source first")
        definition = None
        if body.metric:
            definition = metric_defs.get_definition(
                state.layer.graph, body.metric, source)
            if definition is None:
                raise _error(404, "MetricError", f"no metric {body.metric!r}")
        return validate_sql(state.layer.graph,
                            state.layer._bundle(source).schema, source,
                            body.sql, definition)

    # ---------------------------------------------------- Phase 6: learn
    @app.post("/api/feedback")
    def feedback_create(request: Request, body: FeedbackRequest):
        state = platform(request)
        source = _layer_source(state, body.source) or ""
        if body.agent_id:
            _agent(state, body.agent_id)
        try:
            return feedback_mod.submit(
                state.layer.graph, source=source, question=body.question,
                correction=body.correction, kind=body.kind,
                answer=body.answer, metric=body.metric,
                agent_id=body.agent_id)
        except ValueError as exc:
            raise _error(400, "FeedbackError", str(exc)) from exc

    @app.get("/api/feedback")
    def feedback_list(request: Request, source: str | None = None,
                      pending: bool = False):
        state = platform(request)
        source = _layer_source(state, source) or ""
        return {"items": feedback_mod.list_feedback(
            state.layer.graph, source, pending_only=pending)}

    @app.post("/api/feedback/{item_id}/decision")
    def feedback_decide(item_id: str, request: Request, body: DecisionRequest):
        state = platform(request)
        try:
            return feedback_mod.decide(state.layer.graph, item_id,
                                       body.decision, note=body.note)
        except ValueError as exc:
            raise _error(400, "FeedbackError", str(exc)) from exc
        except KeyError as exc:
            raise _error(404, "FeedbackError", str(exc)) from exc

    @app.get("/api/usage/metrics")
    def usage_metrics(request: Request, source: str | None = None):
        state = platform(request)
        source = _layer_source(state, source)
        ids = [a["id"] for a in state.runtime.list_agents()
               if not source or a.get("source_id") == source]
        return {"source": source,
                "metrics": connections.metric_usage(state.layer.graph, ids)}

    # -------------------------------------------------------------- MCP
    @app.get("/mcp")
    def mcp_get():
        raise _error(405, "MethodNotAllowed", "POST JSON-RPC messages to /mcp")

    @app.post("/mcp")
    async def mcp(request: Request):
        state = platform(request)
        agent_id = connections.verify_key(state.layer.graph,
                                          _request_key(request))
        agent = None
        if agent_id is not None:
            try:
                agent = state.runtime.get_agent(agent_id)
            except KeyError:
                agent = None
        if agent is None:
            return JSONResponse(
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="strata"'},
                content={"error": {
                    "type": "Unauthorized",
                    "message": "a valid agent key is required "
                               "(Authorization: Bearer <key> or x-api-key)"}})
        try:
            message = await request.json()
        except ValueError:
            return JSONResponse(content={"jsonrpc": "2.0", "id": None, "error": {
                "code": -32700, "message": "parse error"}})
        scope = {"agent_id": agent_id,
                 "sources": [agent["source_id"]] if agent.get("source_id") else [],
                 "metrics": list(agent.get("metrics") or []),
                 "tools": tools_for(agent.get("preset"))}
        started = time.perf_counter()
        response = mcp_server.handle(message, state.layer, scope=scope)
        if isinstance(message, dict) and message.get("method") == "tools/call":
            params = message.get("params") or {}
            error = (response or {}).get("error")
            connections.log_call(
                state.layer.graph, agent_id, str(params.get("name") or ""),
                _call_summary(params.get("arguments") or {}),
                ok=error is None,
                error=error.get("message") if error else None,
                latency_ms=(time.perf_counter() - started) * 1000,
                metric=_call_metric(params, response))
        if response is None:
            return Response(status_code=202)
        return JSONResponse(content=response)

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
