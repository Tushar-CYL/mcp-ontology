"""REST API for the Context tool (``/api/ctx/{ontology}/...``).

  POST /api/ctx/{id}/build      question -> linked words, followed graph,
                                checked facts, the pack and the answer
  POST /api/ctx/{id}/pack       the Context Pack only (open format), for any AI
  POST /api/ctx/{id}/feedback   "this answer is wrong because ..." -> a note
                                on the ontology, so the next build uses it
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


def ai_client():
    """The configured model (offline when none). Tests replace this."""
    from agent.llm import EYQClient
    return EYQClient()


def register(app, platform, error) -> None:

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
        return guard(lambda: ctx.build(platform(request).layer, oid, body.question,
                                       budget_chars=body.budget_chars, client=ai_client()))

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
