"""Readiness is cached per source.

Certification scans every node and edge; on a 12M-edge graph it takes about
two minutes. An agent calling check_readiness must not wait for that each
time, but a rebuilt source must never be reported from a stale result.
"""

from __future__ import annotations

import pytest

from agent import certification
from api.service import MiddleLayer


@pytest.fixture
def layer(tmp_path, monkeypatch):
    calls = []

    def fake_certify(layer, source):
        calls.append(source)
        return {"source": source, "status": "pass", "certified": True,
                "layers": [], "run": len(calls)}

    monkeypatch.setattr(certification, "certify_source", fake_certify)
    service = MiddleLayer(str(tmp_path / "cache.duckdb"))
    service._calls = calls
    yield service
    service.close()


def test_second_call_is_served_from_cache(layer):
    first = layer.readiness("shop")
    second = layer.readiness("shop")
    assert layer._calls == ["shop"]
    assert first["cached"] is False
    assert second["cached"] is True
    assert second["run"] == 1
    assert second["checked_at"] == first["checked_at"]


def test_sources_are_cached_separately(layer):
    layer.readiness("shop")
    layer.readiness("hr")
    assert layer._calls == ["shop", "hr"]


def test_refresh_forces_a_new_check(layer):
    layer.readiness("shop")
    fresh = layer.readiness("shop", refresh=True)
    assert layer._calls == ["shop", "shop"]
    assert fresh["cached"] is False


def test_an_expired_result_is_recomputed(layer):
    clock = [1000.0]
    layer._clock = lambda: clock[0]
    layer.readiness("shop", max_age=60)
    clock[0] += 61
    layer.readiness("shop", max_age=60)
    assert layer._calls == ["shop", "shop"]


def test_reloading_a_source_invalidates_its_result(layer):
    from types import SimpleNamespace as NS

    layer.readiness("shop")
    layer.readiness("hr")
    layer._remember(NS(source="shop", schema=None, onto=None))
    layer.readiness("shop")
    layer.readiness("hr")
    assert layer._calls == ["shop", "hr", "shop"]
