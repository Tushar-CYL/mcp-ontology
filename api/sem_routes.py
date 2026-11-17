"""REST API for the Semantic tool (``/api/sem/{ontology}/...``).

  GET  /api/sem/{id}                       metrics (value, trend, status), decisions
  GET  /api/sem/{id}/metric/{name}?by=     one metric: breakdown, receipt, verified Qs
  POST /api/sem/{id}/metric/{name}/certify {owner, note}
  POST /api/sem/{id}/metric/{name}/retire
  POST /api/sem/{id}/metric/{name}/synonym {word}
  POST /api/sem/{id}/metric/{name}/verified {question, by}
  POST /api/sem/{id}/decide                {word, metric}
  POST /api/sem/{id}/words                 {text}  -> a checked, proposed metric
"""

from __future__ import annotations

from fastapi import Request
from pydantic import BaseModel, Field

from semantic import model as sem


class CertifyRequest(BaseModel):
    owner: str = Field("", max_length=120)
    note: str = Field("", max_length=500)


class SynonymRequest(BaseModel):
    word: str = Field(..., min_length=1, max_length=60)


class VerifiedRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    by: str | None = Field(None, max_length=200)


class DecideRequest(BaseModel):
    word: str = Field(..., min_length=1, max_length=60)
    metric: str = Field(..., min_length=1, max_length=200)


class WordsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)


def ai_client():
    """The configured model (offline when none). Tests replace this."""
    from agent.llm import EYQClient
    return EYQClient()


def register(app, platform, error) -> None:

    def guard(fn):
        try:
            return fn()
        except sem.SemanticError as exc:
            raise error(400, "SemanticError", str(exc)) from exc
        except KeyError as exc:
            raise error(404, "NotFound", str(exc).strip("'\"")) from exc
        except ValueError as exc:
            raise error(400, "BadRequest", str(exc)) from exc

    def layer(request: Request):
        return platform(request).layer

    @app.get("/api/sem/{oid}/export")
    def sem_export(oid: str, request: Request, format: str = "sql", status: str = "certified"):  # noqa: A002
        """The metrics in another system's format: `sql` (CREATE VIEW per metric,
        over the source tables by name) or `metricflow` (dbt semantic models)."""
        from fastapi.responses import Response
        from semantic import export
        if format not in ("sql", "metricflow") or status not in ("certified", "all"):
            raise error(400, "BadRequest", "format is sql or metricflow; status is certified or all")
        from ontology import registry as reg
        guard(lambda: reg.get(layer(request).graph, oid))
        if format == "sql":
            text = guard(lambda: export.sql_views(layer(request), oid, status=status))
            return Response(text, media_type="application/sql", headers={
                "Content-Disposition": f'attachment; filename="{oid}-metrics.sql"'})
        text = guard(lambda: export.metricflow(layer(request), oid, status=status))
        return Response(text, media_type="application/yaml", headers={
            "Content-Disposition": f'attachment; filename="{oid}-metricflow.yml"'})

    @app.get("/api/sem/{oid}")
    def sem_overview(oid: str, request: Request):
        return guard(lambda: sem.overview(layer(request), oid))

    @app.get("/api/sem/{oid}/metric/{name}")
    def sem_detail(oid: str, name: str, request: Request, by: str | None = None):
        return guard(lambda: sem.detail(layer(request), oid, name, by=by))

    @app.post("/api/sem/{oid}/metric/{name}/certify")
    def sem_certify(oid: str, name: str, request: Request, body: CertifyRequest):
        return guard(lambda: sem.certify(layer(request), oid, name, owner=body.owner, note=body.note))

    @app.post("/api/sem/{oid}/metric/{name}/retire")
    def sem_retire(oid: str, name: str, request: Request):
        return guard(lambda: sem.retire(layer(request), oid, name))

    @app.post("/api/sem/{oid}/metric/{name}/synonym")
    def sem_synonym(oid: str, name: str, request: Request, body: SynonymRequest):
        return {"synonyms": guard(lambda: sem.add_synonym(layer(request), oid, name, body.word))}

    @app.post("/api/sem/{oid}/metric/{name}/verified")
    def sem_verified(oid: str, name: str, request: Request, body: VerifiedRequest):
        return guard(lambda: sem.add_verified(layer(request), oid, body.question, name, by=body.by))

    @app.post("/api/sem/{oid}/decide")
    def sem_decide(oid: str, request: Request, body: DecideRequest):
        return guard(lambda: sem.decide(layer(request), oid, body.word, body.metric))

    @app.post("/api/sem/{oid}/words")
    def sem_words(oid: str, request: Request, body: WordsRequest):
        return guard(lambda: sem.from_words(layer(request), oid, body.text, ai_client()))
