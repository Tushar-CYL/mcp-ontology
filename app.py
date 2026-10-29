"""The middle layer, as a demo you can click through.

    streamlit run app.py

Point it at any data source - a database file, a folder of CSVs, a
connection URL - and watch the four layers appear. Nothing in here knows
what your data is about.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

# No pandas anywhere in this file, deliberately. Locked-down corporate
# machines block unsigned native libraries - Windows Application Control
# refuses pandas' compiled DLLs outright - and an app that cannot start on
# the customer's laptop is not a demo. st.dataframe takes a list of dicts
# and st.echarts_chart takes a plain dict, so none is needed.

from context.budget import Fact, fit, render
from knowledge_graph.build import build
from knowledge_graph.store import open_graph
from ontology.connect import SourceError, connect
from ontology.discover import discover
from semantic.compile import compile_metric
from semantic.discover import discover_metrics

st.set_page_config(page_title="Middle layer", page_icon=":material/hub:",
                   layout="wide")

GRAPH_DIR = Path("data/graphs")
BUDGET = 1200


# --------------------------------------------------------------- tables
@st.cache_resource(show_spinner=False)
def _have_pandas() -> bool:
    """Can this machine render a dataframe at all?

    st.dataframe converts through pandas, and locked-down corporate
    machines block unsigned native libraries - Windows Application Control
    refuses pandas' compiled DLLs outright, so the import fails at runtime
    rather than at install. Checked once; the app then renders markdown
    tables instead of crashing. A plainer table beats a dead demo.
    """
    try:
        import pandas  # noqa: F401
        return True
    except Exception:
        return False


def table(rows: list[dict], alt: str = "", **kw) -> None:
    """A table, however this machine is able to draw one."""
    if not rows:
        st.caption("_nothing to show_")
        return
    if _have_pandas():
        st.dataframe(rows, hide_index=True, alt=alt, **kw)
        return
    cols = list(rows[0])
    head = "| " + " | ".join(str(c) for c in cols) + " |"
    rule = "| " + " | ".join("---" for _ in cols) + " |"
    body = ["| " + " | ".join(str(r.get(c, "")).replace("|", r"\|")
                              for c in cols) + " |" for r in rows[:200]]
    st.markdown("\n".join([head, rule] + body))
    if len(rows) > 200:
        st.caption(f"showing 200 of {len(rows):,}")


# --------------------------------------------------------------- loading
@st.cache_resource(show_spinner=False)
def load(source: str, _token: int):
    """Connect, discover and build, once per source.

    cache_resource and not cache_data: a database connection is a shared
    handle, not a value to copy per session. `_token` lets the Rebuild
    button force a fresh one without clearing every other source too.
    """
    schema = connect(source)
    onto = discover(schema)
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    name = "".join(c if c.isalnum() else "_" for c in source)[-60:]
    graph = open_graph(GRAPH_DIR / f"{name}.duckdb")
    stats = build(graph, schema, onto)
    return schema, onto, graph, stats


def ontology_diagram(onto) -> str:
    """The ontology as a picture: boxes for things, arrows for links.

    A dashed arrow is an inference. Drawing a guess the same as a fact is
    the one thing this layer exists to prevent, so it must be visible at a
    glance and not only in a table.
    """
    lines = ["digraph {", '  rankdir=LR; bgcolor="transparent";',
             '  node [shape=box style="rounded,filled" fillcolor="#eef2ff"',
             '        color="#4f46e5" fontname="Helvetica" fontsize=11];',
             '  edge [fontname="Helvetica" fontsize=9 color="#64748b"];']
    for c in onto.classes.values():
        clock = " \\n(dated)" if c.time_column else ""
        lines.append(f'  "{c.name}" [label="{c.name}{clock}"];')
    for r in onto.relations.values():
        stated = r.provenance == "measured"
        style = "solid" if stated else "dashed"
        colour = "#0f766e" if stated else "#b45309"
        lines.append(f'  "{r.domain}" -> "{r.range}" '
                     f'[label="{r.name}" style={style} color="{colour}" '
                     f'fontcolor="{colour}"];')
    lines.append("}")
    return "\n".join(lines)


def neighbourhood_chart(graph, onto, cls: str, key: str, depth: int):
    """One node and what it reaches, as an interactive network."""
    reached = sorted(graph.reach(cls, key, None, depth=depth))[:60]
    nodes = [{"name": f"{cls}:{key}", "symbolSize": 42,
              "itemStyle": {"color": "#4f46e5"}, "category": 0}]
    seen = {f"{cls}:{key}"}
    links = []
    for r in reached:
        if r in seen:
            continue
        seen.add(r)
        nodes.append({"name": r, "symbolSize": 20, "category": 1})
        links.append({"source": f"{cls}:{key}", "target": r})
    return {
        "tooltip": {},
        "legend": [{"data": ["focus", "reached"]}],
        "series": [{
            "type": "graph", "layout": "force", "roam": True,
            "label": {"show": True, "position": "right", "fontSize": 10},
            "force": {"repulsion": 220, "edgeLength": 90},
            "categories": [{"name": "focus"}, {"name": "reached"}],
            "data": nodes, "links": links,
        }],
    }


# ------------------------------------------------------------------ page
st.title("The middle layer")
st.caption("Connect any data source. It works out what exists, what "
           "connects to what, and what you can measure.")

with st.sidebar:
    st.subheader("Source")
    source = st.text_input(
        "Path or connection URL", value="data/hospital.db",
        help="A database file, a folder of CSVs, one CSV, or "
             "postgres://user@host/db")
    st.caption("Examples: `data/hospital.db` · `data/raw/kaggledata` · "
               "`sales.csv`")
    if "token" not in st.session_state:
        st.session_state.token = 0
    if st.button("Rebuild", icon=":material/refresh:", width="stretch"):
        st.session_state.token += 1
        load.clear()

if not source:
    st.info("Enter a source on the left to begin.", icon=":material/west:")
    st.stop()

try:
    with st.spinner("Reading the source and building the graph…"):
        schema, onto, graph, stats = load(source, st.session_state.token)
except SourceError as e:
    st.error(str(e), icon=":material/error:")
    st.stop()
except Exception as e:  # a broken source must not show a stack trace
    st.error(f"Could not build from this source.\n\n{e}",
             icon=":material/error:")
    st.stop()

guessed = sum(1 for r in onto.relations.values() if r.provenance != "measured")
cols = st.columns(5, border=True)
cols[0].metric("Tables read", len(schema.tables))
cols[1].metric("Kinds of thing", len(onto.classes))
cols[2].metric("Links", len(onto.relations),
               f"{guessed} guessed" if guessed else "all stated",
               delta_color="off")
cols[3].metric("Things in graph", f"{stats['nodes']:,}")
cols[4].metric("Connections", f"{stats['edges']:,}")

tabs = st.tabs(["Ontology", "Knowledge graph", "Numbers", "Answer"])

# ------------------------------------------------------------- LAYER 1
with tabs[0]:
    st.subheader("What exists, and what is allowed")
    st.caption("Worked out from the source. Nothing was configured.")

    left, right = st.columns([3, 2])
    with left:
        st.graphviz_chart(
            ontology_diagram(onto),
            alt="Each box is a kind of thing; each arrow is a link between "
                "two of them. Dashed arrows were guessed rather than "
                "declared by the source.")
        st.caption(":material/line_end_arrow: solid = the source declared "
                   "it  ·  :material/show_chart: dashed = we worked it out")
    with right:
        st.markdown("**Kinds of thing**")
        table([{
            "thing": c.name,
            "from table": c.table,
            "identified by": c.key + (" (made up)" if c.key_is_synthetic else ""),
            "dated by": c.time_column or "—",
            "rows": (schema.table(c.table).row_count
                     if schema.table(c.table) else 0),
        } for c in onto.classes.values()],
            alt="Each kind of thing found in the source")

    st.markdown("**What connects to what**")
    if onto.relations:
        table([{
            "link": r.name, "from": r.domain, "to": r.range,
            "how": "stated" if r.provenance == "measured" else "guessed",
            "confidence": r.confidence,
        } for r in onto.relations.values()],
            alt="Links between things, and how confident we are in each")
        if guessed:
            st.info(
                f"{guessed} of {len(onto.relations)} links were **guessed** "
                "from column names. This source does not declare its keys — "
                "most CSV exports cannot — so these are strong inferences, "
                "not facts, and they are labelled that way everywhere.",
                icon=":material/info:", title="Guessed links")
    else:
        st.warning("No links found. The source has no foreign keys and no "
                   "columns named after other tables.",
                   icon=":material/link_off:")

# ------------------------------------------------------------- LAYER 2
with tabs[1]:
    st.subheader("The connections, with time on them")

    classes = sorted(onto.classes)
    c1, c2, c3 = st.columns([1, 2, 1], vertical_alignment="bottom")
    cls = c1.selectbox("Kind of thing", classes)
    keys = sorted(graph.keys_of(cls))[:500] if cls else []
    key = c2.selectbox("Which one", keys) if keys else None
    depth = c3.slider("Hops", 1, 4, 2)

    if not key:
        st.info("Nothing of this kind was built.", icon=":material/info:")
    else:
        reached = sorted(graph.reach(cls, key, None, depth=depth))
        a, b = st.columns([3, 2])
        with a:
            st.echarts_chart(
                neighbourhood_chart(graph, onto, cls, key, depth),
                alt=f"{cls} {key} and the {len(reached)} things it reaches "
                    f"within {depth} hops",
                height=460)
        with b:
            st.metric("Reached within "
                      f"{depth} hop{'s' if depth > 1 else ''}", len(reached))
            props = graph.props_of(cls, key)
            if props:
                st.markdown("**What we know about it**")
                table([{"field": k, "value": str(v)}
                       for k, v in props.items()],
                      alt=f"Columns carried on {cls} {key}")
        if reached:
            st.markdown("**What it reaches**")
            table([{"kind": r.split(":", 1)[0], "which": r.split(":", 1)[1]}
                   for r in reached[:300]],
                  alt="Everything reachable from the selected thing")

    with st.container(border=True):
        st.markdown("**Checks**")
        d = graph.dangling_edges()
        k1, k2 = st.columns(2)
        k1.metric("Links pointing at nothing", d,
                  "our build is wrong" if d else "good", delta_color="off")
        k2.metric("Rows whose link had no match", f"{stats['skipped_edges']:,}",
                  "a fact about the data" if stats['skipped_edges'] else "none",
                  delta_color="off")

# ------------------------------------------------------------- LAYER 3
with tabs[2]:
    st.subheader("The numbers, defined once")
    metrics = discover_metrics(onto)
    st.caption(f"{len(metrics)} metrics proposed from the columns found. "
               "Nothing was invented: a source with no numbers gets counts "
               "and nothing else.")

    names = [m.name for m in metrics]
    m1, m2 = st.columns([2, 2], vertical_alignment="bottom")
    chosen = m1.selectbox("Metric", names)
    metric = next(m for m in metrics if m.name == chosen)
    group = m2.selectbox("Group by", ["(none)"] + sorted(metric.dimensions))

    sql, params = compile_metric(metric,
                                 group_by=None if group == "(none)" else group)
    try:
        rows = graph.sql(sql, params)
        if group != "(none)":
            data = [{group: str(r[0]), "value": r[1]} for r in rows]
            if data:
                # ECharts takes a plain dict, so the chart needs no
                # dataframe library either.
                st.echarts_chart({
                    "tooltip": {},
                    "xAxis": {"type": "category",
                              "data": [d[group] for d in data],
                              "axisLabel": {"rotate": 30}},
                    "yAxis": {"type": "value"},
                    "series": [{"type": "bar",
                                "data": [d["value"] for d in data],
                                "itemStyle": {"color": "#4f46e5"}}],
                }, alt=f"{metric.title} by {group}", height=320)
        else:
            data = [{"value": r[0]} for r in rows]
        table(data, alt=metric.title)
    except Exception as e:
        st.error(f"Could not compute this metric.\n\n{e}",
                 icon=":material/error:")

    with st.expander("The SQL this produced"):
        st.code(sql, language="sql")
        st.caption("Generated from the metric definition, so every caller "
                   "gets the same number.")

# ------------------------------------------------------------- LAYER 4
with tabs[3]:
    st.subheader("The packed answer")
    st.caption(f"Everything below fits a hard limit of {BUDGET} characters, "
               "and every line says where it came from.")

    if not classes:
        st.stop()
    acls = st.selectbox("Tell me about", classes, key="answer_class")
    akeys = sorted(graph.keys_of(acls))[:500]
    if not akeys:
        st.info("Nothing of this kind was built.", icon=":material/info:")
    else:
        akey = st.selectbox("Which one", akeys, key="answer_key")
        facts = [Fact(f"{acls} {akey} exists in {schema.name}.",
                      "measured", weight=10)]
        for k, v in list(graph.props_of(acls, akey).items())[:8]:
            if v not in (None, ""):
                facts.append(Fact(f"Its {k} is {v}.", "measured", weight=5))
        for r in sorted(graph.reach(acls, akey, None, depth=2))[:12]:
            kind, which = r.split(":", 1)
            rel = next((x for x in onto.relations.values()
                        if x.range == kind or x.domain == kind), None)
            prov = rel.provenance if rel else "derived"
            facts.append(Fact(f"It connects to {kind} {which}.", prov,
                              weight=3))
        kept = fit(facts, BUDGET)
        st.code(render(kept), language="text")
        a, b = st.columns(2)
        a.metric("Facts gathered", len(facts))
        b.metric("Facts that fit", len(kept),
                 f"{len(facts) - len(kept)} dropped" if len(kept) < len(facts)
                 else "all fit", delta_color="off")
        st.caption("When something has to go, a guess is dropped before a "
                   "measurement. A fact that does not fit is dropped whole, "
                   "never cut in half — half a sentence of evidence still "
                   "reads as complete.")
