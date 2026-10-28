"""Layer 1: a schema goes in, an ontology comes out.

These tests exist before the code because they ARE the specification. If
discovery cannot turn a plain schema into classes and relations without
being told anything, the product claim is false and nothing downstream
matters.

Nothing here touches a database. A Schema is a plain object, so the rules
can be tested on shapes a real source would be tedious to produce.
"""

from __future__ import annotations

import pytest

from ontology.schema import Column, ForeignKey, Schema, Table
from ontology.discover import discover


def tbl(name, cols, pk=None, fks=(), rows=100):
    return Table(
        name=name,
        columns=[Column(n, t) for n, t in cols],
        primary_key=list(pk or []),
        foreign_keys=list(fks),
        row_count=rows,
    )


SHOP = Schema(tables=[
    tbl("customers", [("id", "INTEGER"), ("name", "VARCHAR"),
                      ("country", "VARCHAR")], pk=["id"]),
    tbl("orders", [("id", "INTEGER"), ("customer_id", "INTEGER"),
                   ("placed_at", "TIMESTAMP"), ("total", "DOUBLE")],
        pk=["id"],
        fks=[ForeignKey("customer_id", "customers", "id")]),
])


# ------------------------------------------------------------------ classes
class TestClasses:
    def test_every_table_becomes_a_class(self):
        onto = discover(SHOP)
        assert set(onto.classes) == {"Customer", "Order"}

    def test_table_name_is_singularised_and_capitalised(self):
        onto = discover(Schema(tables=[
            tbl("companies", [("id", "INTEGER")], pk=["id"]),
            tbl("people", [("id", "INTEGER")], pk=["id"]),
            tbl("order_items", [("id", "INTEGER")], pk=["id"]),
            tbl("status", [("id", "INTEGER")], pk=["id"]),
        ]))
        assert set(onto.classes) == {"Company", "Person", "OrderItem", "Status"}

    def test_primary_key_becomes_the_class_key(self):
        assert discover(SHOP).classes["Customer"].key == "id"

    def test_class_remembers_where_it_came_from(self):
        c = discover(SHOP).classes["Customer"]
        assert c.table == "customers"
        assert c.provenance == "measured"

    def test_table_without_primary_key_still_becomes_a_class(self):
        """A CSV has no declared key. Falling over here would rule out every
        file-based source, so a synthetic key is used and marked as such."""
        onto = discover(Schema(tables=[
            tbl("events", [("name", "VARCHAR"), ("at", "TIMESTAMP")])]))
        assert "Event" in onto.classes
        assert onto.classes["Event"].key_is_synthetic is True

    def test_codes_are_stable_across_runs(self):
        """Codes are stored as smallint on every row. If discovery renumbered
        them between runs, a rebuild would silently reinterpret the graph."""
        a = {n: c.code for n, c in discover(SHOP).classes.items()}
        b = {n: c.code for n, c in discover(SHOP).classes.items()}
        assert a == b
        assert len(set(a.values())) == len(a)


# ---------------------------------------------------------------- relations
class TestRelations:
    def test_declared_foreign_key_becomes_a_relation(self):
        onto = discover(SHOP)
        rels = [r for r in onto.relations.values() if r.domain == "Order"]
        assert len(rels) == 1
        assert rels[0].range == "Customer"

    def test_declared_foreign_key_is_measured_not_inferred(self):
        onto = discover(SHOP)
        r = next(r for r in onto.relations.values() if r.domain == "Order")
        assert r.provenance == "measured"
        assert r.confidence == 1.0

    def test_relation_is_named_from_the_column_not_the_table(self):
        """Two columns pointing at the same table must not collide."""
        onto = discover(Schema(tables=[
            tbl("people", [("id", "INTEGER")], pk=["id"]),
            tbl("messages", [("id", "INTEGER"), ("sender_id", "INTEGER"),
                             ("recipient_id", "INTEGER")], pk=["id"],
                fks=[ForeignKey("sender_id", "people", "id"),
                     ForeignKey("recipient_id", "people", "id")]),
        ]))
        names = {r.name for r in onto.relations.values()}
        assert "sender" in names and "recipient" in names

    def test_column_named_after_a_table_is_an_inferred_relation(self):
        """No declared FK - the usual case for CSV and for warehouses where
        constraints were never created."""
        onto = discover(Schema(tables=[
            tbl("customers", [("id", "INTEGER")], pk=["id"]),
            tbl("orders", [("id", "INTEGER"), ("customer_id", "INTEGER")],
                pk=["id"]),
        ]))
        r = next(r for r in onto.relations.values() if r.domain == "Order")
        assert r.range == "Customer"
        assert r.provenance == "derived"
        assert r.confidence < 1.0

    def test_a_guess_is_never_reported_as_a_fact(self):
        """The whole system rests on being able to tell these apart."""
        onto = discover(Schema(tables=[
            tbl("customers", [("id", "INTEGER")], pk=["id"]),
            tbl("orders", [("id", "INTEGER"), ("customer_id", "INTEGER")],
                pk=["id"]),
        ]))
        for r in onto.relations.values():
            if r.confidence < 1.0:
                assert r.provenance == "derived"

    def test_self_reference_is_allowed(self):
        onto = discover(Schema(tables=[
            tbl("employees", [("id", "INTEGER"), ("manager_id", "INTEGER")],
                pk=["id"], fks=[ForeignKey("manager_id", "employees", "id")])]))
        r = next(iter(onto.relations.values()))
        assert r.domain == r.range == "Employee"

    def test_primary_key_is_not_mistaken_for_a_relation(self):
        onto = discover(SHOP)
        assert not any(r.column == "id" for r in onto.relations.values())


# --------------------------------------------------------------------- time
class TestTime:
    def test_timestamp_column_becomes_the_validity_time(self):
        assert discover(SHOP).classes["Order"].time_column == "placed_at"

    def test_table_without_a_date_has_no_time(self):
        assert discover(SHOP).classes["Customer"].time_column is None

    def test_earliest_sounding_name_wins_when_several_dates_exist(self):
        """created_at is when the row became true; updated_at is when someone
        last touched it. Validity starts at the former."""
        onto = discover(Schema(tables=[
            tbl("orders", [("id", "INTEGER"), ("updated_at", "TIMESTAMP"),
                           ("created_at", "TIMESTAMP")], pk=["id"])]))
        assert onto.classes["Order"].time_column == "created_at"


# ----------------------------------------------------------------- measures
class TestMeasures:
    def test_numeric_column_becomes_a_measure(self):
        assert "total" in discover(SHOP).classes["Order"].measures

    def test_key_and_foreign_key_columns_are_not_measures(self):
        m = discover(SHOP).classes["Order"].measures
        assert "id" not in m and "customer_id" not in m

    def test_text_column_becomes_a_dimension(self):
        assert "country" in discover(SHOP).classes["Customer"].dimensions


# ------------------------------------------------------------------ renames
class TestRenames:
    def test_a_name_can_be_overridden_without_changing_code(self):
        """Structure is readable from the data; business names are not. The
        override is stored, never coded."""
        onto = discover(SHOP, names={"customers": "Buyer"})
        assert "Buyer" in onto.classes
        assert "Customer" not in onto.classes
        assert onto.classes["Buyer"].table == "customers"

    def test_renaming_keeps_relations_pointing_at_the_right_class(self):
        onto = discover(SHOP, names={"customers": "Buyer"})
        r = next(r for r in onto.relations.values() if r.domain == "Order")
        assert r.range == "Buyer"


# ------------------------------------------------------------------- safety
class TestSafety:
    def test_empty_schema_is_an_error_not_an_empty_ontology(self):
        """Silently producing nothing would look like success."""
        with pytest.raises(ValueError, match="no tables"):
            discover(Schema(tables=[]))

    def test_duplicate_class_names_do_not_overwrite_each_other(self):
        """'person' and 'people' both singularise to Person."""
        onto = discover(Schema(tables=[
            tbl("person", [("id", "INTEGER")], pk=["id"]),
            tbl("people", [("id", "INTEGER")], pk=["id"]),
        ]))
        assert len(onto.classes) == 2
        assert {c.table for c in onto.classes.values()} == {"person", "people"}
