"""The ontology of a knowledge graph (triples), not of tables.

A triple source (a CSKG folder: entities + relations + triples, or an RDF
file) has one physical table of entities with two columns, id and label.
Treating that as "one thing with two fields" misses the whole ontology, which
lives in the relations. This module derives it from the data:

* **Types (things).** In order of strength:
  1. explicit types (an RDF ``rdf:type`` column) when most entities have one;
  2. types named in the relations: ``usesMethod``, ``solvesTask``,
     ``affectsMetric`` are a verb plus the type of their object, so the
     object of ``usesMethod`` is a Method. An entity's type is the type it is
     most often the object of; the share that agrees is its purity;
  3. otherwise one type, Entity.
* **Links.** Each relation becomes a link between the type most of its
  subjects have and the type most of its objects have, with the counts as
  proof ("94% of subjects are Methods").
* **Hierarchy.** ``skos:broader`` / ``subClassOf`` / ``isA`` become "is a kind
  of" links, not ordinary relations.

Everything is written as the same registry items the table flow writes
(concept, member, meaning, relationship), so the screen, Excel export and MCP
tools need no special case.
"""

from __future__ import annotations

import json
import re
import uuid

from knowledge_graph.build import table_ref
from ontology import meaning as mn
from ontology import registry as reg

HIERARCHY = {"broader": False, "subclassof": False, "isa": False, "is_a": False,
             "parent": False, "kindof": False, "narrower": True, "subclass": True}
TYPE_SUFFIX = re.compile(r"^([a-z][a-z\-_]*?)[\-_]?([A-Z][A-Za-z0-9]*)$")
# A trailing preposition is not a type: locatedIn, bornIn, partOf, notableFor.
PREPOSITIONS = {"in", "of", "for", "by", "at", "with", "on", "to", "from", "as", "into",
                "about", "under", "over"}
# Relations that give an entity its type ("E0 instanceOf C0").
INSTANCE_OF = {"instanceof", "isinstanceof", "typeof", "type", "rdftype", "isa_instance",
               "classifiedas", "category", "hascategory", "kind"}
TOP_TYPES = 25
MAX_LINKS = 200
MIN_TYPED_SHARE = 0.5          # share of relations that must carry a type suffix
SAMPLES = 8


def local(name: str) -> str:
    """'http://x/ns#usesMethod' -> 'usesMethod'; 'skos:broader' -> 'broader'."""
    text = str(name or "")
    text = re.split(r"[#/]", text)[-1] or text
    return text.split(":")[-1]


def split_relation(name: str) -> tuple[str, str | None]:
    """'based-onMethod' -> ('based on', 'Method'); 'usesOtherEntity' ->
    ('uses', 'OtherEntity'); 'related' -> ('related', None)."""
    m = TYPE_SUFFIX.match(local(name))
    if not m:
        return local(name).replace("-", " ").replace("_", " "), None
    return m.group(1).replace("-", " ").replace("_", " ").strip(), m.group(2)


def humanize(name: str) -> str:
    """'locatedIn' -> 'located in'; 'notable_for' -> 'notable for'."""
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", local(name))
    return re.sub(r"[\-_\s]+", " ", text).strip().lower()


def hierarchy_kind(name: str) -> bool | None:
    """None when not a hierarchy relation; False when the subject is the
    narrower thing (broader, subClassOf); True when reversed (narrower)."""
    key = re.sub(r"[^a-z_]", "", local(name).lower())
    return HIERARCHY.get(key)


# ------------------------------------------------------------- detection
def graph_tables(layer, source: str) -> dict | None:
    """SQL for entities (id, label[, type]) and triples (h, rel, t) of a
    triple source, or None for an ordinary tabular source."""
    bundle = layer._bundle(source)
    schema = bundle.schema
    g = layer.graph
    names = {t.name: t for t in schema.tables}
    if schema.triples:
        tr = schema.triples
        ent = table_ref(g, schema, tr["entities"], source)
        rel = table_ref(g, schema, tr["relations"], source)
        tri = table_ref(g, schema, tr["triples"], source)
        return {
            "kind": "triples", "entity_table": f"{source}.{tr['entities']}",
            "entities": f"SELECT CAST(id AS VARCHAR) AS id, CAST(label AS VARCHAR) AS label,"
                        f" NULL::VARCHAR AS type FROM {ent}",
            "triples": f"SELECT CAST(t.head AS VARCHAR) AS h, CAST(r.name AS VARCHAR) AS rel,"
                       f" CAST(t.tail AS VARCHAR) AS t FROM {tri} t JOIN {rel} r"
                       f" ON CAST(r.id AS VARCHAR) = CAST(t.relation AS VARCHAR)"}
    ent = next((t for t in names.values()
                if {"id", "label", "type"} <= {c.name for c in t.columns}), None)
    lnk = next((t for t in names.values()
                if {"source", "predicate", "target"} <= {c.name for c in t.columns}), None)
    if ent is None or lnk is None:
        return None
    e, k = table_ref(g, schema, ent.name, source), table_ref(g, schema, lnk.name, source)
    return {"kind": "rdf", "entity_table": f"{source}.{ent.name}",
            "entities": f"SELECT CAST(id AS VARCHAR) AS id, CAST(label AS VARCHAR) AS label,"
                        f" CAST(type AS VARCHAR) AS type FROM {e}",
            "triples": f"SELECT CAST(source AS VARCHAR) AS h, CAST(predicate AS VARCHAR) AS rel,"
                       f" CAST(target AS VARCHAR) AS t FROM {k}"}


def is_graph_source(layer, source: str) -> bool:
    try:
        return graph_tables(layer, source) is not None
    except KeyError:
        return False


# --------------------------------------------------------------- analysis
def analyse(layer, source: str) -> dict:
    """Types, links and hierarchy of one triple source, measured in SQL."""
    g = layer.graph
    q = graph_tables(layer, source)
    rels = [{"name": r[0], "triples": int(r[1]), "heads": int(r[2]), "tails": int(r[3])}
            for r in g.sql(f"SELECT rel, count(*), count(DISTINCT h), count(DISTINCT t)"
                           f" FROM ({q['triples']}) GROUP BY 1 ORDER BY 2 DESC")]
    total_entities = int(g.sql(f"SELECT count(*) FROM ({q['entities']})")[0][0])
    # A relation may carry its own readable name in the data
    # (<prop/P40> rdfs:label "locatedIn"): use it instead of the id.
    labels = {}
    if rels:
        ids = ", ".join("'" + r["name"].replace("'", "''") + "'" for r in rels)
        # The relation may be stored by its full IRI or by its local name
        # ("P40"); a local name can clash with an ordinary entity (entity/P40),
        # so only an IRI that is never itself a subject or object counts.
        labels = {str(i): str(lbl) for i, lbl in g.sql(f"""
            SELECT coalesce(CASE WHEN e.id IN ({ids}) THEN e.id END,
                            regexp_extract(e.id, '([^/#:]+)$', 1)) AS rel, min(e.label)
            FROM ({q['entities']}) e
            WHERE (e.id IN ({ids}) OR regexp_extract(e.id, '([^/#:]+)$', 1) IN ({ids}))
              AND e.label IS NOT NULL AND e.label <> ''
              AND e.id NOT IN (SELECT h FROM ({q['triples']}))
              AND e.id NOT IN (SELECT t FROM ({q['triples']}))
            GROUP BY 1""")}
    for r in rels:
        r["label"] = labels.get(r["name"]) or local(r["name"])
        r["verb"], r["type"] = split_relation(r["label"])
        if r["type"] and r["type"].lower() in PREPOSITIONS:    # locatedIn: no type "In"
            r["verb"], r["type"] = humanize(r["label"]), None
        r["hierarchy"] = hierarchy_kind(r["label"])
        r["instance"] = _norm(r["label"]) in INSTANCE_OF
    plain = [r for r in rels if r["hierarchy"] is None and not r["instance"]]
    typed_rels = [r for r in plain if r["type"]]
    instance_rels = [r["name"] for r in rels if r["instance"]]

    explicit = int(g.sql(f"SELECT count(*) FROM ({q['entities']}) WHERE type IS NOT NULL"
                         f" AND type <> ''")[0][0])
    instance_targets = 0
    if total_entities and explicit / total_entities >= 0.5:
        method = "explicit"
        type_sql = (f"SELECT id, type AS tp, 1.0 AS purity FROM ({q['entities']})"
                    f" WHERE type IS NOT NULL AND type <> ''")
    elif instance_rels:
        # "E0 instanceOf C0" and C0 is labelled "person": E0 is a Person. The
        # TOP_TYPES most common concepts become things; the rest are Other.
        method = "instance_of"
        names = ", ".join("'" + x.replace("'", "''") + "'" for x in instance_rels)
        instance_targets = int(g.sql(
            f"SELECT count(DISTINCT t) FROM ({q['triples']}) WHERE rel IN ({names})")[0][0])
        type_sql = f"""
            WITH votes AS (
              SELECT r.h AS id, coalesce(nullif(e.label, ''), r.t) AS tp, count(*) AS n
              FROM ({q['triples']}) r LEFT JOIN ({q['entities']}) e ON e.id = r.t
              WHERE r.rel IN ({names}) GROUP BY 1, 2),
            top AS (SELECT tp FROM votes GROUP BY tp ORDER BY count(*) DESC LIMIT {TOP_TYPES}),
            ranked AS (
              SELECT id, CASE WHEN tp IN (SELECT tp FROM top) THEN tp ELSE 'Other' END AS tp,
                     n, sum(n) OVER (PARTITION BY id) AS total,
                     row_number() OVER (PARTITION BY id ORDER BY (tp IN (SELECT tp FROM top)) DESC,
                                        n DESC, tp) AS rk
              FROM votes)
            SELECT id, tp, n / total AS purity FROM ranked WHERE rk = 1"""
    elif plain and len(typed_rels) / len(plain) >= MIN_TYPED_SHARE:
        method = "relation_names"
        cases = " ".join(f"WHEN '{r['name'].replace(chr(39), chr(39) * 2)}' THEN "
                         f"'{r['type']}'" for r in typed_rels)
        type_sql = f"""
            WITH votes AS (
              SELECT t AS id, CASE rel {cases} END AS tp, count(*) AS n
              FROM ({q['triples']}) GROUP BY 1, 2 HAVING tp IS NOT NULL),
            ranked AS (
              SELECT id, tp, n, sum(n) OVER (PARTITION BY id) AS total,
                     row_number() OVER (PARTITION BY id ORDER BY n DESC, tp) AS rk
              FROM votes)
            SELECT id, tp, n / total AS purity FROM ranked WHERE rk = 1"""
    else:
        method = "single"
        type_sql = f"SELECT id, 'Entity' AS tp, 1.0 AS purity FROM ({q['entities']})"

    tmp = f"_kg_types_{uuid.uuid4().hex[:10]}"
    g.sql(f"CREATE OR REPLACE TEMP TABLE {tmp} AS " + type_sql)
    inherited = 0
    broader = [r["name"] for r in rels if r["hierarchy"] is False]
    narrower = [r["name"] for r in rels if r["hierarchy"] is True]
    if method == "relation_names" and (broader or narrower):
        # A thing with no typed relation inherits the type of what it is a kind
        # of: "cnn is a kind of classification_algorithm" makes cnn a Method.
        def names(xs):
            return ", ".join("'" + x.replace("'", "''") + "'" for x in xs) or "NULL"
        edges = (f"SELECT h AS child, t AS parent FROM ({q['triples']}) WHERE rel IN ({names(broader)})"
                 f" UNION ALL SELECT t AS child, h AS parent FROM ({q['triples']})"
                 f" WHERE rel IN ({names(narrower)})")
        for _ in range(4):
            added = g.sql(f"""
                INSERT INTO {tmp}
                SELECT child, arg_max(tp, n), 1.0 FROM (
                  SELECT e.child, p.tp, count(*) AS n FROM ({edges}) e
                  JOIN {tmp} p ON p.id = e.parent
                  WHERE e.child NOT IN (SELECT id FROM {tmp})
                  GROUP BY 1, 2) GROUP BY 1""")
            step = int(added[0][0]) if added else 0
            inherited += step
            if not step:
                break
    types = {}
    for tp, n, purity in g.sql(f"SELECT tp, count(*), avg(purity) FROM {tmp} GROUP BY 1"):
        types[local(tp)] = {"type": local(tp), "raw": tp, "entities": int(n),
                            "purity": round(float(purity or 0), 4)}
    # The concepts that instanceOf points at are the types themselves, not
    # untyped things.
    # Rows that only define a relation (prop/P40 "locatedIn") are not things either.
    untyped = (total_entities - sum(t["entities"] for t in types.values()) - instance_targets
               - len(labels))
    if untyped > 0 and method != "single":
        types["Unclassified"] = {"type": "Unclassified", "raw": None, "entities": untyped,
                                 "purity": 1.0}
    for t in types.values():
        cond = "x.tp IS NULL" if t["raw"] is None else \
            f"x.tp = '{str(t['raw']).replace(chr(39), chr(39) * 2)}'"
        t["samples"] = [str(r[0]) for r in g.sql(
            f"SELECT e.label FROM ({q['entities']}) e LEFT JOIN {tmp} x ON x.id = e.id"
            f" WHERE {cond} AND e.label IS NOT NULL LIMIT {SAMPLES}")]

    # Domain and range of every relation: the majority type of its ends.
    ends = g.sql(f"""
        SELECT r.rel, coalesce(hx.tp, 'Unclassified'), coalesce(tx.tp, 'Unclassified'), count(*)
        FROM ({q['triples']}) r
        LEFT JOIN {tmp} hx ON hx.id = r.h LEFT JOIN {tmp} tx ON tx.id = r.t
        GROUP BY 1, 2, 3""")
    by_rel: dict = {}
    for rel, ht, tt, n in ends:
        e = by_rel.setdefault(rel, {"heads": {}, "tails": {}, "n": 0})
        e["heads"][local(ht)] = e["heads"].get(local(ht), 0) + int(n)
        e["tails"][local(tt)] = e["tails"].get(local(tt), 0) + int(n)
        e["n"] += int(n)
    for r in rels:
        e = by_rel.get(r["name"], {"heads": {}, "tails": {}, "n": 0})
        # Shares are measured among the ends that HAVE a type: an untyped
        # subject is unknown, not evidence against the domain.
        heads = {k: v for k, v in e["heads"].items() if k != "Unclassified"} or e["heads"]
        tails = {k: v for k, v in e["tails"].items() if k != "Unclassified"} or e["tails"]
        if e["n"]:
            r["domain"], dn = max(heads.items(), key=lambda kv: kv[1])
            r["range"], rn = max(tails.items(), key=lambda kv: kv[1])
            r["domain_share"] = round(dn / sum(heads.values()), 4)
            r["range_share"] = round(rn / sum(tails.values()), 4)
            r["typed_ends"] = round((sum(heads.values()) + sum(tails.values()))
                                    / (2 * e["n"]), 4)
        else:
            r["domain"] = r["range"] = "Unclassified"
            r["domain_share"] = r["range_share"] = 0.0
        if r["hierarchy"]:                       # narrower: subject is the broader one
            r["domain"], r["range"] = r["range"], r["domain"]
    g.sql(f"DROP TABLE IF EXISTS {tmp}")
    return {"source": source, "entity_table": q["entity_table"], "method": method,
            "entities": total_entities, "types": types, "relations": rels,
            "inherited": inherited}


# ------------------------------------------------------------------- AI
AI_SYSTEM = ("You describe the types of a knowledge graph for business readers. For each "
             "type, write one plain sentence saying what kind of thing it is, using the "
             "sample names and relations given. Refer to the type by its readable name "
             "exactly as given in `name`. Reply with one JSON object only: "
             "{\"types\": [{\"type\": \"exact type as given\", "
             "\"description\": \"one sentence\"}]}")


def describe_types(client, domain: str, found: dict) -> dict:
    from agent.llm import extract_json_object
    facts = {"domain": domain, "types": [
        {"type": t["type"], "name": display(t), "entities": t["entities"],
         "sample_names": t["samples"],
         "is_object_of": [r["verb"] for r in found["relations"] if r["range"] == t["type"]][:12],
         "is_subject_of": [r["verb"] for r in found["relations"] if r["domain"] == t["type"]][:12]}
        for t in found["types"].values()]}
    reply = client.complete([{"role": "system", "content": AI_SYSTEM},
                             {"role": "user", "content": json.dumps(facts)}], max_tokens=3000)
    data = extract_json_object(reply)
    out = {}
    wanted = {_norm(k): k for k in found["types"]}
    for t in data.get("types") or []:
        key = wanted.get(_norm(t.get("type"))) if isinstance(t, dict) else None
        if key and t.get("description"):
            out[key] = {"description": mn._clean(t.get("description"), 300)}
    return out


def _norm(text) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def display(t: dict) -> str:
    """The name a person sees: the data's own type name, readable."""
    return "Not yet typed" if t["raw"] is None else mn.thing_name(t["type"])


def article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


# ------------------------------------------------------------------ write
def _sample_text(values: list[str], n: int = 4) -> str:
    return ", ".join(v.replace("_", " ") for v in values[:n])


def build(layer, ontology_id: str, source: str, client=None, domain: str = "",
          progress=None, state: dict | None = None) -> dict:
    """Analyse one triple source and write its ontology to the registry.

    Several graph sources in one ontology share `state` (one dict per build):
    a type found in two sources is ONE thing (records added up, both sources
    listed) and the same relation is ONE link (triples added up)."""
    say = progress or (lambda _line: None)
    state = state if state is not None else {}
    things = state.setdefault("things", {})        # concept -> accumulated thing
    links = state.setdefault("links", {})          # link key -> accumulated link
    g = layer.graph
    say(f"Reading {source} as a knowledge graph (types from the relations)...")
    found = analyse(layer, source)
    use_ai = client is not None and not getattr(client, "mock", True) and mn.ai_enabled()
    ai, ai_error = {}, None
    if use_ai and found["types"]:
        try:
            ai = describe_types(client, domain, found)
        except Exception as exc:                  # noqa: BLE001 - template fallback
            ai_error = f"{type(exc).__name__}: {str(exc)[:160]}"
    how = {"explicit": "their declared type",
           "instance_of": "their instance-of relation",
           "relation_names": "the relations that point at them",
           "single": "one type (the relations do not name types)"}[found["method"]]
    entity_table = found["entity_table"]
    for t in found["types"].values():
        concept = re.sub(r"\W", "", t["type"]) or "Entity"
        member = f"{entity_table}#{concept}"
        # The data's own type names (Method, Task) are stable across rebuilds;
        # the AI only writes the description.
        name = display(t)
        first = concept not in things
        acc = things.setdefault(concept, {"members": [], "records": 0, "purity": [],
                                          "description": None, "by": "engine",
                                          "samples": t["samples"]})
        acc["members"].append(member)
        acc["records"] += t["entities"]
        acc["purity"].append((t["purity"], t["entities"]))
        if acc["description"] is None and ai.get(t["type"], {}).get("description"):
            acc["description"], acc["by"] = ai[t["type"]]["description"], "ai"
        purity = sum(p * n for p, n in acc["purity"]) / max(1, acc["records"])
        sources = len(acc["members"])
        if t["raw"] is None:
            evidence = f"{acc['records']:,} entities with no typed relation and no typed parent"
        else:
            evidence = f"{acc['records']:,} entities typed by {how}"
            if found["method"] == "relation_names":
                evidence += f"; {purity:.0%} of their relations agree"
        if sources > 1:
            evidence += f" ({sources} sources)"
        reg.put(g, ontology_id, "concept", concept,
                {"name": concept, "description": "", "members": list(acc["members"]),
                 "master": None, "keys": {m: "id" for m in acc["members"]},
                 "classes": {m: concept for m in acc["members"]}, "graph": True},
                confidence=round(purity, 4), evidence=[evidence])
        reg.put(g, ontology_id, "member", f"{concept}|{member}",
                {"concept": concept, "table": member, "key": "id", "role": "source_system",
                 "master": False}, confidence=t["purity"], evidence=[evidence])
        description = acc["description"] or (
            f"Entities the data has not typed yet, such as {_sample_text(acc['samples'])}."
            if t["raw"] is None else
            f"{article(name).capitalize()} {name.lower()} in the knowledge graph, such as "
            f"{_sample_text(acc['samples'])}.")
        thing = {"concept": concept, "name": name, "description": description,
                 "by": acc["by"], "tables": list(acc["members"]), "records": acc["records"],
                 "proof": evidence}
        mine = reg.get_item(g, ontology_id, "meaning", f"thing:{concept}", missing_ok=True)
        if mine and mine["payload"].get("by") == "you":     # a person's rename wins
            thing.update({k: mine["payload"][k] for k in ("name", "description")
                          if mine["payload"].get(k)}, by="you")
        reg.put(g, ontology_id, "meaning", f"thing:{concept}", thing, fact=True,
                confidence=round(purity, 4))
        if not first:
            continue                              # one ID / Name pair per thing
        for col, label, role, meaning, proof in (
                ("id", "ID", "identifier", f"Unique id of each {name.lower()}.",
                 "every entity has its own id"),
                ("label", "Name", "name", f"The name of the {name.lower()}.",
                 f"e.g. {_sample_text(t['samples'])}" if t["samples"] else "no names")):
            key = f"{member}.{col}"
            reg.put(g, ontology_id, "mapping", key,
                    {"table": member, "column": col, "concept": concept, "property": role,
                     "unit": None, "method": "graph", "definition": meaning,
                     "type": "VARCHAR"}, confidence=1.0, evidence=[proof])
            field = {"key": key, "table": member, "column": col, "type": "VARCHAR",
                     "label": label, "meaning": meaning, "role": role, "unit": None,
                     "by": "engine", "check": "verified", "proof": proof, "confidence": 1.0,
                     "reference_to": None}
            mine = reg.get_item(g, ontology_id, "meaning", f"column:{key}", missing_ok=True)
            if mine and mine["payload"].get("by") == "you":  # a person's edit wins
                field.update({k: mine["payload"][k] for k in ("label", "meaning", "role", "unit")
                              if mine["payload"].get(k) not in (None, "")}, by="you")
            reg.put(g, ontology_id, "meaning", f"column:{key}", field, fact=True,
                    confidence=1.0, evidence=[proof])
    known = {re.sub(r"\W", "", t) for t in found["types"]}
    # A large graph can have thousands of relations (gptkb: P0..P8000). The
    # MAX_LINKS most frequent ones carry nearly all triples; the rest are
    # counted, not listed (a person cannot read 8,000 links).
    linkable = sorted((r for r in found["relations"] if not r.get("instance")),
                      key=lambda r: -r["triples"])
    shown, rest = linkable[:MAX_LINKS], linkable[MAX_LINKS:]
    state["hidden_relations"] = state.get("hidden_relations", 0) + len(rest)
    state["hidden_triples"] = state.get("hidden_triples", 0) + sum(r["triples"] for r in rest)
    for r in shown:
        a = re.sub(r"\W", "", r["domain"]) or "Entity"
        b = re.sub(r"\W", "", r["range"]) or "Entity"
        if a not in known or b not in known:
            continue
        verb = "is a kind of" if r["hierarchy"] is not None else r["verb"]
        key = f"graph:{r['label']}:{a}:{b}"
        acc = links.setdefault(key, {"triples": 0, "dom": 0.0, "rng": 0.0, "sources": 0,
                                     "from": f"{entity_table}#{a}.id",
                                     "to": f"{entity_table}#{b}.id"})
        acc["triples"] += r["triples"]
        acc["dom"] += r["domain_share"] * r["triples"]
        acc["rng"] += r["range_share"] * r["triples"]
        acc["sources"] += 1
        dom, rng = acc["dom"] / max(1, acc["triples"]), acc["rng"] / max(1, acc["triples"])
        proof = [f"{acc['triples']:,} triples ({r['label']})"
                 + (f" across {acc['sources']} sources" if acc["sources"] > 1 else ""),
                 f"{dom:.0%} of typed subjects are {mn.thing_name(r['domain'])}",
                 f"{rng:.0%} of typed objects are {mn.thing_name(r['range'])}"]
        reg.put(g, ontology_id, "relationship", key, {
            "from_concept": a, "to_concept": b, "verb": verb, "relation": r["label"],
            "from": acc["from"], "to": acc["to"], "cardinality": "many-to-many",
            "triples": acc["triples"], "matched": round(min(dom, rng), 4),
            "hierarchy": r["hierarchy"] is not None},
            confidence=round(min(dom, rng), 4), evidence=proof)
    say(f"{source}: {len(found['types'])} types, {len(found['relations'])} relations, "
        f"{found['entities']:,} entities"
        + (f" ({len(rest)} rarer relations not listed)" if rest else ""))
    return {"source": source, "types": len(found["types"]),
            "relations": len(found["relations"]), "entities": found["entities"],
            "method": found["method"], "hidden_relations": len(rest),
            "hidden_triples": sum(r["triples"] for r in rest),
            "ai": {"used": bool(ai), "error": ai_error}}
