# START HERE

One file. Install once, point it at any data source, see the four layers.

## 1. Install (once)

```powershell
python -m pip install -r requirements.txt
```

## 2. Connect any data source

Use the path or URL as the argument. Supported today:

| Source | Example |
|---|---|
| SQLite / DuckDB file | `python run.py "C:\data\shop.db"` |
| Folder of CSV / Parquet / JSON / Excel | `python run.py "C:\data\my_folder"` |
| One file | `python run.py "C:\data\sales.csv"` |
| RDF graph file (`.nt`, `.nq`, `.ttl`, `.rdf`, `.jsonld`) | `python run.py "C:\data\graph.nt"` |
| Triple-store folder (`entities`, `relations`, `triples`/`train`/`test`/`valid`) | `python run.py "C:\data\cskg_dataset"` |
| Postgres / MySQL URL | `python run.py "postgres://user:pass@host/db"` |
| Snowflake / Databricks URL | `python run.py "snowflake://user:pass@acct/DB/SCHEMA?warehouse=WH"` — needs the vendor driver, see below |
| HTTP(S) URL to a supported file | `python run.py "https://example.com/data.csv"` |
| No argument (built-in example) | `python run.py` |
| Several sources, one graph | `python run.py "C:\data\erp" "C:\data\crm"` |

No configuration, no mapping file, no per-dataset code. If a file in a folder
cannot be read it is skipped and reported, and the rest still runs.

### Graph files (RDF)

An `.nt`/`.nq` file is read as a graph, not a table: each subject and IRI object
becomes an **Entity**, and each object property becomes a **Link** with two
declared links to Entity (`source`, `target`). Labels and `rdf:type` become
columns. Very large files are streamed by DuckDB; the first build takes minutes
(a 4 GB file is not unusual for this format).

`.ttl`, `.rdf`, `.jsonld` need the `rdflib` parser:

```powershell
python -m pip install rdflib
```

### Triple-store folders

A folder shaped like a CSKG-style export is read as a graph, not six unrelated
tables: `entities.*` (id, label), `relations.*` (id, name), and
`triples.*` / `train.*` / `test.*` / `valid.*` (head, relation, tail), tab
separated with no header.

The result is one **Entity** class, one relation per predicate, and typed
Entity→Entity edges. On a 36k-entity benchmark folder this produced 132,286
typed links with 0 dangling, in about five seconds.

### Cloud warehouses

```powershell
python -m pip install snowflake-connector-python   # snowflake://
python -m pip install databricks-sql-connector     # databricks://
```

Both copy the tables to a temporary local CSV before the normal build (the
graph must own its data to reopen warm). Credentials go in the URL for a local
demo; do not paste a production password into shell history.

## 3. See the output

Terminal: `python run.py <source>`

```
LAYER 1  ONTOLOGY         what kinds of thing exist, how one is identified,
                          which links are stated vs guessed
LAYER 2  KNOWLEDGE GRAPH  things + links, a time interval on every link,
                          and a check for links pointing at nothing
LAYER 3  SEMANTIC         metrics the columns can actually support, with SQL
LAYER 4  CONTEXT          a small packed answer, every line labelled
                          measured / derived
```

On screen:

```powershell
python run_server.py --port 8000
```

then open <http://127.0.0.1:8000>. The sidebar is grouped by team: **Govern**
(ontology, knowledge graph, Context Factory, certification), **Analytics**
(semantic metrics) and **Serve agents** (context packs, agent connections).

To connect an external agent (Claude Desktop, Cursor, Copilot), open
**Agent connections**, register the agent with a source and metrics, issue a
key, and paste the generated configuration. The agent then calls
`POST http://127.0.0.1:8000/mcp` with `Authorization: Bearer <key>`.

What to look at:
- classes and relations derived from the source (no configuration);
- a dashed arrow / "guessed" label means inferred, not declared;
- `links pointing at nothing 0` means the build is consistent;
- every context line says `measured` or `derived`.

## 4. Optional: review, API, MCP, tests

```powershell
python -m pytest -q                       # 281 tests

python -m review.cli --graph data\graphs\<graph>.duckdb list
python -m api.http --graph data\graphs\<graph>.duckdb
python -m api.mcp_server --graph data\graphs\<graph>.duckdb
```

The graph file name is printed by `run.py`; it lives under `data\graphs\`.

## If something goes wrong

| Message | What to do |
|---|---|
| `ModuleNotFoundError` | Run step 1 again |
| `python` is not recognised | Reinstall Python from python.org and tick "Add python.exe to PATH" |
| `no readable files` | Add `.csv/.parquet/.json/.xlsx` or an RDF graph file (`.nt/.nq/.ttl/.rdf/.jsonld`) |
| `do not know how to read .xyz` | Use a supported type, or point at its folder |
| `not found` | Check the path; quote it if it contains spaces |
| `database is locked` | Close other terminals/notebooks using that DuckDB file |
| A source is slow the first time | It is building the graph; later runs reopen it warm |
| A cloud URL asks for a driver | `pip install snowflake-connector-python` or `databricks-sql-connector` |
| UI shows old screens | Rebuild it: `cd frontend && npm run build`, then restart `run_server.py` |

Deep docs: [SETUP.md](SETUP.md) · [docs/API.md](docs/API.md) ·
[docs/benchmark/](docs/benchmark/README.md) · [STATUS.txt](STATUS.txt).
