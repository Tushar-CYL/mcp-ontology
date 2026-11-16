"""The knowledge graph of an ontology: every record a node, every proven
link a connection, read live from the data.

This is a *virtual* knowledge graph (the Timbr / Stardog virtual-graph
pattern): nothing is copied into a separate graph store. The ontology says
which tables are which business things and which columns link them; this
module answers graph questions over those tables in SQL:

* overview  - how many entities and connections, and graph health in plain
              words (broken links, placeholder hubs, disconnected things);
* search    - find an entity by its id or name, in any thing;
* entity    - one entity's 360: its fields (personal data masked) and every
              connection, both directions, with counts;
* path      - how two entities are connected (shortest path, bounded);
* export    - nodes and relationships as Neo4j import CSVs.

Graph-shaped sources (RDF / triple files) are read through their entity and
triple tables (`ontology.graph_onto.graph_tables`), so the same questions work
for them.
"""

from __future__ import annotations

import csv
import re
import zipfile
from pathlib import Path

from knowledge_graph.build import qi, table_ref
from ontology import simple

SAMPLE = 8                 # connected entities listed per connection
SEARCH_LIMIT = 25
PATH_MAX_HOPS = 4
FRONTIER_CAP = 2000        # entities expanded per hop, so a hub cannot explode a search
HUB_SHARE = 0.2            # one parent holding this share of a link is a hub
HUB_MIN_CHILDREN = 50


class GraphError(ValueError):
    """A request the graph cannot answer, said in plain words."""


# ------------------------------------------------------------------ model
def _columns(graph, ref: str) -> list[str]:
    return [r[0] for r in graph.sql(f"DESCRIBE SELECT * FROM {ref}")]


def model(layer, ontology_id: str) -> dict:
    """Entity sets (one per table of a thing) and connections (one per link),
    with the SQL needed to read them."""
    graph = layer.graph
    v = simple.view(graph, ontology_id)
    sets, graphs, problems = {}, {}, []
    for t in v["things"]:
        for member in t["tables"]:
            source, _, table = member.partition(".")
            if "#" in member:
                graphs.setdefault(source, {"things": set()})["things"].add(t["name"])
                continue
            try:
                schema = layer._bundle(source).schema
            except Exception as exc:               # noqa: BLE001 - said, not hidden
                problems.append(f"{t['name']}: the data source {source!r} could not be opened ({str(exc)[:160]})")
                continue
            spec = next((x for x in schema.tables if x.name == table), None)
            if spec is None:
                problems.append(f"{t['name']}: table {table!r} is no longer in {source!r}")
                continue
            ref = table_ref(graph, schema, table, source=source)
            try:
                cols = _columns(graph, ref)
            except Exception as exc:               # noqa: BLE001 - said, not hidden
                problems.append(f"{t['name']}: table {table!r} could not be read ({str(exc)[:160]})")
                continue
            fields = [f for f in t["fields"] if f["table"] == member]
            pk = [c for c in (spec.primary_key or []) if c in cols]
            ident = [f["column"] for f in fields if f["role"] == "identifier" and f["column"] in cols]
            if pk:
                key_cols = pk                      # declared, possibly several columns
            elif "__row" in cols:
                key_cols = ["__row"]
            elif ident:
                key_cols = ident[:1]
            else:
                key_cols = []
            # The display name: a "name" field that is not personal data,
            # preferring a column literally called name / title.
            names = [f["column"] for f in fields
                     if f["role"] == "name" and f["column"] in cols and not f.get("personal")]
            name_col = next((c for c in names if c.lower() in ("name", "title", "full_name",
                                                                "display_name")),
                            names[0] if names else None)
            sets[member] = {
                "member": member, "thing": t["name"], "source": source, "table": table,
                "ref": ref, "key": "+".join(key_cols) or None, "key_cols": key_cols,
                "label": name_col, "records": None,
                "fields": [f for f in fields if f["column"] in cols],
                "personal": {f["column"]: f["personal"] for f in fields if f.get("personal")},
            }
    links = []
    for link in v["links"]:
        if not link.get("from") or not link.get("to") or "#" in link["from"]:
            continue
        child, ccol = link["from"].rsplit(".", 1)
        parent, pcol = link["to"].rsplit(".", 1)
        if child in sets and parent in sets:
            links.append({"key": link["key"], "child": child, "child_col": ccol,
                          "parent": parent, "parent_col": pcol,
                          "from_thing": link["from_thing"], "to_thing": link["to_thing"],
                          "label": link["label"], "declared": link.get("declared")})
    for source in list(graphs):
        from ontology.graph_onto import graph_tables
        try:
            q = graph_tables(layer, source)
        except KeyError:
            q = None
        if q is None:
            del graphs[source]
            continue
        graphs[source].update(q)
        graphs[source]["things"] = sorted(graphs[source]["things"])
    return {"ontology": v, "sets": sets, "links": links, "graphs": graphs, "problems": problems}


def _lit(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _k(s: dict, alias: str = "") -> str:
    """The entity id as text: one key column, or several joined by '|'."""
    a = f"{alias}." if alias else ""
    parts = [f"CAST({a}{qi(c)} AS VARCHAR)" for c in s["key_cols"]]
    return parts[0] if len(parts) == 1 else f"concat_ws('|', {', '.join(parts)})"


def _lbl(s: dict, alias: str = "") -> str:
    """The entity's display name: its name column, else its id."""
    if s["label"]:
        a = f"{alias}." if alias else ""
        return f"CAST({a}{qi(s['label'])} AS VARCHAR)"
    return _k(s, alias)


def _mask(kind: str, value):
    """Personal data is shown masked: enough to recognise, not to copy."""
    if value is None:
        return None
    text = str(value)
    if kind == "Email" and "@" in text:
        user, _, domain = text.partition("@")
        return f"{user[:1]}***@{domain}"
    if len(text) <= 4:
        return "****"
    return "*" * (len(text) - 2) + text[-2:]


# --------------------------------------------------------------- overview
def overview(layer, ontology_id: str) -> dict:
    m = model(layer, ontology_id)
    g = layer.graph
    things = {}
    for s in m["sets"].values():
        n = int(g.sql(f"SELECT count(*) FROM {s['ref']}")[0][0])
        s["records"] = n
        th = things.setdefault(s["thing"], {"thing": s["thing"], "entities": 0, "tables": []})
        th["entities"] += n
        th["tables"].append(s["member"])
    connections = []
    health = [{"severity": "warning", "kind": "unreadable", "text": text} for text in m["problems"]]
    linked_things = set()
    for link in m["links"]:
        c, p = m["sets"][link["child"]], m["sets"][link["parent"]]
        cc, pc = qi(link["child_col"]), qi(link["parent_col"])
        rows, with_value, matched = g.sql(f"""
            SELECT count(*), count(ch.{cc}),
                   count(*) FILTER (WHERE ch.{cc} IS NOT NULL AND CAST(ch.{cc} AS VARCHAR) IN
                       (SELECT CAST({pc} AS VARCHAR) FROM {p['ref']}))
            FROM {c['ref']} ch""")[0]
        parents, used = g.sql(f"""
            SELECT count(DISTINCT CAST({pc} AS VARCHAR)),
                   count(DISTINCT CAST({pc} AS VARCHAR)) FILTER (WHERE CAST({pc} AS VARCHAR) IN
                       (SELECT CAST({cc} AS VARCHAR) FROM {c['ref']}))
            FROM {p['ref']}""")[0]
        top = g.sql(f"""
            SELECT CAST({cc} AS VARCHAR) v, count(*) n FROM {c['ref']}
            WHERE {cc} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 1""")
        rows, with_value, matched = int(rows), int(with_value), int(matched)
        orphans = with_value - matched
        conn = {"key": link["key"], "label": link["label"], "from_thing": link["from_thing"],
                "to_thing": link["to_thing"], "connections": matched, "orphans": orphans,
                "missing": rows - with_value, "parents": int(parents),
                "parents_used": int(used), "declared": link["declared"]}
        if top:
            conn["busiest"] = {"key": top[0][0], "count": int(top[0][1])}
        connections.append(conn)
        linked_things.update({link["from_thing"], link["to_thing"]})
        if orphans:
            health.append({"severity": "warning", "kind": "broken_link", "link": link["key"],
                           "text": f"{orphans:,} {link['from_thing']} records point to a "
                                   f"{link['to_thing']} that does not exist"})
        if top and matched and int(top[0][1]) >= HUB_MIN_CHILDREN \
                and int(top[0][1]) / max(1, with_value) >= HUB_SHARE:
            share = int(top[0][1]) / max(1, with_value)
            health.append({"severity": "warning", "kind": "hub", "link": link["key"],
                           "entity": {"set": link["parent"], "key": top[0][0]},
                           "text": f"One {link['to_thing']} ({top[0][0]}) holds {share:.0%} of all "
                                   f"{link['from_thing']} records: check it is not a placeholder "
                                   f"such as 'unknown'"})
        unused = int(parents) - int(used)
        if parents and unused / int(parents) >= 0.5:
            health.append({"severity": "info", "kind": "unused", "link": link["key"],
                           "text": f"{unused:,} of {int(parents):,} {link['to_thing']} records have "
                                   f"no {link['from_thing']}"})
    for name in sorted(things):
        if name not in linked_things and len(things) > 1 and not m["graphs"]:
            health.append({"severity": "info", "kind": "isolated",
                           "text": f"{name} is not connected to any other thing"})
    graphs = []
    for source, q in m["graphs"].items():
        ents = int(g.sql(f"SELECT count(*) FROM ({q['entities']})")[0][0])
        trip = int(g.sql(f"SELECT count(*) FROM ({q['triples']})")[0][0])
        loose = int(g.sql(f"""
            SELECT count(*) FROM ({q['entities']}) e WHERE e.id NOT IN (SELECT h FROM ({q['triples']}))
              AND e.id NOT IN (SELECT t FROM ({q['triples']}))""")[0][0])
        hubs = [{"key": k, "label": lbl, "degree": int(d)} for k, lbl, d in g.sql(f"""
            WITH deg AS (SELECT x AS id, count(*) d FROM (SELECT h AS x FROM ({q['triples']})
                         UNION ALL SELECT t FROM ({q['triples']})) GROUP BY 1)
            SELECT deg.id, any_value(e.label), any_value(deg.d)
            FROM deg LEFT JOIN ({q['entities']}) e ON e.id = deg.id
            GROUP BY deg.id ORDER BY 3 DESC, 1 LIMIT 5""")]
        graphs.append({"source": source, "entities": ents, "connections": trip,
                       "unconnected": loose, "busiest": hubs})
        if loose:
            health.append({"severity": "info", "kind": "isolated",
                           "text": f"{loose:,} of {ents:,} entities in {source} have no connection"})
    entities = sum(t["entities"] for t in things.values()) + sum(x["entities"] for x in graphs)
    total_conn = sum(c["connections"] for c in connections) + sum(x["connections"] for x in graphs)
    broken = sum(c["orphans"] for c in connections)
    checked = total_conn + broken
    schema = [{"thing": st["thing"], "table": st["member"], "rows": st["records"],
               "key": [c for c in st["key_cols"] if c != "__row"] or None,
               "columns": [f["label"] for f in st["fields"]]}
              for st in m["sets"].values()]
    for source, q in m["graphs"].items():
        schema.append({"thing": "Entities and relations", "table": source, "rows": None,
                       "key": ["id"], "columns": ["id", "name", "type", "relation"], "graph": True})
    return {
        "ontology": {"id": m["ontology"]["id"], "name": m["ontology"]["name"],
                     "version": m["ontology"].get("version")},
        "schema": schema,
        "summary": {"entities": entities, "connections": total_conn,
                    "things": len(things) + sum(len(x["things"]) for x in m["graphs"].values()),
                    "link_types": len(connections) + sum(
                        1 for link in m["ontology"]["links"] if "#" in str(link.get("from"))),
                    "broken_links": broken,
                    "connected_pct": _share(total_conn, checked)},
        "things": sorted(things.values(), key=lambda t: -t["entities"]),
        "connections": connections, "graphs": graphs, "health": health,
    }


def _share(good: int, total: int) -> float:
    """One decimal, and never "100%" while anything is broken: 13 broken in
    672,000 rounds to 100.0 but is not 100."""
    if not total or good >= total:
        return 100.0
    return min(round(100 * good / total, 1), 99.9)


# ----------------------------------------------------------------- search
SEARCH_COLUMNS = 6         # text columns searched per table, besides the id and name


def _pattern(q: str) -> str:
    """ILIKE pattern: the text anywhere, case-insensitive, user wildcards
    escaped, and a space matching any one character, so "neural network"
    finds neural_network and neural-network too."""
    body = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return _lit("%" + body.replace(" ", "_") + "%")


def search(layer, ontology_id: str, q: str, thing: str | None = None,
           limit: int = SEARCH_LIMIT) -> dict:
    """Entities whose id, name or a plain text field (city, category ...)
    matches. Personal-data columns are never searched."""
    q = (q or "").strip()
    if not q:
        raise GraphError("type an id or a name to search for")
    m = model(layer, ontology_id)
    g = layer.graph
    pattern, exact = _pattern(q), _lit(q)
    hits = []
    # Each set gets a fair share, so a million-row table cannot crowd out the
    # customers; exact id / name matches still sort first overall.
    groups = len(m["sets"]) + len(m["graphs"])
    per_set = max(5, limit // max(1, groups))
    for s in m["sets"].values():
        if thing and s["thing"] != thing or not s["key"]:
            continue
        k, lbl = _k(s), _lbl(s)
        # Any text column except personal data: roles are not needed to find
        # "sao paulo" in a city or "GB" in a two-value country column.
        extra = [f for f in s["fields"]
                 if not f.get("personal") and f["column"] != s["label"]
                 and f["column"] not in s["key_cols"]
                 and "VARCHAR" in str(f.get("type") or "VARCHAR").upper()][:SEARCH_COLUMNS]
        where = [f"{k} = {exact}", f"{lbl} ILIKE {pattern} ESCAPE '\\'"] + [
            f"CAST({qi(f['column'])} AS VARCHAR) ILIKE {pattern} ESCAPE '\\'" for f in extra]
        matched = "CASE " + " ".join(
            f"WHEN CAST({qi(f['column'])} AS VARCHAR) ILIKE {pattern} ESCAPE '\\' "
            f"THEN {_lit(f['label'] + ': ')} || CAST({qi(f['column'])} AS VARCHAR)"
            for f in extra) + " END" if extra else "NULL"
        for key, label, why, rank in g.sql(f"""
                SELECT {k}, {lbl}, {matched},
                       CASE WHEN {k} = {exact} THEN 0
                            WHEN lower({lbl}) = lower({exact}) THEN 1
                            WHEN {lbl} ILIKE {pattern} ESCAPE '\\' THEN 2 ELSE 3 END
                FROM {s['ref']}
                WHERE {' OR '.join(where)}
                ORDER BY 4, 2 LIMIT {int(per_set)}"""):
            hit = {"set": s["member"], "thing": s["thing"], "key": key,
                   "label": _display(s, key, label), "rank": rank}
            if rank == 3 and why:
                hit["matched"] = why
            hits.append(hit)
    for source, gq in m["graphs"].items():
        if thing and thing not in gq["things"]:
            continue
        for key, label, typ, rank in g.sql(f"""
                SELECT id, label, type,
                       CASE WHEN id = {exact} THEN 0 WHEN lower(label) = lower({exact}) THEN 1 ELSE 2 END
                FROM ({gq['entities']})
                WHERE id = {exact} OR label ILIKE {pattern} ESCAPE '\\'
                ORDER BY 4, length(label), 2 LIMIT {int(max(per_set, limit // 2))}"""):
            hits.append({"set": f"graph:{source}", "thing": typ or "Entity", "key": key,
                         "label": label or key, "rank": rank})
    # Best matches first; within a rank, take each kind of thing in turn so
    # one big table cannot fill the list.
    by_rank: dict = {}
    for h in hits:
        by_rank.setdefault(h["rank"], {}).setdefault(h["set"], []).append(h)
    ordered = []
    for rank in sorted(by_rank):
        queues = [sorted(v, key=lambda h: (len(str(h["label"])), str(h["label"])))
                  for _, v in sorted(by_rank[rank].items())]
        while any(queues):
            for qu in queues:
                if qu:
                    ordered.append(qu.pop(0))
    for h in ordered:
        h.pop("rank")
    return {"query": q, "results": ordered[:limit]}


def _shown(s: dict, column: str | None, value):
    kind = s["personal"].get(column) if column else None
    return _mask(kind, value) if kind else value


def _display(s: dict, key, name):
    """What a person sees for one record: its name, or - for a table with no
    name column - the thing and a short id ("Zip Code Geolocation 10",
    "Customer 06b8999e...") rather than a bare row number or hash."""
    if s["label"]:
        return _shown(s, s["label"], name)
    k = str(key)
    return f"{s['thing']} {k if len(k) <= 12 else k[:8] + '...'}"


# ----------------------------------------------------------------- entity
def entity(layer, ontology_id: str, set_name: str, key: str, sample: int = SAMPLE) -> dict:
    m = model(layer, ontology_id)
    if set_name.startswith("graph:"):
        return _graph_entity(layer, m, set_name.split(":", 1)[1], key, sample)
    s = m["sets"].get(set_name)
    if s is None or not s["key"]:
        raise GraphError(f"{set_name} is not part of this ontology")
    g = layer.graph
    cols, rows = g.query_with_columns(
        f"SELECT * FROM {s['ref']} WHERE {_k(s)} = {_lit(key)} LIMIT 1")
    if not rows:
        raise GraphError(f"no {s['thing']} with id {key}")
    row = dict(zip(cols, rows[0]))
    by_col = {f["column"]: f for f in s["fields"]}
    fields = []
    for c in cols:
        if c.startswith("__"):
            continue
        f = by_col.get(c, {})
        value = row[c]
        kind = s["personal"].get(c)
        fields.append({"column": c, "label": f.get("label") or c, "role": f.get("role"),
                       "unit": f.get("unit"), "personal": kind,
                       "value": _mask(kind, value) if kind else _plain(value)})
    connections = []
    for link in m["links"]:
        if link["child"] == set_name:            # this record points at its parent
            p = m["sets"][link["parent"]]
            value = row.get(link["child_col"])
            items = []
            if value is not None:
                items = _items(g, p, f"CAST({qi(link['parent_col'])} AS VARCHAR) = {_lit(value)}", 1)
            connections.append({"link": link["key"], "direction": "out",
                                "text": f"Belongs to {link['to_thing']}",
                                "thing": link["to_thing"], "set": link["parent"],
                                "count": len(items), "items": items,
                                "broken": value is not None and not items, "value": _plain(value)})
        if link["parent"] == set_name:           # records that point at this one
            c = m["sets"][link["child"]]
            value = row.get(link["parent_col"])
            if value is None:
                continue
            where = f"CAST({qi(link['child_col'])} AS VARCHAR) = {_lit(value)}"
            n = int(g.sql(f"SELECT count(*) FROM {c['ref']} WHERE {where}")[0][0])
            connections.append({"link": link["key"], "direction": "in",
                                "text": f"{link['from_thing']} records linked to it",
                                "thing": link["from_thing"], "set": link["child"], "count": n,
                                "items": _items(g, c, where, sample) if n else []})
    return {"set": set_name, "thing": s["thing"], "key": key,
            "label": _display(s, key, row.get(s["label"]) if s["label"] else None),
            "fields": fields, "connections": connections}


def _plain(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _items(g, s: dict, where: str, limit: int) -> list[dict]:
    if not s["key"]:
        return []
    return [{"set": s["member"], "key": key, "label": _display(s, key, label)}
            for key, label in g.sql(
                f"SELECT {_k(s)}, {_lbl(s)} FROM {s['ref']}"
                f" WHERE {where} ORDER BY 1 LIMIT {int(limit)}")]


_REL_LABELS: dict = {}


def _rel_labels(g, q: dict) -> dict:
    """Every relation's label in the data ("P40" is labelled "locatedIn"),
    found in one pass and cached until the triples change. A relation stored
    by local name can clash with an entity (entity/P40), so only an id that is
    never a subject or object counts - the rule ontology.graph_onto.analyse uses.
    A CSKG-style source names its relations already: nothing to look up."""
    if "_labels" in q:
        return q["_labels"]
    if q.get("kind") == "triples":
        q["_labels"] = {}
        return q["_labels"]
    size = int(g.sql(f"SELECT count(*) FROM ({q['triples']})")[0][0])
    ck = (id(g.con), q["triples"], size)
    if ck not in _REL_LABELS:
        rows = g.sql(f"""
            WITH rels AS (SELECT DISTINCT rel FROM ({q['triples']})),
                 ends AS (SELECT h AS id FROM ({q['triples']}) UNION SELECT t FROM ({q['triples']})),
                 cand AS (SELECT e.id, e.label, regexp_extract(e.id, '([^/#:]+)$', 1) AS loc
                          FROM ({q['entities']}) e
                          WHERE e.label IS NOT NULL AND e.label <> ''
                            AND (e.id IN (SELECT rel FROM rels)
                                 OR regexp_extract(e.id, '([^/#:]+)$', 1) IN (SELECT rel FROM rels))
                            AND e.id NOT IN (SELECT id FROM ends))
            SELECT rels.rel, min(cand.label) FROM rels
            JOIN cand ON cand.id = rels.rel OR cand.loc = rels.rel
            GROUP BY 1""")
        if len(_REL_LABELS) > 32:
            _REL_LABELS.clear()
        _REL_LABELS[ck] = {r: lbl for r, lbl in rows}
    q["_labels"] = _REL_LABELS[ck]
    return q["_labels"]


def _rel_label(g, rel: str, q: dict) -> str:
    """A relation in words: its label in the data, else its local name."""
    from ontology.graph_onto import humanize, local
    return humanize(_rel_labels(g, q).get(rel) or local(rel))


def _graph_entity(layer, m: dict, source: str, key: str, sample: int) -> dict:
    q = m["graphs"].get(source)
    if q is None:
        raise GraphError(f"{source} is not part of this ontology")
    g = layer.graph
    found = g.sql(f"SELECT id, label, type FROM ({q['entities']}) WHERE id = {_lit(key)} LIMIT 1")
    if not found:
        raise GraphError(f"no entity with id {key}")
    _, label, typ = found[0]
    k = _lit(key)
    # One pass over the triples: this entity's links, counted per relation and
    # direction, with the first few of each named.
    rows = g.sql(f"""
        WITH mine AS (
            SELECT CASE WHEN h = {k} THEN 'out' ELSE 'in' END AS dir, rel,
                   CASE WHEN h = {k} THEN t ELSE h END AS other
            FROM ({q['triples']}) WHERE h = {k} OR t = {k}),
        counted AS (
            SELECT dir, rel, other, count(*) OVER (PARTITION BY dir, rel) AS n,
                   row_number() OVER (PARTITION BY dir, rel ORDER BY other) AS rk
            FROM mine)
        SELECT dir, rel, n, other FROM counted WHERE rk <= {int(sample)}
        ORDER BY dir DESC, n DESC, rel, other""")
    others = sorted({r[3] for r in rows})
    names = {}
    if others:
        names = {i: lbl for i, lbl in g.sql(
            f"SELECT id, any_value(label) FROM ({q['entities']}) WHERE id IN"
            f" ({', '.join(_lit(o) for o in others)}) GROUP BY 1")}
    groups: dict = {}
    for direction, rel, n, other in rows:
        grp = groups.setdefault((direction, rel), {"count": int(n), "items": []})
        grp["items"].append({"set": f"graph:{source}", "key": other, "label": names.get(other) or other})
    connections = []
    for (direction, rel), grp in list(groups.items())[:60]:
        verb = _rel_label(g, rel, q)
        connections.append({"link": rel, "direction": direction,
                            "text": verb if direction == "out" else f"{verb} (pointing here)",
                            "thing": None, "set": f"graph:{source}", "count": grp["count"],
                            "items": grp["items"]})
    return {"set": f"graph:{source}", "thing": typ or "Entity", "key": key,
            "label": label or key,
            "fields": [{"column": "id", "label": "Id", "role": "identifier", "unit": None,
                        "personal": None, "value": key},
                       {"column": "label", "label": "Name", "role": "name", "unit": None,
                        "personal": None, "value": label}],
            "connections": connections}


# ------------------------------------------------------------------- path
def path(layer, ontology_id: str, a: tuple[str, str], b: tuple[str, str],
         max_hops: int = PATH_MAX_HOPS) -> dict:
    """Shortest chain of proven links between two entities (either direction
    along each link). Searches from both ends and meets in the middle, always
    growing the smaller side, so a busy entity on one end cannot hide the path;
    each step is bounded by FRONTIER_CAP."""
    m = model(layer, ontology_id)
    g = layer.graph
    max_hops = max(1, min(int(max_hops), 6))
    start, goal = (a[0], str(a[1])), (b[0], str(b[1]))
    for node in (start, goal):
        if not (node[0] in m["sets"] or node[0].startswith("graph:")):
            raise GraphError(f"{node[0]} is not part of this ontology")
    # prev[side][node] = (node one step nearer that side's end,
    #                     link read from that node to this one, and back)
    prev = {0: {start: None}, 1: {goal: None}}
    frontier = {0: [start], 1: [goal]}
    meet = start if start == goal else None
    hops = 0
    while meet is None and hops < max_hops and frontier[0] and frontier[1]:
        side = 0 if len(frontier[0]) <= len(frontier[1]) else 1
        hops += 1
        nxt = []
        by_set: dict = {}
        for node in frontier[side][:FRONTIER_CAP]:
            by_set.setdefault(node[0], []).append(node[1])
        for set_name, keys in by_set.items():
            for neighbour, via in _neighbours(g, m, set_name, keys):
                if neighbour in prev[side]:
                    continue
                prev[side][neighbour] = via
                nxt.append(neighbour)
                if neighbour in prev[1 - side]:
                    meet = neighbour
                    break
            if meet is not None:
                break
        frontier[side] = nxt
    if meet is None:
        return {"found": False, "hops_searched": hops,
                "text": f"No connection within {max_hops} steps"}
    # start ... meet, then meet ... goal
    left, node = [], meet
    while node is not None:
        step = prev[0][node]
        left.append((node, step[1] if step else None))      # read start -> meet
        node = step[0] if step else None
    left.reverse()                      # [(start, None), ..., (meet, via)]
    chain = list(left)
    node = meet
    while prev[1][node] is not None:
        nearer, _forward, backward = prev[1][node]
        chain.append((nearer, backward))                     # read meet -> goal
        node = nearer
    steps = []
    for i, ((set_name, key), via) in enumerate(chain):
        steps.append({"set": set_name, "key": key, "thing": _thing_of(m, set_name, g, key),
                      "label": _label_of(m, g, set_name, key), "via": via if i else None})
    return {"found": True, "hops": len(steps) - 1, "steps": steps}


def _neighbours(g, m: dict, set_name: str, keys: list[str]):
    """(neighbour, (from node, link read from -> neighbour, link read back))
    for a batch of keys."""
    keys_sql = ", ".join(_lit(k) for k in keys)
    if set_name.startswith("graph:"):
        q = m["graphs"][set_name.split(":", 1)[1]]
        mine = set(keys)
        for h, rel, t in g.sql(f"""
                SELECT h, rel, t FROM ({q['triples']})
                WHERE h IN ({keys_sql}) OR t IN ({keys_sql}) LIMIT {FRONTIER_CAP * 4}"""):
            if _is_type_relation(g, rel, q):
                continue                       # "is a person": everyone meets there
            verb = _rel_label(g, rel, q)
            if h in mine:                 # here --verb--> there
                yield (set_name, t), ((set_name, h), verb, f"{verb} (reversed)")
            else:                         # there --verb--> here
                yield (set_name, h), ((set_name, t), f"{verb} (reversed)", verb)
        return
    s = m["sets"][set_name]
    for link in m["links"]:
        if link["child"] == set_name:
            p = m["sets"][link["parent"]]
            for mine, theirs in g.sql(f"""
                    SELECT {_k(s, 'c')}, {_k(p, 'p')}
                    FROM {s['ref']} c JOIN {p['ref']} p
                      ON CAST(c.{qi(link['child_col'])} AS VARCHAR) = CAST(p.{qi(link['parent_col'])} AS VARCHAR)
                    WHERE {_k(s, 'c')} IN ({keys_sql}) LIMIT {FRONTIER_CAP}"""):
                yield (link["parent"], theirs), ((set_name, mine), f"belongs to {link['to_thing']}",
                                                 f"has {link['from_thing']}")
        if link["parent"] == set_name:
            c = m["sets"][link["child"]]
            if not c["key"]:
                continue
            for mine, theirs in g.sql(f"""
                    SELECT {_k(s, 'p')}, {_k(c, 'c')}
                    FROM {s['ref']} p JOIN {c['ref']} c
                      ON CAST(c.{qi(link['child_col'])} AS VARCHAR) = CAST(p.{qi(link['parent_col'])} AS VARCHAR)
                    WHERE {_k(s, 'p')} IN ({keys_sql}) LIMIT {FRONTIER_CAP}"""):
                yield (link["child"], theirs), ((set_name, mine), f"has {link['from_thing']}",
                                                f"belongs to {link['to_thing']}")


def _is_type_relation(g, rel: str, q: dict) -> bool:
    """instanceOf / rdf:type style links, by their id or their label."""
    from ontology.graph_onto import INSTANCE_OF, _norm, local
    return _norm(local(rel)) in INSTANCE_OF or _norm(_rel_label(g, rel, q)) in INSTANCE_OF


def _thing_of(m, set_name, g, key):
    if set_name in m["sets"]:
        return m["sets"][set_name]["thing"]
    q = m["graphs"][set_name.split(":", 1)[1]]
    row = g.sql(f"SELECT type FROM ({q['entities']}) WHERE id = {_lit(key)} LIMIT 1")
    return (row[0][0] if row and row[0][0] else "Entity")


def _label_of(m, g, set_name, key):
    if set_name in m["sets"]:
        s = m["sets"][set_name]
        row = g.sql(f"SELECT {_lbl(s)} FROM {s['ref']} WHERE {_k(s)} = {_lit(key)} LIMIT 1")
        if not row:
            return key
        return _display(s, key, row[0][0])
    q = m["graphs"][set_name.split(":", 1)[1]]
    row = g.sql(f"SELECT label FROM ({q['entities']}) WHERE id = {_lit(key)} LIMIT 1")
    return (row[0][0] if row and row[0][0] else key)


# ----------------------------------------------------------------- export
def _neo_label(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", name.title()) or "Entity"


def _neo_type(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_") or "LINKED_TO"


def export_neo4j(layer, ontology_id: str, folder: Path) -> Path:
    """Neo4j `neo4j-admin database import` CSVs (one file per thing and per
    link) plus a README with the command. Personal-data columns are left
    out. Returns the zip path."""
    m = model(layer, ontology_id)
    g = layer.graph
    folder.mkdir(parents=True, exist_ok=True)
    files, nodes_args, rels_args = [], [], []
    for s in m["sets"].values():
        if not s["key"]:
            continue
        label = _neo_label(s["thing"])
        space = f"{label}_{re.sub(r'[^A-Za-z0-9]', '_', s['member'])}"
        cols = [f["column"] for f in s["fields"] if not f.get("personal")]
        name = f"nodes_{re.sub(r'[^A-Za-z0-9]', '_', s['member'])}.csv"
        header = [f"id:ID({space})"] + cols + [":LABEL"]
        select = ", ".join([_k(s)] + [qi(c) for c in cols] + [_lit(label)])
        _copy(g, f"SELECT {select} FROM {s['ref']} WHERE {_k(s)} IS NOT NULL",
              header, folder / name)
        files.append(name)
        nodes_args.append(f"--nodes={label}=import/{name}")
        s["space"] = space
    for link in m["links"]:
        c, p = m["sets"][link["child"]], m["sets"][link["parent"]]
        if not c["key"] or not p["key"]:
            continue
        rtype = _neo_type(f"{link['from_thing']} to {link['to_thing']}")
        name = f"rels_{re.sub(r'[^A-Za-z0-9]', '_', link['key'])[:80]}.csv"
        header = [f":START_ID({c['space']})", f":END_ID({p['space']})", ":TYPE"]
        _copy(g, f"""SELECT {_k(c, 'c')}, {_k(p, 'p')}, {_lit(rtype)}
                     FROM {c['ref']} c JOIN {p['ref']} p
                       ON CAST(c.{qi(link['child_col'])} AS VARCHAR) = CAST(p.{qi(link['parent_col'])} AS VARCHAR)""",
              header, folder / name)
        files.append(name)
        rels_args.append(f"--relationships=import/{name}")
    for source, q in m["graphs"].items():
        name = f"nodes_{source}.csv"
        _copy(g, f"SELECT id, label, coalesce(nullif(type, ''), 'Entity') FROM ({q['entities']})",
              [f"id:ID({source})", "name", ":LABEL"], folder / name)
        files.append(name)
        nodes_args.append(f"--nodes=import/{name}")
        rname = f"rels_{source}.csv"
        _copy(g, f"SELECT h, t, upper(regexp_replace(regexp_extract(rel, '([^/#:]+)$', 1),"
                 f" '[^A-Za-z0-9]+', '_', 'g')) FROM ({q['triples']})",
              [f":START_ID({source})", f":END_ID({source})", ":TYPE"], folder / rname)
        files.append(rname)
        rels_args.append(f"--relationships=import/{rname}")
    readme = (
        f"Knowledge graph of the ontology \"{m['ontology']['name']}\" for Neo4j.\n\n"
        "Copy the CSV files into your Neo4j import folder, stop the database, then run:\n\n"
        "  neo4j-admin database import full neo4j \\\n    "
        + " \\\n    ".join(nodes_args + rels_args) + "\n\n"
        "Personal-data columns are not included. Ids are the source keys as text.\n")
    (folder / "README.txt").write_text(readme, encoding="utf-8")
    files.append("README.txt")
    out = folder.with_suffix(".zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in files:
            z.write(folder / name, name)
    return out


def _copy(g, select: str, header: list[str], dest: Path) -> None:
    """Stream a query to CSV with the given header (DuckDB COPY, no Python rows)."""
    tmp = dest.with_suffix(".body.csv")
    g.con.execute(f"COPY ({select}) TO '{tmp.as_posix()}' (HEADER false, DELIMITER ',', QUOTE '\"')")
    with open(dest, "w", encoding="utf-8", newline="") as out:
        csv.writer(out).writerow(header)
        with open(tmp, encoding="utf-8") as body:
            for chunk in iter(lambda: body.read(1 << 20), ""):
                out.write(chunk)
    tmp.unlink()


# ------------------------------------------------------- the graph picture
SAMPLE_SEEDS = 5          # records the first picture starts from
SAMPLE_PER_SEED = 8       # neighbours drawn per starting record
EXPAND_LIMIT = 15         # neighbours added when a person expands a record


def _node(m: dict, g, set_name: str, key: str) -> dict:
    return {"id": f"{set_name}|{key}", "set": set_name, "key": key,
            "thing": _thing_of(m, set_name, g, key), "label": _label_of(m, g, set_name, key)}


def _around(g, m: dict, set_name: str, key: str, limit: int, nodes: dict, edges: dict) -> None:
    """Add one record and up to `limit` of its neighbours to the picture."""
    me = f"{set_name}|{key}"
    if me not in nodes:
        nodes[me] = _node(m, g, set_name, key)
    added = 0
    for (nset, nkey), (_frm, forward, _back) in _neighbours(g, m, set_name, [key]):
        if added >= limit:
            break
        other = f"{nset}|{nkey}"
        if other == me:
            continue
        if other not in nodes:
            nodes[other] = _node(m, g, nset, nkey)
            added += 1
        eid = "--".join(sorted((me, other)))
        edges.setdefault(eid, {"id": eid, "source": me, "target": other, "label": forward})


def sample(layer, ontology_id: str, seeds: int = SAMPLE_SEEDS,
           per_seed: int = SAMPLE_PER_SEED) -> dict:
    """A first picture of the graph: a few real records from the most
    connected thing, and what each is connected to."""
    m = model(layer, ontology_id)
    g = layer.graph
    nodes: dict = {}
    edges: dict = {}
    if m["sets"]:
        degree: dict = {}
        for link in m["links"]:
            degree[link["child"]] = degree.get(link["child"], 0) + 1
            degree[link["parent"]] = degree.get(link["parent"], 0) + 1
        keyed = [x for x in m["sets"].values() if x["key"]]
        if keyed:
            seed = max(keyed, key=lambda x: (degree.get(x["member"], 0), -len(x["member"])))
            for (key,) in g.sql(f"SELECT {_k(seed)} FROM {seed['ref']} WHERE {_k(seed)} IS NOT NULL"
                                f" ORDER BY 1 LIMIT {int(seeds)}"):
                _around(g, m, seed["member"], key, per_seed, nodes, edges)
    for source, q in m["graphs"].items():
        # Start from well-connected entities, skipping type nodes ("person").
        for (key,) in g.sql(f"""
                SELECT h FROM ({q['triples']}) GROUP BY h ORDER BY count(*) DESC, h
                LIMIT {int(seeds)}"""):
            _around(g, m, f"graph:{source}", key, per_seed, nodes, edges)
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


def expand(layer, ontology_id: str, set_name: str, key: str, limit: int = EXPAND_LIMIT) -> dict:
    """One record and its neighbours, to add to the picture."""
    m = model(layer, ontology_id)
    if not (set_name in m["sets"] or set_name.startswith("graph:")):
        raise GraphError(f"{set_name} is not part of this ontology")
    nodes: dict = {}
    edges: dict = {}
    _around(layer.graph, m, set_name, str(key), max(1, min(int(limit), 50)), nodes, edges)
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}

