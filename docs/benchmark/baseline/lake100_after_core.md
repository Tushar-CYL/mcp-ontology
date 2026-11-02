# Baseline benchmark - lake100

- **Generated:** 2026-10-29T18:02:08+00:00
- **Source:** `D:\tushar\new_latest\ontology\data\fixtures\lake100`
- **Fixture:** `lake100`
- **Environment:** Python 3.14.7, DuckDB 2.0.0, Windows-11-10.0.26200-SP0
- **Method:** cold graph build from an empty file; the semantic and context stages run on that same connection (the path the app takes on its first run); a final warm reopen checks `is_current()` and re-runs one metric on a fresh connection. Sample query: first numeric metric, 20 runs after 3 warm-ups.

## Stages

| Stage | Seconds | Detail |
|---|---:|---|
| connect | 2.1780 | 100 tables, 4,864 rows, formats {'csv': 69, 'parquet': 20, 'json': 11} |
| discover | 0.3792 | 100 classes, 141 relations |
| graph build (cold) | 8.1288 | 4864 nodes, 6347 edges, 1359 skipped edges, 0 dangling |
| graph reopen (warm) | 0.0795 | is_current=True; sample query runs=True; file 41,431,040 bytes (39.512 MiB) |
| metrics discovered | 0.0019 | 742 metrics |
| metrics compiled | 4.5387 | 742 ok, 0 failed |
| metrics executed |  | 25 ok, 0 failed (first 25) |
| sample query (p50) | 0.0006 | p95 0.884 ms over 20 runs |
| context pack | 0.0193 | 7 of 7 facts, 314 chars |
| **total wall time** | 15.6660 | graph file: 41,431,040 bytes |

## Sample query

- Metric: `duration_min_sum` (sum of duration_min in CrmActivity)
- Latency: p50 **0.642 ms**, p95 **0.884 ms**, min 0.545 ms, max 1.065 ms
- Runs: 20 after 3 warm-ups; rows returned: 1

```sql
SELECT sum("duration_min") AS value
FROM "keyed_lake100__crm_activities"
LIMIT 100
```

## Errors

None. Every stage completed.

## Findings

None.

## Notes

- The graph is deleted before the cold build, so the cold number always pays the full build.
- The warm number is a fresh process-local reopen of the same file; `is_current()` compares the source/ontology signature.
- Query latency is the same metric executed repeatedly; it measures the query path, not discovery.
- The benchmark never modifies application code or the source.
- lake100 is synthetic and deterministic: it is an obstacle course for code paths, not a scale claim.
