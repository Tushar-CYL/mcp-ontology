"""Real database servers in Docker: PostgreSQL, MySQL, SQL Server, MongoDB,
Neo4j. Each test starts one container, loads a small schema with declared
keys, connects through Strata by URL, builds an ontology, and stops the
container. Every test skips when no Docker engine is running, so the suite
is green on machines without Docker; run it where Docker exists to prove
the connectors against the real products.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import time

import pytest

from api.service import MiddleLayer
from ontology import simple
from ontology.connect import connect

PASSWORD = "Strata_Test_Pw1!"


def docker_ok() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except Exception:                              # noqa: BLE001
        return False


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Container:
    def __init__(self, image: str, port: int, env: dict, args: list[str] | None = None):
        self.port = free_port()
        cmd = ["docker", "run", "-d", "--rm", "-p", f"127.0.0.1:{self.port}:{port}"]
        for k, v in env.items():
            cmd += ["-e", f"{k}={v}"]
        cmd += [image] + (args or [])
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if out.returncode != 0:
            pytest.skip(f"could not start {image}: {out.stderr.strip()[:200]}")
        self.id = out.stdout.strip()

    def wait(self, probe, timeout=180):
        deadline = time.time() + timeout
        last = ""
        while time.time() < deadline:
            try:
                probe()
                return
            except Exception as exc:               # noqa: BLE001 - keep waiting
                last = str(exc)[:160]
                time.sleep(2)
        self.stop()
        pytest.fail(f"container did not become ready: {last}")

    def stop(self):
        subprocess.run(["docker", "rm", "-f", self.id], capture_output=True, timeout=120)


pytestmark = pytest.mark.skipif(not docker_ok(), reason="no Docker engine running")

DDL = [
    "CREATE TABLE customer (id INTEGER PRIMARY KEY, name VARCHAR(80), country VARCHAR(2))",
    # An explicit constraint: MySQL silently ignores an inline REFERENCES.
    "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, total DECIMAL(12,2), "
    "placed DATE, FOREIGN KEY (customer_id) REFERENCES customer(id))",
]


def seed(execute):
    for ddl in DDL:
        execute(ddl)
    for i in range(50):
        execute(f"INSERT INTO customer VALUES ({i}, 'Cust {i}', '{'DE' if i % 2 else 'FR'}')")
    for i in range(300):
        execute(f"INSERT INTO orders VALUES ({i}, {i % 50}, {i * 2.5}, '2024-03-{1 + i % 28:02d}')")


def check(schema):
    tables = {t.name: t for t in schema.tables}
    assert set(tables) >= {"customer", "orders"}, (set(tables), schema.warnings)
    assert tables["orders"].primary_key == ["id"]
    assert [(f.column, f.ref_table, f.ref_column) for f in tables["orders"].foreign_keys] == \
        [("customer_id", "customer", "id")]
    assert tables["orders"].row_count == 300 and tables["customer"].row_count == 50, schema.warnings


def journey(tmp_path, url, name):
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(url, source=name)
    oid = simple.create_and_build(layer, name, [name])["ontology"]
    v = simple.view(layer.graph, oid)
    assert {t["name"] for t in v["things"]} >= {"Customer", "Order"}
    assert any(l["from_thing"] == "Order" and l["to_thing"] == "Customer" and l["match"] == 1.0
               for l in v["links"])
    return v


def test_postgresql(tmp_path):
    c = Container("postgres:16-alpine", 5432, {"POSTGRES_PASSWORD": PASSWORD, "POSTGRES_DB": "shop"})
    import psycopg

    def probe():
        with psycopg.connect(f"postgresql://postgres:{PASSWORD}@127.0.0.1:{c.port}/shop", connect_timeout=3) as conn:
            conn.execute("SELECT 1")
    try:
        c.wait(probe)
        with psycopg.connect(f"postgresql://postgres:{PASSWORD}@127.0.0.1:{c.port}/shop") as conn:
            seed(lambda q: conn.execute(q))
            conn.commit()
        # Both ways in: DuckDB's extension (postgres://) and the driver (postgresql+psycopg://).
        check(connect(f"postgres://postgres:{PASSWORD}@127.0.0.1:{c.port}/shop", name="pg"))
        check(connect(f"postgresql+psycopg://postgres:{PASSWORD}@127.0.0.1:{c.port}/shop", name="pg2"))
        journey(tmp_path, f"postgres://postgres:{PASSWORD}@127.0.0.1:{c.port}/shop", "pg")
    finally:
        c.stop()


def test_mysql(tmp_path):
    c = Container("mysql:8.4", 3306, {"MYSQL_ROOT_PASSWORD": PASSWORD, "MYSQL_DATABASE": "shop"})
    import pymysql

    def probe():
        pymysql.connect(host="127.0.0.1", port=c.port, user="root", password=PASSWORD, database="shop",
                        connect_timeout=3).close()
    try:
        c.wait(probe, timeout=240)
        conn = pymysql.connect(host="127.0.0.1", port=c.port, user="root", password=PASSWORD, database="shop")
        with conn.cursor() as cur:
            seed(lambda q: cur.execute(q))
        conn.commit()
        conn.close()
        check(connect(f"mysql://root:{PASSWORD}@127.0.0.1:{c.port}/shop", name="my"))
        journey(tmp_path, f"mysql://root:{PASSWORD}@127.0.0.1:{c.port}/shop", "my")
    finally:
        c.stop()


def test_sql_server(tmp_path):
    import pyodbc
    if not any("SQL Server" in d for d in pyodbc.drivers()):
        pytest.skip("no SQL Server ODBC driver")
    c = Container("mcr.microsoft.com/mssql/server:2022-latest", 1433,
                  {"ACCEPT_EULA": "Y", "MSSQL_SA_PASSWORD": PASSWORD, "MSSQL_PID": "Express"})
    driver = next(d for d in pyodbc.drivers() if "SQL Server" in d)
    dsn = f"Driver={{{driver}}};Server=127.0.0.1,{c.port};UID=sa;PWD={PASSWORD};TrustServerCertificate=yes;"

    def probe():
        pyodbc.connect(dsn + "Database=master;", timeout=3).close()
    try:
        c.wait(probe, timeout=300)
        conn = pyodbc.connect(dsn + "Database=master;", autocommit=True)
        conn.execute("CREATE DATABASE shop")
        conn.close()
        conn = pyodbc.connect(dsn + "Database=shop;", autocommit=True)
        seed(lambda q: conn.execute(q))
        conn.close()
        check(connect(f"odbc://{dsn}Database=shop;", name="mssql"))
        check(connect(f"mssql://sa:{PASSWORD}@127.0.0.1:{c.port}/shop?driver={driver.replace(' ', '+')}"
                      "&TrustServerCertificate=yes", name="mssql2"))
        journey(tmp_path, f"odbc://{dsn}Database=shop;", "mssql")
    finally:
        c.stop()


def test_mongodb(tmp_path):
    c = Container("mongo:7", 27017, {})
    from pymongo import MongoClient

    def probe():
        MongoClient(f"mongodb://127.0.0.1:{c.port}", serverSelectionTimeoutMS=2000).admin.command("ping")
    try:
        c.wait(probe)
        client = MongoClient(f"mongodb://127.0.0.1:{c.port}")
        db = client["crm"]
        db.contacts.insert_many([{"name": f"P{i}", "age": 20 + i, "address": {"city": "Pune"}} for i in range(40)])
        db.deals.insert_many([{"deal": i, "amount": i * 100.0, "contact": f"P{i % 40}"} for i in range(80)])
        client.close()
        schema = connect(f"mongodb://127.0.0.1:{c.port}/crm", name="crm")
        tables = {t.name: t for t in schema.tables}
        assert set(tables) == {"contacts", "deals"} and tables["contacts"].row_count == 40
        layer = MiddleLayer(str(tmp_path / "g.duckdb"))
        layer.add_source(f"mongodb://127.0.0.1:{c.port}/crm", source="crm")
        oid = simple.create_and_build(layer, "CRM", ["crm"])["ontology"]
        assert {t["name"] for t in simple.view(layer.graph, oid)["things"]} == {"Contact", "Deal"}
    finally:
        c.stop()


def test_neo4j(tmp_path):
    c = Container("neo4j:5", 7687, {"NEO4J_AUTH": f"neo4j/{PASSWORD}"})
    from neo4j import GraphDatabase

    def probe():
        with GraphDatabase.driver(f"bolt://127.0.0.1:{c.port}", auth=("neo4j", PASSWORD)) as d:
            d.verify_connectivity()
    try:
        c.wait(probe, timeout=300)
        with GraphDatabase.driver(f"bolt://127.0.0.1:{c.port}", auth=("neo4j", PASSWORD)) as d, d.session() as s:
            s.run("UNWIND range(0, 9) AS i CREATE (:Company {name: 'Co ' + i})")
            s.run("UNWIND range(0, 49) AS i CREATE (:Person {name: 'Person ' + i, age: 20 + i})")
            s.run("MATCH (p:Person), (c:Company) WHERE toInteger(substring(p.name, 7)) % 10 = toInteger(substring(c.name, 3)) "
                  "CREATE (p)-[:WORKS_AT]->(c)")
        url = f"neo4j://neo4j:{PASSWORD}@127.0.0.1:{c.port}"
        schema = connect(url, name="people")
        assert {t.name: t.row_count for t in schema.tables} == {"entities": 60, "links": 50}
        layer = MiddleLayer(str(tmp_path / "g.duckdb"))
        layer.add_source(url, source="people")
        oid = simple.create_and_build(layer, "People", ["people"])["ontology"]
        v = simple.view(layer.graph, oid)
        assert {t["name"] for t in v["things"]} == {"Person", "Company"}
        assert any(l["label"] == "Person works at Company" for l in v["links"])
    finally:
        c.stop()
