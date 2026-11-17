"""Strata outside the web app: the Python library and the `strata` command,
each layer on its own, in a fresh process that knows only the registry file."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys

import pytest

import strata
from strata import cli
from tests.integration.test_contract import MINE
from tests.integration.test_semantic_model import make_amounts


@pytest.fixture()
def data(tmp_path):
    return make_amounts(tmp_path / "amounts.db"), tmp_path


def test_the_library_runs_every_layer(data):
    db, tmp = data
    with strata.open(tmp / "work.duckdb") as s:
        src = s.connect(str(db), "shop")
        oid = s.build("Shop", [src], use_ai=False)
        assert s.ontology(oid)["things"]
        assert s.contract(oid)["spec"] == "strata.model/v1"
        assert s.search(oid, "GB")
        names = {m["name"] for m in s.metrics(oid)}
        assert "total_gross_amount" in names
        s.certify(oid, "total_gross_amount", owner="Finance")
        assert "metric_total_gross_amount" in s.export_metrics(oid, "sql")
        pack = s.context(oid, "total Gross Amount by Status")
        assert pack["spec"] == "strata.context/v1" and pack["metric"]["name"] == "total_gross_amount"


def test_a_new_process_reopens_the_sources_it_needs(data):
    """The registry remembers where the data is; the next run needs no connect."""
    db, tmp = data
    with strata.open(tmp / "work.duckdb") as s:
        oid = s.build("Shop", [s.connect(str(db), "shop")], use_ai=False)
    with strata.open(tmp / "work.duckdb") as s:
        assert s.search(oid, "GB")
        want = sqlite3.connect(db).execute("select sum(gross_amount) from orders").fetchone()[0]
        assert abs(s.metric(oid, "total_gross_amount")["rows"][0][0] - want) < 0.01


def test_use_your_ontology_with_the_library(data):
    db, tmp = data
    model = tmp / "mine.json"
    model.write_text(json.dumps(MINE), encoding="utf-8")
    with strata.open(tmp / "work.duckdb") as s:
        oid = s.build("Mine", [s.connect(str(db), "shop")], model=str(model))
        assert sorted(t["name"] for t in s.ontology(oid)["things"]) == ["Client", "Sale"]


def _cli(tmp, *args):
    return cli.main(["--db", str(tmp / "cli.duckdb"), *args])


def test_the_command_line_end_to_end(data, capsys):
    db, tmp = data
    assert _cli(tmp, "connect", str(db), "--name", "shop") == 0
    assert capsys.readouterr().out.strip() == "shop"
    assert _cli(tmp, "build", "Shop", "--source", "shop", "--no-ai") == 0
    assert "confirmed by the data" in capsys.readouterr().out
    assert _cli(tmp, "export", "ontology", "shop", "-o", str(tmp / "m.json")) == 0
    assert json.loads((tmp / "m.json").read_text(encoding="utf-8"))["spec"] == "strata.model/v1"
    assert _cli(tmp, "export", "graph", "shop", "--format", "rdf", "-o", str(tmp / "g.nt")) == 0
    assert (tmp / "g.nt").stat().st_size > 1000
    assert _cli(tmp, "metrics", "shop") == 0
    assert "total_gross_amount" in capsys.readouterr().out
    assert _cli(tmp, "certify", "shop", "total_gross_amount", "--owner", "Finance") == 0
    assert _cli(tmp, "export", "semantic", "shop", "--format", "metricflow", "-o", str(tmp / "mf.yml")) == 0
    assert "semantic_models" in (tmp / "mf.yml").read_text(encoding="utf-8")
    capsys.readouterr()
    assert _cli(tmp, "context", "shop", "total Gross Amount by Status") == 0
    assert json.loads(capsys.readouterr().out)["spec"] == "strata.context/v1"
    assert _cli(tmp, "health", "shop") == 0
    out = capsys.readouterr().out
    assert "ontology" in out and "semantic" in out and "ready" in out


def test_the_command_line_says_what_is_wrong(data, capsys):
    _, tmp = data
    assert _cli(tmp, "metrics", "nope") == 2
    assert "nope" in capsys.readouterr().err


def test_python_dash_m_strata_runs(data):
    _, tmp = data
    r = subprocess.run([sys.executable, "-m", "strata", "--db", str(tmp / "x.duckdb"), "list"],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {"ontologies": [], "sources": []}
