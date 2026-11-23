# Strata final update plan: four layers, shown so that anyone can understand them

Date: 22 Nov 2026. This is the final plan. It replaces `Strata four layers update plan.md`.

It pulls together all the research we did:
- the South Park Ontology Explainer;
- the Minimal Ontology Principle (Modern Data 101);
- the visuals research (graph literacy studies, Palantir, Neo4j, Microsoft Fabric, Atlan, ThoughtSpot and others), in `Simpler ontology visuals for business.md`;
- the Genie and Databricks reading, in `Genie Ontology lessons and build plan.md`;
- **Semantica**, an open-source context-graph library (https://github.com/semantica-agi/semantica, https://getsemantica.ai/). See section 1b.

It is **our own design**, not a copy of any one tool.

---

## 1. The big idea: one real example, four simple questions

Every user, technical or not, understands a story about **one real thing**. So Strata explains its four layers as **four questions about the same real record**:

| Layer | The question it answers | What the user sees first |
|---|---|---|
| **Ontology** | **What is it?** | "An *Order* is a customer's request to buy. Example: Order 1984611, placed by Müller GmbH on 3 Mar 2024." |
| **Knowledge graph** | **What is it connected to?** | "Order 1984611 *has* 4 order lines, *was placed by* Müller GmbH, and *was billed in* Invoice 90012." |
| **Semantic** | **How do we count it?** | "Revenue here means *net value of billed orders, cancelled ones left out*. ◆ This differs from the usual meaning." |
| **Context** | **What is the answer, and why should I believe it?** | "I read your question as [Revenue] [Germany] [2024]. Answer: 8.2 M EUR. ✓ Proved from 3 facts." |

The same example record (picked automatically from the real data) runs through all four pages, so the user sees **one story**, not four tools.

**This is what makes Strata unique.** No tool we studied does all three of these:
1. **Every sentence carries its proof** (✓ checked on the data, ✗ the data disagrees, ? AI guess). Genie, Palantir and Atlan show where a fact came from; none show whether the data agrees.
2. **The "company meaning" mark ◆**, from the Minimal Ontology Principle: we only spell out where *your* meaning differs from the usual one, and we say so on screen.
3. **The same real example everywhere**, from the South Park Explainer: real individuals first, types second.

---

## 1b. What each source gave this plan

| Source | The one idea we take | Where it lands in Strata |
|---|---|---|
| South Park explainer | Real individuals first; facts as sentences; solid = stated, dashed = worked out by a rule | Thing card, Record card, rules as switches |
| Minimal Ontology Principle | Define only where *your* meaning differs from the usual one; grow it from the AI's mistakes | ◆ mark, Meaning card, misreads inbox |
| Visuals research | Fewer than about 20 dots; one record page before any graph | Record card default, small picture on request |
| Databricks Genie | Citations under answers; "Is this correct?"; show the accuracy score to users | Answer card chips, "Is this right?", trust line |
| **Semantica** | **Evidence on every fact; trust grows with how many sources agree; conflicts flagged, never overwritten; a decision log; replay "as it was on a date"; say plainly what is and isn't explained** | Evidence drawer, "agreed by N sources", conflict card, decision log, "as of" date, honest "what I can't explain" line |

### What Semantica is, in simple words
- **An open-source Python library** (MIT licence, about 14.7k GitHub stars, version 0.x, so still early). It builds a "context graph" of entities, facts and **decisions** for AI agents.
- **Built-in pieces:**
  - W3C PROV provenance (where each fact came from);
  - conflict detection (value, type, time);
  - entity de-duplication;
  - SHACL validation;
  - rule reasoning that shows its derivation path;
  - trust tiers (quarantine / bronze / silver / gold, based on how many sources agree);
  - point-in-time snapshots;
  - audit export;
  - an MCP server.
- **Its weak side** is the business user. The only screen is a developer workbench (a force-directed graph, timeline and lineage views). It has **no metrics layer**, no plain-language cards, and no checking of answers against the data.
- Its claims ("6,000× faster", "audit-ready for HIPAA/SOX", customer logos) are self-reported.

### What we take from Semantica, kept simple
1. **An evidence drawer on every fact.** Click any ✓ to see where it came from (table and column, or document and page), when it was checked, the exact count, and who approved it. Semantica's "income_2024.pdf · page 2" card is the model.
2. **"Agreed by N sources".** When a fact is proved by more than one check (data + rule + report check + person), show "✓ agreed by 3". This is a simple version of their bronze/silver/gold tiers, without new jargon.
3. **Conflicts are flagged and never silently overwritten.** Two values or two definitions for the same thing become a **conflict card**, showing both sides with their numbers. A person picks one, and the choice is logged.
4. **The decision log:** "who decided what, and why". Every approval, rule switch, certification and "company meaning" is one line, for example "Asha approved *Revenue = billed, not cancelled*, 12 Nov, because Q3 report matched". The log is linked to what it changed. It is shown on the Trust panel and in a download.
5. **"As of" date.** An answer remembers the ontology version it used, and "Show as it was on 12 Nov" replays it. This explains why a number changed.
6. **An honest scope line** on every answer: "I can show which facts and rules I used. I can't show how the AI chose its words." Semantica says this plainly, and it builds trust.

**What we do NOT take:** OWL/SHACL/RDF exports in the main screens, the force-directed developer workbench, the many storage back ends, or embedding (UMAP) pictures. They are too technical for business users.

---

## 2. Five rules for every screen

1. **Real example first, the type second.** Show "Order 1984611", then "this is one of 512,000 Orders".
2. **Facts as sentences, not tables.** "Order 1984611 → was placed by → Müller GmbH". The table is one click deeper.
3. **One mark on every sentence**, the same legend on all 4 pages:
   - **✓ solid line = proved by the data**
   - **? dashed line = AI guess, not yet checked**
   - **↻ dashed with "worked out from…" = made by a business rule**
   - **✗ = the data disagrees**
   - **👤 = approved by a person** (with their name and date)
   - **◆ = the company meaning differs from the usual one**
4. **Small pictures only:** at most about 20 dots. Big groups become one bubble with a count ("1,297 more").
5. **Plain words, codes behind a button:** "Show SQL", "Show field codes", "Show all fields".

---

## 3. What changes on each page

### Layer 1. Ontology: "What is it?"

**Today:** a fields table with codes, one "81%" number, and 5 tabs.

**New: the Thing card** (the default view for each thing)

```
┌ Order ───────────────────────────────── one of 512,000 ┐
│ A customer's request to buy goods.            ✓ 👤 Asha │
│                                                          │
│ Example: Order 1984611                                   │
│  • was placed by Müller GmbH                     ✓       │
│  • has status Delivered                          ✓       │
│  • net value 4,210 EUR                           ✓       │
│  • counts in revenue only if not cancelled  ↻ rule       │
│                                                          │
│ Trust: ███████████░░░  41 proved · 3 data disagrees ·    │
│        6 for you to decide  → Review                     │
│ [Show all fields]  [Rules]  [What depends on this]       │
└──────────────────────────────────────────────────────────┘
```

- **Changes:**
  - The single % becomes a **3-part bar** (proved / data disagrees / for you to decide). Each part is clickable.
  - Tabs go from 5 to 3: **Things**, **Map**, **Rules & notes**.
  - Review moves into the bar.
- **Business rules become switches**, as in South Park. When one is turned on, the facts it creates are drawn **dashed** with "worked out from Rule X and field Y".
- **The Map** shows things only (not fields), with verb labels on the lines: "places", "has", "billed in".

### Layer 2. Knowledge graph: "What is it connected to?"

**Today:** about 150 dots in globes; records show codes like "Sales Document 0001984611".

**New: the Record card** (the default view)

```
Search: [ Müller          ]   Start from: [Biggest order] [Latest] [Odd one]
┌ Order 1984611 ── Müller GmbH · 3 Mar 2024 · 4,210 EUR ──┐
│ Order 1984611 was placed by Müller GmbH on 3 Mar 2024    │
│ and is Delivered.                                        │
│                                                          │
│ has 4 order lines ✓      [line 10] [line 20] [+2]        │
│ was placed by 1 customer ✓ [Müller GmbH]                 │
│ was billed in 1 invoice ✓ [Invoice 90012]                │
│ ships to (guess) ?        [Plant 1010]                   │
│                                                          │
│ [Show picture (12 dots)]   [How is it connected to …?]   │
└──────────────────────────────────────────────────────────┘
```

- **Readable names:** for each thing type, pick the name field (customer name, description) from the data. One sentence per record comes from a template filled with real values, plus one icon per thing type.
  - Where no name exists (SAP codes), ask the owner once: "Which field is the readable name?"
- **Linked records are grouped by verb, with counts.** Click a chip to move to that record.
- **The picture only appears on request**, up to about 20 dots. The **globes stay as the overview** (one bubble per thing type).
- **Starting examples are chosen from the data,** such as the biggest, the latest, and one with a broken link. There is no fixed example text.

### Layer 3. Semantic: "How do we count it?"

**Today:** metric cards; the formula and SQL take a lot of space.

**New: the Meaning card**

```
┌ Revenue ◆ ───────────────────── 👤 Certified by Finance ┐
│ An AI would assume:  all order value                     │
│ Here it means:       net value of billed orders,         │
│                      cancelled ones left out        ◆    │
│                                                          │
│ 8.2 M EUR this quarter   ✓ matches "Q3 sales pack"       │
│ Uses: Order, Invoice · Rule: "cancelled don't count" ↻   │
│ [Show SQL]  [What depends on this]  [History]            │
└──────────────────────────────────────────────────────────┘
```

- **Only metrics with a different meaning get the ◆ and the "An AI would assume" line.** The others just say "Uses the usual meaning". This is the Minimal Ontology Principle on screen: we spell out only the difference.
- **Three badges:** 👤 approved by a person / ✓ checked on the data / ? AI draft.
- **A maths check before certifying:** a warning such as "this adds up distinct counts, so the total will be too high".

### Layer 4. Context: "What is the answer, and why should I believe it?"

**Today:** build steps and a list of facts.

**New: the Answer card**

```
Question: revenue germany last year
I read it as: [Revenue ◆ ▾] [Country = Germany ▾] [Year = 2024 ▾]   ← can change
┌──────────────────────────────────────────────────────────┐
│ 8.2 M EUR                                ✓ Proved, 3 facts│
│ • Revenue means net value of billed orders   ◆ 👤 Finance │
│ • 1,204 billed orders in Germany in 2024     ✓            │
│ • Cancelled orders left out (rule)           ↻            │
│ I left out 1 number I could not prove.                    │
│ How I got this: read → found → checked → answered  [open]│
│ Is this right?  [Yes, save as a check] [No, fix it] [Ask an owner] │
└──────────────────────────────────────────────────────────┘
```

- **"I read it as" chips:** the user corrects a misreading in one click. Correcting it offers **"Save as company meaning?"**, which is how the ◆ list grows from real mistakes.
- **Each fact is a chip:** click it to open the **evidence drawer**, which shows its source, who wrote it, its proof, "agreed by N sources" and what depends on it.
- **A last line on every answer:** "Based on ontology version 14 (20 Nov) · [Show as it was on…] · I can show the facts and rules I used, not how the AI chose its words."
- **"Is this right?"**
  - "Yes" saves the answer as a report check.
  - "No" becomes a proposal.
  - Nothing changes without a person.

---

## 4. Across the four pages

1. **One running example.** It is picked from the data and shown as a small strip at the top of every page: "Following Order 1984611". Click a layer to see the same order there.
2. **One legend** (section 2), the same component on every page.
3. **One trust line in the header**, for example "12 of 14 report checks match · 41 proved · 6 waiting for you".
4. **A 5-step tour** (optional, under 1 minute), using the running example: What is it → Connected to → How we count → Ask → Why believe it.

---

## 5. Build order (each step: tests first, then a live check, then stop for feedback)

Sizes: S = 1 to 2 days, M = 3 to 5 days.

### Step 1: Foundations (used by every page)
| # | Item | Size | Where in the code |
|---|---|---|---|
| 1.1 | Readable record names + one-sentence summary per record + icon per thing type | M | `knowledge_graph/explore.py` (name field and template), `ontology/simple.py` (store the chosen name field) |
| 1.2 | One legend and status words: a shared `ProofMark` component and one status function in the back end | S | new `frontend/src/components/ProofMark.tsx`, `Legend.tsx`; `api/trust.py` |
| 1.3 | Running example: pick 1 record per ontology from the data, cached by version | S | new `ontology/example.py`; header strip component |
| 1.4 | **Evidence drawer**: one back-end call that returns, for any fact, its source, check, count, date, approver and "agreed by N" (from Semantica) | M | new `api/evidence.py` (reuses `trust.py`, `review.py`, `business_rules.py`, `report_check.py`); `EvidenceDrawer.tsx` |

### Step 2: The four cards (one per layer, in this order)
| # | Item | Size |
|---|---|---|
| 2.1 | **Record card** as the default Knowledge graph view; globes become the overview; picture on request (≤ 20 dots) | M |
| 2.2 | **Thing card** on the Ontology page; 3-part trust bar; tabs from 5 to 3 | M |
| 2.3 | **Meaning card** + ◆ badge on the Semantic page; "An AI would assume" line, written by AI and checked against the data; maths check | M |
| 2.4 | **Answer card** on the Context page: "I read it as" chips, facts as chips, "I left out", "Is this right?" | M |

### Step 3: Learning from real use (the Minimal Ontology loop)
| # | Item | Size |
|---|---|---|
| 3.1 | Rules as switches, with rule-made facts drawn dashed ("worked out from…") | M |
| 3.2 | "Misreads" inbox: every corrected chip and every "No, fix it" in one list, with **"Make it a company meaning"** | M |
| 3.3 | Trust line in every header, plus "what got better or worse" after each change | S |
| 3.4 | 5-step tour on the running example | S |
| 3.5 | **Conflict card**: two values or two definitions side by side, each with its number; a person picks one; nothing is overwritten silently (from Semantica and Genie's weak spot) | M |
| 3.6 | **Decision log**: who decided what, when and why, linked to what it changed; shown on the Trust panel and downloadable as CSV/JSON (from Semantica) | S |
| 3.7 | **"As of" replay** of an answer on the ontology version it used, plus "what changed since" (from Semantica) | M |
| 3.8 | Honest scope line on every answer: what is explained and what is not (from Semantica) | S |

### Later
- "Same thing, or two?" duplicate check.
- Record history line ("open → delivered → billed").
- Multi-step "why" reports.

---

## 6. How we check it worked

- **Tests:** unit and integration tests first (pytest in batches), plus vitest, eslint and the build. Then live on the scratch server (port 8011, scratch database), never the main database.
- **The 1-minute test:** show each card to 2 or 3 of the client's managers. Ask them "What is an Order here?", "What is it connected to?", "Why is revenue 8.2 M?" and "Which of these facts is only a guess?". If they can answer without help, the card works.
- **Things to measure:** time to the first correct answer; how many answers users correct; how many ◆ company meanings get saved.

## 7. Open questions for the manager

1. Which record should the running example start from? By default we pick it from the data: one complete, typical order.
2. For SAP data with codes only: who can tell us the readable name field for each thing?
3. Should the tour be on by default for new users?
