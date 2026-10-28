"""Build the knowledge graph from staging.

Thin wrapper: all the work is in sql/<engine>/build.sql, run statement by
statement with timings so the expensive steps are visible. Those numbers are
the baseline the Postgres port gets compared against.

Usage:
    python graph/build.py
    python graph/build.py --facts        # also build the metric fact tables
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import connect  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", action="store_true",
                    help="also run facts.sql (metric time-series tables)")
    ap.add_argument("--queries", action="store_true", default=True,
                    help="(re)define the query macros")
    args = ap.parse_args()

    with connect() as db:
        d = db.sql_dir()
        total = time.monotonic()

        print(f"building graph ({db.engine})")
        db.script(d / "build.sql", echo=True)

        if args.facts and (d / "facts.sql").exists():
            print("\nbuilding fact tables")
            db.script(d / "facts.sql", echo=True)

        if args.queries and (d / "queries.sql").exists():
            print("\ndefining query macros")
            db.script(d / "queries.sql")

        print(f"\ntotal {time.monotonic() - total:,.1f}s\n")

        print(f"{'kind':<9} {'name':<22} {'provenance':<10} {'rows':>12}")
        print("-" * 58)
        for kind, name, prov, n in db.query("SELECT * FROM graph_summary()"):
            if n:
                print(f"{kind:<9} {name:<22} {prov:<10} {n:>12,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
