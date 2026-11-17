"""REST API for the agents of an ontology (agent/onto_agents.py).

  GET    /api/onto-agents/{ontology}         built-ins (from the data) + your agents
  POST   /api/onto-agents/{ontology}         create your own agent
  GET    /api/oagents/{id}                   one agent
  PUT    /api/oagents/{id}                   change your agent (403 for a built-in)
  DELETE /api/oagents/{id}                   delete your agent (403 for a built-in)
  POST   /api/oagents/{id}/copy              a copy you can change
  POST   /api/oagents/{id}/ask               ask it one question
  POST   /api/onto-agents/{ontology}/try     try an agent before saving it
  GET    /api/oagents/{id}/connection        MCP set-up for Claude, Cursor, curl
Keys and usage reuse /api/agents/{id}/keys and /usage.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from pydantic import BaseModel, Field

from agent import onto_agents as oa


class OntoAgentBody(BaseModel):
    name: str | None = Field(None, max_length=80)
    kind: str | None = None
    job: str | None = Field(None, max_length=2000)
    instructions: str | None = Field(None, max_length=2000)
    scope: dict[str, list[str]] | None = None
    examples: list[Any] | None = None


class CopyBody(BaseModel):
    name: str | None = Field(None, max_length=80)


class QuestionBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class TryBody(OntoAgentBody):
    question: str = Field(..., min_length=1, max_length=1000)


def ai_client():
    from agent.llm import EYQClient
    return EYQClient()


def connection(agent: dict, base: str) -> dict:
    """Copy-paste MCP set-up for this agent (no secret in it)."""
    mcp = f"{base}/mcp"
    server = "strata-" + "".join(c if c.isalnum() else "-" for c in agent["name"].lower()).strip("-")
    tool = agent["tools"][0] if agent["tools"] else "get_ontology"
    example = agent["examples"][0]["text"] if agent["examples"] else "What data do we have?"
    args = {"ontology": agent["ontology"], "question": example} if tool in (
        "context_for_question", "ask_question") else {"ontology": agent["ontology"]}
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": args}})
    return {
        "mcp_url": mcp, "tools": agent["tools"],
        "claude_code": f'claude mcp add --transport http {server} {mcp} --header "Authorization: Bearer <YOUR_KEY>"',
        "claude_desktop": {"mcpServers": {server: {"command": "npx", "args": [
            "-y", "mcp-remote", mcp, "--header", "Authorization: Bearer <YOUR_KEY>"]}}},
        "cursor": {"mcpServers": {server: {"url": mcp, "headers": {"Authorization": "Bearer <YOUR_KEY>"}}}},
        "curl": f"curl -s {mcp} -H \"Authorization: Bearer <YOUR_KEY>\" -H \"Content-Type: application/json\" -d '{body}'",
    }


def register(app, platform, error) -> None:

    def guard(fn):
        try:
            return fn()
        except oa.ReadOnly as exc:
            raise error(403, "ReadOnly", str(exc)) from exc
        except KeyError as exc:
            raise error(404, "NotFound", str(exc).strip("'\"")) from exc
        except ValueError as exc:
            raise error(400, "AgentError", str(exc)) from exc

    def payload(body: BaseModel) -> dict:
        return {k: v for k, v in body.model_dump().items() if v is not None and k != "question"}

    @app.get("/api/onto-agents/{oid}")
    def onto_agents_list(oid: str, request: Request):
        return guard(lambda: oa.listing(platform(request).layer, oid))

    @app.post("/api/onto-agents/{oid}")
    def onto_agents_create(oid: str, request: Request, body: OntoAgentBody):
        return guard(lambda: oa.create(platform(request).layer, oid, payload(body)))

    @app.post("/api/onto-agents/{oid}/try")
    def onto_agents_try(oid: str, request: Request, body: TryBody):
        """Try an agent as it is being written, before it is saved."""
        from agent import onto_runner
        layer = platform(request).layer

        def run():
            clean = oa._clean(layer, oid, payload(body))
            agent = {"id": "draft", "ontology": oid, "name": clean["name"], "kind": clean["kind"],
                     "status": "active", **clean["config"]}
            return onto_runner.run(layer, agent, body.question, client=ai_client())
        return guard(run)

    @app.get("/api/oagents/{agent_id}")
    def oagent_get(agent_id: str, request: Request):
        return guard(lambda: oa.get(platform(request).layer.graph, agent_id))

    @app.put("/api/oagents/{agent_id}")
    def oagent_put(agent_id: str, request: Request, body: OntoAgentBody):
        return guard(lambda: oa.update(platform(request).layer, agent_id, payload(body)))

    @app.delete("/api/oagents/{agent_id}")
    def oagent_delete(agent_id: str, request: Request):
        guard(lambda: oa.delete(platform(request).layer, agent_id))
        return {"deleted": agent_id}

    @app.post("/api/oagents/{agent_id}/copy")
    def oagent_copy(agent_id: str, request: Request, body: CopyBody):
        return guard(lambda: oa.copy(platform(request).layer, agent_id, body.name))

    @app.post("/api/oagents/{agent_id}/ask")
    def oagent_ask(agent_id: str, request: Request, body: QuestionBody):
        from agent import onto_runner
        layer = platform(request).layer
        return guard(lambda: onto_runner.run(layer, oa.get(layer.graph, agent_id), body.question,
                                             client=ai_client()))

    @app.get("/api/oagents/{agent_id}/connection")
    def oagent_connection(agent_id: str, request: Request):
        agent = guard(lambda: oa.get(platform(request).layer.graph, agent_id))
        return connection(agent, str(request.base_url).rstrip("/"))
