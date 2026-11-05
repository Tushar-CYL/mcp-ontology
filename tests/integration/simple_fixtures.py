"""Data from domains that are NOT sales, plus a fake AI model, for the
simple ontology flow tests.

* IoT: sites, devices and sensor readings (coordinates, temperatures,
  battery levels, status codes, a yes/no flag).
* Clinic: patients, doctors, visits (minutes, fees in EUR, diagnosis codes).

The fake model answers like the real one: one JSON object per table, keyed
by column name. It can be told to lie about a column, so the tests can prove
that a claim the data contradicts is shown as a conflict.
"""

from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from api.service import MiddleLayer


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def make_iot(root: Path, seed: int = 3) -> Path:
    rnd = random.Random(seed)
    folder = root / "iot"
    sites = [{"site_id": f"S{i:03d}", "site_name": f"Plant {name}",
              "country": country, "lat": round(lat, 5), "lng": round(lng, 5)}
             for i, (name, country, lat, lng) in enumerate([
                 ("Berlin", "DE", 52.52, 13.40), ("Lyon", "FR", 45.76, 4.84),
                 ("Pune", "IN", 18.52, 73.86), ("Austin", "US", 30.27, -97.74),
                 ("Osaka", "JP", 34.69, 135.50), ("Leeds", "GB", 53.80, -1.55)], start=1)]
    devices = []
    for i in range(1, 121):
        site = rnd.choice(sites)
        devices.append({"device_id": f"D{i:05d}", "site_id": site["site_id"],
                        "model": rnd.choice(["TX-100", "TX-200", "HV-9", "AQ-3"]),
                        "installed_on": (datetime(2022, 1, 1)
                                         + timedelta(days=rnd.randint(0, 700))).date().isoformat(),
                        "is_active": rnd.choice(["Y", "Y", "Y", "N"])})
    readings = []
    start = datetime(2025, 1, 1)
    for i in range(1, 4001):
        d = rnd.choice(devices)
        readings.append({"reading_id": i, "device_id": d["device_id"],
                         "read_at": (start + timedelta(minutes=17 * i)).isoformat(" "),
                         "temp_c": round(rnd.uniform(-5, 85), 2),
                         "battery_pct": rnd.randint(5, 100),
                         "status_code": rnd.choice(["OK", "OK", "OK", "WARN", "FAIL"])})
    write_csv(folder / "sites.csv", sites)
    write_csv(folder / "devices.csv", devices)
    write_csv(folder / "readings.csv", readings)
    return folder


def make_clinic(root: Path, seed: int = 5) -> Path:
    rnd = random.Random(seed)
    folder = root / "clinic"
    patients = [{"pat_no": 1000 + i, "full_name": f"Patient {i}",
                 "birth_dt": (datetime(1940, 1, 1)
                              + timedelta(days=rnd.randint(0, 25000))).date().isoformat(),
                 "city": rnd.choice(["Madrid", "Porto", "Lisbon", "Seville", "Valencia"])}
                for i in range(1, 301)]
    doctors = [{"doc_id": f"DR{i:02d}", "doc_name": f"Dr {name}", "speciality": spec}
               for i, (name, spec) in enumerate([
                   ("Alves", "Cardiology"), ("Moreno", "Dermatology"),
                   ("Costa", "General"), ("Ruiz", "Paediatrics"),
                   ("Silva", "General"), ("Garcia", "Cardiology")], start=1)]
    visits = []
    for i in range(1, 1501):
        visits.append({"visit_id": f"V{i:06d}", "pat_no": rnd.choice(patients)["pat_no"],
                       "doc_id": rnd.choice(doctors)["doc_id"],
                       "visit_dt": (datetime(2024, 1, 1)
                                    + timedelta(hours=7 * i)).isoformat(" "),
                       "mins": rnd.choice([10, 15, 20, 30, 45]),
                       "fee_eur": round(rnd.uniform(30, 250), 2),
                       "icd10": rnd.choice(["I10", "E11", "J45", "L20", "Z00", "M54"])})
    write_csv(folder / "patients.csv", patients)
    write_csv(folder / "doctors.csv", doctors)
    write_csv(folder / "visits.csv", visits)
    return folder


def load(tmp_path: Path, which=("iot",)) -> MiddleLayer:
    layer = MiddleLayer(str(tmp_path / "simple.duckdb"))
    makers = {"iot": make_iot, "clinic": make_clinic}
    for name in which:
        layer.add_source(str(makers[name](tmp_path / "data")), source=name)
    return layer


# What a good model says about these tables (the truth for the tests).
TRUTH = {
    "sites": {"thing": "Site", "columns": {
        "site_id": ("Site ID", "identifier", None), "site_name": ("Site name", "name", None),
        "country": ("Country", "category", None), "lat": ("Latitude", "location", None),
        "lng": ("Longitude", "location", None)}},
    "devices": {"thing": "Device", "columns": {
        "device_id": ("Device ID", "identifier", None), "site_id": ("Site", "reference", None),
        "model": ("Device model", "category", None),
        "installed_on": ("Installation date", "date", None),
        "is_active": ("Active", "flag", None)}},
    "readings": {"thing": "Sensor Reading", "columns": {
        "reading_id": ("Reading ID", "identifier", None),
        "device_id": ("Device", "reference", None),
        "read_at": ("Reading time", "date", None),
        "temp_c": ("Temperature", "measure", "°C"),
        "battery_pct": ("Battery level", "measure", "%"),
        "status_code": ("Status", "category", None)}},
    "patients": {"thing": "Patient", "columns": {
        "pat_no": ("Patient number", "identifier", None),
        "full_name": ("Patient name", "name", None),
        "birth_dt": ("Date of birth", "date", None), "city": ("City", "location", None)}},
    "doctors": {"thing": "Doctor", "columns": {
        "doc_id": ("Doctor ID", "identifier", None), "doc_name": ("Doctor name", "name", None),
        "speciality": ("Speciality", "category", None)}},
    "visits": {"thing": "Visit", "columns": {
        "visit_id": ("Visit ID", "identifier", None),
        "pat_no": ("Patient", "reference", None), "doc_id": ("Doctor", "reference", None),
        "visit_dt": ("Visit time", "date", None), "mins": ("Duration", "measure", "minutes"),
        "fee_eur": ("Fee", "amount", "EUR"), "icd10": ("Diagnosis code", "category", None)}},
}


class FakeAI:
    """Stands in for the EYQ client. `lies` maps column -> role to claim."""

    mock = False
    model = "fake-model"

    def __init__(self, lies: dict | None = None, fail_tables: set | None = None,
                 note_reply: dict | None = None):
        self.lies = lies or {}
        self.fail_tables = fail_tables or set()
        self.note_reply = note_reply
        self.calls: list[dict] = []

    def complete(self, messages, max_tokens=1200):
        prompt = messages[-1]["content"]
        if prompt.startswith("ONTOLOGY:"):
            self.calls.append({"kind": "note"})
            return json.dumps(self.note_reply or {"edits": [], "reply": "no change"})
        facts = json.loads(prompt.split("FACTS:\n", 1)[1])
        table = facts["table"]["name"]
        self.calls.append({"kind": "table", "table": table, "facts": facts})
        if table in self.fail_tables:
            raise RuntimeError("model unavailable")
        truth = TRUTH.get(table, {"thing": table.title(), "columns": {}})
        cols = []
        for c in facts["table"]["columns"]:
            label, role, unit = truth["columns"].get(c["name"], (c["name"], "text", None))
            role = self.lies.get(c["name"], role)
            cols.append({"name": c["name"], "label": label,
                         "meaning": f"The {label.lower()} (from the model).",
                         "role": role, "unit": unit, "confidence": "high"})
        cols.append({"name": "not_a_column", "label": "x", "meaning": "x", "role": "text"})
        return "```json\n" + json.dumps({"thing": {"name": truth["thing"],
                                                   "description": f"One {truth['thing']}."},
                                         "columns": cols}) + "\n```"
