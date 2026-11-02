"""Fast, deterministic revenue dataset with an engineered West October decline.

The first generator tuned by rebuilding the full dataset; on a 2M-order build
that was too slow. This version generates once per candidate volume factor,
uses a single SQL pass for each table, and settles the last few dollars with a
small, plausible credit line. Row counts at the default scale:

    customers    500,000
    products      20,000
    orders     2,000,000   (12 months, Nov 2025 .. Oct 2026)
    order_lines ~5,000,000
    refunds      ~160,000

West revenue in 2026-10 is 8.4% below 2026-09 because October order volume in
segments A and B is reduced; C and D keep their normal volume. The exact
headline is reached by tuning that one volume factor, then verifying with SQL.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import duckdb

REGIONS = [("West", 0.30), ("East", 0.27), ("Central", 0.23), ("South", 0.20)]
SEGMENTS = [("A", 0.25), ("B", 0.25), ("C", 0.25), ("D", 0.25)]
CATEGORIES = [("Hardware", 120.0), ("Software", 90.0), ("Services", 240.0),
              ("Accessories", 35.0), ("Networking", 180.0), ("Storage", 150.0)]
CHANNELS = [("web", 0.45), ("partner", 0.25), ("field", 0.20), ("marketplace", 0.10)]
FIRST = ["Ada", "Grace", "Alan", "Katherine", "Linus", "Margaret", "Dennis", "Barbara"]
LAST = ["Lovelace", "Hopper", "Turing", "Johnson", "Torvalds", "Hamilton", "Ritchie", "Liskov"]
PRIOR = "2026-09-01"
CURRENT = "2026-10-01"
CURRENT_END = "2026-11-01"
TARGET_DROP = 8.4
TARGET_RATIO = 1.0 - TARGET_DROP / 100.0


def _weighted(seed: str, choices: list[tuple[str, float]]) -> str:
    """A SQL CASE expression for a deterministic weighted pick."""
    parts = []
    cumulative = 0.0
    for label, weight in choices[:-1]:
        cumulative += weight
        parts.append(f"WHEN (hash({seed}) % 10000) < {int(round(cumulative * 10000))} "
                     f"THEN '{label}'")
    return "CASE " + " ".join(parts) + f" ELSE '{choices[-1][0]}' END"


def _pick(seed: str, values: list[str]) -> str:
    return f"{values[0]}" if len(values) == 1 else (
        f"[{', '.join(repr(v) for v in values)}]"
        f"[CAST(hash({seed}) % {len(values)} AS INT)]")


def _generate(con: duckdb.DuckDBPyConnection, orders_n: int,
              reduce_pct: int) -> dict:
    customers_n = max(1000, orders_n // 4)
    products_n = 20000
    con.execute("DROP TABLE IF EXISTS customers")
    con.execute("DROP TABLE IF EXISTS products")
    con.execute("DROP TABLE IF EXISTS orders")
    con.execute("DROP TABLE IF EXISTS order_lines")
    con.execute("DROP TABLE IF EXISTS refunds")

    con.execute(f"""
        CREATE TABLE customers AS
        WITH base AS (
            SELECT i,
                   'C' || lpad(CAST(i AS VARCHAR), 7, '0') AS customer_id
            FROM range(1, {customers_n} + 1) t(i)
        )
        SELECT customer_id,
               {_pick('customer_id', FIRST)} || ' ' ||
                   {_pick('customer_id', LAST)} AS name,
               {_weighted("customer_id || '|region'", REGIONS)} AS region,
               {_weighted("customer_id || '|segment'", SEGMENTS)} AS segment,
               DATE '2022-01-01' + CAST(hash(customer_id || '|signup') % 1400 AS INT)
                   AS signup_date
        FROM base
    """)

    con.execute(f"""
        CREATE TABLE products AS
        WITH base AS (
            SELECT i, 'P' || lpad(CAST(i AS VARCHAR), 6, '0') AS product_id
            FROM range(1, {products_n} + 1) t(i)
        ), cats AS (
            SELECT * FROM (VALUES {', '.join(f"('{c}', {p})" for c, p in CATEGORIES)})
                AS t(category, base_price)
        )
        SELECT b.product_id,
               {_pick('b.product_id', ['Alpha', 'Beta', 'Gamma', 'Delta', 'Omega'])} || ' ' ||
                   {_pick('b.product_id', ['Widget', 'Suite', 'Module', 'Kit', 'Unit'])} AS name,
               c.category, c.base_price
        FROM base b
        JOIN cats c ON c.category = {_weighted('b.product_id', CATEGORIES)}
    """)

    # Orders: one hash picks the month, one the customer. The October West A/B
    # reduction is a deterministic keep-rate, so the only changed leg is order
    # volume - exactly the business story.
    month_expr = "CAST(hash(i || '|month') % 12 AS INT)"
    con.execute(f"""
        CREATE TABLE orders AS
        WITH base AS (
            SELECT i,
                   'O' || lpad(CAST(i AS VARCHAR), 8, '0') AS order_id,
                   {month_expr} AS month_idx,
                   'C' || lpad(CAST(1 + hash(i || '|customer') % {customers_n} AS VARCHAR),
                               7, '0') AS customer_id
            FROM range(1, {orders_n} + 1) t(i)
        )
        SELECT b.order_id, b.customer_id,
               c.region, c.segment,
               CAST(DATE '2025-11-01'
                    + CAST(b.month_idx AS INT) * INTERVAL 1 MONTH
                    + CAST(hash(b.order_id || '|day') % 28 AS INT) * INTERVAL 1 DAY
                    AS DATE) AS order_date,
               CASE WHEN hash(b.order_id || '|status') % 100 < 92 THEN 'completed'
                    WHEN hash(b.order_id || '|status') % 100 < 97 THEN 'refunded'
                    ELSE 'cancelled' END AS status,
               {_weighted('b.order_id', CHANNELS)} AS channel
        FROM base b
        JOIN customers c ON c.customer_id = b.customer_id
        WHERE NOT (
            b.month_idx = 11 AND c.region = 'West'
            AND c.segment IN ('A', 'B')
            AND hash(b.order_id || '|keep') % 100 < {reduce_pct}
        )
    """)

    con.execute("""
        CREATE TABLE order_lines AS
        WITH with_n AS (
            SELECT order_id,
                   2 + CAST((hash(order_id || '|nlines') % 1000) < 500 AS INT) AS nlines
            FROM orders
        ), lines AS (
            SELECT o.order_id, t.line_no
            FROM with_n o, range(1, o.nlines + 1) t(line_no)
        )
        SELECT l.order_id, l.line_no,
               'P' || lpad(CAST(1 + hash(l.order_id || '|' ||
                    CAST(l.line_no AS VARCHAR) || '|product') % 20000 AS VARCHAR),
                    6, '0') AS product_id,
               1 + CAST(hash(l.order_id || '|' || CAST(l.line_no AS VARCHAR) || '|qty') % 4 AS INT)
                   AS quantity,
               round(p.base_price *
                     (0.72 + 0.90 * (hash(l.order_id || '|' || CAST(l.line_no AS VARCHAR)) % 1000) / 1000.0),
                     2) AS unit_price,
               CASE (hash(l.order_id || '|' || CAST(l.line_no AS VARCHAR) || '|disc') % 100)
                    WHEN 0 THEN 0.00 WHEN 1 THEN 0.00 WHEN 2 THEN 0.00
                    WHEN 3 THEN 0.05 WHEN 4 THEN 0.05 WHEN 5 THEN 0.10
                    WHEN 6 THEN 0.10 WHEN 7 THEN 0.15 WHEN 8 THEN 0.20
                    ELSE 0.00 END AS discount_pct
        FROM lines l
        JOIN products p ON p.product_id =
            'P' || lpad(CAST(1 + hash(l.order_id || '|' ||
                CAST(l.line_no AS VARCHAR) || '|product') % 20000 AS VARCHAR), 6, '0')
    """)
    con.execute("""
        ALTER TABLE order_lines ADD COLUMN line_revenue DOUBLE
    """)
    con.execute("""
        UPDATE order_lines SET line_revenue =
            round(quantity * unit_price * (1 - discount_pct), 2)
    """)

    con.execute("""
        CREATE TABLE refunds AS
        WITH refunded AS (
            SELECT o.order_id, o.order_date, sum(l.line_revenue) AS amount
            FROM orders o JOIN order_lines l USING (order_id)
            WHERE o.status = 'refunded'
            GROUP BY o.order_id, o.order_date
        ), numbered AS (
            SELECT *, row_number() OVER (ORDER BY order_id) AS rn FROM refunded
        )
        SELECT 'R' || lpad(CAST(rn AS VARCHAR), 7, '0') AS refund_id,
               order_id,
               CAST(order_date + CAST(1 + hash(order_id || '|refund_day') % 30 AS INT)
                    AS DATE) AS refund_date,
               round(amount * (0.25 + 0.75 * (hash(order_id || '|refund') % 1000) / 1000.0), 2)
                   AS amount
        FROM numbered
    """)
    return {"customers": customers_n, "products": products_n,
            "orders": con.execute("SELECT count(*) FROM orders").fetchone()[0],
            "order_lines": con.execute("SELECT count(*) FROM order_lines").fetchone()[0],
            "refunds": con.execute("SELECT count(*) FROM refunds").fetchone()[0]}


def _measure(con):
    row = con.execute(f"""
        SELECT
          coalesce(sum(CASE WHEN o.order_date >= DATE '{PRIOR}'
                             AND o.order_date < DATE '{CURRENT}'
                        THEN l.line_revenue END), 0) AS prior,
          coalesce(sum(CASE WHEN o.order_date >= DATE '{CURRENT}'
                             AND o.order_date < DATE '{CURRENT_END}'
                        THEN l.line_revenue END), 0) AS current
        FROM orders o JOIN order_lines l USING (order_id)
        WHERE o.region = 'West' AND o.status = 'completed'
    """).fetchone()
    return float(row[0]), float(row[1])


def _segments(con):
    rows = con.execute(f"""
        SELECT o.segment,
               coalesce(sum(CASE WHEN o.order_date >= DATE '{PRIOR}'
                                  AND o.order_date < DATE '{CURRENT}'
                             THEN l.line_revenue END), 0) AS prior,
               coalesce(sum(CASE WHEN o.order_date >= DATE '{CURRENT}'
                                  AND o.order_date < DATE '{CURRENT_END}'
                             THEN l.line_revenue END), 0) AS current,
               count(DISTINCT CASE WHEN o.order_date >= DATE '{PRIOR}'
                                    AND o.order_date < DATE '{CURRENT}'
                               THEN o.order_id END) AS prior_orders,
               count(DISTINCT CASE WHEN o.order_date >= DATE '{CURRENT}'
                                    AND o.order_date < DATE '{CURRENT_END}'
                               THEN o.order_id END) AS current_orders
        FROM orders o JOIN order_lines l USING (order_id)
        WHERE o.region = 'West' AND o.status = 'completed'
        GROUP BY o.segment ORDER BY o.segment
    """).fetchall()
    return {r[0]: {"prior_revenue": float(r[1]), "current_revenue": float(r[2]),
                  "prior_orders": int(r[3]), "current_orders": int(r[4])}
            for r in rows}


def _settle(con, prior: float, current: float) -> dict | None:
    """Close the last few dollars with a defensible credit line in West A."""
    target = prior * TARGET_RATIO
    residual = current - target
    if abs(residual) < 0.01:
        return None
    if abs(residual) > 0.005 * prior:
        return None
    customer = con.execute("""
        SELECT c.customer_id FROM customers c
        WHERE c.region='West' AND c.segment='A' LIMIT 1
    """).fetchone()
    if not customer:
        return None
    order_id = "O202610WAADJ0001"
    con.execute("""
        INSERT INTO orders(order_id, customer_id, region, segment, order_date,
                           status, channel)
        VALUES (?, ?, 'West', 'A', DATE '2026-10-15', 'completed', 'web')
    """, [order_id, customer[0]])
    con.execute("""
        INSERT INTO order_lines(order_id, line_no, product_id, quantity,
                                unit_price, discount_pct, line_revenue)
        VALUES (?, 1, 'P000001', 1, ?, 0, ?)
    """, [order_id, round(-residual, 2), round(-residual, 2)])
    return {"order_id": order_id, "line_revenue": round(-residual, 2)}


def _write(con, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    sizes = {}
    for table in ("customers", "products", "orders", "order_lines", "refunds"):
        target = (out / f"{table}.parquet").as_posix()
        con.execute(f"COPY {table} TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        sizes[table] = (out / f"{table}.parquet").stat().st_size
    return sizes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/raw/revenue_huge")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--orders", type=int, default=2_000_000)
    parser.add_argument("--memory-limit", default="6GB")
    args = parser.parse_args(argv)

    orders_n = max(5000, int(args.orders * args.scale))
    out = Path(args.out)
    started = time.monotonic()
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{args.memory_limit}'")
    con.execute("SET threads=4")

    # Tune only the October West A/B keep-rate. One full generation per pass;
    # the search converges in two or three passes because the drop is linear in
    # A/B order volume.
    reduce_pct = 16
    best = None
    for attempt in range(1, 6):
        counts = _generate(con, orders_n, reduce_pct)
        prior, current = _measure(con)
        drop = 100.0 * (1 - current / prior)
        print(f"  pass {attempt}: reduce {reduce_pct}% -> drop {drop:.4f}% "
              f"({counts['orders']:,} orders, {counts['order_lines']:,} lines)")
        if best is None or abs(drop - TARGET_DROP) < abs(best[1] - TARGET_DROP):
            best = (reduce_pct, drop, dict(counts))
        if abs(drop - TARGET_DROP) <= 0.08:
            break
        # The drop is essentially proportional to the A/B volume removed, so
        # scale the keep-rate directly; add a floor when the signal is tiny.
        if drop <= 0.5:
            reduce_pct = min(40, reduce_pct + 4)
        else:
            reduce_pct = max(0, min(40, int(round(
                reduce_pct * TARGET_DROP / drop))))
    reduce_pct = best[0]
    counts = _generate(con, orders_n, reduce_pct)
    prior, current = _measure(con)
    settlement = _settle(con, prior, current)
    if settlement:
        current = _measure(con)[1]
    drop = 100.0 * (1 - current / prior)
    segments = _segments(con)
    # The current month must be materially driven by A/B volume, not by a
    # settlement line. Assert the shape rather than only the headline.
    def _orders(segment):
        row = segments.get(segment, {})
        return int(row.get("current_orders", 0) - row.get("prior_orders", 0))

    ab_order_change = _orders("A") + _orders("B")
    cd_order_change = _orders("C") + _orders("D")
    if ab_order_change >= 0:
        raise RuntimeError("A/B order volume did not fall; dataset is not valid")
    sizes = _write(con, out)
    truth = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "scale": args.scale, "orders_target": orders_n,
        "october_west_ab_reduce_pct": reduce_pct,
        "row_counts": counts,
        "west_revenue_prior": round(prior, 2),
        "west_revenue_current": round(current, 2),
        "drop_pct_exact": round(drop, 4),
        "drop_pct": round(drop, 1),
        "segments": {k: {**v, "revenue_change": round(v["current_revenue"] - v["prior_revenue"], 2),
                         "order_change": v["current_orders"] - v["prior_orders"]}
                     for k, v in segments.items()},
        "ab_order_change": ab_order_change,
        "cd_order_change": cd_order_change,
        "settlement": settlement,
        "parquet_bytes": sizes,
    }
    truth_dir = out.parent.parent / "ground_truth"
    truth_dir.mkdir(parents=True, exist_ok=True)
    (truth_dir / f"{out.name}.json").write_text(
        json.dumps(truth, indent=2) + "\n", encoding="utf-8")
    con.close()
    elapsed = time.monotonic() - started
    print(f"wrote {out} in {elapsed:.1f}s")
    print(f"West {PRIOR} -> {CURRENT}: {prior:,.2f} -> {current:,.2f} "
          f"({drop:.4f}% -> {drop:.1f}%)")
    print(f"A/B orders {ab_order_change:+,}; C/D orders {cd_order_change:+,}; "
          f"settlement {settlement}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
