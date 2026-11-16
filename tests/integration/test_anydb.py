"""Any database in - the connectors that need no server (run everywhere):

* SQLAlchemy over a SQLite URL (the generic relational path, with declared
  primary and foreign keys kept);
* ODBC through the Access Text driver over a CSV folder (the generic ODBC
  path, Windows);
* an Access .accdb file (Windows, when the ACE provider can create one);
* MongoDB through mongomock (the pymongo API without a server);
* Neo4j through a scripted driver;
* a Delta Lake table written with deltalake;
* object-store listing, exercised on a local folder.

Real servers (Postgres, MySQL, SQL Server, MongoDB, Neo4j in Docker) are in
test_anydb_docker.py and skip when no engine is running.
"""

from __future__ import annotations

import json
import sqlite3
import sys

import pytest

from api.service import MiddleLayer
from ontology import anydb, simple
from ontology.connect import SourceError, connect


def _sqlite(path):
    c = sqlite3.connect(path)
    c.executescript("""
        CREATE TABLE customer (id INTEGER PRIMARY KEY, name TEXT, country TEXT);
        CREATE TABLE "order" (id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customer(id),
                              total REAL, placed TEXT, paid INTEGER);
        CREATE VIEW big AS SELECT * FROM "order" WHERE total > 100;
    """)
    c.executemany("INSERT INTO customer VALUES (?,?,?)", [(i, f"C{i}", "DE" if i % 2 else "FR") for i in range(60)])
    c.executemany('INSERT INTO "order" VALUES (?,?,?,?,?)',
                  [(i, i % 60, i * 2.5, f"2024-03-{1 + i % 28:02d}", i % 2) for i in range(400)])
    c.commit()
    c.close()


def test_sqlalchemy_url_keeps_declared_keys_and_reads_views(tmp_path):
    db = tmp_path / "shop.db"
    _sqlite(db)
    schema = connect(f"sqlite:///{db.as_posix()}", name="shop")
    tables = {t.name: t for t in schema.tables}
    assert set(tables) == {"customer", "order", "big"}
    assert tables["order"].primary_key == ["id"]
    assert [(f.column, f.ref_table, f.ref_column) for f in tables["order"].foreign_keys] == \
        [("customer_id", "customer", "id")]
    assert tables["order"].row_count == 400 and tables["big"].row_count > 0
    assert schema.origin.startswith("sqlite:///")
    # The whole journey: load, build, publish.
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(f"sqlite:///{db.as_posix()}", source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    v = simple.view(layer.graph, oid)
    assert {t["name"] for t in v["things"]} >= {"Customer", "Order"}
    assert any(l["from_thing"] == "Order" and l["to_thing"] == "Customer" for l in v["links"])


def test_unknown_dialects_and_bad_urls_say_what_to_install(tmp_path):
    with pytest.raises(SourceError, match="pip install"):
        connect("trino://user@host:8080/catalog")
    with pytest.raises(SourceError):
        connect("sqlite:///C:/does/not/exist/x.db")
    with pytest.raises(SourceError, match="no tables"):
        empty = tmp_path / "empty.db"
        sqlite3.connect(empty).close()
        connect(f"sqlite:///{empty.as_posix()}")


def test_url_normalisation():
    assert anydb.normalise_sqlalchemy_url("postgres://u:p@h/d") == "postgresql+psycopg://u:p@h/d"
    assert anydb.normalise_sqlalchemy_url("mysql://u:p@h/d") == "mysql+pymysql://u:p@h/d"
    assert anydb.normalise_sqlalchemy_url("mssql://u:p@h/d?driver=SQL+Server") == "mssql+pyodbc://u:p@h/d?driver=SQL+Server"
    assert anydb.normalise_sqlalchemy_url("mysql+mysqldb://u@h/d") == "mysql+mysqldb://u@h/d"
    assert anydb._redact("postgres://alice:s3cret@db/x") == "postgres://alice:***@db/x"


@pytest.mark.skipif(sys.platform != "win32", reason="the Access Text ODBC driver is Windows-only")
def test_odbc_through_the_access_text_driver(tmp_path):
    import pyodbc
    if not any("Access Text Driver" in d for d in pyodbc.drivers()):
        pytest.skip("no Access Text ODBC driver")
    folder = tmp_path / "csvdb"
    folder.mkdir()
    (folder / "items.csv").write_text("sku,title,qty\n" + "".join(f"S{i},Item {i},{i}\n" for i in range(30)),
                                      encoding="utf-8")
    url = f"odbc://Driver={{Microsoft Access Text Driver (*.txt, *.csv)}};DBQ={folder};"
    schema = connect(url, name="csvdb")
    assert [t.name for t in schema.tables] == ["items_csv"] or any("items" in t.name for t in schema.tables)
    t = schema.tables[0]
    assert t.row_count == 30 and {c.name.lower() for c in t.columns} == {"sku", "title", "qty"}
    assert "PWD" not in schema.origin


@pytest.mark.skipif(sys.platform != "win32", reason="Access databases are Windows-only")
def test_access_database_file(tmp_path):
    pytest.importorskip("win32com.client")
    import win32com.client
    path = tmp_path / "crm.accdb"
    try:
        cat = win32com.client.Dispatch("ADOX.Catalog")
        cat.Create(f"Provider=Microsoft.ACE.OLEDB.12.0;Data Source={path};")
        conn = cat.ActiveConnection
        conn.Execute("CREATE TABLE Accounts (AccountId COUNTER PRIMARY KEY, Name TEXT(80), Balance CURRENCY)")
        for i in range(25):
            conn.Execute(f"INSERT INTO Accounts (Name, Balance) VALUES ('Acc {i}', {i * 10.5})")
        conn.Close()
    except Exception as exc:                       # noqa: BLE001 - no ACE provider
        pytest.skip(f"cannot create an Access database here: {str(exc)[:120]}")
    schema = connect(str(path))
    t = schema.tables[0]
    assert t.name == "accounts" and t.row_count == 25 and t.primary_key == ["AccountId"]


def test_mongodb_collections_become_tables(tmp_path, monkeypatch):
    import mongomock
    from bson import ObjectId
    client = mongomock.MongoClient()
    db = client["crm"]
    db.contacts.insert_many([{"_id": ObjectId(), "name": f"P{i}", "age": 20 + i,
                              "address": {"city": "Pune", "zip": "411001"},
                              "tags": ["a", "b"][: i % 3]} for i in range(40)])
    db.deals.insert_many([{"deal": i, "amount": i * 100.0, "contact": f"P{i % 40}"} for i in range(80)])
    db.empty.insert_one({"x": 1})
    db.empty.delete_many({})
    monkeypatch.setattr(anydb, "mongo_client", lambda url: client)
    schema = connect("mongodb://localhost:27017/crm", name="crm")
    tables = {t.name: t for t in schema.tables}
    assert set(tables) == {"contacts", "deals"}
    assert tables["contacts"].primary_key == ["_id"] and tables["contacts"].row_count == 40
    assert "address" in {c.name for c in tables["contacts"].columns}
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source("mongodb://localhost:27017/crm", source="crm")
    oid = simple.create_and_build(layer, "CRM", ["crm"])["ontology"]
    assert {t["name"] for t in simple.view(layer.graph, oid)["things"]} == {"Contact", "Deal"}


def test_mongodb_needs_a_database_name_when_several_exist(monkeypatch):
    import mongomock
    client = mongomock.MongoClient()
    client["a"].x.insert_one({"v": 1})
    client["b"].y.insert_one({"v": 1})
    monkeypatch.setattr(anydb, "mongo_client", lambda url: client)
    with pytest.raises(SourceError, match="add the database name"):
        connect("mongodb://localhost:27017")


class FakeNeo4j:
    """The slice of the neo4j driver API the connector uses, with 3 labelled
    node types and 2 relationship types."""

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    def session(self, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, query, **params):
        if "elementId(null)" in query:
            class R:
                def consume(self):
                    return None
            return R()
        skip, limit = params.get("s", 0), params.get("l", 10 ** 9)
        if query.startswith("MATCH (n)"):
            rows = ([{"id": f"4:p:{i}", "labels": ["Person"], "props": {"name": f"Person {i}", "age": i}} for i in range(50)]
                    + [{"id": f"4:c:{i}", "labels": ["Company", "Org"], "props": {"name": f"Co {i}"}} for i in range(10)]
                    + [{"id": f"4:t:{i}", "labels": ["Town"], "props": {"title": f"Town {i}"}} for i in range(5)])
        else:
            rows = ([{"s": f"4:p:{i}", "p": "WORKS_AT", "t": f"4:c:{i % 10}"} for i in range(50)]
                    + [{"s": f"4:p:{i}", "p": "LIVES_IN", "t": f"4:t:{i % 5}"} for i in range(50)]
                    + [{"s": f"4:c:{i}", "p": "BASED_IN", "t": f"4:t:{i % 5}"} for i in range(10)])
        return rows[skip:skip + limit]


def test_neo4j_nodes_and_relationships_become_a_typed_graph(tmp_path, monkeypatch):
    fake = FakeNeo4j()
    monkeypatch.setattr(anydb, "neo4j_driver", lambda url: fake)
    schema = connect("neo4j://neo4j:pw@localhost:7687?database=crm", name="people")
    tables = {t.name: t for t in schema.tables}
    assert tables["entities"].row_count == 65 and tables["links"].row_count == 110
    assert tables["entities"].primary_key == ["id"]
    assert {(f.column, f.ref_table) for f in tables["links"].foreign_keys} == {("source", "entities"), ("target", "entities")}
    assert fake.closed
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source("neo4j://neo4j:pw@localhost:7687?database=crm", source="people")
    oid = simple.create_and_build(layer, "People", ["people"])["ontology"]
    v = simple.view(layer.graph, oid)
    assert {t["name"] for t in v["things"]} == {"Person", "Company", "Town"}
    labels = {l["label"] for l in v["links"]}
    assert {"Person works at Company", "Person lives in Town", "Company based in Town"} <= labels


def test_delta_lake_table(tmp_path):
    deltalake = pytest.importorskip("deltalake")
    import pyarrow as pa
    table = pa.table({"order_id": list(range(300)), "amount": [i * 1.5 for i in range(300)],
                      "region": ["N", "S", "E"] * 100})
    deltalake.write_deltalake(str(tmp_path / "orders"), table)
    schema = connect(str(tmp_path / "orders"))
    t = schema.tables[0]
    assert t.name == "orders" and t.row_count == 300 and t.primary_key == ["order_id"]
    assert any("Delta" in w for w in schema.warnings)
    assert connect(f"delta://{(tmp_path / 'orders').as_posix()}").tables[0].row_count == 300


def test_object_store_listing_logic_on_a_local_folder(tmp_path):
    import duckdb
    folder = tmp_path / "bucket" / "sales"
    (folder / "2024").mkdir(parents=True)
    (folder / "2024" / "jan.csv").write_text("id,v\n1,2\n3,4\n", encoding="utf-8")
    (folder / "2024" / "feb.csv").write_text("id,v\n5,6\n", encoding="utf-8")
    (folder / "readme.md").write_text("ignore", encoding="utf-8")
    schema = anydb._remote_files(duckdb.connect(), folder.as_posix(), "sales", [])
    assert sorted(t.name for t in schema.tables) == ["feb", "jan"]
    assert {t.name: t.row_count for t in schema.tables} == {"jan": 2, "feb": 1}
    with pytest.raises(anydb.AnyDbError, match="no Parquet, CSV or JSON"):
        anydb._remote_files(duckdb.connect(), (tmp_path / "bucket" / "nothing").as_posix(), None, [])


def test_parquet_writer_handles_mixed_and_missing_values(tmp_path):
    import datetime as dt
    import decimal
    import duckdb
    rows = [(1, "a", dt.datetime(2024, 1, 1, 10, 0, tzinfo=dt.timezone.utc), decimal.Decimal("1.50"), True, None),
            (None, None, None, None, None, b"\x00\x01"), ("3", "c", "not a date", "x", 0, b"")]
    n = anydb.write_parquet(tmp_path / "t.parquet", ["i", "s", "ts", "d", "b", "blob"],
                            [int, str, dt.datetime, decimal.Decimal, bool, bytes], [rows[:2], rows[2:]])
    assert n == 3
    got = duckdb.connect().execute(f"SELECT * FROM read_parquet('{(tmp_path / 't.parquet').as_posix()}')").fetchall()
    assert got[0][0] == 1 and got[0][3] == 1.5 and got[0][4] is True
    assert got[2][0] == 3 and got[2][2] is None and got[2][3] is None


def test_parquet_writer_trusts_values_over_the_driver_description(tmp_path):
    """A legacy ODBC driver says DATE but hands back text; values decide."""
    import datetime as dt
    import duckdb
    rows = [("2024-03-01", 1.5, 7), ("2024-03-02", 2, 8)]
    anydb.write_parquet(tmp_path / "t.parquet", ["d", "x", "n"], [dt.date, int, int], [rows])
    got = duckdb.connect().execute(
        f"SELECT typeof(d), typeof(x), typeof(n), count(*) FROM read_parquet('{(tmp_path / 't.parquet').as_posix()}') GROUP BY 1,2,3").fetchall()
    assert got == [("VARCHAR", "DOUBLE", "BIGINT", 2)]


def test_sqlite_file_reads_without_the_duckdb_extension(tmp_path, monkeypatch):
    """Application control can block DuckDB's sqlite extension; the file must
    still come in, keys and all, through Python's own sqlite3."""
    import sqlite3
    import duckdb
    from ontology import connect as connect_mod
    db = tmp_path / "shop.db"
    s = sqlite3.connect(db)
    s.executescript("""
        create table customer(id integer primary key, name text);
        create table orders(id integer primary key,
                            customer_id integer references customer(id), amount real);
        create view big as select * from orders where amount > 100;""")
    s.executemany("insert into customer values(?,?)", [(i, f"c{i}") for i in range(1, 11)])
    s.executemany("insert into orders values(?,?,?)", [(i, i % 10 + 1, i * 3.0) for i in range(1, 61)])
    s.commit()
    s.close()

    def blocked(con):
        raise duckdb.IOException("An Application Control policy has blocked this file.")

    monkeypatch.setattr(connect_mod, "_load_sqlite", blocked)
    schema = connect_mod.connect(str(db))
    tables = {t.name: t for t in schema.tables}
    assert set(tables) == {"customer", "orders", "big"}
    assert tables["orders"].row_count == 60 and tables["big"].row_count == 27
    assert tables["orders"].primary_key == ["id"]
    assert [(f.column, f.ref_table, f.ref_column) for f in tables["orders"].foreign_keys] == [
        ("customer_id", "customer", "id")]
    assert any("sqlite3" in w for w in schema.warnings)
    assert schema.origin == str(db)
