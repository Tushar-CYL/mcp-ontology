"""Your data at a glance: charts chosen from the ontology, before any question."""

from __future__ import annotations

from api.service import MiddleLayer
from context.insights import insights
from ontology import simple
from tests.integration.test_declared_links import make_shop


def test_key_numbers_and_charts_come_from_the_data(tmp_path):
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(make_shop(tmp_path / "shop.db")), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    out = insights(layer, oid)
    kpi = {k["label"]: k["value"] for k in out["kpis"]}
    assert kpi["Order Line records"] > 1900 and any(v == 1000 for v in kpi.values())
    assert any(label.startswith("Total ") for label in kpi)            # a money total
    by_title = {c["title"]: c for c in out["charts"]}
    country = next(c for t, c in by_title.items() if "by Country" in t and "records" in t)
    assert dict(zip(country["x"], country["y"])) == {"IN": 100, "GB": 100}
    # Order status has one value ("paid"): a one-bar chart says nothing, so none.
    assert not any("by Status" in t for t in by_title)
    assert all(c["question"] for c in out["charts"]) and out["questions"]
    assert not any("email" in str(c).lower() for c in out["charts"])   # never personal data


def test_the_most_connected_thing_leads_not_the_biggest_table(tmp_path):
    """Olist opened with a 1M-row zip table that links to nothing."""
    import sqlite3
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    db = make_shop(tmp_path / "shop.db")
    s = sqlite3.connect(db)
    s.execute("create table zip_lookup(zip text, city text)")
    s.executemany("insert into zip_lookup values(?,?)", [(f"{i:05d}", "x") for i in range(5000)])
    s.commit()
    s.close()
    layer.add_source(str(db), source="shop")
    oid = simple.create_and_build(layer, "Shop", ["shop"])["ontology"]
    first = insights(layer, oid)["kpis"][0]["label"]
    assert "Zip" not in first and "Lookup" not in first


def test_an_unfinished_last_month_is_not_drawn_as_a_cliff(tmp_path):
    import sqlite3
    db = tmp_path / "t.db"
    s = sqlite3.connect(db)
    s.execute("create table sale(id integer primary key, placed timestamp, amount real)")
    rows, i = [], 0
    for month, n in (("2024-01", 100), ("2024-02", 120), ("2024-03", 110), ("2024-04", 2)):
        for k in range(n):
            i += 1
            rows.append((i, f"{month}-{k % 28 + 1:02d} 10:00:00", 5.0))
    s.executemany("insert into sale values(?,?,?)", rows)
    s.commit()
    s.close()
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    layer.add_source(str(db), source="t")
    oid = simple.create_and_build(layer, "T", ["t"])["ontology"]
    line = next((c for c in insights(layer, oid)["charts"] if c["kind"] == "line"), None)
    if line is None:
        import pytest
        pytest.skip("no date role on this tiny table without AI")
    assert line["x"][-1] == "2024-03"


def test_several_graph_sources_give_one_set_of_charts(tmp_path):
    """Live: an ontology built from three CSKG folders showed every graph
    chart and the Entities number three times."""
    from tests.integration.test_graph_ontology import write_cskg
    layer = MiddleLayer(str(tmp_path / "g.duckdb"))
    for i in range(3):
        layer.add_source(str(write_cskg(tmp_path / f"cskg{i}")), source=f"kg{i}")
    oid = simple.create_and_build(layer, "KG", ["kg0", "kg1", "kg2"])["ontology"]
    out = insights(layer, oid)
    titles = [c["title"] for c in out["charts"]]
    assert len(titles) == len(set(titles)) and titles.count("Entities by type") == 1
    labels = [k["label"] for k in out["kpis"]]
    assert labels.count("Entities") == 1
    assert len(out["questions"]) == len(set(out["questions"]))
    hubs = next(c for c in out["charts"] if c["title"] == "Most connected entities")
    assert len(hubs["x"]) == len(set(hubs["x"]))              # each entity once, summed
