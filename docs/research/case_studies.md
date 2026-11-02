# Case studies — what vendors claim, and what it is worth

Every outcome below is **vendor-reported** (grade B at best) and none is
measured by us. This file exists so the deck never presents a vendor's customer
story as independent evidence. The only grade-A evidence in this programme is
our own benchmark (`docs/benchmark/`).

## What was found

| Vendor | Claim / case | Grade | Where |
|---|---|---|---|
| Palantir | Customer stories and investor materials; no independently verified outcome captured | B (vendor) | Palantir site |
| Databricks | Unity Catalog governance/PII/impact-analysis use cases; no outcome number captured | B (vendor) | Databricks docs/site |
| Atlan | "400+ enterprises", "8B context reads / 90 days", "87% of customers say generated context is on par with or better than human-written"; named customers (Nasdaq, Mastercard, Autodesk, GM, NHS, Fox) | B (vendor, self-reported) | [atlan.com/context-layer](https://atlan.com/context-layer/) |
| Ontotext GraphDB / metaphactory | Boehringer Ingelheim knowledge democratisation, Scania/TRATON, Sloane Lab; BKW "<2 yr break-even"; Siemens Energy "1,500 hrs saved in year one" | B (vendor) | metaphactory/Graphwise pages |
| Neo4j | IDC study, TfL story (vendor-commissioned); GraphRAG accuracy claims | B (vendor) | Neo4j site |
| TigerGraph | Ford, Intuit, JLR, Xbox named customers; no numbers captured | B (vendor) | TigerGraph site |
| Cube | Brex chose Cube over dbt Semantic Layer and LookML (vendor quote) | B (vendor) | Cube site |
| Snowflake | Cortex accuracy improvements claimed; no measured number in the docs reviewed | B (vendor) | Snowflake docs |
| Zep | S&P Global Market Intelligence quote calling it a "temporal context graph" | B (vendor page) | [getzep.com](https://www.getzep.com/pricing/) |
| Gartner/Forrester badges (Atlan, dbt, etc.) | Analyst recognition, not product outcome | C | vendor pages |

## What this means for our pitch

1. **Do not borrow a vendor's number.** "Atlan says 87%" is not evidence that
   our layer is good; it is evidence that Atlan markets well.
2. **The market has no independent, like-for-like outcome data** for
   auto-derivation, provenance or context packing — because those categories are
   new. Our benchmark is therefore the first comparable number, and we must
   publish the method with it.
3. **Use vendor customers as proof of demand, not of quality.** "Nasdaq uses a
   context platform" proves buyers exist; it does not prove the context is
   correct.
4. **Our own case study is the deliverable.** After the pilot, write it in the
   same format: source, time-to-model, coverage, review items, answer accuracy,
   cost — measured, reproducible.

## Independent evidence that does exist (and its limits)

- Kùzu archive measured via GitHub API (grade A): free tools can die; this is
  evidence for durability, not for a competitor's quality.
- Public pricing pages (grade B): useful for the cost anchor; not comparable
  units across vendors.
- Documentation of capability limits (e.g. Bedrock GraphRAG "no build
  customisation", Snowflake lineage not preserved across renames) (grade B):
  stronger than marketing, still vendor-authored.
- No hands-on trial of paid platforms in this round; all market evidence is
  documented.

## Sources

Full citation list: [../strategy/sources.md](../strategy/sources.md) and the
Sources section of each layer document in `docs/research/01..04`.
