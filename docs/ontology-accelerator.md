# Ontology Accelerator

**Input:** several sources, each with a role (source system, MDM hub, data mart), an owner team and a refresh SLA, plus the problem statement.
**Output:** one governed, versioned enterprise ontology, served over MCP and REST, exported to Git, with a maturity scorecard.

## Five-minute demo (BI/MDM problem)

1. **The problem (30s).** Home → *Ontology Accelerator* → *Load the demo*. The demo has five systems: CRM, ERP, billing, an MDM hub and a data mart. Customer ids differ in every system. The hub runs 2–3 weeks behind. There are ten amount columns with SAP names.
2. **What it found (60s).** About six seconds later, four findings sit at the top:
   - The mart's "revenue" is built from **BRTWR (gross)**, not NETWR, and overstates revenue by **13.3%**.
   - The mart adds three currencies without converting them.
   - 12 customer names were corrected in the hub but never reached the sources.
   - Some customers are mastered twice.
3. **How it knows (90s).** Open *Properties with meaning*. For each column, *How we know* gives the evidence:
   - from the name (SAP dictionary);
   - from the data (NETWR + MWSBK = BRTWR on 99.8% of rows; USD and local are per-currency rate conversions);
   - reconciled with another system (the billing invoice equals the ERP gross, order by order).

   With every column renamed to AMT_01…AMT_10, the data alone still recovers 7 of the 10 columns. It does not guess the other three; it marks them "unclassified".
4. **Identity and truth (45s).**
   - In *Identity*, type `B-5000` to see the CRM, ERP, billing and hub records, plus the golden record.
   - *Conflicts, freshness, survivorship* shows the hub is N days behind its 7-day SLA, the hub corrections, and which source wins each field, with the caveat.
5. **Govern and publish (45s).** Edit a definition, then *Approve confident*. Assign owners: core concepts go to Data Governance, extensions to each system's team. Grant an approver, then *Publish*. Download Turtle, SHACL or the Git zip.
6. **Where it lives (30s).** It lives in the registry, in your Git repo, and on live MCP/REST. Agents call `map_column("bi_mart.sales_monthly.revenue")` and get *gross_amount*, plus the finding. *Maturity* shows Level 1 → **Level 4**. Level 5 needs only agent usage feedback.

## Where the ontology lives

| Place | What | How tools reach it |
|---|---|---|
| Registry (`ontology/registry.py`) | proposals, decisions, owners, audit, versions | — |
| Your Git repo (`export_folder`) | `ontology.ttl`, `shapes.ttl`, `ontology.json`, `concepts/`, `contracts/`, `CHANGELOG.md` | pull requests |
| Live | the pinned published version | MCP: `list_concepts`, `get_concept`, `map_column`, `resolve_entity`, `get_contract`, `validate_rules`, `ontology_version` · REST: `/api/eo/{id}` |

Context, Semantic, Copilot, Databricks and Snowflake agents read the ontology through these routes. None of them reads the raw tables.

## Measured results

**BI/MDM scenario** (`tests/integration/test_eo_*`, scored against `ground_truth.json`):
- Amount meanings: 10/10 with names; 7/10 from data alone, with the other 3 admitted as unknown.
- Concepts match the ground truth.
- Identity: 100% precision and 100% recall, both with and without the hub. This is clean generated data, not a real-world claim.
- Every planted duplicate, correction, stale source and rule violation is found.

**SALT (real SAP data, 4.7M rows):**
- 6 links match SAP's model (the sold-to, ship-to, bill-to and payer customer roles).
- 29 of 31 columns get a business meaning.
- Two repeated customer numbers found.
- Withdrawn currency codes (DEM, IEP, ROL…) and the non-ISO code RMB flagged.
- The accelerator takes 5.3s.
