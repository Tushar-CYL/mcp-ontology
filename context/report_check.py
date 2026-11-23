"""Report check: does Strata give the numbers the client's own reports give?

A check is one number from a real report ("Order lines with Incoterms DDP:
1,466,849 - Q3 sales report, page 2") plus the ways people ask for it. The
run asks Strata each phrasing (the same pipeline the screen and agents use),
reads the number from the data table it computed (never from the AI's
wording) and scores it the way the industry does: the result matches the
report to the report's precision (4 significant digits by default), with a
separate unit check, because a number 1,000 times off is the classic silent
failure. Questions that *should* be refused are checks too.

Checks are never written into notes or verified questions, so the test does
not leak into what it measures.

Scorecard: accuracy, accuracy from certified metrics vs other answers,
refusals done right, agreement across phrasings, and the count of silent
wrong numbers (wrong and not flagged) - the one that must be zero.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import math
import re
import time
import uuid
from datetime import datetime, timezone

MAX_CHECKS = 300
MAX_PHRASINGS = 4
VERDICTS = {
    "pass": "Matches the report",
    "wrong": "Different number",
    "unit": "Unit or scale is off",
    "no_number": "No number came back",
    "refused_ok": "Refused, as it should",
    "should_refuse": "Answered, but should have refused",
    "error": "Could not run",
}

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS ctx_checks (
        id VARCHAR PRIMARY KEY, ontology_id VARCHAR NOT NULL, question VARCHAR NOT NULL,
        phrasings JSON, expected DOUBLE, row_label VARCHAR, unit VARCHAR, digits INTEGER,
        refuse BOOLEAN, source VARCHAR, created_at VARCHAR)""",
    """CREATE TABLE IF NOT EXISTS ctx_check_runs (
        id VARCHAR PRIMARY KEY, ontology_id VARCHAR NOT NULL, run_at VARCHAR,
        summary JSON, results JSON)""",
)


class CheckError(ValueError):
    """A check that cannot be saved or run, in plain words."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure(graph) -> None:
    if getattr(graph, "_ctx_checks_ready", False):
        return
    with graph.lock:
        for sql in _SCHEMA:
            graph.con.execute(sql)
    graph._ctx_checks_ready = True


# ------------------------------------------------------------- the checks
def _number(value) -> float | None:
    """'1,466,849', '1.5M', '63 %', '(120)', '€ 4.2k' -> a float, else None."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip().replace(" ", " ")
    neg = text.startswith("(") and text.endswith(")")
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?|-?\.\d+", text)
    if not m:
        return None
    n = float(m.group(0).replace(",", ""))
    tail = text[m.end():].strip().lower()
    scale = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6,
             "bn": 1e9, "b": 1e9, "billion": 1e9}
    for word, mult in scale.items():
        if re.match(rf"{word}\b", tail):
            n *= mult
            break
    return -n if neg else n


def written_digits(value) -> int | None:
    """The precision a report wrote a rounded number with: "1.79M" is 3
    significant digits, "500.9k" is 4. Only numbers with a scale word count
    (a plain "400" could be exact or rounded, so the default stays)."""
    text = str(value or "")
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|m|mn|million|bn|b|billion)\b", text, re.I)
    if not m:
        return None
    digits = m.group(1).replace(",", "").replace(".", "").lstrip("0")
    return len(digits) or None


def _clean(check: dict) -> dict:
    question = str(check.get("question") or "").strip()
    if not question:
        raise CheckError("each check needs a question")
    if len(question) > 1000:
        raise CheckError("keep each question under 1,000 characters")
    raw = check.get("phrasings") or []
    if isinstance(raw, str):
        raw = raw.split("|")
    phrasings = [str(p).strip() for p in raw if str(p).strip() and str(p).strip() != question]
    refuse = str(check.get("refuse") or check.get("should_refuse") or "").strip().lower() \
        in ("1", "true", "yes", "y", "refuse")
    expected = _number(check.get("expected"))
    if expected is None and not refuse:
        raise CheckError(f"say the number the report gives for: {question[:80]}")
    digits = check.get("digits")
    digits = int(_number(digits) or 4) if digits not in (None, "")         else min(4, written_digits(check.get("expected")) or 4)
    if not 1 <= digits <= 12:
        raise CheckError("precision must be 1 to 12 significant digits")
    return {"question": question, "phrasings": phrasings[:MAX_PHRASINGS],
            "expected": None if refuse else expected,
            "row_label": str(check.get("row_label") or check.get("row") or "").strip() or None,
            "unit": str(check.get("unit") or "").strip() or None, "digits": digits,
            "refuse": refuse, "source": str(check.get("source") or "").strip()[:300] or None}


def _row(r) -> dict:
    (cid, oid, question, phrasings, expected, label, unit, digits, refuse, source, at) = r
    return {"id": cid, "ontology": oid, "question": question,
            "phrasings": json.loads(phrasings or "[]"), "expected": expected,
            "row_label": label, "unit": unit, "digits": digits, "refuse": bool(refuse),
            "source": source, "created_at": at}


def checks(graph, ontology_id: str) -> list[dict]:
    ensure(graph)
    return [_row(r) for r in graph.sql(
        "SELECT id, ontology_id, question, phrasings, expected, row_label, unit, digits,"
        " refuse, source, created_at FROM ctx_checks WHERE ontology_id = ?"
        " ORDER BY created_at, id", [ontology_id])]


def add(graph, ontology_id: str, items: list[dict]) -> list[dict]:
    """Save checks (all or none: a bad row names itself)."""
    ensure(graph)
    from ontology import registry as reg
    reg.get(graph, ontology_id)
    if not items:
        raise CheckError("give at least one check")
    clean = []
    for i, item in enumerate(items, 1):
        try:
            clean.append(_clean(item))
        except CheckError as exc:
            raise CheckError(f"row {i}: {exc}") from exc
    if len(checks(graph, ontology_id)) + len(clean) > MAX_CHECKS:
        raise CheckError(f"keep it to {MAX_CHECKS} checks per ontology")
    at = _now()
    with graph.lock:
        for c in clean:
            graph.con.execute(
                "INSERT INTO ctx_checks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ["chk_" + uuid.uuid4().hex[:10], ontology_id, c["question"],
                 json.dumps(c["phrasings"]), c["expected"], c["row_label"], c["unit"],
                 c["digits"], c["refuse"], c["source"], at])
    return checks(graph, ontology_id)


def remove(graph, ontology_id: str, check_id: str) -> list[dict]:
    ensure(graph)
    if not any(c["id"] == check_id for c in checks(graph, ontology_id)):
        raise KeyError(f"no check {check_id!r}")
    with graph.lock:
        graph.con.execute("DELETE FROM ctx_checks WHERE ontology_id = ? AND id = ?",
                          [ontology_id, check_id])
    return checks(graph, ontology_id)


COLUMNS = {"question": "question", "expected": "expected", "number": "expected",
           "report value": "expected", "value": "expected", "row": "row_label",
           "row label": "row_label", "unit": "unit", "digits": "digits",
           "precision": "digits", "should refuse": "refuse", "refuse": "refuse",
           "other phrasings": "phrasings", "phrasings": "phrasings", "source": "source"}


def parse_file(name: str, content: str) -> list[dict]:
    """A CSV (text) or an Excel workbook (base64) with one check per row.
    Columns: question, expected, row, unit, digits, should refuse, other
    phrasings (separated by |), source."""
    if str(name).lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        try:
            wb = load_workbook(io.BytesIO(base64.b64decode(content)), read_only=True, data_only=True)
        except Exception as exc:                   # noqa: BLE001 - said plainly
            raise CheckError(f"could not read the workbook: {exc}") from exc
        rows = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    else:
        rows = list(csv.reader(io.StringIO(content)))
    rows = [r for r in rows if any(str(c or "").strip() for c in r)]
    if len(rows) < 2:
        raise CheckError("the file needs a header row and at least one check")
    head = [COLUMNS.get(str(h or "").strip().lower()) for h in rows[0]]
    if "question" not in head:
        raise CheckError("the file needs a 'question' column")
    out = []
    for r in rows[1:]:
        item = {}
        for key, cell in zip(head, r):
            if key and cell not in (None, ""):
                item[key] = cell
        out.append(item)
    return out


# ------------------------------------------------------------------ score
def close(got: float, want: float, digits: int) -> bool:
    """Equal to `digits` significant digits (the report's precision)."""
    if want == 0:
        return abs(got) < 1e-9
    step = 10 ** (math.floor(math.log10(abs(want))) - digits + 1)
    return abs(got - want) <= step / 2 + 1e-9 * abs(want)


def unit_off(got: float, want: float, digits: int) -> int | None:
    """The power of ten the answer is off by (thousands vs units, %, ...)."""
    if not got or not want:
        return None
    for k in (1, 2, 3, 6, 9, -1, -2, -3, -6, -9):
        if close(got, want * 10 ** k, digits):
            return k
    return None


def _cell_number(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def pick(table: dict | None, label: str | None) -> tuple[float | None, str]:
    """The number a question's result gives: the last numeric cell of the row
    named by `label`, or of the only row."""
    if not table or not table.get("rows"):
        return None, "no result table"
    rows = table["rows"]
    if label:
        want = label.strip().lower()
        for row in rows:
            if any(str(c).strip().lower() == want for c in row):
                nums = [n for n in (_cell_number(c) for c in row) if n is not None]
                if nums:
                    return nums[-1], "row " + label
        return None, f"no row called {label!r} in the result"
    if len(rows) > 1:
        return None, f"{len(rows)} rows came back; say which row the report means"
    nums = [n for n in (_cell_number(c) for c in rows[0]) if n is not None]
    return (nums[-1], "the only row") if nums else (None, "no number in the result")


def score(check: dict, built: dict) -> dict:
    """One phrasing's verdict."""
    facts = built["steps"]["facts"]
    table = facts.get("table")
    said = built["steps"]["answer"]
    certified = bool(facts.get("metric"))
    got, how = pick(table, check["row_label"])
    if check["refuse"]:
        verdict = "refused_ok" if got is None else "should_refuse"
    elif got is None:
        verdict = "no_number"
    elif close(got, check["expected"], check["digits"]):
        verdict = "pass"
    elif unit_off(got, check["expected"], check["digits"]) is not None:
        verdict = "unit"
    else:
        verdict = "wrong"
    # Loud: Strata itself said something is off (no number, an unchecked
    # number flagged, a refusal). Silent: a wrong number shown as an answer.
    flagged = said.get("status") in ("unverified", "not_enough") or got is None
    return {"got": got, "how": how, "verdict": verdict, "label": VERDICTS[verdict],
            "certified": certified, "metric": (facts.get("metric") or {}).get("title"),
            "silent": verdict in ("wrong", "unit", "should_refuse") and not flagged,
            "sql": facts.get("sql")}


def run(layer, ontology_id: str, client=None, progress=None) -> dict:
    """Ask every phrasing of every check; save and return the scorecard."""
    from context import engine as ctx
    graph = layer.graph
    todo = checks(graph, ontology_id)
    if not todo:
        raise CheckError("add a check first: a number from one of your reports")
    say = progress or (lambda _line: None)
    started = time.perf_counter()
    results = []
    for i, check in enumerate(todo, 1):
        say(f"Check {i} of {len(todo)}: {check['question'][:80]}")
        answers = []
        for phrasing in [check["question"], *check["phrasings"]]:
            t = time.perf_counter()
            try:
                built = ctx.build(layer, ontology_id, phrasing, client=client, phrase=False)
                one = score(check, built)
            except Exception as exc:               # noqa: BLE001 - one bad question is a verdict
                one = {"got": None, "how": str(exc)[:200], "verdict": "error",
                       "label": VERDICTS["error"], "certified": False, "metric": None,
                       "silent": False, "sql": None}
            answers.append({"phrasing": phrasing, **one,
                            "ms": round((time.perf_counter() - t) * 1000)})
        got = {a["got"] for a in answers if a["got"] is not None}
        ok = {"pass", "refused_ok"}
        results.append({"id": check["id"], "question": check["question"],
                        "expected": check["expected"], "unit": check["unit"],
                        "row_label": check["row_label"], "refuse": check["refuse"],
                        "source": check["source"], "answers": answers,
                        "passed": all(a["verdict"] in ok for a in answers),
                        "agree": len(got) <= 1 and len({a["verdict"] for a in answers}) == 1})
    summary = summarize(results)
    summary["seconds"] = round(time.perf_counter() - started, 1)
    run_id = "run_" + uuid.uuid4().hex[:10]
    at = _now()
    ensure(graph)
    with graph.lock:
        graph.con.execute("INSERT INTO ctx_check_runs VALUES (?, ?, ?, ?, ?)",
                          [run_id, ontology_id, at, json.dumps(summary),
                           json.dumps(results, default=str)])
    say(f"Done: {summary['passed']} of {summary['checks']} checks match the reports")
    return {"id": run_id, "at": at, "summary": summary, "results": results}


def _pct(a: int, b: int) -> int | None:
    return round(100 * a / b) if b else None


def summarize(results: list[dict]) -> dict:
    answers = [a for r in results for a in r["answers"]]
    numbers = [a for r in results if not r["refuse"] for a in r["answers"]]
    refusals = [a for r in results if r["refuse"] for a in r["answers"]]
    cert = [a for a in numbers if a["certified"]]
    other = [a for a in numbers if not a["certified"]]
    return {
        "checks": len(results), "asked": len(answers),
        "passed": sum(r["passed"] for r in results),
        "accuracy_pct": _pct(sum(a["verdict"] == "pass" for a in numbers), len(numbers)),
        "certified": {"asked": len(cert), "pct": _pct(sum(a["verdict"] == "pass" for a in cert), len(cert))},
        "other": {"asked": len(other), "pct": _pct(sum(a["verdict"] == "pass" for a in other), len(other))},
        "refusals": {"asked": len(refusals),
                     "pct": _pct(sum(a["verdict"] == "refused_ok" for a in refusals), len(refusals))},
        "agreement_pct": _pct(sum(r["agree"] for r in results if len(r["answers"]) > 1),
                              sum(len(r["answers"]) > 1 for r in results)),
        "silent_wrong": sum(a["silent"] for a in answers),
        "verdicts": {k: sum(a["verdict"] == k for a in answers) for k in VERDICTS},
    }


def runs(graph, ontology_id: str, limit: int = 10) -> list[dict]:
    ensure(graph)
    return [{"id": r[0], "at": r[1], "summary": json.loads(r[2] or "{}")}
            for r in graph.sql("SELECT id, run_at, summary FROM ctx_check_runs WHERE ontology_id = ?"
                               " ORDER BY run_at DESC, id DESC LIMIT ?", [ontology_id, limit])]


def last_run(graph, ontology_id: str) -> dict | None:
    ensure(graph)
    rows = graph.sql("SELECT id, run_at, summary, results FROM ctx_check_runs WHERE ontology_id = ?"
                     " ORDER BY run_at DESC, id DESC LIMIT 1", [ontology_id])
    if not rows:
        return None
    r = rows[0]
    return {"id": r[0], "at": r[1], "summary": json.loads(r[2] or "{}"),
            "results": json.loads(r[3] or "[]")}


def overview(graph, ontology_id: str) -> dict:
    from ontology import registry as reg
    reg.get(graph, ontology_id)
    return {"checks": checks(graph, ontology_id), "last_run": last_run(graph, ontology_id),
            "history": runs(graph, ontology_id), "verdicts": VERDICTS}
