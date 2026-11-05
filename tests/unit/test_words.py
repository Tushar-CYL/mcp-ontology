"""Words in enterprise names: SAP exports write SALESDOCUMENT, SOLDTOPARTY,
CUSTOMERPAYMENTTERMS with no separators. Every naming decision in the
ontology (concept names, property names, synonyms) goes through here."""

from __future__ import annotations

import pytest

from ontology.words import display_name, segment, words


@pytest.mark.parametrize("raw, expected", [
    ("salesdocument", ["sales", "document"]),
    ("soldtoparty", ["sold", "to", "party"]),
    ("customerpaymentterms", ["customer", "payment", "terms"]),
    ("distributionchannel", ["distribution", "channel"]),
    ("incotermsclassification", ["incoterms", "classification"]),
    ("shippingpoint", ["shipping", "point"]),
    ("payerparty", ["payer", "party"]),
    ("salesdocumentitemcategory", ["sales", "document", "item", "category"]),
    ("condition", ["condition"]),                 # longest match wins over "on"
    ("xqzvbn", ["xqzvbn"]),                       # unknown stays whole
])
def test_segment_run_together_words(raw, expected):
    assert segment(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("SOLDTOPARTY", ["sold", "to", "party"]),
    ("SalesOrganization", ["sales", "organization"]),
    ("billing_ref", ["billing", "ref"]),
    ("NETWR_USD", ["netwr", "usd"]),
    ("AMT_01", ["amt", "01"]),
])
def test_words_handles_every_casing(raw, expected):
    assert words(raw) == expected


@pytest.mark.parametrize("table, expected", [
    ("i_salesdocumentitem", "SalesDocumentItem"),
    ("salesdocuments", "SalesDocument"),
    ("I_Customer", "Customer"),
    ("sales_orders", "SalesOrder"),
    ("golden_customers", "Customer"),
    ("sales_monthly", "SalesMonthly"),
    ("accounts", "Account"),
    ("invoices", "Invoice"),
])
def test_display_names_for_tables(table, expected):
    assert display_name(table) == expected
