"""REST API for the Context tool (``/api/ctx/{ontology}/...``).

  POST /api/ctx/{id}/build      question -> linked words, followed graph,
                                checked facts, the pack and the answer
  POST /api/ctx/{id}/pack       the Context Pack only (open format), for any AI
  POST /api/ctx/{id}/feedback   "this answer is wrong because ..." -> a note
                                on the ontology, so the next build uses it
  GET  /api/ctx/{id}/checks     report check: numbers from real reports and the last scorecard
  POST /api/ctx/{id}/checks     add checks (JSON rows, or a CSV / Excel file)
  POST /api/ctx/{id}/checks/run ask every check (a job) and score it
  GET  /api/ctx/{id}/gaps       questions it could not answer, grouped, with a fix
"""

from __future__ import annotations

from fastapi import Request
from pydantic import BaseModel, Field

from context import engine as ctx
from knowledge_graph.explore import GraphError


class BuildRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    budget_chars: int = Field(ctx.BUDGET, ge=200, le=8000)


class FeedbackRequest(BaseModel):
    question: str = Field("", max_length=1000)
    text: str = Field(..., min_length=1, max_length=2000)


class CheckRow(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    expected: float | str | None = None
    row_label: str | None = Field(None, max_length=200)
    unit: str | None = Field(None, max_length=40)
    digits: int | None = Field(None, ge=1, le=12)
    refuse: bool = False
    phrasings: list[str] = Field(default_factory=list, max_length=4)
    source: str | None = Field(None, max_length=300)


class ChecksRequest(BaseModel):
    checks: list[CheckRow] = Field(default_factory=list, max_length=300)
    file_name: str | None = Field(None, max_length=200)
    file_content: str | None = Field(None, max_length=8_000_000)


def ai_client():
    """The configured model (offline when none). Tests replace this."""
    from agent.llm import EYQClient
    return EYQClient()


def register(app, platform, error) -> None:

    from context import report_check as rc

    def guard(fn):
        try:
            return fn()
        except (ctx.ContextError, GraphError, ValueError) as exc:
            raise error(400, "ContextError", str(exc)) from exc
        except KeyError as exc:
            raise error(404, "NotFound", str(exc).strip("'\"")) from exc

    @app.get("/api/ctx/{oid}/insights")
    def ctx_insights(oid: str, request: Request):
        from context.insights import insights
        return guard(lambda: insights(platform(request).layer, oid))

    @app.post("/api/ctx/{oid}/build")
    def ctx_build(oid: str, request: Request, body: BuildRequest):
        from context import gaps
        layer = platform(request).layer
        out = guard(lambda: ctx.build(layer, oid, body.question,
                                      budget_chars=body.budget_chars, client=ai_client()))
        out["gap"] = gaps.record(layer.graph, oid, out, source="context")
        return out

    @app.get("/api/ctx/{oid}/gaps")
    def ctx_gaps(oid: str, request: Request):
        """Questions Strata could not answer, grouped, with a suggested fix."""
        from context import gaps
        return guard(lambda: gaps.groups(platform(request).layer.graph, oid))

    @app.delete("/api/ctx/{oid}/gaps")
    def ctx_gaps_dismiss(oid: str, key: str, request: Request):
        from context import gaps
        return guard(lambda: gaps.dismiss(platform(request).layer.graph, oid, key))

    @app.post("/api/ctx/{oid}/pack")
    def ctx_pack(oid: str, request: Request, body: BuildRequest):
        """Only the Context Pack (open format), no AI answer: for your own model."""
        out = guard(lambda: ctx.build(platform(request).layer, oid, body.question,
                                      budget_chars=body.budget_chars, client=None))
        return ctx.to_pack(out)

    @app.post("/api/ctx/{oid}/feedback")
    def ctx_feedback(oid: str, request: Request, body: FeedbackRequest):
        from ontology import simple
        text = body.text.strip()
        if body.question.strip():
            text = f"{text} (about the question: {body.question.strip()})"
        out = guard(lambda: simple.add_context(platform(request).layer, oid, text,
                                               client=ai_client(), by="feedback"))
        return {"saved": True, "changes": out.get("changes", []), "reply": out.get("reply", "")}

    @app.get("/api/ctx/{oid}/checks")
    def ctx_checks(oid: str, request: Request):
        return guard(lambda: rc.overview(platform(request).layer.graph, oid))

    @app.post("/api/ctx/{oid}/checks")
    def ctx_checks_add(oid: str, request: Request, body: ChecksRequest):
        graph = platform(request).layer.graph
        rows = [c.model_dump() for c in body.checks]
        if body.file_content:
            rows += guard(lambda: rc.parse_file(body.file_name or "checks.csv", body.file_content))
        guard(lambda: rc.add(graph, oid, rows))
        return guard(lambda: rc.overview(graph, oid))

    @app.delete("/api/ctx/{oid}/checks/{check_id}")
    def ctx_checks_remove(oid: str, check_id: str, request: Request):
        graph = platform(request).layer.graph
        guard(lambda: rc.remove(graph, oid, check_id))
        return guard(lambda: rc.overview(graph, oid))

    @app.post("/api/ctx/{oid}/checks/run")
    def ctx_checks_run(oid: str, request: Request):
        from fastapi.responses import JSONResponse
        state = platform(request)
        if not guard(lambda: rc.checks(state.layer.graph, oid)):
            raise error(400, "ContextError", "add a check first: a number from one of your reports")
        job_id = state.start_job(lambda say: rc.run(state.layer, oid, client=ai_client(), progress=say),
                                 label=f"report check {oid}")
        return JSONResponse(status_code=202, content={"job_id": job_id, "status": "running"})
