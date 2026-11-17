===============================================================================

                                  S T R A T A

         Turn any company data into something an AI can trust.

===============================================================================

 CONTENTS

   1.  The concept
   2.  Why it exists (the problem)
   3.  Overall architecture
   4.  Layer 1 - Ontology
   5.  Layer 2 - Knowledge graph
   6.  Layer 3 - Semantic layer
   7.  Layer 4 - Context
   8.  Agents (on top of the four layers)
   9.  How the layers work together (one question, end to end)
  10.  Use one layer, or your own ontology (open formats, CLI, bundle)
  11.  Setup - install and run
  12.  First use (5 minutes)
  13.  Data you can connect
  14.  Configuration (.env)
  15.  Connect an AI agent over MCP
  16.  Shared server
  17.  Other commands and tests
  18.  Troubleshooting
  19.  Project layout
  20.  Limits, stated plainly


===============================================================================
 1. THE CONCEPT
===============================================================================

 You connect a database, a folder of files or a URL. Strata reads it and builds
 four layers on top of it, automatically and with proof:

   1. ONTOLOGY         What the business things are (Customer, Order, Payment),
                       what each column means, and how things link.

   2. KNOWLEDGE GRAPH  The real records joined into one connected picture you
                       can search and walk ("how is this customer connected to
                       that seller?").

   3. SEMANTIC LAYER   One agreed, governed number per business word
                       ("revenue" is exactly this sum, of this column, with
                       these filters).

   4. CONTEXT          For any question, the small, checked set of facts an AI
                       needs to answer it, and nothing else.

 On top of the four layers sit AI AGENTS, in the app or in any tool that speaks
 MCP (Claude, Copilot-style assistants, your own code). They answer from these
 layers instead of guessing from raw tables.

 Each layer is also a SEPARATE TOOL. A team that only needs an ontology can use
 only the Ontology page and its exports. Together they power the agents.

 THE ONE RULE:  a guess must never look like a fact.
                The AI PROPOSES  ->  the data CHECKS  ->  a person DECIDES.
                Every name, link and number carries its proof; anything
                unproven is shown as unproven.


===============================================================================
 2. WHY IT EXISTS (THE PROBLEM)
===============================================================================

 A typical company (a real case from our BI work) has:

   - an MDM hub, a data mart and the source systems: THREE "sources of truth"
     that drift apart by weeks;
   - 10-12 DIFFERENT "AMOUNT" COLUMNS (net, gross, tax, freight, discount...)
     and nobody is sure which one a report should use;
   - reports that are slow and quietly wrong, because someone picked the wrong
     column or a join counted rows twice.

 Put an AI chatbot on that data and it does what people do, only faster: it
 picks a plausible column and returns a confident wrong number.

 Strata fixes the layer UNDER the AI. Before the AI answers, it has the meaning,
 the links, the agreed formulas and the evidence.


===============================================================================
 3. OVERALL ARCHITECTURE
===============================================================================

   YOUR DATA (stays where it is)          STRATA                       WHO USES IT
  +---------------------------+   +----------------------------+   +----------------+
  | Databases                 |   |                            |   | Web app        |
  |  Postgres, SQL Server,    |   |  PROFILE                   |   |  one page per  |
  |  MySQL, Oracle, Snowflake,|   |  types, counts, keys,      |   |  layer         |
  |  Databricks, Mongo, Neo4j |-->|  samples                   |   +----------------+
  | Files                     |   |      |                     |   | AI agents      |
  |  CSV, Excel, Parquet, JSON|   |      v                     |   |  6 presets     |
  | Graphs                    |   |  1 ONTOLOGY ------+        |-->+----------------+
  |  RDF, triples             |   |      |            |        |   | MCP            |
  | Metadata (optional)       |   |      v            v        |   |  Claude, any   |
  |  Power BI model, dbt,     |   |  2 KNOWLEDGE   3 SEMANTIC  |   |  agent         |
  |  data dictionary          |   |    GRAPH         LAYER     |   +----------------+
  +---------------------------+   |      |            |        |   | Excel / Nexus, |
                                  |      +-----+------+        |   | Apache Ossie,  |
                                  |            v               |   | OWL / SHACL    |
                                  |        4 CONTEXT           |   +----------------+
                                  |                            |
                                  |  REGISTRY (DuckDB):        |
                                  |  versions, notes, edits,   |
                                  |  decisions, metrics        |
                                  +----------------------------+

 How each layer uses the one before it:

   - The ONTOLOGY is the foundation. Every other layer reads its things, fields
     and proven links.
   - The KNOWLEDGE GRAPH is a VIEW over the ontology's tables. Nothing is
     copied, so it is always current.
   - The SEMANTIC LAYER builds metrics from the ontology's money and count
     fields, joined only through its proven links.
   - CONTEXT links a question to ontology things and graph records, prefers a
     certified metric for any number, and packs the result under a budget.
   - AGENTS use all four through tools (MCP), with guardrails on every tool.

 SUGGESTIONS FROM YOUR DATA, IN EVERY LAYER

   No screen shows a fixed example. Each one suggests what is worth doing with
   THIS data, built from real names, real values and real counts, with the fact
   behind it ("1,234 orders have status canceled or unavailable"):

     Ontology        notes to add: statuses that should not count, money with
                     no currency, codes nobody explained, fields the data
                     disagrees with, technical names to rename
     Ontology Ask    questions with real values ("...with Status delivered?")
     Knowledge graph real values to search (SP, delivered, credit_card)
     Semantic        metrics to define in words ("Delivered Payment Amount is
                     the total Payment Amount of orders with Status delivered")
     Context         the questions most worth asking

   The data's suggestions appear at once (under 0.3 s). When an AI model is
   configured, it picks the best ones and completes them a few seconds later
   (4-11 s on Olist, then cached until the ontology changes). Anything the AI
   says that names nothing in the data is dropped, and so is a metric whose
   name contradicts its own filter.

   A note works in every layer: "revenue = Payment Amount" also becomes another
   name of that metric in the Semantic layer, and the notes about a metric
   show on its receipt.

 Technology: Python (FastAPI) backend, DuckDB for profiling, queries and the
 registry, React + TypeScript web app, and MCP over HTTP for outside agents. The
 AI model (EYQ / Azure OpenAI, gpt-5.2) is optional.


===============================================================================
 4. LAYER 1 - ONTOLOGY                      (web app: Accelerators -> Ontology)
===============================================================================

 WHAT IT IS
   A plain-words map of your data: the business things (Customer, Order,
   Product), every field's meaning, type and unit, and the links between things,
   each with its proof.

 ARCHITECTURE

   source data            metadata (optional)
        |                        |
        v                        v
  +-----------+          +---------------+
  |  CONNECT  |          | Power BI, dbt,|
  | files/URL |          | dictionary    |
  +-----+-----+          +-------+-------+
        |                        |
        v                        |
  +-----------+                  |
  |  PROFILE  |  type, empty %, distinct, range, 5 samples, declared keys
  +-----+-----+                  |
        |                        |
        v                        v
  +-----------------------------------------+      +------------------------+
  |  NAME AND EXPLAIN                       | <--- |  AI (optional)         |
  |  things, fields, meaning, type, unit    |      |  sees names, numbers,  |
  +--------------------+--------------------+      |  <= 5 samples / column |
                       |                           +------------------------+
                       v
  +-----------------------------------------+
  |  CHECK AGAINST THE DATA                 |  id unique? money numeric?
  |  verified  /  "Data disagrees"          |  date parses? category small?
  +--------------------+--------------------+
                       v
  +-----------------------------------------+
  |  FIND LINKS by matching values          |  target must be unique,
  |  match %  ;  drop indirect / duplicate  |  values must really match
  +--------------------+--------------------+
                       v
  +-----------------------------------------+      +------------------------+
  |  PERSONAL DATA flagged                  |      |  YOUR NOTES AND EDITS  |
  |  NEW VERSION published                  | <--- |  survive every rebuild |
  +--------------------+--------------------+      +------------------------+
                       v
     Excel | Nexus JSON | Ossie YAML | OWL/SHACL | MCP get_ontology | Ask

 HOW IT IS MADE (step by step)
   1. CONNECT: files, a database file or a URL. Optionally a Power BI model,
      a dbt schema.yml or a data dictionary.
   2. PROFILE: measure every column (type, empty share, distinct count, range,
      a few sample values). Declared primary and foreign keys are kept.
   3. NAME AND EXPLAIN: the AI suggests names and meanings. It sees column
      names, numbers and at most 5 sample values per column, never whole rows.
   4. CHECK AGAINST THE DATA: an id must be unique, money must be numeric, a
      date must parse, a category must have few values. When the data disagrees
      the screen says "Data disagrees" and keeps the data's answer.
   5. FIND LINKS by matching values: kept only if the target is unique and the
      values really match (with a match %). Indirect and duplicate links are
      dropped.
   6. PERSONAL DATA (emails, phones, names, tax ids...) is detected and flagged.
   7. NOTES AND EDITS in your own words ("KUNNR = customer number") survive every
      rebuild. Every change publishes a new version. "Add context" suggests
      the notes worth adding for THIS data (e.g. "Customer Orders with Status
      canceled or unavailable do not count in revenue", backed by "1,234
      records"); clicking one selects its "..." so you type only the missing
      part.
   8. USE IT: Excel, Nexus JSON feed, Apache Ossie YAML, OWL/SHACL, MCP, or ask
      questions in plain English (Ask).

   Who wins when sources disagree:
      what you say  >  your metadata  >  the AI checked against the data
      >  the engine's guess from names

 HOW IT PERFORMS (real data, real model)
   Olist e-commerce, 9 tables, 1.5 M rows   built in 17-23 s: 9 things,
                                            52 fields, 7 links, all 7 links a
                                            100 % match in the data
   Same, AI claims                          49 / 52 confirmed by the data;
                                            3 wrong AI claims caught
   BI/MDM case: 10 "amount" columns with    10 / 10 meanings correct
   SAP names (NETWR, MWSBK...)
   Same columns, names removed (AMT_01..)   7 / 10 from values alone; the other
                                            3 say "unknown" instead of guessing
   SAP SALT, 4.7 M rows, 31 columns         29 / 31 meanings; 2 real data
                                            conflicts reported
   27 awkward inputs (emoji names, 400      27 / 27 handled
   columns, BOM, broken files...)
   Questions (Ask) on Olist                 answered in 2.4-3.6 s each; an
                                            off-topic question is refused

 WHY IT IS BETTER THAN OTHERS
   - Palantir, Microsoft Fabric IQ and Protege/OWL: people model the ontology
     by hand, which takes weeks per domain.
   - LLM "auto-ontology" tools trust whatever the model says.
   - Strata builds the ontology from the data in seconds AND checks every AI
     claim against the data.

   EXAMPLE: on Olist the AI called "order_item_id" a "unique id". The data
   showed only 21-29 distinct values in 100 k rows, so it is really a line
   number within an order. Strata rejected the claim and said why. An
   auto-ontology tool would have published it, and every join built on it would
   be wrong.


===============================================================================
 5. LAYER 2 - KNOWLEDGE GRAPH              (web app: Accelerators -> Knowledge graph)
===============================================================================

 WHAT IT IS
   Your actual records (this customer, this order, this payment) connected
   through the ontology's proven links, so you can find any record and see
   everything around it.

 ARCHITECTURE

   ONTOLOGY (things, keys, proven links)          YOUR TABLES (live, not copied)
            |                                               |
            v                                               |
   +------------------------+                               |
   | STEP 1  READ SCHEMA    |  things, keys (composite too),|
   |                        |  proven links                 |
   +-----------+------------+                               |
               v                                            v
   +---------------------------------------------------------------+
   | STEP 2  READ DATA                                             |
   |   records per thing  ;  per link: how many connect,           |
   |   how many point at nothing   ->  health warnings             |
   +-------------------------------+-------------------------------+
                                   v
   +---------------------------------------------------------------+
   | STEP 3  MAKE THE GRAPH  (virtual: queries run on your tables) |
   |                                                               |
   |    [Customer] --places--> [Order] --has--> [Order Item]       |
   |                              |                   |            |
   |                           paid by             sold by         |
   |                              v                   v            |
   |                          [Payment]           [Seller]         |
   +-------+-------------+-------------+-------------+-------------+
           |             |             |             |
        search        record        how are        export
        any value     + expand      two connected  Neo4j
                      neighbours    (path)
           |             |             |
           +-------------+-------------+--> MCP: find_entity, get_entity,
                                             how_connected

 HOW IT IS MADE (one Build button, 3 visible steps)
   1. READ THE SCHEMA: take the ontology's things, their keys (composite keys
      too) and their proven links.
   2. READ THE DATA: count records per thing and check each link: how many
      records connect, how many point at nothing.
   3. MAKE THE GRAPH: draw the things and links. Click a thing for sample
      records; click a record to expand its neighbours; search any value
      (the search box offers real values from your data to try).
   Also answers "how are these two connected?" (shortest path, in plain words:
   "order 7 was placed by customer 3"), exports to Neo4j, and serves
   find_entity, get_entity and how_connected over MCP.

 HOW IT PERFORMS
   - VIRTUAL: queries run on your tables through the ontology's links, so there
     is no copy to load and nothing goes stale.
   - One record's page is one scan. Path search runs from both ends at once.
   - Graph files: a 116 MB RDF sample (574 k labels, 8,142 relations) typed in
     20 s.
   - Health warnings show broken links. The share never reads 100 % while
     anything is broken.

 WHY IT IS BETTER THAN OTHERS
   - A classic graph project copies data into Neo4j with hand-written ETL, so it
     is stale the day after.
   - GraphRAG-style tools have an LLM EXTRACT entities and edges from text, so
     it invents some.
   - Strata's edges are only the links the data proved, over live tables.

   EXAMPLE: search "sao paulo". You get the customers AND the sellers in that
   city, each labelled with which field matched. Click a customer to see their
   orders, payments and reviews. Every edge on screen was proven to match in the
   data; none was guessed by a model.


===============================================================================
 6. LAYER 3 - SEMANTIC LAYER                (web app: Accelerators -> Semantic)
===============================================================================

 WHAT IT IS
   One governed number per business word, computed the same way everywhere: on
   screen, in Context, by agents and in Excel.

 ARCHITECTURE

   ONTOLOGY fields (money, counts, measures, dates) + proven links
            |
            v
   +---------------------------------------------------------------+
   | PROPOSE                                                       |
   |  count per thing ; totals for money and counts ; averages for |
   |  scores and measures ; NEVER a sum of ids, scores, heights    |
   +-------------------------------+-------------------------------+
                                   v
   +---------------------------------------------------------------+
   | SAFE JOINS  only to the "one" side of proven links, each join |
   |             key checked unique  ->  no row counted twice      |
   +-------------------------------+-------------------------------+
                                   v
   +---------------------------------------------------------------+
   | DECISION  "Revenue could be 3 different numbers. Which one?"  |
   |    Payment Amount  ################################  16.0 M   |
   |    Item Price      ###########################       13.6 M   |
   |    Freight         #####                              2.3 M   |
   |    -> a person clicks "This one is revenue" once              |
   +-------------------------------+-------------------------------+
                                   v
   +-------------------+   +-------------------+   +----------------+
   | CERTIFIED METRIC  |-->| RECEIPT           |   | DRIFT GUARD    |
   | owner, date,      |   | words, formula,   |   | fingerprint:   |
   | other names       |   | filters, joins,   |   | rows, empty %, |
   | (revenue, sales,  |   | SQL               |   | range, type    |
   |  turnover)        |   +-------------------+   | -> "Check"     |
   +---------+---------+                           +----------------+
             |        +---------------------------+
             |        | VERIFIED QUESTIONS        |
             |        | re-checked every rebuild  |
             |        +---------------------------+
             v
   ONLY CERTIFIED metrics are served to:
   Context | Ask | agents (MCP list_business_metrics, get_business_metric)
   | Excel | Ossie

   "Add a metric in words":  AI proposes -> data checks -> person certifies

 HOW IT IS MADE (step by step)
   1. PROPOSE from the ontology: a count per thing; totals only for money and
      for counts (qty, units, instalments); averages for scores and measures.
      Never a sum of ids, scores, heights or weights.
   2. ASK THE QUESTION PEOPLE ARGUE ABOUT: "Revenue could be 3 different
      numbers. Which one is it?" A bar chart shows the candidates side by side;
      a person decides once. That metric is certified and learns the words
      revenue, sales and turnover.
   3. JOIN SAFELY: a metric joins only to the "one" side of proven links, and
      each join key is checked unique in the data. No row is ever counted twice.
   4. RECEIPT on every metric: meaning in words, formula, filters, joins and why
      they are safe, owner, certified date, other names and the SQL.
   5. DRIFT GUARD: certifying saves a fingerprint (rows, empty share, range,
      type). If the data under it changes (values go empty, the largest value
      moves 10x, a column disappears), the card turns to "Check" and says why.
   6. VERIFIED QUESTIONS are saved with a metric and re-checked after every
      rebuild.
   7. ADD A METRIC IN WORDS, e.g. "Delivered revenue is payment value of orders
      with status delivered". The AI proposes the definition; Strata checks the
      field and the filter value exist and shows the number; a person
      certifies it. Ready-made definitions are suggested from the data; on
      Olist, clicking "Delivered Item Price" gave 13,221,498.11, exactly what
      independent SQL on the raw files gives.

 HOW IT PERFORMS (Olist)
   - 21 metrics proposed, with values and trend lines, in about 2.5 s.
   - Revenue by payment type: credit_card = 12,542,084.19.
   - "Delivered revenue", defined in words: 15,422,461.77.
   - Both are EXACTLY equal to independent SQL on the raw CSV files.

 WHY IT IS BETTER THAN OTHERS
   dbt MetricFlow, Cube, AtScale,        |  Strata
   LookML, Snowflake / Databricks        |
   metric views                          |
   --------------------------------------+---------------------------------------
   an engineer writes YAML by hand       |  proposed from the ontology
   which "amount" is revenue is left     |  competing totals shown side by side,
   to people                             |  decided once
   joins are declared and trusted        |  joins proven in the data and checked
                                         |  unique: nothing double-counted
   silent drift                          |  fingerprint + "Check" with the reason
   a number with no story                |  a receipt on every number

   EXAMPLE: the "10-12 amount columns" problem. Strata does not pick one
   silently. It shows the candidates with their totals and a person chooses
   once. From then on "revenue", "sales" and "turnover" mean that one certified
   formula in every screen, agent and spreadsheet.


===============================================================================
 7. LAYER 4 - CONTEXT                        (web app: Accelerators -> Context)
===============================================================================

 WHAT IT IS
   For one question, the SMALL, CHECKED EVIDENCE PACK an AI needs: the right
   things, records, metrics and rules, with citations, under a fixed budget.

 ARCHITECTURE (ontology-based context: link -> traverse -> check -> pack -> answer)

   QUESTION  "What is the revenue by payment type?"
        |
        v
   +-------------------------------------------------------------+
   | 1 LINK      words -> ontology things, fields, synonyms,     |  <- ONTOLOGY
   |             record ids ("order 3"), values ("sao paulo")    |
   +-----------------------------+-------------------------------+
                                 v
   +-------------------------------------------------------------+
   | 2 TRAVERSE  up to 2 hops through the graph from linked      |  <- KNOWLEDGE
   |             records                                         |     GRAPH
   +-----------------------------+-------------------------------+
                                 v
   +-------------------------------------------------------------+
   | 3 GATHER    certified metric FIRST (no AI-written SQL)      |  <- SEMANTIC
   |   + CHECK   else a checked query that states its filter     |
   |             conflicting meanings quarantined                |
   +-----------------------------+-------------------------------+
                                 v
   +-------------------------------------------------------------+
   | 4 PACK      2,000-token budget, most relevant first,        |
   |             records what was left out, every fact cited     |
   +-----------------------------+-------------------------------+
                                 v
   +-------------------------------------------------------------+
   | 5 ANSWER    AI answers ONLY from the pack ; every number    |
   |             in the answer checked against the evidence      |
   +-----------------------------+-------------------------------+
                                 v
   screen: big number or chart + one-line headline + trail
           (understood -> looked at -> facts checked) + "What the AI saw"

 HOW IT IS MADE (step by step)
   1. LINK the question's words to the ontology: things, fields, synonyms from
      your notes, record ids ("order 3" is an order, not customer 3) and values
      ("sao paulo" -> Customer City, with a count).
   2. TRAVERSE up to 2 hops through the knowledge graph from linked records.
   3. GATHER AND CHECK: a certified metric first (no AI-written SQL); otherwise
      a checked query that states its filter. Facts with conflicting meanings
      are quarantined, not mixed in.
   4. PACK into a 2,000-token budget, most relevant first, recording what was
      left out.
   5. ANSWER: the AI answers only from the pack, and every number in the answer
      is checked against the evidence.
   The screen is pictures-first: key numbers and charts from your data,
   suggested questions, then the answer as a chart or a big number.

 HOW IT PERFORMS
   - "What is the revenue by payment type?" -> "credit_card is the largest:
     12.5 M, 78 % of 16 M". It came from the certified metric with no generated
     SQL, matches the raw data exactly, and is backed by 6 checked facts.

 WHY IT IS BETTER THAN OTHERS
   - Plain RAG retrieves text chunks that LOOK similar to the question and lets
     the model fill the gaps.
   - Strata retrieves the THINGS AND RECORDS the question is about, follows
     proven links, prefers certified numbers, and rejects an answer whose
     numbers are not in the evidence.

   EXAMPLE: asked about "order 3", RAG would happily pull any chunk mentioning
   "3". Strata reads the word before the number, so it gets order 3, not
   customer 3, and walks to that order's items, payments and customer. If the
   model then writes a number that is not in the pack, the answer is refused
   rather than shown.


===============================================================================
 8. AGENTS (ON TOP OF THE FOUR LAYERS)                 (web app: Agents)
===============================================================================

 ARCHITECTURE

          +---------+  +----------+  +-----------+  +---------+  +-------+  +-------+
          | Data    |  | Metric   |  | Entity    |  | Insight |  | Trust |  |Steward|
          | Guide   |  | Analyst  |  | Investig. |  | Analyst |  |Checker|  |       |
          +----+----+  +----+-----+  +-----+-----+  +----+----+  +---+---+  +---+---+
               |            |              |             |           |          |
               +------------+------+-------+-------------+-----------+----------+
                                   v
            +----------------------------------------------+
            |  MCP TOOLS (30)  with guardrails:            |
            |  scoped to the agent key's sources,          |
            |  personal data removed, receipt on answers   |
            +---+------------+-------------+-----------+---+
                v            v             v           v
            ONTOLOGY   KNOWLEDGE GRAPH   SEMANTIC    CONTEXT

   Outside agents (Claude, Copilot-style, your code) use the SAME tools at /mcp.

 BUILT-IN AGENTS, FROM YOUR DATA (6 TO 10, READY TO USE)
   Strata works out the agents for each ontology from its data. Nothing to
   set up: open Agents, pick one, ask. Their names and example questions come
   from your data (real things, fields, values and record ids).

   Always:
   Data Guide            ontology          what the data is and how it links;
                                           never gives numbers
   <Thing> Investigator  knowledge graph   one record by id or name and what it
                                           is linked to (e.g. Order Investigator)
   Metric Analyst        semantic          certified metrics only, with formula
                                           and owner; refuses anything else
   Insight Analyst       all four          any question, from checked facts
   Trust Checker         read-only         certification, drift, data checks,
                                           empty fields, broken links
   Data Steward          ontology          proposes notes; a person applies them
   When the data supports them (up to 10 in all):
   Revenue / money analyst, <Status> Watcher (e.g. Order Status Watcher),
   Regional Analyst (a place field), Trend Analyst (per month), Privacy
   Checker (where personal data is; never shows a value).

   Built-ins are read-only and refresh when the data changes. To change one,
   click COPY: the copy is yours to rename, narrow (which things and metrics
   it may use), give instructions and example questions. Or CREATE AGENT from
   scratch. Every change bumps the agent's version; "Try it" asks the agent
   before you save it.

   Numbers come only from the data: a certified metric first; then, for
   counting questions (how many / total / by / per month / which has the
   most), Strata's own query over proven links (no AI-written SQL); only then
   a checked AI query, labelled as such.
   On Olist: canceled orders 625; customers in SP 41,746 (42 %); total price
   of delivered orders 13,221,498.11 - each equal to plain SQL.

   CONNECT ANY AGENT: open it -> Create a key -> paste the Claude / Cursor
   line. The key reaches only that agent's tools, ontology and metrics
   (anything else is refused and logged under "What outside AIs asked it").
   Agents made per data source before this version are under Agents ->
   "older agents".

 Key MCP tools: get_ontology, ask_question, find_entity, get_entity,
 how_connected, list_business_metrics, get_business_metric,
 context_for_question, check_answerable, propose_change.


===============================================================================
 9. HOW THE LAYERS WORK TOGETHER (ONE QUESTION, END TO END)
===============================================================================

  "What is the revenue by payment type?"

   ONTOLOGY        "payment type" is the field payment_type of Order Payment;
                   "revenue" is a business word with a certified metric.
        |
   KNOWLEDGE GRAPH Order Payment -> Customer Order -> Customer are proven
                   links (100 % match).
        |
   SEMANTIC        "revenue" = certified Total Payment Amount = sum(payment_value),
                   safe joins, certified by a person, no drift.
        |
   CONTEXT         pack: certified metric by payment_type, 6 facts, cited,
                   within budget.
        |
   AGENT / SCREEN  "credit_card is the largest: 12.5 M, 78 % of 16 M"
                   + chart + receipt. Same number in Excel and over MCP.


===============================================================================
 10. USE ONE LAYER, OR YOUR OWN ONTOLOGY
===============================================================================

 Every layer works on its own, in three ways. Pick what fits the team.

 IN THE WEB APP: sidebar -> Use them -> USE ANYWHERE shows all three ways, and
 every layer page (Ontology "Use it" tab, Knowledge graph, Semantic, Context)
 ends with a panel "Use the <layer> layer in your own system": download it in
 an open format, download a ready-to-run zip with only that layer, or copy the
 API / MCP / command-line call.

   A. ALL FOUR LAYERS HERE   the web app, as described above.
   B. YOUR ONTOLOGY, OUR LAYERS
                             bring your own ontology; the Knowledge graph,
                             Semantic and Context layers run on top of it.
   C. OUR LAYER, YOUR SYSTEM take one layer out, in an open format or as a
                             ready-to-run copy, and use it where you work.

   YOUR DATA ---> ONTOLOGY (ours, or yours as a Strata Model file)
                     |                |                 |
                     v                v                 v
              KNOWLEDGE GRAPH      SEMANTIC          CONTEXT
              RDF, JSON, Neo4j     SQL views,        Context Pack
                                   dbt MetricFlow    (JSON)

 THE OPEN FORMAT BETWEEN LAYERS: STRATA MODEL v1
   One JSON file: things, fields (role, meaning, unit), the table and column
   behind each, and the links. Schema: docs/spec/strata-model.schema.json.
     Download:  Ontology -> Use it -> Strata Model, or GET /api/onto/<id>/contract
     Agents:    MCP get_ontology with format "contract"

 B. USE YOUR OWN ONTOLOGY
   Ontology -> New ontology -> "Use my ontology exactly", then add the data and
   your file: a Strata Model (.json), an Ossie model (.yaml), a dbt schema.yml
   or a data dictionary (.csv / .xlsx).
     - Your names, fields and links are used as written. The AI is not asked.
     - Tables your file does not name are left out (the build says which).
     - Everything is still checked against the data. If your file says a text
       column is money, it stays money and the screen says "Data disagrees"
       and why. A declared link the data does not support is marked the same.
     - Your edits and notes survive rebuilds, as always.
   Other choice: "Keys only": names from the columns and the keys the database
   declares, never any AI (also on rebuild).
   Live on Olist: our ontology exported, then imported exactly, gave the same
   9 things, 52 fields and 7 links, 100 % confirmed, and all 24 metric values
   identical. The import took 5.7 s.

 C. EACH LAYER IN ANOTHER SYSTEM'S FORMAT
   Ontology         Strata Model JSON, Apache Ossie, OWL / SHACL, Excel, Nexus
   Knowledge graph  RDF N-Triples (any triple store), JSON nodes and edges,
                    Neo4j import files.   GET /api/kg/<id>/rdf, /graph.json, /neo4j
                    Olist: 10.4 million triples written in 15 s.
   Semantic         SQL views (one CREATE VIEW per certified metric, over the
                    source tables by their own names) and dbt MetricFlow YAML.
                    GET /api/sem/<id>/export?format=sql   (or metricflow)
                    Olist: the SQL view gave 16,008,872.12, the same as
                    Strata and as plain SQL on the CSV files.
   Context          Context Pack v1: the checked facts for one question, each
                    with its citation; any AI can answer from it.
                    POST /api/ctx/<id>/pack
                    Schema: docs/spec/context-pack.schema.json
   Personal-data columns (emails, phones, ids...) never leave in an export.

 ONLY SOME LAYERS ON A SERVER
       python run_server.py --layers semantic,context
       (or STRATA_LAYERS=semantic,context in .env)
   The web app shows only those pages, the other layers' API answers "switched
   off", and agents over MCP see only those tools. The ontology is always on.
   GET /api/health/layers says, per layer, whether it is ready and why not.

 COMMAND LINE AND PYTHON (no web app needed)
       pip install .                  (then the  strata  command exists;
                                       or: python -m strata ...)
       strata connect D:/data/shop --name shop
       strata build "Shop" --source shop        (or --model my.json, --keys-only)
       strata export ontology shop -o shop.strata-model.json
       strata export graph shop --format rdf -o shop.nt
       strata export semantic shop --format metricflow -o metrics.yml
       strata metrics shop
       strata certify shop total_payment_value --owner Finance
       strata context shop "revenue by payment type"
       strata health shop
       strata serve --layers semantic
   In Python:
       import strata
       s = strata.open("work.duckdb")
       s.metrics("shop")

 A READY-TO-RUN COPY FOR ANOTHER TEAM (Python only, no Docker)
       strata bundle -o strata-semantic.zip --layers semantic --ontology shop
   One zip (about 1 MB): the code, the built web app, the open specs, your
   ontology as a Strata Model to start from, and start.bat / start.sh. They
   unzip it and double-click start.bat (or run ./start.sh). The first start
   makes a private .venv and installs the requirements; then Strata opens with
   only those layers. Their data never moves: they connect it from the app.


===============================================================================
 11. SETUP - INSTALL AND RUN
===============================================================================

 WHAT YOU NEED
   - Python 3.10 or newer        https://www.python.org/downloads/
   - Node.js 18 or newer         https://nodejs.org/   (builds the web app)
   - Git                         https://git-scm.com/
   - 8 GB RAM is enough. Windows, macOS or Linux.
   - Optional: an EYQ / Azure OpenAI endpoint and key for the AI steps.
     Without it everything still runs; names come from the engine, not the AI.

   Check:   python --version      node --version

 INSTALL (one time)

   Windows (PowerShell):
       git clone https://github.com/Tushar-CYL/mcp-ontology.git
       cd mcp-ontology
       python -m venv .venv
       .venv\Scripts\activate
       python -m pip install -r requirements.txt
       copy .env.example .env

   macOS / Linux:
       git clone https://github.com/Tushar-CYL/mcp-ontology.git
       cd mcp-ontology
       python3 -m venv .venv
       source .venv/bin/activate
       python -m pip install -r requirements.txt
       cp .env.example .env

 ADD THE AI KEY (optional) - open .env and fill in:
       EYQ_INCUBATOR_ENDPOINT=https://...
       EYQ_INCUBATOR_KEY=...
       EYQ_MODEL=gpt-5.2

 START
       python run_server.py

   Then open  http://127.0.0.1:8000

   The first start runs "npm install" and "npm run build" for you (a few
   minutes). After that it starts in seconds. The web app, the API and MCP
   are all on that one address. Stop with Ctrl+C. After a "git pull", just
   start it again; it rebuilds the web app by itself when needed.


===============================================================================
 12. FIRST USE (5 MINUTES)
===============================================================================

   1. Data sources -> Connect: a folder of CSV files, a .db file, or a URL
      such as  postgres://user:pass@host:5432/dbname
   2. Ontology: watch it build; read the things, fields, links and proof.
   3. Knowledge graph -> Build: search a value; click a record.
   4. Semantic: answer "which one is revenue?"; certify the metrics you trust.
   5. Context: click a suggested question or type your own.
   6. Agents: pick an agent, or connect Claude (section 15).


===============================================================================
 13. DATA YOU CAN CONNECT
===============================================================================

   Files           CSV, TSV, Excel, JSON, NDJSON, Parquet, Delta Lake folder
   Database files  SQLite, DuckDB, Access (.accdb)
   URLs            postgres://  mysql://  mssql://  oracle://  odbc://
                   mongodb://  neo4j://  s3://  gs://  az://  delta://
                   snowflake://  databricks://  and any SQLAlchemy dialect
   Graph files     .nt, .ttl, CSKG folders
   Metadata        Power BI model.bim, dbt schema.yml, a data dictionary
   (optional)      (.csv or .xlsx with table, column, description)

   Declared primary and foreign keys are kept; links are still checked against
   the data. If a database driver is missing, the error names the exact
   "pip install ..." to run.


===============================================================================
 14. CONFIGURATION (.env)
===============================================================================

   EYQ_INCUBATOR_ENDPOINT,     the AI model; leave empty to run without AI
   EYQ_INCUBATOR_KEY,
   EYQ_MODEL
   STRATA_AI=off               turn the AI off completely
   STRATA_AI_SAMPLES           sample values per column the AI may see
                               (default 5; 0 = none). Never whole rows.
   MIDDLE_LAYER_GRAPH          where the registry lives
                               (default data/graphs/platform.duckdb)
   MIDDLE_LAYER_HOST / _PORT   server address (default 127.0.0.1:8000)
   STRATA_DATA_ROOTS           shared server: folders the API may read
   STRATA_API_TOKENS           shared server: access tokens (unset = open)
   STRATA_GRAPH_BUILD_MAX_ROWS graph files above this load as tables only
                               (default 10,000,000)


===============================================================================
 15. CONNECT AN AI AGENT OVER MCP
===============================================================================

   With the server running:

       claude mcp add --transport http strata http://127.0.0.1:8000/mcp

   Any MCP client works the same way with the address
   http://127.0.0.1:8000/mcp


===============================================================================
 16. SHARED SERVER
===============================================================================

   For a server other people use, set in .env:

       MIDDLE_LAYER_HOST=0.0.0.0
       MIDDLE_LAYER_PORT=8000
       STRATA_API_TOKENS=a-long-random-token      (login for the app and API)
       STRATA_DATA_ROOTS=D:\data;D:\shared        (folders the API may read)


===============================================================================
 17. OTHER COMMANDS AND TESTS
===============================================================================

       python run_server.py --port 8010       another port
       python run_server.py --rebuild-ui      force a fresh web-app build
       python run_server.py --no-ui           API only
       python -m pytest -q                    Python tests (about 1,230)
       cd frontend
       npm test                               web-app tests (111)
       npm run dev                            web app with hot reload at
                                              http://localhost:5173 (server
                                              started with --no-ui)


===============================================================================
 18. TROUBLESHOOTING
===============================================================================

   "Restart the server" on a page
       The server is older than the web app. Ctrl+C, then python run_server.py

   "AI busy" (503)
       The model is rate-limited. Strata retries; try again in a few seconds.

   The web app does not build
       Check node --version is 18 or newer, then:
       python run_server.py --rebuild-ui

   Windows blocks a DuckDB extension (Application Control)
       SQLite and MySQL fall back to pure-Python readers by themselves.
       For PostgreSQL, allow the DuckDB extension folder or use odbc://

   Port 8000 is taken
       python run_server.py --port 8010


===============================================================================
 19. PROJECT LAYOUT
===============================================================================

   ontology/          connect, profile, meanings, links, versions, Ask,
                      exports (Excel, Ossie, OWL)
   knowledge_graph/   the virtual graph: model, search, records, paths, Neo4j
   semantic/          metric store and engine; model.py is the Semantic tool,
                      export.py writes SQL views and dbt MetricFlow
   context/           the context engine (engine.py) and pictures-first insights
   agent/             agent presets, LLM client, guardrails, receipts
   api/               FastAPI server, REST routes per layer, MCP server
   review/            human review queue for proposed changes
   frontend/          React web app (one page per layer, plus Agents)
   tests/             unit and integration tests
   scripts/, datasets/, benchmarks/
                      test-data generators and QA runs used by the tests
   docs/research/     the research behind each layer, with sources
                      (REPORT.md first)
   data/              your local data and registry (not in git)
   strata/            the strata command, the Python library, bundles
   docs/spec/         open formats: Strata Model, Context Pack (JSON Schema)
   run_server.py      starts everything (--layers to choose layers)
   requirements.txt   Python packages


===============================================================================
 20. LIMITS, STATED PLAINLY
===============================================================================

   - Running totals, month-to-date and year-to-date metrics, and per-user row
     access, are not built yet.
   - Identity resolution across systems was measured on generated data
     (100 %); real-world identity is harder.
   - Cloud connectors (Snowflake, Databricks) use the vendor drivers and have
     not been tested against live accounts here.

===============================================================================
