# data/

What is here is deliberate; everything else is generated or was removed.

## Kept (small, useful)

| Path | Why |
|---|---|
| `example.db` | the built-in demo shop (`python run.py`) |
| `hospital.db` | the "real foreign keys" demo used in docs/tests |
| `raw/kaggledata/` | the Olist CSVs (9 files, 121 MB) used by the UI default source |

## Generated (safe to delete; recreated on demand)

| Path | Recreated by |
|---|---|
| `graphs/` | `python run.py <source>` / `ui.py` / `app.py` |
| `fixtures/` | `python benchmarks/fixture_lake100.py` (benchmark auto-generates) |
| `bench_graphs/` | `python benchmark.py` |

## Removed in the cleanup

The earlier Alibaba/Flights builds and their download archives were deleted:
`alibaba.duckdb` (~7.6 GB), `flights.duckdb`, `olist.duckdb`, the
CallGraph/MSMetrics/NodeMetrics/MSRTMCR archives, and the copy of the Olist
database. The current code does not use them. The Olist *source CSVs* were kept.

To point at your own data, pass any supported path to `run.py`; nothing needs to
live in this folder.
