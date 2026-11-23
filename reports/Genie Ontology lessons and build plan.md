# Databricks Genie Ontology: what to learn, and the build plan for Strata

Date: 22 Nov 2026. Sources are listed at the end. The Databricks pages are the primary sources. Atlan, Genloop and Typedef sell competing products, so their criticisms are advocacy, not neutral reviews.

## 1. What Databricks built (plain English)

**Genie Ontology** (announced June 2026, still in preview) is Databricks' "context layer" for AI agents. It has two kinds of knowledge:

- **Modeled knowledge** is what the company writes down itself: metric views (governed KPIs), business-term "Pages", domains, and certified or deprecated tables.
- **Learned knowledge** is what Genie extracts on its own from dashboards, SQL query history, metric views and Genie Agents, and in beta from BI tools such as Power BI.

The unit of knowledge is a **snippet**, for example a metric definition, an authoritative source or a business rule. Each snippet gets an **authority score** from **OntoRank**, a PageRank-like ranking. It weighs:
- where the snippet came from;
- who wrote it;
- how often people rely on it;
- its ties to certified assets;
- how fresh it is.

**When definitions conflict:** modeled knowledge beats learned knowledge, and certified knowledge beats popular knowledge. If Genie still can't decide, it asks the user to clarify.

**What a user sees:** a "Genie Ontology" citation under each answer. Click it to see which snippets were used. Click a snippet to see its description, source asset, author, domain and lineage.

**Limits:**
- Learned snippets **cannot be edited**; you have to fix the source asset.
- Agents outside Databricks connect through the Genie One MCP server, with the same permissions.

**Genie Agents** (formerly Genie Spaces) are the curated question-answering spaces. They have five building blocks.

| Part | What it is |
|---|---|
| Knowledge store | Up to 200 snippets: table descriptions, joins (with many-to-one and similar types), SQL measures, filters and fields, each with synonyms and notes. "Entity matching" stores the real values of up to 120 text columns, so "Florida" becomes `state = 'FL'`. |
| Instructions | Global rules only, such as the fiscal year, rounding and formats. Anything narrower belongs in an example query. |
| Trusted assets | Example queries and functions with parameters, written by the author. An answer that used one is marked **trusted**, and the user can change a parameter and run it again. |
| Benchmarks | Up to 500 test questions, each with the correct SQL. Each run gives a dated accuracy score. Answers are compared cell by cell to 4 significant digits. Benchmarks are only for measuring; Genie does not learn from them. |
| Feedback | Every answer asks **"Is this correct?"** with three choices: Yes, Fix it (pick a reason and try again) or Request review. The author's monitor tab can then **Add as instruction** or **Add as benchmark**. |

**What an answer looks like:**
- **Analysis** steps: how it understood the question, the data it found, the example it used, and its thinking in plain words.
- A one-line summary, a table with "Show code", an automatic chart, editable **Applied filters**, and follow-up questions.

**Agent mode** handles "why" questions. It writes a plan, runs many queries, and returns a short report that cites each step.

**Databricks' own recipe for trust:**
1. Clean descriptions and keys.
2. Write down business rules.
3. Write 10 to 15 benchmark questions, ideally collected from subject experts before building.
4. Measure a baseline, then change one thing at a time.
5. Reach more than 80% before user testing.
6. **Show the accuracy to the users.**

The biggest single improvement came from example queries.

## 2. Where Genie is weak (Strata's opening)

1. **It ranks definitions but never checks the answer against the data.** Popular does not mean correct. Typedef's example is "monthly active users" built by adding up daily distinct counts. The definition can be popular and still give the wrong number.
2. **About 1 in 6 benchmark answers was wrong** (Databricks' own 84.5% figure, on 28 questions), and Genie does not warn the user when it is unsure.
3. **Learned changes happen silently.** You can't see what it learned, can't edit a learned snippet, and there is no screen to approve learned knowledge.
4. **Conflicts are settled by Genie.** The user never sees both definitions side by side with their numbers.
5. **It only works on Databricks data,** and it needs a lot of hand setup in each Genie Agent.

**Strata's rule is "AI proposes, data checks, person decides".** That is the exact answer to points 1, 3 and 4. We should copy Genie's *visible* parts (citations, "Is this correct?", trusted marks, benchmark score) and keep our *proof from the data* on every one.

## 3. Strata vs Genie today

| Genie has | Strata today | Gap |
|---|---|---|
| Modeled vs learned, plus an authority score | Review status (confirmed, AI guess, approved), "set by" a person, certified metrics | No single **"where this came from and how strong it is"** mark on every fact |
| Snippet citations on an answer | The context pack lists its facts | Facts are not clickable to show their source, author, date and proof |
| "Is this correct?" with Yes, Fix it or Request review | `/api/ctx/{id}/feedback` becomes a note proposal (`semantic/feedback.py`) | No three-button feedback on every answer; no "Add as report check" from a good answer |
| Trusted assets (author-verified queries) | Verified questions per metric (`sem.add_verified`) | The answer is not marked "trusted" when a verified question matched |
| Benchmarks with a dated score | Report check, with runs and history (`context/report_check.py`) | The score is not shown to users at the top of each page; there is no "one change, then re-run" diff |
| Entity matching ("Florida" becomes FL) | Value suggestions in `ontology/suggest.py` | No stored dictionary of real values per text field that the question matcher uses |
| Join types (many-to-one and so on) | Links found in the data, with checks | The type of each link is not shown in plain words ("each order has one customer") |
| Applied filters the user can edit | — | Answers don't show their filters as chips the user can change |
| Clarifying question when unsure | Gaps log "not_enough" | We don't ask a clarifying question; we log a gap instead |
| Conflict: modeled beats learned | Business rules conflict with metrics (`business_rules.conflicts`) | No side-by-side view of two definitions with both numbers |
| (missing in Genie) Check the number on the data | Receipts, SQL checks, drift | **Our advantage.** Make it visible everywhere. |
| (missing in Genie) Additivity check | `semantic/model.py` marks additive or not when proposing | Not yet a warning on certified metrics ("this sums distinct counts") |

## 4. The build plan (ranked; each step tested first, then shown live)

Sizes: S = 1 to 2 days, M = 3 to 5 days, for our team.

### Phase 1: "Where did this come from?" on every fact (match Genie, then beat it)

1. **Source mark on every fact (S).** Every fact on all four pages gets one small mark:
   - **Company said** (modeled): a person wrote it, set it or approved it, shown with their name and date;
   - **Learned from data**: Strata found it, with a proof mark (✓ checked / ✗ the data disagrees);
   - **AI guess**: not checked yet.

   Rule: company-said beats learned, which beats AI guess, so this works like Genie's precedence, but it is visible. It extends rank #2 of the earlier visuals report (the shared legend).

2. **Clickable citations on answers (M).** On the Context answer, each fact becomes a chip. Clicking a chip shows: where it came from (thing, field, metric, rule or note), who wrote it and when, the proof (the SQL count or the receipt), and **"What depends on this"** (reusing `WhatDepends`). Genie shows only the source; we also show the proof.

3. **"Is this correct?" under every answer (S).** Three buttons:
   - **Yes:** offers "Save as report check" (one click adds a benchmark with today's number);
   - **Fix it:** pick a reason (wrong number / wrong meaning / missing information), which uses the existing `ctx feedback` and turns into a proposal;
   - **Ask an owner:** adds the answer to the review queue.

   Nothing changes until a person approves.

### Phase 2: Show the score to users (Databricks' trust recipe, built in)

4. **Accuracy score in the page header (S).** Every page shows, for example, "Answers checked against 14 of your reports: 12 match (86%), last run 20 Nov". It comes from the `report_check` runs. Below 80% it turns amber and says "not ready to share".

5. **Report check diff (M).** After any change (a rule, a note or a certified metric), "Run the checks again" shows **what got better and what got worse**, question by question. This is Genie's "one change at a time" made automatic.

6. **Collect report checks before building (S).** When a new ontology is set up, ask the business owner for 10 to 15 questions with the numbers from their own reports (paste or upload). Suggest questions from the real data, never fixed example text.

### Phase 3: Understand the question the way Genie does, but show it

7. **Value dictionary (M).** For each text field, store its real distinct values (up to about 1,000) with any synonyms people add. The question matcher maps "Florida", "FL" and "florida" to the same value. Values come from the data only, cached per version. Personal-data fields are skipped.

8. **"I read your question as" chips plus applied filters (M).** This is the same as rank #5 in the earlier report: chips for the metric, the filters and the time range, each of which the user can change and run again. When two readings are close, **ask one clarifying question** instead of guessing, which is better than logging a gap.

9. **Trusted mark (S).** When the answer used a certified metric with a verified question, the answer says **"Trusted: certified by Finance, matches report check 'Q3 sales pack'"**. Otherwise it says "Not yet trusted" and names the reason.

### Phase 4: Where we go further than Genie

10. **Two definitions side by side (M).** When two metrics or notes mean the same word (for example two "revenue" definitions), show both, each with its number on the real data, the difference, who wrote each one, and what uses each one. A person picks one, and the other is retired. Genie settles this silently.

11. **Metric sanity check (S).** Before a metric can be certified, check its maths: summing distinct counts, averaging averages, or summing percentages gets a warning in plain words. This is the Typedef "monthly active users" trap, which Genie can't catch.

12. **"Learned this week" review list (S).** Everything Strata learned or changed (new links, new suggestions, metric drift) goes in one list, showing *before → after*, with approve or reject. This answers Genie's weak point 3: nothing changes silently.

13. **Link types in plain words (S).** Each link reads "each Order has one Customer; a Customer has many Orders (checked: 99.4%)", built from the data's cardinality.

14. **One context layer over MCP (already partly done).** External agents get the same facts with their source marks and proof. Genie only does this for Databricks data; Strata works on any source.

### Not now (Genie has it; it doesn't fit our size)

- Learning automatically from query history or Slack.
- PageRank-style scoring. Our three marks (company said / learned / AI guess) plus proof are simpler and easier to explain.
- Agent mode for multi-step "why" reports: later, once phases 1 to 3 are done.

## 5. Order of work

1. **Phase 1, items 1 to 3.** Then stop for the user and the manager to try it.
2. **Phase 2, items 4 to 6.**
3. **Phase 3, items 7 to 9**, together with the earlier visuals report ranks #1, #3 and #4 (readable record names, record card, thing card).
4. **Phase 4.**

**Testing for every item:**
- a unit or integration test first (pytest in batches);
- vitest, eslint and the build;
- then live on the scratch server, port 8011, with the scratch database;
- never on the main database.

## 6. Sources

- Databricks docs, Genie Ontology: https://docs.databricks.com/aws/en/genie/genie-ontology/
- Databricks product page: https://www.databricks.com/product/genie/ontology
- Databricks blog, Genie One / Agents / Ontology: https://www.databricks.com/blog/introducing-genie-one-genie-ontology-and-genie-agents
- Databricks docs, Genie Agents concepts: https://docs.databricks.com/aws/en/genie/concepts
- Databricks docs, knowledge store: https://docs.databricks.com/en/genie/knowledge-store
- Databricks blog, building production-ready Genie spaces: https://www.databricks.com/blog/how-build-production-ready-genie-spaces-and-build-trust-along-way
- Databricks docs, business semantics: https://docs.databricks.com/aws/en/business-semantics
- Atlan: https://atlan.com/know/ai-agent/databricks/genie-ontology/
- Genloop: https://genloop.ai/blogs/understanding-genie-ontology
- Typedef: https://www.typedef.ai/blog/what-is-genie-ontology-databricks-continuously-learned-context-layer-explained
- ITdaily: https://itdaily.com/blogs/cloud/databricks-genie-ontology/
