"""Remember what is read often and changes rarely: the ontology view and the
graph model built from it.

Every layer starts from the same two reads: `simple.view` (the ontology in
plain words) and `knowledge_graph.explore.model` (the tables and links behind
it, which needs one DESCRIBE per table). Context alone asked for them about a
dozen times per question.

A cached value is used only while the data it came from is unchanged. That is
checked on every call with one cheap query - a fingerprint of the ontology's
registry rows (every kind, key, status and payload), its versions, its
sources and when each source was last loaded - so an edit, a note, a rebuild
or a reload is seen at once, from this process or any other writer. Nothing
has to remember to clear the cache, which is what makes it safe. Callers get
their own copy, so changing what they were given cannot change the cache.
"""

from __future__ import annotations

import copy
import threading
import time
import uuid
from collections import OrderedDict

MAX_ENTRIES = 64
_entries: OrderedDict = OrderedDict()
_lock = threading.Lock()
stats = {"hits": 0, "misses": 0}

_STAMP = """
SELECT (SELECT count(*) FROM eo_items WHERE ontology_id = ?),
       (SELECT coalesce(sum(hash(kind, key, status, payload, coalesce(updated_at, ''))), 0)
          FROM eo_items WHERE ontology_id = ?),
       (SELECT coalesce(max(version), 0) FROM eo_versions WHERE ontology_id = ?),
       (SELECT coalesce(string_agg(source_id, ',' ORDER BY source_id), '')
          FROM eo_sources WHERE ontology_id = ?),
       (SELECT coalesce(string_agg(source_id || '@' || coalesce(CAST(built_at AS VARCHAR), '')
                                   || '#' || coalesce(signature, ''), ',' ORDER BY source_id), '')
          FROM sources)
"""


def stamp(graph, ontology_id: str) -> tuple:
    """A fingerprint of everything the view and the model are made from."""
    return tuple(graph.sql(_STAMP, [ontology_id] * 4)[0])


def _token(graph) -> str:
    """Which open database this is. Not id(): ids are reused once an object
    is gone, and two test databases with the same content would share one."""
    tok = getattr(graph, "_cache_token", None)
    if tok is None:
        tok = uuid.uuid4().hex
        graph._cache_token = tok
    return tok


def remember(graph, name: str, ontology_id: str, extra: tuple, make, keep=None,
             ttl: float | None = None):
    """`make()`'s value, reused while the ontology and its data are unchanged.
    `keep(value)` False means do not remember it (a passing failure, such as a
    source that could not be opened this time, must not stick). `ttl` seconds
    bounds how old a value may be even when the registry did not change: record
    counts of a live database move without anyone reloading it."""
    key = (_token(graph), name, ontology_id, extra)
    now = stamp(graph, ontology_id)
    with _lock:
        hit = _entries.get(key)
        if hit is not None and hit[0] == now and (ttl is None or time.monotonic() - hit[2] < ttl):
            _entries.move_to_end(key)
            stats["hits"] += 1
            return copy.deepcopy(hit[1])
    value = make()
    if keep is not None and not keep(value):
        return value
    with _lock:
        stats["misses"] += 1
        _entries[key] = (now, value, time.monotonic())
        _entries.move_to_end(key)
        while len(_entries) > MAX_ENTRIES:
            _entries.popitem(last=False)
    return copy.deepcopy(value)


def forget() -> None:
    with _lock:
        _entries.clear()
