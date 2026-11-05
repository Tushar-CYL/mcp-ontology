"""Read the metadata people already have, so the ontology starts from it.

Three shapes cover what clients usually hand over:

* a **Power BI / Fabric semantic model** (``model.bim`` or any Tabular JSON):
  tables, column descriptions and data types, measures (DAX) and the
  relationships the model declares;
* a **dbt project file** (``schema.yml`` / ``models.yml``): model and column
  descriptions, and ``relationships`` tests as declared links;
* a **data dictionary** (CSV or Excel) with ``table``, ``column`` and
  ``description`` columns (``label`` and ``unit`` optional).

Everything comes back in one shape, so the rest of the system never learns
which tool the client uses::

    {"kind": "powerbi" | "dbt" | "dictionary", "file": "...",
     "tables": {table: {"description": str, "columns": {col: {...}}}},
     "relationships": [{"from_table", "from_column", "to_table", "to_column"}],
     "measures": [{"table", "name", "expression", "description"}]}
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

MODEL_FILES = {".bim", ".json"}
DBT_FILES = {".yml", ".yaml"}
DICTIONARY_FILES = {".csv", ".tsv", ".xlsx", ".xls"}
# Prefixes that modelling conventions add to a table name without changing
# what the table is (dim_customer is the customer table).
NAME_PREFIXES = ("dim_", "fact_", "fct_", "stg_", "int_", "vw_", "v_", "tbl_", "t_")


class MetadataError(ValueError):
    """A metadata file that cannot be read, with a reason a person can act on."""


def norm(name: str) -> str:
    """Compare names the way a person would: case, separators and the usual
    modelling prefixes ignored."""
    text = str(name or "").strip().rsplit(".", 1)[-1]
    # DimCustomer / FactSales: a Power BI prefix written in CamelCase.
    text = re.sub(r"^(Dim|Fact|Fct|Stg)(?=[A-Z])", lambda m: m.group(1) + "_", text)
    text = text.lower()
    for prefix in NAME_PREFIXES:
        if text.startswith(prefix) and len(text) > len(prefix) + 1:
            text = text[len(prefix):]
            break
    return re.sub(r"[^a-z0-9]", "", text)


def _empty(kind: str, path: Path) -> dict:
    return {"kind": kind, "file": path.name, "tables": {}, "relationships": [],
            "measures": []}


def _table(out: dict, name: str) -> dict:
    return out["tables"].setdefault(str(name), {"description": "", "columns": {}})


def _text(value) -> str:
    if isinstance(value, list):
        return " ".join(str(v) for v in value).strip()
    return str(value or "").strip()


# ------------------------------------------------------------- Power BI
def parse_tabular(data: dict, path: Path) -> dict:
    model = data.get("model", data)
    if not isinstance(model, dict) or not isinstance(model.get("tables"), list):
        raise MetadataError(f"{path.name} is JSON but not a semantic model "
                            "(no model.tables list)")
    out = _empty("powerbi", path)
    for t in model["tables"]:
        name = t.get("name")
        if not name or t.get("isHidden") and str(name).startswith(("DateTableTemplate",
                                                                   "LocalDateTable")):
            continue
        table = _table(out, name)
        table["description"] = _text(t.get("description"))
        for c in t.get("columns") or []:
            if c.get("type") == "rowNumber" or not c.get("name"):
                continue
            table["columns"][c["name"]] = {
                "description": _text(c.get("description")),
                "type": str(c.get("dataType") or ""),
                "label": "", "unit": "",
                "format": str(c.get("formatString") or ""),
                "source_column": str(c.get("sourceColumn") or c["name"]),
                "calculated": c.get("type") == "calculated"}
        for m in t.get("measures") or []:
            out["measures"].append({"table": name, "name": m.get("name", ""),
                                    "expression": _text(m.get("expression")),
                                    "description": _text(m.get("description")),
                                    "format": str(m.get("formatString") or "")})
    for r in model.get("relationships") or []:
        if not (r.get("fromTable") and r.get("toTable")):
            continue
        out["relationships"].append({
            "from_table": r["fromTable"], "from_column": r.get("fromColumn", ""),
            "to_table": r["toTable"], "to_column": r.get("toColumn", ""),
            "active": r.get("isActive", True) is not False})
    return out


# ------------------------------------------------------------------- dbt
_REF = re.compile(r"""ref\(\s*['"]([^'"]+)['"]""")


def parse_dbt(data: dict, path: Path) -> dict:
    if not isinstance(data, dict) or not any(k in data for k in ("models", "sources",
                                                                "semantic_models")):
        raise MetadataError(f"{path.name} is YAML but not a dbt file "
                            "(no models, sources or semantic_models)")
    out = _empty("dbt", path)
    models = list(data.get("models") or [])
    for src in data.get("sources") or []:
        models += list(src.get("tables") or [])
    for m in models:
        if not m.get("name"):
            continue
        table = _table(out, m["name"])
        table["description"] = _text(m.get("description"))
        for c in m.get("columns") or []:
            if not c.get("name"):
                continue
            meta = c.get("meta") or {}
            table["columns"][c["name"]] = {
                "description": _text(c.get("description")),
                "type": str(c.get("data_type") or ""),
                "label": str(meta.get("label") or ""), "unit": str(meta.get("unit") or "")}
            for test in (c.get("tests") or []) + (c.get("data_tests") or []):
                rel = test.get("relationships") if isinstance(test, dict) else None
                if isinstance(rel, dict) and rel.get("to"):
                    found = _REF.search(str(rel["to"]))
                    out["relationships"].append({
                        "from_table": m["name"], "from_column": c["name"],
                        "to_table": found.group(1) if found else str(rel["to"]),
                        "to_column": str(rel.get("field") or "id"), "active": True})
    for sm in data.get("semantic_models") or []:
        found = _REF.search(str(sm.get("model") or ""))
        table_name = found.group(1) if found else sm.get("name")
        if not table_name:
            continue
        for measure in sm.get("measures") or []:
            agg, expr = measure.get("agg", ""), measure.get("expr") or measure.get("name")
            out["measures"].append({"table": table_name, "name": measure.get("name", ""),
                                    "expression": f"{agg}({expr})" if agg else str(expr),
                                    "description": _text(measure.get("description"))})
    return out


# ------------------------------------------------------------ dictionary
_HEADERS = {
    "table": ("table", "table_name", "tablename", "entity", "object", "model", "dataset"),
    "column": ("column", "column_name", "columnname", "field", "field_name", "attribute"),
    "description": ("description", "definition", "meaning", "comment", "business_definition"),
    "label": ("label", "business_name", "display_name", "name_business"),
    "unit": ("unit", "units", "currency", "uom"),
}


def _rows_from_file(path: Path) -> list[dict]:
    if path.suffix.lower() in (".xlsx", ".xls"):
        import duckdb
        con = duckdb.connect(":memory:")
        try:
            try:
                rel = con.execute("SELECT * FROM read_xlsx(?, all_varchar=true)",
                                  [str(path)])
            except duckdb.Error:
                con.execute("INSTALL excel; LOAD excel")
                rel = con.execute("SELECT * FROM read_xlsx(?, all_varchar=true)",
                                  [str(path)])
            names = [d[0] for d in rel.description]
            return [dict(zip(names, r)) for r in rel.fetchall()]
        finally:
            con.close()
    text = path.read_text(encoding="utf-8-sig")
    dialect = csv.excel_tab if path.suffix.lower() == ".tsv" else csv.excel
    return list(csv.DictReader(text.splitlines(), dialect=dialect))


def parse_dictionary(path: Path) -> dict:
    rows = _rows_from_file(path)
    if not rows:
        raise MetadataError(f"{path.name} has no rows")
    headers = {re.sub(r"[^a-z_]", "", str(h).strip().lower().replace(" ", "_")): h
               for h in rows[0].keys() if h is not None}
    pick = {}
    for field, names in _HEADERS.items():
        pick[field] = next((headers[n] for n in names if n in headers), None)
    if not pick["column"] or not (pick["description"] or pick["label"]):
        raise MetadataError(
            f"{path.name}: a data dictionary needs a 'column' column and a "
            "'description' (or 'label') column; 'table' is recommended")
    out = _empty("dictionary", path)
    for r in rows:
        col = str(r.get(pick["column"]) or "").strip()
        if not col:
            continue
        table_name = str(r.get(pick["table"]) or "").strip() if pick["table"] else ""
        table = _table(out, table_name or "*")
        table["columns"][col] = {
            "description": str(r.get(pick["description"]) or "").strip()
            if pick["description"] else "",
            "label": str(r.get(pick["label"]) or "").strip() if pick["label"] else "",
            "unit": str(r.get(pick["unit"]) or "").strip() if pick["unit"] else "",
            "type": ""}
    return out


# ------------------------------------------------------------------ entry
def parse(path: str | Path) -> dict:
    """Read one metadata file (semantic model, dbt YAML or data dictionary)."""
    p = Path(path)
    if not p.exists():
        raise MetadataError(f"metadata file not found: {path}")
    suffix = p.suffix.lower()
    if p.is_dir():
        candidates = [f for f in sorted(p.rglob("*"))
                      if f.suffix.lower() in MODEL_FILES | DBT_FILES | DICTIONARY_FILES]
        if not candidates:
            raise MetadataError(f"no .bim, .yml or dictionary file in {path}")
        merged = None
        for f in candidates:
            try:
                one = parse(f)
            except MetadataError:
                continue
            merged = one if merged is None else merge(merged, one)
        if merged is None:
            raise MetadataError(f"none of the files in {path} is metadata Strata reads")
        return merged
    if suffix in MODEL_FILES:
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
        except ValueError as exc:
            raise MetadataError(f"{p.name} is not valid JSON: {exc}") from exc
        return parse_tabular(data, p)
    if suffix in DBT_FILES:
        import yaml
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise MetadataError(f"{p.name} is not valid YAML: {exc}") from exc
        return parse_dbt(data or {}, p)
    if suffix in DICTIONARY_FILES:
        return parse_dictionary(p)
    raise MetadataError(f"{p.name}: give a Power BI model (.bim), a dbt file (.yml) "
                        "or a data dictionary (.csv / .xlsx)")


def merge(a: dict, b: dict) -> dict:
    out = {"kind": a["kind"] if a["kind"] == b["kind"] else "mixed",
           "file": f"{a['file']}, {b['file']}", "tables": json.loads(json.dumps(a["tables"])),
           "relationships": a["relationships"] + b["relationships"],
           "measures": a["measures"] + b["measures"]}
    for name, t in b["tables"].items():
        mine = out["tables"].setdefault(name, {"description": "", "columns": {}})
        mine["description"] = mine["description"] or t["description"]
        for col, info in t["columns"].items():
            mine["columns"].setdefault(col, info)
    return out


def match_table(meta: dict, table: str) -> dict | None:
    """The metadata entry for a loaded table, matched by name."""
    want = norm(table)
    for name, t in meta.get("tables", {}).items():
        if name != "*" and norm(name) == want:
            return t
    return None


def column_info(meta: dict, table: str, column: str) -> dict | None:
    """What the metadata says about one column: the table's own entry first,
    then a dictionary row with no table (applies to that name anywhere)."""
    want = norm(column)
    entries = [match_table(meta, table), meta.get("tables", {}).get("*")]
    for entry in entries:
        if not entry:
            continue
        for name, info in entry["columns"].items():
            source = info.get("source_column") or name
            if norm(name) == want or norm(source) == want:
                return info
    return None
