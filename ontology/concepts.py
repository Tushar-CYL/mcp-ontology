"""Shared concepts across sources: one Customer, not four tables.

Each source is discovered on its own (``ontology/discover.py``): CRM has an
Account, ERP a Customer, billing an Account, the MDM hub a GoldenCustomer.
This step decides, from evidence in the data, which of those tables are the
SAME business concept.

The evidence is a crosswalk: a column whose values cover another table's key.
A crosswalk alone does not mean "same thing" - every invoice points at an
order, and an invoice is not an order. Tables are unified only when

* the crosswalk is one-to-one (the column is near-unique and covers most of
  the other table's keys), AND
* an MDM hub vouches for it (the crosswalk lives in a source whose role is
  ``mdm_hub``) or the two class names are business synonyms
  (Account ~ Customer, Material ~ Product, Vendor ~ Supplier).

Any other crosswalk is kept as a relationship between concepts. Everything is
written to the registry as a proposal with its evidence; a person decides.
"""

from __future__ import annotations

from knowledge_graph.build import qi, table_ref
from ontology import registry as reg
from ontology.keys import _looks_like_id, _looks_like_name
from ontology.words import display_name, words as _split

# A column must cover at least this share of the other table's keys, and its
# own values must land inside that key set this often, to count as a crosswalk.
CONTAINMENT = 0.9      # share of the column's values found in the key
SAME_COVERAGE = 0.8    # share of the key's values the column reaches
NEAR_UNIQUE = 0.95     # distinct / non-null for a one-to-one crosswalk
MAX_PAIRS = 4000       # cost guard on very wide estates

# (canonical name, words that mean the same business thing)
SYNONYM_GROUPS = [
    ("Customer", {"customer", "account", "client", "buyer", "party", "partner",
                  "debtor", "kunde", "soldto", "billto"}),
    ("Product", {"product", "material", "item", "sku", "article", "part"}),
    ("Supplier", {"supplier", "vendor", "creditor"}),
    ("Employee", {"employee", "worker", "staff", "person"}),
    ("SalesOrder", {"order", "salesorder"}),
    ("Invoice", {"invoice", "bill", "billingdocument"}),
    ("Location", {"location", "site", "plant", "warehouse"}),
]
SYNONYMS = [words for _, words in SYNONYM_GROUPS]
ATTRIBUTE_OVERLAP = 0.8   # share of the smaller table's values found in the other
ALTERNATE_KEY = 0.99      # distinct / rows for a column to serve as a business key
MIN_LINK_VALUES = 20      # a code with fewer values is a category, not a link
_MASTER_PREFIXES = ("golden", "master", "gold", "mdm", "dim", "canonical")
# Words too generic to relate a column to a table by name.
_GENERIC = {"id", "no", "nr", "num", "number", "code", "key", "type", "group",
            "category", "name", "ref", "to", "date", "time", "status", "item", "items"}


def _words(name: str) -> list[str]:
    return _split(name)


def _table_stem(t: dict) -> str:
    """The concept-ish stem of a table: golden_customers -> customer."""
    return "".join(_words(display_name(t["table"].name))).lower()


def _synonyms(a: str, b: str) -> bool:
    if a == b:
        return True
    return any(a in group and b in group for group in SYNONYMS)


def _canonical(stems: set[str]) -> str | None:
    """Different words for one thing (account, customer) -> its canonical name."""
    for name, words in SYNONYM_GROUPS:
        if stems <= words:
            return name
    return None


def _norm_sql(column: str) -> str:
    return f"regexp_replace(lower(CAST({qi(column)} AS VARCHAR)), '[^a-z0-9]', '', 'g')"


def find_attribute_overlaps(graph, tables: list[dict], linked: set) -> list[dict]:
    """Same-entity evidence without shared ids: near-unique attributes (a tax
    id, a company name) whose normalised values overlap across two tables of
    synonymous classes in different sources."""
    def unique_text(t):
        out = []
        for c in t["table"].columns:
            if c.name.startswith("__") or c.name == t["id"]:
                continue
            if "VARCHAR" not in str(c.type).upper():
                continue
            if c.distinct is not None and t["rows"] and c.distinct / t["rows"] < 0.9:
                continue
            out.append(c.name)
        return out

    found = []
    for i, a in enumerate(tables):
        for b in tables[i + 1:]:
            if a["source"] == b["source"] or (a["key"], b["key"]) in linked \
                    or not _synonyms(_table_stem(a), _table_stem(b)):
                continue
            best = None
            for ca in unique_text(a):
                for cb in unique_text(b):
                    shared, na, nb = graph.sql(
                        f"SELECT (SELECT count(*) FROM (SELECT DISTINCT {_norm_sql(ca)} v"
                        f" FROM {a['ref']} WHERE {qi(ca)} IS NOT NULL) x JOIN (SELECT"
                        f" DISTINCT {_norm_sql(cb)} v FROM {b['ref']}) y USING (v)),"
                        f" (SELECT count(DISTINCT {_norm_sql(ca)}) FROM {a['ref']}),"
                        f" (SELECT count(DISTINCT {_norm_sql(cb)}) FROM {b['ref']})")[0]
                    share = shared / min(na, nb) if min(na, nb) else 0.0
                    if share >= ATTRIBUTE_OVERLAP and (best is None or share > best[0]):
                        best = (share, ca, cb, shared)
            if best:
                share, ca, cb, shared = best
                found.append({
                    "from": f"{a['key']}.{ca}", "to": f"{b['key']}.{cb}",
                    "from_table": a["key"], "to_table": b["key"], "matched": shared,
                    "contained": round(share, 4), "coverage": round(share, 4),
                    "unique": 1.0, "hub": False, "method": "attribute"})
    return found


def _tables(layer, onto) -> list[dict]:
    """Every visible table of the ontology's sources, with its class and key."""
    out = []
    for src in onto["sources"]:
        bundle = layer._bundle(src["source_id"])
        classes = {c.table: c for c in bundle.onto.classes.values()}
        for table in bundle.schema.tables:
            if getattr(table, "hidden", False) or table.name not in classes:
                continue
            klass = classes[table.name]
            out.append({
                "key": f"{src['source_id']}.{table.name}",
                "source": src["source_id"], "role": src["role"],
                "table": table, "class": klass.name,
                "id": None if klass.key_is_synthetic else klass.key,
                "rows": table.row_count or 0,
                "ref": table_ref(layer.graph, bundle.schema, table.name,
                                 source=src["source_id"]),
            })
    return out


def _distinct(graph, ref: str, column: str) -> tuple[int, int]:
    q = qi(column)
    non_null, distinct = graph.sql(
        f"SELECT count({q}), count(DISTINCT {q}) FROM {ref}")[0]
    return int(non_null or 0), int(distinct or 0)


def business_keys(t: dict) -> list[str]:
    """The table's key plus ALTERNATE keys: near-unique, non-name, non-date
    columns (SAP keys I_Customer on ADDRESSID; CUSTOMER is the business key)."""
    keys = [t["id"]] if t["id"] else []
    rows = t["rows"] or 0
    for c in t["table"].columns:
        if c.name.startswith("__") or c.name in keys or c.distinct is None or not rows:
            continue
        if _looks_like_name(c.name) and not _looks_like_id(c.name):
            continue
        if _family(c) != "text" and not (_family(c) == "numeric" and not _is_float(c)):
            continue
        if c.distinct >= MIN_LINK_VALUES and c.distinct / rows >= ALTERNATE_KEY:
            keys.append(c.name)
    return keys


def _family(column) -> str:
    from ontology.profile import _family as fam
    return fam(column)


def _is_float(column) -> bool:
    return any(x in str(column.type).upper() for x in ("DOUBLE", "FLOAT", "REAL",
                                                        "DECIMAL", "NUMERIC"))


def _related_by_name(column: str, t: dict, key: str) -> bool:
    """SALESDOCUMENT relates to salesdocuments; SOLDTOPARTY to Customer
    (party is a customer synonym); PLANT to nothing here."""
    mine = set(_words(column)) - _GENERIC
    theirs = (set(_words(key)) | set(_words(display_name(t["table"].name)))) - _GENERIC
    if mine & theirs:
        return True
    stem = _table_stem(t)
    return any(_synonyms(w, stem) or _synonyms(w, x) for w in mine for x in theirs)


def find_crosswalks(graph, tables: list[dict]) -> list[dict]:
    """Columns whose values cover another table's key, with the numbers.

    A column is tried against a key when it is named like an identifier, or
    carries the key's own name, or relates to the key's table by name (with
    at least MIN_LINK_VALUES values, so a 3-value code never becomes a link).
    Values decide: at least CONTAINMENT of the column's values must be keys.
    """
    targets = [(t, k) for t in tables for k in business_keys(t)]
    stats: dict = {}

    def stat(t, col):
        k = (t["key"], col)
        if k not in stats:
            stats[k] = _distinct(graph, t["ref"], col)
        return stats[k]

    found, pairs = [], 0
    for a in tables:
        for col in a["table"].columns:
            name = col.name
            if name.startswith("__") or _family(col) == "temporal" or _is_float(col):
                continue
            id_named = _looks_like_id(name) and name != a["id"]
            for b, key in targets:
                if b["key"] == a["key"]:
                    continue
                same_name = name.lower() == key.lower()
                if not (id_named or same_name or _related_by_name(name, b, key)):
                    continue
                pairs += 1
                if pairs > MAX_PAIRS:
                    return found
                a_non_null, a_distinct = stat(a, name)
                _, b_distinct = stat(b, key)
                if not a_distinct or not b_distinct:
                    continue
                if not (id_named or same_name) and a_distinct < MIN_LINK_VALUES:
                    continue
                if a_distinct > b_distinct / CONTAINMENT:
                    continue                 # cannot be contained: skip the join
                matched = int(graph.sql(
                    f"SELECT count(*) FROM (SELECT DISTINCT CAST({qi(name)} AS VARCHAR) v"
                    f" FROM {a['ref']} WHERE {qi(name)} IS NOT NULL) x JOIN"
                    f" (SELECT DISTINCT CAST({qi(key)} AS VARCHAR) v FROM {b['ref']}) y"
                    f" USING (v)")[0][0])
                contained = matched / a_distinct
                if contained < CONTAINMENT:
                    continue
                found.append({
                    "from": f"{a['key']}.{name}", "to": f"{b['key']}.{key}",
                    "from_table": a["key"], "to_table": b["key"],
                    "matched": matched, "contained": round(contained, 4),
                    "coverage": round(matched / b_distinct, 4),
                    "unique": round(a_distinct / a_non_null, 4) if a_non_null else 0.0,
                    "hub": a["role"] == "mdm_hub" or b["role"] == "mdm_hub",
                    "alternate_key": key != b["id"],
                })
    return found


def duplicate_business_keys(graph, tables: list[dict]) -> list[dict]:
    """A column that names the table's own identity (CUSTOMER in I_Customer)
    and is almost - but not - unique: the repeats are a data-quality fact."""
    out = []
    for t in tables:
        stem = _table_stem(t)
        rows = t["rows"] or 0
        for c in t["table"].columns:
            if c.name.startswith("__") or c.distinct is None or not rows:
                continue
            if "".join(_words(c.name)).lower() != stem or c.distinct >= rows:
                continue
            if c.distinct / rows < ALTERNATE_KEY:
                continue
            dup_sql = (f"SELECT {qi(c.name)} FROM {t['ref']} WHERE {qi(c.name)} IS NOT NULL"
                       f" GROUP BY 1 HAVING count(*) > 1")
            repeated = int(graph.sql(f"SELECT count(*) FROM ({dup_sql}) g")[0][0])
            if not repeated:
                continue
            sample = [str(r[0]) for r in graph.sql(f"{dup_sql} ORDER BY 1 LIMIT 5")]
            out.append({
                "type": "duplicate_business_key", "column": f"{t['key']}.{c.name}",
                "repeated_values": repeated, "sample": sample,
                "detail": (f"{t['key']}.{c.name} identifies a "
                           f"{display_name(t['table'].name)} but {repeated} value(s) "
                           f"appear more than once (e.g. {', '.join(sample[:3])}); "
                           f"the table is keyed on {t['id'] or 'a row number'} instead")})
    return out


def _is_same_entity(walk: dict, by_key: dict) -> bool:
    if walk["unique"] < NEAR_UNIQUE or walk["coverage"] < SAME_COVERAGE:
        return False
    a, b = by_key[walk["from_table"]], by_key[walk["to_table"]]
    return walk["hub"] or _synonyms(_table_stem(a), _table_stem(b))


def _evidence(walk: dict) -> str:
    if walk.get("method") == "attribute":
        return (f"{walk['from']} and {walk['to']} share {walk['matched']} values after"
                f" normalising ({walk['coverage']:.0%} of the smaller set)")
    return (f"{walk['from']} covers {walk['coverage']:.0%} of {walk['to']}"
            f" ({walk['matched']} shared values; {walk['contained']:.0%} of its"
            f" values match; {walk['unique']:.0%} unique)")


def _describe(name: str, members: list[dict], master: str | None) -> str:
    if len(members) == 1:
        m = members[0]
        ident = f", identified by {m['id']}" if m["id"] else \
            " (no natural identifier; rows are numbered)"
        return (f"{name}: one row per {_words(name)[-1] if _words(name) else 'record'}"
                f" in {m['key']} ({m['rows']:,} rows){ident}.")
    where = "; ".join(f"{m['table'].name} in {m['source']} ({m['id'] or 'row number'})"
                      for m in members)
    text = (f"{name}: one business entity recorded in {len(members)} systems"
            f" under different ids - {where}.")
    if master:
        text += f" Mastered in {master}, which cross-references the others."
    return text


def propose_concepts(layer, ontology_id: str) -> dict:
    """Group the ontology's tables into shared concepts and record proposals."""
    onto = reg.get(layer.graph, ontology_id)
    tables = _tables(layer, onto)
    by_key = {t["key"]: t for t in tables}
    walks = find_crosswalks(layer.graph, tables)
    linked = {(w["from_table"], w["to_table"]) for w in walks} |         {(w["to_table"], w["from_table"]) for w in walks}
    attribute_walks = find_attribute_overlaps(layer.graph, tables, linked)

    # Union-find over same-entity crosswalks.
    parent = {t["key"]: t["key"] for t in tables}

    def root(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for w in walks:
        w["kind"] = "same_entity" if _is_same_entity(w, by_key) else "reference"
        if w["kind"] == "same_entity":
            parent[root(w["from_table"])] = root(w["to_table"])
    for w in attribute_walks:
        w["kind"] = "same_entity"
        parent[root(w["from_table"])] = root(w["to_table"])
    walks += attribute_walks

    groups: dict = {}
    for t in tables:
        groups.setdefault(root(t["key"]), []).append(t)

    concepts, used = [], set()
    for members in sorted(groups.values(), key=lambda g: (-len(g), g[0]["key"])):
        members.sort(key=lambda m: m["key"])
        hubs = [m for m in members if m["role"] == "mdm_hub"]
        master = hubs[0]["key"] if len(members) > 1 and hubs else None
        if master:
            name = display_name(by_key[master]["table"].name)
        else:
            stems = [_table_stem(m) for m in members]
            best = sorted(set(stems), key=lambda s: (-stems.count(s), len(s), s))[0]
            name = (len(set(stems)) > 1 and _canonical(set(stems))) or display_name(
                next(m["table"].name for m in members if _table_stem(m) == best))
        if name in used:
            name = f"{name}{''.join(w.capitalize() for w in _words(members[0]['source']))}"
        used.add(name)
        keys = {m["key"] for m in members}
        evidence = [_evidence(w) for w in walks if w["kind"] == "same_entity"
                    and w["from_table"] in keys and w["to_table"] in keys]
        if not evidence:
            evidence = [f"{m['key']}: {m['rows']:,} rows, discovered as {m['class']}"
                        for m in members]
        confidence = round(min([1.0] + [w["coverage"] for w in walks
                                        if w["kind"] == "same_entity"
                                        and w["from_table"] in keys]), 3) \
            if len(members) > 1 else 0.9
        concepts.append({
            "name": name, "members": [m["key"] for m in members],
            "master": master, "keys": {m["key"]: m["id"] for m in members},
            "classes": {m["key"]: m["class"] for m in members},
            "description": _describe(name, members, master),
            "evidence": evidence, "confidence": confidence,
        })

    concept_of = {m: c["name"] for c in concepts for m in c["members"]}
    for w in walks:
        w["from_concept"] = concept_of[w["from_table"]]
        w["to_concept"] = concept_of[w["to_table"]]

    graph = layer.graph
    keep_concepts, keep_members, keep_links = set(), set(), set()
    for c in concepts:
        payload = {k: c[k] for k in ("name", "description", "members", "master",
                                     "keys", "classes")}
        reg.put(graph, ontology_id, "concept", c["name"], payload,
                confidence=c["confidence"], evidence=c["evidence"])
        keep_concepts.add(c["name"])
        for m in c["members"]:
            key = f"{c['name']}|{m}"
            reg.put(graph, ontology_id, "member", key,
                    {"concept": c["name"], "table": m, "key": c["keys"][m],
                     "role": by_key[m]["role"], "master": m == c["master"]},
                    confidence=c["confidence"], evidence=c["evidence"][:3])
            keep_members.add(key)
    for w in walks:
        if w["kind"] != "reference" or w["from_concept"] == w["to_concept"]:
            continue
        key = f"{w['from']}->{w['to']}"
        reg.put(graph, ontology_id, "relationship", key,
                {"from_concept": w["from_concept"], "to_concept": w["to_concept"],
                 "from": w["from"], "to": w["to"], "coverage": w["coverage"],
                 "contained": w["contained"], "unique": w["unique"]},
                confidence=w["contained"], evidence=[_evidence(w)])
        keep_links.add(key)
    dup_keys = duplicate_business_keys(graph, tables)
    keep_findings = set()
    for f in dup_keys:
        key = f"{f['type']}|{f['column']}"
        keep_findings.add(key)
        reg.put(graph, ontology_id, "finding", key, f, confidence=0.95,
                evidence=[f["detail"]])
    reg.prune(graph, ontology_id, "finding", keep_findings,
              prefixes=("duplicate_business_key|",))
    reg.prune(graph, ontology_id, "concept", keep_concepts)
    reg.prune(graph, ontology_id, "member", keep_members)
    reg.prune(graph, ontology_id, "relationship", keep_links)
    return {"concepts": concepts, "crosswalks": walks, "findings": dup_keys}
