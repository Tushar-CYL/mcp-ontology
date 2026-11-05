"""Words in enterprise names.

Exports name things every way at once: ``sales_orders``, ``SalesOrganization``,
``NETWR_USD`` and, from SAP, run-together capitals like ``SOLDTOPARTY``. Every
naming decision in the ontology (concept names, proposed property names,
synonym matching) goes through ``words`` so they agree.

Run-together words are split on a business vocabulary, longest match first,
and kept whole unless at least 80% of the word is recognised - so a cryptic
field (VKORG, NETWR) stays one token instead of being chopped into nonsense.
"""

from __future__ import annotations

import re

VOCAB = sorted({
    # documents and parties
    "sales", "sale", "document", "documents", "item", "items", "customer",
    "customers", "address", "addr", "org", "organization", "name", "postal",
    "order", "orders", "line", "lines", "product", "products", "invoice",
    "payment", "payments", "shipping", "ship", "delivery", "material",
    "vendor", "supplier", "account", "accounts", "billing", "bill", "party",
    "sold", "to", "payer", "partner", "contract", "purchase", "employee", "user",
    # organisation
    "plant", "region", "country", "company", "code", "group", "office",
    "channel", "distribution", "division", "type", "category", "point", "store",
    # money and quantities
    "price", "amount", "quantity", "currency", "net", "gross", "tax", "value",
    "discount", "freight", "cost", "rebate", "list", "local", "unit", "weight",
    "volume", "total",
    # terms and status
    "condition", "terms", "incoterms", "classification", "status", "header",
    "position", "rep", "representation", "transaction", "transactions",
    "event", "stock", "requested", "goods", "issue",
    # time
    "creation", "created", "changed", "date", "time", "last", "first",
    "joined", "tables", "table",
}, key=len, reverse=True)

_PREFIX = {"i", "c", "p", "t", "v", "f", "d", "zi", "zc", "dim", "fact", "fct", "stg",
           "tbl", "vw", "src"}
_MASTER_PREFIXES = ("golden", "master", "gold", "mdm", "canonical")


def segment(word: str) -> list[str]:
    """Split one run-together lower-case word on the business vocabulary."""
    parts: list[str] = []
    unknown = ""
    known = 0
    i = 0
    while i < len(word):
        match = next((v for v in VOCAB if word.startswith(v, i)), None)
        if match:
            if unknown:
                parts.append(unknown)
                unknown = ""
            parts.append(match)
            known += len(match)
            i += len(match)
        else:
            unknown += word[i]
            i += 1
    if unknown:
        parts.append(unknown)
    return parts if known >= 0.8 * len(word) else [word]


def words(name: str) -> list[str]:
    """Lower-case words of any identifier, whatever its casing."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(name))
    out: list[str] = []
    for token in re.split(r"[^A-Za-z0-9]+", spaced):
        if not token:
            continue
        low = token.lower()
        out.extend(segment(low) if low.isalpha() and len(low) > 6 else [low])
    return out


def _singular(word: str) -> str:
    from ontology.discover import singular
    return singular(word)


def display_name(table: str) -> str:
    """A readable concept name from a table name: prefixes dropped, words
    found, last word singular. ``i_salesdocumentitem`` -> SalesDocumentItem."""
    parts = words(table)
    while len(parts) > 1 and parts[0] in _PREFIX:
        parts = parts[1:]
    while len(parts) > 1 and parts[0] in _MASTER_PREFIXES:
        parts = parts[1:]
    if not parts:
        return str(table)
    parts[-1] = _singular(parts[-1])
    return "".join(p.capitalize() for p in parts)
