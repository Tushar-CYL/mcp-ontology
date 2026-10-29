# The middle layer

Connect any data source. It works out what exists, what connects to what,
and what you can measure — then packs an answer an AI can use.

```
  ANY data source   ──▶   THE MIDDLE LAYER   ──▶   BI / AI
  Postgres, CSV,          1 ontology
  Snowflake, Excel,       2 knowledge graph
  SQLite, Parquet         3 semantic
                          4 context
```

**No code is written per dataset.** The same command reads a shop, a
hospital, or a 121 MB e-commerce export.

## Try it

```powershell
python -m pip install -r requirements.txt   # once

python run.py                               # see it in the terminal
python ui.py                                # see it on a screen
```

Three commands. No virtual environment, no `py` launcher, no `streamlit`
command — each of those is a thing that can be missing on a locked-down
machine.

`python run.py` with no argument builds a small example, so a fresh clone
always has something to show. Point it at your own data with
`python run.py <file-or-folder>`.

Sources: a database file, a folder of CSV/Parquet/Excel, one file, or a
`postgres://` / `mysql://` URL.

## The four layers

| Folder | Layer | What it does |
|---|---|---|
| `ontology/` | 1 | Reads any source and works out what kinds of thing exist, how they are identified, and what links them |
| `knowledge_graph/` | 2 | Turns rows into nodes and edges, with a validity interval on every edge so the graph can be rewound |
| `semantic/` | 3 | Proposes the metrics the data can actually support, and compiles them to SQL |
| `context/` | 4 | Packs facts into a hard size limit, dropping guesses before measurements |

## The one idea that matters

**A guess must never read as a fact.**

A real database declares its foreign keys, so those links are `stated` at
100%. A CSV declares nothing, so links are worked out from column names and
marked `guessed` at 70% — in the tables, in the diagram as a dashed arrow,
and in the final answer. If the two looked alike, nobody could tell which
answers to trust, and the first wrong one would discredit all of them.

## What it cannot do

It reads **structure** from the data — tables, keys, types, dates. It
cannot read your **business names**: nothing in a schema says `tbl_cust_01`
means Customer. Rename it and the new name is stored, not coded:

```powershell
python run.py mydata.db
```
