"""Properties with meaning: map every source column to a canonical property.

This is where "which of our twelve amount columns is net revenue?" gets an
answer with evidence. Three kinds of evidence, weakest first:

1. **Name.** A business glossary plus the SAP field dictionary (NETWR is net
   value, MWSBK tax, BRTWR gross ...). Names are hints: "revenue" usually
   means net, but a name is only what someone typed.
2. **Value structure inside a table.** Tested row by row in DuckDB: which
   column is the sum of two others (net + tax = gross, net + discount =
   list); which is another column times a fixed per-currency rate (a
   currency conversion - and the currency whose rows have rate 1.000 says
   which currency it is). This works even when every column is called
   AMT_01..AMT_10.
3. **Reconciliation against another system.** Through a crosswalk found in
   the concept step (invoice.order_ref -> order.VBELN) a column is compared
   with the other system's columns order by order; a data-mart measure is
   compared month by month with the sums of each candidate source column.
   This is the strongest evidence, and when it contradicts the name it
   becomes a finding: the mart's "revenue" equals the sum of BRTWR (gross,
   tax included), not NETWR.

A steward's decision always wins. Everything is written to the registry as a
proposal with its evidence.
"""

from __future__ import annotations


from knowledge_graph.build import qi
from ontology import registry as reg
from ontology.concepts import _tables
from ontology.keys import _looks_like_id
from ontology.profile import _family
from ontology.words import words as _split

SAMPLE_ROWS = 50_000
SUM_HOLDS = 0.95          # share of rows for a + b = c to count
MATCH_HOLDS = 0.95        # share of joined rows for two columns to be equal
PERIOD_HOLDS = 0.8        # share of periods for a mart measure to reconcile
MAX_STRUCT_COLUMNS = 16   # cost guard: 16 columns is 1,680 sum hypotheses

# Active ISO 4217 codes, and withdrawn ones still found in old ERP data.
ISO_CURRENCIES = set("""
AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL
BSD BTN BWP BYN BZD CAD CDF CHF CLP CNY COP CRC CUP CVE CZK DJF DKK DOP DZD EGP
ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR
IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL
LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MYR MZN NAD NGN NIO NOK NPR
NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD
SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX
USD UYU UZS VES VND VUV WST XAF XCD XCG XOF XPF YER ZAR ZMW ZWG ZWL
""".split())
LEGACY_CURRENCIES = set("""
ATS BEF BGL CYP DEM EEK ESP FIM FRF GHC GRD HRK IEP ITL LTL LUF LVL MTL MXP NLG
PLZ PTE ROL RUR SDD SIT SKK TRL VEB YUM ZWD
""".split())

AMOUNT_PROPS = {
    "net_amount": "Value after discounts and before tax; the figure finance "
                  "reports as net revenue.",
    "tax_amount": "Tax charged on the net amount (VAT or sales tax).",
    "gross_amount": "Net amount plus tax; what the customer is invoiced.",
    "discount_amount": "Reduction from the list value granted to the customer.",
    "freight_amount": "Shipping charge billed with the order.",
    "list_amount": "Value at list price before discounts (net + discount).",
    "cost_amount": "Cost of goods sold for the order.",
    "rebate_amount": "Rebate accrued to the customer and settled later.",
    "net_amount_local": "Net amount converted to the company-code currency.",
    "net_amount_usd": "Net amount converted to US dollars for group reporting.",
    "paid_amount": "Amount the customer has paid against the invoice.",
    "amount_unclassified": "A money column whose meaning the data does not "
                           "show; a person needs to say what it is.",
}
OTHER_PROPS = {
    "identifier": "Identifies a record, or points at a record in another table.",
    "country": "Country, as an ISO 3166 code.",
    "tax_id": "Tax registration number of the business partner.",
    "currency": "ISO 4217 code of the currency the row's amounts are in.",
    "quantity": "Number of units.",
    "record_count": "A count of records, not money.",
    "period": "Reporting period (year and month).",
    "snapshot_date": "When this copy of the data was taken.",
    "sync_timestamp": "When this record was last synchronised from its sources.",
    "last_updated": "When this record was last changed in its system.",
    "region": "Sales region.",
    "record_owner": "The person responsible for the record.",
    "invoice_date": "Date the invoice was issued.",
    "due_date": "Date payment is due.",
    "sales_organization": "The selling unit responsible for the sale (SAP VKORG).",
    "distribution_channel": "How goods reach the customer, e.g. wholesale or retail (SAP VTWEG).",
    "division": "Product line grouping for sales responsibility (SAP SPART).",
    "sales_office": "Physical sales office handling the business (SAP VKBUR).",
    "sales_group": "Team of salespeople within an office (SAP VKGRP).",
    "plant": "Site that supplies the goods (SAP WERKS).",
    "shipping_point": "Place from which goods are shipped (SAP VSTEL).",
    "shipping_condition": "Agreed shipping strategy, e.g. standard or express (SAP VSBED).",
    "payment_terms": "Agreed terms of payment (SAP ZTERM).",
    "incoterms": "International commercial terms for delivery responsibility (SAP INCO1).",
    "document_type": "Kind of sales document, e.g. standard order or return (SAP AUART).",
    "item_category": "How an item is processed, e.g. standard or free of charge (SAP PSTYV).",
    "company_code": "Legal entity that books the revenue (SAP BUKRS).",
    "creation_time": "Time of day the record was created.",
    "date": "A date whose business meaning is not yet named.",
    "number": "A number whose business meaning is not yet named.",
    "attribute": "A descriptive attribute not yet mapped to the glossary.",
}

# Exact names, lower-cased. NAME and CREATED are resolved against the concept
# (NAME1 in Customer -> customer_name; ERDAT in SalesOrder -> order_date).
EXACT = {
    **dict.fromkeys(["netwr", "net_amount", "net_value", "netamount", "net_sales"], "net_amount"),
    **dict.fromkeys(["mwsbk", "mwst", "tax_amount", "vat_amount", "taxamount"], "tax_amount"),
    **dict.fromkeys(["brtwr", "gross_amount", "gross_value", "total_amount"], "gross_amount"),
    **dict.fromkeys(["rabatt", "discount_amount", "discount"], "discount_amount"),
    **dict.fromkeys(["fracht", "freight_amount", "freight", "shipping_amount"], "freight_amount"),
    **dict.fromkeys(["listpr", "list_amount", "list_value"], "list_amount"),
    **dict.fromkeys(["wavwr", "cost_amount", "cogs", "cost_of_goods"], "cost_amount"),
    **dict.fromkeys(["bonus", "rebate_amount", "rebate"], "rebate_amount"),
    **dict.fromkeys(["netwr_lc", "net_amount_local", "net_local"], "net_amount_local"),
    **dict.fromkeys(["netwr_usd", "net_amount_usd", "net_usd"], "net_amount_usd"),
    **dict.fromkeys(["paid_amount", "amount_paid", "paid"], "paid_amount"),
    **dict.fromkeys(["name1", "name", "legal_name", "account_name", "bill_to_name",
                     "customer_name", "company_name"], "NAME"),
    **dict.fromkeys(["erdat", "created_on", "creation_date", "created_date",
                     "order_date", "doc_date", "audat"], "CREATED"),
    **dict.fromkeys(["land1", "country", "country_code", "ctry"], "country"),
    **dict.fromkeys(["stcd1", "tax_id", "vat_id", "vat_number", "tax_number"], "tax_id"),
    **dict.fromkeys(["waerk", "waers", "currency", "curr", "currency_code"], "currency"),
    **dict.fromkeys(["kwmeng", "menge", "qty", "quantity", "units"], "quantity"),
    **dict.fromkeys(["month", "period", "fiscal_period", "year_month", "yearmonth"], "period"),
    **dict.fromkeys(["snapshot_date", "as_of", "as_of_date", "load_date"], "snapshot_date"),
    **dict.fromkeys(["last_synced", "synced_at", "last_sync"], "sync_timestamp"),
    **dict.fromkeys(["updated_at", "last_updated", "modified_at", "aedat"], "last_updated"),
    **dict.fromkeys(["region", "sales_region"], "region"),
    **dict.fromkeys(["owner", "account_owner", "record_owner"], "record_owner"),
    **dict.fromkeys(["invoice_date", "fkdat", "billing_date"], "invoice_date"),
    **dict.fromkeys(["due_date", "zfbdt", "payment_due"], "due_date"),
    **dict.fromkeys(["vkorg", "sales_organization", "sales_org"], "sales_organization"),
    **dict.fromkeys(["vtweg", "distribution_channel"], "distribution_channel"),
    **dict.fromkeys(["spart", "division", "organization_division"], "division"),
    **dict.fromkeys(["vkbur", "sales_office"], "sales_office"),
    **dict.fromkeys(["vkgrp", "sales_group"], "sales_group"),
    **dict.fromkeys(["werks", "plant"], "plant"),
    **dict.fromkeys(["vstel", "shipping_point"], "shipping_point"),
    **dict.fromkeys(["vsbed", "shipping_condition"], "shipping_condition"),
    **dict.fromkeys(["zterm", "payment_terms", "customer_payment_terms"], "payment_terms"),
    **dict.fromkeys(["inco1", "incoterms", "incoterms_classification"], "incoterms"),
    **dict.fromkeys(["auart", "sales_document_type", "order_type", "document_type"],
                    "document_type"),
    **dict.fromkeys(["pstyv", "sales_document_item_category", "item_category"],
                    "item_category"),
    **dict.fromkeys(["bukrs", "company_code", "billing_company_code"], "company_code"),
    **dict.fromkeys(["transaction_currency", "document_currency"], "currency"),
    **dict.fromkeys(["erzet", "creation_time", "created_time"], "creation_time"),
}
# The same names with separators removed: SALESORGANIZATION, SalesOrganization.
EXACT_COMPACT = {k.replace("_", ""): v for k, v in EXACT.items()}
# Tokens for money columns (numeric only), with how much a token alone says.
TOKENS = [
    ({"gross", "brutto"}, "gross_amount", 0.75),
    ({"tax", "vat", "mwst"}, "tax_amount", 0.75),
    ({"discount", "disc", "rabatt"}, "discount_amount", 0.75),
    ({"freight", "shipping"}, "freight_amount", 0.75),
    ({"rebate", "bonus"}, "rebate_amount", 0.75),
    ({"cost", "cogs"}, "cost_amount", 0.75),
    ({"list"}, "list_amount", 0.7),
    ({"paid", "payment"}, "paid_amount", 0.75),
    ({"net", "netto"}, "net_amount", 0.75),
    ({"revenue", "sales", "turnover"}, "net_amount", 0.55),
]
MAPPING_FINDINGS = ("name_contradicts_values|", "wrong_amount_column|",
                    "mixed_currency_total|")
_FLOAT_TYPES = ("DOUBLE", "FLOAT", "REAL", "DECIMAL", "NUMERIC")


def _words(name: str) -> list[str]:
    return _split(name)


def _snake(concept: str) -> str:
    return "_".join(_words(concept)) or "record"


def _is_float(column) -> bool:
    return any(t in str(column.type).upper() for t in _FLOAT_TYPES)


# ------------------------------------------------------------- 1. names
def name_meaning(column, family: str, concept: str, is_key: bool) -> tuple[str, float, str]:
    """(property, confidence, evidence) from the column name alone."""
    low = column.name.lower()
    hit = EXACT.get(low) or EXACT_COMPACT.get(low.replace("_", ""))
    if hit in AMOUNT_PROPS and family != "numeric":
        hit = None
    if hit == "NAME":
        return f"{_snake(concept)}_name", 0.9, f"name {column.name!r} is a name field"
    if hit == "CREATED":
        doc = _words(concept)[-1] if _words(concept) else "record"
        return f"{doc}_date", 0.85, \
            f"{column.name!r} is the creation date of a {concept} (glossary)"
    if hit:
        return hit, 0.9, f"{column.name!r} is a known field name for {hit} (glossary)"
    if is_key or (_looks_like_id(low) and not (family == "numeric" and _is_float(column))):
        return "identifier", 0.9, f"{column.name!r} is an identifier"
    words = set(_words(column.name))
    if family == "numeric":
        if words & {"count", "cnt"}:
            return "record_count", 0.8, f"{column.name!r} counts records"
        for tokens, prop, score in TOKENS:
            if words & tokens:
                return prop, score, f"the word {sorted(words & tokens)[0]!r} in {column.name!r}"
        if _is_float(column) or words & {"amount", "amt", "value", "price"}:
            return "amount_unclassified", 0.3, f"{column.name!r} holds money-like decimals"
        return "number", 0.4, f"{column.name!r} is numeric"
    if "name" in words and family == "text":
        return f"{_snake(concept)}_name", 0.75, f"{column.name!r} contains 'name'"
    named = _words(column.name)
    if len(named) >= 2 and all(w.isalpha() for w in named):
        # No glossary term: propose a new one from the column's own words.
        term = "_".join(named)
        if family == "temporal" and not term.endswith(("_date", "_time")):
            term += "_date"
        return term, 0.5, (f"no glossary term for {column.name!r}; proposed the new "
                           f"term {term!r} from its words")
    if family == "temporal":
        return "date", 0.4, f"{column.name!r} is a date"
    return "attribute", 0.4, f"{column.name!r} is descriptive text"


# ---------------------------------------------------- 2. value structure
def _currency_column(graph, t, names: dict) -> str | None:
    for c in t["table"].columns:
        if names.get(c.name, ("",))[0] == "currency":
            return c.name
    for c in t["table"].columns:          # by values: mostly ISO codes
        if _family(c) != "text" or c.name.startswith("__"):
            continue
        rows = graph.sql(f"SELECT {qi(c.name)}, count(*) FROM {t['ref']}"
                         f" GROUP BY 1 ORDER BY 2 DESC LIMIT 12")
        total = sum(n for _, n in rows) or 1
        iso = sum(n for v, n in rows if str(v).upper() in ISO_CURRENCIES)
        if len(rows) <= 12 and iso / total >= 0.8:
            return c.name
    return None


def value_structure(graph, t, amounts: list[str], currency: str | None) -> dict:
    """{column: (property, confidence, [evidence])} from arithmetic alone."""
    cols = amounts[:MAX_STRUCT_COLUMNS]
    if len(cols) < 3:
        return {}
    src = f"(SELECT * FROM {t['ref']} LIMIT {SAMPLE_ROWS})"
    hyps, exprs = [], []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            for c in cols:
                if c in (a, b):
                    continue
                hyps.append((a, b, c))
                exprs.append(
                    f"avg(CASE WHEN abs({qi(a)} + {qi(b)} - {qi(c)}) <= "
                    f"greatest(0.011, 1e-6 * abs({qi(c)})) THEN 1.0 ELSE 0.0 END)")
    row = graph.sql(f"SELECT {', '.join(exprs)} FROM {src}")[0]
    triples = [(h, float(s)) for h, s in zip(hyps, row) if s is not None and s >= SUM_HOLDS]
    if not triples:
        return {}

    mags = dict(zip(cols, graph.sql(
        f"SELECT {', '.join(f'avg(abs({qi(c)}))' for c in cols)} FROM {src}")[0]))
    addend_uses: dict = {}
    for (a, b, _), _s in triples:
        addend_uses[a] = addend_uses.get(a, 0) + 1
        addend_uses[b] = addend_uses.get(b, 0) + 1
    net = sorted(addend_uses, key=lambda c: (-addend_uses[c], -(mags[c] or 0), c))[0]

    group = qi(currency) if currency else "'all'"

    def per_currency_constant(col: str) -> tuple[bool, float]:
        ratios, groups, median = graph.sql(
            f"SELECT count(DISTINCT {group} || '|' || round({qi(col)} / {qi(net)}, 3)),"
            f" count(DISTINCT {group}), median({qi(col)} / {qi(net)})"
            f" FROM {src} WHERE {qi(net)} <> 0")[0]
        return int(ratios or 0) <= 2 * int(groups or 1) + 2, float(median or 0)

    out: dict = {}
    for (a, b, c), share in triples:
        if net not in (a, b):
            continue
        other = b if a == net else a
        constant, median = per_currency_constant(other)
        add, total = ("tax_amount", "gross_amount") if constant else \
            ("discount_amount", "list_amount")
        why = (f"{net} + {other} = {c} on {share:.1%} of rows; {other} is "
               f"{'a fixed' if constant else 'a varying'} share of {net} "
               f"(median {median:.1%}{' per currency' if constant and currency else ''})")
        out[c] = (total, 0.9, [why])
        out[other] = (add, 0.9, [why])
        prev = out.get(net, ("net_amount", 0.9, []))
        out[net] = ("net_amount", 0.9, prev[2] + [why])

    for col in cols:                       # conversions of net
        if col in out or col == net:
            continue
        constant, median = per_currency_constant(col)
        if not constant or not 0.3 <= median <= 3.0:
            continue
        native = None
        if currency:
            for cur, same in graph.sql(
                    f"SELECT {qi(currency)}, avg(CASE WHEN abs({qi(col)} - {qi(net)})"
                    f" <= 0.011 THEN 1.0 ELSE 0.0 END) FROM {src} GROUP BY 1"):
                if same is not None and same >= 0.95 and str(cur).upper() in ISO_CURRENCIES:
                    native = str(cur).upper()
        why = (f"{col} is {net} times a fixed rate per currency"
               + (f"; rate 1.000 for {native} rows, so it is in {native}" if native else ""))
        if native == "USD":
            out[col] = ("net_amount_usd", 0.9, [why])
        elif native:
            out[col] = ("net_amount_local", 0.9, [why])
        else:
            out[col] = ("amount_unclassified", 0.5, [why])
        out[col] = (*out[col][:2], out[col][2], native)
    return out


# --------------------------------------------------- 3. reconciliation
def _equal_share(graph, t, u, link_from: str, link_to: str, xs: list[str],
                 ys: list[str]) -> tuple[int, dict]:
    pairs = [(x, y) for x in xs for y in ys]
    if not pairs:
        return 0, {}
    exprs = [f"avg(CASE WHEN abs(a.{qi(x)} - b.{qi(y)}) <= greatest(0.011,"
             f" 0.0005 * abs(b.{qi(y)})) THEN 1.0 ELSE 0.0 END)" for x, y in pairs]
    row = graph.sql(
        f"SELECT count(*), {', '.join(exprs)} FROM"
        f" (SELECT * FROM {t['ref']} LIMIT {SAMPLE_ROWS}) a JOIN {u['ref']} b"
        f" ON CAST(a.{qi(link_from)} AS VARCHAR) = CAST(b.{qi(link_to)} AS VARCHAR)")[0]
    return int(row[0] or 0), {p: float(s or 0) for p, s in zip(pairs, row[1:])}


def _period_expr(graph, t, column) -> str | None:
    q = qi(column.name)
    fam = _family(column)
    if fam == "temporal":
        return f"strftime(CAST({q} AS DATE), '%Y-%m')"
    if fam == "text":
        bad = graph.sql(f"SELECT count(*) FROM {t['ref']} WHERE {q} IS NOT NULL"
                        f" AND NOT regexp_matches(CAST({q} AS VARCHAR), '^[0-9]{{4}}-[0-9]{{2}}$')")[0][0]
        return f"CAST({q} AS VARCHAR)" if bad == 0 else None
    return None


# --------------------------------------------------------------- main
def map_properties(layer, ontology_id: str) -> dict:
    graph = layer.graph
    onto = reg.get(graph, ontology_id)
    tables = _tables(layer, onto)
    by_key = {t["key"]: t for t in tables}
    concept_of = {}
    for m in reg.items(graph, ontology_id, kind="member"):
        if m["status"] != "rejected":
            concept_of[m["payload"]["table"]] = m["payload"]["concept"]

    cols: dict = {}          # column_key -> result
    names: dict = {}         # table_key -> {column: (prop, conf, why)}
    for t in tables:
        concept = concept_of.get(t["key"], t["class"])
        names[t["key"]] = {}
        for c in t["table"].columns:
            if c.name.startswith("__"):
                continue
            fam = _family(c)
            prop, conf, why = name_meaning(c, fam, concept, c.name == t["id"])
            names[t["key"]][c.name] = (prop, conf, why)
            cols[f"{t['key']}.{c.name}"] = {
                "table": t["key"], "column": c.name, "concept": concept,
                "family": fam, "type": str(c.type), "property": prop,
                "name_property": prop, "confidence": conf, "method": "name",
                "evidence": [why], "unit": None}

    for rel in reg.items(graph, ontology_id, kind="relationship"):
        if rel["status"] == "rejected":
            continue
        target = cols.get(rel["payload"]["to"])
        if target and target["property"] != "identifier":
            target.update(property="identifier", name_property="identifier",
                          confidence=0.9, method="values")
            target["evidence"] = target["evidence"] + [
                f"{rel['payload']['from']} points at it: it is a business key"]
        ref = cols.get(rel["payload"]["from"])
        if ref and ref["property"] != "identifier":
            ref.update(property="identifier", name_property="identifier",
                       confidence=0.9, method="values")
            ref["evidence"] = ref["evidence"] + [
                f"points at {rel['payload']['to']} "
                f"({rel['payload'].get('contained', 1):.0%} of its values are keys there)"]

    def is_amount(key: str) -> bool:
        r = cols[key]
        return r["family"] == "numeric" and r["property"] in AMOUNT_PROPS

    # 2. value structure, table by table
    currency_of: dict = {}
    findings: list[dict] = []
    for t in tables:
        currency = _currency_column(graph, t, names[t["key"]])
        currency_of[t["key"]] = currency
        amounts = [c.name for c in t["table"].columns
                   if f"{t['key']}.{c.name}" in cols and is_amount(f"{t['key']}.{c.name}")]
        for col, found in value_structure(graph, t, amounts, currency).items():
            prop, conf, why = found[:3]
            r = cols[f"{t['key']}.{col}"]
            agrees = r["property"] == prop
            if agrees and r["method"] == "name" and r["confidence"] >= 0.7:
                r.update(confidence=0.97, method="values+name")
            elif r["property"] in ("amount_unclassified",) or r["confidence"] < 0.7 \
                    or prop == "amount_unclassified":
                if prop != "amount_unclassified" or r["property"] == "amount_unclassified":
                    r.update(property=prop, confidence=0.85 if prop != "amount_unclassified"
                             else min(r["confidence"], 0.5), method="values")
            elif not agrees:
                findings.append({
                    "type": "name_contradicts_values", "column": f"{t['key']}.{col}",
                    "name_says": r["property"], "data_says": prop,
                    "detail": f"{col} is named like {r['property']} but behaves like {prop}"})
                r.update(property=prop, confidence=0.7, method="values")
            r["evidence"] = r["evidence"] + why
            if len(found) > 3 and found[3]:
                r["unit"] = found[3]

    _apply_steward(graph, ontology_id, cols)

    # 3a. row-level reconciliation through crosswalks
    for rel in reg.items(graph, ontology_id, kind="relationship"):
        if rel["status"] == "rejected":
            continue
        p = rel["payload"]
        t_key, link_from = p["from"].rsplit(".", 1)
        u_key, link_to = p["to"].rsplit(".", 1)
        if t_key not in by_key or u_key not in by_key:
            continue
        xs = [c for c in names[t_key] if is_amount(f"{t_key}.{c}")
              and cols[f"{t_key}.{c}"]["method"] != "steward"]
        ys = [c for c in names[u_key] if is_amount(f"{u_key}.{c}")
              and cols[f"{u_key}.{c}"]["property"] != "amount_unclassified"]
        joined, shares = _equal_share(graph, by_key[t_key], by_key[u_key],
                                      link_from, link_to, xs, ys)
        for x in xs:
            best = max(((shares[(x, y)], y) for y in ys), default=(0, None))
            if best[0] < MATCH_HOLDS:
                continue
            y = best[1]
            target = cols[f"{u_key}.{y}"]
            r = cols[f"{t_key}.{x}"]
            if r["name_property"] not in (target["property"], "amount_unclassified") \
                    and r["confidence"] >= 0.7 and r["name_property"] in AMOUNT_PROPS:
                findings.append({
                    "type": "name_contradicts_values", "column": f"{t_key}.{x}",
                    "name_says": r["name_property"], "data_says": target["property"],
                    "detail": f"{x} is named like {r['name_property']} but equals "
                              f"{u_key}.{y} ({target['property']})"})
            r.update(property=target["property"], method="reconciliation",
                     confidence=round(0.9 + 0.1 * best[0] - 0.05, 3))
            r["evidence"] = r["evidence"] + [
                f"{x} equals {u_key}.{y} ({target['property']}) on {best[0]:.1%} of "
                f"{joined:,} rows matched through {p['from']} -> {p['to']}"]
            if target["unit"] and not r["unit"]:
                r["unit"] = target["unit"]

    # 3b. period-level reconciliation for marts and aggregates
    findings += _reconcile_aggregates(graph, tables, cols, names, currency_of)

    # units
    for t in tables:
        currency = currency_of[t["key"]]
        for c in names[t["key"]]:
            r = cols[f"{t['key']}.{c}"]
            if r["family"] != "numeric" or r["property"] not in AMOUNT_PROPS or r["unit"]:
                continue
            if r["property"] == "net_amount_usd":
                r["unit"] = "USD"
            elif currency:
                r["unit"] = f"currency in {currency}"
            else:
                r["unit"] = "unknown currency (no currency column)"

    _apply_steward(graph, ontology_id, cols)
    return _store(graph, ontology_id, cols, findings)


def _reconcile_aggregates(graph, tables, cols, names, currency_of) -> list[dict]:
    findings = []
    sources = []
    for s in tables:
        date_cols = [c for c in s["table"].columns if _family(c) == "temporal"
                     and cols.get(f"{s['key']}.{c.name}", {}).get("property", "").endswith("_date")]
        resolved = [c for c in names[s["key"]]
                    if cols[f"{s['key']}.{c}"]["family"] == "numeric"
                    and cols[f"{s['key']}.{c}"]["property"] in AMOUNT_PROPS
                    and cols[f"{s['key']}.{c}"]["property"] != "amount_unclassified"]
        if date_cols and resolved:
            sources.append((s, date_cols[0].name, resolved))

    for m in tables:
        measures = [c for c in names[m["key"]]
                    if cols[f"{m['key']}.{c}"]["family"] == "numeric"
                    and cols[f"{m['key']}.{c}"]["property"] in AMOUNT_PROPS
                    and cols[f"{m['key']}.{c}"]["method"] in ("name",)
                    and cols[f"{m['key']}.{c}"]["confidence"] < 0.7]
        if not measures:
            continue
        period = cutoff = None
        for c in m["table"].columns:
            prop = cols.get(f"{m['key']}.{c.name}", {}).get("property")
            if period is None and prop == "period":
                period = _period_expr(graph, m, c)
            elif cutoff is None and _family(c) == "temporal" and prop != "period":
                cutoff = c.name
        if period is None:
            continue
        cut = graph.sql(f"SELECT CAST(max(CAST({qi(cutoff)} AS DATE)) AS VARCHAR)"
                        f" FROM {m['ref']}")[0][0] if cutoff else None
        mart = {}
        for row in graph.sql(f"SELECT {period}, {', '.join(f'sum({qi(x)})' for x in measures)}"
                             f" FROM {m['ref']} GROUP BY 1"):
            mart[row[0]] = dict(zip(measures, row[1:]))
        for s, date_col, resolved in sources:
            if s["key"] == m["key"]:
                continue
            where = f" WHERE CAST({qi(date_col)} AS DATE) <= DATE '{cut}'" if cut else ""
            srows = graph.sql(
                f"SELECT strftime(CAST({qi(date_col)} AS DATE), '%Y-%m'),"
                f" {', '.join(f'sum({qi(y)})' for y in resolved)} FROM {s['ref']}{where}"
                f" GROUP BY 1")
            src = {r[0]: dict(zip(resolved, r[1:])) for r in srows}
            periods = [p for p in mart if p in src]
            if not periods:
                continue
            for x in measures:
                scores = []
                for y in resolved:
                    ok = sum(1 for p in periods if mart[p][x] is not None and src[p][y]
                             is not None and abs(mart[p][x] - src[p][y])
                             <= 0.001 * abs(src[p][y]) + 0.05)
                    scores.append((ok / len(mart), ok, y))
                share, ok, y = max(scores)
                if share < PERIOD_HOLDS:
                    continue
                r = cols[f"{m['key']}.{x}"]
                target = cols[f"{s['key']}.{y}"]
                name_said = r["name_property"]
                r.update(property=target["property"], method="reconciliation",
                         confidence=round(0.85 + 0.1 * share, 3))
                r["evidence"] = r["evidence"] + [
                    f"monthly totals of {x} equal the sum of {s['key']}.{y} "
                    f"({target['property']}) in {ok} of {len(mart)} months"
                    + (f" (orders up to the snapshot {cut})" if cut else "")]
                if name_said in AMOUNT_PROPS and name_said not in (
                        target["property"], "amount_unclassified"):
                    right = next((c for c in resolved
                                  if cols[f"{s['key']}.{c}"]["property"] == name_said), None)
                    over = None
                    if right:
                        tot = graph.sql(f"SELECT sum({qi(y)}), sum({qi(right)})"
                                        f" FROM {s['ref']}{where}")[0]
                        over = round((tot[0] / tot[1] - 1) * 100, 1) if tot[1] else None
                    findings.append({
                        "type": "wrong_amount_column", "column": f"{m['key']}.{x}",
                        "built_from": f"{s['key']}.{y}",
                        "should_be": f"{s['key']}.{right}" if right else None,
                        "label_means": name_said, "data_means": target["property"],
                        "overstatement_pct": over,
                        "detail": (f"{m['key']}.{x} is labelled like {name_said} but is "
                                   f"built from {s['key']}.{y} ({target['property']})"
                                   + (f"; it should use {right}, and overstates it by "
                                      f"{over}%" if right and over is not None else ""))})
                if not currency_of.get(m["key"]) and currency_of.get(s["key"]):
                    codes = graph.sql(f"SELECT DISTINCT CAST({qi(currency_of[s['key']])}"
                                      f" AS VARCHAR) FROM {s['ref']}")
                    n = sum(1 for (v,) in codes if str(v).upper() in ISO_CURRENCIES)
                    if n and n > 1:
                        r["unit"] = "mixed currencies (no currency column)"
                        findings.append({
                            "type": "mixed_currency_total", "column": f"{m['key']}.{x}",
                            "detail": f"{m['key']}.{x} adds {s['key']}.{y} across {n} "
                                      f"currencies without converting"})
    return findings


def _apply_steward(graph, ontology_id, cols) -> None:
    for item in reg.items(graph, ontology_id, kind="mapping", status="approved"):
        r = cols.get(item["key"])
        prop = item["payload"].get("property")
        if r is None or not prop:
            continue
        audit = [a for a in reg.audit(graph, ontology_id)
                 if a["kind"] == "mapping" and a["key"] == item["key"]]
        r.update(property=prop, confidence=1.0,
                 method="steward" if audit else r["method"])
        if audit:
            r["evidence"] = [f"set by {audit[-1]['by']} ({audit[-1]['decision']})"]


def _store(graph, ontology_id, cols, findings) -> dict:
    props: dict = {}
    for key, r in cols.items():
        definition = AMOUNT_PROPS.get(r["property"]) or OTHER_PROPS.get(r["property"]) \
            or f"{r['property'].replace('_', ' ').capitalize()}."
        r["definition"] = definition
        reg.put(graph, ontology_id, "mapping", key,
                {k: r[k] for k in ("table", "column", "concept", "property", "unit",
                                   "method", "definition", "type")},
                confidence=r["confidence"], evidence=r["evidence"])
        if r["property"] in ("identifier", "attribute", "date", "number"):
            continue
        p = props.setdefault(r["property"], {
            "definition": definition, "kind": "amount" if r["property"] in AMOUNT_PROPS
            else "other", "columns": [], "units": []})
        p["columns"].append(key)
        if r["unit"] and r["unit"] not in p["units"]:
            p["units"].append(r["unit"])
    for name, p in props.items():
        reg.put(graph, ontology_id, "property", name, p, confidence=0.9,
                evidence=[f"mapped from {len(p['columns'])} column(s)"])
    keep = set()
    for f in findings:
        key = f"{f['type']}|{f['column']}"
        keep.add(key)
        reg.put(graph, ontology_id, "finding", key, f, confidence=0.9,
                evidence=[f["detail"]])
    reg.prune(graph, ontology_id, "finding", keep, prefixes=MAPPING_FINDINGS)
    reg.prune(graph, ontology_id, "property", set(props))
    return {"columns": cols, "findings": findings, "properties": props}
