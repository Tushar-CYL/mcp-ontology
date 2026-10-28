"""Load raw .tar.gz archives into the stg_* tables (DuckDB).

The Postgres version of this file had to split lines by hand to survive the
1,089 structurally malformed rows in each CallGraph file - one bad row
aborts a COPY. DuckDB does that natively via read_csv(store_rejects = true),
which quarantines bad lines with their line number and reason while the
good ones load on all 16 cores.

Keeping both implementations is deliberate: the contrast is one of the
findings this project is meant to produce.

Python's only job is to extract the single CSV member from the tar and hand
its path to the engine. It never sees a row.

Column types are declared explicitly rather than sniffed. The source has
placeholders like 'NaN' and 'UNKNOWN' sitting in otherwise-numeric columns,
and auto-detection would silently type a column differently from one file
to the next - which is exactly the kind of drift the ontology exists to
prevent.

Usage:
    python ingest/load.py --table CallGraph --limit 1
    python ingest/load.py --all
    python ingest/load.py --all --delete-after
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import ROOT, connect, human  # noqa: E402

# local dir -> (staging table, CSV header in file order)
SPECS: dict[str, tuple[str, list[str]]] = {
    "CallGraph": ("stg_callgraph", [
        "timestamp", "traceid", "service", "rpc_id", "rpctype", "um",
        "uminstanceid", "interface", "dm", "dminstanceid", "rt"]),
    "MSMetrics": ("stg_msmetrics", [
        "timestamp", "msname", "msinstanceid", "nodeid",
        "cpu_utilization", "memory_utilization"]),
    "NodeMetrics": ("stg_nodemetrics", [
        "timestamp", "nodeid", "cpu_utilization", "memory_utilization"]),
    "MSRTMCR": ("stg_msrtmcr", [
        "timestamp", "msname", "msinstanceid", "nodeid",
        "providerrpc_rt", "providerrpc_mcr", "consumerrpc_rt", "consumerrpc_mcr",
        "writemc_rt", "writemc_mcr", "readmc_rt", "readmc_mcr",
        "writedb_rt", "writedb_mcr", "readdb_rt", "readdb_mcr",
        "consumermq_rt", "consumermq_mcr", "providermq_rt", "providermq_mcr",
        "http_mcr", "http_rt"]),
}

# CSV calls it "timestamp"; the staging table calls it "ts".
COLMAP = {"timestamp": "ts"}
# Only the timestamp is numeric in staging; everything else stays text so
# the validator can see the placeholders before anything is cleaned.
BIGINT_COLS = {"ts"}


def extract_csv(archive: Path, workdir: Path) -> tuple[Path, int]:
    """Extract the single CSV member. Returns (path, uncompressed size)."""
    workdir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, mode="r|gz") as tf:
        for m in tf:
            if not (m.isfile() and m.name.lower().endswith(".csv")):
                continue
            fh = tf.extractfile(m)
            if fh is None:
                raise RuntimeError(f"cannot read {m.name} in {archive.name}")
            out = workdir / Path(m.name).name
            with out.open("wb") as dst:
                shutil.copyfileobj(fh, dst, length=8 << 20)
            return out, m.size
    raise RuntimeError(f"no .csv member in {archive.name}")


def column_spec(header: list[str]) -> str:
    parts = []
    for c in header:
        name = COLMAP.get(c, c)
        parts.append(f"'{c}': '{'BIGINT' if name in BIGINT_COLS else 'VARCHAR'}'")
    return "{" + ", ".join(parts) + "}"


def load_archive(db, archive: Path, table: str, header: list[str],
                 workdir: Path, force: bool = False) -> int:
    done = db.one("SELECT rows_loaded FROM ingest_log WHERE src_file = ?",
                  [archive.name])
    if done is not None and not force:
        print(f"  = {archive.name} already loaded ({done:,} rows)")
        return 0
    if done is not None:
        print(f"  ~ {archive.name} reloading (was {done:,} rows)")
        db.execute(f"DELETE FROM {table} WHERE src_file = ?", [archive.name])
        db.execute("DELETE FROM ingest_log WHERE src_file = ?", [archive.name])
        db.execute("DELETE FROM stg_reject WHERE src_file = ?", [archive.name])

    started = time.monotonic()
    csv_path, raw_size = extract_csv(archive, workdir)
    print(f"  . {archive.name} -> {csv_path.name} "
          f"({human(raw_size)} uncompressed)")

    reject_tbl = "reject_errors"
    reject_scan = "reject_scans"
    # Each read_csv call gets a fresh scan_id, so recording the high-water
    # mark first lets us attribute rejects to THIS archive even when several
    # are loaded on one connection.
    try:
        prev_scan = db.one(f"SELECT coalesce(max(scan_id), -1) FROM {reject_tbl}")
    except Exception:          # noqa: BLE001 - table appears on first use
        prev_scan = -1
    if prev_scan is None:
        prev_scan = -1

    target_cols = [COLMAP.get(c, c) for c in header]
    sql = (
        f"INSERT INTO {table} ({', '.join(target_cols)}, src_file) "
        f"SELECT *, '{archive.name}' FROM read_csv("
        f"  '{csv_path.as_posix()}', "
        f"  columns = {column_spec(header)}, "
        f"  header = true, "
        f"  store_rejects = true, "
        f"  rejects_table = '{reject_tbl}', "
        f"  rejects_scan = '{reject_scan}')")

    before = db.one(f"SELECT count(*) FROM {table}") or 0
    db.execute(sql)
    after = db.one(f"SELECT count(*) FROM {table}") or 0
    rows = after - before

    # Copy this archive's rejects somewhere durable before the connection
    # closes and reject_errors disappears with it.
    try:
        db.execute(
            "INSERT INTO stg_reject(src_file, table_name, line_no, "
            "column_name, error_type, error_message, raw_line) "
            f"SELECT ?, ?, line, column_name, CAST(error_type AS VARCHAR), "
            f"error_message, csv_line FROM {reject_tbl} WHERE scan_id > ?",
            [archive.name, table, prev_scan])
        rejected = db.one(
            f"SELECT count(*) FROM {reject_tbl} WHERE scan_id > ?",
            [prev_scan]) or 0
    except Exception:          # noqa: BLE001 - no rejects means no table
        rejected = 0

    csv_path.unlink(missing_ok=True)
    el = max(time.monotonic() - started, 1e-6)

    db.execute(
        "INSERT INTO ingest_log(src_file, table_name, rows_loaded, "
        "rows_rejected, bytes_read, seconds) VALUES (?,?,?,?,?,?)",
        [archive.name, table, rows, rejected, raw_size, round(el, 1)])

    msg = (f"  + {archive.name}: {rows:,} rows, {human(raw_size)} in "
           f"{el:,.0f}s ({raw_size / el / 1048576:.0f} MiB/s)")
    if rejected:
        pct = 100.0 * rejected / max(rows + rejected, 1)
        msg += f"  [REJECTED {rejected:,} malformed rows, {pct:.4f}%]"
    print(msg)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", action="append", choices=sorted(SPECS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--src", type=Path, default=ROOT / "data" / "raw")
    ap.add_argument("--workdir", type=Path, default=ROOT / "data" / "tmp",
                    help="where the CSV is unpacked before loading")
    ap.add_argument("--limit", type=int, help="at most N archives per table")
    ap.add_argument("--delete-after", action="store_true",
                    help="delete each archive once loaded, to bound disk use")
    ap.add_argument("--force", action="store_true",
                    help="reload archives already recorded in ingest_log")
    args = ap.parse_args()

    if not args.all and not args.table:
        ap.error("give --table or --all")
    names = sorted(SPECS) if args.all else args.table

    total = 0
    with connect() as db:
        for name in names:
            table, header = SPECS[name]
            d = args.src / name
            if not d.is_dir():
                print(f"{name}: no directory {d}, skipping")
                continue
            archives = sorted(
                d.glob("*.tar.gz"),
                key=lambda p: int(p.stem.rsplit("_", 1)[-1].split(".")[0]))
            if args.limit:
                archives = archives[:args.limit]
            if not archives:
                print(f"{name}: no archives, skipping")
                continue

            print(f"\n{name} -> {table}  ({len(archives)} archive(s))")
            for a in archives:
                total += load_archive(db, a, table, header, args.workdir,
                                      force=args.force)
                if args.delete_after:
                    a.unlink(missing_ok=True)
                    print(f"    - deleted {a.name}")

        print("\nstaging row counts:")
        for name in sorted(SPECS):
            t = SPECS[name][0]
            print(f"  {t:<18} {db.one(f'SELECT count(*) FROM {t}'):>14,}")
        n = db.one("SELECT count(*) FROM stg_reject") or 0
        print(f"  {'rejected (durable)':<18} {n:>14,}")

    print(f"\nloaded {total:,} rows this run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
