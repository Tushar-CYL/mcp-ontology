"""The simple ontology flow: connect data, get an ontology, optionally add
context, use it anywhere.

    build(...)        data (+ optional metadata) -> ontology, published
    view(...)         the ontology in plain words: things, fields, links
    add_context(...)  a person's note ("KUNNR is the customer number") applied
    edit_field(...)   / edit_thing(...): direct corrections
    for_excel(...)    flat Things / Fields / Links tables (Nexus, Excel)

Underneath it is the same engine as the full accelerator (profile, concepts,
mapping, structure, identity) plus AI meanings checked against the data
(``ontology.meaning``). Every build and every change publishes a new version,
so the MCP tools, the REST API and the Excel export always read the same,
pinned ontology. Approval steps, roles and survivorship stay available in
the advanced accelerator but are not part of this flow.
"""

from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime, timezone

from ontology import meaning as mn
from ontology import metadata as md
from ontology import registry as reg

KEEP_KINDS = ("meaning", "note", "metadata")
ENGINE = [("profile", "ontology.profile", "profile_ontology", "Profiling every column"),
          ("concepts", "ontology.concepts", "propose_concepts", "Finding the business things"),
          ("mapping", "ontology.mapping", "map_properties", "Reading what each field holds"),
          ("structure", "ontology.structure", "propose_structure",
           "Proving the links between things")]
BUILDER = "strata"
_CREATE_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slug(name: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")
    return text[:40] or "ontology"


def unique_id(graph, name: str) -> str:
    # "new" and "all" are screen addresses (/tools/ontology/new, /all).
    taken = {o["id"] for o in reg.list_ontologies(graph)} | {"new", "all"}
    base = slug(name)
    out, n = base, 2
    while out in taken:
        out = f"{base}-{n}"
        n += 1
    return out


# ------------------------------------------------------------------ build
def _reset(graph, ontology_id: str) -> None:
    """A rebuild starts clean: the engine re-measures everything. Meanings,
    notes and metadata stay (a person's corrections must survive)."""
    with graph.lock:
        graph.con.execute(
            "DELETE FROM eo_items WHERE ontology_id = ? AND kind NOT IN (?, ?, ?)",
            [ontology_id, *KEEP_KINDS])
    # Generated meanings are rebuilt too; only a person's edits ("by": "you")
    # and the AI answer cache ("ai:") survive. Otherwise a column or type that
    # no longer exists would linger as a stale field.
    for item in reg.items(graph, ontology_id, kind="meaning"):
        if item["key"].startswith(("column:", "thing:")) and item["payload"].get("by") != "you":
            with graph.lock:
                graph.con.execute("DELETE FROM eo_items WHERE ontology_id = ? AND"
                                  " kind = 'meaning' AND key = ?", [ontology_id, item["key"]])


def add_metadata(graph, ontology_id: str, path: str) -> dict:
    meta = md.parse(path)
    reg.put(graph, ontology_id, "metadata", meta["file"], meta, fact=True,
            evidence=[f"{len(meta['tables'])} tables, {len(meta['relationships'])} links, "
                      f"{len(meta['measures'])} measures from {meta['file']}"])
    return meta


def _declared_links(layer, ontology_id: str, meta: dict | None) -> int:
    """Links the client's model declares, checked against the data."""
    if not meta or not meta.get("relationships"):
        return 0
    from ontology.concepts import _tables
    from ontology.structure import measure_relationship
    graph = layer.graph
    tables = _tables(layer, reg.get(graph, ontology_id))
    by_norm = {md.norm(t["table"].name): t for t in tables}
    concept_of = {i["payload"]["table"]: i["payload"]["concept"]
                  for i in reg.items(graph, ontology_id, kind="member")}
    have = {i["key"] for i in reg.items(graph, ontology_id, kind="relationship")}
    added = 0
    for r in meta["relationships"]:
        t, u = by_norm.get(md.norm(r["from_table"])), by_norm.get(md.norm(r["to_table"]))
        if not t or not u:
            continue
        col = next((c.name for c in t["table"].columns
                    if md.norm(c.name) == md.norm(r["from_column"])), None)
        key = next((c.name for c in u["table"].columns
                    if md.norm(c.name) == md.norm(r["to_column"])), None)
        if not col or not key:
            continue
        link = f"{t['key']}.{col}->{u['key']}.{key}"
        if link in have or t["key"] == u["key"]:
            continue
        stats = measure_relationship(graph, t, u, col, key)
        reg.put(graph, ontology_id, "relationship", link, {
            "from_concept": concept_of.get(t["key"], t["class"]),
            "to_concept": concept_of.get(u["key"], u["class"]),
            "from": f"{t['key']}.{col}", "to": f"{u['key']}.{key}",
            "declared": meta["file"], **stats},
            confidence=stats["matched"],
            evidence=[f"declared in {meta['file']}; checked: {stats['matched']:.0%} of "
                      f"{t['key']} rows find their {u['key']} row"])
        added += 1
    return added


def tidy_links(layer, ontology_id: str) -> list[str]:
    """Keep the links a person would draw.

    Discovery also finds indirect matches: order_items.order_id matches
    reviews.order_id because both point at orders, and a one-to-one pair is
    found in both directions. A link whose target column is NOT the target
    table's own key is dropped when the same column also links to a real key,
    or when the reverse link lands on a real key."""
    from ontology.concepts import _tables
    graph = layer.graph
    pk = {t["key"]: t["id"] for t in _tables(layer, reg.get(graph, ontology_id))}
    rels = [i for i in reg.items(graph, ontology_id, kind="relationship")
            if i["status"] != "rejected"]

    def lands_on_key(frm_to: tuple) -> bool:
        table, col = frm_to[1].rsplit(".", 1)
        return pk.get(table) == col

    pairs = {(i["payload"]["from"], i["payload"]["to"]): i["key"] for i in rels}
    drop = []
    for (frm, to), key in pairs.items():
        if lands_on_key((frm, to)):
            continue
        same_source = any(f == frm and t != to and lands_on_key((f, t)) for f, t in pairs)
        reverse = (to, frm) in pairs and lands_on_key((to, frm))
        if same_source or reverse:
            drop.append(key)
    with graph.lock:
        for key in drop:
            graph.con.execute("DELETE FROM eo_items WHERE ontology_id = ? AND"
                              " kind = 'relationship' AND key = ?", [ontology_id, key])
    return drop


def _forget_tables(graph, ontology_id: str, sources: list[str]) -> None:
    """The table engine ran over every source; for a knowledge-graph source
    its "one Entity table" reading is replaced by graph_onto, so drop it."""
    if not sources:
        return
    prefixes = tuple(f"{s}." for s in sources)
    for item in reg.items(graph, ontology_id):
        p = item["payload"]
        refs = [item["key"], p.get("table", ""), p.get("from", ""), p.get("to", ""),
                p.get("column", ""), *p.get("members", [])]
        if item["kind"] in ("profile", "concept", "member", "mapping", "relationship",
                            "finding", "property", "hierarchy", "identity") and                 any(str(r).startswith(prefixes) for r in refs if r):
            with graph.lock:
                graph.con.execute("DELETE FROM eo_items WHERE ontology_id = ? AND kind = ?"
                                  " AND key = ?", [ontology_id, item["kind"], item["key"]])


def _model_only(graph, ontology_id: str, meta: dict) -> None:
    """No data connected: the ontology comes from the semantic model alone,
    and says so on every item."""
    note = f"declared in {meta['file']}; no data connected to check it"
    concept_of = {}
    for table, t in meta["tables"].items():
        if table == "*":
            continue
        concept = mn.thing_name(table).replace(" ", "")
        concept_of[md.norm(table)] = concept
        key = f"model.{table}"
        reg.put(graph, ontology_id, "concept", concept,
                {"name": concept, "description": t["description"], "members": [key],
                 "master": None, "keys": {}, "classes": {key: concept}},
                confidence=0.7, evidence=[note])
        reg.put(graph, ontology_id, "member", f"{concept}|{key}",
                {"concept": concept, "table": key, "key": None, "role": "source_system",
                 "master": False}, confidence=0.7, evidence=[note])
        reg.put(graph, ontology_id, "meaning", f"thing:{concept}",
                {"concept": concept, "name": mn.thing_name(table), "tables": [key],
                 "by": "metadata", "description": t["description"]
                 or f"The {mn.thing_name(table).lower()} table of the semantic model."},
                fact=True, confidence=0.7)
        for col, info in t["columns"].items():
            ckey = f"{key}.{col}"
            role = _role_from_type(info.get("type", ""), col)
            reg.put(graph, ontology_id, "mapping", ckey,
                    {"table": key, "column": col, "concept": concept, "property": role,
                     "unit": info.get("unit") or None, "method": "model",
                     "definition": info.get("description"), "type": info.get("type")},
                    confidence=0.7, evidence=[note])
            reg.put(graph, ontology_id, "meaning", f"column:{ckey}", {
                "key": ckey, "table": key, "column": col, "type": info.get("type", ""),
                "label": info.get("label") or mn.field_label(col),
                "meaning": info.get("description") or "", "role": role,
                "unit": info.get("unit") or None, "by": "metadata", "check": "unchecked",
                "proof": note, "confidence": 0.7, "reference_to": None},
                fact=True, confidence=0.7, evidence=[note])
    for r in meta["relationships"]:
        a, b = concept_of.get(md.norm(r["from_table"])), concept_of.get(md.norm(r["to_table"]))
        if not a or not b or a == b:
            continue
        frm = f"model.{r['from_table']}.{r['from_column']}"
        to = f"model.{r['to_table']}.{r['to_column']}"
        reg.put(graph, ontology_id, "relationship", f"{frm}->{to}",
                {"from_concept": a, "to_concept": b, "from": frm, "to": to,
                 "cardinality": "many-to-one", "declared": meta["file"]},
                confidence=0.7, evidence=[note])


def _role_from_type(data_type: str, column: str) -> str:
    t = str(data_type).lower()
    if any(x in t for x in ("date", "time")):
        return "date"
    if t in ("boolean", "bool"):
        return "flag"
    if any(x in t for x in ("decimal", "currency", "double", "int", "number")):
        if mn._has(column, "id", "key", "code", "no"):
            return "identifier"
        return "amount" if any(x in t for x in ("decimal", "currency")) else "measure"
    if mn._has(column, "id", "key"):
        return "identifier"
    if mn._has(column, "name", "title"):
        return "name"
    return "category"


def _approve_and_publish(layer, ontology_id: str, notes: str) -> int:
    graph = layer.graph
    with graph.lock:
        graph.con.execute("UPDATE eo_items SET status = 'approved' WHERE ontology_id = ?"
                          " AND status = 'proposed'", [ontology_id])
    from ontology import publish as pub
    has_data = bool(reg.get(graph, ontology_id)["sources"])
    if has_data:
        return pub.publish_version(layer, ontology_id, by=BUILDER, notes=notes)["version"]
    return reg.publish(graph, ontology_id, by=BUILDER, notes=notes)["version"]


def build(layer, ontology_id: str, client=None, progress=None) -> dict:
    """Run everything for an existing ontology and publish a version."""
    say = progress or (lambda _line: None)
    graph = layer.graph
    onto = reg.get(graph, ontology_id)
    started = time.perf_counter()
    _reset(graph, ontology_id)
    meta = mn.metadata_of(graph, ontology_id)
    steps = []
    from ontology import graph_onto
    graph_sources = [s["source_id"] for s in onto["sources"]
                     if graph_onto.is_graph_source(layer, s["source_id"])]
    table_sources = [s["source_id"] for s in onto["sources"]
                     if s["source_id"] not in graph_sources]
    summary: dict = {"ai": {"used": False, "calls": 0, "errors": [], "model": None}}
    if table_sources:
        from importlib import import_module
        run = list(ENGINE)
        if len(table_sources) > 1:
            run.append(("identity", "ontology.identity", "resolve_identities",
                        "Matching the same records across sources"))
        for step_id, module, func, title in run:
            say(f"{title}...")
            t0 = time.perf_counter()
            getattr(import_module(module), func)(layer, ontology_id)
            steps.append({"id": step_id, "seconds": round(time.perf_counter() - t0, 2)})
            if step_id == "concepts":
                tidy_links(layer, ontology_id)
        _forget_tables(graph, ontology_id, graph_sources)
        if meta:
            added = _declared_links(layer, ontology_id, meta)
            if added:
                say(f"{added} link(s) declared in your metadata, checked against the data")
        say("Writing plain meanings (AI checked against the data)...")
        t0 = time.perf_counter()
        summary = mn.enrich(layer, ontology_id, client=client, progress=say)
        steps.append({"id": "meaning", "seconds": round(time.perf_counter() - t0, 2)})
    graph_state: dict = {}                       # merges types/links across graph sources
    for source in graph_sources:
        t0 = time.perf_counter()
        out = graph_onto.build(layer, ontology_id, source, client=client,
                               domain=onto.get("domain") or "", progress=say,
                               state=graph_state)
        steps.append({"id": f"graph:{source}", "seconds": round(time.perf_counter() - t0, 2)})
        if out["ai"]["used"]:
            summary["ai"] = {**summary["ai"], "used": True,
                             "model": getattr(client, "model", None),
                             "calls": summary["ai"].get("calls", 0) + 1}
        if out["ai"]["error"]:
            summary["ai"]["errors"] = summary["ai"].get("errors", []) + [out["ai"]["error"]]
        if out.get("hidden_relations"):
            summary["hidden_relations"] = summary.get("hidden_relations", 0) + out["hidden_relations"]
            summary["hidden_triples"] = summary.get("hidden_triples", 0) + out["hidden_triples"]
    if not onto["sources"]:
        if not meta:
            raise ValueError("connect at least one data source or give a semantic model / "
                             "data dictionary")
        say("No data connected: building from your semantic model alone")
        _model_only(graph, ontology_id, meta)
        summary = {"tables": len(meta["tables"]), "ai": {"used": False, "calls": 0,
                                                         "errors": [], "model": None}}
    version = _approve_and_publish(layer, ontology_id, "automatic build")
    seconds = round(time.perf_counter() - started, 2)
    record = {"at": _now(), "seconds": seconds, "steps": steps, "version": version,
              **summary}
    reg.put(graph, ontology_id, "meaning", "build:last", record, fact=True)
    say(f"Published version {version} in {seconds}s")
    return {"ontology": ontology_id, "version": version, "seconds": seconds,
            "summary": summary}


def create_and_build(layer, name: str, sources: list[str], metadata: list[str] | None = None,
                     domain: str = "", problem: str = "", client=None, progress=None,
                     ontology_id: str | None = None) -> dict:
    graph = layer.graph
    loaded = set(layer.graph.source_ids())
    missing = [s for s in sources if s not in loaded]
    if missing:
        raise ValueError("these sources are not loaded: " + ", ".join(missing))
    if not sources and not metadata:
        raise ValueError("connect at least one data source or give a semantic model / "
                         "data dictionary")
    metas = [md.parse(p) for p in metadata or []]       # fail before creating anything
    # Choosing a free id and claiming it is one step: two builds with the
    # same name at the same moment must not pick the same id.
    with _CREATE_LOCK:
        oid = ontology_id or unique_id(graph, name)
        reg.create(graph, oid, name=name or oid, problem=problem, domain=domain,
                   sources=[{"source_id": s} for s in sources])
    try:
        for meta in metas:
            reg.put(graph, oid, "metadata", meta["file"], meta, fact=True)
        return build(layer, oid, client=client, progress=progress)
    except Exception:
        reg.delete_ontology(graph, oid)
        raise


# ------------------------------------------------------------------- view
def _link_label(frm: str, to: str, cardinality: str | None, verb: str | None = None) -> str:
    if verb:
        return f"{frm} {verb} {to}"
    if cardinality == "one-to-one":
        return f"Each {frm} has one {to}"
    return f"Each {frm} belongs to one {to} (one {to} can have many)"


def confirmed_pct(counts: dict) -> int:
    """Share of fields whose meaning the data confirmed, as a whole percent."""
    total = sum(counts.values())
    return round(100 * counts.get("verified", 0) / total) if total else 0


def view(graph, ontology_id: str, version: int | None = None,
         published: bool = False) -> dict:
    """The ontology in plain words, for the screen, Nexus and agents.

    By default it reads the live registry (what the screen edits). With
    `published=True` (or a `version`) it reads a frozen published version, so
    an agent sees exactly the pinned ontology."""
    onto = reg.get(graph, ontology_id)
    if published or version is not None:
        snap = reg.version(graph, ontology_id, version)
        frozen = [{**i, "status": "approved"} for i in snap["items"]]

        def items(kind):
            return [i for i in frozen if i["kind"] == kind]
    else:
        # One query for the whole ontology, grouped here: the view reads ten
        # kinds, and ten round trips through the shared lock capped
        # throughput at ~20 views/s under concurrent users.
        grouped: dict = {}
        for item in reg.items(graph, ontology_id):
            grouped.setdefault(item["kind"], []).append(item)

        def items(kind):
            return grouped.get(kind, [])
    meanings = {i["key"]: i["payload"] for i in items("meaning")}
    profiles = {i["key"]: i["payload"] for i in items("profile")}
    concepts = [i for i in items("concept")
                if i["status"] != "rejected"]
    thing_of_table, things = {}, []
    for item in concepts:
        c = item["payload"]
        m = meanings.get(f"thing:{item['key']}", {})
        name = m.get("name") or mn.thing_name(item["key"])
        for t in c.get("members", []):
            thing_of_table[t] = name
        things.append({"key": item["key"], "name": name,
                       "description": m.get("description") or c.get("description") or "",
                       "by": m.get("by", "engine"), "tables": c.get("members", []),
                       "records": sum(profiles.get(t, {}).get("rows", 0)
                                      for t in c.get("members", [])) or int(m.get("records") or 0),
                       "fields": []})
    by_key = {t["key"]: t for t in things}
    concept_of = {}
    for i in items("member"):
        concept_of[i["payload"]["table"]] = i["payload"]["concept"]
    counts = {"verified": 0, "conflict": 0, "unchecked": 0}
    by_count: dict = {}
    order = {"identifier": 0, "reference": 1, "name": 2}
    for key, m in meanings.items():
        if not key.startswith("column:"):
            continue
        thing = by_key.get(concept_of.get(m["table"]))
        if thing is None:
            continue
        ref = m.get("reference_to")
        field = {k: m.get(k) for k in ("key", "table", "column", "label", "meaning", "role",
                                       "unit", "type", "by", "check", "proof", "confidence")}
        field["role_label"] = mn.ROLES.get(m.get("role"), m.get("role"))
        field["links_to"] = thing_of_table.get(ref) if ref else None
        if field["links_to"] and str(field.get("proof") or "").startswith("values match"):
            # Name the target the way the screen does, not by its raw table.
            field["proof"] = f"values match {field['links_to']} in the data"
        thing["fields"].append(field)
        counts[m.get("check", "unchecked")] = counts.get(m.get("check", "unchecked"), 0) + 1
        by_count[m.get("by")] = by_count.get(m.get("by"), 0) + 1
    for thing in things:
        thing["fields"].sort(key=lambda f: (f["table"], order.get(f["role"], 3), f["column"]))
    links = []
    for item in items("relationship"):
        if item["status"] == "rejected":
            continue
        p = item["payload"]
        a = by_key.get(p.get("from_concept"), {}).get("name") or p.get("from_concept")
        b = by_key.get(p.get("to_concept"), {}).get("name") or p.get("to_concept")
        links.append({"key": item["key"], "from_thing": a, "to_thing": b,
                      "from": p.get("from"), "to": p.get("to"),
                      "cardinality": p.get("cardinality") or "many-to-one",
                      "label": _link_label(a, b, p.get("cardinality"), p.get("verb")),
                      "verb": p.get("verb"), "triples": p.get("triples"),
                      "relation": p.get("relation"),
                      "match": p.get("matched"), "declared": p.get("declared"),
                      "proof": item["evidence"][:3]})
    links.sort(key=lambda link: (-(link["triples"] or 0), link["label"]))
    hierarchies = [{"thing": by_key.get(i["payload"]["concept"], {}).get("name")
                    or i["payload"]["concept"], "levels": i["payload"]["levels"],
                    "proof": i["evidence"][:1]}
                   for i in items("hierarchy")
                   if i["status"] != "rejected"]
    meta = None
    for i in items("metadata"):
        meta = i["payload"] if meta is None else md.merge(meta, i["payload"])
    calculations = []
    for m in (meta or {}).get("measures", []):
        table = next((t for t in things if any(
            md.norm(x.rsplit(".", 1)[-1]) == md.norm(m["table"]) for x in t["tables"])), None)
        calculations.append({**m, "thing": table["name"] if table else m["table"]})
    notes = sorted(({**i["payload"], "key": i["key"]}
                    for i in items("note")),
                   key=lambda n: n.get("at", ""))
    def plain(text: str) -> str:
        # "salt.i_customer.CUSTOMER" -> "Customer.CUSTOMER": things, not tables.
        for table in sorted(thing_of_table, key=len, reverse=True):
            text = text.replace(table, thing_of_table[table])
        return text.replace("value(s)", "values")

    findings = [{"type": i["payload"].get("type"), "detail": plain(str(i["payload"].get("detail")))}
                for i in items("finding")
                if i["status"] != "rejected"][:8]
    versions = reg.versions(graph, ontology_id)
    if published or version is not None:
        versions = [x for x in versions if x["version"] <= snap["version"]]
    last = meanings.get("build:last", {})
    return {
        "id": onto["id"], "name": onto["name"], "domain": onto["domain"],
        "problem": onto["problem"], "created_at": onto["created_at"],
        "sources": [s["source_id"] for s in onto["sources"]],
        "metadata": [i["key"] for i in items("metadata")],
        "version": versions[-1]["version"] if versions else None,
        "published_at": versions[-1]["published_at"] if versions else None,
        "built": last or None,
        "summary": {"things": len(things), "fields": sum(len(t["fields"]) for t in things),
                    "links": len(links), "checks": counts, "by": by_count,
                    # The one number the pitch rests on: how much of this
                    # ontology the data itself confirmed (not the AI's word).
                    "confirmed_pct": confirmed_pct(counts)},
        "things": sorted(things, key=lambda t: t["name"].lower()),
        "links": links, "hierarchies": hierarchies, "calculations": calculations,
        "notes": notes, "findings": findings,
    }


# ---------------------------------------------------------------- context
def _republish(layer, ontology_id: str, why: str) -> int:
    return _approve_and_publish(layer, ontology_id, why)


def edit_field(layer, ontology_id: str, key: str, by: str = "you", **changes) -> dict:
    graph = layer.graph
    item = reg.get_item(graph, ontology_id, "meaning", f"column:{key}", missing_ok=True)
    if item is None:
        raise KeyError(f"no field {key!r} in ontology {ontology_id!r}")
    allowed = {k: v for k, v in changes.items()
               if k in ("label", "meaning", "role", "unit") and v is not None}
    if "role" in allowed and allowed["role"] not in mn.ROLES:
        raise ValueError(f"role must be one of {', '.join(mn.ROLES)}")
    if not allowed:
        raise ValueError("nothing to change: give label, meaning, role or unit")
    payload = {**item["payload"], **{k: (str(v).strip() or None) if k == "unit" else
                                     str(v).strip() for k, v in allowed.items()},
               "by": "you", "confidence": 1.0, "edited": _now(), "editor": by}
    reg.put(graph, ontology_id, "meaning", f"column:{key}", payload, fact=True,
            confidence=1.0, evidence=[f"set by {by}"])
    _republish(layer, ontology_id, f"{by} edited {key}")
    return payload


def edit_thing(layer, ontology_id: str, concept: str, by: str = "you", **changes) -> dict:
    graph = layer.graph
    item = reg.get_item(graph, ontology_id, "meaning", f"thing:{concept}", missing_ok=True)
    if item is None:
        raise KeyError(f"no thing {concept!r} in ontology {ontology_id!r}")
    allowed = {k: str(v).strip() for k, v in changes.items()
               if k in ("name", "description") and v}
    if not allowed:
        raise ValueError("nothing to change: give name or description")
    payload = {**item["payload"], **allowed, "by": "you", "edited": _now(), "editor": by}
    reg.put(graph, ontology_id, "meaning", f"thing:{concept}", payload, fact=True,
            confidence=1.0, evidence=[f"set by {by}"])
    _republish(layer, ontology_id, f"{by} renamed {concept}")
    return payload


def _catalog(graph, ontology_id: str) -> dict:
    v = view(graph, ontology_id)
    return {"things": [{"key": t["key"], "name": t["name"]} for t in v["things"]],
            "fields": [{"key": f["key"], "column": f["column"], "label": f["label"],
                        "role": f["role"], "thing": t["name"]}
                       for t in v["things"] for f in t["fields"]]}


_RULE = re.compile(r"^\s*(?P<name>[\w .\-/]+?)\s*(?:=|:|->|\bmeans\b|\bis\b|\bare\b|"
                   r"\bshould be called\b|\bstands for\b)\s*(?P<value>.+?)\s*\.?\s*$", re.I)


def parse_note(text: str, catalog: dict) -> list[dict]:
    """Offline reading of a note: lines like 'KUNNR = customer number' or
    'Order Item should be called Order Line'."""
    edits = []
    for line in re.split(r"[\n;]+", text):
        m = _RULE.match(line)
        if not m:
            continue
        name, value = m.group("name").strip(), m.group("value").strip().strip('"\'')
        if not value:
            continue
        want = md.norm(name)
        thing = next((t for t in catalog["things"]
                      if md.norm(t["name"]) == want or md.norm(t["key"]) == want), None)
        if thing:
            short = len(value.split()) <= 4
            edits.append({"target": "thing", "key": thing["key"],
                          **({"name": value.title()} if short else {"description": value})})
            continue
        fields = [f for f in catalog["fields"]
                  if want in (md.norm(f["column"]), md.norm(f["label"]), md.norm(f["key"]))]
        for f in fields:
            short = len(value.split()) <= 5
            edits.append({"target": "field", "key": f["key"],
                          **({"label": value[:1].upper() + value[1:]} if short
                             else {"meaning": value})})
    return edits


NOTE_SYSTEM = (
    "You maintain a business ontology. A person wrote a note with knowledge about "
    "their data. Turn it into precise edits of the ontology below. Only edit items "
    "that exist (use their exact keys). Field edits may set label, meaning, role "
    "(one of: " + ", ".join(mn.ROLES) + ") and unit. Thing edits may set name and "
    "description. If the note contains no change, return no edits. Reply with one "
    "JSON object only: {\"edits\": [{\"target\": \"field\"|\"thing\", \"key\": \"...\", "
    "\"label\"?: \"...\", \"meaning\"?: \"...\", \"role\"?: \"...\", \"unit\"?: \"...\", "
    "\"name\"?: \"...\", \"description\"?: \"...\"}], \"reply\": \"one sentence on what "
    "you changed\"}")


def ai_note(client, text: str, catalog: dict) -> tuple[list[dict], str]:
    from agent.llm import extract_json_object
    small = {"things": catalog["things"], "fields": catalog["fields"][:600]}
    reply = client.complete([{"role": "system", "content": NOTE_SYSTEM},
                             {"role": "user", "content": "ONTOLOGY:\n" + json.dumps(small)
                              + "\n\nNOTE:\n" + text}], max_tokens=4000)
    data = extract_json_object(reply)
    edits = [e for e in data.get("edits") or [] if isinstance(e, dict)]
    return edits, mn._clean(data.get("reply"), 400)


def add_context(layer, ontology_id: str, text: str, client=None, by: str = "you") -> dict:
    """Apply a person's note. Returns the changes made and a reply."""
    text = str(text or "").strip()
    if not text:
        raise ValueError("write a note first")
    if len(text) > 4000:
        raise ValueError("keep a note under 4,000 characters")
    graph = layer.graph
    catalog = _catalog(graph, ontology_id)
    use_ai = client is not None and not getattr(client, "mock", True) and mn.ai_enabled()
    reply, method = "", "rules"
    edits = []
    if use_ai:
        try:
            edits, reply = ai_note(client, text, catalog)
            method = "ai"
        except Exception as exc:                  # noqa: BLE001 - fall back
            reply = f"The AI could not read the note ({type(exc).__name__}); read it with rules."
            edits = []
    if not edits:
        edits = parse_note(text, catalog)
    things = {t["key"] for t in catalog["things"]}
    fields = {f["key"] for f in catalog["fields"]}
    applied = []
    for e in edits:
        key = str(e.get("key") or "")
        try:
            if e.get("target") == "thing" and key in things:
                changes = {k: e[k] for k in ("name", "description") if e.get(k)}
                if changes:
                    _set_thing(graph, ontology_id, key, by, changes)
                    applied.append({"target": "thing", "key": key, **changes})
            elif e.get("target") == "field" and key in fields:
                changes = {k: e[k] for k in ("label", "meaning", "role", "unit")
                           if e.get(k) not in (None, "")}
                if changes.get("role") and changes["role"] not in mn.ROLES:
                    changes.pop("role")
                if changes:
                    _set_field(graph, ontology_id, key, by, changes)
                    applied.append({"target": "field", "key": key, **changes})
        except (KeyError, ValueError):
            continue
    if not reply:
        reply = (f"Changed {len(applied)} item(s)." if applied else
                 "Saved the note; it did not name a field or thing I could change. "
                 "Try 'COLUMN = meaning'. It will guide the AI on the next rebuild.")
    note_key = f"{_now()}|{len(reg.items(graph, ontology_id, kind='note'))}"
    reg.put(graph, ontology_id, "note", note_key,
            {"text": text, "by": by, "at": _now(), "method": method, "reply": reply,
             "changes": applied}, fact=True)
    version = _republish(layer, ontology_id, f"context note by {by}") if applied else None
    return {"changes": applied, "reply": reply, "method": method, "version": version}


def _set_field(graph, ontology_id, key, by, changes) -> None:
    item = reg.get_item(graph, ontology_id, "meaning", f"column:{key}")
    payload = {**item["payload"], **changes, "by": "you", "confidence": 1.0,
               "edited": _now(), "editor": by}
    reg.put(graph, ontology_id, "meaning", f"column:{key}", payload, fact=True,
            confidence=1.0, evidence=[f"set by {by} in a note"])


def _set_thing(graph, ontology_id, key, by, changes) -> None:
    item = reg.get_item(graph, ontology_id, "meaning", f"thing:{key}")
    payload = {**item["payload"], **changes, "by": "you", "edited": _now(), "editor": by}
    reg.put(graph, ontology_id, "meaning", f"thing:{key}", payload, fact=True,
            confidence=1.0, evidence=[f"set by {by} in a note"])


# ---------------------------------------------------------------- exports
SET_BY = {"you": "You", "metadata": "Your metadata", "ai": "AI, checked against data",
          "engine": "Engine (from names)"}
CHECK = {"verified": "Checked in data", "conflict": "Data disagrees", "unchecked": "Not checked"}


def for_excel(graph, ontology_id: str, version: int | None = None) -> dict:
    """Three flat tables (plus calculations) that Nexus or any Excel sheet can
    read directly: one row per thing, per field, per link. Reads the published
    version (the latest unless one is named)."""
    v = view(graph, ontology_id, version=version, published=True)
    things = [{"Thing": t["name"], "Description": t["description"],
               "Records": t["records"], "Fields": len(t["fields"]),
               "Tables": ", ".join(t["tables"]), "Set by": SET_BY.get(t["by"], t["by"])}
              for t in v["things"]]
    fields = [{"Thing": t["name"], "Field": f["label"], "Meaning": f["meaning"],
               "Role": f["role_label"], "Unit": f["unit"] or "",
               "Links to": f["links_to"] or "", "Column": f["column"],
               "Table": f["table"], "Type": f["type"],
               "Check": CHECK.get(f["check"], f["check"]), "Proof": f["proof"] or "",
               "Set by": SET_BY.get(f["by"], f["by"]),
               "Confidence": round(float(f["confidence"] or 0), 2)}
              for t in v["things"] for f in t["fields"]]
    links = [{"From": link["from_thing"], "To": link["to_thing"], "Meaning": link["label"],
              "Cardinality": link["cardinality"], "From column": link["from"],
              "To column": link["to"],
              "Match": f"{link['match']:.0%}" if isinstance(link["match"], (int, float))
              else "", "Proof": "; ".join(link["proof"])}
             for link in v["links"]]
    calcs = [{"Thing": c["thing"], "Calculation": c["name"], "Formula": c["expression"],
              "Description": c.get("description", "")} for c in v["calculations"]]
    return {"ontology": {"id": v["id"], "name": v["name"], "version": v["version"],
                         "published_at": v["published_at"],
                         "confirmed_pct": v["summary"]["confirmed_pct"],
                         "fields_checked": v["summary"]["checks"]},
            "things": things, "fields": fields, "links": links, "calculations": calcs}


def to_xlsx(graph, ontology_id: str, version: int | None = None) -> bytes:
    from ontology.xlsx import workbook
    data = for_excel(graph, ontology_id, version)
    o = data["ontology"]
    about = [{"Item": "Ontology", "Value": o["name"]},
             {"Item": "Version", "Value": o["version"]},
             {"Item": "Published", "Value": o["published_at"]},
             {"Item": "Things", "Value": len(data["things"])},
             {"Item": "Fields", "Value": len(data["fields"])},
             {"Item": "Links", "Value": len(data["links"])},
             {"Item": "Confirmed by the data", "Value": f"{o['confirmed_pct']}% of fields"},
             {"Item": "Fields where the data disagreed with the AI",
              "Value": o["fields_checked"].get("conflict", 0)}]
    sheets = [("Things", data["things"]), ("Fields", data["fields"]),
              ("Links", data["links"])]
    if data["calculations"]:
        sheets.append(("Calculations", data["calculations"]))
    sheets.append(("About", about))
    return workbook(sheets)
