"""Generate the BI/MDM demo scenario with a known answer key.

The problem, as the team lead described it (data.txt):

* several source systems (CRM, ERP, billing) produce data with their own ids;
* an MDM hub maps them into golden customers, but runs 2-3 weeks behind and
  holds corrected values the sources do not;
* a data mart is built from the hub, so it is stale too;
* each company has 10-12 "amount" columns, and reports get built on the
  wrong one.

Five source folders are written (crm, erp, billing, mdm, mart), plus
``ground_truth.json`` recording the true meaning of every column, the true
identity of every customer across systems, and every planted conflict,
duplicate, stale field and rule violation. Tests measure the ontology against
it. Deterministic for a given seed.

    python -m datasets.generate_bi_mdm data/scenarios/bi_mdm
"""

from __future__ import annotations

import csv
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# SAP-style names on purpose: real exports are cryptic, which is the problem.
AMOUNT_COLUMNS = {
    "NETWR": "net_amount",           # net value
    "MWSBK": "tax_amount",           # tax
    "BRTWR": "gross_amount",         # gross = net + tax
    "RABATT": "discount_amount",     # discount given
    "FRACHT": "freight_amount",      # freight charged
    "LISTPR": "list_amount",         # list value = net + discount
    "WAVWR": "cost_amount",          # cost of goods
    "BONUS": "rebate_amount",        # rebate accrued
    "NETWR_LC": "net_amount_local",  # net in company-code currency
    "NETWR_USD": "net_amount_usd",   # net in USD
}

_PREFIX = ["North", "Blue", "Silver", "Prime", "Atlas", "Nova", "Summit",
           "Harbor", "Vertex", "Crest", "Pioneer", "Evergreen", "Granite",
           "Lumen", "Orbit", "Sterling", "Apex", "Delta", "Union", "Metro"]
_NOUN = ["Logistics", "Foods", "Retail", "Pharma", "Energy", "Motors",
         "Textiles", "Systems", "Chemicals", "Holdings", "Media", "Foods",
         "Electronics", "Packaging", "Tools", "Beverages", "Health", "Labs"]
_SUFFIX = ["GmbH", "Ltd", "Inc", "SA", "BV", "AG", "LLC", "PLC"]
_COUNTRIES = {"DE": "EMEA", "FR": "EMEA", "GB": "EMEA", "NL": "EMEA",
              "US": "AMER", "CA": "AMER", "BR": "AMER",
              "IN": "APAC", "JP": "APAC", "AU": "APAC"}
_CURRENCY = {"DE": "EUR", "FR": "EUR", "NL": "EUR", "GB": "GBP", "US": "USD",
             "CA": "USD", "BR": "USD", "IN": "USD", "JP": "USD", "AU": "USD"}
_TAX = {"EUR": 0.19, "GBP": 0.20, "USD": 0.10}
_TO_USD = {"EUR": 1.08, "GBP": 1.27, "USD": 1.0}
_TO_LOCAL = {"EUR": 1.0, "GBP": 1.17, "USD": 0.93}   # company code runs in EUR
_OWNERS = ["a.khan", "j.smith", "m.rossi", "l.chen", "p.novak"]

START = date(2024, 1, 1)
END = date(2024, 12, 20)


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _money(value: float) -> float:
    return round(value + 1e-9, 2)


def generate(out: str | Path, seed: int = 7, customers: int = 300) -> Path:
    rnd = random.Random(seed)
    root = Path(out)
    root.mkdir(parents=True, exist_ok=True)
    lag = rnd.randint(14, 21)
    sync_day = END - timedelta(days=lag)

    truth: dict = {
        "seed": seed, "customers": customers,
        "column_meanings": {}, "concepts": {}, "identity": [],
        "duplicates": {}, "conflicts": {"name_corrected_in_mdm": []},
        "staleness": {}, "rule_violations": {}, "mart": {},
    }

    # ------------------------------------------------------------ customers
    people = []
    used_names: set[str] = set()
    for i in range(customers):
        while True:
            name = (f"{rnd.choice(_PREFIX)} {rnd.choice(_NOUN)} "
                    f"{rnd.choice(_SUFFIX)}")
            if name not in used_names:
                used_names.add(name)
                break
        country = rnd.choice(list(_COUNTRIES))
        people.append({
            "name": name, "country": country, "region": _COUNTRIES[country],
            "crm_id": None if rnd.random() < 0.08 else f"AC-{1000 + i}",
            "erp_no": str(100000 + i * 7),
            "billing_ref": f"B-{5000 + i * 3}",
            "mdm_id": f"M{i:06d}",
            "tax_id": f"TX{rnd.randint(10_000_000, 99_999_999)}",
        })

    crm_rows, erp_cust, bill_acct, hub_rows = [], [], [], []
    corrected = set(rnd.sample(range(customers), max(3, customers // 25)))
    for i, p in enumerate(people):
        if p["crm_id"]:
            crm_rows.append([p["crm_id"], p["name"].replace(" GmbH", " G.m.b.H."),
                             p["region"], p["country"], rnd.choice(_OWNERS),
                             (END - timedelta(days=rnd.randint(0, 40))).isoformat()])
        erp_cust.append([p["erp_no"], p["name"], p["country"], p["tax_id"]])
        bill_acct.append([p["billing_ref"], p["name"].lower(), p["country"],
                          p["tax_id"]])
        legal = p["name"]
        if i in corrected:
            legal = p["name"].rsplit(" ", 1)[0] + " International " + \
                p["name"].rsplit(" ", 1)[1]
            truth["conflicts"]["name_corrected_in_mdm"].append(
                {"mdm_id": p["mdm_id"], "erp_no": p["erp_no"],
                 "erp_value": p["name"], "mdm_value": legal})
        hub_rows.append([p["mdm_id"], p["crm_id"] or "", p["erp_no"],
                         p["billing_ref"], legal, p["country"], p["region"],
                         f"{sync_day.isoformat()}T02:00:00"])
        truth["identity"].append({k: p[k] for k in
                                  ("mdm_id", "crm_id", "erp_no", "billing_ref")})
    # Near-duplicate golden records: the same ERP customer mastered twice.
    for n, i in enumerate(rnd.sample(range(customers), 4)):
        p = people[i]
        dup_id = f"M9{n:05d}"
        typo = p["name"].replace("o", "0", 1) if "o" in p["name"] else p["name"] + "."
        hub_rows.append([dup_id, "", p["erp_no"], p["billing_ref"], typo,
                         p["country"], p["region"],
                         f"{sync_day.isoformat()}T02:00:00"])
        truth["duplicates"][dup_id] = p["mdm_id"]

    # --------------------------------------------------------------- orders
    order_rows, invoice_rows = [], []
    gross_bad, early_invoices, bad_currency = [], [], []
    n_orders = customers * 10
    span = (END - START).days
    planted_gross = set(rnd.sample(range(n_orders), 5))
    planted_currency = set(rnd.sample(range(n_orders), 2))
    planted_early = set(rnd.sample(range(n_orders), 4))
    for n in range(n_orders):
        p = people[rnd.randrange(customers)]
        vbeln = str(4500000000 + n)
        day = END if n == n_orders - 1 else START + timedelta(days=rnd.randint(0, span))
        cur = _CURRENCY[p["country"]]
        net = _money(rnd.uniform(200, 20000))
        tax = _money(net * _TAX[cur])
        gross = _money(net + tax)
        true_gross = gross
        if n in planted_gross:
            gross = _money(gross + rnd.choice([-1, 1]) * rnd.uniform(15, 300))
            gross_bad.append(vbeln)
        disc = _money(net * rnd.uniform(0.0, 0.15))
        written_cur = cur
        if n in planted_currency:
            written_cur = "XXX"
            bad_currency.append(vbeln)
        order_rows.append([
            vbeln, p["erp_no"], day.isoformat(), written_cur,
            rnd.randint(1, 500),
            net, tax, gross, disc, _money(rnd.uniform(0, 250)),
            _money(net + disc), _money(net * rnd.uniform(0.55, 0.8)),
            _money(net * 0.02), _money(net * _TO_LOCAL[cur]),
            _money(net * _TO_USD[cur])])
        if rnd.random() < 0.92 or n in planted_early:
            inv_id = f"INV-{700000 + n}"
            if n in planted_early:
                inv_day = day - timedelta(days=3)
                early_invoices.append(inv_id)
            else:
                inv_day = min(END, day + timedelta(days=rnd.randint(0, 10)))
            invoice_amount = true_gross if n in planted_gross else gross
            paid = _money(invoice_amount * rnd.choice([1.0, 1.0, 1.0, 0.5, 0.0]))
            invoice_rows.append([inv_id, p["billing_ref"], vbeln, invoice_amount,
                                 tax, paid, cur, inv_day.isoformat(),
                                 (inv_day + timedelta(days=30)).isoformat()])

    # ----------------------------------------------------------- data mart
    hub_by_erp = {p["erp_no"]: p["mdm_id"] for p in people}
    mart: dict = {}
    for row in order_rows:
        if row[2] > sync_day.isoformat():
            continue
        key = (hub_by_erp[row[1]], row[2][:7])
        total, count = mart.get(key, (0.0, 0))
        mart[key] = (total + row[7], count + 1)        # BRTWR: the wrong column
    mart_rows = [[k[0], k[1], _money(v[0]), v[1], sync_day.isoformat()]
                 for k, v in sorted(mart.items())]

    # ---------------------------------------------------------------- write
    _write(root / "crm" / "accounts.csv",
           ["acct_id", "account_name", "region", "country", "owner", "updated_at"],
           crm_rows)
    _write(root / "erp" / "customers.csv", ["KUNNR", "NAME1", "LAND1", "STCD1"],
           erp_cust)
    _write(root / "erp" / "sales_orders.csv",
           ["VBELN", "KUNNR", "ERDAT", "WAERK", "KWMENG", *AMOUNT_COLUMNS],
           order_rows)
    _write(root / "billing" / "accounts.csv",
           ["billing_ref", "bill_to_name", "country", "tax_id"], bill_acct)
    _write(root / "billing" / "invoices.csv",
           ["inv_id", "cust_ref", "order_ref", "invoice_amount", "tax_amount",
            "paid_amount", "currency", "invoice_date", "due_date"], invoice_rows)
    _write(root / "mdm" / "golden_customers.csv",
           ["mdm_id", "crm_id", "erp_no", "billing_ref", "legal_name", "country",
            "region", "last_synced"], hub_rows)
    _write(root / "mart" / "sales_monthly.csv",
           ["mdm_id", "month", "revenue", "orders_count", "snapshot_date"],
           mart_rows)

    # ----------------------------------------------------------- the truth
    meanings = truth["column_meanings"]
    for column, meaning in AMOUNT_COLUMNS.items():
        meanings[f"erp.sales_orders.{column}"] = meaning
    meanings.update({
        "billing.invoices.invoice_amount": "gross_amount",
        "billing.invoices.tax_amount": "tax_amount",
        "billing.invoices.paid_amount": "paid_amount",
        "mart.sales_monthly.revenue": "gross_amount",   # labelled revenue, built from gross
        "crm.accounts.account_name": "customer_name",
        "erp.customers.NAME1": "customer_name",
        "billing.accounts.bill_to_name": "customer_name",
        "mdm.golden_customers.legal_name": "customer_name",
        "crm.accounts.country": "country",
        "erp.customers.LAND1": "country",
        "billing.accounts.country": "country",
        "mdm.golden_customers.country": "country",
        "erp.customers.STCD1": "tax_id",
        "billing.accounts.tax_id": "tax_id",
        "erp.sales_orders.ERDAT": "order_date",
        "erp.sales_orders.WAERK": "currency",
        "billing.invoices.currency": "currency",
        "billing.invoices.invoice_date": "invoice_date",
        "erp.sales_orders.KWMENG": "quantity",
    })
    truth["concepts"] = {
        "Customer": ["crm.accounts", "erp.customers", "billing.accounts",
                     "mdm.golden_customers"],
        "SalesOrder": ["erp.sales_orders"],
        "Invoice": ["billing.invoices"],
        "SalesMonthly": ["mart.sales_monthly"],
    }
    truth["relationships"] = [
        {"from": "erp.sales_orders.KUNNR", "to": "erp.customers.KUNNR",
         "cardinality": "many-to-one", "required": True},
        {"from": "billing.invoices.order_ref", "to": "erp.sales_orders.VBELN",
         "cardinality": "one-to-one", "required": True},
        {"from": "billing.invoices.cust_ref", "to": "billing.accounts.billing_ref",
         "cardinality": "many-to-one", "required": True},
        {"from": "mart.sales_monthly.mdm_id", "to": "mdm.golden_customers.mdm_id",
         "cardinality": "many-to-one", "required": True},
    ]
    truth["hierarchies"] = [{"concept": "Customer", "levels": ["region", "country"],
                             "parent_of": {c: r for c, r in _COUNTRIES.items()}}]
    truth["staleness"] = {"mdm_lag_days": lag, "mart_lag_days": lag,
                          "latest_source_date": END.isoformat(),
                          "mdm_synced": sync_day.isoformat()}
    truth["rule_violations"] = {"gross_not_net_plus_tax": gross_bad,
                                "invoice_before_order": early_invoices,
                                "invalid_currency": bad_currency}
    truth["mart"] = {"wrong_column": "BRTWR", "right_column": "NETWR",
                     "snapshot_date": sync_day.isoformat(),
                     "table": "mart.sales_monthly", "column": "revenue"}
    (root / "ground_truth.json").write_text(json.dumps(truth, indent=2),
                                            encoding="utf-8")
    return root


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "data/scenarios/bi_mdm"
    print(generate(target))
