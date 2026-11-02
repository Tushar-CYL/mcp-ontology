# Baseline benchmark - data\hospital.db

- **Generated:** 2026-10-29T17:34:03+00:00
- **Source:** `data\hospital.db`
- **Environment:** Python 3.14.7, DuckDB 2.0.0, Windows-11-10.0.26200-SP0
- **Method:** cold graph build from an empty file; the semantic and context stages run on that same connection (the path the app takes on its first run); a final warm reopen checks `is_current()` and re-runs one metric on a fresh connection. Sample query: first numeric metric, 20 runs after 3 warm-ups.

## Stages

| Stage | Seconds | Detail |
|---|---:|---|
| connect | 0.2498 | 4 tables, 13 rows, formats {'database': 4} |
| discover | 0.0012 | 4 classes, 3 relations |
| graph build (cold) | 0.3537 | 13 nodes, 13 edges, 0 skipped edges, 0 dangling |
| graph reopen (warm) | 0.0478 | is_current=True; sample query runs=False; file 3,682,304 bytes (3.512 MiB) |
| metrics discovered | 0.0002 | 22 metrics |
| metrics compiled | 0.0970 | 22 ok, 0 failed |
| metrics executed |  | 22 ok, 0 failed (first 25) |
| sample query (p50) | 0.0025 | p95 3.63 ms over 20 runs |
| context pack | 0.0198 | 4 of 4 facts, 158 chars |
| **total wall time** | 0.9761 | graph file: 3,682,304 bytes |

## Sample query

- Metric: `floor_sum` (sum of floor in Department)
- Latency: p50 **2.52 ms**, p95 **3.63 ms**, min 1.404 ms, max 4.083 ms
- Runs: 20 after 3 warm-ups; rows returned: 1

```sql
SELECT sum("floor") AS value
FROM s."departments"
LIMIT 100
```

## Errors

None. Every stage completed.

## Findings

- **warm reopen:** is_current() is True, but the sample metric cannot run on the reopened graph without rebuilding: the source is not re-attached to the new connection. This is the cached path a second app/run.py process takes.
  - observed error: `CatalogException: Catalog Error: Table with name "s.departments" does not exist because schema "s" does not exist.

LINE 2: FROM s."departments"
             ^^^^^^^^^^^^^^^`

## Notes

- The graph is deleted before the cold build, so the cold number always pays the full build.
- The warm number is a fresh process-local reopen of the same file; `is_current()` compares the source/ontology signature.
- Query latency is the same metric executed repeatedly; it measures the query path, not discovery.
- The benchmark never modifies application code or the source.
