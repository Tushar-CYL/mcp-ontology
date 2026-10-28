# SETUP — install and run on a new machine

Follow top to bottom. Every command is PowerShell, run from the project root.

**Total time: about 25 minutes**, most of it waiting on a download and a build.

---

## What this project is

The **middle layer** between a company's data and their BI/AI tools:
ontology, knowledge graph, semantic layer, context layer. Written in Python,
configured by YAML, so one engine serves any client.

It is tested on a real public dataset: Alibaba microservice traces.

---

## 0. Before you start

| Need | Why |
|---|---|
| **Windows 10/11** | Developed and tested here. Linux/macOS work, paths differ. |
| **Python 3.14** from [python.org](https://www.python.org/downloads/) | See the warning below — do not use another build. |
| **~15 GB free disk** | 2 GB downloads + 7 GB database + room to work. |
| **8 GB RAM minimum**, 32 GB comfortable | The build is memory-hungry at full slice. |
| **Internet** | Only for step 2 and 3. Everything after runs offline. |

> **Use the signed python.org installer.**
> Windows Smart App Control blocks unsigned executables. A `uv`-managed
> CPython is unsigned and its virtual environments will refuse to start. The
> python.org build is signed and its venvs inherit that signature.
> If `.venv\Scripts\python.exe` dies silently, this is why.

Check your Python:

```powershell
py -3.14 --version
# Python 3.14.x
```

---

## 1. Install

```powershell
cd <wherever you copied the project>

py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Verify:

```powershell
.\.venv\Scripts\python.exe -c "import duckdb, yaml, httpx, networkx; print('ok', duckdb.__version__)"
# ok 2.0.0
```

> From here on, every command uses `.\.venv\Scripts\python.exe`, not `python`.
> That avoids picking up a different interpreter by accident.

---

## 2. Download the data

The dataset is public and ungated — no account, no survey.

```powershell
.\.venv\Scripts\python.exe ingest\fetch.py --start 0d0 --minutes 9
```

**~2 GB, a few minutes.** Downloads resume on interruption, so a dropped
connection costs nothing — just run it again.

See the plan before committing to it:

```powershell
.\.venv\Scripts\python.exe ingest\fetch.py --start 0d0 --minutes 9 --dry-run
```

**Scale note:** CallGraph files cover **3 trace-minutes each**, so `--minutes 9`
fetches 3 of them. NodeMetrics covers 12 hours in one file; MSMetrics 30
minutes. Asking for more minutes only adds CallGraph and MSRTMCR files.

---

## 3. Load it into the database

```powershell
.\.venv\Scripts\python.exe graph\apply_schema.py --reset
.\.venv\Scripts\python.exe ingest\load.py --all
```

**About 2 minutes.** Expect roughly:

```
stg_callgraph          39,183,679
stg_msmetrics          13,987,704
stg_msrtmcr            32,573,038
stg_nodemetrics        30,587,212
rejected (durable)          3,078
```

> **The 3,078 rejects are correct, not a failure.** About 0.008% of rows in
> this dataset are structurally malformed — the wrong number of fields. We
> quarantine them in `stg_reject` with the line number and reason rather than
> dropping them silently or letting one abort the load.

---

## 4. Build the graph

```powershell
.\.venv\Scripts\python.exe graph\build.py --facts
```

**About 6 minutes.** Ends with a summary:

```
class     Container              measured      1,085,261
class     Microservice           measured         38,780
class     Node                   measured         46,208
relation  instance_of            measured        759,307
relation  runs_on                measured        468,597
relation  calls                  measured        211,534
...
```

Then derive the team ownership (a separate step — `build.py` does not run it,
and without it `who_pages` returns nothing):

```powershell
.\.venv\Scripts\python.exe ingest\derive_teams.py
```

> Teams are **derived, not measured.** This dataset has no org chart, so teams
> are inferred from the call pattern by community detection. They are tagged
> `derived` everywhere they appear, including in the final answer.

---

## 5. Check the rules

```powershell
.\.venv\Scripts\python.exe ontology\validate.py --stage staging
.\.venv\Scripts\python.exe ontology\validate.py --stage graph
```

Prints every rule, how many rows broke it, and sample rows.

**Reading the result:**

| Severity | Meaning | Build behaviour |
|---|---|---|
| **1** | Our builder is broken | **Fails the build** |
| **2** | The source data contradicts itself | Repaired, reported |
| **3** | Worth recording | Reported only |

**Severity 1 and 2 should both be zero.** Severity 3 rules will fire — that is
the source dataset's own inconsistency, and reporting it is the point.

---

## 6. Prove it works

```powershell
.\.venv\Scripts\python.exe verify.py
```

Re-measures every number the demo quotes and runs the regression tests.
Should end with `all checks passed`.

Run one section at a time:

```powershell
.\.venv\Scripts\python.exe verify.py --only path       # the critical_path fix
.\.venv\Scripts\python.exe verify.py --only travel     # time travel
.\.venv\Scripts\python.exe verify.py --only metric     # semantic layer
.\.venv\Scripts\python.exe verify.py --only incident   # the hot node
```

---

## 7. Ask it things

### Metrics

```powershell
.\.venv\Scripts\python.exe semantic\compile.py --list
.\.venv\Scripts\python.exe semantic\compile.py rt_p99 --by microservice --limit 5
.\.venv\Scripts\python.exe semantic\compile.py fan_out --as-of "2022-01-01 00:02:00"
```

Add `--show-sql` to see the SQL it generated from `semantic/metrics.yaml`.

### Graph queries

```powershell
.\.venv\Scripts\python.exe -c @'
import sys; sys.path.insert(0, ".")
from db import connect
with connect(read_only=True) as db:
    for r in db.query("""
        SELECT count(*) FROM blast_radius('NODE_12426',
               TIMESTAMP '2022-01-01 00:01:00', 12)"""):
        print("affected services at 00:01:00 :", r[0])
    for r in db.query("""
        SELECT count(*) FROM blast_radius('NODE_12426',
               TIMESTAMP '2022-01-01 00:02:30', 12)"""):
        print("affected services at 00:02:30 :", r[0])
'@
```

Expected: **2,591** and **2,055**.

Two different answers to the same question is the point — the graph stores a
time window on every link, so it can be rewound. A normal dashboard can only
ever show you *now*.

Available queries, all defined once in `sql/duckdb/queries.sql`:

| Query | Answers |
|---|---|
| `blast_radius(node, as_of, cap)` | if this node dies, what breaks? |
| `placement_history(container)` | where has this container run? |
| `topology_at(service, as_of, depth)` | what did this look like then? |
| `critical_path(trace)` | where did the time go in this request? |
| `choke_points(as_of, top_n, cap)` | which services are least survivable? |
| `who_pages(node, as_of)` | who owns what runs here? |
| `graph_summary()` | row counts by class and relation |

---

## 8. Optional — run it on Postgres instead

Everything above uses DuckDB, which needs no server. The same system runs on
Postgres, which is what Grafana can read with its official built-in datasource.

1. Install PostgreSQL 17 (native, no Docker).
2. Create the database:

```sql
CREATE DATABASE okg;
CREATE USER okg WITH PASSWORD 'okg';
GRANT ALL ON DATABASE okg TO okg;
```

3. Point the project at it and build:

```powershell
$env:OKG_ENGINE = "postgres"
$env:OKG_DSN = "host=localhost port=5432 dbname=okg user=okg password=okg"

.\.venv\Scripts\python.exe sql\postgres\apply_schema.py --reset
.\.venv\Scripts\python.exe ingest\load.py --all
.\.venv\Scripts\python.exe graph\build.py --facts
```

Switch back with `$env:OKG_ENGINE = "duckdb"`.

> `sql/duckdb/` and `sql/postgres/` hold the same filenames in two dialects.
> **The diff between those folders is a deliverable** — it is the evidence that
> this runs on whatever database a client already has approved.

---

## Settings

| Variable | Default | Does |
|---|---|---|
| `OKG_ENGINE` | `duckdb` | `duckdb` or `postgres` |
| `OKG_DUCKDB` | `data\okg.duckdb` | database file location |
| `OKG_DSN` | localhost okg/okg | Postgres connection string |

Put secrets in a `.env` file. It is gitignored and must never be committed.

---

## When it goes wrong

**`.venv\Scripts\python.exe` exits silently, no error**
Smart App Control is blocking an unsigned interpreter. Delete `.venv`,
reinstall Python from python.org, recreate the venv.

**`IOException: Could not set lock on file ... okg.duckdb`**
DuckDB allows one writer. Close the other Python process or notebook. Readers
must pass `read_only=True`.

**Out of memory during `graph/build.py`**
Load fewer files: `ingest\load.py --table CallGraph --limit 1`, then rebuild.

**Download stalls**
Press Ctrl-C and run `fetch.py` again. It resumes from where it stopped.

**`validate.py` reports severity-1 violations**
A real bug in the build, not messy data. Read the sample rows it prints; they
name the exact rows that broke the rule.

**Everything is slow**
Check `data\okg.duckdb` is on an SSD, not a network drive or USB disk.

---

## Where things live

```
ontology\     ontology.yaml     the rules - 17 classes, 17 relations, 12 rules
              validate.py       runs the rules, fails the build on severity 1

semantic\     metrics.yaml      every metric defined once
              compile.py        turns that YAML into SQL

ingest\       fetch.py          resumable download
              load.py           CSV -> staging, bad rows quarantined
              derive_teams.py   infers team ownership from the call graph

sql\duckdb\   schema, build, facts, queries, shapes
sql\postgres\ the same files, Postgres dialect

graph\        apply_schema.py   creates the tables
              build.py          staging -> graph

db.py         the only file that knows which engine is in use
verify.py     re-measures every number the demo quotes
docs\         ARCHITECTURE.txt, STORY.txt
```

**The two files that make this a product, not a project:**
`ontology/ontology.yaml` and `semantic/metrics.yaml`. They contain no SQL and
no vendor syntax. A new client gets a new YAML file — not new software.
