# Show real records first, prove every line

*Research report, 21 November 2026. Built from the three notes in `research_notes/Simpler ontology visuals for business/` (graph literacy, vendor visual patterns, semantic and answer explanations), the South Park Ontology Explainer shared by the manager, the Modern Data 101 "Minimal Ontology Principle" article, and a description of what Strata shows today. The earlier report `Strata product ideas from market.md` was used as background only. This report is about how things look and read on screen, not about new back-end features.*

## Summary in simple English

Business users understand **one real example, written as sentences, with a clear sign of what is proven**. They do not understand big pictures of many dots, column codes, or tables of field settings. The research agrees on this from three sides. Studies show people **struggle to read node-link pictures with more than about 50 nodes** when lines are dense ([Yoghourdjian et al. 2020](https://vcg.seas.harvard.edu/publications/20201001-scalability-of-network-visualisation-from-a-cognitive-load-perspective)). Interviews with knowledge-graph teams found that **end users preferred simple tables and "Wikipedia-style" entity pages** to graph screens ([Li et al.](https://arxiv.org/html/2304.01311)). And almost every serious vendor (Palantir, Microsoft Fabric IQ, Neo4j Bloom, Stardog, Atlan, Collibra) opens on **search, then a list, then one profile page per record**, with the graph as an extra.

The South Park explainer teaches the same thing by example. It shows one small graph of about 12 circles, real people before their types, every line labelled with a plain verb, facts written as sentences, and a legend where **solid means "we stated it" and dashed means "a rule worked it out"** ([South Park Ontology Explainer](https://southpark-ontology-explainer.jessica-tali-7056.chatgpt.site/)). The Modern Data 101 article adds the second big idea: **only define what is different in this company**. An AI already knows what "customer" usually means. The work is to find and show where this company means something else ([Modern Data 101](https://moderndata101.substack.com/p/minimal-ontology-principle)).

Strata today has strong proof behind the screens but shows it in a technical way. The Ontology page leads with a field table. The Knowledge graph page leads with about 150 dots per thing type, labelled with SAP codes such as "Sales Document 0001984611". The Semantic and Context pages are closer to the market, but they show formulas, joins and build steps before the plain answer.

**The proposed change is one design idea used in all four layers: a "record card" that starts with a real example in one sentence, lists facts as sentences, and marks each fact with the same legend.** Solid with a tick means the data proved it. Dashed means the AI guessed it or a rule worked it out. A small "Means something different here" badge marks company-specific meaning. No product we found ships that last badge, or a per-fact "proved by the data" mark. That combination is what makes Strata unique.

**Top 5 changes (details and effort at the end):** (1) readable record names and a one-sentence summary for every record, with an icon per thing type; (2) a record card as the default Knowledge graph view, with a small picture of at most about 20 nodes on request; (3) one shared legend and plain status words across all four pages; (4) an Ontology page that opens on a real example and facts as sentences, with the field table one click deeper; (5) an answer card on the Context page that says "I read your question as..." before showing how it got the answer.

*Effort scale (small React team): **S** = a few days to one week, **M** = one to three weeks, **L** = one to two months.*

*Note on the wireframes: names and numbers inside them (ACME GmbH, Hamburg, M. Weber, 412,000 EUR, 214 claims) are made-up placeholders to show the layout. Only the SAP SALT record counts and the 81% headline come from Strata today. In the product, every example must come from the real data.*

**A warning about the evidence.** The node-count limits come from one lab study of one task (finding a path). The "entity pages beat graphs" finding comes from interviews, not a controlled test with business users. Most vendor facts come from vendor documents, which describe what they intend, not how well it works. The 10 to 30 node target used below is our own inference from the studies, not a measured number.

---

## What the research says about reading pictures of data

This section collects the evidence that every layer below uses. It is short on purpose.

**Big graph pictures break down fast.** In a study with 22 people and brain and eye measures, readers "have significant difficulty finding the shortest path in high-density node-link diagrams with more than **50 nodes** and even low-density graphs with more than **100 nodes**". Their mental effort rose and then fell, which the authors read as people giving up ([Yoghourdjian et al. 2020](https://vcg.seas.harvard.edu/publications/20201001-scalability-of-network-visualisation-from-a-cognitive-load-perspective)). The limit was measured for one task only, and most graph studies use small graphs ([survey, arXiv 1809.00270](https://arxiv.org/abs/1809.00270v1)). Novices also lack the habits to read node-link pictures at all. Unlike a bar chart, a node-link picture has no fixed axis, and museum visitors mostly could not explain how to read one ([Zoss 2018](https://cns.iu.edu/docs/publications/2018-Zoss-NetworkVisualizationLiteracy.pdf)).

**Business users prefer pages and tables.** Li et al. interviewed 19 knowledge-graph practitioners. They found node-link diagrams "are often ineffective for both generating and delivering insights from large KGs". One team's end users preferred simple tables to a custom graph tool. Wikipedia-style entity pages with links to the next entity were preferred for open exploration. One practitioner saw users stop trusting results once the graph got too complex. The authors suggest **"knowledge cards", like a baseball card**, with the most important facts about one entity ([Li et al.](https://arxiv.org/html/2304.01311)). In a separate study of an AI-assisted graph tool, people used tables, not graphs, for results ([arXiv 2505.21512](https://arxiv.org/abs/2505.21512)).

**Start from one thing, then expand.** The classic pattern is "search, show context, expand on demand". The system finds the thing the user asked about, shows its closest neighbours, and lets the user grow the picture in the most useful direction ([van Ham and Perer 2009](https://dig.cmu.edu/publications/2009-doigraphs.html)). Nielsen Norman Group adds a firm rule: **keep to two levels** (overview, then detail); three or more levels usually means the design should be simpler ([NN/g](https://www.nngroup.com/articles/progressive-disclosure/)).

**Real examples first, then the type.** Learning research calls this "concreteness fading": start with concrete cases, then move clearly to the abstract idea. Going from concrete to abstract helped people apply what they learned better than the other order ([Fyfe et al. 2014, via McNeil and Fyfe](https://pcl.sitehost.iu.edu/rgoldsto/courses/cogscilearning/McNeilFyfe12.pdf)). This comes from maths and science teaching, not from ontology screens, and a 2020 review says it "may not be as generalizable as has been suggested" ([Educational Psychology Review 2020](https://link.springer.com/article/10.1007/s10648-020-09581-7)).

**Words help; sentences help.** People preferred charts with the most text notes over minimal charts ([Stokes et al. 2023](https://vis.mit.edu/pubs/vis-text-balance)). Concept maps, which are labelled "thing, verb, thing" statements, gave a clear learning gain (overall **g = 0.58** across 142 effect sizes) ([Schroeder et al. 2017](https://link.springer.com/doi/10.1007/s10648-017-9403-9)). A fact written as "Customer ACME places Order 0001984611" is exactly such a statement.

**Dashed lines work for "not certain", but pictures can over-sell.** In a test of ways to show uncertain lines, people preferred **dashed lines** over blur, grey or sketchy lines ([Boukhelifa et al. 2012](https://ieeevis.org/year/2012/paper/infovis/evaluating-sketchiness-visual-variable-depiction-qualitative-uncertainty)). But even experts **over-trusted wrong AI answers because the graph picture looked convincing** ([arXiv 2505.21512](https://arxiv.org/abs/2505.21512)). So a line style alone is not enough. Every unproven fact also needs a status word and a reason.

**Icons that carry meaning are fine; decoration is not.** Pictures that stand for data had "no user costs – and some intriguing benefits", while extra decorative images can distract ([Haroz, Kosara and Franconeri, CHI 2015](https://tableau.com/research/publications/isotype-visualization-working-memory-performance-and-engagement-pictographs)). One icon per thing type (customer, order, address) is meaningful.

---

## Layer 1. Ontology: show one real order before the word "Sales Document"

### 1. What users need to understand, in one line

"These are the kinds of things in our business, how they connect, and which of the AI's claims about them the data has proved."

### 2. What Strata shows today, and why it is hard

Strata's Ontology page shows a list of things on the left (name, field count, record count). On the right is a table of fields: label, column code, meaning, role pill, "Checked in data" or "Data disagrees" badge, proof text, "Set by AI/you", and review status. Above are five tabs: Overview, Map, Business rules, Ask, Use it. There is a review queue, a "Why you can trust this ontology" panel and a "What depends on this?" list. The headline is a percentage, for example **81% of AI claims confirmed** on the SAP SALT sales data.

The proof is excellent. The problem is the order and the form. A manager opening "Sales Document" sees a table of columns such as `VBELN` and `ERDAT` with role pills. That is the schema, the most abstract level, shown first. There is no real order on the screen, so there is nothing concrete to hold on to. The Map tab is a node-link picture of types, again with no examples. Five tabs plus a panel plus a queue is more than the two levels NN/g advises. And "81% confirmed" is a single abstract number. It does not say what the other 19% are or what the user should do about them.

### 3. What the South Park explainer and the Minimal Ontology article teach

The South Park explainer gives a clear recipe ([South Park Ontology Explainer](https://southpark-ontology-explainer.jessica-tali-7056.chatgpt.site/)). It starts with a one-line definition: an ontology defines kinds of things, their properties and rules; the knowledge graph uses them to connect facts. It shows **concrete people first** (Stan, Kyle, Randy), and the classes (Person, Student) are drawn as dashed circles beside them. Facts are written as sentences, "Randy → is parent of → Stan", in a checklist. Ticking a fact shows it on the graph. A plain summary box describes one person: "Stan is explicitly recorded as a Person. His recorded role is Student. His recorded grade is 4." Rules are toggles in plain words. Turning on "a parent of a parent is a grandparent" draws dashed orange lines and explains each one: "Worked out by the property chain rule from 'Marvin is parent of Randy' and 'Randy is parent of Stan'". There is also a warning: a model can be wrong without any contradiction. If Stan is split into "Stan-grade-4" and "Stan-grade-5", a search misses his parent.

The Minimal Ontology article adds a filter for what to show at all. The model already knows most business meanings. So the screen should spend attention on the **delta**: the places where this company's meaning differs ([Modern Data 101](https://moderndata101.substack.com/p/minimal-ontology-principle)). For the Ontology page, this means the field table should not give equal space to "Customer Name" (obvious) and "Order Type ZOR = standard order, excluding returns" (company-specific).

### 4. What the best tools do

Microsoft Fabric IQ splits the **schema canvas** from the **instances**. It has a "Neighborhood" view that shows one type and its related types only, and an Instances tab with real rows ([MS Learn](https://learn.microsoft.com/en-us/fabric/iq/ontology/how-to-use-preview-experience)). Palantir gives every type an automatic **Standard Object View**, a profile page built from the type's settings with no setup ([Palantir Object Views](https://www.palantir.com/docs/foundry/object-views/overview/)). metaphactory offers each resource as a Page, a **Statements** list (facts as lines) and a Graph ([AWS blog](https://aws.amazon.com/blogs/database/visualize-and-explore-knowledge-graphs-quickly-by-connecting-metaphactory-to-amazon-neptune)). Atlan glossary pages lead with a definition, owner and certificate, and mark related versus "recommended" terms ([Atlan](https://docs.atlan.com/product/capabilities/governance/glossary/concepts/what-is-a-glossary)). None of these shows a per-claim "proved by the data" mark. Fabric IQ, in an earlier version, showed type nodes first and needed a query to load instances ([MS Learning lab](https://microsoftlearning.github.io/mslearn-fabric/Instructions/Labs/27-visualize-ontology.html)), which is the opposite of "real examples first".

### 5. Proposed new design (our design; not shipped by anyone in this form)

The page keeps the left list of things but adds an icon per thing and a plain-English count ("Sales Documents, 0.5 million"). Clicking a thing opens a **thing card** with three blocks, top to bottom.

```
+----------------------------------------------------------------+
| [order icon]  Sales Document                                   |
| "A customer's order. Each one has a customer, a date, a total  |
|  and one or more order lines."                                 |
|                                                                |
| ONE REAL EXAMPLE                         [Show another example]|
|  Order 0001984611 from ACME GmbH, created 3 Mar 2024,          |
|  12,400 EUR, 4 order lines, shipped to Hamburg.                |
|  This is one of 512,000 Sales Documents.                       |
|                                                                |
| WHAT WE KNOW ABOUT SALES DOCUMENTS            [legend ⓘ]       |
|  ✓── Each order belongs to one Customer    proved on 99.8%     |
|  ✓── Each order has 1 or more Order Lines  proved on 100%      |
|  ┄┄  Order type "ZOR" means a standard     AI guess, you decide|
|      sale                       [Means something different ◆] |
|  ✗── "Net value" is always positive        data disagrees: 312 |
|                                             returns  [see them]|
|                                                                |
| AI CLAIMS:  ███████████████░░░░  174 proved · 12 disagree ·    |
|             28 for you to decide   [Decide now]                |
|                                                                |
| [Show all 42 fields]  [Show as picture]  [What depends on this]|
+----------------------------------------------------------------+
```

The first block is a one-sentence meaning written by the AI and checked by the user. The second block is **one real example**, picked by the AI from the data (a record with readable fields and typical links, following the "suggestions from the real data" rule). "Show another example" picks a different one. The line "This is one of 512,000 Sales Documents" makes the move from record to type, the concreteness-fading step. The third block lists **facts as sentences**, one line each, with the shared legend (see the cross-layer section): solid line with a tick for proved, dashed for an AI guess, a cross for "data disagrees". Each line ends with the proof in plain words and a link: "proved on 99.8%" opens the records that pass and fail. Company-specific meanings carry the ◆ badge.

The headline 81% becomes a **three-part bar with counts**: proved, data disagrees, for you to decide. The "Decide now" button opens the existing review queue. Each review item shows a real example record, the AI's claim as a sentence, and what the data found, with three buttons: "Yes, that's right", "No, change it", "Not sure, ask someone".

The field table does not go away. It moves behind "Show all 42 fields", one click deeper, for builders. "Show as picture" opens a **Neighborhood** view: this thing in the middle, its directly linked things around it, every line labelled with a verb ("places", "ships to", "contains"), and at most about 12 boxes. No full-ontology map by default.

The tabs shrink from five to three: **This thing** (the card above), **Rules**, **Use it**. "Ask" moves to the Context page, where questions already live. This follows the user's own rule of simple screens without tab sprawl.

The **Rules** tab copies the South Park toggles. Each rule is one sentence ("An order's total equals the sum of its lines"). Next to it: "Checked on 512,000 orders: 511,688 pass, 312 fail [see the 312]". If a rule creates new facts (for example "a customer's region is the region of its sold-to address"), turning it on shows those facts as **dashed lines** with "Worked out by this rule from: [fact A] and [fact B]".

A **"Same thing, or two?"** check covers the South Park split-identity warning. Strata can look for records that seem to be one real thing stored twice, for example two customer numbers with the same name and address. These show in the review queue as "These 2 customers look like the same company. Merge them for answers?" This needs a back-end check (see the top list).

### 6. What makes it unique to Strata

Every fact line carries **its own proof from the data**, with a count and a link to the passing and failing records. South Park shows stated versus worked-out facts. Vendors show definitions and owners. No one we found shows "proved on 99.8% of 512,000 records" per sentence. The three-part bar turns Strata's rule, "AI proposes, data checks, person decides", into one picture.

---

## Layer 2. Knowledge graph: replace 150 dots with one readable record card

### 1. What users need to understand, in one line

"Here is one real record, the records linked to it, and how two records are connected."

### 2. What Strata shows today, and why it is hard

The Knowledge graph page shows three build steps with counts (read schema, read data, make graph). The main view is "Globes": one circle-cluster per thing type, with about 150 real records as dots and lines between them. Hovering lights links. Clicking opens a record panel with fields and expandable linked records. There is a path finder, plus "Web" and "Record by record" views.

The Globes view is attractive, but four types times 150 dots is about **600 dots**, far past the 50 to 100 node range where path reading breaks down ([Yoghourdjian et al. 2020](https://vcg.seas.harvard.edu/publications/20201001-scalability-of-network-visualisation-from-a-cognitive-load-perspective)). The dots do not carry meaning a manager can read. Worse, the labels are SAP codes: "Sales Document 0001984611", "Customer 0000100234". A business user cannot tell one order from another. Three different picture views also ask the user to learn three ways of reading. The record panel, which is the most useful part, is hidden behind a click on a dot.

**We must be honest: the SAP SALT data has codes, not friendly names.** Many records have no name field. Any design that assumes "Stan" and "Kyle" will fail on this data. The design below solves readability first.

### 3. What the South Park explainer and the Minimal Ontology article teach

South Park shows **one small graph of about 12 circles**, not hundreds. Every line has a verb label. Each person has a portrait, so you know at once who is who. Tapping a circle or line shows its facts and sources. The summary box writes the record as plain sentences ([South Park Ontology Explainer](https://southpark-ontology-explainer.jessica-tali-7056.chatgpt.site/)). It also teaches that a thing can change (Stan moves to grade 5) while its identity stays, and that history needs dates. For Strata, an order's status changes while its order number stays.

The Minimal Ontology article has less to say here. Its one lesson: when a record's field uses a company-specific code (order type ZOR, a sales org code), the screen should translate it and mark it as company meaning ([Modern Data 101](https://moderndata101.substack.com/p/minimal-ontology-principle)).

### 4. What the best tools do

Palantir opens on **Object Explorer: search, then a table or chart of a set, then one Object View per record**. The graph tool, Vertex, is a separate app for analysts. Even there, the graph starts empty and grows from objects you pick. A right-click shows **related types with counts** before you add them, a node can be drawn **as a full object card**, and "group into edge" folds transaction records into the line between two parties ([Palantir Object Explorer](https://www.palantir.com/docs/foundry/object-explorer/overview/); [Vertex](https://palantir.com/docs/foundry/vertex/explore-object-relationships/); [Vertex display options](https://palantir.com/docs/foundry/vertex/graphs-display-options/)). Neo4j Bloom, the most graph-centred business tool, starts from an **empty scene and a search box**, and pairs the canvas with a **card list** and an Inspector that shows neighbours as cards. A "Perspective" gives business names, captions and colours to the raw graph ([Bloom card list](https://neo4j.com/docs/bloom-user-guide/current/bloom-visual-tour/card-list/); [Bloom perspectives](https://neo4j.com/docs/bloom-user-guide/current/bloom-perspectives/bloom-perspectives/)). Stardog's entity page shows **up to 10 linked records per link type**, each clickable ([Stardog Explorer](https://stardog.com/blog/discover-connections-in-your-data-fabric-with-stardog-explorer/)). Collibra's current docs list relations as **a table or tiles** ([Collibra 2026.02](https://productresources.collibra.com/docs/collibra/2026.02/Content/Assets/co_asset-pages.htm)). Kumu, a full-map tool, offers a "prompted" mode that gives readers a search box instead of the full map ([Kumu focus](https://docs.kumu.io/guides/focus)). Google's Knowledge Panel shows related entities as a "People also search for" strip, without drawing a graph at all ([Search Engine Land](https://searchengineland.com/guides/knowledge-graph)).

The pattern is the same everywhere: **search, list, card; graph only on request, and small.** Cambridge Intelligence, a graph vendor and so biased toward graphs, gives the same advice for hairballs: design for the task, filter and group, and say clearly what was left out ([Cambridge Intelligence](https://cambridge-intelligence.com/how-to-fix-hairballs/)).

### 5. Proposed new design (our design; parts are copied from the tools above)

**Step 1: make records readable.** Every record gets a **display name** and a **one-sentence summary**, built by a template per thing type. The AI writes the template once per type, from the ontology. The values are filled straight from the data, so the sentence cannot invent facts. The name rule tries, in order: a real name field (customer name), a description field (material text), a decoded code (country "DE" becomes "Germany", if the data has a text or lookup table), and finally the most telling values (amount and date). Examples:

- Customer: "**ACME GmbH** (customer 0000100234), Hamburg, Germany. 1,204 orders since 2021."
- Sales Document: "**Order of 3 Mar 2024 from ACME GmbH**, 12,400 EUR, 4 lines (no. 0001984611)."
- Order Line: "**Line 20 of that order**: 50 × Steel bolt M8, 1,100 EUR."
- Postal Address: "**Hafenstrasse 12, Hamburg**, used by 3 customers."

The code is still shown, but small and after the words. Each thing type gets **one icon** (person-and-building for customer, document for order, list for order line, pin for address), which encodes the type and so is meaningful, not decoration ([Haroz et al. 2015](https://tableau.com/research/publications/isotype-visualization-working-memory-performance-and-engagement-pictographs)). Where no readable field exists, the card says so plainly: "This record has only codes. [Ask the data owner for a name field]".

**Step 2: the record card is the default view.** The page opens with a search box ("Find a customer, order, product...") and three to five **starting examples picked by the AI from the data**, such as "The customer with the most orders this year" or "The largest order last month". Choosing one opens the card:

```
+--------------------------------------------------------------+
| [customer icon] ACME GmbH                 customer 0000100234 |
| ACME GmbH is a customer in Hamburg, Germany. It placed 1,204 |
| orders since 2021, worth 8.2 million EUR.                     |
|                                                               |
| FACTS                                                         |
|  ✓── Country: Germany                                         |
|  ✓── Sold-to address: Hafenstrasse 12, Hamburg                |
|  ┄┄  Region: North (worked out by rule "region of address")  |
|                                                               |
| LINKED RECORDS                                                |
|  Places → 1,204 orders           [5 latest as mini cards]  ▸ |
|  Ships to → 3 addresses          [3 mini cards]            ▸ |
|  Buys → 86 products (via order lines)                      ▸ |
|                                                               |
| [Show as picture]  [How is this connected to ...?]           |
+--------------------------------------------------------------+
```

Linked records are **grouped by the link verb, with a count**, and show the first five as mini cards (Stardog shows 10; five keeps the card short). Clicking a mini card opens that record's card, so users "hop" like on Wikipedia. "Buys → 86 products (via order lines)" is Palantir's "group into edge" in words: the order lines in the middle are folded, so the user sees customer to product.

**Step 3: the picture is small and on request.** "Show as picture" draws this record in the middle and its linked records around it, **at most about 20 nodes**. Large groups become one bubble ("1,204 orders") instead of 1,204 dots. Clicking the bubble lists them or expands the top ten. Before any expand, the count is shown ("adds 86 products"), as in Palantir's right-click. Nodes show the icon and the short display name. Lines carry verbs. A line at the bottom says what was left out: "Showing 18 of 1,297 linked records".

**Step 4: connections answer in sentences.** The path finder answers as a chain of sentences, then a small picture: "ACME GmbH → placed → Order of 3 Mar 2024 → ships to → Hafenstrasse 12, Hamburg". Short paths only, since long multi-step paths were hard to follow in tests ([TRACE, MIT](https://dspace.mit.edu/server/api/core/bitstreams/32132935-fd7e-4117-b251-9912522dbad2/content)).

**What happens to Globes?** Keep it as an **overview picture of the whole graph at the top of the build steps**, but with one bubble per thing type sized by record count, verb-labelled lines between types, and a few sample dots. It shows "what is in here", which answers the "initial exploration problem" that lay users face ([McNamara et al.](https://arxiv.org/html/2602.21066)). It is no longer the place where users read records. "Web" and "Record by record" can be folded into "Show as picture" (one picture style, not three).

**History.** Where the data has dates, the card can show "Status changed: open (3 Mar) → delivered (9 Mar) → billed (12 Mar)", following South Park's point that a thing changes while its identity stays. Effort depends on the data having change dates.

### 6. What makes it unique to Strata

The record sentence is **built from the data with a checked template**, so every word in it traces to a field. Each fact line carries the same proof mark as the Ontology page. Rule-made facts are dashed and say which rule and which facts made them. Vendors show records and links. None we found marks, on the record itself, which facts the data proved and which a rule or the AI added.

---

## Layer 3. Semantic layer: show the meaning first and the SQL last

### 1. What users need to understand, in one line

"This number means exactly this here, a named person approved it, and it matches the reports you already trust."

### 2. What Strata shows today, and why it is hard

Metric cards show a title, big number, sparkline and a Certified or Proposed badge. The metric panel has a "receipt": plain words, formula, filters, joins, owner, certified date and SQL. It also lists verified questions, synonyms, drift warnings and "what depends on this". Users can add a metric in words.

This is the page closest to the market. The issue is weight, not structure. The receipt shows formula, filters, joins and SQL together, at the same level as the plain words. A manager does not need joins. The two badge states, Certified and Proposed, do not say whether the data checked the metric or whether this company defines it differently from the usual way. And the most important question, "is this different from what I think revenue means?", is not answered in one place.

### 3. What the Minimal Ontology article and the South Park explainer teach

The Minimal Ontology article is the key source for this layer ([Modern Data 101](https://moderndata101.substack.com/p/minimal-ontology-principle)). Its examples are metric definitions: revenue booked on contract signature; "active user" means at least one transaction in 28 days, excluding test accounts; net revenue means billed minus refunds and credits, on cash receipt, excluding intercompany. Its test for each concept is: **does the model already get it right here?** If yes, do not define it. If no, write the difference, keep it in the versioned semantic layer, and write the description for the model, not only for people. It also says to log how agents read each term, and to turn mismatches into **definition candidates**. It proposes no screen.

South Park adds two small lessons: show the type of a value (it shows `xsd:integer` hints, and the form rejects a grade that is not a whole number), and let the user add a statement with checking. For Strata's "add a metric in words", that means checking the unit and type as the user types.

### 4. What the best tools do

Tableau Pulse puts the **value, the change versus the last period, the definition's filters and insights** in the header, and explains "why it changed" with top drivers, limited to the dimensions the analyst chose ([Tableau](https://docs.salesforce.com/tableau/current/en-us/online/pulse_explore_metrics.md); [insight types](https://help.tableau.com/current/online/en-us/pulse_insights_platform_insight_types.htm)). dbt Catalog keeps the full lineage picture **behind an "Explore Lineage" button** ([dbt](https://docs.getdbt.com/docs/explore/explore-projects)). DataHub shows an expression, a Certified tag and a lineage tab ([DataHub](https://docs.datahub.com/docs/features/feature-guides/metrics-and-semantic-models)). Power BI shows a **"Verified checkmark"** for human-approved answers ([MS Learn](https://learn.microsoft.com/power-bi/create-reports/copilot-prepare-data-ai-verified-answers)). Atlan certificates have four states (Verified, Draft, Deprecated, none), and AI-made terms get their own icon ([Atlan](https://docs.atlan.com/product/capabilities/atlan-ai/how-tos/use-atlan-ai-for-glossary-management)). Hex tells its agent: "Don't guess or swap in a look-alike metric. Say it isn't covered" ([Hex](https://hex.tech/product/semantic-models)). Snowflake shows up to 10 **suggested verified queries** from usage, never applied automatically ([Snowflake](https://docs.snowflake.com/user-guide/views-semantic/verified-query-suggestions)).

**No vendor we found shows "what the word usually means" next to "what it means here".** And no vendor documents a badge for "the AI guessed this meaning". Both are open space.

### 5. Proposed new design (our design; the meaning card is not shipped by anyone)

The **metric card** keeps the big number and sparkline. The badge becomes one of three states from the shared legend: **Approved by [person]** (solid, tick), **Checked on data, not yet approved** (solid, no tick), **AI draft** (dashed outline). If the company meaning differs from the usual one, the ◆ "Means something different here" badge sits next to the title. If the metric matched a client report, a line under the number says "Matches Q3 sales pack, checked 2 days ago".

Clicking the card opens the **metric page**, top to bottom:

```
+---------------------------------------------------------------+
| Net revenue                        Approved by M. Weber, 2 Oct |
| 8.2 million EUR this quarter   ▲ 4% vs last quarter            |
| "Money billed to customers, minus credit notes and returns,   |
|  in EUR, by billing date. Internal company sales left out."    |
|                                                                |
| ◆ MEANS SOMETHING DIFFERENT HERE                               |
|  What an AI would assume    |  What it means here              |
|  All sales value on orders  |  Billed value only, minus credit |
|                             |  notes; excludes sales between   |
|                             |  our own companies               |
|  Difference: billed, not ordered; intercompany left out        |
|                                                                |
| PROVED ON                                                      |
|  ✓ Q3 sales pack, page 2: 8.2m — match                         |
|  ✓ Rule "never negative per month": 12 of 12 months pass       |
|                                                                |
| WHERE IT COMES FROM  (3 steps)                                 |
|  1. Billing documents  2. minus credit notes  3. by billing date|
|  [See example records]                                         |
|                                                                |
| [Why did it change?] [Questions it answers] [What depends on it]|
| [Show formula and SQL]                                         |
+---------------------------------------------------------------+
```

The **meaning card** is the core idea. The left column is what a general AI model would assume. Strata can produce it by asking the model, with no company context, "What does net revenue usually mean?" The right column is the company definition. The highlighted "Difference" line is one sentence. For a metric with no real difference, the card shows instead: **"Uses the usual meaning. No special definition needed."** This puts the Minimal Ontology Principle on screen: effort and attention go only where the company differs.

"Where it comes from" is a short numbered list, with "See example records" opening record cards from the Knowledge graph layer. Formula, filters, joins and SQL go behind **"Show formula and SQL"**, as dbt hides lineage behind a button. "Why did it change?" follows Tableau Pulse and uses only the dimensions in the definition. When adding a metric in words, Strata checks units and types as the user types, as South Park checks a grade is a whole number.

A **coverage line** at the top of the Semantic page summarises the layer: "24 terms defined. 9 mean something different here. 3 misread by the AI this week [review]". This shows the layer growing from real failures, as the article asks.

### 6. What makes it unique to Strata

Three things together: the **meaning card** (no vendor ships it), the **"Proved on" block** tying each metric to the client's own report and to rules checked on data, and the **three-state badge** that separates "a person approved it" from "the data checked it" from "the AI drafted it".

---

## Layer 4. Context: say how the question was read, then the answer and its facts

### 1. What users need to understand, in one line

"This answer comes only from these facts, I read your words this way, and you can correct me."

### 2. What Strata shows today, and why it is hard

The Context page lets the user ask a question. It shows build steps (link question to ontology, follow graph, gather facts, pack within budget, answer only from facts, with unsupported numbers rejected). "What the AI saw" lists facts with citations. There is a report check scorecard against client reports, an unanswered-questions log, and suggestions from the data.

The method is strong and close to what the market is moving toward. But the build steps speak the builder's language ("pack within budget"). The facts list uses record codes, so citations are hard to check. The most common cause of a wrong answer, a misread word, is not shown before the answer. And when Strata rejects an unsupported number, the user may not see that it happened, which is a trust signal wasted.

### 3. What the South Park explainer and the Minimal Ontology article teach

South Park's "Worked out by the property chain rule from 'Marvin is parent of Randy' and 'Randy is parent of Stan'" is the model for every answer: **a conclusion, plus the exact facts it came from, in sentences** ([South Park Ontology Explainer](https://southpark-ontology-explainer.jessica-tali-7056.chatgpt.site/)). Its warning section also applies: an answer can be wrong without any contradiction, for example when one customer is stored twice and half its orders are missed.

The Minimal Ontology article says to **log how the agent read each term** and turn mismatches into definition candidates ([Modern Data 101](https://moderndata101.substack.com/p/minimal-ontology-principle)). The Context page is where those mismatches happen, so it is where the user should see and fix them.

### 4. What the best tools do

The shipped tools agree on one layout: **answer first, then collapsible plain-language explanation, with code one click deeper.** Databricks Genie has an "Analysis" section ("Understanding the question", "Found relevant data", "Referenced SQL example", "Thinking steps"), a summary, a table with **"Show code"**, and editable **"Applied filters"**. Its feedback row has "Yes", "Fix it" (a list of common problems) and "Request review" ([Databricks](https://docs.databricks.com/aws/en/genie/talk-to-genie)). Looker has **"How was this calculated?"** with a plain text explanation of fields, calculations, filters and sort order ([Google Cloud](https://docs.cloud.google.com/looker/docs/conversational-analytics-looker-data)). Power BI shows a **"Matched trigger phrase"** so users see how their prompt was read, and "How Copilot arrived at this" ([MS Learn](https://learn.microsoft.com/power-bi/create-reports/copilot-prepare-data-ai-verified-answers)). ThoughtSpot Spotter shows the **search tokens** it used, which users can click and edit, and lets editors accept or reject the business terms mapped to tokens ([ThoughtSpot](https://docs.thoughtspot.com/cloud/10.10.0.cl/spotter-getting-started); [coaching](https://docs.thoughtspot.com/cloud/10.10.0.cl/spotter-coach)). Stardog Voicebox shows a **knowledge panel** next to the answer and marks graph answers separately from LLM answers ([Stardog Voicebox](https://docs.stardog.com/voicebox)). **None of these answer tools draws a lineage graph inside the answer**; they use step lists.

### 5. Proposed new design (our design; the chip strip combines Spotter tokens and Genie filters)

```
+---------------------------------------------------------------+
| You asked: "What did ACME buy last quarter?"                   |
|                                                                |
| I READ YOUR QUESTION AS                                        |
|  [Customer: ACME GmbH ✓] [Bought = billed value ◆ company]     |
|  [Last quarter = Jul–Sep 2026 ┄ my guess  ✎ correct this]      |
|                                                                |
| ANSWER                                                         |
|  ACME GmbH was billed 412,000 EUR in Jul–Sep 2026, across      |
|  31 orders. Top product: Steel bolt M8 (88,000 EUR).          |
|  Approved metric: Net revenue · Matches Q3 sales pack ✓        |
|                                                                |
| FACTS I USED (6)                                [show all]     |
|  ✓── ACME GmbH was billed 412,000 EUR in Q3   [record card]    |
|  ✓── 31 orders from ACME GmbH in Q3          [list]           |
|  I left out 1 number I could not prove from the data. [why]    |
|                                                                |
| ▸ How I got this (4 steps)   ▸ Show query                     |
| [Correct]  [Something is wrong]  [Ask the data owner]          |
+---------------------------------------------------------------+
```

**"I read your question as"** comes first, as chips. Each chip is marked with where its meaning came from, using the shared legend: tick for a matched record, ◆ for a company definition, dashed outline for an AI guess. Clicking "correct this" on a guess chip lets the user pick the right meaning. Strata then asks: **"Save this as the company meaning?"** A yes creates a draft definition in the Semantic layer for an owner to approve. This is the Minimal Ontology loop made visible.

The **answer** is one or two sentences with the trust line under it (approved metric, report match). **Facts I used** lists facts as sentences with readable record names, each linking to the record card. A plain note, **"I left out 1 number I could not prove"**, shows Strata's refusal rule working. Clicking "why" shows the number and the reason.

**"How I got this"** is collapsed by default and rewritten in business words: (1) "Found what your words refer to: the customer ACME GmbH and the metric Net revenue"; (2) "Followed links: customer → orders → billing documents"; (3) "Checked 6 facts against the data"; (4) "Wrote the answer using only those facts". A tiny picture of the path (at most about 8 nodes) can sit inside this step. Because pictures can make wrong answers look right ([arXiv 2505.21512](https://arxiv.org/abs/2505.21512)), each node in it keeps its status word.

The feedback row copies Genie: **Correct**, **Something is wrong** (a short list: wrong customer, wrong period, wrong meaning, wrong number, other), **Ask the data owner**. All three feed the existing unanswered-questions log, which becomes the **"Misreads and gaps" inbox** described in the meaning-delta section.

The report check scorecard stays, but each row reads as a sentence: "Q3 sales pack, net revenue, Germany: report says 3.1m, Strata says 3.1m. Match."

### 6. What makes it unique to Strata

Answers in other tools explain their steps. Strata's answers also **show which facts the data proved, show what was rejected, and tie the number to the client's own report**. The "Save as company meaning?" step connects a single misread directly to the governed Semantic layer.

---

## Across all four layers: one example, one legend, one meaning badge

### One running example, picked from the data

South Park works because one story (Stan's family and school) runs through every section. Strata should do the same. On first open, the AI picks **one running example from the real data**: a customer with a readable name, a typical number of orders, and links to all four thing types. It follows the "suggestions from the real data" rule; there is no fixed demo text. The same customer then appears in every layer: as the "one real example" on the Ontology page, as the first suggested record in the Knowledge graph, inside the example records of the Net revenue metric, and as the first suggested question on the Context page ("What did ACME buy last quarter?").

This supports a short guided tour in the "martini glass" shape: a few author-led steps, then free exploration ([Segel and Heer 2010](https://homes.cs.washington.edu/~jheer/files/narrative.pdf)). Five steps fit Strata's build-steps style: things found, how they link, what the data proved, one number, one answer. After that, the user explores freely. There is no strong evidence that this format improves understanding; narrative visuals are rarely tested well ([UTS 2025](https://opus.lib.uts.edu.au/bitstream/10453/186527/2/s12650-025-01051-y.pdf)). It is cheap to try.

### One legend, the same on every page

Each page has a small "ⓘ What the marks mean" button that opens the same legend.

| Mark | Meaning in plain words | Where it appears |
|---|---|---|
| Solid line with ✓ | The data proved this (with a count) | Fact lines, links, chips, metrics |
| Solid line, no tick | Stated in the source, not yet checked | Facts loaded but not tested |
| Dashed line or outline | The AI guessed this, or a rule worked it out; says which | AI claims, rule conclusions, AI-guess chips, AI-draft metrics |
| ✗ in red | The data disagrees (with the failing count and a link) | Fact lines, rules |
| Person icon with name | A person approved this | Metrics, reviewed claims |
| ◆ "Means something different here" | The company meaning differs from the usual one | Fields, codes, metrics, chips |
| Rounded box with type icon | A kind of thing (type) | Ontology picture, overview |
| Small card with icon and name | One real record | Record cards, pictures, facts |

One deliberate change from South Park: South Park draws **classes as dashed circles**. Strata should not, because dashed must mean only "not proven yet". Strata shows the type-versus-record difference by **shape** (rounded box with icon for a type, small card for a record). Dashing is then free to mean one thing everywhere. Every dashed or red mark also has a **status word**, because line style alone does not stop over-trust.

### The meaning-delta design, based on the Minimal Ontology Principle

The article gives the method but no screen. Strata can give it a screen in four parts (our design; no vendor ships this).

**The question for every term.** For each field, code and metric, Strata asks: does a general AI already get this right here? It answers by comparing the model's default meaning (asked with no company context) with the company meaning and with the data. Terms where they agree get "Uses the usual meaning" and need no work. Terms where they differ get the ◆ badge and a meaning card. This puts a number on the article's claim: "Of 214 terms, 197 use the usual meaning. 17 mean something different here."

**The meaning card.** Two columns, "What an AI would assume" and "What it means here", with one "Difference" line. It appears on the Ontology fact line (for codes such as order type ZOR), on the metric page, and in the answer chip popover.

**The "Misreads and gaps" inbox.** Corrections from the answer chips, "Something is wrong" feedback and unanswered questions are grouped: "The AI read 'sales' as order value 14 times this week; users meant billed value." Each group has **"Make it a company meaning"** or **"Dismiss"**. Like Snowflake's suggestions, nothing is applied automatically ([Snowflake](https://docs.snowflake.com/user-guide/views-semantic/verified-query-suggestions)). This follows the article: the layer grows from failures, not from workshops.

**Descriptions for the model.** Each meaning card has a hidden "What we tell the AI" text, the description the article says matters as much as SQL. Builders can see and edit it behind a "Show AI description" link. It is stored and versioned in the Semantic layer, not in model tuning.

---

## Ranked top list of changes

| Rank | Change | Layer | Effort | Why this rank |
|---|---|---|---|---|
| 1 | Readable record names and one-sentence summary per record (template per type, values from data), plus one icon per thing type | Knowledge graph (used by all) | M | Every other screen shows records; SAP codes make all of them unreadable today |
| 2 | One shared legend and status words (proved / AI guess / rule made / data disagrees / approved / ◆) on all four pages | All | S | Cheap; makes Strata's proof visible everywhere; reduces over-trust |
| 3 | Record card as the default Knowledge graph view: search plus AI-picked starting examples, facts as sentences, linked records grouped by verb with counts and 5 mini cards | Knowledge graph | M | Matches the vendor pattern and the user research; replaces the 600-dot first view |
| 4 | Ontology thing card: meaning sentence, one real example, "one of 512,000", facts as sentences with proof; field table behind "Show all fields"; tabs from 5 to 3 | Ontology | M | Real example first; puts proof per sentence |
| 5 | Answer card: "I read your question as" chips, short answer with trust line, facts in sentences, "I left out 1 number", plain 4-step "How I got this", feedback row | Context | M | Most answer errors are misreads; shows the refusal rule working |
| 6 | Three-part trust bar (proved / disagrees / for you to decide) replacing the single % | Ontology | S | Turns the headline into an action |
| 7 | Meaning card and ◆ badge on metrics and coded fields; "Uses the usual meaning" for the rest; SQL behind a button | Semantic, Ontology | M | Unique; puts the Minimal Ontology Principle on screen |
| 8 | Small picture on request: at most about 20 nodes, big groups as one bubble, count shown before expand, "showing 18 of 1,297" | Knowledge graph, Ontology | M | Keeps pictures under the readable limit |
| 9 | Rules as toggles: one sentence, pass/fail counts, rule-made facts drawn dashed with "worked out from" | Ontology, Knowledge graph | M | The most direct copy of what the manager liked in South Park |
| 10 | "Misreads and gaps" inbox with "Make it a company meaning", plus coverage line | Semantic, Context | M | Builds the delta loop; needs answer chips (rank 5) first |
| 11 | Running example and five-step guided tour, picked from real data | All | S | Cheap; untested, so measure it |
| 12 | Globes becomes the overview (one bubble per type, verb-labelled lines); Web and Record-by-record folded into one picture | Knowledge graph | S | Keeps a visual overview without asking users to read dots |
| 13 | "Same thing, or two?" duplicate check in the review queue | Ontology | L | Covers the South Park split-identity warning; needs new back-end matching |
| 14 | Record history line ("open → delivered → billed") where dates exist | Knowledge graph | M | Useful, but depends on the data having change dates |

Ranks 1 and 2 should come first because ranks 3 to 9 depend on them. Ranks 3, 4 and 5 can then be built in parallel, one per chunk, following the "one tool in depth per chunk" way of working.

## Conclusion

The research changes the question. It is not "which graph picture is clearest?" The evidence says business users mostly should not have to read a graph picture at all. They should read **one record, in sentences, with a mark on each sentence saying who or what stands behind it**. The picture is a helper, kept under about 20 nodes. This is good news for Strata, because its real strength, per-claim proof from the data, fits that sentence-and-mark form better than it fits a cloud of dots. Today that proof is hidden in tables and percentages. The redesign moves it onto every line.

The second shift comes from the Minimal Ontology Principle. A business user does not need to see everything the ontology knows. They need to see **where this company differs from common sense**, and to fix the AI when it gets that wrong. No tool we found shows "what an AI assumes" next to "what it means here". Strata can be first. The open risk is evidence: none of these designs has been tested with business users, and the strongest numbers come from lab tasks and interviews. Strata should test ranks 1 to 5 with two or three of the client's managers on the SAP data before building the rest, and measure one thing: can they explain, in their own words, what one order is and why they can trust its numbers?
