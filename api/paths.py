"""Which local files the API may read.

The API takes file and folder paths from the caller (data sources, metadata
files). On a laptop that is the point: "load D:\\data\\sales". On a shared
server it would let anyone who can reach the API read any file the server
can (C:\\Windows\\win.ini, ~/.ssh/...), and sample values end up visible in
the ontology.

    STRATA_DATA_ROOTS=D:\\data;\\\\share\\finance

When set (separated by ; or the OS path separator), only paths inside those
folders are accepted; database URLs (postgres://...) are not file reads and
are unaffected. When unset, every local path is allowed, as before.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

URL = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)


def allowed_roots() -> list[Path]:
    raw = os.environ.get("STRATA_DATA_ROOTS", "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in re.split(r"[;" + re.escape(os.pathsep) + r"]", raw) if p.strip()]
    return [Path(p).expanduser().resolve() for p in parts]


def check(path: str) -> None:
    """Raise PermissionError when `path` is a local file outside the roots."""
    roots = allowed_roots()
    if not roots or URL.match(str(path or "")):
        return
    target = Path(path).expanduser().resolve()
    for root in roots:
        if target == root or root in target.parents:
            return
    raise PermissionError(
        f"{path} is outside the folders this server may read (STRATA_DATA_ROOTS)")
