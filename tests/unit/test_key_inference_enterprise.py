"""Key and link inference on real enterprise exports.

Found on the BI/MDM scenario: ERP customers were keyed on the company NAME
(unique, but a name is not an identity), billing accounts on tax_id instead
of billing_ref, and SAP order numbers (VBELN) were ignored because they are
numeric - so orders got a synthetic row number and nothing linked. A key
should be an identifier, and a column carrying another table's key name is a
link (sales_orders.KUNNR -> customers.KUNNR).
"""

from __future__ import annotations

import pytest

from ontology.discover import discover
from ontology.keys import pick_key
from ontology.schema import Column, Schema, Table


def _table(name, cols, rows=100):
    return Table(name=name, row_count=rows, columns=[
        Column(name=c, type=t, nullable=False, distinct=d) for c, t, d in cols])


@pytest.mark.parametrize("cols, expected", [
    # SAP customer master: numeric KUNNR beats a unique company name.
    ([("KUNNR", "BIGINT", 100), ("NAME1", "VARCHAR", 100), ("LAND1", "VARCHAR", 9)],
     "KUNNR"),
    # *_ref is an identifier; tax_id is unique too but is an attribute.
    ([("billing_ref", "VARCHAR", 100), ("bill_to_name", "VARCHAR", 100),
      ("tax_id", "VARCHAR", 100)], "billing_ref"),
    # SAP sales document number.
    ([("VBELN", "BIGINT", 100), ("KUNNR", "BIGINT", 40), ("NETWR", "DOUBLE", 100)],
     "VBELN"),
    # The classic still wins.
    ([("name", "VARCHAR", 100), ("customer_id", "VARCHAR", 100)], "customer_id"),
    # A unique amount is never a key.
    ([("amount", "DOUBLE", 100), ("note", "VARCHAR", 3)], None),
])
def test_identity_columns_win_over_unique_attributes(cols, expected):
    table = _table("customers" if expected != "VBELN" else "sales_orders", cols)
    assert pick_key(table) == expected


def test_a_name_column_is_never_preferred_over_an_identifier():
    table = _table("accounts", [("account_name", "VARCHAR", 100),
                                ("acct_no", "VARCHAR", 100)])
    assert pick_key(table) == "acct_no"


@pytest.mark.parametrize("table, cols, expected", [
    # One invoice per order makes order_ref unique, but it points elsewhere.
    ("invoices", [("inv_id", "VARCHAR"), ("cust_ref", "VARCHAR"),
                  ("order_ref", "VARCHAR")], "inv_id"),
    ("accounts", [("owner_ref", "VARCHAR"), ("acct_id", "VARCHAR")], "acct_id"),
    ("purchase_orders", [("vendor_no", "VARCHAR"), ("po_no", "VARCHAR")], "po_no"),
])
def test_an_abbreviation_of_the_tables_own_name_wins(table, cols, expected):
    t = _table(table, [(c, ty, 100) for c, ty in cols])
    assert pick_key(t) == expected


def test_a_column_carrying_another_tables_key_name_is_a_link():
    customers = _table("customers", [("KUNNR", "BIGINT", 100), ("NAME1", "VARCHAR", 100)])
    customers.primary_key = ["KUNNR"]
    orders = _table("sales_orders", [("VBELN", "BIGINT", 500), ("KUNNR", "BIGINT", 90)],
                    rows=500)
    orders.primary_key = ["VBELN"]
    onto = discover(Schema(tables=[customers, orders], name="erp"))
    links = [(r.domain, r.range, r.column, r.provenance) for r in onto.relations.values()]
    assert ("SalesOrder", "Customer", "KUNNR", "derived") in links


def test_a_tables_own_key_is_not_a_link_to_itself():
    customers = _table("customers", [("KUNNR", "BIGINT", 100)])
    customers.primary_key = ["KUNNR"]
    onto = discover(Schema(tables=[customers], name="erp"))
    assert not onto.relations
