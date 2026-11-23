"""Review by exception: a person sees only what the data could not settle.

IoT data with a fake AI that makes two claims nothing in the data can prove
(`model` and `status_code` "point at another table" - no table holds those
values), so they need a person; everything else the data confirmed."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api import onto_routes
from api.server import create_app
from context import engine as ctx
from knowledge_graph import explore as kg
from ontology import registry as reg
from ontology import review as rv
from ontology import simple
from tests.integration.simple_fixtures import FakeAI, load, make_iot

LIES = {"model": "reference", "status_code": "reference"}


@pytest.fixture
def iot(tmp_path):
    layer = load(tmp_path, ["iot"])
    oid = simple.create_and_build(layer, "Sensors", ["iot"], client=FakeAI(lies=LIES))["ontology"]
    return layer, oid


def _field(view, column):
    return next(f for t in view["things"] for f in t["fields"] if f["column"] == column)


def test_only_what_the_data_could_not_settle_needs_a_person(iot):
    layer, oid = iot
    v = simple.view(layer.graph, oid)
    counts = v["summary"]["review"]
    assert counts["needs_you"] == 2
    # 14 fields + 2 links proved by the data
    assert counts["confirmed"] == 16 and counts["disagrees"] == 0
    assert _field(v, "model")["review"] == "needs_you"
    assert _field(v, "temp_c")["review"] == "confirmed"
    q = rv.queue(layer.graph, oid)
    unproven = [c for c in q["cards"] if c["why"] == "unproven"]
    assert {c["column"] for c in unproven} == {"model", "status_code"}
    # Evidence comes with every card, before the claim.
    card = unproven[0]
    assert list(card)[:7] == ["target", "kind", "thing", "title", "column", "why", "evidence"]
    assert card["evidence"]["proof"] == "no other table holds these values"
    assert card["claim"]["by"] == "ai"


def test_unproven_cards_come_first_then_spot_checks_ranked_by_impact(iot):
    layer, oid = iot
    q = rv.queue(layer.graph, oid)
    whys = [c["why"] for c in q["cards"]]
    assert whys == sorted(whys, key=lambda w: w != "unproven")
    unproven = [c for c in q["cards"] if c["why"] == "unproven"]
    impacts = [c["impact"] for c in unproven]
    assert impacts == sorted(impacts, reverse=True) and len(set(impacts)) == 2


def test_a_steady_spot_check_sample_of_confirmed_items(iot):
    layer, oid = iot
    v = simple.view(layer.graph, oid)
    spots = [f for t in v["things"] for f in t["fields"] if f["spot_check"]]
    spots += [lk for lk in v["links"] if lk["spot_check"]]
    assert len(spots) >= 1 and all(s["review"] == "confirmed" for s in spots)
    assert v["summary"]["review"]["spot_checks"] == len(spots)
    again = simple.view(layer.graph, oid)
    assert [f["key"] for t in again["things"] for f in t["fields"] if f["spot_check"]] == \
           [f["key"] for t in v["things"] for f in t["fields"] if f["spot_check"]]
    assert any(c["why"] == "spot_check" for c in rv.queue(layer.graph, oid)["cards"])


def test_approving_takes_it_off_the_queue_and_is_counted(iot):
    layer, oid = iot
    out = rv.decide(layer, oid, ["column:iot.devices.model"], "approved", by="ana")
    assert out["version"] is None                      # approving changes nothing anyone uses
    v = simple.view(layer.graph, oid)
    assert _field(v, "model")["review"] == "approved"
    assert v["summary"]["review"]["needs_you"] == 1
    assert out["stats"] == {"decisions": 1, "approved": 1, "rejected": 0, "acceptance_pct": 100,
                            "spot_checked": 0, "checks_wrong_pct": None}
    assert reg.audit(layer.graph, oid)[-1]["by"] == "ana"


def test_a_rejected_field_is_held_back_from_answers(iot):
    layer, oid = iot
    before = reg.versions(layer.graph, oid)[-1]["version"]
    out = rv.decide(layer, oid, ["column:iot.readings.status_code"], "rejected")
    assert out["version"] == before + 1               # every layer gets the change
    v = simple.view(layer.graph, oid)
    assert _field(v, "status_code")["review"] == "rejected"
    built = ctx.build(layer, oid, "status code of sensor readings")
    held = built["steps"]["facts"]["quarantined"]
    assert any("Status" in h["what"] and "rejected" in h["why"] for h in held)
    assert not any("status_code" in f["citation"] for f in built["steps"]["facts"]["kept"])


def test_a_rejected_link_stops_joining_records_everywhere(iot):
    layer, oid = iot
    link = simple.view(layer.graph, oid)["links"][0]
    rv.decide(layer, oid, [f"link:{link['key']}"], "rejected")
    v = simple.view(layer.graph, oid)
    assert link["key"] not in {lk["key"] for lk in v["links"]}
    assert [lk["key"] for lk in v["rejected_links"]] == [link["key"]]
    assert v["summary"]["links"] == 1 and v["summary"]["review"]["rejected"] == 1
    assert link["key"] not in {lk["key"] for lk in kg.model(layer, oid)["links"]}
    # Taking it back restores it.
    rv.undo(layer, oid, f"link:{link['key']}")
    assert link["key"] in {lk["key"] for lk in simple.view(layer.graph, oid)["links"]}


def test_approve_all_in_a_thing_leaves_spot_checks_alone(iot):
    layer, oid = iot
    out = rv.decide(layer, oid, [], "approved", thing="Sensor Reading")
    assert out["decided"] == ["column:iot.readings.status_code"]
    with pytest.raises(ValueError, match="nothing in 'Sensor Reading'"):
        rv.decide(layer, oid, [], "approved", thing="Sensor Reading")


def test_a_spot_check_that_fails_is_measured(iot):
    layer, oid = iot
    v = simple.view(layer.graph, oid)
    spot = next(f for t in v["things"] for f in t["fields"] if f["spot_check"])
    out = rv.decide(layer, oid, [f"column:{spot['key']}"], "rejected")
    assert out["stats"]["spot_checked"] == 1 and out["stats"]["checks_wrong_pct"] == 100


def test_a_decision_survives_a_rebuild_but_not_a_changed_claim(iot):
    layer, oid = iot
    rv.decide(layer, oid, ["column:iot.devices.model"], "approved")
    simple.build(layer, oid, client=FakeAI(lies=LIES))
    assert _field(simple.view(layer.graph, oid), "model")["review"] == "approved"
    # A later build says something else about the column (AI answers are
    # cached, so write the new claim directly): the old yes no longer applies.
    item = reg.get_item(layer.graph, oid, "meaning", "column:iot.devices.model")
    reg.put(layer.graph, oid, "meaning", "column:iot.devices.model",
            {**item["payload"], "role": "category", "meaning": "The device model."}, fact=True)
    assert _field(simple.view(layer.graph, oid), "model")["review"] != "approved"


def test_unknown_targets_and_bad_decisions_are_refused(iot):
    layer, oid = iot
    with pytest.raises(KeyError):
        rv.decide(layer, oid, ["column:nope"], "approved")
    with pytest.raises(ValueError):
        rv.decide(layer, oid, ["column:iot.devices.model"], "maybe")
    with pytest.raises(ValueError):
        rv.decide(layer, oid, [], "approved")
    with pytest.raises(KeyError):
        rv.undo(layer, oid, "column:iot.devices.model")


# ------------------------------------------------------------------- API
@pytest.fixture(scope="module")
def api(tmp_path_factory):
    root = tmp_path_factory.mktemp("review-api")
    fake = FakeAI(lies=LIES)
    original = onto_routes.ai_client
    onto_routes.ai_client = lambda: fake
    app = create_app(root / "graphs" / "g.duckdb", warm=False)
    with TestClient(app) as c:
        c.root = root
        c.iot = make_iot(root / "data")
        yield c
    onto_routes.ai_client = original


def test_review_through_the_api(api):
    import time
    job = api.post("/api/onto/build", json={"name": "Sensors", "paths": [
        {"path": str(api.iot), "name": "iot"}]}).json()
    for _ in range(600):
        state = api.get(f"/api/jobs/{job['job_id']}").json()
        if state["status"] != "running":
            break
        time.sleep(0.2)
    assert state["status"] == "done", state
    oid = state["result"]["ontology"]
    q = api.get(f"/api/onto/{oid}/review").json()
    assert q["counts"]["needs_you"] == 2
    target = next(c["target"] for c in q["cards"] if c["why"] == "unproven")
    r = api.post(f"/api/onto/{oid}/review", json={"targets": [target], "decision": "approved"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["counts"]["needs_you"] == 1
    assert body["ontology"]["summary"]["review"]["approved"] == 1
    assert api.post(f"/api/onto/{oid}/review", json={"targets": [target], "decision": "nah"}
                    ).status_code == 422
    assert api.post(f"/api/onto/{oid}/review", json={"targets": ["column:x"], "decision": "approved"}
                    ).status_code == 404
    assert api.post(f"/api/onto/{oid}/review/undo", json={"target": target}).json()["counts"]["needs_you"] == 2
    assert api.get("/api/onto/nope/review").status_code == 404


def test_spot_checks_end_once_the_sample_is_done(iot):
    """Live: approving the last spot check brought in a new one, every time,
    so the queue never emptied."""
    layer, oid = iot
    for _ in range(3):
        v = simple.view(layer.graph, oid)
        spots = [f for t in v["things"] for f in t["fields"] if f["spot_check"]]
        spots += [lk for lk in v["links"] if lk["spot_check"]]
        if not spots:
            break
        target = (f"column:{spots[0]['key']}" if "column" in spots[0] else f"link:{spots[0]['key']}")
        rv.decide(layer, oid, [target], "approved")
    assert simple.view(layer.graph, oid)["summary"]["review"]["spot_checks"] == 0
    assert not [c for c in rv.queue(layer.graph, oid)["cards"] if c["why"] == "spot_check"]
