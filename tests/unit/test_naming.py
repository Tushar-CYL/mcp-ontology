"""Real exports do not have clean table names.

Found on the Olist dataset: nine CSVs named `olist_customers_dataset`,
`olist_orders_dataset`, `product_category_name_translation`. Two things
broke at once.

  The class names came out as `OlistCustomersDataset` - unreadable, and
  unusable in front of anyone.

  NOT ONE relationship was found. `customer_id` looks for a table called
  `customer`; the table is called `olist_customers_dataset`, so the match
  failed and the graph had zero edges. The data was fine; the matching was
  too literal.

Both are fixed by stripping noise before matching, and both are tested here
on names taken from real exports rather than invented ones.
"""

from __future__ import annotations

import pytest

from ontology.discover import class_name, core_name, strip_common_prefix
from ontology.schema import Column, Schema, Table


def tbl(name, cols=(("id", "INTEGER"),)):
    return Table(name=name, columns=[Column(n, t) for n, t in cols])


class TestCoreName:
    """The meaningful part of a table name, with export noise removed."""

    @pytest.mark.parametrize("raw,want", [
        # `olist` is NOT stripped here. A single name cannot tell an
        # export prefix from a real word - only seeing every table can.
        ("olist_customers_dataset", "olist_customers"),
        ("olist_orders_dataset", "olist_orders"),
        ("customers_table", "customers"),
        ("tbl_customers", "customers"),
        ("dim_customer", "customer"),
        ("fact_sales", "sales"),
        ("stg_orders", "orders"),
        ("customers_raw", "customers"),
        ("customers_final_v2", "customers"),
        ("customers", "customers"),
        ("product_category_name_translation", "product_category_name_translation"),
    ])
    def test_noise_is_stripped(self, raw, want):
        assert core_name(raw) == want

    def test_a_name_that_is_all_noise_survives(self):
        """Stripping everything would leave nothing to call the class."""
        assert core_name("dataset") == "dataset"
        assert core_name("data") == "data"


class TestCommonPrefix:
    """A prefix shared by every table is the export's name, not the data's."""

    def test_shared_prefix_is_removed(self):
        names = ["olist_customers", "olist_orders", "olist_sellers"]
        assert strip_common_prefix(names) == ["customers", "orders", "sellers"]

    def test_a_clear_majority_is_enough(self):
        """Requiring EVERY table to share the prefix was too strict. The
        real Olist export has `olist_` on eight of nine files, and the one
        exception left every class called OlistSomething."""
        names = ["olist_customers", "olist_orders", "payments"]
        assert strip_common_prefix(names) == ["customers", "orders", "payments"]

    def test_the_odd_table_out_keeps_its_own_name(self):
        names = ["olist_customers", "olist_orders", "olist_sellers",
                 "product_category_translation"]
        assert strip_common_prefix(names) == [
            "customers", "orders", "sellers", "product_category_translation"]

    def test_a_minority_prefix_is_kept(self):
        """One table in three is not an export prefix, it is a word."""
        names = ["olist_customers", "orders", "payments"]
        assert strip_common_prefix(names) == names

    def test_a_single_table_keeps_its_name(self):
        """With one table everything is a 'common' prefix. Stripping it
        would leave nothing."""
        assert strip_common_prefix(["olist_customers"]) == ["olist_customers"]

    def test_prefix_is_not_stripped_if_it_empties_a_name(self):
        names = ["olist", "olist_orders"]
        assert strip_common_prefix(names) == names


class TestClassName:
    def test_noisy_export_names_become_readable(self):
        """class_name sees one name, so it strips noise words only. The
        shared `olist_` prefix is removed by discover(), which sees all
        of them - tested below."""
        assert class_name("customers_dataset") == "Customer"
        assert class_name("order_items_dataset") == "OrderItem"

    def test_clean_names_are_unaffected(self):
        assert class_name("customers") == "Customer"
        assert class_name("order_items") == "OrderItem"


class TestRelationMatchingAcrossNoisyNames:
    """The failure that produced a graph with zero edges."""

    def test_column_matches_a_noisy_table_name(self):
        from ontology.discover import discover
        onto = discover(Schema(tables=[
            tbl("olist_customers_dataset", [("customer_id", "VARCHAR")]),
            tbl("olist_orders_dataset",
                [("order_id", "VARCHAR"), ("customer_id", "VARCHAR")]),
        ]))
        rels = list(onto.relations.values())
        assert len(rels) == 1, "orders.customer_id must find the customers table"
        assert rels[0].domain == "Order"
        assert rels[0].range == "Customer"
        assert rels[0].provenance == "derived"      # nothing was declared

    def test_the_whole_olist_shape_connects_up(self):
        """Table and column names taken verbatim from the real export."""
        from ontology.discover import discover
        onto = discover(Schema(tables=[
            tbl("olist_customers_dataset", [("customer_id", "VARCHAR")]),
            tbl("olist_orders_dataset", [("order_id", "VARCHAR"),
                                         ("customer_id", "VARCHAR")]),
            tbl("olist_order_items_dataset", [("order_id", "VARCHAR"),
                                              ("product_id", "VARCHAR"),
                                              ("seller_id", "VARCHAR")]),
            tbl("olist_products_dataset", [("product_id", "VARCHAR")]),
            tbl("olist_sellers_dataset", [("seller_id", "VARCHAR")]),
            tbl("olist_order_payments_dataset", [("order_id", "VARCHAR")]),
            tbl("olist_order_reviews_dataset", [("review_id", "VARCHAR"),
                                                ("order_id", "VARCHAR")]),
        ]))
        pairs = {(r.domain, r.range) for r in onto.relations.values()}
        assert ("Order", "Customer") in pairs
        assert ("OrderItem", "Order") in pairs
        assert ("OrderItem", "Product") in pairs
        assert ("OrderItem", "Seller") in pairs
        assert ("OrderPayment", "Order") in pairs
        assert ("OrderReview", "Order") in pairs

    def test_a_table_does_not_link_to_itself_through_its_own_key(self):
        """orders.order_id is the key OF orders, not a link TO orders."""
        from ontology.discover import discover
        onto = discover(Schema(tables=[
            tbl("olist_orders_dataset", [("order_id", "VARCHAR"),
                                         ("customer_id", "VARCHAR")]),
            tbl("olist_customers_dataset", [("customer_id", "VARCHAR")]),
        ]))
        assert not any(r.domain == r.range for r in onto.relations.values())
