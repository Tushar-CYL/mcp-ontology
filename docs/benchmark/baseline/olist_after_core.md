# Baseline benchmark - data\raw\kaggledata

- **Generated:** 2026-10-29T18:03:02+00:00
- **Source:** `data\raw\kaggledata`
- **Environment:** Python 3.14.7, DuckDB 2.0.0, Windows-11-10.0.26200-SP0
- **Method:** cold graph build from an empty file; the semantic and context stages run on that same connection (the path the app takes on its first run); a final warm reopen checks `is_current()` and re-runs one metric on a fresh connection. Sample query: first numeric metric, 20 runs after 3 warm-ups.

## Stages

| Stage | Seconds | Detail |
|---|---:|---|
| connect | 2.1792 | 9 tables, 1,550,922 rows, formats {'csv': 9} |
| discover | 0.0063 | 9 classes, 6 relations |
| graph build (cold) | 20.4997 | 1550922 nodes, 640501 edges, 0 skipped edges, 0 dangling |
| graph reopen (warm) | 0.1406 | is_current=True; sample query runs=True; file 433,598,464 bytes (413.512 MiB) |
| metrics discovered | 0.0008 | 99 metrics |
| metrics compiled | 0.2663 | 99 ok, 0 failed |
| metrics executed |  | 25 ok, 0 failed (first 25) |
| sample query (p50) | 0.0021 | p95 3.784 ms over 20 runs |
| context pack | 0.0757 | 6 of 6 facts, 354 chars |
| **total wall time** | 23.9019 | graph file: 433,598,464 bytes |

## Sample query

- Metric: `geolocation_lat_sum` (sum of geolocation_lat in Geolocation)
- Latency: p50 **2.075 ms**, p95 **3.784 ms**, min 1.454 ms, max 4.225 ms
- Runs: 20 after 3 warm-ups; rows returned: 1

```sql
SELECT sum("geolocation_lat") AS value
FROM "keyed_kaggledata__olist_geolocation_dataset"
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
