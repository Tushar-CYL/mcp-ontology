"""How records look to a person: one icon per kind of thing, and the fields
that could serve as a record's readable name (plan step 1.1).

Icons are picked from the thing's own name ("Sales Document" is an order,
"Zip Code Geolocation" is a place), so every page and agent shows the same
one. Name candidates come from the data: text fields that are not ids, links
or personal data, with how many distinct values they hold and one example."""

from __future__ import annotations

import re

# Checked in order: the first match wins, so "Order Line" is a line and
# "Order Review" a review before either is taken for an order.
_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("line", ("line", "item", "position", "detail")),
    ("review", ("review", "rating", "feedback", "survey")),
    ("payment", ("payment", "transaction", "receipt", "refund")),
    ("order", ("order", "sale", "sales", "purchase", "booking", "quote", "quotation")),
    ("document", ("invoice", "bill", "billing", "credit note", "contract", "document")),
    ("person", ("customer", "client", "person", "people", "user", "employee", "patient",
                "member", "contact", "account", "partner", "staff", "doctor")),
    ("store", ("seller", "vendor", "supplier", "store", "shop", "merchant", "plant", "company")),
    ("product", ("product", "material", "sku", "article", "goods", "part", "catalog")),
    ("place", ("geolocation", "location", "address", "zip", "postal", "city", "country",
               "region", "site", "warehouse", "geo")),
    ("device", ("sensor", "device", "machine", "meter", "asset", "equipment")),
    ("event", ("event", "visit", "appointment", "shipment", "delivery", "reading", "log")),
]
ICONS = tuple(sorted({icon for icon, _ in _RULES} | {"thing"}))


def icon(thing: str) -> str:
    words = " " + " ".join(re.findall(r"[a-z]+", str(thing).lower())) + " "
    for name, keys in _RULES:
        if any(f" {k} " in words or f" {k}s " in words for k in keys):
            return name
    return "thing"


NAME_ROLES = ("name", "category", "flag", "text", "location")
MAX_CANDIDATES = 6


def name_candidates(layer, ontology_id: str, thing_key: str) -> list[dict]:
    """Fields that could be this thing's readable name, read from the data:
    [{column, label, distinct, example}], most distinct first."""
    from knowledge_graph import explore as kg
    from ontology import simple
    from knowledge_graph.build import qi
    v = simple.view(layer.graph, ontology_id)
    thing = next((t for t in v["things"] if t["key"] == thing_key), None)
    if thing is None:
        raise KeyError(f"no thing {thing_key!r} in ontology {ontology_id!r}")
    m = kg.model(layer, ontology_id)
    sets = [s for s in m["sets"].values() if s["thing"] == thing["name"]]
    out = []
    for s in sets:
        for f in s["fields"]:
            if f.get("personal") or f["role"] not in NAME_ROLES                     or "CHAR" not in str(f.get("type") or "VARCHAR").upper():
                continue
            col = qi(f["column"])
            try:
                n, example = layer.graph.sql(
                    f"SELECT approx_count_distinct({col}), any_value(CAST({col} AS VARCHAR))"
                    f" FROM {s['ref']} WHERE {col} IS NOT NULL")[0]
            except Exception:                  # noqa: BLE001 - an unreadable column is no candidate
                continue
            if not n:
                continue
            out.append({"column": f["column"], "label": f.get("label") or f["column"],
                        "distinct": int(n), "example": example})
    out.sort(key=lambda c: -c["distinct"])
    return out[:MAX_CANDIDATES]
