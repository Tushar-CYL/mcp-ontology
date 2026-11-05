"""Edge-case datasets for the QA data matrix: every shape of data a client
might hand over, including broken ones. `make_all(root)` writes them and
returns {case: (path, expectation)} where expectation is "ok" (must build an
ontology) or "reject" (must fail with a clear message, never a crash)."""

from __future__ import annotations

import csv
import json
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path


def _csv(path: Path, header: list, rows: list, delimiter: str = ",", bom: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig" if bom else "utf-8") as f:
        w = csv.writer(f, delimiter=delimiter)
        w.writerow(header)
        w.writerows(rows)
    return path


def make_all(root: Path) -> dict:
    rnd = random.Random(11)
    root.mkdir(parents=True, exist_ok=True)
    cases: dict = {}

    def add(name, path, expect="ok"):
        cases[name] = (str(path), expect)

    # --- shapes that must work -------------------------------------------
    d = root / "basic"
    _csv(d / "customers.csv", ["customer_id", "name", "country"],
         [[f"C{i:03d}", f"Customer {i}", rnd.choice(["DE", "FR", "IN"])] for i in range(80)])
    _csv(d / "orders.csv", ["order_id", "customer_id", "amount", "ordered_on"],
         [[i, f"C{i % 80:03d}", round(rnd.uniform(5, 500), 2),
           (date(2024, 1, 1) + timedelta(days=i % 300)).isoformat()] for i in range(400)])
    add("csv_two_tables", d)

    add("csv_unicode_names", _csv(root / "unicode" / "kunden_顧客.csv",
        ["客户编号", "Prix (€)", "nom_é", "emoji_😀", "Größe"],
        [[f"K{i}", round(i * 1.5, 2), f"Zoë {i} — ✓", "😀🚀" * (i % 3), i % 7]
         for i in range(60)]))

    add("csv_sql_like_names", _csv(root / "sqlish" / "select.csv",
        ["id", 'name"; DROP TABLE eo_items;--', "x' OR '1'='1", "from", "order", "group by"],
        [[i, f"Robert'); DROP TABLE students;-- {i}", "' OR 1=1 --", "a", i, "b"]
         for i in range(50)]))

    long_col = "a_" + "very_long_column_name_" * 14
    add("csv_long_names_and_cells", _csv(root / "long" / "long.csv",
        ["id", long_col, "note"],
        [[i, i * 2, ("lorem ipsum " * 6000)[:65000]] for i in range(30)]))

    add("csv_wide_400_columns", _csv(root / "wide" / "wide.csv",
        ["row_id"] + [f"metric_{i}" for i in range(399)],
        [[r] + [rnd.randint(0, 1000) for _ in range(399)] for r in range(40)]))

    add("csv_duplicate_columns", _csv(root / "dupcols" / "dup.csv",
        ["id", "value", "value", "Value"], [[i, i, i * 2, i * 3] for i in range(30)]))

    add("csv_header_only", _csv(root / "headeronly" / "empty_rows.csv",
        ["id", "name", "amount"], []))

    add("csv_single_cell", _csv(root / "single" / "one.csv", ["only"], [["x"]]))

    add("csv_all_null_column", _csv(root / "nulls" / "nulls.csv",
        ["id", "always_empty", "sometimes"],
        [[i, "", "" if i % 2 else i] for i in range(40)]))

    add("csv_bom_semicolon", _csv(root / "bom" / "semi.csv",
        ["id", "Betrag", "Datum"], [[i, f"{i},50", f"0{1 + i % 9}.03.2024"] for i in range(30)],
        delimiter=";", bom=True))

    add("csv_quoted_newlines", _csv(root / "newlines" / "notes.csv",
        ["id", "comment"], [[i, f"line one\nline two, with comma\n\"quoted\" {i}"]
                            for i in range(25)]))

    add("tsv_file", _csv(root / "tsv" / "items.tsv", ["sku", "title", "qty"],
                         [[f"S{i}", f"Item {i}", i] for i in range(30)], delimiter="\t"))

    add("csv_leading_zero_ids", _csv(root / "zeros" / "zips.csv", ["zip", "city"],
        [[f"{i:05d}", f"Town {i}"] for i in range(0, 600, 7)]))

    add("csv_mixed_date_formats", _csv(root / "dates" / "events.csv",
        ["event_id", "when_iso", "when_us", "when_epoch", "when_text"],
        [[i, (datetime(2024, 1, 1) + timedelta(hours=i)).isoformat(),
          (date(2024, 1, 1) + timedelta(days=i)).strftime("%m/%d/%Y"),
          1700000000 + i * 3600, f"{i} days ago"] for i in range(50)]))

    names = root / "names"
    for fname in ("my table.csv", "order.csv", "123start.csv"):
        _csv(names / fname, ["id", "val"], [[i, i] for i in range(20)])
    add("odd_table_names", names)

    j = root / "json"
    j.mkdir(parents=True, exist_ok=True)
    (j / "people.json").write_text(json.dumps(
        [{"person_id": i, "name": f"P{i}", "address": {"city": "Pune", "zip": "411001"},
          "tags": ["a", "b"][: i % 3], "score": None if i % 5 == 0 else i / 3}
         for i in range(40)]), encoding="utf-8")
    add("json_nested", j)

    nd = root / "ndjson"
    nd.mkdir(parents=True, exist_ok=True)
    (nd / "events.ndjson").write_text("\n".join(json.dumps(
        {"event_id": i, "kind": rnd.choice(["click", "view"]), "at": f"2024-05-0{1 + i % 9}"})
        for i in range(60)), encoding="utf-8")
    add("ndjson", nd)

    import duckdb
    pq = root / "parquet"
    pq.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"""COPY (SELECT i AS id, (i * 1.25)::DECIMAL(12,2) AS price,
        TIMESTAMPTZ '2024-01-01 00:00:00+00' + INTERVAL (i) HOUR AS ts, i % 2 = 0 AS active,
        [i, i + 1] AS list_col, {{'k': i}} AS struct_col, uuid() AS guid
        FROM range(200) t(i)) TO '{(pq / "typed.parquet").as_posix()}' (FORMAT parquet)""")
    con.close()
    add("parquet_rich_types", pq)

    xl = root / "excel"
    xl.mkdir(parents=True, exist_ok=True)
    from ontology.xlsx import workbook
    (xl / "budget.xlsx").write_bytes(workbook([
        ("Budget", [{"dept_id": f"D{i}", "department": f"Dept {i}", "budget_eur": i * 1000.5}
                    for i in range(25)])]))
    add("xlsx_file", xl)

    db = root / "shop.db"
    c = sqlite3.connect(db)
    c.executescript("""
        CREATE TABLE customer (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE "order" (id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customer(id),
                              total REAL, placed TEXT);
        CREATE VIEW big_orders AS SELECT * FROM "order" WHERE total > 100;
    """)
    c.executemany("INSERT INTO customer VALUES (?, ?)", [(i, f"Cust {i}") for i in range(50)])
    c.executemany('INSERT INTO "order" VALUES (?, ?, ?, ?)',
                  [(i, i % 50, i * 3.5, f"2024-02-{1 + i % 27:02d}") for i in range(300)])
    c.commit()
    c.close()
    add("sqlite_fk_and_view", db)

    mixed = root / "mixed"
    _csv(mixed / "stores.csv", ["store_id", "city"], [[f"ST{i}", f"City {i}"] for i in range(30)])
    con = duckdb.connect()
    con.execute(f"""COPY (SELECT i AS sale_id, 'ST' || (i % 30) AS store_id, i * 2.0 AS revenue
        FROM range(300) t(i)) TO '{(mixed / "sales.parquet").as_posix()}' (FORMAT parquet)""")
    con.close()
    (mixed / "regions.json").write_text(json.dumps(
        [{"region": r, "manager": f"M {r}"} for r in "NESW"]), encoding="utf-8")
    add("mixed_csv_parquet_json", mixed)

    nt = root / "small.nt"
    lines = []
    for i in range(200):
        s = f"<http://ex.org/person/{i}>"
        lines.append(f'{s} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://ex.org/Person> .')
        lines.append(f'{s} <http://www.w3.org/2000/01/rdf-schema#label> "Person {i} — é" .')
        lines.append(f"{s} <http://ex.org/worksFor> <http://ex.org/org/{i % 10}> .")
    for k in range(10):
        o = f"<http://ex.org/org/{k}>"
        lines.append(f"{o} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://ex.org/Organisation> .")
        lines.append(f'{o} <http://www.w3.org/2000/01/rdf-schema#label> "Org {k}" .')
    nt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    add("rdf_ntriples_typed", nt)

    ttl = root / "small.ttl"
    ttl.write_text("@prefix ex: <http://ex.org/> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
                   + "".join(f'ex:p{i} a ex:Paper ; rdfs:label "Paper {i}" ; ex:cites ex:p{(i + 1) % 30} .\n'
                             for i in range(30)), encoding="utf-8")
    add("rdf_turtle", ttl)

    # --- shapes that must be rejected cleanly ----------------------------
    e = root / "empty_file"
    e.mkdir(parents=True, exist_ok=True)
    (e / "empty.csv").write_bytes(b"")
    add("csv_zero_bytes", e, "reject_or_ok")

    g = root / "garbage"
    g.mkdir(parents=True, exist_ok=True)
    (g / "data.csv").write_bytes(bytes(rnd.getrandbits(8) for _ in range(5000)))
    add("binary_garbage_csv", g, "reject_or_ok")

    nf = root / "nothing_readable"
    nf.mkdir(parents=True, exist_ok=True)
    (nf / "readme.md").write_text("hello", encoding="utf-8")
    (nf / "image.png").write_bytes(b"\x89PNG\r\n")
    add("folder_without_data", nf, "reject")

    add("path_not_found", root / "does_not_exist", "reject")
    return cases
