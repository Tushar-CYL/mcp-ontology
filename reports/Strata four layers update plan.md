# Strata update plan: four layers, shown so that anyone can understand them

Date: 22 Nov 2026.

This plan pulls together all the research we did:
- the South Park Ontology Explainer;
- the Minimal Ontology Principle (Modern Data 101);
- the visuals research (graph literacy studies, Palantir, Neo4j, Microsoft Fabric, Atlan, ThoughtSpot and others), in `reports/Simpler ontology visuals for business.md`;
- the Genie and Databricks reading, in `reports/Genie Ontology lessons and build plan.md`.

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
- **Each fact is a chip:** click it to see its source, who wrote it, its proof, and what depends on it.
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
