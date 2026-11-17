"""A ready-to-copy Strata for another team: one zip, Python only, no Docker.

    strata bundle -o strata-semantic.zip --layers semantic --ontology shop

The zip holds the code, the built web app, the open specs, an optional
ontology as a Strata Model (so the other team starts from your structure on
their own data) and two start scripts. On their machine:

    unzip strata-semantic.zip && cd strata-semantic
    start.bat            (Windows)     or     ./start.sh   (macOS / Linux)

The script makes a private Python environment (.venv) the first time,
installs the requirements into it, and starts Strata with only the chosen
layers on http://127.0.0.1:8000. Nothing is installed system-wide, and the
data never moves: they connect their own files or database from the app.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE = ("agent", "api", "context", "knowledge_graph", "ontology", "review", "semantic", "strata")
FILES = ("run_server.py", "requirements.txt", "pyproject.toml", "README.txt", ".env.example")
SKIP_DIRS = {"__pycache__", ".pytest_cache", "node_modules"}


def _start_bat(layers: str) -> str:
    flag = f" --layers {layers}" if layers else ""
    return "\r\n".join([
        "@echo off",
        "rem Starts Strata. The first run creates .venv and installs the requirements.",
        "cd /d \"%~dp0\"",
        "where python >nul 2>nul || (echo Install Python 3.10 or newer from https://www.python.org/downloads/ & pause & exit /b 1)",
        "if not exist .venv\\Scripts\\python.exe (",
        "  echo Creating a private Python environment in .venv ...",
        "  python -m venv .venv || (pause & exit /b 1)",
        "  .venv\\Scripts\\python.exe -m pip install --upgrade pip",
        "  .venv\\Scripts\\python.exe -m pip install -r requirements.txt || (pause & exit /b 1)",
        ")",
        "if not exist .env if exist .env.example copy .env.example .env >nul",
        f".venv\\Scripts\\python.exe run_server.py --no-build{flag} %*",
        "pause", ""])


def _start_sh(layers: str) -> str:
    flag = f" --layers {layers}" if layers else ""
    return "\n".join([
        "#!/usr/bin/env sh",
        "# Starts Strata. The first run creates .venv and installs the requirements.",
        "set -e",
        "cd \"$(dirname \"$0\")\"",
        "PY=$(command -v python3 || command -v python) || { echo 'Install Python 3.10 or newer'; exit 1; }",
        "if [ ! -x .venv/bin/python ]; then",
        "  echo 'Creating a private Python environment in .venv ...'",
        "  \"$PY\" -m venv .venv",
        "  .venv/bin/python -m pip install --upgrade pip",
        "  .venv/bin/python -m pip install -r requirements.txt",
        "fi",
        "[ -f .env ] || { [ -f .env.example ] && cp .env.example .env; } || true",
        f"exec .venv/bin/python run_server.py --no-build{flag} \"$@\"", ""])


def _readme(layers: tuple[str, ...], ontology: dict | None, has_ui: bool) -> str:
    lines = [
        "STRATA - READY-TO-RUN BUNDLE",
        "============================",
        "",
        f"Layers in this bundle: {', '.join(layers)} (the ontology is always on).",
        "",
        "START",
        "  Windows:        double-click start.bat",
        "  macOS / Linux:  ./start.sh",
        "  Then open http://127.0.0.1:8000" + ("" if has_ui else "  (API and MCP only: no web app in this bundle)"),
        "",
        "  The first start makes a private Python environment (.venv) and installs",
        "  the requirements (a few minutes, needs internet or a pip mirror). Nothing",
        "  is installed system-wide. Needs Python 3.10 or newer.",
        "",
        "AI (optional): open .env and fill EYQ_INCUBATOR_ENDPOINT, EYQ_INCUBATOR_KEY.",
        "",
        "YOUR DATA stays where it is: in the app, Data sources -> Connect a folder,",
        "a .db file or a database URL (postgres://, mssql://, snowflake://, ...).",
        "",
        "COMMAND LINE (same layers, no web app):",
        "  .venv\\Scripts\\python -m strata --help        (Windows)",
        "  .venv/bin/python -m strata --help             (macOS / Linux)",
        "",
        "OPEN FORMATS (docs/spec/):",
        "  strata-model.schema.json   an ontology as JSON (import / export)",
        "  context-pack.schema.json   the evidence pack any AI can answer from",
    ]
    if ontology:
        lines += [
            "",
            "STARTING ONTOLOGY",
            f"  models/{ontology['file']} is the ontology \"{ontology['name']}\"",
            "  ({things} things, {links} links). To use it on your own copy of the data:".format(**ontology),
            "  Ontology -> New -> \"Use my ontology exactly\" -> add this file, or",
            f"  python -m strata build \"{ontology['name']}\" --path <your data> --model models/{ontology['file']}",
            "  Tables are matched by name; whatever does not match is listed, never guessed.",
        ]
    return "\n".join(lines) + "\n"


def make_bundle(dest: str | Path, layers: str = "", ontology: dict | None = None,
                include_ui: bool = True) -> Path:
    """Write the zip. `ontology` is a Strata Model document to include."""
    from api import layers as api_layers
    chosen = api_layers.parse(layers)
    layer_arg = "" if chosen == api_layers.LAYERS else ",".join(chosen)
    dest = Path(dest)
    name = dest.stem
    dist = ROOT / "frontend" / "dist"
    has_ui = include_ui and (dist / "index.html").exists()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        def add(path: Path, arc: str) -> None:
            z.write(path, f"{name}/{arc}")

        for pkg in CODE:
            for f in sorted((ROOT / pkg).rglob("*")):
                if f.is_file() and not (SKIP_DIRS & set(f.relative_to(ROOT).parts)) \
                        and f.suffix not in (".pyc",):
                    add(f, f.relative_to(ROOT).as_posix())
        for fname in FILES:
            if (ROOT / fname).exists():
                add(ROOT / fname, fname)
        for f in sorted((ROOT / "docs" / "spec").glob("*.json")):
            add(f, f"docs/spec/{f.name}")
        if has_ui:
            for f in sorted(dist.rglob("*")):
                if f.is_file():
                    add(f, "frontend/dist/" + f.relative_to(dist).as_posix())
        info = None
        if ontology:
            fname = f"{ontology.get('id') or 'ontology'}.strata-model.json"
            z.writestr(f"{name}/models/{fname}", json.dumps(ontology, indent=2, ensure_ascii=False))
            info = {"file": fname, "name": ontology.get("name"), "things": len(ontology["things"]),
                    "links": len(ontology.get("links") or [])}
        z.writestr(f"{name}/start.bat", _start_bat(layer_arg))
        sh = zipfile.ZipInfo(f"{name}/start.sh")
        sh.external_attr = 0o755 << 16                 # executable after unzip
        z.writestr(sh, _start_sh(layer_arg))
        z.writestr(f"{name}/BUNDLE.txt", _readme(chosen, info, has_ui))
    return dest
