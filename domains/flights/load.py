r"""Load the flights files into staging. DuckDB reads; Python only unzips.

Same division of labour as the other domain: Python hands the engine a path
and never sees a row. DuckDB parses on every core and quarantines malformed
lines into a durable table instead of aborting, so "how many rows were bad"
stays a number we can report.

Two awkward bits of the source, both handled here rather than hidden:

  OpenFlights writes a literal \N for "no value" - two characters, not SQL
  NULL - and quotes inconsistently. We load it raw and let the validator
  count what is missing.

  The BTS CSV has 110 columns and a trailing comma on every line, which
  makes naive readers see a phantom 111th field. We name the 16 columns we
  want and let DuckDB ignore the rest.

Usage:
    python domains/flights/load.py --all
    python domains/flights/load.py --table flights
    python domains/flights/load.py --all --force
"""

from __future__ import annotations

import argparse
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from db import connect  # noqa: E402

RAW = ROOT / "data" / "raw" / "flights"
TMP = ROOT / "data" / "tmp"

# The 16 BTS columns we keep, mapped from their source names. The file has
# 110; carrying the rest would cost about four times the space for fields
# nothing reads.
BTS_COLUMNS = {
    "flight_date": "FlightDate",
    "carrier": "Reporting_Airline",
    "flight_number": "Flight_Number_Reporting_Airline",
    "tail_number": "Tail_Number",
    "origin": "Origin",
    "origin_city": "OriginCityName",
    "dest": "Dest",
    "dest_city": "DestCityName",
    "sched_dep": "CRSDepTime",
    "dep_delay": "DepDelay",
    "arr_delay": "ArrDelay",
    "cancelled": "Cancelled",
    "cancel_code": "CancellationCode",
    "diverted": "Diverted",
    "air_time": "AirTime",
    "distance": "Distance",
}

STATIC = {
    "airports": ("stg_airports", 14),
    "airlines": ("stg_airlines", 8),
    "routes":   ("stg_routes", 9),
}


def already(db, name: str) -> bool:
    return bool(db.one("SELECT count(*) FROM ingest_log WHERE src_file = ?",
                       [name]))


def record(db, name: str, table: str, rows: int, rejected: int,
           size: int, secs: float) -> None:
    db.execute("DELETE FROM ingest_log WHERE src_file = ?", [name])
    db.execute(
        "INSERT INTO ingest_log(src_file, table_name, rows_loaded, "
        "rows_rejected, bytes_read, seconds) VALUES (?,?,?,?,?,?)",
        [name, table, rows, rejected, size, round(secs, 1)])


def persist_rejects(db, src: str, table: str) -> int:
    """Move DuckDB's session-scoped reject table into a durable one.

    reject_errors vanishes when the connection closes. The counts would
    survive in ingest_log but the actual bad lines would not, and "N rows
    are broken" is worth far less than being able to show one.
    """
    if not db.query("SELECT 1 FROM duckdb_tables() "
                    "WHERE table_name = 'reject_errors'"):
        return 0
    n = db.one("SELECT count(*) FROM reject_errors") or 0
    if n:
        db.execute("""
            INSERT INTO stg_reject(src_file, table_name, line_no,
                                   column_name, error_type, error_message,
                                   raw_line)
            SELECT ?, ?, line, column_name, error_type, error_message,
                   csv_line FROM reject_errors
        """, [src, table])
        db.execute("DELETE FROM reject_errors")
    return n


def load_static(db, which: list[str], force: bool) -> None:
    for name in which:
        table, ncols = STATIC[name]
        path = RAW / f"{name}.dat"
        if not path.exists():
            print(f"  ! {path.name} missing - run fetch.py first",
                  file=sys.stderr)
            continue
        if already(db, path.name) and not force:
            print(f"  = {path.name} already loaded")
            continue

        cols = ", ".join(f"'column{i:02d}': 'VARCHAR'" for i in range(ncols))
        t0 = time.monotonic()
        db.execute(f"DELETE FROM {table} WHERE src_file = ?", [path.name])
        # header=false: none of the three OpenFlights files has one.
        db.execute(f"""
            INSERT INTO {table}
            SELECT *, ? FROM read_csv(?, header = false, columns = {{{cols}}},
                                      store_rejects = true,
                                      rejects_table = 'reject_errors')
        """, [path.name, str(path)])
        rej = persist_rejects(db, path.name, table)
        n = db.one(f"SELECT count(*) FROM {table} WHERE src_file = ?",
                   [path.name])
        el = time.monotonic() - t0
        record(db, path.name, table, n, rej, path.stat().st_size, el)
        extra = f"  [REJECTED {rej:,}]" if rej else ""
        print(f"  + {path.name}: {n:,} rows in {el:.0f}s{extra}")


def load_flights(db, force: bool) -> None:
    zips = sorted(RAW.glob("bts_*.zip"))
    if not zips:
        print("  ! no bts_*.zip found - run fetch.py first", file=sys.stderr)
        return

    select = ", ".join(f'"{src}" AS {dst}' for dst, src in BTS_COLUMNS.items())
    TMP.mkdir(parents=True, exist_ok=True)

    for z in zips:
        if already(db, z.name) and not force:
            print(f"  = {z.name} already loaded")
            continue
        with zipfile.ZipFile(z) as zf:
            member = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
            csv_path = TMP / Path(member).name
            print(f"  . {z.name} -> {csv_path.name}")
            with zf.open(member) as fh, csv_path.open("wb") as out:
                while chunk := fh.read(1 << 22):
                    out.write(chunk)

        t0 = time.monotonic()
        db.execute("DELETE FROM stg_flights WHERE src_file = ?", [z.name])
        # all_varchar: every field stays text so nothing is coerced before
        # the validator has counted it. ignore_errors is NOT set - a
        # structurally bad line must land in reject_errors, not vanish.
        db.execute(f"""
            INSERT INTO stg_flights
            SELECT {select}, ?
            FROM read_csv(?, header = true, all_varchar = true,
                          store_rejects = true,
                          rejects_table = 'reject_errors')
        """, [z.name, str(csv_path)])
        rej = persist_rejects(db, z.name, "stg_flights")
        n = db.one("SELECT count(*) FROM stg_flights WHERE src_file = ?",
                   [z.name])
        el = time.monotonic() - t0
        record(db, z.name, "stg_flights", n, rej, csv_path.stat().st_size, el)
        extra = f"  [REJECTED {rej:,}]" if rej else ""
        print(f"  + {z.name}: {n:,} flights in {el:.0f}s{extra}")
        csv_path.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", choices=list(STATIC) + ["flights"])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="reload files already in ingest_log")
    args = ap.parse_args()

    if not args.all and not args.table:
        ap.error("give --all or --table")

    with connect() as db:
        if args.all or args.table in STATIC:
            which = list(STATIC) if args.all else [args.table]
            print("OpenFlights -> staging")
            load_static(db, which, args.force)
        if args.all or args.table == "flights":
            print("\nBTS flights -> staging")
            load_flights(db, args.force)

        print("\nstaging row counts:")
        for t in ("stg_airports", "stg_airlines", "stg_routes", "stg_flights"):
            print(f"  {t:<16} {db.one(f'SELECT count(*) FROM {t}'):>12,}")
        print(f"  {'rejected':<16} "
              f"{db.one('SELECT count(*) FROM stg_reject'):>12,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
