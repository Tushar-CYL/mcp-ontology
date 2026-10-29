"""A CSV declares no primary key. One has to be found, or nothing works.

On the Olist export every class came out with a made-up `__row` key. That
is not a cosmetic problem: an edge is built by matching a child's column
against a parent's KEY, so with the wrong key on the parent nothing joins
and the graph is empty.

`customer_id` in the customers file IS the key - it is unique and never
null. That is readable from the data itself, by counting.
"""

from __future__ import annotations

from ontology.keys import pick_key
from ontology.schema import Column, Table


def col(name, type_="VARCHAR", distinct=None, nullable=True):
    return Column(name, type_, nullable=nullable, distinct=distinct)


def tbl(name, cols, rows):
    return Table(name=name, columns=list(cols), row_count=rows)


class TestPickKey:
    def test_a_unique_non_null_column_is_the_key(self):
        t = tbl("customers", [col("customer_id", distinct=100, nullable=False),
                              col("city", distinct=12)], rows=100)
        assert pick_key(t) == "customer_id"

    def test_a_column_with_repeats_is_not_a_key(self):
        t = tbl("orders", [col("city", distinct=12)], rows=100)
        assert pick_key(t) is None

    def test_a_key_named_after_its_own_table_wins(self):
        """Both are unique. `customer_id` in `customers` is the identity;
        `email` merely happens to be unique too."""
        t = tbl("customers", [col("email", distinct=100, nullable=False),
                              col("customer_id", distinct=100, nullable=False)],
                rows=100)
        assert pick_key(t) == "customer_id"

    def test_plain_id_wins_over_an_unrelated_unique_column(self):
        t = tbl("things", [col("serial", distinct=50, nullable=False),
                           col("id", distinct=50, nullable=False)], rows=50)
        assert pick_key(t) == "id"

    def test_a_nullable_unique_column_is_rejected(self):
        """A null key cannot identify a row, and would quietly drop it."""
        t = tbl("customers", [col("customer_id", distinct=100, nullable=True)],
                rows=100)
        assert pick_key(t) is None

    def test_unprofiled_columns_give_no_key_rather_than_a_guess(self):
        """distinct=None means nobody counted. Guessing would be worse than
        admitting we do not know."""
        t = tbl("customers", [col("customer_id", nullable=False)], rows=100)
        assert pick_key(t) is None

    def test_empty_table_has_no_key(self):
        t = tbl("empty", [col("id", distinct=0, nullable=False)], rows=0)
        assert pick_key(t) is None

    def test_a_measure_is_never_chosen_as_a_key(self):
        """100 distinct prices across 100 rows is a coincidence, not an
        identity, and using it would wreck every join."""
        t = tbl("sales", [col("price", "DOUBLE", distinct=100, nullable=False)],
                rows=100)
        assert pick_key(t) is None

    def test_a_timestamp_is_never_chosen_as_a_key(self):
        t = tbl("events", [col("happened_at", "TIMESTAMP", distinct=100,
                               nullable=False)], rows=100)
        assert pick_key(t) is None
