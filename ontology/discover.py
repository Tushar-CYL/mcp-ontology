"""Layer 1: turn a schema into an ontology, without being told anything.

This is the file that makes the product claim true or false. If a schema
cannot be read into classes, relations, time and measures on its own, then
every new dataset needs a human to write a mapping, and we are selling
consulting rather than a product.

What the source can tell us, and what it cannot:

    STRUCTURE is readable.  A table is a kind of thing. A foreign key is a
    relationship. A date column says when a row was true. A numeric column
    is something you would want to average.

    NAMES are not.  Nothing in a schema says that `tbl_cust_01` means
    Customer. That one gap is closed by an override - a stored rename, not
    a code change - and nothing else about discovery changes.

Every rule here is deterministic: the same schema always gives the same
ontology, including the class codes, because those codes are written onto
tens of millions of rows and must not drift between runs.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from ontology.schema import (Schema, Table, is_boolean, is_numeric,
                             is_temporal, is_textual)

# A column called `created_at` says when the row became true. `updated_at`
# says when somebody last touched it. Validity starts at the former, so the
# list is ordered by preference, not alphabetically.
TIME_PREFERENCE = ("created", "started", "opened", "placed", "occurred",
                   "event", "timestamp", "date", "at", "time",
                   "modified", "updated")

# Irregular plurals worth knowing. Anything else falls through to the
# suffix rules below, which handle the ordinary cases.
IRREGULAR = {"people": "person", "children": "child", "men": "man",
             "women": "woman", "teeth": "tooth", "feet": "foot",
             "mice": "mouse", "geese": "goose", "data": "datum",
             "indices": "index", "matrices": "matrix", "vertices": "vertex"}


def singular(word: str) -> str:
    """Best-effort singular. Wrong occasionally, and that is acceptable:
    a class called `Addres` is ugly but harmless, and a rename fixes it."""
    w = word.lower()
    if w in IRREGULAR:
        return IRREGULAR[w]
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith(("ses", "xes", "zes", "ches", "shes")):
        return w[:-2]
    # `status`, `address`, `series` are already singular despite the s.
    if w.endswith("ss") or w.endswith("us") or w.endswith("ies"):
        return w
    if w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


# Words that describe the EXPORT, not the data. Real files are called
# `olist_customers_dataset`, `dim_customer`, `stg_orders_v2` - and a class
# called OlistCustomersDataset is unusable in front of anyone.
NOISE = {"dataset", "data", "table", "tbl", "dim", "fact", "fct", "stg",
         "staging", "raw", "final", "export", "extract", "tmp", "temp",
         "new", "old", "copy", "backup", "bak", "csv", "file"}

VERSION = re.compile(r"^v?\d+$")


def core_name(table: str) -> str:
    """The meaningful part of a table name, with export noise removed.

    `olist_customers_dataset` -> `customers`. If every part is noise the
    name is kept whole: something must be left to call the class.
    """
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", table.lower()) if p]
    kept = [p for p in parts if p not in NOISE and not VERSION.match(p)]
    return "_".join(kept) if kept else "_".join(parts) or table.lower()


def strip_common_prefix(names: list[str]) -> list[str]:
    """Drop a first word shared by EVERY table.

    It names the export, not the thing. Requiring EVERY table to share it
    was too strict on real data: the Olist export has `olist_` on eight of
    nine files, and the ninth
    (`product_category_name_translation`) left every class called
    OlistSomething. A clear majority is enough, and the odd table out keeps
    its name.
    """
    if len(names) < 2:
        return list(names)
    from collections import Counter
    firsts = Counter(n.split("_", 1)[0] for n in names if "_" in n)
    if not firsts:
        return list(names)
    prefix, hits = firsts.most_common(1)[0]
    if hits < 2 or hits / len(names) < 0.6:
        return list(names)
    out = []
    for n in names:
        tail = n[len(prefix) + 1:] if n.startswith(prefix + "_") else n
        out.append(tail or n)       # never strip a name down to nothing
    return out


def class_name(table: str) -> str:
    """`olist_order_items_dataset` -> `OrderItem`. Stable for a given input."""
    parts = re.split(r"[^A-Za-z0-9]+", core_name(table))
    parts = [p for p in parts if p]
    if not parts:
        return "Thing"
    parts[-1] = singular(parts[-1])
    return "".join(p[:1].upper() + p[1:] for p in parts)


def stable_code(name: str, taken: set[int]) -> int:
    """A small, stable integer for a name.

    Stored as smallint on every node and edge, so it must be identical on
    every run or a rebuild silently reinterprets the whole graph. Derived
    from the name rather than from position, because a new table appearing
    must not renumber the existing ones.
    """
    h = int(hashlib.sha256(name.encode()).hexdigest(), 16)
    code = h % 30000 + 1
    while code in taken:            # collisions are rare and resolved the
        code = code % 30000 + 1     # same way every time, so still stable
    return code


@dataclass
class DiscoveredClass:
    name: str
    code: int
    table: str
    key: str
    # Every column of the key. A composite key - order_items keyed by
    # (order_id, line) - is normal, and taking only the first column made
    # three rows collapse into two because order_id repeats.
    key_columns: list[str] = field(default_factory=list)
    provenance: str = "measured"
    key_is_synthetic: bool = False
    time_column: str | None = None
    measures: list[str] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)


@dataclass
class DiscoveredRelation:
    name: str
    code: int
    domain: str
    range: str
    column: str
    ref_column: str
    provenance: str = "measured"   # 'measured' = the source declared it
    confidence: float = 1.0


@dataclass
class Ontology:
    classes: dict[str, DiscoveredClass] = field(default_factory=dict)
    relations: dict[str, DiscoveredRelation] = field(default_factory=dict)
    source: str = "source"

    def class_for_table(self, table: str) -> DiscoveredClass | None:
        lowered = table.lower()
        return next((c for c in self.classes.values()
                     if c.table.lower() == lowered), None)


def _pick_time(table: Table) -> str | None:
    temporal = [c.name for c in table.columns if is_temporal(c)]
    if not temporal:
        return None
    for want in TIME_PREFERENCE:
        for name in temporal:
            if want in name.lower():
                return name
    return temporal[0]


def _unique(name: str, taken: set[str]) -> str:
    """Two tables can singularise to the same class name. Neither may
    overwrite the other, so the loser keeps a suffix."""
    if name not in taken:
        return name
    i = 2
    while f"{name}{i}" in taken:
        i += 1
    return f"{name}{i}"


def discover(schema: Schema, names: dict[str, str] | None = None) -> Ontology:
    """Schema in, ontology out.

    `names` overrides a table's class name - the one piece a schema cannot
    supply. It is configuration, not code: nothing else changes with it.
    """
    if not schema.tables:
        raise ValueError("source has no tables - nothing to discover")

    names = {k.lower(): v for k, v in (names or {}).items()}
    onto = Ontology(source=schema.name)

    # A first word shared by EVERY table names the export, not the data -
    # `olist_` on all nine Olist files. Only visible across the whole set,
    # which is why it is removed here and not inside core_name().
    cores = [core_name(t.name) for t in schema.tables]
    cleaned = dict(zip([t.name for t in schema.tables],
                       strip_common_prefix(cores)))

    # --------------------------------------------------------- classes
    taken_names: set[str] = set()
    taken_codes: set[int] = set()
    for t in schema.tables:
        name = names.get(t.name.lower()) or class_name(cleaned[t.name])
        name = _unique(name, taken_names)
        taken_names.add(name)

        synthetic = not t.primary_key
        key_cols = list(t.primary_key)
        key = key_cols[0] if key_cols else "__row"
        code = stable_code(name, taken_codes)
        taken_codes.add(code)

        fk_cols = {fk.column.lower() for fk in t.foreign_keys}
        time_col = _pick_time(t)

        measures, dimensions = [], []
        for c in t.columns:
            low = c.name.lower()
            if low == key.lower() or low in fk_cols or low == (time_col or "").lower():
                continue
            # A column that names another table is a link, not a number to
            # average, even when it is stored as an integer.
            if _referenced_table(schema, c.name):
                continue
            if is_numeric(c):
                measures.append(c.name)
            elif is_textual(c) or is_boolean(c):
                dimensions.append(c.name)

        onto.classes[name] = DiscoveredClass(
            name=name, code=code, table=t.name, key=key,
            key_columns=key_cols, key_is_synthetic=synthetic,
            time_column=time_col, measures=measures, dimensions=dimensions)

    # -------------------------------------------------------- relations
    rel_names: set[str] = set()
    for t in schema.tables:
        src = onto.class_for_table(t.name)
        if src is None:
            continue

        declared = {fk.column.lower() for fk in t.foreign_keys}

        # What the source states. Trustworthy, so provenance is 'measured'.
        for fk in t.foreign_keys:
            target = onto.class_for_table(fk.ref_table)
            if target is None:
                continue
            _add_relation(onto, rel_names, taken_codes, src, target,
                          fk.column, fk.ref_column, "measured", 1.0)

        # What we work out ourselves: a column named after another table.
        # Common in warehouses where constraints were never created, and in
        # every CSV. Always 'derived' - a guess must never read as a fact.
        for c in t.columns:
            # A column is excluded for being THE key only when the key is a
            # single column. In a composite key - a join table keyed by
            # (order_id, line) - the key columns are usually foreign keys
            # too, and skipping them left such tables connected to nothing.
            sole_key = (len(src.key_columns) <= 1
                        and c.name.lower() == src.key.lower())
            if c.name.lower() in declared or sole_key:
                continue
            ref = _referenced_table(schema, c.name)
            if ref is None or ref.name.lower() == t.name.lower():
                continue
            target = onto.class_for_table(ref.name)
            if target is None:
                continue
            ref_key = ref.primary_key[0] if ref.primary_key else "__row"
            _add_relation(onto, rel_names, taken_codes, src, target,
                          c.name, ref_key, "derived", 0.7)

    return onto


def _referenced_table(schema: Schema, column: str) -> Table | None:
    """Does this column name point at another table?

    `customer_id` -> customers. Matching on the stem rather than the whole
    name is what makes it work across naming conventions: `customer_id`,
    `customerId`, `fk_customer` and `customer_ref` all reduce to `customer`.
    """
    stem = re.sub(r"(^fk_|_?id$|_?ref$|_?key$|_?code$)", "",
                  column.lower().replace("-", "_"))
    stem = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", stem).strip("_")
    if not stem:
        return None
    for t in schema.tables:
        core = core_name(t.name)
        if core == stem or singular(core) == singular(stem):
            return t
    # Last resort: the stem is the TAIL of the core name. `customer_id`
    # against `ecommerce_customers`, which the exact match above misses.
    for t in schema.tables:
        core = singular(core_name(t.name))
        if core.endswith("_" + singular(stem)) or singular(stem) == core:
            return t
    return None


def _add_relation(onto, rel_names, taken_codes, src, target,
                  column, ref_column, provenance, confidence) -> None:
    # Named from the COLUMN, not the target table: `sender_id` and
    # `recipient_id` both point at people and must not collide.
    base = re.sub(r"(_?id|_?ref|_?key|_?code)$", "", column.lower()) or column.lower()
    # Several tables legitimately have a `customer_id`. Numbering the
    # clashes (`order2`, `order3`) hides which is which, so a clash is
    # qualified by the table that owns it: `payment_order`, `review_order`.
    if base in rel_names:
        base = f"{src.name.lower()}_{base}"
    name = _unique(base, rel_names)
    rel_names.add(name)
    code = stable_code(f"{src.name}.{name}", taken_codes)
    taken_codes.add(code)
    onto.relations[name] = DiscoveredRelation(
        name=name, code=code, domain=src.name, range=target.name,
        column=column, ref_column=ref_column,
        provenance=provenance, confidence=confidence)
