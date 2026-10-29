"""Layer 3: propose the metrics a source can actually support.

Built from the ontology, so no dataset needs its own metric file. The
catalogue exists so that a number means ONE thing: the dashboard, the API
and the agent all compile from here rather than each writing their own
aggregate.

What matters as much as what IS proposed is what is NOT. A key is never
offered as a measure - summing customer ids is meaningless and looks
authoritative - and nothing is proposed that the columns cannot support.
A missing metric is a fact about the data; an invented one is a number
wearing a real metric's name.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ontology.discover import Ontology
from ontology.schema import is_numeric

# Aggregates worth offering for any number. Ordered, so the catalogue is
# identical on every run.
AGGS = (("sum", "sum"), ("avg", "avg"), ("min", "min"), ("max", "max"),
        ("p50", "median"), ("p99", "quantile_cont"))


@dataclass
class Metric:
    name: str
    title: str
    table: str
    column: str | None
    agg: str
    class_name: str
    provenance: str = "measured"
    dimensions: list[str] = field(default_factory=list)
    time_column: str | None = None


def discover_metrics(onto: Ontology) -> list[Metric]:
    out: list[Metric] = []
    for cls in onto.classes.values():
        # Every class can be counted. It is the one metric that needs no
        # numeric column and is almost always the first thing asked.
        out.append(Metric(
            name=f"{cls.name.lower()}_count",
            title=f"Number of {cls.name}",
            table=cls.table, column=None, agg="count",
            class_name=cls.name, dimensions=list(cls.dimensions),
            time_column=cls.time_column))

        for col in cls.measures:
            for suffix, fn in AGGS:
                out.append(Metric(
                    name=f"{col.lower()}_{suffix}",
                    title=f"{suffix} of {col} in {cls.name}",
                    table=cls.table, column=col, agg=fn,
                    class_name=cls.name, dimensions=list(cls.dimensions),
                    time_column=cls.time_column))
    return out


def measures_only(onto: Ontology) -> list[str]:
    """Columns that are genuinely numbers, for a quick summary."""
    return [f"{c.name}.{m}" for c in onto.classes.values() for m in c.measures]
