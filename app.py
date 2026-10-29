"""The middle layer. Four views, one per layer.

    streamlit run app.py        (or .\\run_ui.ps1, which kills a stale one)

No pandas anywhere, deliberately: locked-down machines block unsigned
native libraries - Windows Application Control refuses pandas' compiled
DLLs - and st.dataframe converts through pandas. The app checks once and
falls back to markdown. A plainer table beats a dead demo.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from context.budget import Fact, fit, render
from knowledge_graph.build import build, is_current, row_for
from knowledge_graph.store import open_graph
from ontology.connect import SourceError, connect
from ontology.discover import discover
from semantic.compile import compile_metric
from semantic.discover import discover_metrics

st.set_page_config(page_title="Middle layer", page_icon=":material/hub:",
                   layout="wide")

GRAPH_DIR = Path("data/graphs")
BUDGET = 1200

# One colour per kind of thing, reused by the graph and the charts so a
# colour always means the same thing wherever it appears.
PALETTE = ["#4f46e5", "#0d9488", "#b45309", "#be123c", "#7c3aed",
           "#0369a1", "#65a30d", "#c2410c", "#0f766e", "#9333ea"]


# ------------------------------------------------------------- plumbing
@st.cache_resource(show_spinner=False)
def _pandas_works() -> bool:
    try:
        import pandas  # noqa: F401
        return True
    except Exception:
        return False


def table(rows: list[dict], alt: str = "", height=None) -> None:
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
    if is_current(graph, schema, onto):
        stats = {"nodes": graph.one("SELECT count(*) FROM nodes") or 0,
                 "edges": graph.one("SELECT count(*) FROM edges") or 0}
    else:
        stats = build(graph, schema, onto)
    return schema, onto, graph, stats


def colour_of(name: str, order: list[str]) -> str:
    return PALETTE[order.index(name) % len(PALETTE)] if name in order \
        else "#64748b"


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

counts = graph.class_counts()
order = [n for n, _ in counts]
guessed = sum(1 for r in onto.relations.values() if r.provenance != "measured")

tabs = st.tabs(["1 · Ontology", "2 · Knowledge graph", "3 · Semantic",
                "4 · Context"])

# ====================================================== 1 · ONTOLOGY
with tabs[0]:
    st.subheader("What exists here")
    st.caption("Read from the source. Nothing was configured.")

    k = st.columns(4, border=True)
    k[0].metric("Kinds of thing", len(onto.classes))
    k[1].metric("Kinds of link", len(onto.relations))
    k[2].metric("Things", f"{stats['nodes']:,}")
    k[3].metric("Guessed links", guessed)

    left, right = st.columns([2, 3])

    with left:
        st.markdown("**Things per kind**")
        shown = [(n, c) for n, c in counts if c][:14]
        if shown:
            st.echarts_chart({
                "tooltip": {},
                "grid": {"left": 110, "right": 24, "top": 8, "bottom": 24},
                "xAxis": {"type": "value"},
                "yAxis": {"type": "category",
                          "data": [n for n, _ in shown][::-1]},
                "series": [{
                    "type": "bar",
                    "data": [{"value": c,
                              "itemStyle": {"color": colour_of(n, order)}}
                             for n, c in shown][::-1]}],
            }, alt="How many of each kind of thing exist",
                height=max(220, 30 * len(shown)))

    with right:
        st.markdown("**How the kinds connect**")
        lines = ["digraph {", '  rankdir=LR; bgcolor="transparent";',
                 '  node [shape=box style="rounded,filled" '
                 'fontname="Helvetica" fontsize=11 fontcolor="white"];',
                 '  edge [fontname="Helvetica" fontsize=9];']
        for name, n in counts:
            lines.append(f'  "{name}" [label="{name}\\n{n:,}" '
                         f'fillcolor="{colour_of(name, order)}" '
                         f'color="{colour_of(name, order)}"];')
        for r in onto.relations.values():
            stated = r.provenance == "measured"
            col = "#0f766e" if stated else "#b45309"
            lines.append(f'  "{r.domain}" -> "{r.range}" [label="{r.name}" '
                         f'style={"solid" if stated else "dashed"} '
                         f'color="{col}" fontcolor="{col}"];')
        st.graphviz_chart("\n".join(lines + ["}"]),
                          alt="Each box is a kind of thing with how many "
                              "exist; each arrow is a link. Dashed arrows "
                              "were guessed, not declared.")
        st.caption("solid = the source declared it · "
                   "dashed = we worked it out")

    # The same information in words. A dashed line is readable by a person
    # looking at the picture and by nobody else - not a screen reader, not
    # a test, not someone copying it into a document. Whether a link was
    # stated or guessed is the most important fact on this page, so it is
    # not left to line style alone.
    if onto.relations:
        st.markdown("**Every link, and how we know**")
        table([{
            "link": r.name, "from": r.domain, "to": r.range,
            "how": "stated" if r.provenance == "measured" else "guessed",
            "sure": f"{r.confidence:.0%}",
        } for r in onto.relations.values()],
            alt="Links between kinds of thing, and whether the source "
                "declared each one or we inferred it")

    st.divider()
    st.markdown("**Look inside a kind**")
    pick = st.selectbox("Kind", order, label_visibility="collapsed")
    cls = onto.classes[pick]
    i1, i2, i3, i4 = st.columns(4, border=True)
    i1.metric("How many", f"{dict(counts).get(pick, 0):,}")
    # Which table it came from: the thread back from the name we invented
    # to the thing in your data it was invented for.
    i2.metric("From table", cls.table)
    i3.metric("Identified by",
              cls.key + (" (made up)" if cls.key_is_synthetic else ""))
    i4.metric("Dated by", cls.time_column or "—")

    rows = graph.instances(pick, limit=25)
    out = []
    for key, props in rows:
        d = {"id": key}
        if props:
            p = json.loads(props) if isinstance(props, str) else dict(props)
            d.update({k_: str(v) for k_, v in p.items()})
        out.append(d)
    st.caption(f"Real {pick}s from your data")
    table(out, alt=f"A sample of {pick} instances")

    if guessed:
        st.info(
            f"{guessed} of {len(onto.relations)} links were guessed from "
            "column names. This source does not declare its keys — most CSV "
            "exports cannot — so these are strong inferences, not facts, "
            "and they are labelled that way everywhere.",
            icon=":material/info:")

# =============================================== 2 · KNOWLEDGE GRAPH
with tabs[1]:
    st.subheader("The graph itself")
    st.caption("Real things and the real links between them. Drag to move, "
               "scroll to zoom.")

    c1, c2 = st.columns([1, 2], vertical_alignment="bottom")
    rel_names = ["all links"] + sorted(onto.relations)
    rel = c1.selectbox("Show", rel_names)
    size = c2.slider("How much of it", 50, 1200, 300, step=50,
                     help="Number of links drawn. More shows shape; "
                          "fewer is readable.")

    nodes, edges = graph.subgraph(
        limit=size, relation=None if rel == "all links" else rel)

    if not edges:
        st.warning("No links to draw. This source has no foreign keys and "
                   "no columns named after other tables.",
                   icon=":material/link_off:")
    else:
        kinds = sorted({n["class"] for n in nodes})
        st.echarts_chart({
            "tooltip": {},
            "legend": [{"data": kinds, "top": 0}],
            "series": [{
                "type": "graph", "layout": "force", "roam": True,
                "categories": [{"name": k_,
                                "itemStyle": {"color": colour_of(k_, order)}}
                               for k_ in kinds],
                "label": {"show": len(nodes) <= 60, "position": "right",
                          "fontSize": 9},
                "emphasis": {"focus": "adjacency"},
                "force": {"repulsion": 160, "edgeLength": 70,
                          "gravity": 0.08},
                "lineStyle": {"opacity": 0.5, "curveness": 0.08},
                "data": [{"name": n["id"], "value": n["key"],
                          "category": kinds.index(n["class"]),
                          "symbolSize": 10 if len(nodes) > 200 else 18}
                         for n in nodes],
                "links": [{"source": e["source"], "target": e["target"],
                           "value": e["relation"]} for e in edges],
            }],
        }, alt=f"{len(nodes):,} things and {len(edges):,} links between "
               f"them, coloured by kind", height=620)

        g1, g2, g3 = st.columns(3, border=True)
        g1.metric("Things drawn", f"{len(nodes):,}")
        g2.metric("Links drawn", f"{len(edges):,}")
        g3.metric("Links in total", f"{stats['edges']:,}")
        st.caption("Hover a thing to highlight what it touches. Each colour "
                   "is a kind, matching the chart in Ontology.")

# ====================================================== 3 · SEMANTIC
with tabs[2]:
    st.subheader("What you can measure")
    metrics = discover_metrics(onto)
    st.caption(f"{len(metrics)} metrics, every one from a column that is "
               "actually there. A source with no numbers gets counts and "
               "nothing else — nothing is invented.")

    m1, m2 = st.columns(2, vertical_alignment="bottom")
    chosen = m1.selectbox("Measure", [m.name for m in metrics])
    metric = next(m for m in metrics if m.name == chosen)
    group = m2.selectbox("Split by", ["(nothing)"] + sorted(metric.dimensions))

    sql, params = compile_metric(
        metric, group_by=None if group == "(nothing)" else group)
    try:
        rows = graph.sql(sql, params)
        if group != "(nothing)" and rows:
            st.echarts_chart({
                "tooltip": {},
                "grid": {"left": 60, "right": 24, "top": 16, "bottom": 90},
                "xAxis": {"type": "category",
                          "data": [str(r[0]) for r in rows],
                          "axisLabel": {"rotate": 35}},
                "yAxis": {"type": "value"},
                "series": [{"type": "bar", "data": [r[1] for r in rows],
                            "itemStyle": {"color": PALETTE[0]}}],
            }, alt=f"{metric.title} by {group}", height=340)
            table([{group: str(r[0]), "value": r[1]} for r in rows],
                  alt=metric.title)
        else:
            table([{"value": r[0]} for r in rows], alt=metric.title)
    except Exception as e:
        st.error(f"Could not compute this.\n\n{e}", icon=":material/error:")

    with st.expander("The SQL this produced"):
        st.code(sql, language="sql")
        st.caption("Generated from the definition, so every caller gets "
                   "the same number.")

# ======================================================= 4 · CONTEXT
with tabs[3]:
    st.subheader("One packed answer")
    st.caption(f"Fits {BUDGET} characters. Every line says where it came "
               "from, so a reader can tell a measurement from a guess.")

    a1, a2 = st.columns(2, vertical_alignment="bottom")
    acls = a1.selectbox("About", order, key="acls")
    akeys = sorted(graph.keys_of(acls))[:300]
    if not akeys:
        st.info("Nothing of this kind was built.", icon=":material/info:")
    else:
        akey = a2.selectbox("Which one", akeys, key="akey")
        facts = [Fact(f"{acls} {akey} exists in {schema.name}.",
                      "measured", weight=10)]
        for k_, v in list(row_for(graph, schema, onto,
                                  acls, akey).items())[:8]:
            if v not in (None, ""):
                facts.append(Fact(f"Its {k_} is {v}.", "measured", 5))
        for r in sorted(graph.reach(acls, akey, None, depth=2))[:12]:
            kind, which = r.split(":", 1)
            rel_ = next((x for x in onto.relations.values()
                         if kind in (x.range, x.domain)), None)
            facts.append(Fact(f"It connects to {kind} {which}.",
                              rel_.provenance if rel_ else "derived", 3))
        kept = fit(facts, BUDGET)
        st.code(render(kept), language="text")
        b1, b2 = st.columns(2, border=True)
        b1.metric("Facts gathered", len(facts))
        b2.metric("Facts that fit", len(kept))
        st.caption("When something must go, a guess is dropped before a "
                   "measurement, and a fact is dropped whole rather than "
                   "cut in half — half a sentence of evidence still reads "
                   "as complete.")
