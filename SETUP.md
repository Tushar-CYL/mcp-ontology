# SETUP

## Quick start

Open PowerShell in this folder and run **one command**:

```powershell
.\setup.ps1
```

That's it. It installs everything, downloads the data, builds the graph and
checks that it works. **About 15 minutes**, mostly waiting.

When it finishes you'll see:

```
================================================
 DONE. Everything is installed and verified.
================================================
```

If it stops early it tells you exactly what went wrong and what to do.

### Other ways to run it

```powershell
.\setup.ps1 -Code      # just install the packages, skip the 2 GB download
.\setup.ps1 -Fresh     # delete everything and start over
```

> **If PowerShell refuses to run the script**, it's Windows blocking scripts
> by default. Run this once, then try again:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> ```
> This only affects the current window.

---

## What you need

| | |
|---|---|
| **Windows** | 10 or 11 |
| **Python 3.10 or newer** | [python.org](https://www.python.org/downloads/) — tick **"Add python.exe to PATH"** during install |
| **15 GB free disk** | 2 GB download + 7 GB database |
| **8 GB RAM** | 32 GB is comfortable |
| **Internet** | only for the download step |

Check what you have:

```powershell
py -3 --version
```

---

## If something goes wrong

**"No Python 3.10 or newer found"**
Install from [python.org](https://www.python.org/downloads/) and tick *Add
python.exe to PATH*. Close PowerShell, open a new window, try again.

**"The virtual environment will not start"**
Windows Smart App Control is blocking an unsigned Python. A `uv`-managed
Python is unsigned; the python.org one is signed. Install from python.org,
then `.\setup.ps1 -Fresh`.

**"Package install failed"**
No internet, or your company uses a proxy or a private mirror:
```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt -i <mirror-url>
```

**Download stalls or drops**
Just run `.\setup.ps1` again. It resumes from where it stopped — nothing is
lost.

**`CERTIFICATE_VERIFY_FAILED` / "unable to get local issuer certificate"**
Common on company laptops. Your employer inspects HTTPS by re-signing it with
their own certificate authority. Windows trusts it — that's why your browser
works — but Python ships its own certificate list and doesn't.

`requirements.txt` already installs **truststore**, which makes Python verify
against the Windows trust store instead, so this should be handled
automatically. Nothing is weakened: it checks against the same certificates
your browser already trusts.

If you still hit it, make sure truststore is actually installed:
```powershell
.venv\Scripts\python.exe -m pip install truststore
.\setup.ps1
```

**The network simply will not allow the download**
You don't need it. Copy the `data\raw` folder from a machine that already has
it into this project, then run `.\setup.ps1`. It finds the archives and skips
the download entirely.

**"Could not create the tables"**
Something else has the database open. DuckDB allows one writer at a time.
Close other terminals, notebooks or editors touching `data\okg.duckdb`.

**Out of memory during the build**
Use less data:
```powershell
.venv\Scripts\python.exe ingest\load.py --table CallGraph --limit 1
.venv\Scripts\python.exe graph\build.py --facts
```

**Everything is slow**
Make sure the folder is on an SSD, not a USB stick or network drive.

---

## Using it

All commands start with `.venv\Scripts\python.exe` — that guarantees the
right interpreter.

### Metrics

```powershell
.venv\Scripts\python.exe semantic\compile.py --list
.venv\Scripts\python.exe semantic\compile.py rt_p99 --by microservice --limit 5
```

Add `--show-sql` to see the SQL generated from `semantic\metrics.yaml`.

### Check it still works

```powershell
.venv\Scripts\python.exe verify.py
```

Re-measures every number this project quotes. Run it any time, especially on
a new machine.

### Time travel — the thing worth seeing

```powershell
.venv\Scripts\python.exe verify.py --only travel
```

Expect **2,591** affected services at 00:01:00 and **2,055** at 00:02:30.

Same question, different moment, two different correct answers. Every link in
the graph carries a time window, so the whole thing can be rewound. A normal
dashboard can only ever show you *now*.

### The queries

| Query | Answers |
|---|---|
| `blast_radius(node, as_of, cap)` | if this node dies, what breaks? |
| `placement_history(container)` | where has this container run? |
| `topology_at(service, as_of, depth)` | what did this look like then? |
| `critical_path(trace)` | where did the time go in this request? |
| `choke_points(as_of, top_n, cap)` | which services are least survivable? |
| `who_pages(node, as_of)` | who owns what runs here? |

All defined once in `sql\duckdb\queries.sql`.

---

## Running the steps by hand

`setup.ps1` runs exactly these. Use them if you want to redo one step.

```powershell
py -3 -m venv .venv                                        # 1 environment
.venv\Scripts\python.exe -m pip install -r requirements.txt # 2 packages
.venv\Scripts\python.exe ingest\fetch.py --start 0d0 --minutes 9   # 3 download (2 GB)
.venv\Scripts\python.exe graph\apply_schema.py --reset      # 4 tables
.venv\Scripts\python.exe ingest\load.py --all               # 5 load   (~2 min)
.venv\Scripts\python.exe graph\build.py --facts             # 6 build  (~6 min)
.venv\Scripts\python.exe ingest\derive_teams.py             # 7 teams
.venv\Scripts\python.exe ontology\validate.py --stage graph # 8 rules
.venv\Scripts\python.exe verify.py                          # 9 verify
```

**Two things about step 5 and 7 that look like problems but aren't:**

- About **3,000 rows are rejected** as malformed. That's correct. Roughly
  0.008% of this dataset has the wrong number of fields. We quarantine them
  in `stg_reject` with the line number and reason instead of dropping them
  silently or letting one abort the whole load.
- **Teams are derived, not measured.** This dataset has no org chart, so
  teams are inferred from the call pattern. They're tagged `derived`
  everywhere, including in the final answer.

### Reading the rule check (step 8)

| Severity | Means | Build |
|---|---|---|
| **1** | our builder is broken | **stops** |
| **2** | the source data contradicts itself | repaired, reported |
| **3** | worth recording | reported only |

Severity 1 and 2 should both be **zero**. Severity 3 will fire — that's the
dataset's own inconsistency, and reporting it is the point.

---

## Optional: run on PostgreSQL

DuckDB needs no server. The same system also runs on Postgres, which is what
Grafana reads with its official built-in datasource.

```sql
CREATE DATABASE okg;
CREATE USER okg WITH PASSWORD 'okg';
GRANT ALL ON DATABASE okg TO okg;
```

```powershell
$env:OKG_ENGINE = "postgres"
$env:OKG_DSN = "host=localhost port=5432 dbname=okg user=okg password=okg"

.venv\Scripts\python.exe sql\postgres\apply_schema.py --reset
.venv\Scripts\python.exe ingest\load.py --all
.venv\Scripts\python.exe graph\build.py --facts
```

Switch back with `$env:OKG_ENGINE = "duckdb"`.

### Settings

| Variable | Default | Does |
|---|---|---|
| `OKG_ENGINE` | `duckdb` | `duckdb` or `postgres` |
| `OKG_DUCKDB` | `data\okg.duckdb` | database file location |
| `OKG_DSN` | localhost okg/okg | Postgres connection string |

Secrets go in a `.env` file. It's gitignored and must never be committed.

---

## What's in here

```
setup.ps1       one-command install
requirements.txt  packages, with licences (this ships to clients)
verify.py       re-measures every number this project quotes

ontology\       ontology.yaml  the rules - 17 classes, 17 relations, 12 rules
                validate.py    runs the rules, stops the build on severity 1
semantic\       metrics.yaml   every metric defined once
                compile.py     turns that YAML into SQL
ingest\         fetch.py       resumable download
                load.py        CSV -> staging, bad rows quarantined
                derive_teams.py infers ownership from the call graph
graph\          apply_schema.py creates the tables
                build.py        staging -> graph
sql\duckdb\     schema, build, facts, queries, shapes
sql\postgres\   the same files in Postgres dialect
db.py           the only file that knows which engine is in use
docs\           ARCHITECTURE.txt, STORY.txt
```

**The two files that make this a product rather than a project:**
`ontology\ontology.yaml` and `semantic\metrics.yaml`. Neither contains SQL or
any vendor syntax. A new client gets a new YAML file — not new software.
