"""`strata bundle`: one zip another team unzips and starts, Python only.
The test unzips it somewhere else and proves the copy works on its own."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile

import strata
from strata.bundle import make_bundle
from tests.integration.test_semantic_model import make_amounts


def _run(cwd, code, env=None, timeout=600):
    e = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "STRATA_LAYERS")}
    e.update(env or {})
    return subprocess.run([sys.executable, "-c", code], cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, env=e)


def test_a_bundle_runs_on_its_own(tmp_path):
    db = make_amounts(tmp_path / "amounts.db")
    with strata.open(tmp_path / "work.duckdb") as s:
        oid = s.build("Shop", [s.connect(str(db), "shop")], use_ai=False)
        doc = s.contract(oid)
    zpath = make_bundle(tmp_path / "out" / "strata-semantic.zip", "semantic", ontology=doc)
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        z.extractall(tmp_path / "unzipped")
    root = tmp_path / "unzipped" / "strata-semantic"
    # What is inside: code, scripts, specs, the starting ontology; no data, no secrets.
    assert "strata-semantic/start.bat" in names and "strata-semantic/start.sh" in names
    assert "strata-semantic/models/shop.strata-model.json" in names
    assert "strata-semantic/docs/spec/strata-model.schema.json" in names
    assert not any(n.endswith((".duckdb", ".db", ".pyc")) or "/tests/" in n or n.endswith("/.env")
                   for n in names)
    assert "--layers ontology,semantic" in (root / "start.bat").read_text(encoding="utf-8")
    assert "Layers in this bundle: ontology, semantic" in (root / "BUNDLE.txt").read_text(encoding="utf-8")

    # 1. The command line of the copy (imports come from the copy, not this repo).
    r = _run(root, "import strata, sys; print(strata.__file__); "
                   "from strata.cli import main; sys.exit(main(['--db', 'x.duckdb', 'list']))")
    assert r.returncode == 0, r.stderr
    assert str(root) in r.stdout.splitlines()[0]

    # 2. The server of the copy, with only the chosen layers.
    code = (
        "from fastapi.testclient import TestClient\n"
        "from api.server import create_app\n"
        "import json\n"
        "with TestClient(create_app('reg.duckdb', warm=False)) as c:\n"
        "    print(json.dumps({'layers': c.get('/api/health').json()['layers'],\n"
        "                      'kg': c.get('/api/kg/x/overview').status_code}))\n")
    r = _run(root, code, env={"STRATA_LAYERS": "ontology,semantic"})
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out == {"layers": ["ontology", "semantic"], "kg": 404}

    # 3. The other team starts from our ontology, on their own copy of the data.
    theirs = make_amounts(tmp_path / "their.db")
    code = (
        "import strata, json\n"
        "with strata.open('their.duckdb') as s:\n"
        f"    oid = s.build('Ours on theirs', [s.connect(r'{theirs}', 'mine')],\n"
        "                  model='models/shop.strata-model.json')\n"
        "    print(json.dumps(sorted(t['name'] for t in s.ontology(oid)['things'])))\n")
    r = _run(root, code)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout.strip().splitlines()[-1]) == sorted(t["name"] for t in doc["things"])


def test_a_bundle_without_the_web_app_or_a_choice(tmp_path):
    zpath = make_bundle(tmp_path / "strata.zip", include_ui=False)
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        bat = z.read("strata/start.bat").decode()
    assert not any("/frontend/dist/" in n for n in names)
    assert "--layers" not in bat                       # every layer on
