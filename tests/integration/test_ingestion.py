"""Loading big data: fast, honest, and never freezing the API.

Measured on SAP SALT (10.4M records): the graph build took 104 s, but the
server held one lock for the whole build, so every other request (including
the health check) waited and the UI reported "API unreachable". The source
also carried ML split copies (_train/_test) and an exact duplicate table that
doubled the graph, and guessed links that matched almost nothing.
"""

from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from api.service import MiddleLayer
from ontology.connect import connect
from ontology.copies import hide_copies
from tests.integration.test_autopilot import _write_salt_like


def _add_duplicate_and_bad_link(folder):
    # An exact copy of the documents table under another name.
    docs = (folder / "sales_documents.csv").read_text(encoding="utf-8")
    (folder / "documents_export.csv").write_text(docs, encoding="utf-8")
    # A column named after a kind of thing ("customer") whose values match no
    # customer: the same pattern that produced SALT's bad links.
    rows = ["note_id,customer,text"]
    rows += [f"N{i},ZZ{i:05d},hello" for i in range(200)]
    (folder / "notes.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ copies
def test_ml_splits_and_exact_duplicates_are_hidden(tmp_path):
    folder = tmp_path / "salt"
    _write_salt_like(folder)
    _add_duplicate_and_bad_link(folder)
    schema = connect(str(folder))
    hidden = hide_copies(schema)
    assert "sales_documents_train" in hidden
    assert ("documents_export" in hidden) != ("sales_documents" in hidden)
    visible = {t.name for t in schema.tables if not t.hidden}
    assert "sales_document_items" in visible and "customers" in visible
    assert any("copies" in w.lower() for w in schema.warnings)


def test_a_dataset_of_only_splits_keeps_them(tmp_path):
    folder = tmp_path / "ml"
    folder.mkdir()
    (folder / "data_train.csv").write_text("a,b\n1,x\n2,y\n", encoding="utf-8")
    (folder / "data_test.csv").write_text("a,b\n3,z\n", encoding="utf-8")
    schema = connect(str(folder))
    hide_copies(schema)
    assert any(not t.hidden for t in schema.tables)


def test_hidden_copies_stay_queryable_but_leave_the_graph(tmp_path):
    folder = tmp_path / "salt"
    _write_salt_like(folder)
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    try:
        layer.add_source(str(folder), source="salt")
        bundle = layer._bundle("salt")
        tables = {c.table for c in bundle.onto.classes.values()}
        assert "sales_documents_train" not in tables
        from knowledge_graph.build import source_rows
        cols, rows = source_rows(layer.graph, bundle.schema,
                                 "sales_documents_train", limit=3, source="salt")
        assert rows                                   # still loaded
    finally:
        layer.close()


# ------------------------------------------------------- link verification
def test_guessed_links_that_do_not_match_the_data_are_dropped(tmp_path):
    folder = tmp_path / "salt"
    _write_salt_like(folder)
    _add_duplicate_and_bad_link(folder)
    layer = MiddleLayer(str(tmp_path / "v.duckdb"))
    try:
        summary = layer.add_source(str(folder), source="salt")
        bundle = layer._bundle("salt")
        notes = [r for r in bundle.onto.relations.values()
                 if r.domain.lower().startswith("note")]
        assert notes == [], [(r.name, r.domain, r.range) for r in notes]
        assert summary["rejected_links"]
        # Restart: the decision is remembered without rebuilding.
        layer2 = MiddleLayer(str(tmp_path / "v.duckdb"))
        layer.close()
        layer2.add_source(str(folder), source="salt")
        again = [r for r in layer2._bundle("salt").onto.relations.values()
                 if r.domain.lower().startswith("note")]
        assert again == []
        layer2.close()
    finally:
        try:
            layer.close()
        except Exception:                            # noqa: BLE001 - closed above
            pass


# --------------------------------------------------------- non-blocking build
def test_a_build_never_holds_the_shared_lock_for_long(tmp_path):
    """While a big build runs, other requests can take the lock at once."""
    folder = tmp_path / "big"
    folder.mkdir()
    rows = ["order_id,customer_id,region,amount,order_date"]
    rows += [f"O{i},C{i % 5000},R{i % 7},{i % 997},2024-0{1 + i % 9}-1{i % 9}"
             for i in range(300_000)]
    newline = chr(10)
    (folder / "orders.csv").write_text(newline.join(rows) + newline, encoding="utf-8")
    (folder / "customers.csv").write_text(
        "customer_id,segment" + newline
        + newline.join(f"C{i},S{i % 4}" for i in range(5000)) + newline,
        encoding="utf-8")
    layer = MiddleLayer(str(tmp_path / "nb.duckdb"))
    errors = []

    def run():
        try:
            layer.add_source(str(folder), source="big")
        except Exception as exc:                     # noqa: BLE001 - reported
            errors.append(exc)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    waits = []
    while worker.is_alive():
        t = time.monotonic()
        with layer.graph.lock:
            waits.append(time.monotonic() - t)
        time.sleep(0.05)
    worker.join()
    assert not errors, errors
    assert waits, "the build finished before it could be observed"
    assert max(waits) < 1.5, f"a reader waited {max(waits):.1f}s for the lock"
    assert layer.graph.one("SELECT count(*) FROM nodes WHERE source_id = 'big'") > 300_000
    layer.close()


# ------------------------------------------------------------ background jobs
@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "jobs.duckdb", warm=False)) as c:
        yield c


def _wait(client, job_id, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.2)
    raise AssertionError("job did not finish")


def test_background_load_reports_progress_and_result(client, tmp_path):
    folder = tmp_path / "salt"
    _write_salt_like(folder)
    started = client.post("/api/sources", json={
        "path": str(folder), "name": "salt", "background": True})
    assert started.status_code == 202, started.text
    job = _wait(client, started.json()["job_id"])
    assert job["status"] == "done", job
    assert job["result"]["id"] == "salt"
    assert job["steps"], "progress lines are reported"
    assert job["elapsed_s"] >= 0
    assert client.get("/api/sources").json()["sources"][0]["id"] == "salt"


def test_background_load_of_a_bad_path_fails_cleanly(client, tmp_path):
    started = client.post("/api/sources", json={
        "path": str(tmp_path / "missing"), "background": True})
    job = _wait(client, started.json()["job_id"])
    assert job["status"] == "failed"
    assert "not found" in job["error"].lower()


def test_unknown_job_is_404(client):
    assert client.get("/api/jobs/nope").status_code == 404


def test_health_answers_while_a_load_runs(client, tmp_path):
    folder = tmp_path / "salt"
    _write_salt_like(folder)
    started = client.post("/api/sources", json={
        "path": str(folder), "name": "salt", "background": True}).json()
    t = time.monotonic()
    assert client.get("/api/health").status_code == 200
    assert time.monotonic() - t < 2.0
    _wait(client, started["job_id"])


def test_the_foreground_load_still_works(client, tmp_path):
    folder = tmp_path / "salt"
    _write_salt_like(folder)
    response = client.post("/api/sources", json={"path": str(folder), "name": "salt"})
    assert response.status_code == 200
    assert response.json()["id"] == "salt"


def test_server_answers_while_sources_warm_in_the_background(tmp_path, monkeypatch):
    """Startup must not wait for every saved source to re-open (minutes)."""
    from api import server as server_mod
    started = threading.Event()

    def slow_warm(self):
        started.set()
        time.sleep(3)
        self.warm_done = True

    monkeypatch.setattr(server_mod.Platform, "warm", slow_warm)
    t = time.monotonic()
    with TestClient(create_app(tmp_path / "w.duckdb", warm=True)) as c:
        health = c.get("/api/health")
        assert health.status_code == 200
        assert time.monotonic() - t < 2.5
        assert started.wait(5)
        assert health.json()["warming"] is True
