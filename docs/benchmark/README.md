# Baseline benchmarks - the current code, before the better version

This folder is the "before" picture. Every number was produced today by
`benchmark.py` on this machine, on the same sources a later version can be
measured against. Nothing here is inherited from the earlier Alibaba
generation.

| File | What it measured |
|---|---|
| `baseline/lake100_current.json` / `.md` | the deterministic 100-table lake (4,864 rows, 3 formats) |
| `baseline/example_current.json` / `.md` | `data/example.db`, the built-in 4-table shop |
| `baseline/hospital_current.json` / `.md` | `data/hospital.db`, a 4-table database with real foreign keys |

Machine: Windows 11, Python 3.14.7, DuckDB 2.0.0. One pass, cold graph build.
These are not scale claims; they are the ruler for before/after.

## Summary

| Source | connect | discover | graph build (cold) | warm reopen | total wall | graph file | nodes / edges |
|---|---:|---:|---:|---:|---:|---:|---|
| lake100 (100 tables) | 2.372 s | 0.383 s | 6.043 s | 0.055 s | **11.863 s** | 38.76 MiB | 4,864 / 6,347 |
| example.db (4 tables) | 0.193 s | 0.003 s | 0.367 s | 0.052 s | **0.903 s** | 3.51 MiB | 21 / 21 |
| hospital.db (4 tables) | 0.250 s | 0.001 s | 0.354 s | 0.048 s | **0.976 s** | 3.51 MiB | 13 / 13 |

Semantic layer and query, same runs:

| Source | metrics discovered | compiled | executed | sample query p50 / p95 |
|---|---:|---:|---:|---:|
| lake100 | 742 | 742 ok, 0 failed | 25 ok, 0 failed | 0.696 / 0.865 ms |
| example.db | 22 | 22 ok, 0 failed | 22 ok, 0 failed | 1.879 / 2.468 ms |
| hospital.db | 22 | 22 ok, 0 failed | 22 ok, 0 failed | 2.520 / 3.630 ms |

## Findings from the baseline run

1. **lake100 completes end to end.** 100 tables -> 100 distinct classes, 141
   inferred relations, 4,864 nodes, 6,347 edges, **0 dangling edges**, 742
   metrics compiled and executed without a failure. The current code survives
   a 100-table mixed-format lake, including reserved-word columns, non-ASCII
   values, keyless tables and composite identities.
2. **The same 100 tables cost 38.8 MiB of graph file for 4,864 rows.** That is
   not data volume: the graph copies every source table and every rewritten
   keyless table into DuckDB, and each small table pays page overhead. It is
   a real file-size baseline, and it says the current storage is optimised for
   correctness, not size.
3. **A warm graph of a database source crashes on reuse.** `is_current()` is
   `True`, so a second process skips the rebuild - and then layer 3 fails with
   `CatalogException: Table with name "s.order_lines" does not exist` because
   the source is attached only inside `build()`. Reproduce directly with two
   `python run.py data\example.db` runs; the second one fails at
   `run.py:248`. The lake100 (file) warm reopen works because file tables are
   copied into the graph. This is a pre-existing defect in application code
   and was not modified here; it is recorded in the two database baselines as
   a **finding**, not hidden.
4. **The three product masters are three classes.** `erp_products`,
   `pim_products` and `marketplace_products` share the `product_id` space but
   are discovered as `ErpProduct`, `PimProduct`, `MarketplaceProduct`. No
   merge happens; only the first product-named table in folder order receives
   `product_id` edges. That is the gap the better version has to close.
5. **No class-name collision is lost.** Tables that clean to the same name
   (`sales_targets` / `sales_targets_v2`, `orders` / `stg_orders_raw`) keep
   distinct classes with a numeric suffix instead of overwriting each other.

## Reproduce

From the repo root, with `.venv\Scripts\python.exe` (or any Python 3.10+ with
the requirements installed):

```powershell
# 1. the deterministic fixture (data/ is git-ignored; ground truth is tracked)
python benchmarks\fixture_lake100.py --out data\fixtures\lake100

# 2. prove the fixture is byte-identical to its tracked ground truth
python benchmarks\fixture_lake100.py --check

# 3. the baselines
python benchmark.py --fixture lake100 --json docs\benchmark\baseline\lake100_current.json --md docs\benchmark\baseline\lake100_current.md
python benchmark.py --source data\example.db --json docs\benchmark\baseline\example_current.json --md docs\benchmark\baseline\example_current.md
python benchmark.py --source data\hospital.db --json docs\benchmark\baseline\hospital_current.json --md docs\benchmark\baseline\hospital_current.md
```

Timings will differ by machine and by warm file cache. Compare the JSON
fields, not the markdown prose, when tracking changes:

| JSON field | Means |
|---|---|
| `stages.connect.seconds` | read the source into one schema |
| `stages.discover.seconds` | schema -> classes / keys / relations |
| `stages.graph.cold_build_seconds` | nodes + edges from an empty graph file |
| `stages.graph.warm_reopen_seconds` | fresh connection, `is_current()` + sample metric |
| `stages.graph.file_bytes` | graph file (+ WAL) after build |
| `stages.semantic.compiled` / `executed` | metrics compiled / actually run |
| `stages.semantic.query_p50_ms` / `query_p95_ms` | sample metric latency, 20 runs |
| `stages.context.seconds` / `facts_kept` | budgeted context pack |
| `total_seconds` | whole run |
| `errors`, `findings` | stage failures (benchmark exit 1) and behaviour worth knowing |

## What the fixture is and is not

`benchmarks/fixture_lake100.py` writes 100 deterministic files (69 CSV, 20
Parquet, 11 JSON): four domains, noisy legacy names, three overlapping product
masters, keyless tables, composite identities, reserved-word columns,
non-ASCII values and a few deliberate orphan references. It is an obstacle
course for code paths, not a scale test and not a realistic warehouse.

Its ground truth (`benchmarks/lake100_ground_truth.json`) is tracked in git
and pins: expected class per table, declared vs expected keys, all 141
expected relations (domain/range), format/domain/key counts and the SHA-256 of
every data file. `--check` regenerates in a temp folder and diffs it.

## After the core refactor (2026-10-29)

The graph now materialises every source table instead of relying on an attach
from `build()`. That fixes the warm-reopen crash recorded below and makes the
second process a pure read. The cost is build time (the graph owns its data);
the benefit is that any source — file or database — reopens warm and answers.

| Source | connect | discover | build | warm reopen | total | graph file | nodes / edges |
|---|---:|---:|---:|---:|---:|---:|---|
| lake100 (100 tables) | 2.178 s | 0.379 s | 8.129 s | 0.080 s | **15.666 s** | 39.51 MiB | 4,864 / 6,347 |
| Olist (9 CSV, 121 MB, 1.55M rows) | 2.179 s | 0.006 s | 20.500 s | 0.141 s | **23.902 s** | 413.51 MiB | 1,550,922 / 640,501 |
| example.db | 0.179 s | 0.003 s | 0.277 s | 0.074 s | **0.794 s** | 5.01 MiB | 21 / 21 |
| hospital.db | 0.217 s | 0.002 s | 0.282 s | 0.070 s | **0.794 s** | 5.01 MiB | 13 / 13 |

Warm reopen now reports `sample query runs=True` for the database sources
(previously `CatalogException: s.<table>`). Full runs:
`baseline/*_after_core.json` / `.md`. The original `*_current.*` files are kept
as the honest "before" picture — same machine, same fixtures, older code.

