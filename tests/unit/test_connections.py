"""Agent connections: API keys and the usage log.

A key is the only thing an external agent holds. It must be shown once,
stored only as a hash, be revocable, and every tool call made with it must
be recorded against the agent.
"""

from __future__ import annotations

import pytest

from agent import connections
from knowledge_graph.store import open_graph


@pytest.fixture
def graph(tmp_path):
    g = open_graph(str(tmp_path / "keys.duckdb"))
    yield g
    g.close()


def test_issue_returns_a_prefixed_secret_once(graph):
    issued = connections.issue_key(graph, "agent_1", label="claude desktop")
    assert issued["key"].startswith("strata_")
    assert len(issued["key"]) > 30
    assert issued["prefix"] == issued["key"][:12]
    assert issued["id"]


def test_the_secret_is_never_stored_in_plain_text(graph):
    issued = connections.issue_key(graph, "agent_1")
    dump = repr(graph.sql("SELECT * FROM agent_keys"))
    assert issued["key"] not in dump


def test_verify_maps_a_key_to_its_agent(graph):
    issued = connections.issue_key(graph, "agent_1")
    assert connections.verify_key(graph, issued["key"]) == "agent_1"


@pytest.mark.parametrize("bad", ["", "strata_nope", "Bearer x", None])
def test_verify_rejects_unknown_keys(graph, bad):
    connections.issue_key(graph, "agent_1")
    assert connections.verify_key(graph, bad) is None


def test_list_keys_hides_the_secret_and_tracks_use(graph):
    issued = connections.issue_key(graph, "agent_1", label="cursor")
    connections.verify_key(graph, issued["key"])
    keys = connections.list_keys(graph, "agent_1")
    assert len(keys) == 1
    item = keys[0]
    assert "key" not in item
    assert item["prefix"] == issued["prefix"]
    assert item["label"] == "cursor"
    assert item["revoked"] is False
    assert item["last_used_at"]


def test_revoked_keys_stop_working(graph):
    issued = connections.issue_key(graph, "agent_1")
    assert connections.revoke_key(graph, "agent_1", issued["id"]) is True
    assert connections.verify_key(graph, issued["key"]) is None
    assert connections.list_keys(graph, "agent_1")[0]["revoked"] is True


def test_revoke_cannot_touch_another_agents_key(graph):
    issued = connections.issue_key(graph, "agent_1")
    assert connections.revoke_key(graph, "agent_2", issued["id"]) is False
    assert connections.verify_key(graph, issued["key"]) == "agent_1"


def test_keys_are_listed_per_agent(graph):
    connections.issue_key(graph, "agent_1")
    connections.issue_key(graph, "agent_2")
    assert len(connections.list_keys(graph, "agent_1")) == 1


def test_usage_log_records_calls_newest_first(graph):
    connections.log_call(graph, "agent_1", "get_context",
                         "Why did revenue fall?", ok=True, latency_ms=12.5)
    connections.log_call(graph, "agent_1", "get_metric", "revenue",
                         ok=False, error="forbidden", latency_ms=1.0)
    connections.log_call(graph, "agent_2", "get_metric", "x", ok=True)
    rows = connections.usage(graph, "agent_1")
    assert [row["tool"] for row in rows] == ["get_metric", "get_context"]
    assert rows[0]["ok"] is False
    assert rows[0]["error"] == "forbidden"
    assert rows[1]["summary"] == "Why did revenue fall?"


def test_usage_summary_is_truncated(graph):
    connections.log_call(graph, "agent_1", "get_context", "x" * 5000, ok=True)
    assert len(connections.usage(graph, "agent_1")[0]["summary"]) <= 300


def test_forget_agent_removes_its_keys_and_calls_only(graph):
    mine = connections.issue_key(graph, "agent_1")
    theirs = connections.issue_key(graph, "agent_2")
    connections.log_call(graph, "agent_1", "get_metric", "x", ok=True)
    connections.log_call(graph, "agent_2", "get_metric", "y", ok=True)
    connections.forget_agent(graph, "agent_1")
    assert connections.verify_key(graph, mine["key"]) is None
    assert connections.list_keys(graph, "agent_1") == []
    assert connections.usage(graph, "agent_1") == []
    assert connections.verify_key(graph, theirs["key"]) == "agent_2"
    assert len(connections.usage(graph, "agent_2")) == 1


def test_metric_usage_counts_calls_and_agents_per_metric(graph):
    connections.log_call(graph, "a1", "get_context", "q", ok=True, metric="revenue")
    connections.log_call(graph, "a1", "get_metric", "revenue", ok=True, metric="revenue")
    connections.log_call(graph, "a2", "evaluate_metric", "revenue", ok=True, metric="revenue")
    connections.log_call(graph, "a2", "get_metric", "aov", ok=True,
                         metric="average_order_value")
    connections.log_call(graph, "a2", "get_metric", "refund_rate", ok=False,
                         error="forbidden", metric="refund_rate")
    connections.log_call(graph, "a2", "list_sources", "", ok=True)
    usage = {row["metric"]: row for row in connections.metric_usage(graph)}
    assert set(usage) == {"revenue", "average_order_value"}   # refused not counted
    assert usage["revenue"]["calls"] == 3
    assert usage["revenue"]["agents"] == 2
    assert usage["revenue"]["last_used_at"]
    assert list(usage)[0] == "revenue"                          # busiest first


def test_old_usage_tables_gain_the_metric_column(tmp_path):
    g = open_graph(str(tmp_path / "old.duckdb"))
    with g.lock:
        g.con.execute(
            "CREATE TABLE agent_calls (id TEXT PRIMARY KEY, agent_id TEXT NOT NULL,"
            " tool TEXT NOT NULL, summary TEXT, ok BOOLEAN NOT NULL, error TEXT,"
            " latency_ms DOUBLE, created_at TEXT NOT NULL, seq BIGINT NOT NULL)")
    connections.log_call(g, "a1", "get_metric", "revenue", ok=True, metric="revenue")
    assert connections.metric_usage(g)[0]["metric"] == "revenue"
    g.close()
