# Measured results

Every number here was produced by a test or a script in this repository and can
be re-run. Where a number comes from generated data, that is said: generated
data is clean, so those results are an upper bound, not a field claim.

| Re-run | Command |
|---|---|
| Ground-truth suites | `python -m pytest -q tests/integration/test_eo_mapping.py tests/integration/test_eo_identity.py tests/integration/test_bi_mdm_scenario.py tests/integration/test_eo_sap_style.py` |
| Every kind of data | `python scripts/qa_data_matrix.py --real --ai` |
| Question answering | `python -m pytest -q tests/integration/test_ask.py` (scripted model); live numbers below used gpt-5.2 |

## 1. Meaning of columns (what each field is)

| Data | Result | Notes |
|---|---|---|
| BI/MDM scenario, 10 "amount" columns with SAP-style names (NETWR, MWSBK, …) | **10 / 10** correct | generated data, ground truth in `ground_truth.json` |
| Same columns with names removed (AMT_01 … AMT_10) | **7 / 10** correct, 3 reported as unknown | from values and cross-system reconciliation alone; no guessing |
| SAP SALT (real, 4.7 M rows, 31 columns) | **29 / 31** get a business meaning; 24 confirmed by the data, 2 flagged as conflicts, 5 unchecked codes | conflicts are real data problems (repeated address ids, non-unique item numbers) |
| olist e-commerce (real, 1.5 M rows, 52 columns, gpt-5.2) | **49 / 52** confirmed by the data; 3 AI claims rejected | the AI called sequence numbers "unique id"; the data has 21–29 distinct values in 100 k rows |

## 2. Links between things

| Data | Result |
|---|---|
| olist (9 tables) | 7 links, all **100 % match** in the data; indirect and reverse links removed |
| SAP SALT | 6 links, all **100 %**: the sold-to, ship-to, bill-to and payer customer roles, item → document, customer → address |
| BI/MDM scenario | relationships, cardinalities and 2 hierarchies match the ground truth |

## 3. Identity across systems

| Data | Precision | Recall |
|---|---|---|
| BI/MDM scenario, with the MDM hub | **100 %** | **100 %** |
| Same, without the hub (tax id and name + country only) | **100 %** | **100 %** |
| SAP SALT | 2 repeated customer numbers found, reported with a survivor | — |

Generated data; real-world identity is harder than this.

## 4. Knowledge graphs

| Data | Result |
|---|---|
| CSKG sup_3 / sup_5 / sup_10 (research graphs, up to 2.3 M triples) | 5 types from the relation names (Method, Task, Material, Metric, Other Entity) plus "not yet typed"; verbs as links; `skos:broader` as "is a kind of"; the three folders merge into one ontology |
| gptkb `disamkb.nt` sample (116 MB, 574 k labels, 8,142 relations) | 27 types from `instanceOf`; 200 most frequent relations listed, 7,942 rarer ones counted; **20 s** |

## 5. Every kind of data

`scripts/qa_data_matrix.py`: load → build → 15 invariants → Excel → MCP → context note →
edit → rebuild keeps the edit → delete leaves no rows.

| Set | Result |
|---|---|
| 27 generated edge cases (Unicode/emoji names, SQL-like names, 400 columns, duplicate columns, header-only, BOM + `;`, quoted newlines, TSV, JSON, NDJSON, Parquet with time zones / lists / structs, Excel, SQLite with views, mixed folders, N-Triples, Turtle, and 4 broken inputs) | **27 / 27** |
| 8 real datasets (olist, revenue Parquet, 2 SQLite, 3 CSKG graphs, SAP SALT) | **8 / 8** |
| 8 edge cases with the real model | **8 / 8** |

## 6. Question answering (`ask_question`)

olist, published ontology, gpt-5.2 writes the SQL; every number comes from running it.

| Question | Answered | Repaired | Time |
|---|---|---|---|
| How many orders per order status? | yes, 8 rows | no | 2.4 s |
| Average freight value per seller state, top 5 | yes, 5 rows, 2-table join | no | 3.5 s |
| Which product categories have the most items sold? | yes, 3-table join with English names | no | 3.6 s |
| Average review score for delivered orders | yes, 4.16 | no | 3.3 s |
| Total payment value by payment type | yes, 5 rows | no | 2.7 s |
| What is the weather in Berlin? | **refused** (coverage 0, nothing matches) | — | 0.0 s |

Safety, from the test suite: `DELETE`, two statements, `INSERT`, a query on the registry
table and a query that selects personal data are all refused before they run; a broken
query is repaired once; a query over the row or time limit is cut.

## 7. Speed

| Step | Measured |
|---|---|
| Ontology build, olist (1.5 M rows), with the model | 17–23 s |
| Ontology build, SAP SALT (4.7 M rows), with the model | 14–15 s |
| 400-column table, with the model | 36 s (was 104 s before chunks ran in parallel) |
| Ontology view under 20 concurrent users | 57 requests/s, p95 408 ms |
| Excel export, 52 fields | 29 ms |

## 8. Test suites

Python **983 / 983**, frontend **87 / 87**, build and lint clean (2026-11-11).
