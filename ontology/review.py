"""Review by exception: a person sees only what the data could not settle.

Every claim the AI (or the engine, or a metadata file) made about a field or a
link lands in one of these groups:

* confirmed by checks - the data proved it (values match, every value unique ...)
* data disagrees      - the data contradicts it; the screen already says why
* set by you          - a person wrote it
* approved / rejected - a person decided on it here
* needs you           - nothing in the data can prove or disprove it

Only "needs you" goes to a person, ranked by how much rides on it. A steady
~5% spot-check sample of "confirmed by checks" joins the queue, so Strata
measures how often the checks themselves are wrong instead of assuming they
never are. Every decision is audited, so Strata reports its own acceptance
rate (no vendor number needed).

Decisions are stored as `meaning` items keyed ``review:<target>`` with a copy
of the claim the person saw: they survive rebuilds, and when a rebuild changes
the claim the old decision no longer applies and the item comes back.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone

from ontology import registry as reg

SPOT_EVERY = 20                        # ~5% of confirmed items are spot-checked
DECISIONS = ("approved", "rejected")
STATUS = {
    "needs_you": "Needs you",
    "confirmed": "Confirmed by checks",
    "disagrees": "Data disagrees",
    "set_by_you": "Set by you",
    "approved": "Approved by you",
    "rejected": "Rejected by you",
}
# How much an answer leans on a field of this role (ids and links join
# things; amounts become numbers; dates, categories and places slice them).
ROLE_WEIGHT = {"identifier": 3, "reference": 3, "amount": 3, "date": 2, "category": 2,
               "place": 2, "flag": 2, "name": 1, "text": 1}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def field_target(field: dict) -> str:
    return f"column:{field['key']}"


def link_target(link: dict) -> str:
    return f"link:{link['key']}"


def field_claim(field: dict) -> dict:
    return {"label": field.get("label"), "meaning": field.get("meaning"), "role": field.get("role")}


def link_claim(link: dict) -> dict:
    return {"from": link.get("from"), "to": link.get("to")}


def decisions(meanings: dict) -> dict:
    """{target: decision payload} from the view's meaning items."""
    return {k[len("review:"):]: v for k, v in meanings.items() if k.startswith("review:")}


def spot(target: str) -> bool:
    """A steady, repeatable ~5% sample (the same items every time)."""
    return _hash(target) % SPOT_EVERY == 0


def _hash(target: str) -> int:
    return int(hashlib.sha1(target.encode()).hexdigest(), 16)


def mark_spots(view: dict, reviewed: dict | None = None) -> None:
    """Flag the spot-check sample among the items the data confirmed: a steady
    ~5% (the same items every time), and at least one once there are five -
    until a person has spot-checked something. Then the sample is done: it
    is never refilled with the next item each time one is approved."""
    confirmed = [(field_target(f), f) for t in view["things"] for f in t["fields"]
                 if f["review"] == "confirmed"]
    confirmed += [(link_target(lk), lk) for lk in view["links"] if lk["review"] == "confirmed"]
    picked = [item for target, item in confirmed if spot(target)]
    checked = any(d.get("spot_check") for d in (reviewed or {}).values())
    if not picked and not checked and len(confirmed) >= 5:
        picked = [min(confirmed, key=lambda c: _hash(c[0]))[1]]
    for item in picked:
        item["spot_check"] = True


def status(item: dict, claim: dict, decided: dict | None) -> str:
    """Which group a field or link is in (see the module docstring)."""
    if decided and decided.get("claim") == claim and decided.get("decision") in DECISIONS:
        return decided["decision"]
    if item.get("by") == "you":
        return "set_by_you"
    check = item.get("check")
    if check == "conflict":
        return "disagrees"
    if check == "verified":
        return "confirmed"
    return "needs_you"


def counts(view: dict) -> dict:
    """The header numbers: how many need a person, how many the data settled."""
    out = {k: 0 for k in STATUS}
    out["spot_checks"] = 0
    for t in view["things"]:
        for f in t["fields"]:
            out[f["review"]] += 1
            out["spot_checks"] += bool(f.get("spot_check"))
    for link in view["links"]:
        out[link["review"]] += 1
        out["spot_checks"] += bool(link.get("spot_check"))
    out["rejected"] += len(view.get("rejected_links") or [])
    return out


def _impact(role: str | None, records: int, links: int) -> float:
    return ROLE_WEIGHT.get(role or "", 1) * 2 + math.log10(max(records, 1)) + 2 * links


def queue(graph, ontology_id: str) -> dict:
    """What a person should look at, most important first, evidence before claim."""
    from ontology import simple
    view = simple.view(graph, ontology_id)
    links_of: dict = {}
    for link in view["links"]:
        for end in (link["from_thing"], link["to_thing"]):
            links_of[end] = links_of.get(end, 0) + 1
    cards = []
    for t in view["things"]:
        for f in t["fields"]:
            if f["review"] != "needs_you" and not f.get("spot_check"):
                continue
            cards.append({
                "target": field_target(f), "kind": "field", "thing": t["name"],
                "title": f"{t['name']} . {f['label']}", "column": f["column"],
                "why": "spot_check" if f["review"] == "confirmed" else "unproven",
                "evidence": {"check": f["check"], "proof": f.get("proof") or "",
                             "records": t["records"]},
                "claim": {"label": f["label"], "meaning": f.get("meaning") or "",
                          "role": f.get("role_label") or f.get("role"),
                          "links_to": f.get("links_to"), "by": f.get("by")},
                "impact": round(_impact(f.get("role"), t["records"], links_of.get(t["name"], 0)), 2),
            })
    for link in view["links"]:
        if link["review"] != "needs_you" and not link.get("spot_check"):
            continue
        cards.append({
            "target": link_target(link), "kind": "link", "thing": link["from_thing"],
            "title": link["label"], "column": f"{link['from']} = {link['to']}",
            "why": "spot_check" if link["review"] == "confirmed" else "unproven",
            "evidence": {"check": link["check"], "match": link.get("match"),
                         "proof": "; ".join(str(p) for p in link.get("proof") or [])},
            "claim": {"label": link["label"], "by": "engine"},
            "impact": round(_impact("reference", link.get("triples") or 0, 1), 2),
        })
    # Unproven first (they are the real gaps), then spot checks; each by impact.
    cards.sort(key=lambda c: (c["why"] != "unproven", -c["impact"], c["title"]))
    return {"ontology": view["id"], "counts": view["summary"]["review"],
            "cards": cards, "stats": stats(graph, ontology_id),
            "rejected_links": view.get("rejected_links") or []}


def _targets(view: dict) -> dict:
    """target -> (claim, thing name) for every field and link in the view."""
    out = {}
    for t in view["things"]:
        for f in t["fields"]:
            out[field_target(f)] = (field_claim(f), t["name"])
    for link in view["links"] + (view.get("rejected_links") or []):
        out[link_target(link)] = (link_claim(link), link["from_thing"])
    return out


def decide(layer, ontology_id: str, targets: list[str], decision: str, by: str = "you",
           thing: str | None = None, note: str = "") -> dict:
    """A person's decision on one or more claims (or every open one of a thing).

    Rejecting changes what every layer uses (a rejected field is held back from
    answers; a rejected link stops joining records), so it publishes a new
    version. Approving changes nothing but the record of who vouched for it."""
    from ontology import simple
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {', '.join(DECISIONS)}")
    graph = layer.graph
    view = simple.view(graph, ontology_id)
    known = _targets(view)
    if thing:
        # "Approve all in <thing>": only what is still open, never a
        # field a person set or the data contradicts. Spot checks stay
        # one by one, or the sample would measure nothing.
        wanted = {thing.lower()}
        targets = [field_target(f) for t in view["things"] if t["name"].lower() in wanted
                   for f in t["fields"] if f["review"] == "needs_you"]
        targets += [link_target(lk) for lk in view["links"] if lk["from_thing"].lower() in wanted
                    and lk["review"] == "needs_you"]
        if not targets:
            raise ValueError(f"nothing in {thing!r} is waiting for a decision")
    unknown = [t for t in targets if t not in known]
    if unknown:
        raise KeyError(f"no field or link {unknown[0]!r} in ontology {ontology_id!r}")
    if not targets:
        raise ValueError("say which field or link you decide on")
    spot_targets = {field_target(f) for t in view["things"] for f in t["fields"] if f.get("spot_check")}
    spot_targets |= {link_target(lk) for lk in view["links"] if lk.get("spot_check")}
    for target in dict.fromkeys(targets):
        claim, _ = known[target]
        reg.put(graph, ontology_id, "meaning", f"review:{target}",
                {"target": target, "decision": decision, "by": by, "at": _now(),
                 "claim": claim, "spot_check": target in spot_targets},
                fact=True, confidence=1.0, evidence=[f"{decision} by {by}"])
        reg._audit(graph, ontology_id, "review", target,
                   decision if target not in spot_targets else f"spot_{decision}", by, note)
    version = None
    if decision == "rejected":
        version = simple._republish(layer, ontology_id, f"{by} rejected {len(targets)} claim(s)")
    return {"decided": list(dict.fromkeys(targets)), "decision": decision, "version": version,
            **queue(graph, ontology_id)}


def undo(layer, ontology_id: str, target: str, by: str = "you") -> dict:
    """Take a decision back: the claim returns to its group."""
    from ontology import simple
    graph = layer.graph
    item = reg.get_item(graph, ontology_id, "meaning", f"review:{target}", missing_ok=True)
    if item is None:
        raise KeyError(f"no decision on {target!r}")
    with graph.lock:
        graph.con.execute("DELETE FROM eo_items WHERE ontology_id = ? AND kind = 'meaning'"
                          " AND key = ?", [ontology_id, f"review:{target}"])
    reg._audit(graph, ontology_id, "review", target, "undone", by, "")
    if item["payload"].get("decision") == "rejected":
        simple._republish(layer, ontology_id, f"{by} took back a rejection")
    return queue(graph, ontology_id)


def stats(graph, ontology_id: str) -> dict:
    """Strata's own numbers: how often people accept what it proposed, and how
    often a spot check found a confirmed item wrong."""
    rows = [a for a in reg.audit(graph, ontology_id) if a["kind"] == "review"]
    latest: dict = {}
    for a in rows:                               # the last word on each target counts
        latest[a["key"]] = a["decision"]
    final = [d for d in latest.values() if d != "undone"]
    approved = sum(d in ("approved", "spot_approved") for d in final)
    rejected = sum(d in ("rejected", "spot_rejected") for d in final)
    spot_ok = sum(d == "spot_approved" for d in final)
    spot_bad = sum(d == "spot_rejected" for d in final)
    return {"decisions": len(final), "approved": approved, "rejected": rejected,
            "acceptance_pct": round(100 * approved / len(final)) if final else None,
            "spot_checked": spot_ok + spot_bad,
            "checks_wrong_pct": round(100 * spot_bad / (spot_ok + spot_bad))
            if spot_ok + spot_bad else None}
