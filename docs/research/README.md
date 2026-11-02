# Research pack — how this evidence was gathered

This folder is the evidence base for the "better middle layer" program. It
answers three questions the manager asked directly:

1. **Which tools does the industry use for each of our four layers?**
2. **Which business problems do those tools actually solve with the layer?**
3. **Where are they weak enough that a better version can win for a defined job?**

## Files

| File | Contents |
|---|---|
| `01_ontology_layer.md` | L1: Palantir Foundry Ontology, Databricks Unity Catalog, Atlan, Stardog, Ontotext GraphDB + virtualization, standards |
| `02_knowledge_graph_layer.md` | L2: Neo4j, Amazon Neptune Analytics, Stardog virtual graphs, TigerGraph/Memgraph, Databricks GraphFrames, SQL-only warehouses, Kuzu |
| `03_semantic_layer.md` | L3: dbt MetricFlow, Cube, AtScale, Databricks UC Metric Views, Snowflake Semantic Views + Cortex Analyst, LookML/Power BI |
| `04_context_layer.md` | L4: Atlan Context Layer, Neo4j Context Engine, Palantir AIP, Microsoft GraphRAG, MCP, Glean, Zep/Letta, vector stores |
| `rows/*.csv` | One machine-readable row per tool, same columns across layers |

The consolidated source index (URLs, grades, what each is used for) is in
[../strategy/sources.md](../strategy/sources.md).

## Evidence grades — kept the same discipline as the product

The product's rule is "a guess must never read as a fact". Research follows the
same rule:

| Grade | Meaning |
|---|---|
| **A** | We ran it ourselves, on this machine, and recorded the result |
| **B** | Primary vendor documentation (docs, pricing page, datasheet) |
| **C** | Independent source (analyst, press, third-party comparison) |
| **D** | Our inference or extrapolation — must be labelled as such |

Rules:

- **No grade, no row.** Every factual claim in a layer document carries a grade
  and a link.
- Vendor case studies are **B** at best and are labelled "vendor-reported
  outcome", not "measured".
- Pricing is **public list price only**, as of the stated date. "Contact us" is
  recorded as "not public".
- "Documented" and "measured" are separate columns. We will not present a
  documented competitor capability as if we measured it.
- Date accessed: **2026-10-29** for this round.

## Per-tool record

CSV columns (identical for all four layers, so the Lead can concatenate):

```
layer,tool,vendor,category,licence_pricing,deployment,inputs,entry_criteria,
how_layer_built,automation_level,human_in_loop,artifacts_exit_criteria,
time_versioning,lineage_provenance,agent_consumption,problems_solved,
documented_outcomes,limits,gap_for_us,evidence_grade,source_url,source_date,notes
```

Markdown deep dives follow the same order, plus a layer-level synthesis:

1. five-line executive summary,
2. comparison table,
3. per-tool sections (entry criteria → how built → human-in-the-loop → exit
   criteria → problems solved → limits),
4. "Problems well served vs under-served",
5. "What a better version must do",
6. sources.

## How this feeds the plan

- **Layer docs →** `docs/strategy/industry_map.md` (the landscape and the trend)
  and `docs/strategy/gap_analysis.md` (served vs under-served).
- **Gap analysis →** `docs/strategy/better_version_blueprint.md` (3–5
  differentiators, each with a demo test and a metric).
- **Every number in the deck →** `docs/benchmark/` or a graded research row.
  No other source is allowed.

## Known limits of this round

- Paid platforms are documented, not measured (no accounts, no data upload).
- Free/local tools can be probed hands-on once the benchmark harness exists.
- The market moves fast: findings carry an access date and are refreshed at
  Gate 1 rather than trusted indefinitely.
