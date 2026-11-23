# Accuracy and trust testing for AI answers over business data (2025-2026): market patterns and ideas for Strata

Scope: how products let users test, measure and trust AI answers over business data. Researched 2026-11-20. Most sources are vendor documentation, so they describe each vendor's own feature set in favourable terms. Independent evidence is mainly the arXiv papers.

## Q1. How do the leading products design the accuracy-testing UX (generating questions, getting ground truth, showing results, turning failures into fixes)?

### Takeaway
Every major vendor has settled on the same loop: a benchmark set of question -> ground truth (usually SQL) -> run -> Good/Bad/needs-review per question -> accuracy % plus run history plus regressions -> a "fix" action that suggests context changes -> re-run. Products differ in two places: where the questions come from (written by hand at Databricks and Snowflake, generated from dashboards and SQL history at Atlan) and how the answer is judged (an exact result-set match at Databricks, an LLM judge on executed results at Snowflake and Fabric). No vendor yet builds the test set automatically from a business user's own report.

### Cited Findings

**Databricks Genie benchmarks**
- Each benchmark item has a Question, an optional SQL Answer (ground truth) and an optional Evaluation note. The user can write the SQL or click "Generate SQL" and then verify it. Any chat response can be promoted through "Add as benchmark". The docs describe no bulk import. Limits are 500 benchmark questions per space, and Databricks recommends 2-4 phrasings per common question. — [Databricks docs](https://docs.databricks.com/aws/en/genie/benchmarks)
- Assessment in Chat mode compares result sets. A result is "Good" if the SQL or the result set matches, allowing different row order and numbers rounded to the same 4 significant digits. It is "Bad" for an empty result, an error, extra columns or a single differing cell. Only 5,000 rows are compared. Agent mode uses an LLM judge against the Evaluation note. Questions with no SQL answer are labelled "Manual review needed", and reviewers can override any verdict. — [Databricks docs](https://docs.databricks.com/aws/en/genie/benchmarks)
- The API returns failure categories such as RESULT_MISSING_ROWS, missing columns, single-cell value differences and LLM-judged wrong tables or fields. — [Databricks API: list eval runs](https://docs.databricks.com/api/azure/workspace/genie/genielistevalruns), [get eval result details](https://docs.databricks.com/api/genie/v1/genie-get-eval-result-details)
- The Evaluations tab lists timestamped runs with accuracy and creator. Detailed results are kept for 1 week. To fix a failure, the user edits the generated SQL and saves it with "Add as instruction", or "Update ground truth" accepts the agent's answer as the new truth. Genie Code can analyse a whole run and suggest instruction and context changes for the user to accept or reject. — [Databricks docs](https://docs.databricks.com/aws/en/genie/benchmarks)
- Benchmark SQL is not given to Genie as context, so it stays a held-out evaluation set. — [Databricks blog](https://www.databricks.com/blog/how-build-production-ready-genie-spaces-and-build-trust-along-way); [C# Corner write-up](https://www.c-sharpcorner.com/article/benchmarking-databricks-genie-agents-why-ground-truth-sql-matters-for-reliable-ai-applications)

**Snowflake Cortex Analyst**
- Evaluations use verified queries (VQs: a question plus expected SQL) as ground truth. The selected VQs are removed from a temporary copy of the semantic view during the run so they cannot leak into SQL generation. A VQ can either guide answers at runtime or serve as eval ground truth, not both. — [Snowflake docs: evaluations](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)
- The only metric is `sql_correctness`: the generated SQL is executed and an LLM judge compares the result sets. Metric versions v1/v2/v3 pin the judge model, prompt and rubric. v3 uses claude-sonnet-4-6 and openai-gpt-5.4 as judges, and scores from different versions are not comparable. The run screen shows Accuracy, Regressions ("previously correct but now failing") and Latency, with a per-query view of question, expected SQL, generated SQL and verdict with an explanation. — [Snowflake docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)
- Because generation is non-deterministic, Snowflake advises running the same set several times to learn its normal range before setting a threshold. It warns that time-relative VQs such as "last quarter" drift and should be pinned to absolute dates. Datasets are not generated automatically from history, there is no multi-turn evaluation, and each run covers one semantic view. The "Improve" button starts semantic-view optimisation, which suggests changes based on the failures. — [Snowflake docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)
- Verified query suggestions (Preview, October 2025): Cortex Analyst watches incoming requests and proposes candidate VQs in Snowsight. — [Snowflake release note](https://docs.snowflake.com/release-notes/2025/other/2025-10-09-verified-query-suggestions); [VQR docs](https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-analyst/verified-query-repository)

**Microsoft Fabric data agent and Power BI**
- The evaluation is code-first (Python SDK, Preview). Input is a DataFrame or CSV with the columns `question` and `expected_answer`, where the expected answer is a value such as "46,117.30", not SQL. A built-in critic prompt or a custom `critic_prompt` (with {query}, {expected_answer}, {actual_answer}) judges equivalence. Results are written to two tables (summary and `_steps`) with counts of correct, incorrect and unclear answers, and `get_evaluation_details` can return failures only. A Diagnostics button exports the configuration and execution steps. It requires F2+ or P1+ capacity. — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/data-science/evaluate-data-agent); [Fabric blog](https://blog.fabric.microsoft.com/en-us/blog/evaluate-your-fabric-data-agents-programmatically-with-the-python-sdk?ft=All)
- Power BI "verified answers" are user-approved visuals attached to trigger questions and stored on the semantic model. The agent uses the visual's columns, measures and filters to steer DAX generation. — [Microsoft Learn](https://learn.microsoft.com/fabric/data-science/data-agent-semantic-model)
- A community pattern uses existing Power BI DAX results as ground truth for the agent's answers. This is not an official feature. — [Fabric community blog](https://community.fabric.microsoft.com/t5/Data-Engineering-Community-Blog/Self-Learning-Fabric-Data-Agent-Using-pbip-SDK/ba-p/4923521)

**ThoughtSpot Spotter**
- Coaching consists of reference questions (now labelled "legacy memory sources" in 26.8, replaced by "add memory from a conversation"), business terms and data-model fixes. Thumbs feedback does not train Spotter. It only appears on the Spotter Conversations Liveboard for reviewers. — [ThoughtSpot docs 26.8](https://docs.thoughtspot.com/cloud/26.8.0.cl/spotter-reference-questions); [After coaching](https://docs.thoughtspot.com/cloud/26.2.0.cl/spotter-coach-after)
- ThoughtSpot says "most accuracy issues trace back to the data model, not missing coaching". It warns that many near-duplicate reference questions confuse Spotter and recommends testing whether it generalises before adding more. — [Coaching best practices](https://docs.thoughtspot.com/cloud/26.2.0.cl/spotter-coach-not-coach)
- Monitoring is done through votes on the Liveboard and by finding coverage gaps, which become candidates for new reference questions or terms. — [After coaching](https://docs.thoughtspot.com/cloud/26.2.0.cl/spotter-coach-after)

**Atlan Context Engineering Studio** (vendor marketing only, not independently verified)
- The studio reads BI dashboards and SQL queries, "generates 100s of questions that your AI agent needs to answer correctly", and runs them against simulated personas (Data Analyst, CEO, Analytics Engineer). For each failure it names the missing piece ("a relationship the model doesn't know, a synonym it can't resolve", a default filter) and suggests a context fix. Humans verify. When a user confirms an answer in production, it "becomes a new regression test". Context Repos are versioned like Git (branching, A/B tests, rollback), and evals persist across versions. No accuracy numbers are given. — [Atlan CES page](https://atlan.com/context-engineering-studio/)
- The stated inputs are BI dashboard questions, SQL history, known answers and production traces. Candidate context is simulated against historical traces before certification. Atlan concedes that generated scenarios "do not automatically behave like real users". — [Atlan: context simulation vs manual QA](https://atlan.com/know/ai-agent/ai-agent-evals/context-simulation-vs-manual-qa-for-ai-agents/); [What is context testing](https://atlan.com/know/ai-agent/ai-agent-evals/what-is-context-testing-for-ai-agents/)
- The Atlan docs place talk-to-data evals in Metric Studio and Atlan Trident instead, so how CES and Trident evals relate is unclear. — [Atlan docs](https://docs.atlan.com/product/capabilities/governance/context-engineering-studio)

**Google Looker / BigQuery Conversational Analytics**
- Golden queries are natural-language questions, with alternative phrasings, paired with Looker queries (`looker_golden_queries`). They do not support pivots or custom fields. — [Google docs](https://docs.cloud.google.com/gemini/docs/conversational-analytics-api/data-agent-authored-context-looker)
- Prism (open source, April 2026) runs every test question, grades each pass/fail, and has a comparison dashboard that tracks improvements and regressions across agent versions. Results can be written to day-partitioned BigQuery tables next to production agent_events. Google says a first-party product will grow out of it. — [Google Cloud blog](https://cloud.google.com/blog/products/ai-machine-learning/run-evals-for-conversational-analytics-agents-using-prism); [secondary coverage](https://letsdatascience.com/news/google-adds-agent-observability-and-governance-to-bigquery-a-216e0590)

**dbt, Wren AI, Hex**
- dbt has structural tests, not answer-accuracy tests. `dbt sl validate` runs parsing, semantic and data-platform validations (such as unique measure names and metrics that exist) and can run in CI on `state:modified+`. Saved queries are DAG nodes, and exports write their output to tables. — [dbt docs: validation](https://docs.getdbt.com/docs/build/validation); [saved queries](https://docs.getdbt.com/docs/build/saved-queries); [Classmethod CI write-up](https://dev.classmethod.jp/articles/dbt-cloud-ci-job-with-dbt-semantic-layer-object/)
- Wren AI Evaluation (paid tiers) pairs each question with ground-truth SQL, written by hand or AI-generated, and offers "View Diff": a side-by-side view of ground-truth and generated SQL plus a data preview. Question-SQL pairs are also stored to make future answers consistent. — [Wren docs](https://docs.getwren.ai/cp/guide/evaluation/overview); [Wren API](https://wrenai.readme.io/reference/knowledgesql_pairs)
- Hex: I found no source on Hex's accuracy-testing UX (see Gaps).

**LLM-eval platforms** (sources are mostly vendor comparisons)
- LangSmith builds datasets from production traces, routes traces to annotation queues (including pairwise ones) and runs online evals on live traffic. — [LangChain comparison](https://www.langchain.com/resources/langsmith-vs-braintrust)
- Braintrust turns failures into regression tests and runs evals per PR through GitHub Actions, blocking merges below a threshold. — [Braintrust article](https://www.braintrust.dev/articles/langsmith-vs-braintrust)

### Inferences
- The most reusable UX pieces are: Databricks' Good/Bad/Needs-review triage with reviewer override and "Update ground truth"; Snowflake's explicit Regressions counter and its held-out mechanism; Fabric's value-based expected answer (closest to what a business user knows: a number, not SQL); Atlan's "a confirmed answer becomes a regression test"; Wren's side-by-side diff.
- All vendors except Atlan assume the person who writes ground truth is an analyst who can write or check SQL. Strata's users hold numbers in reports, which is the gap to fill.

### Gaps
- Hex threads and semantic-model endorsement UX: not found.
- OpenAI Evals, Ragas and DeepEval UX specifics were not fetched. Only their licences are covered below.
- Atlan CES claims are unverified, and no screenshots or accuracy figures are public.

## Q2. Can tests be created automatically from existing artefacts (dashboards, Excel, PDF reports)? Does any product offer "upload your report, we check our answers against it"?

### Takeaway
Partially. Atlan says it generates questions from dashboards and SQL history, Snowflake suggests verified queries from usage, and Power BI verified answers anchor to visuals. I found no BI or semantic-layer product where a user uploads an Excel or PDF report and the system extracts each number plus the question it answers, then scores the agent against them. The closest are generic finance "output verifiers" that compare two numbers. This is an open niche for Strata.

### Cited Findings
- Atlan: questions are generated from BI dashboards and SQL queries into an eval suite (vendor claim). — [Atlan](https://atlan.com/context-engineering-studio/)
- Snowflake: verified query suggestions come from observed requests, but the docs state that eval datasets are not auto-generated from query history or synthetic sources. — [Snowflake release note](https://docs.snowflake.com/release-notes/2025/other/2025-10-09-verified-query-suggestions); [Snowflake evaluations](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)
- Fabric accepts value answers in CSV (question, expected_answer), which is what a report-derived test set would look like, but the user has to build the CSV. — [Microsoft Learn](https://learn.microsoft.com/en-us/fabric/data-science/evaluate-data-agent)
- Energent's "AI accounting output verifier" checks AI totals and ratios against source documents and gives a pass/fail with evidence. Its embedded tool only compares two numbers and does not inspect files, formulas or source rows. — [Energent](https://www.energent.ai/ugc/en/tool/ai-accounting-output-verification)
- Finance practitioner guidance: trace every AI number to a source record, check units before the maths, then recompute derived numbers. — [Rework](https://resources.rework.com/libraries/ai-for-finance/ai-accuracy-controls-in-finance); [Layerproof](https://layerproof.app/blog/How-to-verify-AI-data-for-financial-reports/)
- Daloopa's open financial-retrieval benchmark found about 53% conditional accuracy on attempted answers for one chatbot, which shows how often unchecked AI numbers are wrong. — [Daloopa](https://daloopa.com/blog/ai/open-source-benchmark-to-measure-llm-accuracy-in-financial-retrieval)

### Inferences
- Strata's existing "report check" form, which scores a match to the report's precision and flags unit errors, refusals and silent wrong numbers, is already closer to what business users need than anything vendors ship. The step up is to remove the typing: extract (number, label, period, filter) tuples from the uploaded report, turn each into a question, and keep the report's displayed precision as the tolerance.
- Precision-aware matching (Databricks uses 4 significant digits; Strata uses the report's own rounding) and unit-error detection (x1000, %, currency) are differentiators. No vendor documents unit-error classification.

### Gaps
- I found no evidence of a product that extracts questions from Excel/PDF reports for agent evaluation. This is absence of evidence from about 18 searches, not proof that none exists.

## Q3. Which answer-level trust signals are shown to end users?

### Takeaway
In-product signals are thin: "verified" provenance (Snowflake VQR, Power BI verified answers, ThoughtSpot reference questions), showing the SQL or steps, and refusal when context is missing. Research shows that self-consistency confidence is only a moderate predictor (AUROC about 0.61-0.68). Verification-style signals such as a judge ensemble do better (about 0.82).

### Cited Findings
- When a question resembles a VQR entry, Cortex Analyst uses the verified SQL. This is the "verified" provenance signal. — [Snowflake VQR](https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-analyst/verified-query-repository)
- Genie declines to generate SQL when it lacks context, which Databricks describes as intended anti-hallucination behaviour. Databricks recommends sharing benchmark accuracy and the unmet gaps with stakeholders, and treating above 80% benchmark accuracy as the bar before user acceptance testing. — [Databricks blog](https://www.databricks.com/blog/how-build-production-ready-genie-spaces-and-build-trust-along-way)
- Confidence for text-to-SQL: consistency-based methods (generate N queries and check agreement) perform best among black-box approaches, and calibrated scalar scores work better than binary abstention. — [arXiv 2508.14056](https://arxiv.org/abs/2508.14056)
- A selective-prediction study (July 2026) found that string, structural and execution self-consistency all sit at about 0.61-0.68 AUROC, a two-provider judge ensemble reaches about 0.82, and one round of self-correction barely changes accuracy while badly miscalibrating confidence. These figures come from a search snippet, not a full read. — [arXiv 2607.06799](https://arxiv.org/abs/2607.06799)
- TrustSQL benchmark: the model either returns SQL or abstains, with separate answerability detection and error detection stages. — [arXiv 2403.15879](https://arxiv.org/pdf/2403.15879v2)
- A governed confidence-score study on BIRD with a pre-registered check on Spider reports that verification signals can outrank consistency. — [arXiv 2610.17256](https://arxiv.org/pdf/2610.17256)
- ThoughtSpot thumbs votes are visible only to reviewers, not to other end users. — [ThoughtSpot](https://docs.thoughtspot.com/cloud/26.2.0.cl/spotter-coach-after)

### Inferences
- A good badge set for Strata would be: "Matches your report" (a tested question whose number agreed), "Uses a governed metric" (from the semantic layer), "Consistent across N phrasings", and "Unverified, check before using". A badge linked to a real stored check is more honest than a model confidence score.

### Gaps
- I found no public screenshots or numbers on how end users respond to confidence badges in BI tools.

## Q4. How much do these loops improve accuracy, and what are the known pitfalls?

### Takeaway
Vendor case studies show large jumps on small sets (Databricks: 0 -> 54 -> 77 -> 100% on 13 questions). Independent work shows that the ground truth itself is often wrong (52.8-66% annotation errors in BIRD Mini-Dev and Spider 2.0-Snow), that LLM judges agree with experts better than raw execution match, and that runs are non-deterministic, so single-run scores mislead.

### Cited Findings
- Databricks walkthrough with 13 benchmark questions: baseline 0 correct; foundational metadata 54%; example SQL for custom metrics 77%; text instructions for domain rules 100%. Recommended set size is 10-20 questions. This is vendor-authored. — [Databricks blog](https://www.databricks.com/blog/how-build-production-ready-genie-spaces-and-build-trust-along-way)
- Annotation errors: BIRD Mini-Dev 52.8%, Spider 2.0-Snow 62.8% (arXiv v3) or 66.1% (CIDR 2026 version). After correcting 100 BIRD Dev examples, agent rankings correlated only weakly with the originals (Spearman 0.32, p=0.23). The SAR-Agent LLM reviewer flagged errors with 83% precision. — [arXiv 2601.08778](https://arxiv.org/abs/2601.08778); [CIDR 2026](https://vldb.org/cidrdb/2026/text-to-sql-benchmarks-are-broken-an-in-depth-analysis-of-annotation-errors.html)
- Execution accuracy has many false positives and negatives. The FLEX LLM judge reaches Cohen's kappa 87.04 with experts, against 62 for execution accuracy. — [FLEX arXiv 2409.19014](https://arxiv.org/html/2409.19014v4)
- Committees of judges can share correlated errors, so a majority vote can amplify bias, and false accepts cost more than false rejects. — [arXiv 2602.18492](https://arxiv.org/pdf/2602.18492)
- A single ground-truth SQL undercounts valid answers. One paper proposes multiple ground-truth interpretations. — [arXiv 2506.13785](https://arxiv.org/html/2506.13785v1)
- Snowflake on run variance: run the set several times and set thresholds from the normal range. Judge-version changes make scores incomparable. Relative dates drift. — [Snowflake](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)
- Leakage: Snowflake removes eval VQs from the model's context during runs, and Databricks keeps benchmark SQL out of Genie's context. ThoughtSpot warns that near-duplicate examples can confuse the model, a form of overfitting. — [Snowflake](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations); [Databricks blog](https://www.databricks.com/blog/how-build-production-ready-genie-spaces-and-build-trust-along-way); [ThoughtSpot](https://docs.thoughtspot.com/cloud/26.2.0.cl/spotter-coach-not-coach)
- Databricks' exact-match rule can mark large or reordered results Bad, because only 5,000 rows are compared. — [Databricks docs](https://docs.databricks.com/aws/en/genie/benchmarks)

### Inferences
- For Strata, a report number is excellent ground truth for a scalar, because a human already published it. Two failure modes need handling. The report itself may be wrong or stale, so a mismatch should mean "investigate", not "AI wrong". The report may also use a different definition (gross vs net, fiscal calendar), so the mismatch reason should be captured as a definition fix in the ontology or semantic layer.
- Keep the report-derived questions held out from the agent's examples, as Snowflake does. Otherwise a fix that pastes the answer into context inflates the score.

### Gaps
- I found no independent before/after accuracy numbers for Snowflake VQR, ThoughtSpot coaching or Atlan CES.

## Q5. Which open-source eval tools could Strata borrow from, and under what licences?

### Takeaway
Use permissive tools (MIT/Apache) for runners and metrics. Avoid embedding Arize Phoenix code because of its Elastic License 2.0. Google's Prism is the most domain-specific reference design for conversational analytics evals.

### Cited Findings
- promptfoo: MIT, YAML test cases with CI gating and regression and red-team testing. DeepEval: Apache-2.0, pytest-style gating, with no production trace dashboard. Ragas: a metrics library, with its licence reported as both MIT and Apache-2.0 in secondary sources (check the repo). Arize Phoenix: Elastic License 2.0, source-available rather than OSI open source, with versioned datasets and experiments. Langfuse: MIT core, but the `ee/` directories are under an enterprise licence. LLM-as-judge was reportedly moved to MIT in June 2025. These come from secondary comparison blogs. — [MLflow comparison](https://mlflow.org/articles/tags/llm-evaluation-tools-compared/); [Framework profiles](https://aadhar-build.github.io/llm-evals-comparison/frameworks/); [Arize comparison (vendor)](https://arize.com/llm-evaluation-platforms-top-frameworks)
- Prism (Google): open source, pass/fail per question, a version-comparison dashboard, and results stored in day-partitioned tables. — [Google Cloud blog](https://cloud.google.com/blog/products/ai-machine-learning/run-evals-for-conversational-analytics-agents-using-prism)
- Snowflake's open-source semantic-model-generator app has a "Save as verified query" flow worth copying. — [Snowflake VQR docs](https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-repository)

### Inferences
- Strata is Python-only with no Docker, so the logic is cheapest to build natively: result-set comparison, the report-precision tolerance it already has, and an optional judge. promptfoo/DeepEval-style YAML or pytest export can follow later for CI.

### Gaps
- I did not verify Prism's licence or the exact licences of OpenAI Evals or Ragas against their repositories.

---

## Proposal: the best accuracy and trust experience for Strata ("Prove it against my report")

**Flow for a busy business user**
1. **Drop a report.** The user uploads an Excel, CSV, PDF or Power BI/Excel pivot export they already trust (the monthly pack). *Automatic:* Strata extracts each number together with its row and column labels, period, filters, units and displayed precision, giving tuples such as (Revenue, EMEA, Q3 2026, EUR thousands, 1 dp) = 4,812.3.
2. **Strata proposes the questions.** *Automatic:* each tuple becomes a plain-English question ("What was EMEA revenue in Q3 2026?") plus 2 AI paraphrases, which echoes Databricks' 2-4 phrasings advice. Relative dates are pinned to absolute ones (Snowflake's drift warning). Questions are ranked so the most important rows come first (totals, KPIs that map to governed metrics).
3. **One-screen confirmation.** *Person, about 1 minute:* a checklist of "Use these 12 numbers as the truth?" showing each number highlighted in a thumbnail of the report. The user unticks anything wrong or stale. Ground truth comes from what the user already published, so nothing has to be typed.
4. **Run.** *Automatic:* each question runs fresh with no shared context, 3 times to measure consistency, with the report questions held out from the agent's examples to prevent leakage.
5. **Scorecard.** Each line gets one verdict, in words a business user understands: **Match** (within the report's precision), **Off by a unit** (x1000, %, currency), **Different definition** (for example gross vs net, detected when another governed metric matches), **Wrong number** (silent error, shown in red at the top), **Refused** (shown as a coverage gap, not a failure), and **Unstable** (the phrasings disagree). The headline reads "11 of 12 numbers match your report".
6. **Fix in one click.** For each failure, Strata suggests the smallest fix: add a synonym, set a default filter, correct a unit, or map to a metric, following Atlan's failure -> missing piece pattern. The user picks "Report is right" (fix Strata), "Report is wrong or old" (drop the test), or "Both are right, different definitions" (add a named variant). The change is re-tested at once on that question and its paraphrases.
7. **Keep it as a guard.** The confirmed set becomes the "Report pack" regression suite. It re-runs automatically when the ontology, semantic or context layer changes, or nightly. A history sparkline shows accuracy per suite, and a Regressions counter shows "was right, now wrong" (Snowflake-style). Any regression is pushed to the dashboard and the CLI (`strata check --suite q3-pack`, with a non-zero exit for CI).
8. **Trust in everyday answers.** When a chat answer hits a metric covered by a passing test, it shows "Matches Q3 pack ✓ (checked 2 days ago)". Otherwise it shows "Not yet checked", with a one-click "Check against a report" option. Each answer has a "Show how" link to its lineage (the ontology path and SQL).

**Automatic vs person:** Strata does extraction, question writing, paraphrasing, running, classification, fix suggestions and re-runs. The person ticks the numbers to trust, picks which side is right for each failure, and approves the fixes.

**Ranked feature ideas**
1. **Report import -> auto test set** (extract numbers, labels, period, units and precision from xlsx/csv/pdf; generate questions plus paraphrases; one-screen tick confirmation). Replaces the manual form. **L** (PDF tables are the hard part; start with xlsx/csv, which is **M**).
2. **Business-language verdict classes** (Match / Off by a unit / Different definition / Wrong number / Refused / Unstable) on top of the existing precision scoring. **S-M**
3. **Suites with history and a regression counter**, auto re-run on layer change, plus a `strata check` CLI exit code for CI. **M**
4. **Failure -> one-click fix** (synonym, default filter, unit, metric mapping) with an immediate re-test of the question and its paraphrases, and a "report is wrong / both right" triage. **M**
5. **Consistency check across 3 paraphrases and runs**, shown as an "Unstable" flag. It is a cheap confidence signal, but research rates it only a moderate predictor, so do not present it as a probability. **S**
6. **"Matches your report" badge on live answers**, linked to the last passing test, with "Not yet checked" otherwise. **S**
7. **Promote a confirmed chat answer to a test** ("This number is right -> keep checking it"), following Databricks "Add as benchmark" and Atlan's "a confirmed answer becomes a regression test". **S**
8. **Data-driven question suggestions** from the user's own query log and ontology KPIs, to fill coverage gaps the report does not contain (in the spirit of Snowflake verified-query suggestions). **M**
