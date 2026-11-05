"""Start Strata: the API and the web app, on one address.

    python run_server.py                  then open http://127.0.0.1:8000
    python run_server.py --port 8010      another port
    python run_server.py --no-ui          API only (e.g. while running `npm run dev`)
    python run_server.py --rebuild-ui     force a fresh build of the web app

The web app is a React build in frontend/dist. That folder is not in git, so
on a fresh clone (and after a `git pull` that changed the frontend) this
script builds it first with npm - `npm install` once, then `npm run build`.
It needs Node.js 18+; without it the API still starts and the home page says
what to install.

Frontend development: run this with --no-ui, and `npm run dev` in frontend/
(http://localhost:5173, which proxies /api here). Secrets stay in .env /
environment and never reach the browser.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
DIST_INDEX = FRONTEND / "dist" / "index.html"
# What a UI build depends on: if any is newer than the build, rebuild.
UI_INPUTS = ("src", "index.html", "package.json", "package-lock.json", "vite.config.ts",
             "tsconfig.json")


def load_env() -> None:
    """Minimal .env loader; existing environment always wins."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _newest_input() -> float:
    newest = 0.0
    for name in UI_INPUTS:
        path = FRONTEND / name
        if path.is_file():
            newest = max(newest, path.stat().st_mtime)
        elif path.is_dir():
            for f in path.rglob("*"):
                if f.is_file():
                    newest = max(newest, f.stat().st_mtime)
    return newest


def ui_needs_build() -> bool:
    if not DIST_INDEX.exists():
        return True
    return _newest_input() > DIST_INDEX.stat().st_mtime


def _npm(*args: str) -> None:
    npm = shutil.which("npm")                    # npm.cmd on Windows
    if npm is None:
        raise FileNotFoundError("npm")
    print(f"  > npm {' '.join(args)}", flush=True)
    subprocess.run([npm, *args], cwd=FRONTEND, check=True)


def build_ui(force: bool = False) -> bool:
    """Build frontend/dist when missing or out of date. True when a usable
    build exists afterwards."""
    if not force and not ui_needs_build():
        return True
    print("Building the web app (first start or frontend changed)...", flush=True)
    try:
        if not (FRONTEND / "node_modules").exists():
            _npm("install", "--no-audit", "--no-fund")
        _npm("run", "build")
        print("Web app built.", flush=True)
        return True
    except FileNotFoundError:
        print("\n  Node.js / npm was not found, so the web app cannot be built.\n"
              "  Install Node.js 18 or newer from https://nodejs.org, then run this again.\n"
              "  The API still starts.\n", flush=True)
    except subprocess.CalledProcessError as exc:
        print(f"\n  Building the web app failed (npm exit code {exc.returncode}).\n"
              "  Fix the error above, or run it yourself:  cd frontend && npm install && "
              "npm run build\n  The API still starts.\n", flush=True)
    return DIST_INDEX.exists()


def main(argv=None) -> int:
    load_env()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default=os.environ.get("MIDDLE_LAYER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("MIDDLE_LAYER_PORT", "8000")))
    parser.add_argument("--reload", action="store_true",
                        help="developer reload (not for production)")
    parser.add_argument("--no-ui", action="store_true",
                        help="do not build or serve the web app (API only)")
    parser.add_argument("--rebuild-ui", action="store_true",
                        help="rebuild the web app even if it looks up to date")
    args = parser.parse_args(argv)

    has_ui = False if args.no_ui else build_ui(force=args.rebuild_ui)
    if args.no_ui:
        os.environ["STRATA_NO_UI"] = "1"
    import uvicorn
    shown = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    print("\n" + "=" * 60, flush=True)
    if has_ui:
        print(f"  Strata is starting.  Open  http://{shown}:{args.port}", flush=True)
    else:
        print(f"  Strata API is starting on http://{shown}:{args.port}  (no web app)",
              flush=True)
        if args.no_ui:
            print("  For the web app run:  cd frontend && npm run dev  "
                  "-> http://localhost:5173", flush=True)
    print("=" * 60 + "\n", flush=True)
    uvicorn.run("api.server:app", host=args.host, port=args.port,
                reload=args.reload, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
