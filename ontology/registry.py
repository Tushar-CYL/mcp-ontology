"""The enterprise ontology registry: the system of record for an ontology
that spans several sources.

Discovery (``ontology/discover.py``) describes ONE source. An enterprise
ontology unifies many: CRM "Account", ERP "Customer" and the MDM "golden
customer" become one Customer concept, and each source column is mapped to a
canonical property with a definition. That ontology lives here.

Every item - concept, property, mapping, relationship, hierarchy, identity,
conflict, rule, action, contract - is stored the same way: a JSON payload plus
status, owner, confidence and evidence. That uniformity is what makes
governance (maturity levels 2 and 4) real rather than decorative:

* the accelerator writes PROPOSALS; re-running it refreshes them but never
  overrides a person's decision;
* a person approves, rejects or edits; every decision is audited;
* publishing freezes the approved items as a numbered version that tools read.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

KINDS = ("profile", "concept", "member", "property", "mapping", "relationship",
         "hierarchy", "identity", "conflict", "freshness", "survivorship",
         "rule", "action", "contract", "drift", "finding",
         # The simple flow: plain meanings (AI, metadata or a person), the
         # context notes people add, and imported metadata files.
         "meaning", "note", "metadata")
ROLES = ("source_system", "mdm_hub", "data_mart", "reference")
DECISIONS = ("approved", "rejected", "edited")
USER_ROLES = ("viewer", "editor", "approver")
_DECIDED = ("approved", "rejected")

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS eo_ontologies (id TEXT PRIMARY KEY, name TEXT,"
    " problem TEXT, domain TEXT, questions TEXT, created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS eo_sources (ontology_id TEXT, source_id TEXT,"
    " role TEXT, owner_team TEXT, cadence_days INTEGER, position INTEGER,"
    " PRIMARY KEY (ontology_id, source_id))",
    "CREATE TABLE IF NOT EXISTS eo_items (ontology_id TEXT, kind TEXT, key TEXT,"
    " payload TEXT, status TEXT, confidence DOUBLE, evidence TEXT, owner TEXT,"
    " updated_at TEXT, PRIMARY KEY (ontology_id, kind, key))",
    "CREATE TABLE IF NOT EXISTS eo_audit (ontology_id TEXT, kind TEXT, key TEXT,"
    " decision TEXT, by_user TEXT, note TEXT, decided_at TEXT, seq BIGINT)",
    "CREATE TABLE IF NOT EXISTS eo_roles (ontology_id TEXT, user_name TEXT,"
    " role TEXT, PRIMARY KEY (ontology_id, user_name))",
    "CREATE TABLE IF NOT EXISTS eo_versions (ontology_id TEXT, version INTEGER,"
    " published_at TEXT, by_user TEXT, notes TEXT, snapshot TEXT,"
    " PRIMARY KEY (ontology_id, version))",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure(graph) -> None:
    with graph.lock:
        for statement in _SCHEMA:
            graph.con.execute(statement)


# -------------------------------------------------------------- ontologies
def create(graph, ontology_id: str, name: str, problem: str = "",
           domain: str = "", questions: list[str] | None = None,
           sources: list[dict] | None = None) -> dict:
    """Start an ontology from the intake: the problem, the domain, the
    questions that matter, and each source's role, owner and cadence."""
    ensure(graph)
    ontology_id = str(ontology_id or "").strip()
    if not ontology_id:
        raise ValueError("an ontology needs an id")
    if graph.one("SELECT count(*) FROM eo_ontologies WHERE id = ?", [ontology_id]):
        raise ValueError(f"ontology {ontology_id!r} already exists")
    cleaned = []
    for i, src in enumerate(sources or []):
        sid = str(src.get("source_id") or "").strip()
        role = src.get("role", "source_system")
        cadence = int(src.get("cadence_days", 1))
        if not sid:
            raise ValueError("every source needs a source_id")
        if role not in ROLES:
            raise ValueError(f"role must be one of {', '.join(ROLES)}")
        if cadence < 1:
            raise ValueError("cadence_days must be at least 1")
        cleaned.append((sid, role, str(src.get("owner_team") or ""), cadence, i))
    with graph.lock:
        graph.con.execute(
            "INSERT INTO eo_ontologies VALUES (?, ?, ?, ?, ?, ?)",
            [ontology_id, name, problem, domain,
             json.dumps(list(questions or [])), _now()])
        for sid, role, owner, cadence, pos in cleaned:
            graph.con.execute(
                "INSERT INTO eo_sources VALUES (?, ?, ?, ?, ?, ?)",
                [ontology_id, sid, role, owner, cadence, pos])
    return get(graph, ontology_id)


def get(graph, ontology_id: str) -> dict:
    ensure(graph)
    rows = graph.sql("SELECT id, name, problem, domain, questions, created_at"
                     " FROM eo_ontologies WHERE id = ?", [ontology_id])
    if not rows:
        raise KeyError(f"no ontology {ontology_id!r}")
    oid, name, problem, domain, questions, created = rows[0]
    sources = [{"source_id": r[0], "role": r[1], "owner_team": r[2],
                "cadence_days": int(r[3])}
               for r in graph.sql(
                   "SELECT source_id, role, owner_team, cadence_days FROM eo_sources"
                   " WHERE ontology_id = ? ORDER BY position", [oid])]
    return {"id": oid, "name": name, "problem": problem, "domain": domain,
            "questions": json.loads(questions or "[]"), "created_at": created,
            "sources": sources}


def delete_ontology(graph, ontology_id: str) -> None:
    """Remove an ontology and everything recorded about it. Source data is
    untouched: only the registry rows go."""
    get(graph, ontology_id)
    with graph.lock:
        # Every table that records something per ontology (items, audit,
        # versions, roles, sources, the identity crosswalk, and any added
        # later) is found by its ontology_id column, so nothing is left behind.
        tables = [r[0] for r in graph.con.execute(
            "SELECT DISTINCT table_name FROM information_schema.columns"
            " WHERE column_name = 'ontology_id' AND table_name LIKE 'eo\\_%' ESCAPE '\\'"
        ).fetchall()]
        for table in tables:
            graph.con.execute(f'DELETE FROM "{table}" WHERE ontology_id = ?', [ontology_id])
        graph.con.execute("DELETE FROM eo_ontologies WHERE id = ?", [ontology_id])
        try:
            graph.con.execute("CHECKPOINT")     # write the deletion to the file now
        except Exception:                        # noqa: BLE001 - busy; DuckDB will later
            pass


def list_ontologies(graph) -> list[dict]:
    ensure(graph)
    return [get(graph, r[0]) for r in
            graph.sql("SELECT id FROM eo_ontologies ORDER BY created_at, id")]


# ------------------------------------------------------------------- items
def _check_kind(kind: str) -> None:
    if kind not in KINDS:
        raise ValueError(f"unknown item kind {kind!r}; use one of {', '.join(KINDS)}")


def _row(row) -> dict:
    kind, key, payload, status, confidence, evidence, owner, updated = row
    return {"kind": kind, "key": key, "payload": json.loads(payload or "{}"),
            "status": status, "confidence": confidence,
            "evidence": json.loads(evidence or "[]"), "owner": owner or "",
            "updated_at": updated}


def put(graph, ontology_id: str, kind: str, key: str, payload: dict,
        confidence: float | None = None, evidence: list | None = None,
        owner: str | None = None, status: str = "proposed",
        fact: bool = False) -> dict:
    """Write a proposal. An item a person already approved or rejected is
    left exactly as they decided.

    `fact=True` is for measurements (a profile, a freshness lag, a data
    contract): they are stored approved and always refreshed, because a
    measurement is not a decision."""
    _check_kind(kind)
    get(graph, ontology_id)
    current = get_item(graph, ontology_id, kind, key, missing_ok=True)
    if fact:
        status = "approved"
    elif current and current["status"] in _DECIDED:
        return current
    with graph.lock:
        graph.con.execute(
            "DELETE FROM eo_items WHERE ontology_id = ? AND kind = ? AND key = ?",
            [ontology_id, kind, key])
        graph.con.execute(
            "INSERT INTO eo_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [ontology_id, kind, key, json.dumps(payload, default=str), status,
             confidence, json.dumps(list(evidence or []), default=str),
             owner if owner is not None else (current or {}).get("owner", ""),
             _now()])
    return get_item(graph, ontology_id, kind, key)


def get_item(graph, ontology_id: str, kind: str, key: str,
             missing_ok: bool = False) -> dict | None:
    ensure(graph)
    rows = graph.sql("SELECT kind, key, payload, status, confidence, evidence,"
                     " owner, updated_at FROM eo_items WHERE ontology_id = ?"
                     " AND kind = ? AND key = ?", [ontology_id, kind, key])
    if not rows:
        if missing_ok:
            return None
        raise KeyError(f"no {kind} {key!r} in ontology {ontology_id!r}")
    return _row(rows[0])


def items(graph, ontology_id: str, kind: str | None = None,
          status: str | None = None) -> list[dict]:
    ensure(graph)
    sql = ("SELECT kind, key, payload, status, confidence, evidence, owner,"
           " updated_at FROM eo_items WHERE ontology_id = ?")
    args: list = [ontology_id]
    if kind:
        _check_kind(kind)
        sql += " AND kind = ?"
        args.append(kind)
    if status:
        sql += " AND status = ?"
        args.append(status)
    sql += " ORDER BY kind, key"
    return [_row(r) for r in graph.sql(sql, args)]


def annotate(graph, ontology_id: str, kind: str, key: str, owner: str | None = None,
             **fields) -> dict:
    """System labels (owner, tier) on an item, whatever its status. Never
    used for meaning: that only changes through a proposal or a decision."""
    item = get_item(graph, ontology_id, kind, key)
    payload = {**item["payload"], **fields}
    with graph.lock:
        graph.con.execute(
            "UPDATE eo_items SET payload = ?, owner = coalesce(?, owner)"
            " WHERE ontology_id = ? AND kind = ? AND key = ?",
            [json.dumps(payload, default=str), owner, ontology_id, kind, key])
    return get_item(graph, ontology_id, kind, key)


def set_owner(graph, ontology_id: str, kind: str, key: str, owner: str) -> dict:
    get_item(graph, ontology_id, kind, key)
    with graph.lock:
        graph.con.execute("UPDATE eo_items SET owner = ? WHERE ontology_id = ?"
                          " AND kind = ? AND key = ?", [owner, ontology_id, kind, key])
    return get_item(graph, ontology_id, kind, key)


# ------------------------------------------------------------- governance
def grant(graph, ontology_id: str, user: str, role: str) -> None:
    if role not in USER_ROLES:
        raise ValueError(f"role must be one of {', '.join(USER_ROLES)}")
    get(graph, ontology_id)
    with graph.lock:
        graph.con.execute("DELETE FROM eo_roles WHERE ontology_id = ? AND user_name = ?",
                          [ontology_id, user])
        graph.con.execute("INSERT INTO eo_roles VALUES (?, ?, ?)", [ontology_id, user, role])


def roles(graph, ontology_id: str) -> list[dict]:
    ensure(graph)
    return [{"user": u, "role": r} for u, r in graph.sql(
        "SELECT user_name, role FROM eo_roles WHERE ontology_id = ? ORDER BY 1",
        [ontology_id])]


def _require_approver(graph, ontology_id: str, user: str) -> None:
    """Until anyone is granted a role, the first steward bootstraps the
    ontology; after that only approvers decide and publish."""
    granted = {r["user"]: r["role"] for r in roles(graph, ontology_id)}
    if granted and granted.get(user) != "approver":
        raise PermissionError(f"{user!r} is not an approver of ontology {ontology_id!r}")


def _audit(graph, ontology_id, kind, key, decision, by, note) -> None:
    with graph.lock:
        seq = graph.con.execute(
            "SELECT coalesce(max(seq), 0) + 1 FROM eo_audit").fetchone()[0]
        graph.con.execute("INSERT INTO eo_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                          [ontology_id, kind, key, decision, by, note, _now(), seq])


def decide(graph, ontology_id: str, kind: str, key: str, decision: str,
           by: str, payload: dict | None = None, note: str = "") -> dict:
    """A person's decision. 'edited' replaces the payload and approves it."""
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {', '.join(DECISIONS)}")
    current = get_item(graph, ontology_id, kind, key)
    _require_approver(graph, ontology_id, by)
    status = "rejected" if decision == "rejected" else "approved"
    new_payload = payload if decision == "edited" and payload is not None \
        else current["payload"]
    with graph.lock:
        graph.con.execute(
            "UPDATE eo_items SET status = ?, payload = ?, updated_at = ?"
            " WHERE ontology_id = ? AND kind = ? AND key = ?",
            [status, json.dumps(new_payload, default=str), _now(),
             ontology_id, kind, key])
    _audit(graph, ontology_id, kind, key, decision, by, note)
    return get_item(graph, ontology_id, kind, key)


def approve_all(graph, ontology_id: str, kind: str, by: str,
                min_confidence: float = 0.0) -> list[str]:
    """Bulk approval with evidence visible: only proposals at or above the
    confidence a person chose."""
    done = []
    for item in items(graph, ontology_id, kind=kind, status="proposed"):
        if (item["confidence"] or 0) >= min_confidence:
            decide(graph, ontology_id, kind, item["key"], "approved", by=by,
                   note=f"bulk approve (confidence >= {min_confidence})")
            done.append(item["key"])
    return done


def audit(graph, ontology_id: str) -> list[dict]:
    ensure(graph)
    return [{"kind": r[0], "key": r[1], "decision": r[2], "by": r[3],
             "note": r[4], "at": r[5]}
            for r in graph.sql(
                "SELECT kind, key, decision, by_user, note, decided_at FROM eo_audit"
                " WHERE ontology_id = ? ORDER BY seq", [ontology_id])]


# --------------------------------------------------------------- versions
def publish(graph, ontology_id: str, by: str, notes: str = "") -> dict:
    """Freeze every approved item as the next version."""
    _require_approver(graph, ontology_id, by)
    # Snapshot, number and insert under one hold of the (re-entrant) lock:
    # two edits publishing at the same moment must get distinct versions.
    with graph.lock:
        approved = items(graph, ontology_id, status="approved")
        if not approved:
            raise ValueError("nothing is approved yet; approve items before publishing")
        number = int(graph.one("SELECT coalesce(max(version), 0) + 1 FROM eo_versions"
                               " WHERE ontology_id = ?", [ontology_id]))
        snapshot = [{k: i[k] for k in ("kind", "key", "payload", "confidence",
                                       "evidence", "owner")} for i in approved]
        graph.con.execute("INSERT INTO eo_versions VALUES (?, ?, ?, ?, ?, ?)",
                          [ontology_id, number, _now(), by, notes,
                           json.dumps(snapshot, default=str)])
    _audit(graph, ontology_id, "version", str(number), "published", by, notes)
    return version(graph, ontology_id, number)


def versions(graph, ontology_id: str) -> list[dict]:
    ensure(graph)
    return [{"version": r[0], "published_at": r[1], "by": r[2], "notes": r[3]}
            for r in graph.sql("SELECT version, published_at, by_user, notes"
                               " FROM eo_versions WHERE ontology_id = ?"
                               " ORDER BY version", [ontology_id])]


def version(graph, ontology_id: str, number: int | None = None) -> dict:
    """One published version (the latest when no number is given)."""
    ensure(graph)
    if number is None:
        number = graph.one("SELECT max(version) FROM eo_versions"
                           " WHERE ontology_id = ?", [ontology_id])
        if number is None:
            raise KeyError(f"ontology {ontology_id!r} has no published version")
    rows = graph.sql("SELECT version, published_at, by_user, notes, snapshot"
                     " FROM eo_versions WHERE ontology_id = ? AND version = ?",
                     [ontology_id, int(number)])
    if not rows:
        raise KeyError(f"no version {number} of ontology {ontology_id!r}")
    v, at, by, notes, snap = rows[0]
    return {"ontology_id": ontology_id, "version": v, "published_at": at,
            "by": by, "notes": notes, "items": json.loads(snap)}


def diff(graph, ontology_id: str, a: int, b: int) -> dict:
    old = {(i["kind"], i["key"]): i for i in version(graph, ontology_id, a)["items"]}
    new = {(i["kind"], i["key"]): i for i in version(graph, ontology_id, b)["items"]}

    def ref(k):
        return {"kind": k[0], "key": k[1]}
    return {"from": a, "to": b,
            "added": [ref(k) for k in sorted(new.keys() - old.keys())],
            "removed": [ref(k) for k in sorted(old.keys() - new.keys())],
            "changed": [ref(k) for k in sorted(new.keys() & old.keys())
                        if new[k]["payload"] != old[k]["payload"]]}


def prune(graph, ontology_id: str, kind: str, keep: set,
          prefixes: tuple | None = None) -> list[str]:
    """Drop PROPOSALS of a kind that a fresh run no longer makes. Anything a
    person approved or rejected stays. `prefixes` limits the sweep to the keys
    one step owns (several steps write findings)."""
    gone = [i["key"] for i in items(graph, ontology_id, kind=kind, status="proposed")
            if i["key"] not in keep
            and (prefixes is None or i["key"].startswith(tuple(prefixes)))]
    with graph.lock:
        for key in gone:
            graph.con.execute("DELETE FROM eo_items WHERE ontology_id = ? AND kind = ?"
                              " AND key = ? AND status = 'proposed'",
                              [ontology_id, kind, key])
    return gone
