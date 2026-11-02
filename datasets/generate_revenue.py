"""Generate the large retail-revenue dataset used by the demo and validation.

Deterministic by construction: every value comes from DuckDB's `hash()` of the
row's own primary key plus a constant salt. There is no `random()`, no clock and
no network, so running the same command twice produces the same rows on any
machine (DuckDB's `hash` is stable within a version).

The dataset carries one deliberately engineered property, because a large demo
needs an answer that can be checked rather than admired:

    West-region revenue in 2026-10 is 8.4% lower than in 2026-09, and the drop
    comes from fewer orders in segments A and B; C and D are steady.

That number is never written into the rows. The generator builds the data,
measures the drop with SQL over completed orders, and searches an October
West A/B order-volume factor until the measured drop rounds to exactly 8.4%.
Order ids encode (month, region, segment, sequence), so shrinking those two
cells leaves every other row untouched and the search is cheap.

Outputs (Parquet, plus a JSON ground truth):
    customers.parquet    ~500k
    products.parquet     ~20k
    orders.parquet       ~2,000,000 across 2025-11 .. 2026-10
    order_lines.parquet  ~5,000,000 (about 2.5 per order)
    refunds.parquet      ~100k
    _ground_truth.json   the measured numbers, for verification only
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "raw" / "revenue_huge"
WORK_DIR = ROOT / "data" / "tmp" / "revenue_duckdb"

# Salt for every derived value. Change it and the dataset changes; keep it and
# the dataset is reproducible forever.
SALT = "middle-layer/revenue/v1"

# Twelve consecutive months with mild seasonality (holiday peak, January low).
# 2026-10 is 1.02x 2026-09, so C and D - which are left alone - stay steady
# while the A/B cell is deliberately shrunk.
MONTHS: list[tuple[str, float]] = [
    ("2025-11", 1.10), ("2025-12", 1.18), ("2026-01", 0.86),
    ("2026-02", 0.84), ("2026-03", 0.95), ("2026-04", 0.97),
    ("2026-05", 1.00), ("2026-06", 1.02), ("2026-07", 1.03),
    ("2026-08", 1.00), ("2026-09", 1.00), ("2026-10", 1.02),
]
REGIONS: list[tuple[str, float]] = [
    ("West", 0.30), ("East", 0.28), ("Central", 0.23), ("South", 0.19)]
SEGMENTS: list[tuple[str, float]] = [
    ("A", 0.26), ("B", 0.24), ("C", 0.27), ("D", 0.23)]
CHANNELS: list[tuple[str, float]] = [
    ("Web", 0.42), ("Mobile", 0.33), ("Store", 0.15), ("Partner", 0.10)]

PRIOR_MONTH = "2026-09"
CURRENT_MONTH = "2026-10"
PRIOR_YM = "202609"
CURRENT_YM = "202610"
TARGET_DROP_PCT = 8.4
TARGET_RATIO = 1.0 - TARGET_DROP_PCT / 100.0
# Percentage points. Far inside the +-0.05pp window implied by rounding to one
# decimal, and reachable even though revenue moves in whole-order steps.
DROP_TOLERANCE = 0.005

BASE_CUSTOMERS = 500_000
BASE_PRODUCTS = 20_000
BASE_ORDERS = 2_000_000

FIRST_NAMES = [
    "Ada", "Grace", "Alan", "Katherine", "Linus", "Margaret", "Dennis",
    "Barbara", "Ken", "Frances", "Tim", "Radia", "Guido", "Anita", "Bjarne",
    "Shafi", "Donald", "Evelyn", "Leslie", "Jean", "Vint", "Hedy", "Chris",
    "Sophie", "Adele", "Ravi", "Mei", "Tomas", "Amara", "Jonas"]
LAST_NAMES = [
    "Lovelace", "Hopper", "Turing", "Johnson", "Torvalds", "Hamilton",
    "Ritchie", "Liskov", "Thompson", "Allen", "Berners-Lee", "Perlman",
    "Rossum", "Borg", "Stroustrup", "Goldwasser", "Knuth", "Granville",
    "Lamport", "Bartik", "Cerf", "Lamarr", "Lattner", "Wilson", "Okafor",
    "Sharma", "Chen", "Novak", "Mensah", "Eriksson"]
ADJECTIVES = [
    "Compact", "Studio", "Everyday", "Pro", "Classic", "Wireless", "Smart",
    "Portable", "Deluxe", "Essential", "Eco", "Ultra", "Mini", "Signature",
    "Rugged", "Precision"]
NOUNS = [
    "Blender", "Speaker", "Camera", "Lamp", "Chair", "Notebook", "Tracker",
    "Mixer", "Monitor", "Keyboard", "Backpack", "Kettle", "Tripod", "Charger",
    "Heater", "Sensor", "Headset", "Router", "Mug", "Clock"]
# Category list with a representative retail price. Unit prices are derived from
# these, so revenue per line stays realistic and the same for a given product.
CATEGORIES: list[tuple[str, float]] = [
    ("Audio", 89.0), ("Cameras", 249.0), ("Computers", 799.0), ("Home", 45.0),
    ("Kitchen", 39.0), ("Garden", 29.0), ("Sports", 55.0), ("Toys", 25.0),
    ("Books", 15.0), ("Beauty", 22.0), ("Fashion", 65.0), ("Outdoors", 75.0),
    ("Furniture", 189.0), ("Lighting", 35.0), ("Tools", 49.0), ("Auto", 95.0),
    ("Office", 12.0), ("Gaming", 99.0), ("Baby", 18.0), ("Health", 27.0),
    ("Pets", 32.0), ("Music", 21.0), ("Mobile", 349.0), ("Wearables", 129.0)]

TABLES = ["customers", "products", "orders", "order_lines", "refunds"]


# --------------------------------------------------------------- SQL helpers
def _q(value: str) -> str:
    """A SQL string literal, apostrophes doubled."""
    return "'" + str(value).replace("'", "''") + "'"


def _uniform(key_sql: str, salt: str) -> str:
    """A deterministic value in [0, 1) derived from one row's identity.

    `hash` of a string is stable for a given DuckDB build, which is what makes
    the whole dataset reproducible without a stateful PRNG.
    """
    return (f"((hash(CAST({key_sql} AS VARCHAR) || '|{salt}') % 1000000) "
            f"/ 1000000.0)")


def _weighted(key_sql: str, salt: str,
              options: list[tuple[str, float]]) -> str:
    """SQL CASE picking one already-quoted literal by weight.

    Thresholds are cumulative, so the last option is the ELSE branch and the
    weights need not sum to exactly one.
    """
    u = _uniform(key_sql, salt)
    whens: list[str] = []
    cumulative = 0.0
    for literal, weight in options[:-1]:
        cumulative += weight
        whens.append(f"WHEN {u} < {cumulative:.6f} THEN {literal}")
    return "CASE " + " ".join(whens) + f" ELSE {options[-1][0]} END"


def _pick(key_sql: str, salt: str, values: list[str]) -> str:
    """SQL expression picking one string from a list by hash."""
    literal = "[" + ", ".join(_q(v) for v in values) + "]"
    return (f"{literal}[(hash(CAST({key_sql} AS VARCHAR) || '|{salt}') "
            f"% {len(values)})::INT + 1]")


def _allocate(total: int, weights: list[float]) -> list[int]:
    """Split `total` into integer shares by weight (largest remainder).

    Deterministic by construction: floors first, then the leftover units go to
    the largest fractional parts, ties broken by position. The parts always sum
    to `total`, which is what keeps the promised row counts exact.
    """
    if total <= 0 or not weights:
        return [0] * len(weights)
    raw = [total * w / sum(weights) for w in weights]
    base = [int(math.floor(x)) for x in raw]
    leftover = total - sum(base)
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - base[i]), i))
    for i in order[:leftover]:
        base[i] += 1
    return base


# ------------------------------------------------------------------- cells
@dataclass(frozen=True)
class Cell:
    """One (month, region, segment) bucket of orders."""

    month_start: str          # YYYY-MM-01
    ym: str                   # YYYYMM, embedded in the order id
    region: str
    segment: str
    n: int


def _base_cells(scale: float) -> list[Cell]:
    """Order counts per cell before the October West A/B correction."""
    total = max(len(MONTHS) * len(REGIONS) * len(SEGMENTS) * 2,
                int(round(BASE_ORDERS * scale)))
    cells: list[Cell] = []
    month_counts = _allocate(total, [w for _, w in MONTHS])
    for (month, _), month_n in zip(MONTHS, month_counts):
        region_counts = _allocate(month_n, [w for _, w in REGIONS])
        for (region, _), region_n in zip(REGIONS, region_counts):
            segment_counts = _allocate(region_n, [w for _, w in SEGMENTS])
            for (segment, _), segment_n in zip(SEGMENTS, segment_counts):
                cells.append(Cell(f"{month}-01", month.replace("-", ""),
                                  region, segment, segment_n))
    return cells


def _cells(scale: float, oct_west_ab_factor: float) -> list[Cell]:
    """The full cell table, with October West A/B volume scaled by `factor`.

    The removed volume is moved to regions outside West, so the grand total
    stays exactly what was promised while West September and every West segment
    other than October A/B are untouched. That keeps the headline total honest
    and makes the tuning search one-dimensional.
    """
    base = _base_cells(scale)
    target_total = sum(c.n for c in base)

    adjusted: list[Cell] = []
    for cell in base:
        n = cell.n
        if (cell.ym == CURRENT_YM and cell.region == "West"
                and cell.segment in ("A", "B")):
            n = max(1, int(round(cell.n * oct_west_ab_factor)))
        adjusted.append(replace(cell, n=n))

    deficit = target_total - sum(c.n for c in adjusted)
    if deficit > 0:
        weights = [c.n if c.region != "West" else 0.0 for c in adjusted]
        if sum(weights) <= 0:                      # unreachable in practice
            raise RuntimeError("no non-West cell can absorb the volume shift")
        for i, extra in enumerate(_allocate(deficit, weights)):
            adjusted[i] = replace(adjusted[i], n=adjusted[i].n + extra)
    return adjusted


# ------------------------------------------------------------- dimensions
def _build_customers(con: duckdb.DuckDBPyConnection, count: int) -> None:
    region_choice = _weighted("customer_id", "region",
                              [(f"'{r}'", w) for r, w in REGIONS])
    segment_choice = _weighted("customer_id", "segment",
                               [(f"'{s}'", w) for s, w in SEGMENTS])
    con.execute(f"""
        CREATE OR REPLACE TABLE customers AS
        WITH base AS (
            SELECT i,
                   'C' || lpad(CAST(i AS VARCHAR), 6, '0') AS customer_id
            FROM range(1, {int(count)} + 1) t(i)
        )
        SELECT customer_id,
               {_pick('customer_id', 'first', FIRST_NAMES)} || ' ' ||
               {_pick('customer_id', 'last', LAST_NAMES)} AS name,
               {region_choice} AS region,
               {segment_choice} AS segment,
               DATE '2022-01-01' +
                   CAST(hash(customer_id || '|signup') % 1400 AS INT)
                   AS signup_date
        FROM base""")


def _build_products(con: duckdb.DuckDBPyConnection, count: int) -> None:
    con.execute(f"""
        CREATE OR REPLACE TABLE category_price(category VARCHAR, base_price DOUBLE)
    """)
    con.executemany("INSERT INTO category_price VALUES (?, ?)", CATEGORIES)

    categories = [name for name, _ in CATEGORIES]
    con.execute(f"""
        CREATE OR REPLACE TABLE products AS
        WITH base AS (
            SELECT i,
                   'P' || lpad(CAST(i AS VARCHAR), 6, '0') AS product_id
            FROM range(1, {int(count)} + 1) t(i)
        )
        SELECT product_id,
               {_pick('product_id', 'adj', ADJECTIVES)} || ' ' ||
               {_pick('product_id', 'noun', NOUNS)} AS name,
               {_pick('product_id', 'category', categories)} AS category
        FROM base""")


# ---------------------------------------------------------------- orders
def _build_orders(con: duckdb.DuckDBPyConnection,
                  cells: list[Cell]) -> None:
    """Create the orders table for exactly these cells.

    `range(1, n+1)` next to the cell is a lateral join: DuckDB expands each
    bucket into its own rows. The window in `cust` assigns every (region,
    segment) group a dense customer index, so an order can pick a customer of
    its own region and segment with one hash and one hash join.
    """
    if not cells:
        raise ValueError("no order cells to generate")
    values = ",\n            ".join(
        f"(DATE '{c.month_start}', '{c.ym}', '{c.region}', '{c.segment}', "
        f"{c.n})" for c in cells)
    status_choice = _weighted("s.oid", "status", [
        ("'completed'", 0.92), ("'refunded'", 0.97), ("'cancelled'", 1.0)])
    channel_choice = _weighted("s.oid", "channel",
                               [(f"'{ch}'", w) for ch, w in CHANNELS])
    con.execute(f"""
        CREATE OR REPLACE TABLE orders AS
        WITH cells(month_start, ym, region, segment, n) AS (
            VALUES
            {values}
        ),
        cust AS (
            SELECT customer_id, region, segment,
                   row_number() OVER (PARTITION BY region, segment
                                      ORDER BY customer_id) - 1 AS ci,
                   count(*) OVER (PARTITION BY region, segment) AS cn
            FROM customers
        ),
        shaped AS (
            SELECT c.*, t.seq,
                   'O' || c.ym || left(c.region, 1) || c.segment ||
                       lpad(CAST(t.seq AS VARCHAR), 6, '0') AS oid
            FROM cells c, range(1, c.n + 1) t(seq)
        )
        SELECT s.oid AS order_id,
               cu.customer_id,
               s.region,
               s.segment,
               s.month_start +
                   CAST(hash(s.oid || '|day') %
                        day(s.month_start + INTERVAL 1 MONTH
                            - INTERVAL 1 DAY) AS INT) AS order_date,
               {status_choice} AS status,
               {channel_choice} AS channel
        FROM shaped s
        JOIN cust cu
          ON cu.region = s.region AND cu.segment = s.segment
         AND cu.ci = (hash(s.oid || '|customer') % cu.cn)::INT""")


def _build_lines(con: duckdb.DuckDBPyConnection, products_n: int) -> None:
    """Explode every order into 2-3 lines (mean 2.5) with coherent money.

    Every line value depends only on (order_id, line_no), never on the row's
    position in the result, so the lines of an order are identical whether the
    order was built alone during tuning or as part of the full dataset.
    """
    quantity_choice = _weighted("wp.order_id || '|qty' || CAST(wp.line_no AS "
                                "VARCHAR)", "qty",
                                [("1", 0.35), ("2", 0.30), ("3", 0.20),
                                 ("4", 0.15)])
    discount_choice = _weighted(
        "wp.order_id || '|disc' || CAST(wp.line_no AS VARCHAR)", "disc",
        [("0.00", 0.42), ("0.05", 0.62), ("0.10", 0.82), ("0.15", 0.92),
         ("0.20", 0.97), ("0.25", 1.00)])
    con.execute(f"""
        CREATE OR REPLACE TABLE order_lines AS
        WITH orders_n AS (
            SELECT order_id,
                   2 + CAST((hash(order_id || '|nlines') % 1000) < 500 AS INT)
                       AS nlines
            FROM orders
        ),
        lines AS (
            SELECT o.order_id, t.line_no
            FROM orders_n o, range(1, o.nlines + 1) t(line_no)
        ),
        with_product AS (
            SELECT l.order_id, l.line_no,
                   'P' || lpad(CAST(
                       (hash(l.order_id || '|' || CAST(l.line_no AS VARCHAR)
                             || '|product') % {products_n})::INT + 1
                       AS VARCHAR), 6, '0') AS product_id
            FROM lines l
        ),
        priced AS (
            SELECT wp.order_id, wp.line_no, wp.product_id,
                   {quantity_choice} AS quantity,
                   round(cp.base_price *
                         (0.72 + 0.90 * {_uniform("wp.product_id", "price")}),
                         2) AS unit_price,
                   {discount_choice} AS discount_pct
            FROM with_product wp
            JOIN products p ON p.product_id = wp.product_id
            JOIN category_price cp ON cp.category = p.category
        )
        SELECT order_id, line_no, product_id, quantity, unit_price,
               discount_pct,
               round(quantity * unit_price * (1 - discount_pct), 2)
                   AS line_revenue
        FROM priced""")


def _build_refunds(con: duckdb.DuckDBPyConnection) -> None:
    """One refund for every refunded order: about 5% of them (~100k)."""
    con.execute(f"""
        CREATE OR REPLACE TABLE refunds AS
        WITH refunded AS (
            SELECT o.order_id, o.order_date,
                   sum(l.line_revenue) AS order_revenue
            FROM orders o
            JOIN order_lines l ON l.order_id = o.order_id
            WHERE o.status = 'refunded'
            GROUP BY o.order_id, o.order_date
        ),
        numbered AS (
            SELECT *, row_number() OVER (ORDER BY order_id) AS rn
            FROM refunded
        )
        SELECT 'R' || lpad(CAST(rn AS VARCHAR), 6, '0') AS refund_id,
               order_id,
               CAST(order_date +
                    CAST(1 + hash(order_id || '|refund_day') % 45 AS INT)
                    AS DATE) AS refund_date,
               round(order_revenue *
                     (0.30 + 0.70 * {_uniform('order_id', 'refund_amount')}), 2)
                   AS amount
        FROM numbered""")


# ------------------------------------------------------------- measurement
def _measure_west(con: duckdb.DuckDBPyConnection) -> dict:
    """Revenue and order counts per West segment for the two months.

    Completed orders only, summed from `line_revenue`: that is the definition
    the demo's headline number uses, so it is the one the generator tunes to.
    """
    rows = con.execute(f"""
        SELECT strftime(o.order_date, '%Y-%m') AS ym, o.segment,
               sum(l.line_revenue) AS revenue,
               count(DISTINCT o.order_id) AS orders
        FROM orders o
        JOIN order_lines l ON l.order_id = o.order_id
        WHERE o.region = 'West' AND o.status = 'completed'
          AND o.order_date >= DATE '{PRIOR_MONTH}-01'
          AND o.order_date <  DATE '{CURRENT_MONTH}-01' + INTERVAL 1 MONTH
        GROUP BY 1, 2""").fetchall()
    out: dict = {PRIOR_MONTH: {}, CURRENT_MONTH: {}}
    for ym, segment, revenue, orders in rows:
        out[ym][segment] = {"revenue": float(revenue or 0.0),
                            "orders": int(orders or 0)}
    for ym in out:
        for segment, _ in SEGMENTS:
            out[ym].setdefault(segment, {"revenue": 0.0, "orders": 0})
    return out


def _west_totals(measure: dict) -> tuple[float, float]:
    prior = sum(v["revenue"] for v in measure[PRIOR_MONTH].values())
    current = sum(v["revenue"] for v in measure[CURRENT_MONTH].values())
    return prior, current


def _drop_pct(prior: float, current: float) -> float:
    return 100.0 * (1.0 - current / prior) if prior else 0.0


def _tune_october_volume(con: duckdb.DuckDBPyConnection,
                         scale: float, products_n: int) -> dict:
    """Find the October West A/B order-volume factor that yields an 8.4% drop.

    Only West September and West October cells are generated here, so each
    probe costs a few hundred thousand rows instead of the full dataset. The
    correction is proportional and needs two or three passes, because revenue
    is very nearly linear in order count while order counts are integers.
    """
    factor = 0.82
    best = (factor, float("inf"))
    trace: list[dict] = []
    # Tuning only needs the ratio, not 2M rows. A 5% sample gives the same
    # monthly ratio to well inside the settlement tolerance while keeping the
    # search cheap; the chosen factor is then applied to the full dataset once.
    tune_scale = min(max(scale * 0.05, 0.01), 0.05)

    for attempt in range(1, 13):
        cells = _cells(tune_scale, factor)
        west_cells = [c for c in cells if c.region == "West"
                      and c.ym in (PRIOR_YM, CURRENT_YM)]
        _build_orders(con, west_cells)
        _build_lines(con, products_n)
        measure = _measure_west(con)
        prior, current = _west_totals(measure)
        if prior <= 0:
            raise RuntimeError("September West revenue is zero; cannot tune")
        drop = _drop_pct(prior, current)
        trace.append({"attempt": attempt, "factor": round(factor, 6),
                      "drop_pct": round(drop, 6)})
        if abs(drop - TARGET_DROP_PCT) < best[1]:
            best = (factor, abs(drop - TARGET_DROP_PCT))
        if abs(drop - TARGET_DROP_PCT) <= DROP_TOLERANCE:
            return {"factor": factor, "attempts": attempt,
                    "drop_pct": round(drop, 6), "trace": trace}

        # Revenue is linear in order count: solve for the A/B revenue that makes
        # the current month land on target, then rescale the count factor.
        target_current = prior * TARGET_RATIO
        ab_current = measure[CURRENT_MONTH]["A"]["revenue"] + \
            measure[CURRENT_MONTH]["B"]["revenue"]
        cd_current = measure[CURRENT_MONTH]["C"]["revenue"] + \
            measure[CURRENT_MONTH]["D"]["revenue"]
        needed_ab = target_current - cd_current
        if ab_current <= 0 or needed_ab <= 0:
            break
        factor = max(0.05, min(1.20, factor * needed_ab / ab_current))

    cells = _cells(tune_scale, best[0])
    west_cells = [c for c in cells if c.region == "West"
                  and c.ym in (PRIOR_YM, CURRENT_YM)]
    _build_orders(con, west_cells)
    _build_lines(con, products_n)
    measure = _measure_west(con)
    prior, current = _west_totals(measure)
    return {"factor": best[0], "attempts": len(trace),
            "drop_pct": round(_drop_pct(prior, current), 6),
            "trace": trace}


def _settle_to_target(con: duckdb.DuckDBPyConnection,
                      measure: dict) -> dict | None:
    """Last-resort exact correction with one small settlement line.

    Integer order counts can leave the measured drop a few hundred dollars off
    the target even after tuning. If that ever happens, one negative-quantity
    line (a return/price-protection credit, which is a normal retail row) on a
    settlement order in October West segment A closes the gap. It is small by
    construction and is never used unless tuning could not get within
    tolerance - the expected path never reaches this function.
    """
    prior, current = _west_totals(measure)
    residual = current - prior * TARGET_RATIO
    if abs(residual) < 0.01:
        return None
    if abs(residual) > 0.005 * prior:              # >0.5% of a month: not small
        raise RuntimeError(
            f"tuning missed the target by {residual:,.2f}; that is too large "
            f"for an adjustment line")

    customer = con.execute("""
        SELECT customer_id FROM customers
        WHERE region = 'West' AND segment = 'A'
        ORDER BY customer_id LIMIT 1""").fetchone()[0]
    next_seq = con.execute("""
        SELECT count(*) FROM orders
        WHERE region = 'West' AND segment = 'A'
          AND strftime(order_date, '%Y-%m') = ?""", [CURRENT_MONTH]).fetchone()[0]
    settlement_id = (f"O{CURRENT_YM}WA"
                     + str(next_seq + 1).zfill(6) + "S")
    quantity = -1 if residual > 0 else 1
    amount = round(abs(residual), 2)
    con.execute("""
        INSERT INTO orders VALUES (?, ?, 'West', 'A', DATE '2026-10-15',
                                   'completed', 'Partner')""",
                [settlement_id, customer])
    con.execute("""
        INSERT INTO order_lines VALUES (?, 1, 'P000001', ?, ?, 0.0, ?)""",
                [settlement_id, quantity, amount, quantity * amount])
    return {"order_id": settlement_id, "line_revenue": quantity * amount}


# -------------------------------------------------------------- reporting
def _row_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    return {table: int(con.execute(
        f"SELECT count(*) FROM {table}").fetchone()[0]) for table in TABLES}


def _west_monthly(con: duckdb.DuckDBPyConnection) -> dict[str, float]:
    rows = con.execute("""
        SELECT strftime(o.order_date, '%Y-%m') AS ym,
               sum(l.line_revenue) AS revenue
        FROM orders o
        JOIN order_lines l ON l.order_id = o.order_id
        WHERE o.region = 'West' AND o.status = 'completed'
        GROUP BY 1 ORDER BY 1""").fetchall()
    return {ym: round(float(revenue or 0.0), 2) for ym, revenue in rows}


def _ground_truth(con: duckdb.DuckDBPyConnection, scale: float, tune: dict,
                  settlement: dict | None) -> dict:
    """The numbers a checker can recompute from the shipped Parquet files."""
    measure = _measure_west(con)
    prior, current = _west_totals(measure)
    drop = _drop_pct(prior, current)

    segments: dict[str, dict] = {}
    for segment, _ in SEGMENTS:
        prior_rev = measure[PRIOR_MONTH][segment]["revenue"]
        current_rev = measure[CURRENT_MONTH][segment]["revenue"]
        prior_orders = measure[PRIOR_MONTH][segment]["orders"]
        current_orders = measure[CURRENT_MONTH][segment]["orders"]
        segments[segment] = {
            "prior_revenue": round(prior_rev, 2),
            "current_revenue": round(current_rev, 2),
            "delta_revenue": round(current_rev - prior_rev, 2),
            "contribution_to_west_drop_pct": round(
                100.0 * (prior_rev - current_rev) / prior, 4),
            "prior_orders": prior_orders,
            "current_orders": current_orders,
            "order_change_pct": round(
                100.0 * (current_orders - prior_orders) / prior_orders, 2)
                if prior_orders else 0.0,
        }

    west_orders = con.execute("""
        SELECT strftime(order_date, '%Y-%m') AS ym,
               count(*) AS orders,
               count(*) FILTER (WHERE status = 'completed') AS completed
        FROM orders WHERE region = 'West'
          AND strftime(order_date, '%Y-%m') IN (?, ?)
        GROUP BY 1 ORDER BY 1""", [PRIOR_MONTH, CURRENT_MONTH]).fetchall()
    west_order_counts = {
        ym: {"all": int(all_n), "completed": int(completed)}
        for ym, all_n, completed in west_orders}

    return {
        "dataset": "revenue_huge",
        "scale": scale,
        "salt": SALT,
        "definition": ("West-region revenue per month = sum(order_lines."
                       "line_revenue) over orders with region='West' and "
                       "status='completed'."),
        "prior_month": PRIOR_MONTH,
        "current_month": CURRENT_MONTH,
        "target_drop_pct": TARGET_DROP_PCT,
        "west_revenue_prior": round(prior, 2),
        "west_revenue_current": round(current, 2),
        "drop_pct": round(drop, 1),
        "drop_pct_exact": round(drop, 6),
        "west_order_counts": west_order_counts,
        "segments": segments,
        "october_west_ab_volume_factor": round(tune["factor"], 6),
        "tuning": {"attempts": tune["attempts"], "trace": tune["trace"],
                   "adjustment_line": settlement},
        "west_monthly_revenue": _west_monthly(con),
        "row_counts": _row_counts(con),
    }


def _write_parquet(con: duckdb.DuckDBPyConnection, out: Path) -> dict[str, int]:
    sizes: dict[str, int] = {}
    for table in TABLES:
        path = (out / f"{table}.parquet").as_posix()
        con.execute(f"""
            COPY (SELECT * FROM {table}) TO '{path}'
            (FORMAT PARQUET, COMPRESSION ZSTD)""")
        sizes[table] = (out / f"{table}.parquet").stat().st_size
    return sizes


# -------------------------------------------------------------------- main
def _configure(con: duckdb.DuckDBPyConnection, memory_limit: str) -> None:
    """Keep DuckDB inside a sane box on a small machine.

    The build machine can have less free memory than the dataset needs; letting
    DuckDB spill to a temp directory turns an out-of-memory failure into a
    slower run, which is the right trade for a one-off generation.
    """
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    con.execute("SET enable_progress_bar = false")
    con.execute(f"SET memory_limit = '{memory_limit}'")
    con.execute(f"SET temp_directory = '{WORK_DIR.as_posix()}'")
    con.execute("SET preserve_insertion_order = true")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the deterministic revenue dataset.")
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help="output folder (default: data/raw/revenue_huge)")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="row-count multiplier (default: 1.0)")
    parser.add_argument("--memory-limit", default="3GB",
                        help="DuckDB memory limit; spills to disk above it")
    args = parser.parse_args(argv)

    if args.scale <= 0:
        parser.error("--scale must be positive")

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    customers_n = max(16, int(round(BASE_CUSTOMERS * args.scale)))
    products_n = max(len(CATEGORIES), int(round(BASE_PRODUCTS * args.scale)))

    started = time.monotonic()
    con = duckdb.connect(":memory:")
    try:
        _configure(con, args.memory_limit)

        print(f"generating {args.scale:g}x revenue dataset into {out}")
        _build_customers(con, customers_n)
        _build_products(con, products_n)
        print(f"  customers {customers_n:,}   products {products_n:,}")

        tune = _tune_october_volume(con, args.scale, products_n)
        print(f"  tuned October West A/B factor {tune['factor']:.4f} in "
              f"{tune['attempts']} SQL pass(es); measured drop "
              f"{tune['drop_pct']:.4f}%")

        cells = _cells(args.scale, tune["factor"])
        _build_orders(con, cells)
        orders_n = con.execute("SELECT count(*) FROM orders").fetchone()[0]
        _build_lines(con, products_n)
        lines_n = con.execute("SELECT count(*) FROM order_lines").fetchone()[0]
        print(f"  orders {orders_n:,}   order lines {lines_n:,} "
              f"({lines_n / orders_n:.2f} per order)")
        _build_refunds(con)
        refunds_n = con.execute("SELECT count(*) FROM refunds").fetchone()[0]
        completed_share = con.execute(
            "SELECT 100.0 * count(*) FILTER (WHERE status = 'completed')"
            " / count(*) FROM orders").fetchone()[0]
        print(f"  refunds {refunds_n:,}   completed orders {completed_share:.2f}%")

        # The full dataset is measured again; only if tuning could not land
        # inside tolerance does the small settlement line get added.
        measure = _measure_west(con)
        prior, current = _west_totals(measure)
        drop = _drop_pct(prior, current)
        settlement = None
        if abs(drop - TARGET_DROP_PCT) > DROP_TOLERANCE:
            settlement = _settle_to_target(con, measure)
            if settlement:
                print(f"  adjustment line {settlement['order_id']}: "
                      f"line_revenue {settlement['line_revenue']:,.2f}")

        truth = _ground_truth(con, args.scale, tune, settlement)
        sizes = _write_parquet(con, out)
    finally:
        con.close()

    truth["parquet_bytes"] = sizes
    truth_path = out / "_ground_truth.json"
    truth_path.write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")

    elapsed = time.monotonic() - started
    rows = truth["row_counts"]
    print()
    print(f"wrote {out} in {elapsed:,.1f}s")
    for table in TABLES:
        print(f"  {table + '.parquet':<22}{rows[table]:>12,} rows"
              f"   {sizes[table] / 1e6:8.1f} MB")
    print(f"  {'_ground_truth.json':<22}{'':>12}      "
          f"{truth_path.stat().st_size / 1e3:8.1f} KB")
    print()
    print(f"West revenue {PRIOR_MONTH} (completed)  "
          f"{truth['west_revenue_prior']:>18,.2f}")
    print(f"West revenue {CURRENT_MONTH} (completed)  "
          f"{truth['west_revenue_current']:>18,.2f}")
    print(f"drop {truth['drop_pct_exact']:.4f}%  -> rounds to "
          f"{truth['drop_pct']:.1f}%  (target {TARGET_DROP_PCT}%)")
    for segment, _ in SEGMENTS:
        s = truth["segments"][segment]
        print(f"  segment {segment}: {s['prior_revenue']:>16,.2f} -> "
              f"{s['current_revenue']:>16,.2f}   orders "
              f"{s['prior_orders']:>7,} -> {s['current_orders']:>7,} "
              f"({s['order_change_pct']:+.1f}%)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:                    # a clean message, no trace
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
