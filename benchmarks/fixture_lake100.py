"""lake100: a deterministic, synthetic 100-table data lake for benchmarks.

Why this exists
---------------
The current product claims "any data source, no per-dataset code". A benchmark
on one hand-written demo table proves nothing about that claim. lake100 is a
folder of 100 deliberately different tables -- four business domains, three
file formats, noisy legacy names, keyless tables, composite identities,
reserved-word columns and non-ASCII data -- so connect / discover / build /
metrics can be measured on the same input every time.

It is NOT a realistic data warehouse and it is not meant to be. It is a
repeatable obstacle course.

Contract
--------
* exactly 100 files, all directly in one folder (connect() reads one level)
* formats: .csv, .parquet (written by DuckDB) and .json only
* no external services, no network, no clock, no absolute paths in the data
* byte-for-byte deterministic for a fixed generator version: a fixed seed and
  a per-table RNG derived from the table name, dates picked from a fixed list
  and no generation timestamps anywhere. Two runs must produce identical
  SHA-256 hashes; `--check` proves it.
* ground truth is written to benchmarks/lake100_ground_truth.json, which is
  tracked in git (data/ is not).

Special cases deliberately included
-----------------------------------
* 3 overlapping product masters (erp_products.csv, pim_products.parquet,
  marketplace_products.json): same product_id space, different attributes and
  coverage. Current single-source discovery reads them as three classes; it
  does not merge them, and only the first product-named table in folder order
  receives the product_id edges. That is a baseline finding, not a bug in the
  fixture.
* tables with no usable key: every column repeats a value, so current file
  discovery falls back to a synthetic row number (marked `__row`).
* composite identities (order_id, line_no): a file cannot declare a composite
  primary key, so current discovery also falls back to `__row`. The ground
  truth records the intended identity AND what the current code should do.
* reserved-word column names (`order`, `select`, `group`) and non-ASCII values.
* deliberate orphan references (a few rows point at ids that do not exist), so
  findings / missed-edge counting has something to find.

Usage
-----
    python benchmarks/fixture_lake100.py --out data/fixtures/lake100
    python benchmarks/fixture_lake100.py --check

The ground truth's `class` and `expected_relations` values are derived with the
CURRENT naming rules (ontology.discover) from the same table/column shapes, so
they document "what today's code should discover". They are a regression pin,
not an independent semantic oracle: if the naming rules improve, the ground
truth must be regenerated and the diff reviewed on purpose.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUT = ROOT / "data" / "fixtures" / "lake100"
DEFAULT_TRUTH = HERE / "lake100_ground_truth.json"

GENERATOR = "lake100"
GENERATOR_VERSION = "lake100-v1"
SEED = 20241029
COMPOSITE_INNER = 4          # rows per first composite-key part
FORMATS = ("csv", "parquet", "json")
RESERVED_WORDS = ("order", "select", "group")


# ---------------------------------------------------------------- test data
NAMES = (
    "José Álvarez", "Müller GmbH", "张伟", "Zoë Okafor", "Łukasz Nowak",
    "Priya Raman", "François Dubois", "Ana Beatriz", "Søren Kierkegaard",
    "محمد علي", "Ewa Kowalska", "Renée Laurent",
)
CITIES = (
    "München", "Málaga", "北京", "São Paulo", "Kraków",
    "Zürich", "Montréal", "Bogotá",
)
NOTES = (
    "Résumé envoyé - café",
    "已确认 · 東京",
    "Ação concluída",
    "Prüfung bestanden",
    "Segunda llamada",
    "Uwaga: łączenie",
)


# ------------------------------------------------------------- table model
@dataclass(frozen=True)
class TablePlan:
    name: str                      # file stem, lowercase
    domain: str                    # sales | inventory | crm | finance
    fmt: str                       # csv | parquet | json
    rows: int
    cls: str                       # expected class name (asserted against discovery)
    key_kind: str                  # natural | composite | none
    key_cols: tuple[str, ...]      # intended identity (natural: 1, composite: 2+)
    cols: tuple[tuple[str, str], ...]   # (column name, generator spec)


# Generator-spec helpers. A spec is a short deterministic recipe, not data:
#   key        unique 1..rows          comp:0/comp:1  one part of a composite id
#   fk:<table> reference to a table    pick:a|b|c     repeating category
#   int:lo:hi  repeating integers      money:lo:hi    repeating money values
#   date       a date in 2024          name/city/note fixed pools (< rows)
#   flag       yes|no                  const:x        one constant value
def K(c):  # noqa: N802
    return (c, "key")


def C0(c):  # noqa: N802
    return (c, "comp:0")


def C1(c):  # noqa: N802
    return (c, "comp:1")


def FK(c, table):  # noqa: N802
    return (c, "fk:" + table)


def P(c, *values):  # noqa: N802
    return (c, "pick:" + "|".join(values))


def I(c, lo, hi):  # noqa: N802
    return (c, f"int:{lo}:{hi}")


def M(c, lo, hi):  # noqa: N802
    return (c, f"money:{lo}:{hi}")


def D(c):  # noqa: N802
    return (c, "date")


def N(c):  # noqa: N802
    return (c, "name")


def CI(c):  # noqa: N802
    return (c, "city")


def NO(c):  # noqa: N802
    return (c, "note")


def F(c):  # noqa: N802
    return (c, "flag")


def _t(name, domain, fmt, rows, cls, key_kind, key_cols, cols):
    return TablePlan(name=name, domain=domain, fmt=fmt, rows=rows, cls=cls,
                     key_kind=key_kind, key_cols=tuple(key_cols),
                     cols=tuple(cols))


def plans() -> list[TablePlan]:
    """The 100 tables. Order here is irrelevant; files are written sorted."""
    p: list[TablePlan] = []

    # ------------------------------------------------------------ sales (29)
    p += [
        _t("customers", "sales", "csv", 60, "Customer", "natural",
           ("customer_id",),
           [K("customer_id"), N("customer_name"), CI("city"),
            P("country", "UK", "US", "DE", "IN", "BR", "JP"),
            D("signup_date"), P("loyalty_tier", "basic", "silver", "gold")]),
        _t("orders", "sales", "csv", 90, "Order", "natural", ("order_id",),
           [K("order_id"), FK("customer_id", "customers"), D("placed_at"),
            P("status", "paid", "pending", "shipped", "refunded"),
            M("order_total", 5, 2000)]),
        _t("order_items", "sales", "csv", 120, "OrderItem", "composite",
           ("order_id", "line_no"),
           [C0("order_id"), C1("line_no"), FK("product_id", "erp_products"),
            I("quantity", 1, 9), M("unit_price", 1, 500),
            M("line_total", 1, 4000)]),
        _t("erp_products", "sales", "csv", 30, "ErpProduct", "natural",
           ("product_id",),
           [K("product_id"), N("product_name"),
            P("category", "home", "office", "garden", "tech"),
            M("list_price", 1, 900), P("uom", "each", "box", "kg"),
            D("erp_updated_at")]),
        _t("pim_products", "sales", "parquet", 20, "PimProduct", "natural",
           ("product_id",),
           [K("product_id"), N("product_name"),
            P("brand", "acme", "northwind", "zenith"),
            P("color", "red", "blue", "black"), NO("marketing_desc"),
            P("pim_version", "v1", "v2")]),
        _t("marketplace_products", "sales", "json", 15,
           "MarketplaceProduct", "natural", ("product_id",),
           [K("product_id"), N("product_name"),
            P("channel", "amazon", "ebay", "etsy"),
            M("market_price", 1, 1200), I("rating", 1, 5)]),
        _t("sales_channels", "sales", "csv", 12, "SalesChannel", "natural",
           ("channel_id",),
           [K("channel_id"), P("channel_name", "direct", "partner",
                               "reseller", "online"),
            P("channel_type", "owned", "third-party")]),
        _t("sales_regions", "sales", "csv", 12, "SalesRegion", "natural",
           ("region_id",),
           [K("region_id"), P("region_name", "north", "south", "east",
                              "west", "central"),
            P("country", "UK", "US", "DE", "IN")]),
        _t("sales_quotes", "sales", "json", 40, "SalesQuote", "natural",
           ("quote_id",),
           [K("quote_id"), FK("customer_id", "customers"), D("quote_date"),
            I("order", 1, 5), M("quote_total", 50, 5000)]),
        _t("sales_quote_lines", "sales", "csv", 48, "SalesQuoteLine",
           "composite", ("quote_id", "line_no"),
           [C0("quote_id"), C1("line_no"), FK("product_id", "erp_products"),
            I("qty", 1, 12), M("price", 1, 700)]),
        _t("sales_payments", "sales", "parquet", 70, "SalesPayment", "natural",
           ("payment_id",),
           [K("payment_id"), FK("order_id", "orders"), D("paid_at"),
            M("amount", 5, 3000), P("method", "card", "bank", "cash"),
            P("currency", "GBP", "USD", "EUR")]),
        _t("sales_shipments", "sales", "csv", 50, "SalesShipment", "natural",
           ("shipment_id",),
           [K("shipment_id"), FK("order_id", "orders"),
            P("carrier", "dhl", "ups", "dpd"), D("shipped_at"),
            D("delivered_at"), M("weight_kg", 0, 30)]),
        _t("sales_returns", "sales", "csv", 35, "SalesReturn", "natural",
           ("return_id",),
           [K("return_id"), FK("order_id", "orders"), D("returned_at"),
            P("reason", "damaged", "wrong-item", "changed-mind"),
            M("refund_amount", 1, 800)]),
        _t("sales_invoices", "sales", "parquet", 55, "SalesInvoice", "natural",
           ("invoice_id",),
           [K("invoice_id"), FK("order_id", "orders"),
            FK("customer_id", "customers"), D("issued_at"),
            M("invoice_total", 10, 4000), F("paid")]),
        _t("sales_discounts", "sales", "csv", 30, "SalesDiscount", "natural",
           ("discount_id",),
           [K("discount_id"), FK("channel_id", "sales_channels"),
            P("code", "SAVE10", "SAVE20", "VIP", "NONE"),
            I("pct", 5, 40), D("valid_from")]),
        _t("sales_targets", "sales", "csv", 40, "SalesTarget", "none", (),
           [FK("region_id", "sales_regions"),
            P("month", "2024-01", "2024-02", "2024-03", "2024-04",
              "2024-05", "2024-06", "2024-07", "2024-08", "2024-09",
              "2024-10", "2024-11", "2024-12"),
            M("target_amount", 1000, 90000), I("stretch", 0, 30)]),
        _t("sales_daily_rollup", "sales", "parquet", 60, "SalesDailyRollup",
           "none", (),
           [D("rollup_date"), FK("channel_id", "sales_channels"),
            FK("region_id", "sales_regions"), I("orders", 1, 40),
            M("revenue", 10, 5000)]),
        _t("sales_forecast", "sales", "csv", 45, "SalesForecast", "none", (),
           [FK("product_id", "erp_products"),
            P("month", "2024-01", "2024-02", "2024-03", "2024-04",
              "2024-05", "2024-06"),
            I("forecast_units", 10, 500),
            P("confidence", "high", "medium", "low")]),
        _t("sales_budget_lines", "sales", "csv", 36, "SalesBudgetLine",
           "composite", ("budget_id", "line_no"),
           [C0("budget_id"), C1("line_no"),
            FK("channel_id", "sales_channels"), M("amount", 100, 20000)]),
        _t("sales_commissions", "sales", "csv", 44, "SalesCommission",
           "natural", ("commission_id",),
           [K("commission_id"), FK("order_id", "orders"), N("rep_name"),
            I("commission_pct", 1, 15),
            M("commission_amount", 1, 500)]),
        _t("sales_leads", "sales", "csv", 65, "SalesLead", "natural",
           ("lead_id",),
           [K("lead_id"), N("lead_name"), CI("city"),
            P("source", "web", "event", "referral", "ads"),
            D("created_at"), F("converted")]),
        _t("sales_pipeline", "sales", "parquet", 52, "SalesPipeline", "none",
           (),
           [P("stage", "discovery", "proposal", "negotiation", "won",
              "lost"),
            FK("account_id", "crm_accounts"), M("amount", 100, 50000),
            I("probability", 0, 100)]),
        _t("sales_targets_v2", "sales", "csv", 38, "SalesTarget2", "none", (),
           [FK("region_id", "sales_regions"),
            P("quarter", "Q1", "Q2", "Q3", "Q4"),
            M("goal", 1000, 90000), M("actual", 500, 95000)]),
        _t("sales_refunds", "sales", "csv", 33, "SalesRefund", "natural",
           ("refund_id",),
           [K("refund_id"), FK("payment_id", "sales_payments"),
            D("refunded_at"), M("refund_amount", 1, 600),
            P("reason", "duplicate", "fraud", "service")]),
        _t("sales_segments", "sales", "json", 14, "SalesSegment", "natural",
           ("segment_id",),
           [K("segment_id"), P("segment_name", "smb", "mid", "enterprise"),
            P("group", "A", "B", "C"), NO("description")]),
        _t("sales_events", "sales", "json", 58, "SalesEvent", "natural",
           ("event_id",),
           [K("event_id"), FK("customer_id", "customers"),
            P("event_type", "view", "click", "cart", "purchase"),
            D("occurred_at"), P("select", "yes", "no")]),
        _t("stg_orders_raw", "sales", "csv", 80, "Order2", "none", (),
           [FK("order_id", "orders"), FK("customer_id", "customers"),
            P("select", "true", "false"), P("load_batch", "b1", "b2", "b3"),
            M("raw_amount", 1, 2000)]),
        _t("tbl_cust_01", "sales", "csv", 36, "Cust", "natural",
           ("cust_id",),
           [K("cust_id"), N("cust_name"), CI("city"),
            P("segment", "retail", "wholesale"),
            D("signup_date")]),
        _t("fct_sales_2024", "sales", "csv", 62, "Sale", "none", (),
           [FK("customer_id", "customers"),
            FK("region_id", "sales_regions"), M("revenue", 10, 9000),
            I("units", 1, 60), I("order", 1, 5)]),
    ]

    # -------------------------------------------------------- inventory (25)
    p += [
        _t("inventory_warehouses", "inventory", "csv", 12,
           "InventoryWarehouse", "natural", ("warehouse_id",),
           [K("warehouse_id"), P("warehouse_name", "north", "south", "east"),
            CI("city"), I("capacity", 100, 5000)]),
        _t("inventory_stock", "inventory", "parquet", 64, "InventoryStock",
           "composite", ("warehouse_id", "product_id"),
           [C0("warehouse_id"), C1("product_id"), I("on_hand", 0, 500),
            I("reserved", 0, 50), I("reorder_point", 5, 50)]),
        _t("inventory_movements", "inventory", "parquet", 90,
           "InventoryMovement", "natural", ("movement_id",),
           [K("movement_id"), FK("warehouse_id", "inventory_warehouses"),
            FK("product_id", "erp_products"), D("moved_at"),
            I("qty", -50, 50),
            P("movement_type", "in", "out", "transfer", "adjust")]),
        _t("inventory_suppliers", "inventory", "json", 20,
           "InventorySupplier", "natural", ("supplier_id",),
           [K("supplier_id"), N("supplier_name"),
            P("country", "UK", "CN", "DE", "US"), I("lead_days", 1, 30),
            I("rating", 1, 5)]),
        _t("inventory_receipts", "inventory", "parquet", 45,
           "InventoryReceipt", "natural", ("receipt_id",),
           [K("receipt_id"), FK("supplier_id", "inventory_suppliers"),
            FK("warehouse_id", "inventory_warehouses"), D("received_at"),
            M("receipt_total", 50, 9000)]),
        _t("inventory_receipt_lines", "inventory", "csv", 70,
           "InventoryReceiptLine", "composite", ("receipt_id", "line_no"),
           [C0("receipt_id"), C1("line_no"),
            FK("product_id", "erp_products"), I("qty", 1, 100),
            M("unit_cost", 1, 400)]),
        _t("inventory_cycle_counts", "inventory", "csv", 40,
           "InventoryCycleCount", "none", (),
           [FK("warehouse_id", "inventory_warehouses"),
            FK("product_id", "erp_products"), D("counted_at"),
            I("counted_qty", 0, 400), I("expected_qty", 0, 400)]),
        _t("inventory_adjustments", "inventory", "csv", 36,
           "InventoryAdjustment", "natural", ("adjustment_id",),
           [K("adjustment_id"),
            FK("warehouse_id", "inventory_warehouses"),
            FK("product_id", "erp_products"), D("adjusted_at"),
            I("delta", -30, 30),
            P("reason", "shrinkage", "damage", "miscount")]),
        _t("inventory_transfers", "inventory", "csv", 42,
           "InventoryTransfer", "natural", ("transfer_id",),
           [K("transfer_id"),
            FK("warehouse_id", "inventory_warehouses"),
            I("dest_warehouse_id", 1, 12),
            FK("product_id", "erp_products"), I("qty", 1, 80),
            D("shipped_at")]),
        _t("inventory_bins", "inventory", "csv", 30, "InventoryBin",
           "natural", ("bin_id",),
           [K("bin_id"), FK("warehouse_id", "inventory_warehouses"),
            P("aisle", "A", "B", "C", "D"), P("shelf", "1", "2", "3"),
            I("capacity", 10, 200)]),
        _t("inventory_batches", "inventory", "parquet", 55,
           "InventoryBatch", "natural", ("batch_id",),
           [K("batch_id"), FK("product_id", "erp_products"),
            P("batch_code", "LOT-1", "LOT-2", "LOT-3", "LOT-4"),
            D("expires_at"), I("qty", 1, 300)]),
        _t("inventory_reorder", "inventory", "csv", 38, "InventoryReorder",
           "none", (),
           [FK("product_id", "erp_products"),
            FK("warehouse_id", "inventory_warehouses"),
            I("suggested_qty", 5, 500), I("lead_days", 1, 30),
            P("priority", "low", "medium", "high")]),
        _t("inventory_backorders", "inventory", "csv", 44,
           "InventoryBackorder", "natural", ("backorder_id",),
           [K("backorder_id"), FK("order_id", "orders"),
            FK("product_id", "erp_products"), I("qty", 1, 50),
            D("promised_at")]),
        _t("inventory_allocations", "inventory", "csv", 60,
           "InventoryAllocation", "composite", ("order_id", "product_id"),
           [C0("order_id"), C1("product_id"),
            FK("warehouse_id", "inventory_warehouses"), I("qty", 1, 20),
            D("allocated_at")]),
        _t("inventory_picking", "inventory", "csv", 66, "InventoryPick",
           "natural", ("pick_id",),
           [K("pick_id"), FK("order_id", "orders"),
            FK("warehouse_id", "inventory_warehouses"), D("picked_at"),
            N("picker"), I("qty", 1, 20)]),
        _t("inventory_putaway", "inventory", "csv", 48,
           "InventoryPutaway", "natural", ("putaway_id",),
           [K("putaway_id"), FK("receipt_id", "inventory_receipts"),
            FK("bin_id", "inventory_bins"), D("putaway_at"),
            I("qty", 1, 100)]),
        _t("inventory_serials", "inventory", "csv", 34, "InventorySerial",
           "natural", ("serial_id",),
           [K("serial_id"), FK("product_id", "erp_products"),
            P("serial_no", "SN-A", "SN-B", "SN-C", "SN-D", "SN-E"),
            P("status", "in-stock", "sold", "rma"),
            I("warranty_months", 3, 36)]),
        _t("inventory_returns", "inventory", "csv", 40,
           "InventoryReturn", "natural", ("inv_return_id",),
           [K("inv_return_id"), FK("order_id", "orders"),
            FK("product_id", "erp_products"), D("returned_at"),
            I("qty", 1, 10),
            P("condition", "new", "used", "broken")]),
        _t("stg_inventory_raw", "inventory", "csv", 72, "Inventory", "none",
           (),
           [FK("product_id", "erp_products"),
            FK("warehouse_id", "inventory_warehouses"),
            P("load_batch", "b1", "b2", "b3", "b4"),
            I("raw_qty", 0, 100), D("load_date")]),
        _t("tbl_stock_01", "inventory", "csv", 36, "Stock", "natural",
           ("stock_id",),
           [K("stock_id"), FK("product_id", "erp_products"),
            FK("warehouse_id", "inventory_warehouses"), I("qty", 0, 200),
            P("group", "A", "B", "C")]),
        _t("dim_warehouse_v2", "inventory", "csv", 15, "Warehouse",
           "natural", ("warehouse_id",),
           [K("warehouse_id"), P("warehouse_name", "north", "south", "east"),
            CI("city"), F("active")]),
        _t("fct_stock_snapshot_2024", "inventory", "csv", 60,
           "StockSnapshot", "none", (),
           [FK("product_id", "erp_products"),
            FK("warehouse_id", "inventory_warehouses"), D("snapshot_date"),
            I("on_hand", 0, 400), M("value", 10, 9000)]),
        _t("inventory_demand", "inventory", "parquet", 50,
           "InventoryDemand", "none", (),
           [FK("product_id", "erp_products"),
            P("week", "W01", "W02", "W03", "W04", "W05", "W06", "W07",
              "W08", "W09", "W10", "W11", "W12"),
            I("demand_units", 0, 200), I("forecast_units", 0, 200)]),
        _t("inventory_damage", "inventory", "csv", 26, "InventoryDamage",
           "natural", ("damage_id",),
           [K("damage_id"), FK("product_id", "erp_products"),
            FK("warehouse_id", "inventory_warehouses"), D("damaged_on"),
            I("qty", 1, 10), NO("note")]),
        _t("inventory_aging", "inventory", "csv", 46, "InventoryAging",
           "none", (),
           [FK("product_id", "erp_products"),
            FK("warehouse_id", "inventory_warehouses"),
            P("bucket", "0-30", "31-60", "61-90", "90+"),
            I("qty", 0, 300), M("value", 10, 6000)]),
    ]

    # --------------------------------------------------------------- crm (24)
    p += [
        _t("crm_accounts", "crm", "csv", 50, "CrmAccount", "natural",
           ("account_id",),
           [K("account_id"), N("account_name"),
            P("industry", "retail", "tech", "health", "finance"),
            P("country", "UK", "US", "DE", "IN"), D("created_at"),
            P("tier", "bronze", "silver", "gold")]),
        _t("crm_contacts", "crm", "parquet", 80, "CrmContact", "natural",
           ("contact_id",),
           [K("contact_id"), FK("account_id", "crm_accounts"),
            N("contact_name"),
            P("email_local", "info", "sales", "support", "hello", "team"),
            CI("city"), F("opted_in")]),
        _t("crm_opportunities", "crm", "parquet", 45,
           "CrmOpportunity", "natural", ("opportunity_id",),
           [K("opportunity_id"), FK("account_id", "crm_accounts"),
            FK("contact_id", "crm_contacts"),
            P("stage", "discovery", "proposal", "won", "lost"),
            M("amount", 500, 80000), D("close_date")]),
        _t("crm_activities", "crm", "parquet", 95, "CrmActivity", "none",
           (),
           [FK("contact_id", "crm_contacts"),
            P("activity_type", "call", "email", "meeting", "note"),
            D("occurred_at"), I("duration_min", 1, 120), N("owner")]),
        _t("crm_campaigns", "crm", "csv", 22, "CrmCampaign", "natural",
           ("campaign_id",),
           [K("campaign_id"),
            P("campaign_name", "spring", "summer", "black-friday", "launch"),
            P("channel", "email", "social", "search"),
            M("budget", 500, 50000), D("start_date")]),
        _t("crm_tickets", "crm", "parquet", 70, "CrmTicket", "natural",
           ("ticket_id",),
           [K("ticket_id"), FK("account_id", "crm_accounts"),
            FK("contact_id", "crm_contacts"), D("opened_at"),
            P("priority", "low", "medium", "high", "urgent"),
            P("status", "open", "pending", "closed"),
            P("group", "support", "billing", "tech")]),
        _t("crm_ticket_events", "crm", "csv", 88, "CrmTicketEvent",
           "composite", ("ticket_id", "event_no"),
           [C0("ticket_id"), C1("event_no"),
            P("event_type", "opened", "replied", "escalated", "closed"),
            D("occurred_at"), NO("note")]),
        _t("crm_consents", "crm", "csv", 60, "CrmConsent", "none", (),
           [FK("contact_id", "crm_contacts"),
            P("consent_type", "email", "sms", "post"), F("granted"),
            D("changed_at")]),
        _t("crm_subscriptions", "crm", "csv", 55, "CrmSubscription",
           "natural", ("subscription_id",),
           [K("subscription_id"), FK("account_id", "crm_accounts"),
            P("plan", "basic", "pro", "enterprise"), D("started_on"),
            M("mrr", 10, 5000), P("status", "active", "paused", "cancelled")]),
        _t("crm_churn_scores", "crm", "csv", 64, "CrmChurnScore", "none",
           (),
           [FK("account_id", "crm_accounts"), D("scored_at"),
            I("churn_score", 0, 100),
            P("risk_band", "low", "medium", "high")]),
        _t("crm_segments", "crm", "json", 16, "CrmSegment", "natural",
           ("segment_id",),
           [K("segment_id"),
            P("segment_name", "smb", "mid", "enterprise"),
            P("group", "A", "B", "C"), NO("description")]),
        _t("crm_emails", "crm", "parquet", 75, "CrmEmail", "natural",
           ("email_id",),
           [K("email_id"), FK("campaign_id", "crm_campaigns"),
            FK("contact_id", "crm_contacts"), D("sent_at"), F("opened"),
            F("clicked")]),
        _t("crm_calls", "crm", "csv", 52, "CrmCall", "natural",
           ("call_id",),
           [K("call_id"), FK("contact_id", "crm_contacts"),
            D("called_at"), I("duration_sec", 10, 900),
            P("outcome", "connected", "voicemail", "no-answer")]),
        _t("crm_meetings", "crm", "csv", 30, "CrmMeeting", "natural",
           ("meeting_id",),
           [K("meeting_id"), FK("account_id", "crm_accounts"),
            FK("contact_id", "crm_contacts"), D("meeting_at"),
            I("attendees", 1, 20), NO("notes")]),
        _t("crm_notes", "crm", "csv", 85, "CrmNote", "natural",
           ("note_id",),
           [K("note_id"), FK("account_id", "crm_accounts"),
            FK("contact_id", "crm_contacts"), D("created_at"),
            NO("body")]),
        _t("crm_prospects", "crm", "json", 48, "CrmProspect", "natural",
           ("prospect_id",),
           [K("prospect_id"), N("prospect_name"),
            P("source", "web", "event", "referral"), CI("city"),
            D("created_at")]),
        _t("crm_owners", "crm", "csv", 14, "CrmOwner", "natural",
           ("owner_id",),
           [K("owner_id"), N("owner_name"),
            FK("region_id", "sales_regions"),
            P("email_local", "a", "b", "c", "d")]),
        _t("crm_loyalty", "crm", "csv", 42, "CrmLoyalty", "none", (),
           [FK("customer_id", "customers"),
            P("tier", "bronze", "silver", "gold"), I("points", 0, 10000),
            D("joined_at")]),
        _t("crm_nps", "crm", "csv", 58, "CrmNps", "none", (),
           [FK("account_id", "crm_accounts"), D("survey_date"),
            I("score", 0, 10), NO("comment")]),
        _t("crm_cases", "crm", "csv", 40, "CrmCase", "natural",
           ("case_id",),
           [K("case_id"), FK("account_id", "crm_accounts"),
            D("opened_at"), P("severity", "low", "medium", "high"),
            I("resolution_days", 0, 60), P("select", "yes", "no")]),
        _t("tbl_contact_01", "crm", "csv", 44, "Contact", "natural",
           ("contact_id",),
           [K("contact_id"), FK("account_id", "crm_accounts"),
            N("contact_name"), CI("city"), I("order", 1, 9)]),
        _t("dim_account_v2", "crm", "csv", 28, "Account", "natural",
           ("account_id",),
           [K("account_id"), N("account_name"),
            P("industry", "retail", "tech", "health", "finance"),
            P("country", "UK", "US", "DE", "IN")]),
        _t("fct_engagement_2024", "crm", "csv", 68, "Engagement", "none",
           (),
           [FK("contact_id", "crm_contacts"),
            FK("campaign_id", "crm_campaigns"),
            P("engagement_type", "open", "click", "reply", "unsubscribe"),
            D("engaged_at"), I("score", 0, 100)]),
        _t("crm_customer_profiles", "crm", "csv", 46,
           "CrmCustomerProfile", "none", (),
           [FK("customer_id", "customers"),
            FK("segment_id", "crm_segments"), M("ltv", 100, 50000),
            D("updated_at"),
            P("preferred_channel", "email", "phone", "post")]),
    ]

    # ----------------------------------------------------------- finance (22)
    p += [
        _t("finance_gl_entries", "finance", "parquet", 100,
           "FinanceGlEntry", "natural", ("entry_id",),
           [K("entry_id"),
            P("account_code", "4000", "4100", "5000", "6100", "6200"),
            P("period", "2024-01", "2024-02", "2024-03", "2024-04",
              "2024-05", "2024-06"),
            D("posted_at"), M("debit", 0, 20000), M("credit", 0, 20000),
            NO("memo")]),
        _t("finance_chart_of_accounts", "finance", "json", 40,
           "FinanceChartOfAccount", "natural", ("account_id",),
           [K("account_id"),
            P("account_code", "4000", "4100", "5000", "6100", "6200",
              "6300", "7000"),
            N("account_name"),
            P("account_type", "asset", "liability", "equity", "revenue",
              "expense"),
            P("currency", "GBP", "USD", "EUR")]),
        _t("finance_journal_lines", "finance", "csv", 72,
           "FinanceJournalLine", "composite", ("journal_id", "line_no"),
           [C0("journal_id"), C1("line_no"),
            FK("account_id", "finance_chart_of_accounts"),
            M("debit", 0, 15000), M("credit", 0, 15000),
            NO("description")]),
        _t("finance_cost_centers", "finance", "csv", 18,
           "FinanceCostCenter", "natural", ("cost_center_id",),
           [K("cost_center_id"),
            P("cost_center_name", "ops", "sales", "it", "hr"),
            FK("region_id", "sales_regions"), N("manager")]),
        _t("finance_budgets", "finance", "csv", 48, "FinanceBudget", "none",
           (),
           [FK("cost_center_id", "finance_cost_centers"),
            P("period", "2024-01", "2024-02", "2024-03", "2024-04",
              "2024-05", "2024-06"),
            M("budget_amount", 1000, 80000),
            M("actual_amount", 500, 90000)]),
        _t("finance_actuals", "finance", "parquet", 64, "FinanceActual",
           "none", (),
           [FK("cost_center_id", "finance_cost_centers"),
            FK("account_id", "finance_chart_of_accounts"),
            P("period", "2024-01", "2024-02", "2024-03", "2024-04",
              "2024-05", "2024-06"),
            M("amount", 10, 10000)]),
        _t("finance_ap_invoices", "finance", "parquet", 50,
           "FinanceApInvoice", "natural", ("ap_invoice_id",),
           [K("ap_invoice_id"),
            FK("supplier_id", "inventory_suppliers"), D("received_at"),
            D("due_at"), M("amount", 50, 20000),
            P("status", "open", "paid", "overdue")]),
        _t("finance_ar_invoices", "finance", "csv", 54,
           "FinanceArInvoice", "natural", ("ar_invoice_id",),
           [K("ar_invoice_id"), FK("customer_id", "customers"),
            D("issued_at"), D("due_at"), M("amount", 20, 30000),
            P("paid", "yes", "no")]),
        _t("finance_tax_rates", "finance", "csv", 24, "FinanceTaxRate",
           "natural", ("tax_rate_id",),
           [K("tax_rate_id"),
            P("country", "UK", "US", "DE", "IN"), M("rate_pct", 0, 25),
            D("effective_from"), P("tax_name", "vat", "gst", "sales-tax")]),
        _t("finance_exchange_rates", "finance", "json", 40,
           "FinanceExchangeRate", "natural", ("rate_id",),
           [K("rate_id"), P("from_currency", "GBP", "USD", "EUR"),
            P("to_currency", "USD", "EUR", "JPY"), D("rate_date"),
            M("rate", 0.5, 2)]),
        _t("finance_periods", "finance", "json", 14, "FinancePeriod",
           "natural", ("period_id",),
           [K("period_id"),
            P("period_name", "2024-01", "2024-02", "2024-03", "2024-04",
              "2024-05", "2024-06", "2024-07", "2024-08", "2024-09",
              "2024-10", "2024-11", "2024-12"),
            F("closed"), D("opened_at")]),
        _t("finance_assets", "finance", "csv", 36, "FinanceAsset",
           "natural", ("asset_id",),
           [K("asset_id"), FK("cost_center_id", "finance_cost_centers"),
            P("asset_name", "server", "licence", "vehicle", "building"),
            D("purchased_at"), M("cost", 500, 100000),
            I("useful_life_months", 12, 120)]),
        _t("finance_depreciation", "finance", "csv", 44,
           "FinanceDepreciation", "none", (),
           [FK("asset_id", "finance_assets"), D("run_date"),
            M("depreciation", 10, 2000), M("accumulated", 10, 50000)]),
        _t("finance_balance_snapshot", "finance", "csv", 60,
           "FinanceBalanceSnapshot", "none", (),
           [FK("account_id", "finance_chart_of_accounts"),
            P("period", "2024-01", "2024-02", "2024-03", "2024-04",
              "2024-05", "2024-06"),
            M("debit_total", 0, 500000), M("credit_total", 0, 500000),
            M("balance", -100000, 500000)]),
        _t("finance_cashflow", "finance", "csv", 48, "FinanceCashflow",
           "none", (),
           [P("period", "2024-01", "2024-02", "2024-03", "2024-04",
              "2024-05", "2024-06"),
            FK("cost_center_id", "finance_cost_centers"),
            M("inflow", 0, 90000), M("outflow", 0, 90000),
            M("net", -50000, 90000)]),
        _t("finance_vat_returns", "finance", "json", 20,
           "FinanceVatReturn", "natural", ("vat_return_id",),
           [K("vat_return_id"),
            P("country", "UK", "US", "DE", "IN"),
            P("period", "2024-01", "2024-02", "2024-03", "2024-04"),
            M("vat_due", 100, 40000), D("filed_at")]),
        _t("finance_purchase_orders", "finance", "parquet", 58,
           "FinancePurchaseOrder", "natural", ("po_id",),
           [K("po_id"), FK("supplier_id", "inventory_suppliers"),
            FK("cost_center_id", "finance_cost_centers"), D("ordered_at"),
            M("total", 50, 50000),
            P("status", "draft", "approved", "received", "cancelled")]),
        _t("finance_po_lines", "finance", "parquet", 76,
           "FinancePoLine", "composite", ("po_id", "line_no"),
           [C0("po_id"), C1("line_no"),
            FK("product_id", "erp_products"), I("qty", 1, 200),
            M("unit_cost", 1, 500)]),
        _t("finance_credit_notes", "finance", "csv", 32,
           "FinanceCreditNote", "natural", ("credit_note_id",),
           [K("credit_note_id"), FK("customer_id", "customers"),
            D("issued_at"), M("amount", 10, 5000),
            P("reason", "return", "discount", "error")]),
        _t("stg_finance_raw", "finance", "csv", 84, "Finance", "none", (),
           [FK("account_id", "finance_chart_of_accounts"),
            P("period", "2024-01", "2024-02", "2024-03", "2024-04",
              "2024-05", "2024-06"),
            M("debit", 0, 15000), M("credit", 0, 15000),
            P("load_batch", "b1", "b2", "b3"), D("load_date")]),
        _t("tbl_ledger_01", "finance", "csv", 56, "Ledger", "natural",
           ("ledger_id",),
           [K("ledger_id"),
            FK("account_id", "finance_chart_of_accounts"),
            P("period", "2024-01", "2024-02", "2024-03", "2024-04"),
            M("amount", 10, 20000), P("select", "yes", "no")]),
        _t("fct_revenue_2024", "finance", "csv", 62, "Revenue", "none", (),
           [FK("customer_id", "customers"),
            FK("region_id", "sales_regions"), M("revenue", 10, 9000),
            I("units", 1, 60), I("order", 1, 5)]),
    ]

    return p


# ------------------------------------------------------------- generation
def _rng(table_name: str) -> random.Random:
    """A per-table RNG, stable across processes and platforms."""
    digest = hashlib.sha256(f"{SEED}:{table_name}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _type_of(spec: str) -> str:
    if spec in ("key", "comp:0", "comp:1"):
        return "BIGINT"
    if spec.startswith("fk:") or spec.startswith("int:"):
        return "BIGINT"
    if spec.startswith("money:"):
        return "DOUBLE"
    if spec == "date":
        return "DATE"
    return "VARCHAR"


def _looks_like_id(name: str) -> bool:
    low = name.lower()
    return low == "id" or low.endswith(("_id", "id", "_key", "_code", "_no"))


def _family(spec: str) -> str:
    if spec in ("key", "comp:0", "comp:1") or spec.startswith(
            ("fk:", "int:", "money:")):
        return "numeric"
    if spec == "date":
        return "temporal"
    return "text"


def _eligible_as_key(column: str, spec: str) -> bool:
    """Mirror ontology.keys: numeric columns only count if id-like, dates
    never count, text always can."""
    family = _family(spec)
    if family == "numeric":
        return _looks_like_id(column)
    if family == "temporal":
        return False
    return True


def _values(spec: str, plan: TablePlan, rng: random.Random,
            fk_rows: dict[str, int]) -> list:
    rows = plan.rows
    if spec == "key":
        return list(range(1, rows + 1))
    if spec == "comp:0":
        return [i // COMPOSITE_INNER + 1 for i in range(rows)]
    if spec == "comp:1":
        return [i % COMPOSITE_INNER + 1 for i in range(rows)]
    if spec.startswith("fk:"):
        target = spec[3:]
        top = min(20, fk_rows[target])
        out = [rng.randint(1, top) for _ in range(rows)]
        # A few deliberate orphan references: rows that point at nothing.
        if rows >= 6:
            out[-1] = 9001
            out[-2] = 9002
        return out
    if spec.startswith("pick:"):
        choices = spec[5:].split("|")
        return [choices[(i * 7 + 3) % len(choices)] for i in range(rows)]
    if spec.startswith("int:"):
        _, lo, hi = spec.split(":")
        return [rng.randint(int(lo), int(hi)) for _ in range(rows)]
    if spec.startswith("money:"):
        _, lo, hi = spec.split(":")
        return [round(rng.uniform(float(lo), float(hi)), 2)
                for _ in range(rows)]
    if spec == "date":
        base = date(2024, 1, 1)
        return [base + timedelta(days=rng.randrange(365))
                for _ in range(rows)]
    if spec == "name":
        pool = NAMES[:max(2, min(len(NAMES), max(2, rows // 2)))]
        return [pool[(i * 5 + 1) % len(pool)] for i in range(rows)]
    if spec == "city":
        pool = CITIES
        return [pool[(i * 3) % len(pool)] for i in range(rows)]
    if spec == "note":
        pool = NOTES
        return [pool[(i * 2) % len(pool)] for i in range(rows)]
    if spec == "flag":
        return [["yes", "no"][i % 2] for i in range(rows)]
    raise ValueError(f"unknown generator spec: {spec!r}")


def _validate(plan: TablePlan, values: dict[str, list],
              specs: dict[str, str]) -> None:
    """Fail generation rather than silently produce a table that breaks the
    fixture's stated properties (natural key unique, no-key truly keyless)."""
    rows = plan.rows
    for col, vals in values.items():
        if len(vals) != rows:
            raise AssertionError(f"{plan.name}.{col}: {len(vals)} != {rows}")
        if any(v is None for v in vals):
            raise AssertionError(f"{plan.name}.{col}: null generated")
    unique_eligible = [
        col for col, vals in values.items()
        if len(set(vals)) == rows and _eligible_as_key(col, specs[col])]

    if plan.key_kind == "natural":
        if tuple(unique_eligible) != plan.key_cols:
            raise AssertionError(
                f"{plan.name}: expected exactly natural key "
                f"{plan.key_cols}, got eligible-unique {unique_eligible}")
    else:
        if unique_eligible:
            raise AssertionError(
                f"{plan.name}: key_kind={plan.key_kind} but these columns are "
                f"unique and key-eligible: {unique_eligible}")

    if plan.key_kind == "composite":
        combos = {tuple(values[c][i] for c in plan.key_cols)
                  for i in range(rows)}
        if len(combos) != rows:
            raise AssertionError(
                f"{plan.name}: composite key {plan.key_cols} is not unique")


def _csv_cell(value) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _write_csv(path: Path, plan: TablePlan, values: dict[str, list]) -> None:
    cols = [c for c, _ in plan.cols]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(cols)
        for i in range(plan.rows):
            writer.writerow([_csv_cell(values[c][i]) for c in cols])


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _duck_type(spec: str) -> str:
    family = _family(spec)
    if family == "temporal":
        return "DATE"
    if family == "numeric":
        return "DOUBLE" if spec.startswith("money:") else "BIGINT"
    return "VARCHAR"


def _write_parquet(path: Path, plan: TablePlan,
                   values: dict[str, list]) -> None:
    """Write Parquet through DuckDB, not pyarrow.

    DuckDB is already the engine this project reads every source with, so the
    writer adds no dependency. It is also the dependable choice on a
    locked-down Windows machine: Application Control blocks pandas' compiled
    DLL there, and pyarrow's array constructor lazily imports pandas to ask
    "is this array-like?" - so a pyarrow write dies after the app's guarded
    `import pandas` fails. DuckDB never touches pandas.
    """
    import duckdb

    columns = [c for c, _ in plan.cols]
    ddl = ", ".join(f"{_quote_ident(c)} {_duck_type(spec)}"
                    for c, spec in plan.cols)
    placeholders = ", ".join("?" * len(columns))
    con = duckdb.connect(":memory:")
    try:
        con.execute(f"CREATE TABLE lake_table ({ddl})")
        con.executemany(
            f"INSERT INTO lake_table VALUES ({placeholders})",
            [tuple(values[c][i] for c in columns) for i in range(plan.rows)])
        escaped = str(path).replace("'", "''")
        con.execute(f"COPY lake_table TO '{escaped}' (FORMAT PARQUET)")
    finally:
        con.close()


def _write_json(path: Path, plan: TablePlan, values: dict[str, list]) -> None:
    cols = [c for c, _ in plan.cols]
    records = [{c: values[c][i] for c in cols} for i in range(plan.rows)]
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(records, f, ensure_ascii=False, separators=(",", ":"),
                  default=lambda o: o.isoformat() if isinstance(o, date)
                  else str(o))
        f.write("\n")


_WRITERS = {"csv": _write_csv, "parquet": _write_parquet,
            "json": _write_json}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _simulated_discovery(plans_by_name: dict[str, TablePlan],
                        distinct: dict[str, dict[str, int]],
                        filename_order: list[str]):
    """What connect()+discover() should produce for these shapes, without
    opening DuckDB.

    connect() profiles each file once (distinct + non-null) and lets
    pick_key() choose a key; a file source can never declare a foreign key.
    Rebuilding exactly that shape here keeps the ground truth honest about
    the CURRENT code's expected output.
    """
    from ontology.discover import discover
    from ontology.keys import pick_key
    from ontology.schema import Column, Schema, Table

    tables = []
    expected_key: dict[str, list[str]] = {}
    for filename in filename_order:                 # folder order is sorted
        plan = plans_by_name[filename.rsplit(".", 1)[0]]
        stats = distinct[plan.name]
        columns = [Column(name=c, type=_type_of(spec), nullable=False,
                          distinct=stats[c]) for c, spec in plan.cols]
        table = Table(name=plan.name, columns=columns, primary_key=[],
                      foreign_keys=[], row_count=plan.rows)
        found = pick_key(table)
        if found:
            table.primary_key = [found]
        expected_key[plan.name] = [found] if found else ["__row"]
        tables.append(table)

    schema = Schema(tables=tables, name="lake100", origin="", readers={})
    onto = discover(schema)

    class_of_table = {
        plan.name: next(c.name for c in onto.classes.values()
                        if c.table == plan.name)
        for plan in plans_by_name.values()}
    relations = sorted((
        {
            "domain_table": onto.classes[r.domain].table,
            "column": r.column,
            "range_table": onto.classes[r.range].table,
            "domain_class": r.domain,
            "range_class": r.range,
            "provenance": r.provenance,
        }
        for r in onto.relations.values()
    ), key=lambda r: (r["domain_table"], r["column"], r["range_table"]))
    return class_of_table, expected_key, relations


def generate(out: str | Path = DEFAULT_OUT,
             truth_path: str | Path | None = DEFAULT_TRUTH,
             quiet: bool = False) -> dict:
    """Write the fixture and (optionally) its ground truth. Returns the truth.

    Deterministic: no clock, no absolute paths, no network. `truth_path=None`
    writes only the data files (used by --check inside a temp folder).
    """
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    # Clear only files this generator owns; leave anything else alone.
    for old in out.iterdir():
        if old.is_file() and old.suffix.lower().lstrip(".") in FORMATS:
            old.unlink()

    all_plans = plans()
    if len(all_plans) != 100:
        raise AssertionError(f"lake100 must have 100 tables, got {len(all_plans)}")
    plans_by_name = {p.name: p for p in all_plans}
    if len(plans_by_name) != len(all_plans):
        raise AssertionError("duplicate table name in plans")
    fk_rows = {p.name: p.rows for p in all_plans}
    filename_order = sorted(f"{p.name}.{p.fmt}" for p in all_plans)

    distinct: dict[str, dict[str, int]] = {}
    values_by_table: dict[str, dict[str, list]] = {}
    for plan in all_plans:
        rng = _rng(plan.name)
        specs = dict(plan.cols)
        values = {col: _values(spec, plan, rng, fk_rows)
                  for col, spec in plan.cols}
        _validate(plan, values, specs)
        distinct[plan.name] = {c: len(set(v)) for c, v in values.items()}
        values_by_table[plan.name] = values

    files: dict[str, str] = {}
    for filename in filename_order:
        plan = plans_by_name[filename.rsplit(".", 1)[0]]
        path = out / filename
        _WRITERS[plan.fmt](path, plan, values_by_table[plan.name])
        files[filename] = _sha256(path)

    class_of_table, expected_key, relations = _simulated_discovery(
        plans_by_name, distinct, filename_order)

    # ------------------------------------------------------------- counts
    formats = {f: sum(1 for p in all_plans if p.fmt == f) for f in FORMATS}
    domains = {d: sum(1 for p in all_plans if p.domain == d)
               for d in ("sales", "inventory", "crm", "finance")}
    key_kinds = {k: sum(1 for p in all_plans if p.key_kind == k)
                 for k in ("natural", "composite", "none")}
    reserved = {p.name: [c for c, _ in p.cols if c in RESERVED_WORDS]
                for p in all_plans}
    reserved = {k: v for k, v in sorted(reserved.items()) if v}
    fk_tables = sorted({p.name for p in all_plans
                        for c, spec in p.cols
                        if spec.startswith("fk:")})
    non_ascii_tables = sorted({
        name for name, values in values_by_table.items()
        for col, vals in values.items()
        if any(isinstance(v, str) and not v.isascii() for v in vals)})

    product_masters = ("erp_products", "pim_products",
                       "marketplace_products")
    truth = {
        "fixture": GENERATOR,
        "generator_version": GENERATOR_VERSION,
        "seed": SEED,
        "table_count": len(all_plans),
        "counts": {
            "tables": len(all_plans),
            "rows": sum(p.rows for p in all_plans),
            "formats": formats,
            "domains": domains,
            "key_kinds": key_kinds,
            "tables_with_fk_columns": len(fk_tables),
            "tables_with_no_usable_key": key_kinds["none"]
            + key_kinds["composite"],
            "tables_with_reserved_word_columns": len(reserved),
            "tables_with_non_ascii_values": len(non_ascii_tables),
        },
        "tables": [
            {
                "name": p.name,
                "file": f"{p.name}.{p.fmt}",
                "domain": p.domain,
                "format": p.fmt,
                "rows": p.rows,
                "class": class_of_table[p.name],
                "declared_key": None,
                "expected_key": expected_key[p.name],
                "key_kind": p.key_kind,
                "intended_key": list(p.key_cols),
                "key_note": ("natural key inferred from data"
                             if p.key_kind == "natural" else
                             "a file cannot declare a composite key; current "
                             "discovery falls back to the synthetic __row"
                             if p.key_kind == "composite" else
                             "no single usable key; current discovery falls "
                             "back to the synthetic __row"),
            }
            for p in sorted(all_plans, key=lambda x: x.name)
        ],
        "expected_relations": relations,
        "product_masters": {
            "tables": [f"{n}.{plans_by_name[n].fmt}" for n in product_masters],
            "shared_key": "product_id",
            "coverage_rows": {n: plans_by_name[n].rows
                              for n in product_masters},
            "expected_classes": {n: class_of_table[n] for n in product_masters},
            "note": ("Same product_id space, different attributes and "
                     "coverage. Current single-source discovery models them "
                     "as three separate classes and does not merge them; only "
                     "the first product-named table in folder order receives "
                     "product_id edges."),
        },
        "special_cases": {
            "reserved_word_columns": reserved,
            "composite_key_tables": sorted(
                p.name for p in all_plans if p.key_kind == "composite"),
            "no_key_tables": sorted(
                p.name for p in all_plans if p.key_kind == "none"),
            "tables_with_fk_columns": fk_tables,
            "non_ascii_tables": non_ascii_tables,
        },
        "files": dict(sorted(files.items())),
        "notes": {
            "determinism": ("Fixed seed, per-table RNG from the table name, "
                            "fixed date range 2024-01-01..2024-12-31, no "
                            "clock and no absolute paths in the output."),
            "ground_truth_derivation": (
                "class and expected_relations are derived by replaying the "
                "CURRENT naming rules (ontology.discover) on the same table/"
                "column shapes; regenerating is required if those rules "
                "change."),
            "orphans": ("A few foreign-key rows hold 9001/9002 on purpose, so "
                        "rows pointing at nothing are exercised."),
            "formats": ("connect() reads one folder level; all 100 files are "
                        "directly in the folder."),
        },
    }

    if truth_path is not None:
        truth_path = Path(truth_path)
        truth_path.parent.mkdir(parents=True, exist_ok=True)
        truth_path.write_text(
            json.dumps(truth, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")

    if not quiet:
        print(f"lake100 generated")
        print(f"  out    : {out}")
        if truth_path is not None:
            print(f"  truth  : {truth_path}")
        print(f"  tables : {truth['counts']['tables']} "
              f"(csv {formats['csv']}, parquet {formats['parquet']}, "
              f"json {formats['json']})")
        print(f"  rows   : {truth['counts']['rows']:,}")
        print(f"  domains: " + ", ".join(f"{k} {v}" for k, v in domains.items()))
        print(f"  keys   : natural {key_kinds['natural']}, "
              f"composite {key_kinds['composite']}, "
              f"none {key_kinds['none']}")
        print(f"  classes: {len(set(class_of_table.values()))} "
              f"from {len(all_plans)} tables")
    return truth


# ------------------------------------------------------------------ check
def _diff_truth(expected: dict, actual: dict) -> list[str]:
    diffs = [f"field {k}" for k in sorted(set(expected) | set(actual))
             if k != "files" and expected.get(k) != actual.get(k)]
    ef, af = expected.get("files", {}), actual.get("files", {})
    for name in sorted(set(ef) | set(af)):
        if ef.get(name) != af.get(name):
            diffs.append(f"file hash {name}")
    return diffs


def check(truth_path: str | Path = DEFAULT_TRUTH) -> int:
    """Regenerate into a temp folder and diff against the tracked truth."""
    truth_path = Path(truth_path)
    if not truth_path.exists():
        print(f"error: ground truth not found: {truth_path}", file=sys.stderr)
        return 2
    tracked = json.loads(truth_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="lake100-check-") as tmp:
        actual = generate(Path(tmp) / "lake100", truth_path=None, quiet=True)
    diffs = _diff_truth(tracked, actual)
    print(f"check  : {truth_path}")
    print(f"  tables : {actual['counts']['tables']}")
    print(f"  rows   : {actual['counts']['rows']:,}")
    print(f"  files  : {len(actual['files'])} hashes compared")
    if diffs:
        print(f"MISMATCH ({len(diffs)}):")
        for d in diffs[:40]:
            print(f"  - {d}")
        if len(diffs) > 40:
            print(f"  ... and {len(diffs) - 40} more")
        return 1
    print("result : OK (identical bytes and ground truth)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate (or verify) the deterministic lake100 fixture.")
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help="folder to write the 100 data files to")
    ap.add_argument("--truth", default=str(DEFAULT_TRUTH),
                    help="ground-truth JSON to write (non---check mode)")
    ap.add_argument("--check", action="store_true",
                    help="regenerate in a temp folder and diff hashes")
    ap.add_argument("--quiet", action="store_true",
                    help="no summary output")
    args = ap.parse_args(argv)

    if args.check:
        return check(args.truth)
    generate(args.out, args.truth, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
