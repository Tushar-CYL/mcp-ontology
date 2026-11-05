"""Semantic autopilot: propose governed metrics for any dataset.

The hand-curated revenue catalog only fits order/line/product data. A real
enterprise source (SAP SALT: sales documents, items, customers and addresses,
no money columns at all) otherwise gets no metrics, an empty Semantic layer
and nothing for agents to measure.

Like Snowflake's Semantic View Autopilot and Databricks metric views
(docs/research/2026/03_semantic_layer.md), Strata proposes metrics from the
data itself and stores them as DRAFTS for a person to approve:

* **count**: records per entity, dated by its own date column or by its
  parent's along a verified many-to-one link (items take their document's
  date);
* **ratio**: child records per parent (items per sales document);
* **distinct**: distinct values of high-cardinality reference columns
  (products, sold-to parties);
* **total / average**: real numeric measures only - nothing is invented when
  a dataset has none;
* low-cardinality columns become dimensions; technical columns
  (``__index_level_0__``, ``__row``) and duplicate split tables (``_train``,
  ``_test``) are ignored.

Every link used for a join is checked against the data (values of the child
column must exist in the parent's unique key), so a proposal never fans out.
"""

from __future__ import annotations

import re

from ontology.words import segment

from knowledge_graph.build import qi, table_ref
from semantic import definitions as metric_defs

OWNER = "Strata autopilot"
CAVEAT = ("Proposed automatically from the data; check the definition, then "
          "approve it before agents use it.")
AUTO_CAVEAT = ("Counted directly from the data, so it is exact by construction;"
               " approved automatically. A person can send it back to draft.")
# Exact facts read straight from the data need no business judgement, so they
# are approved automatically. Totals and averages of amount-like columns can
# need business rules ("only completed orders count") and wait for a person.
MECHANICAL = ("count", "distinct", "ratio")


def is_mechanical(value_expr: str) -> bool:
    expr = " ".join(str(value_expr or "").upper().split())
    return (expr == "COUNT(*)" or expr.startswith("COUNT(DISTINCT ")
            or (expr.startswith("COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT ")))
MAX_DIMENSIONS = 8
MAX_DISTINCT = 3
MAX_PER_SOURCE = 40
DIM_MIN, DIM_MAX = 2, 60
INCLUSION = 0.9                      # share of child values found in the parent

_NUMERIC = ("TINYINT", "SMALLINT", "INTEGER", "INT", "BIGINT", "HUGEINT",
            "DOUBLE", "FLOAT", "REAL", "DECIMAL", "NUMERIC", "UBIGINT",
            "UINTEGER", "USMALLINT", "UTINYINT")
_TIME = ("DATE", "TIMESTAMP")
_SPLIT = re.compile(r"(_(train|test|val|valid|validation|dev|sample|copy|bak|"
                    r"backup|old|tmp)|\d+)$", re.I)
_PREFIX = {"i", "t", "v", "f", "d", "dim", "fact", "stg", "tbl", "vw"}
_ID_LIKE = re.compile(r"(^|_)(id|key|no|num|nr|number|code|item|position|pos|"
                      r"line|seq|index|year|month|day|zip|postcode)$", re.I)
_ML_SPLIT = re.compile(r"_(train|test|val|valid|validation|dev)$", re.I)
# Run-together names (SAP "salesdocumentitem") are split by the shared
# vocabulary in ontology/words.py, so the ontology and semantic layers agree.
_REF_HINT = ("party", "customer", "product", "material", "vendor", "supplier",
             "user", "account", "client", "employee", "store", "sku")


# ----------------------------------------------------------------- naming
def _is_technical(name: str) -> bool:
    low = name.lower()
    return low.startswith("__") or low in ("index", "_row", "level_0") \
        or low.startswith("unnamed")


_segment = segment


def _core_words(table: str) -> list[str]:
    words = [w for w in re.split(r"[_\W]+", table.lower()) if w]
    while len(words) > 1 and words[0] in _PREFIX:
        words = words[1:]
    out: list[str] = []
    for word in words:
        out.extend(_segment(word))
    return out


def _noun(table: str) -> str:
    return " ".join(_core_words(table)) or table


def _slug(table: str) -> str:
    return "_".join(_core_words(table)) or re.sub(r"\W+", "_", table.lower())


def _singular(noun: str) -> str:
    if noun.endswith("ies"):
        return noun[:-3] + "y"
    if noun.endswith("ses") or noun.endswith("xes"):
        return noun[:-2]
    if noun.endswith("s") and not noun.endswith("ss"):
        return noun[:-1]
    return noun


def _plural(noun: str) -> str:
    if noun.endswith("s"):
        return noun
    if noun.endswith("y") and noun[-2:-1] not in "aeiou":
        return noun[:-1] + "ies"
    return noun + "s"


def _human(column: str) -> str:
    """'SHIPTOPARTY' -> 'ship to party'; 'line_revenue' -> 'line revenue'."""
    words: list[str] = []
    for part in column.lower().split("_"):
        if part:
            words.extend(_segment(part))
    return " ".join(words) or column.lower()


# --------------------------------------------------------------- profiling
def _base_type(column) -> str:
    return str(getattr(column, "type", "") or "").upper().split("(")[0].strip()


def _is_temporal(column) -> bool:
    """Dates, timestamps and times of day: never a reference or dimension."""
    return _base_type(column).startswith(("DATE", "TIME", "INTERVAL"))


def _profile(graph, ref: str, columns: list) -> tuple[int, dict[str, int]]:
    """Row count and approximate distinct count per column, in one scan."""
    if not columns:
        return int(graph.one(f"SELECT count(*) FROM {ref}") or 0), {}
    parts = ", ".join(f"approx_count_distinct({qi(c.name)})" for c in columns)
    row = graph.sql(f"SELECT count(*), {parts} FROM {ref}")[0]
    return int(row[0] or 0), {c.name: int(v or 0) for c, v in zip(columns, row[1:])}


def _columns_signature(table) -> frozenset:
    return frozenset(c.name.lower() for c in table.columns
                     if not _is_technical(c.name))


def canonical_tables(schema, row_counts: dict[str, int]) -> set[str]:
    """Drop split/backup copies: a table whose columns equal another's and
    whose name is that one plus a split suffix, or the smaller of a group."""
    groups: dict[frozenset, list] = {}
    tables = [t for t in schema.tables if not getattr(t, "hidden", False)]
    # Machine-learning splits (_train/_test/...) are never the system of
    # record; drop them unless the whole dataset is splits.
    if any(not _ML_SPLIT.search(t.name) for t in tables):
        tables = [t for t in tables if not _ML_SPLIT.search(t.name)]
    for table in tables:
        groups.setdefault(_columns_signature(table), []).append(table)
    keep: set[str] = set()
    for tables in groups.values():
        def rank(t):
            split = bool(_SPLIT.search(t.name))
            return (split, -row_counts.get(t.name, 0), len(t.name))
        keep.add(sorted(tables, key=rank)[0].name)
    return keep


# ---------------------------------------------------------------- proposer
def propose_metrics(graph, schema, onto, source: str) -> list[dict]:
    by_table = {t.name: t for t in schema.tables}
    klass_of = {c.table: c for c in onto.classes.values()}
    refs, profiles, rows = {}, {}, {}
    for table in schema.tables:
        try:
            refs[table.name] = table_ref(graph, schema, table.name, source=source)
        except Exception:                          # noqa: BLE001 - not materialised
            continue
        useful = [c for c in table.columns if not _is_technical(c.name)]
        rows[table.name], profiles[table.name] = _profile(graph, refs[table.name], useful)
    keep = canonical_tables(schema, rows) & set(refs)

    def time_of(table) -> str | None:
        klass = klass_of.get(table.name)
        if klass is not None and klass.time_column:
            col = next((c for c in table.columns if c.name == klass.time_column), None)
            if col is not None and _base_type(col).startswith(_TIME):
                return col.name
        for col in table.columns:
            if _base_type(col).startswith(_TIME) and not _is_technical(col.name):
                return col.name
        return None

    def key_of(table) -> str | None:
        klass = klass_of.get(table.name)
        key = klass.key if klass is not None else None
        if key and not _is_technical(key) and \
                profiles[table.name].get(key, 0) >= rows[table.name] * 0.98:
            return key
        return None

    def dims_of(table, exclude=()) -> list[str]:
        prof = profiles[table.name]
        cands = [c.name for c in table.columns
                 if not _is_technical(c.name) and c.name not in exclude
                 and DIM_MIN <= prof.get(c.name, 0) <= DIM_MAX
                 and not _is_temporal(c)]
        return sorted(cands, key=lambda n: prof.get(n, 0))[:MAX_DIMENSIONS]

    def verified_parent(child, column: str):
        """A dated canonical table whose unique key holds this column's values."""
        for name in sorted(keep):
            if name == child.name:
                continue
            parent = by_table[name]
            key = key_of(parent)
            if not key or key.lower() != column.lower() or time_of(parent) is None:
                continue
            exact = graph.one(
                f"SELECT count(*) = count(DISTINCT {qi(key)}) FROM {refs[name]}")
            if not exact:
                continue
            missing = graph.one(
                f"SELECT avg(CASE WHEN p.{qi(key)} IS NULL THEN 1.0 ELSE 0 END)"
                f" FROM (SELECT {qi(column)} AS v FROM {refs[child.name]}"
                f" WHERE {qi(column)} IS NOT NULL LIMIT 50000) c"
                f" LEFT JOIN {refs[name]} p"
                f" ON CAST(c.v AS VARCHAR) = CAST(p.{qi(key)} AS VARCHAR)")
            if missing is not None and float(missing) <= 1 - INCLUSION:
                return parent, key
        return None, None

    proposals: list[dict] = []
    for name in sorted(keep, key=lambda n: -rows.get(n, 0)):
        table = by_table[name]
        if not rows.get(name):
            continue
        klass = klass_of.get(name)
        entity = klass.name if klass is not None else name
        prof = profiles[name]
        noun = _noun(name)
        own_key = key_of(table)
        time_col = time_of(table)
        parent, fk = (None, None)
        parent_links = []
        for col in table.columns:
            if _is_technical(col.name) or col.name == own_key:
                continue
            p, k = verified_parent(table, col.name)
            if p is not None:
                parent_links.append((col.name, p, k))
        if parent_links:
            fk, parent, _ = parent_links[0]

        # The base query: own columns, plus the parent's date and dimensions
        # when this table has no date of its own.
        select = []
        join = ""
        dims = dims_of(table)
        out_time = time_col
        if time_col is None and parent is not None:
            pkey = key_of(parent)
            out_time = time_of(parent)
            join = (f" LEFT JOIN {refs[parent.name]} p ON CAST(t.{qi(fk)} AS VARCHAR)"
                    f" = CAST(p.{qi(pkey)} AS VARCHAR)")
            parent_dims = [d for d in dims_of(parent, exclude=set(dims) | {fk})
                           if d not in {c.name for c in table.columns}]
            select.append(f"p.{qi(out_time)} AS {qi(out_time)}")
            select += [f"p.{qi(d)} AS {qi(d)}" for d in parent_dims]
            dims = (dims + parent_dims)[:MAX_DIMENSIONS]
        elif time_col is not None:
            select.append(f"t.{qi(time_col)} AS {qi(time_col)}")
        own_cols = [c for c in table.columns
                    if not _is_technical(c.name) and c.name != time_col]
        select += [f"t.{qi(c.name)} AS {qi(c.name)}" for c in own_cols]
        base = f"SELECT {', '.join(select)} FROM {refs[name]} t{join}"

        def add(kind, metric_name, title, description, expr, fmt="integer",
                precision=0, unit=""):
            proposals.append({
                "kind": kind, "entity": entity, "name": metric_name,
                "title": title, "description": description, "unit": unit,
                "base_sql": base, "value_expr": expr, "time_column": out_time,
                "dimensions": list(dims), "format": fmt, "precision": precision})

        slug = _slug(name)
        add("count", f"{slug}_count", f"Number of {_plural(noun)}",
            f"How many {_plural(noun)} there are"
            + (f", dated by {out_time}" if out_time else "") + ".",
            "COUNT(*)", unit=_plural(noun))

        for col, p, _k in parent_links[:2]:
            pnoun = _singular(_noun(p.name))
            add("ratio", f"{slug}_per_{_slug(p.name)}",
                f"{_plural(noun).capitalize()} per {pnoun}",
                f"Average number of {_plural(noun)} on each {pnoun}.",
                f"COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT {qi(col)}), 0)",
                fmt="number", precision=2)

        linked = {col for col, _p, _k in parent_links}
        refs_cols = [c for c in table.columns
                     if not _is_technical(c.name) and c.name not in linked
                     and c.name != own_key and not _is_temporal(c)
                     and prof.get(c.name, 0) > DIM_MAX
                     # near-unique columns are identifiers, not references
                     and prof.get(c.name, 0) < rows[name] * 0.9
                     and not _base_type(c).startswith(_NUMERIC)]
        refs_cols.sort(key=lambda c: (not any(h in c.name.lower() for h in _REF_HINT),
                                      -prof.get(c.name, 0)))
        for col in refs_cols[:MAX_DISTINCT]:
            add("distinct", f"{slug}_distinct_{col.name.lower()}",
                f"Distinct {_human(col.name)} in {_plural(noun)}",
                f"How many different {_human(col.name)} values appear in "
                f"{_plural(noun)}.", f"COUNT(DISTINCT {qi(col.name)})",
                unit=_human(col.name))

        for col in table.columns:
            if _is_technical(col.name) or col.name == own_key \
                    or not _base_type(col).startswith(_NUMERIC) \
                    or _ID_LIKE.search(col.name) or prof.get(col.name, 0) <= 20:
                continue
            label = _human(col.name)
            add("total", f"{slug}_{col.name.lower()}_total", f"Total {label}",
                f"Sum of {label} over {_plural(noun)}.", f"SUM({qi(col.name)})",
                fmt="number", precision=2)
            add("average", f"{slug}_{col.name.lower()}_average",
                f"Average {label}", f"Average {label} per {_singular(noun)}.",
                f"AVG({qi(col.name)})", fmt="number", precision=2)
    return proposals[:MAX_PER_SOURCE]


def seed_proposals(graph, schema, onto, source: str) -> list[str]:
    """Save proposals as drafts. Does nothing when the source already has
    metric definitions, so a curated catalog or an approved metric is never
    overwritten and re-running is free."""
    if metric_defs.list_definitions(graph, source):
        return []
    created = []
    for p in propose_metrics(graph, schema, onto, source):
        if metric_defs.get_definition(graph, p["name"], source) is not None:
            continue
        exact = p["kind"] in MECHANICAL
        metric_defs.upsert_metric(
            graph, source=source, name=p["name"], title=p["title"],
            base_sql=p["base_sql"], value_expr=p["value_expr"],
            description=p["description"], unit=p["unit"],
            time_column=p["time_column"], dimensions=p["dimensions"],
            owner=OWNER, status="approved" if exact else "draft",
            format=p["format"], precision=p["precision"],
            caveats=AUTO_CAVEAT if exact else CAVEAT)
        created.append(p["name"])
    return created


def upgrade_mechanical(graph, source: str) -> list[str]:
    """Approve autopilot drafts that are exact facts and that nobody has
    touched (version 1). Sources seeded before auto-approval existed get the
    same treatment as new ones; a metric a person sent back to draft (its
    version moved on) is left alone."""
    upgraded = []
    for d in metric_defs.list_definitions(graph, source):
        if d.get("owner") != OWNER or d.get("status") != "draft" \
                or int(d.get("version") or 1) != 1 \
                or not is_mechanical(d.get("value_expr")):
            continue
        with graph.lock:
            graph.con.execute(
                "UPDATE metric_definitions SET status = 'approved', caveats = ?"
                " WHERE source_id = ? AND name = ?",
                [AUTO_CAVEAT, source, d["name"]])
        upgraded.append(d["name"])
    return upgraded
