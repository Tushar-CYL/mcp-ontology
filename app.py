"""The middle layer, as a demo.

    streamlit run app.py

Point it at any data source and look at what comes out. Nothing in here
knows what your data is about.

No pandas anywhere, deliberately. Locked-down machines block unsigned
native libraries - Windows Application Control refuses pandas' compiled
DLLs - and st.dataframe converts through pandas, so the app checks once
and falls back to markdown. A plainer table beats a dead demo.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from context.budget import Fact, fit, render
from knowledge_graph.build import build, is_current, row_for, source_rows
from knowledge_graph.store import open_graph
from ontology.connect import SourceError, connect
from ontology.discover import discover
from semantic.compile import compile_metric
from semantic.discover import discover_metrics

st.set_page_config(page_title="Middle layer", page_icon=":material/hub:",
                   layout="wide")

GRAPH_DIR = Path("data/graphs")
BUDGET = 1200


# ------------------------------------------------------------- plumbing
@st.cache_resource(show_spinner=False)
def _pandas_works() -> bool:
    try:
        import pandas  # noqa: F401
        return True
    except Exception:
        return False


def table(rows: list[dict], alt: str = "", height=None) -> None:
    """A table, however this machine can draw one."""
    if not rows:
        st.caption("_nothing to show_")
        return
    if _pandas_works():
        st.dataframe(rows, hide_index=True, alt=alt, height=height)
        return
    cols = list(rows[0])
    out = ["| " + " | ".join(str(c) for c in cols) + " |",
           "| " + " | ".join("---" for _ in cols) + " |"]
    for r in rows[:200]:
        out.append("| " + " | ".join(
            str(r.get(c, "")).replace("|", r"\|") for c in cols) + " |")
    st.markdown("\n".join(out))
    if len(rows) > 200:
        st.caption(f"showing 200 of {len(rows):,}")


@st.cache_resource(show_spinner=False)
def load(source: str, _token: int):
    schema = connect(source)
    onto = discover(schema)
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    name = "".join(c if c.isalnum() else "_" for c in source)[-60:]
    graph = open_graph(GRAPH_DIR / f"{name}.duckdb")
    # Already built from this exact source and ontology? Open it, do not
    # rebuild it. Redoing correct work reads as broken, not as thorough.
    if is_current(graph, schema, onto):
        stats = {"nodes": graph.one("SELECT count(*) FROM nodes") or 0,
                 "edges": graph.one("SELECT count(*) FROM edges") or 0,
                 "cached": True}
    else:
        stats = build(graph, schema, onto)
        stats["cached"] = False
    return schema, onto, graph, stats


def diagram(onto) -> str:
    """Boxes are things, arrows are links. A dashed arrow is a guess -
    visible at a glance, not buried in a column."""
    out = ["digraph {", '  rankdir=LR; bgcolor="transparent";',
           '  node [shape=box style="rounded,filled" fillcolor="#eef2ff"',
           '        color="#4f46e5" fontname="Helvetica" fontsize=11];',
           '  edge [fontname="Helvetica" fontsize=9];']
    for c in onto.classes.values():
        out.append(f'  "{c.name}";')
    for r in onto.relations.values():
        stated = r.provenance == "measured"
        colour = "#0f766e" if stated else "#b45309"
        out.append(f'  "{r.domain}" -> "{r.range}" [label="{r.name}" '
                   f'style={"solid" if stated else "dashed"} '
                   f'color="{colour}" fontcolor="{colour}"];')
    return "\n".join(out + ["}"])


def network(cls: str, key: str, reached: list[str]) -> dict:
    nodes = [{"name": f"{cls}:{key}", "symbolSize": 44,
              "itemStyle": {"color": "#4f46e5"}}]
    links = []
    for r in reached[:50]:
        nodes.append({"name": r, "symbolSize": 20})
        links.append({"source": f"{cls}:{key}", "target": r})
    return {"tooltip": {}, "series": [{
        "type": "graph", "layout": "force", "roam": True,
        "label": {"show": True, "position": "right", "fontSize": 10},
        "force": {"repulsion": 230, "edgeLength": 95},
        "data": nodes, "links": links}]}


# ----------------------------------------------------------------- page
st.title("The middle layer")

with st.sidebar:
    source = st.text_input("Data source", value="data/raw/kaggledata")
    st.caption("A database file, a folder of CSVs, one file, or a "
               "`postgres://` URL.")
    if "token" not in st.session_state:
        st.session_state.token = 0
    if st.button("Rebuild", icon=":material/refresh:", width="stretch"):
        st.session_state.token += 1
        load.clear()

if not source:
    st.info("Enter a data source on the left.", icon=":material/west:")
    st.stop()

try:
    with st.spinner("Reading the source…"):
        schema, onto, graph, stats = load(source, st.session_state.token)
except SourceError as e:
    st.error(str(e), icon=":material/error:")
    st.stop()
except Exception as e:
    st.error(f"Could not read this source.\n\n{e}", icon=":material/error:")
    st.stop()

guessed = sum(1 for r in onto.relations.values() if r.provenance != "measured")
c = st.columns(4, border=True)
c[0].metric("Tables", len(schema.tables))
c[1].metric("Kinds of thing", len(onto.classes))
c[2].metric("Things", f"{stats['nodes']:,}")
c[3].metric("Connections", f"{stats['edges']:,}")

tabs = st.tabs(["Your data", "What's in it", "Connections", "Numbers",
                "Answer"])

# -------------------------------------------------------- YOUR DATA
with tabs[0]:
    st.subheader("Your data, as it is")
    names = [t.name for t in schema.tables]
    picked = st.selectbox("Table", names)
    t = schema.table(picked)
    st.caption(f"{t.row_count:,} rows · {len(t.columns)} columns"
               if t.row_count else f"{len(t.columns)} columns")
    n = st.slider("Rows to show", 5, 200, 25, step=5)
    try:
        cols, rows = source_rows(graph, schema, picked, limit=n)
        table([dict(zip(cols, r)) for r in rows],
              alt=f"Rows from {picked}")
    except Exception as e:
        st.error(f"Could not read this table.\n\n{e}",
                 icon=":material/error:")

# ------------------------------------------------------ WHAT'S IN IT
with tabs[1]:
    st.subheader("What exists, and what links to what")
    st.caption("Worked out from the source. Nothing was configured.")

    left, right = st.columns([3, 2])
    with left:
        st.graphviz_chart(
            diagram(onto),
            alt="Boxes are kinds of thing, arrows are links. Dashed arrows "
                "were guessed rather than declared by the source.")
        st.caption("solid = the source declared it · dashed = we worked it out")
    with right:
        table([{
            "thing": c_.name,
            "from table": c_.table,
            "identified by": c_.key + (" (made up)" if c_.key_is_synthetic
                                       else ""),
            "dated by": c_.time_column or "—",
        } for c_ in onto.classes.values()], alt="Kinds of thing found")

    if onto.relations:
        table([{
            "link": r.name, "from": r.domain, "to": r.range,
            "how": "stated" if r.provenance == "measured" else "guessed",
            "sure": f"{r.confidence:.0%}",
        } for r in onto.relations.values()], alt="Links between things")
        if guessed:
            st.info(
                f"{guessed} of {len(onto.relations)} links were guessed from "
                "column names. This source does not declare its keys — most "
                "CSV exports cannot — so these are strong inferences, not "
                "facts, and they are labelled that way everywhere.",
                icon=":material/info:")
    else:
        st.warning("No links found: no foreign keys, and no columns named "
                   "after other tables.", icon=":material/link_off:")

# -------------------------------------------------------- CONNECTIONS
with tabs[2]:
    st.subheader("Follow the connections")
    classes = sorted(onto.classes)
    a, b, d = st.columns([1, 2, 1], vertical_alignment="bottom")
    cls = a.selectbox("Kind", classes)
    keys = sorted(graph.keys_of(cls))[:300] if cls else []
    key = b.selectbox("Which one", keys) if keys else None
    depth = d.slider("Hops", 1, 4, 2)

    if not key:
        st.info("Nothing of this kind was built.", icon=":material/info:")
    else:
        row = row_for(graph, schema, onto, cls, key)
        if row:
            st.markdown("**Its actual row in your data**")
            table([{k: str(v) for k, v in row.items()}],
                  alt=f"The source row behind {cls} {key}")

        reached = sorted(graph.reach(cls, key, None, depth=depth))
        st.markdown(f"**Reaches {len(reached)} things within "
                    f"{depth} hop{'s' if depth > 1 else ''}**")
        if reached:
            st.echarts_chart(network(cls, key, reached),
                             alt=f"{cls} {key} and what it connects to",
                             height=420)
            table([{"kind": r.split(":", 1)[0], "which": r.split(":", 1)[1]}
                   for r in reached[:200]], alt="What it reaches")

# ------------------------------------------------------------ NUMBERS
with tabs[3]:
    st.subheader("What you can measure")
    metrics = discover_metrics(onto)
    st.caption(f"{len(metrics)} metrics, all from columns actually present. "
               "A source with no numbers gets counts and nothing else.")

    m1, m2 = st.columns(2, vertical_alignment="bottom")
    chosen = m1.selectbox("Metric", [m.name for m in metrics])
    metric = next(m for m in metrics if m.name == chosen)
    group = m2.selectbox("Group by", ["(none)"] + sorted(metric.dimensions))

    sql, params = compile_metric(metric,
                                 group_by=None if group == "(none)" else group)
    try:
        rows = graph.sql(sql, params)
        if group != "(none)" and rows:
            st.echarts_chart({
                "tooltip": {},
                "xAxis": {"type": "category",
                          "data": [str(r[0]) for r in rows],
                          "axisLabel": {"rotate": 30}},
                "yAxis": {"type": "value"},
                "series": [{"type": "bar", "data": [r[1] for r in rows],
                            "itemStyle": {"color": "#4f46e5"}}],
            }, alt=f"{metric.title} by {group}", height=320)
            table([{group: str(r[0]), "value": r[1]} for r in rows],
                  alt=metric.title)
        else:
            table([{"value": r[0]} for r in rows], alt=metric.title)
    except Exception as e:
        st.error(f"Could not compute this.\n\n{e}", icon=":material/error:")

    with st.expander("The SQL this produced"):
        st.code(sql, language="sql")

# ------------------------------------------------------------- ANSWER
with tabs[4]:
    st.subheader("One packed answer")
    st.caption(f"Fits {BUDGET} characters. Every line says where it "
               "came from.")
    classes = sorted(onto.classes)
    if classes:
        acls = st.selectbox("About", classes, key="acls")
        akeys = sorted(graph.keys_of(acls))[:300]
        if akeys:
            akey = st.selectbox("Which one", akeys, key="akey")
            facts = [Fact(f"{acls} {akey} exists in {schema.name}.",
                          "measured", weight=10)]
            for k, v in list(row_for(graph, schema, onto,
                                     acls, akey).items())[:8]:
                if v not in (None, ""):
                    facts.append(Fact(f"Its {k} is {v}.", "measured", 5))
            for r in sorted(graph.reach(acls, akey, None, depth=2))[:12]:
                kind, which = r.split(":", 1)
                rel = next((x for x in onto.relations.values()
                            if kind in (x.range, x.domain)), None)
                facts.append(Fact(f"It connects to {kind} {which}.",
                                  rel.provenance if rel else "derived", 3))
            kept = fit(facts, BUDGET)
            st.code(render(kept), language="text")
            st.caption(f"{len(kept)} of {len(facts)} facts fit. When "
                       "something must go, a guess is dropped before a "
                       "measurement, and a fact is dropped whole rather "
                       "than cut in half.")
        else:
            st.info("Nothing of this kind was built.", icon=":material/info:")
