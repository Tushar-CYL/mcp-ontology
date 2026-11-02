"""Start the production API and (when built) the TypeScript UI.

    python run_server.py --port 8000

The frontend is served from frontend/dist by the same FastAPI app when that
build exists; during frontend development run `npm run dev` in frontend/ and it
proxies /api to this server. Secrets stay in .env / environment and never reach
the browser.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_env() -> None:
    """Minimal .env loader; existing environment always wins."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main(argv=None) -> int:
    load_env()
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get(
        "MIDDLE_LAYER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get(
        "MIDDLE_LAYER_PORT", "8000")))
    parser.add_argument("--reload", action="store_true",
                        help="developer reload (not for production)")
    args = parser.parse_args(argv)
    uvicorn.run("api.server:app", host=args.host, port=args.port,
                reload=args.reload, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
