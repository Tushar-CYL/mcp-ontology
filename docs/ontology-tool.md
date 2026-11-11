# The Ontology tool: connect, get an ontology, use it

**Connect data → automatic ontology → (optional) add context → use it in Nexus, Excel or any agent.**

## 1. Connect

Give it any of these. You can combine them.

| Input | Examples |
|---|---|
| Data | a CSV / Excel file, a folder of files, a SQLite / DuckDB file, `postgres://…`, `mysql://…` |
| Metadata (optional) | a Power BI / Fabric semantic model (`model.bim`), a dbt file (`schema.yml`), a data dictionary (`.csv` / `.xlsx` with `table`, `column`, `description`; `label` and `unit` are optional) |

A semantic model on its own is enough. Every item it produces is then marked "not checked", because there is no data to check it against.

## 2. The ontology (automatic)

- **Business things:** one per table, or one per group of tables that hold the same thing.
- **Every field in plain words:** a name, a one-line meaning, a type (id, link, money, date, category…) and a unit.
- **Links:** proven by matching values in the data, with a match percentage. Indirect and duplicate links are dropped.
- **Proof on every field.**
  - The AI (the configured EYQ model) suggests names and meanings.
  - The data checks each claim: an id must be unique, money must be numbers, a date must parse, a category must have few values.
  - When the data disagrees with the AI, the screen shows **Data disagrees** and keeps the data's answer.
- **Who wins:** what you say > your metadata > the AI checked against the data > the engine's guess from names.
- **Add context:** write in your own words, e.g. `KUNNR = customer number` or `canceled orders are excluded from revenue`.
  - The AI turns the note into edits.
  - Your notes and edits survive rebuilds and guide the AI next time.
- **Versions:** every build, note or edit publishes a new version.

**What the AI sees:** table and column names, profile numbers, and `STRATA_AI_SAMPLES` sample values per column (default 5; `0` sends none). It never sees whole rows. `STRATA_AI=off` turns the AI off, and the engine's names are used instead.

## 2b. Ask a question (the **Ask** tab, or the `ask_question` MCP tool)

Type a business question in plain words. Strata picks the things it is about,
the AI writes **one read-only SQL query** from them, the query is checked
(single SELECT, known tables only, no personal-data columns, compiles), run with
a row and time limit, and the answer is shown with the SQL, the fields it used
(each with its data check), how much of the question the ontology covered, and
the ontology version. A failing query is repaired once, then refused honestly.
Every number comes from running the SQL; the AI never writes an answer.

## 3. Use it

| Consumer | How |
|---|---|
| **Nexus (Excel add-in)** | `GET /api/onto/{id}/nexus`: JSON with `things`, `fields`, `links` and `calculations`, one row per item, ready for Excel tables. Add `?version=N` to pin a version. |
| **Excel** | `GET /api/onto/{id}/excel`: a workbook with sheets Things, Fields, Links (Calculations), About. |
| **Claude / any agent** | MCP at `/mcp`, tool `get_ontology {"ontology": "<id>"}` (optional `"thing"`). The other ontology tools (`get_concept`, `map_column`…) return the same plain meanings. |
| **Files** | JSON (as for Nexus), **Apache Ossie YAML** (`/api/onto/{id}/ossie`, the interchange format NVIDIA Auto Ontology and others read), OWL/Turtle, SHACL and a Git folder zip. An Ossie file can also be given as metadata on Connect. |

**For the Nexus team:** a browser-based add-in calls the API from its own web address. Add that address to `MIDDLE_LAYER_ORIGINS` (a comma-separated list) on the Strata server.

### Nexus row shape (`fields`)

```json
{"Thing": "Customer Order", "Field": "Order Status",
 "Meaning": "Order lifecycle status; 'delivered' means the customer received the parcel.",
 "Role": "Category", "Unit": "", "Links to": "", "Column": "order_status",
 "Table": "shop.orders", "Type": "VARCHAR", "Check": "Checked in data",
 "Proof": "8 distinct values: delivered, shipped, canceled, unavailable",
 "Set by": "You", "Confidence": 1.0}
```

## API (for the screens)

- `POST /api/onto/build {name, sources[], paths[{path,name?}], metadata[], domain?}` starts a job.
- `GET /api/onto` and `GET /api/onto/{id}` read ontologies.
- `POST /api/onto/{id}/rebuild` rebuilds.
- `POST /api/onto/{id}/metadata {path}` adds metadata.
- `POST /api/onto/{id}/context {text}` applies a note.
- `POST /api/onto/{id}/ask {question, max_rows?, version?}` answers a question (see 2b).
- `GET /api/onto/{id}/ossie` exports Apache Ossie YAML.
- `PUT /api/onto/{id}/fields {key, label?, meaning?, role?, unit?}` edits a field.
- `PUT /api/onto/{id}/things {key, name?, description?}` edits a thing.
- `DELETE /api/onto/{id}` removes the ontology only, never the data.
- `GET /api/onto/{id}/use` returns every consumption link.

## Measured (real data, real model)

- **Olist e-commerce** (9 tables, 1.5M rows, gpt-5.2):
  - built in 17–23 s: 9 things, 52 fields, 7 links;
  - 49 of 52 fields checked in the data;
  - 3 cases where the AI called a sequence number a "unique id" were caught, because the data has 21–29 distinct values in 100k rows.
- **Approvals, owners, survivorship, drift and maturity** are still available at `/tools/ontology-advanced`, but are not part of this flow.
