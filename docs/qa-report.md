# QA report: Strata (ontology tool and platform API)

Date: 2026-11-06. Everything below was executed; nothing is estimated.
Re-run: `python -m pytest -q`, `cd frontend && npx vitest run && npm run build`, and
`python scripts/qa_data_matrix.py --real [--ai]`.

## 1. Architecture tested

- **Backend.** FastAPI (`api/server.py`, `api/onto_routes.py`, `api/eo_routes.py`, `api/mcp_server.py`).
  - One DuckDB file holds sources, the knowledge graph and the ontology registry (`eo_*` tables).
  - Background jobs live in memory.
- **Ontology engine.**
  - Steps: profile → concepts → mapping → structure → identity (`ontology/*.py`).
  - AI meanings checked against the data: `ontology/meaning.py`.
  - Knowledge-graph ontologies: `ontology/graph_onto.py`.
  - Metadata readers: `ontology/metadata.py`.
  - Excel writer: `ontology/xlsx.py`.
  - Versions: `ontology/registry.py`.
- **Frontend.**
  - React + TypeScript + Vite, React Flow / dagre for the map.
  - EY tokens in `styles.css`.
- **AI.** The EYQ incubator (gpt-5.2) through `agent/llm.py`. Offline (mock) mode is used in the tests.

## 2. What was tested

| Area | How |
|---|---|
| Every kind of data (31 generated cases) | **Must work:**<br>• CSV: two tables, Unicode/emoji names, SQL-like names, 960-char names and 65 KB cells, 400 columns, duplicate columns, header only, single cell, all-null column, BOM + `;`, quoted newlines, leading zeros, mixed date formats, odd table names<br>• TSV, nested JSON, NDJSON, Excel<br>• Parquet with TIMESTAMPTZ / DECIMAL / LIST / STRUCT / UUID<br>• SQLite with FK and view<br>• mixed CSV + Parquet + JSON folder<br>• N-Triples, Turtle<br>**Must be rejected cleanly:** empty file, binary garbage, folder without data, missing path |
| Real data (8 datasets) | olist CSV (1.5M rows), revenue Parquet, hospital and example SQLite, CSKG sup_10 / 5 / 3, SAP SALT Parquet (2.3M rows); plus a 116 MB representative sample of the 4 GB `disamkb.nt` |
| Full journey per dataset | load → build → 15 invariants → Excel (XML parsed) → MCP `get_ontology` → context note → field edit → rebuild keeps the edit → delete leaves 0 rows in every `eo_*` table |
| With the real AI | 8 edge cases (Unicode, SQL-like names, 400 columns, nested JSON, Parquet, mixed folder, RDF, SQLite) |
| API attacks (24 tests) | invalid / malformed bodies, hostile names (XSS, SQL, `../`), hostile ids, versions −1 / 0 / huge / text, 4,001-char note, bad edits, 10,000-item source list, non-metadata paths, the live DB as a source, 5 parallel builds with one name, 16 parallel edits, delete during rebuild, 100 parallel reads |
| All platform endpoints with odd data | 8 layer endpoints × 6 odd sources, plus global and 404 endpoints: no 500s |
| Security | key leakage (files, logs, git history), formula injection in Excel, OWL / SHACL validity with hostile names, file-read exposure, prompt injection, dependency audit |
| UI (Chromium) | 375 / 768 / 1280 / 1920 px, horizontal overflow, keyboard (Tab order, dialog Enter / Escape, focus), API down → error → recovery, double-click on Build, all 8 pages for console errors |
| Performance | latency of list / view / Nexus / Excel; 200 concurrent views; build times on the largest data |

## 3. Results

| Suite | Executed | Passed | Failed | Skipped |
|---|---:|---:|---:|---:|
| Python (unit, integration, data matrix, attacks, smoke) | 980 | 980 | 0 | 0 |
| Frontend (vitest) | 84 | 84 | 0 | 0 |
| Real-data matrix (engine) | 8 | 8 | 0 | 0 |
| Edge cases with the real AI | 8 | 8 | 0 | 0 |
| Race / attack suite, 3 repeats | 72 | 72 | 0 | 0 |
| Manual browser checks (overflow ×4, layout ×2, keyboard ×6, API down / recovery ×5, double-click ×1, page smoke ×8) | 26 | 26 | 0 | 0 |
| **Total** | **1,178** | **1,178** | **0** | **0** |

**Pass rate after fixes: 100%.** The first run of the new suites passed 85% (data matrix, round 1) and 92% (attacks, round 1); every failure was a real bug, fixed below.

**Other checks**
- Build: succeeds.
- Lint: 0 problems (5 earlier warnings fixed).
- `npm audit --omit=dev`: 0 vulnerabilities.
- `pip check`: OK.

## 4. Bugs found and fixed (root cause → fix)

| # | Sev | Bug | Root cause | Fix |
|---|---|---|---|---|
| B1 | High | Parquet with time-zone timestamps crashed the build | Fetching TIMESTAMPTZ into Python needs `pytz` | min / max cast to text in profiling, plus `pytz` added (B8) |
| B2 | High | Our Excel export unreadable by strict readers | `styles.xml` lacked required xf / border attributes | Spec-complete styles; test reads it back with DuckDB |
| B3 | High | Knowledge-graph / RDF ontologies lost a person's edits on rebuild | The graph writer overwrote meanings without checking `by: you` | The person's edit wins, same as the table flow |
| B4 | High | 5 builds with the same name at once: 4 failed | Id chosen and claimed in two steps | Lock around choosing and creating the id |
| B5 | Critical | Parallel edits → HTTP 500 | Version number read outside the lock; duplicate primary key | Snapshot, number and insert under one lock |
| B6 | High | Real RDF (gptkb) became one "Entity" | Types via `instanceOf` and relation labels were not used | instanceOf typing (top 25 types plus Other); relation labels; prepositions are not types |
| B7 | Med | Large KG: 8,142 links, 138 s build | Every relation listed and saved one by one | 200 most frequent listed, the rest counted and shown; 138 s → 20 s |
| B8 | High | `/api/certification` → 500 on time-zone data | Same root cause as B1, in the context layer | `pytz>=2024.1` in requirements (MIT) |
| B9 | Low | Error hint told users to run `python -m api.http` (doesn't exist) | Stale text | Correct command |
| U1 | Med | Page title pushed right on tablet / phone | A later CSS rule overrode the stacked mobile header | Narrow-screen override |
| U2 | Med | Server stopped → "The service failed" | Proxy 502 treated as a server fault | "Cannot reach the server" with the start command |
| U3 | Low | Top bar "API status unknown" when the API is down | Health check skipped when the source list failed | Health always checked |
| U4 | Low | Top bar stayed "unreachable" up to 45 s after recovery | 45 s poll | 3 s retry while unreachable |
| P1/P2 | Med | List 107 ms (2 ontologies); 20 views/s under load | The view made ~10 registry queries | One query per view: list 40 ms, view 19 ms, 57 req/s |
| P3 | Low | 400-column table with AI took 104 s | Column chunks sent one after another | Chunks in parallel: 36 s |
| Q1 | Low | 5 React hook warnings (graph and context panels) | Fresh `[]` each render broke memoisation | `useMemo` |

## 5. Security findings

| # | Finding | Status |
|---|---|---|
| S1 | The API accepts any local path, so anyone who can reach it could read any file (sample values become visible) | **Mitigated.** The server listens on 127.0.0.1 by default; new optional `STRATA_DATA_ROOTS` allowlist (403 outside it), tested |
| S2 | Prompt injection through cell values | **Hardened.** The prompt states that values are data, never instructions; every AI claim is still checked against the data |
| S3 | Formula injection in the Excel export | **Not vulnerable.** All cells are typed text; tested |
| S4 | SQL injection through names, ids, keys and search | **Not vulnerable.** All parameterised or quoted; hostile names round-trip; registry intact |
| S5 | XSS through names | **Not vulnerable.** React escapes; no `dangerouslySetInnerHTML` |
| S6 | API key exposure | **None.** Key not in any file, log or git history; `.env` git-ignored; key redacted in errors |
| S7 | Dependencies | **Production 0.** 10 moderate in dev-only tooling (minimatch chain); not shipped |

## 6. Remaining risks and limitations

- **No login on the REST API** (a local tool by design; MCP uses keys). Before any shared deployment:
  - put it behind authentication or a reverse proxy;
  - set `STRATA_DATA_ROOTS`;
  - keep it bound to 127.0.0.1.
- **The full 4 GB `disamkb.nt` was not built end to end.** Loading the whole file previously hit memory limits; a 116 MB representative sample was built (27 types, 20 s).
- **Background jobs live in memory.** A server restart forgets a running build, and a page refresh does not re-attach to it (the finished ontology still appears in the list).
- **Not tested:**
  - Postgres / MySQL / Snowflake / Databricks connectors (no servers available);
  - the real Nexus add-in;
  - Firefox and Safari (Chromium only).
- **Load times.** Loading revenue Parquet takes 81 s in the existing knowledge-graph build (the ontology build itself takes 5 s).
- **Database size.** DuckDB does not shrink the file after a delete; freed space is reused.
- **Git hygiene.** `.server.log` and `.server_final.log` are tracked in git from earlier commits (no secrets).

## 7. Verdict

- **Ready for a local, single-team pilot:**
  - all suites green;
  - every critical and high bug found here is fixed and covered by tests;
  - real data from 6 formats builds correctly.
- **Not production-ready for a shared or multi-user deployment** until authentication is added and the deployment items in §6 are done.
