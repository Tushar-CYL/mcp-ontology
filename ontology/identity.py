"""Identity across sources: which records in which systems are one entity.

``knowledge_graph/resolve.py`` links records only when their key values are
identical. In the MDM world that never happens: CRM says AC-1000, ERP says
100000, billing says B-5000. Identity is resolved here from, strongest first:

1. **the MDM hub's cross-reference columns** (golden_customers.erp_no points
   at ERP customer 100000) - score 1.0;
2. **a shared tax id** - 0.98;
3. **the same normalised name in the same country** - 0.9;
4. **the same normalised name** when one side has no country and the name is
   unique on both sides - 0.8.

Clusters are built strongest evidence first, with one guard: attributes never
put two records of the same source system into one entity (two ERP customers
with similar names stay two). Two GOLDEN records landing in one entity are
the hub's own duplicates, reported with the record that should survive (the
one with more cross-references; on a tie the older id).

As in resolve.py, nothing is merged in the sources: the result is a separate
crosswalk table with a method and score on every row, reviewable and
reversible.
"""

from __future__ import annotations

import re

from knowledge_graph.build import qi
from ontology import registry as reg
from ontology.concepts import _tables, find_crosswalks

_SCHEMA = ("CREATE TABLE IF NOT EXISTS eo_crosswalk (ontology_id TEXT, concept TEXT,"
           " entity_id TEXT, table_key TEXT, record TEXT, method TEXT, score DOUBLE)")
IDENTITY_FINDINGS = ("duplicate_golden_record|",)


def _norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _columns_by_property(graph, ontology_id) -> dict:
    out: dict = {}
    for m in reg.items(graph, ontology_id, kind="mapping"):
        p = m["payload"]
        prop = p["property"]
        kind = "name" if prop.endswith("_name") else prop
        if kind in ("name", "country", "tax_id"):
            out.setdefault(p["table"], {}).setdefault(kind, p["column"])
    return out


def _load(graph, t, key, attrs) -> dict:
    cols = [qi(key)] + [qi(attrs[k]) if k in attrs else "NULL"
                        for k in ("name", "country", "tax_id")]
    out = {}
    for rec, name, country, tax in graph.sql(
            f"SELECT {', '.join(cols)} FROM {t['ref']} WHERE {qi(key)} IS NOT NULL"):
        out[str(rec)] = {"name": _norm(name), "country": _norm(country),
                         "tax": _norm(tax)}
    return out


def _resolve_concept(graph, concept: dict, tables: dict, attrs_of: dict) -> dict:
    members = [m for m in concept["members"] if m in tables and concept["keys"].get(m)]
    hub = concept.get("master")
    records = {m: _load(graph, tables[m], concept["keys"][m], attrs_of.get(m, {}))
               for m in members}
    edges = []                                     # (score, method, a, b)

    if hub:
        for w in find_crosswalks(graph, [tables[m] for m in members]):
            if w["from_table"] != hub or w["to_table"] == hub:
                continue
            col = w["from"].rsplit(".", 1)[1]
            target = w["to_table"]
            for rec, val in graph.sql(
                    f"SELECT {qi(concept['keys'][hub])}, {qi(col)} FROM {tables[hub]['ref']}"
                    f" WHERE {qi(col)} IS NOT NULL"):
                if str(val) in records[target]:
                    edges.append((1.0, "mdm_xref", (hub, str(rec)), (target, str(val))))

    plain = [m for m in members if m != hub]
    for i, a in enumerate(plain):
        for b in plain[i + 1:]:
            for field, method, score, need_country in (
                    ("tax", "tax_id", 0.98, False),
                    ("name", "name+country", 0.9, True),
                    ("name", "name", 0.8, False)):
                if method == "name" and all(
                        any(r["country"] for r in records[x].values()) for x in (a, b)):
                    continue                      # both have countries: use name+country
                index_a = _unique_index(records[a], field, need_country)
                index_b = _unique_index(records[b], field, need_country)
                for value, rec_a in index_a.items():
                    rec_b = index_b.get(value)
                    if rec_b:
                        edges.append((score, method, (a, rec_a), (b, rec_b)))

    parent: dict = {}
    tables_in: dict = {}
    method_of: dict = {}

    def root(n):
        parent.setdefault(n, n)
        tables_in.setdefault(n, {} if n[0] == hub else {n[0]: n[1]})
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    for m in members:
        for rec in records[m]:
            root((m, rec))
    for score, method, a, b in sorted(edges, key=lambda e: -e[0]):
        ra, rb = root(a), root(b)
        if ra == rb:
            continue
        clash = any(t in tables_in[rb] and tables_in[rb][t] != r
                    for t, r in tables_in[ra].items())
        if clash:
            continue
        parent[ra] = rb
        tables_in[rb].update(tables_in[ra])
        for node in (a, b):
            if node not in method_of or method_of[node][0] < score:
                method_of[node] = (score, method)

    clusters: dict = {}
    for n in list(parent):
        clusters.setdefault(root(n), []).append(n)

    xrefs = {}
    for _s, method, a, _b in edges:
        if method == "mdm_xref":
            xrefs[a] = xrefs.get(a, 0) + 1

    crosswalk, findings = [], []
    for nodes in clusters.values():
        nodes.sort()
        golden = [n for n in nodes if n[0] == hub]
        if golden:
            survivor = sorted(golden, key=lambda n: (-xrefs.get(n, 0), n[1]))[0]
            entity = survivor[1]
            for dup in golden:
                if dup == survivor:
                    continue
                findings.append({
                    "type": "duplicate_golden_record", "column": f"{hub}.{dup[1]}",
                    "duplicate": f"{hub}.{dup[1]}", "survivor": f"{hub}.{survivor[1]}",
                    "concept": concept["name"],
                    "detail": (f"golden records {dup[1]} and {survivor[1]} point at the "
                               f"same source records; keep {survivor[1]} ("
                               + (f"{xrefs.get(survivor, 0)} cross-references vs "
                                  f"{xrefs.get(dup, 0)}" if xrefs.get(survivor, 0)
                                  != xrefs.get(dup, 0) else
                                  "same cross-references; the older id survives")
                               + ")")})
        else:
            entity = f"{nodes[0][0]}:{nodes[0][1]}"
        for n in nodes:
            if golden and n == survivor:
                score, method = 1.0, "master"
            elif len(nodes) == 1:
                score, method = 1.0, "unmatched"
            else:
                score, method = method_of.get(n, (1.0, "master"))
            crosswalk.append({"entity_id": entity, "table": n[0], "record": n[1],
                              "method": method, "score": score})

    methods: dict = {}
    for row in crosswalk:
        methods[row["method"]] = methods.get(row["method"], 0) + 1
    entities = len(clusters)
    linked = sum(1 for nodes in clusters.values() if len({n[0] for n in nodes}) > 1)
    unmatched = {m: sum(1 for r in crosswalk if r["table"] == m and r["method"] == "unmatched")
                 for m in members}
    return {"crosswalk": crosswalk, "findings": findings, "entities": entities,
            "linked_entities": linked, "records": len(crosswalk), "methods": methods,
            "unmatched": unmatched, "master": hub}


def _unique_index(records: dict, field: str, need_country: bool) -> dict:
    seen: dict = {}
    for rec, attrs in records.items():
        value = attrs[field]
        if not value or (need_country and not attrs["country"]):
            continue
        k = (value, attrs["country"]) if need_country else value
        seen.setdefault(k, []).append(rec)
    return {k: v[0] for k, v in seen.items() if len(v) == 1}


def resolve_identities(layer, ontology_id: str) -> dict:
    graph = layer.graph
    onto = reg.get(graph, ontology_id)
    tables = {t["key"]: t for t in _tables(layer, onto)}
    attrs_of = _columns_by_property(graph, ontology_id)
    with graph.lock:
        graph.con.execute(_SCHEMA)
    result, all_findings = {}, []
    for item in reg.items(graph, ontology_id, kind="concept"):
        concept = item["payload"]
        if item["status"] == "rejected" or len(concept.get("members", [])) < 2:
            continue
        r = _resolve_concept(graph, concept, tables, attrs_of)
        result[concept["name"]] = r
        all_findings += r["findings"]
        with graph.lock:
            graph.con.execute("DELETE FROM eo_crosswalk WHERE ontology_id = ? AND concept = ?",
                              [ontology_id, concept["name"]])
            if r["crosswalk"]:
                graph.con.executemany(
                    "INSERT INTO eo_crosswalk VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [[ontology_id, concept["name"], row["entity_id"], row["table"],
                      row["record"], row["method"], row["score"]] for row in r["crosswalk"]])
        summary = {k: r[k] for k in ("entities", "linked_entities", "records", "methods",
                                     "unmatched", "master")}
        summary["duplicates"] = len(r["findings"])
        reg.put(graph, ontology_id, "identity", concept["name"], summary,
                confidence=0.95 if r["master"] else 0.85,
                evidence=[f"{r['records']:,} records resolved into {r['entities']:,} "
                          f"entities ({r['linked_entities']:,} seen in more than one system)",
                          "methods: " + ", ".join(f"{k} {v:,}" for k, v in
                                                  sorted(r["methods"].items()))])
    keep = set()
    for f in all_findings:
        key = f"{f['type']}|{f['column']}"
        keep.add(key)
        reg.put(graph, ontology_id, "finding", key, f, confidence=0.95,
                evidence=[f["detail"]])
    reg.prune(graph, ontology_id, "finding", keep, prefixes=IDENTITY_FINDINGS)
    return {"concepts": result, "findings": all_findings}


def resolve_entity(graph, ontology_id: str, value) -> dict | None:
    """Every record of the entity that `value` (any system's id) belongs to."""
    if not graph.one("SELECT count(*) FROM information_schema.tables"
                     " WHERE table_name = 'eo_crosswalk'"):
        return None                                  # identity has not run yet
    hit = graph.sql("SELECT concept, entity_id FROM eo_crosswalk WHERE"
                    " ontology_id = ? AND record = ? LIMIT 1", [ontology_id, str(value)])
    if not hit:
        return None
    concept, entity = hit[0]
    records: dict = {}
    methods: dict = {}
    for table, record, method, score in graph.sql(
            "SELECT table_key, record, method, score FROM eo_crosswalk WHERE"
            " ontology_id = ? AND concept = ? AND entity_id = ? ORDER BY 1, 2",
            [ontology_id, concept, entity]):
        records.setdefault(table, []).append(record)
        methods[f"{table}.{record}"] = {"method": method, "score": score}
    return {"concept": concept, "entity_id": entity, "records": records,
            "methods": methods}
