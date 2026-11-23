# How commercial ontology / KG / catalog products visualize ontologies and records for business users (as of Nov 2026)

Scope note: about 20 search and fetch calls. Most sources are vendor docs, so they describe what each vendor intends and say nothing about how well it works. Where a doc page did not cover a detail (icons, exact card contents), the detail is listed under Gaps and not filled in from memory.

## Palantir Foundry: do they lead with cards and lists, or with graphs?

### Takeaway
Foundry leads with search, then a list or table, then a per-object profile page (the Object View). The graph tool (Vertex) is a separate app for analysts. Even inside Vertex the graph is built up from objects you choose, it is never shown all at once, and a node can be drawn as a full object card.

### Cited Findings
- Object Explorer is "a search and analysis tool for answering questions about anything in the Ontology". You find objects with point-and-click keyword search, then property filters. Results show either as an "exploration view" (preset, configurable charts or maps for drilling into subsets) or as a results table. It needs little setup and is aimed at less technical users — [Palantir Object Explorer overview](https://www.palantir.com/docs/foundry/object-explorer/overview/)
- From Object Explorer you can compare object sets, run bulk Actions (writeback), open a set in Quiver, export it, and save explorations that reopen with current results. Clicking one object opens its Object View. The navigation also has a "Pivot to explore linked objects" step (moving from a set to its linked set) — [Palantir Object Explorer overview](https://www.palantir.com/docs/foundry/object-explorer/overview/)
- An Object View is "a central hub for all information related to an object": key details, properties, links and related apps. Every object type gets a built-in Standard Object View, generated from the type's configuration with no setup. A Configured view, built in Workshop, becomes the default once it exists, and users can always switch back to the standard one. Views come as **Full** (everything about the object) or **Panel** (a compact version embedded in other apps). Patient example: the full view shows demographics, vitals, care plans, linked procedures, prescriptions, diagnoses and trends; the panel shows only demographics and vitals — [Palantir Object Views overview](https://www.palantir.com/docs/foundry/object-views/overview/)
- Vertex flow:
  1. "+ New Graph" opens a blank canvas, and "+ add objects" opens a search pop-up; the chosen objects become nodes.
  2. Clicking a node opens a selection panel with its properties. Derived property functions (for example, a count of alerts on routes linked to an airport) appear at the top of that panel.
  3. Right-clicking nodes gives a menu that lists **related object types with counts**. "Open" on a count launches the Search Around panel, where you can add filters and chain steps.
  4. Shortcuts: "All linked objects" (Ctrl+Shift+S), "Shortest path" (exactly two objects selected), and "Links to objects on graph".
  5. A histogram of property values for the selected objects filters the graph when you click a value.
  — [Palantir Vertex: explore object relationships](https://palantir.com/docs/foundry/vertex/explore-object-relationships/)
- Vertex display options:
  - Nodes: draw each node as a default node **or as a full object card**. Fill colour can come from a property, a time-series measure or a derived function. A subtitle under each node shows the object type or a chosen property. Extended labels show chosen properties. Badges show the count of linked events.
  - Edges: colour by type or by a shared property, width by a property (for example transaction volume), straight, curved or orthogonal lines, aggregated labels, and arrow direction defaults per link type.
  - Layouts: Auto, Circular, Hierarchy, Grid, Row/Column sorted by a property, Radial (centred on a chosen node), Cluster (grouped by object type by default), and Cartesian (x and y from numeric properties).
  - Grouping: merge selected objects into one node, regroup by a histogram property, or "group into edge", which turns transaction objects into the edge between two entities.
  - Time windows restyle the graph as the window moves. Saved styles, and saved selections drawn as coloured split borders, are also available.
  — [Palantir Vertex display options](https://palantir.com/docs/foundry/vertex/graphs-display-options/)
- Existing graphs can be shared read-only. Readers filter with the Histogram tab; editors can also run Search Arounds and change styling and layout — [Palantir Vertex: explore existing graphs](https://palantir.com/docs/foundry/vertex/graphs-explore/)

### Inferences
- The pattern to copy: search, then a table or chart of a set, then a profile page per object, with "linked object types with counts" as the way to move along links. The graph is opt-in and grows one step at a time.
- Two Vertex ideas suit business users and a small React team: "related types with counts" on right-click, which tells you how much will be added before you add it, and "group into edge", which hides transaction records inside the edge between two parties.
- The auto-generated standard view means every type gets a decent profile page on day one. That is the most important thing to copy.

### Gaps
- I did not fetch the pages on the Ontology Manager graph view, the exact layout of a standard Object View (header, tabs, link sections) or Quiver, so there are no concrete details for those.
- The Vertex docs do not say whether nodes can carry icons.

## Microsoft Fabric IQ ontology (preview)

### Takeaway
Fabric IQ splits the **schema canvas** (types and relationships, with Full ontology / Neighborhood / Inheritance views) from the **instance** views (an Instances table, then a per-instance view of properties and relationships). Graph views of instances need a query; they are never drawn by default. Everything is still preview.

### Cited Findings
- The home configuration canvas has three views, switched in the upper-right corner:
  - **Full ontology**: all entity types and relationships.
  - **Neighborhood**: one entity type plus its related types. This is an ego view of the schema.
  - **Inheritance**: one type's inheritance structure.
  Picking a type in the left **Explorer** pane centres it on the canvas. The doc is dated 2026-10-20 and the feature is labelled "preview" — [MS Learn: View ontology details](https://learn.microsoft.com/en-us/fabric/iq/ontology/how-to-use-preview-experience)
- An entity type details page has two tabs:
  - **Configure**: properties, data bindings, relationship types, metrics, metadata, resource links.
  - **Instances**: the instances and their static property values.
  — [MS Learn: View ontology details](https://learn.microsoft.com/en-us/fabric/iq/ontology/how-to-use-preview-experience)
- In an earlier version described by a Microsoft Learning lab, the expanded graph first shows **entity type nodes, not data instances**, and you load instances by running a Query builder query. Selecting a row in the Entity instances table opens that instance's properties and relationships. The graph depends on Graph in Microsoft Fabric being enabled for the tenant — [MS Learning lab: Visualize ontology](https://microsoftlearning.github.io/mslearn-fabric/Instructions/Labs/27-visualize-ontology.html); [MS Learn: ontology overview](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)

### Inferences
- Microsoft also defaults to a table of instances, then one instance page. The "Neighborhood" schema view is a cheap, readable ego view of the schema.

### Gaps
- I could not find out what the per-instance view looks like (card, list or mini-graph) from the doc text.

## Neo4j Bloom / Neo4j Explore (Aura)

### Takeaway
These tools are search-first. You start from an empty "scene" and type a near-natural-language query into a search bar that offers suggestions. A "Perspective" turns the raw graph into business categories, captions and colours. You then expand on demand. Bloom and Explore are the most graph-centric of the business tools, but they avoid hairballs by showing only what you searched for.

### Cited Findings
- The search bar accepts four kinds of input:
  - **Graph patterns**: a "relaxed, near-natural language" grammar matched against labels, relationship types, property keys, indexed values and Perspective categories, offered as suggestions while you type.
  - **Search phrases**: saved, parameterised Cypher queries stored in the Perspective.
  - **Full-text search**: the fallback when no suggestion fits.
  - **Actions**: commands such as Clear Scene, Expand selection, Dismiss and Undo.
  You pick a suggestion with TAB or a click — [Bloom search bar](https://neo4j.com/docs/bloom-user-guide/current/bloom-visual-tour/search-bar/)
- Explore (Aura) adds a co-pilot for search that Neo4j labels "experimental" and says "does not provide guaranteed accuracy" — [Aura Explore search bar](https://neo4j.com/docs/aura/preview/explore/explore-visual-tour/search-bar)
- A Perspective is "a certain business view or domain" of the graph. It defines categories (business entities), captions, colours, which properties show and of what type, which relationships show, and custom search phrases. Bloom auto-generates one on first launch from the data it finds, with a quick-scan option for graphs over 10M nodes and relationships — [Bloom perspectives](https://neo4j.com/docs/bloom-user-guide/current/bloom-perspectives/bloom-perspectives/)
- The scene holds "just the parts of the graph which you've found through search or exploration". The legend panel offers rule-based styling on string, number, boolean and temporal properties, in single, range or unique-value modes. Styling changes apply to the current scene; new scenes use the Perspective's styling — [Bloom overview](https://neo4j.com/docs/bloom-user-guide/current/bloom-visual-tour/bloom-overview/); [Bloom legend panel](https://Neo4J.com/docs/bloom-user-guide/current/bloom-visual-tour/legend-panel/); [Aura Explore styling](https://neo4j.com/docs/aura/explore/explore-visual-tour/styling/)
- The card list is a panel of small cards, one per node on the scene, each showing a few properties. Selection is linked both ways between cards and nodes, and Expand and Dismiss sit at the bottom of the list. **Double-clicking a card opens the Inspector**, which shows full properties (hover shows the data type, and they can be edited with write access) plus the node's relationships and neighbours **as cards** you can navigate to — [Bloom card list](https://neo4j.com/docs/bloom-user-guide/current/bloom-visual-tour/card-list/)

### Inferences
- Even the main graph-visualization vendor pairs the canvas with a card list and an Inspector made of neighbour cards. That is the profile-page pattern again.
- An auto-generated "Perspective" (business names, captions, colours, hidden technical properties) is the layer that makes the graph readable. It fits a small team well: build it automatically from the data and let users edit it.

### Gaps
- The fetched pages did not confirm the details of category icons (Bloom is widely known to support them, but I did not cite that). Node size options were not covered either.

## Stardog Explorer / Voicebox

### Takeaway
Stardog's business-user surfaces are an entity page per class or instance, with linked previews of neighbours, and the Voicebox chat with a "knowledge panel" beside the answer. A graph view is offered from the visual Query Builder.

### Cited Findings
- Explorer has an entity view: a detailed page per entity showing **up to 10 instances of each connected property**, each a link to keep exploring. Its visual Query Builder shows results as a list or a graph. Visualizations are capped at about 5,000 entities — [Stardog blog: Explorer](https://stardog.com/blog/discover-connections-in-your-data-fabric-with-stardog-explorer/); [Stardog Explorer docs](https://docs.stardog.com/stardog-applications/explorer/)
- Voicebox turns natural language into SPARQL. Its **knowledge panel** gives "a detailed view of the data associated with a user question or selected item", with attributes and relationships hyperlinked for traversal. Answers from the graph are marked separately from answers produced by an LLM or RAG — [Stardog Voicebox docs](https://docs.stardog.com/voicebox)
- Stardog's own positioning (vendor claim): Voicebox exists because "not all users have the specialized skills needed to query data" — [Databricks/Stardog case study](https://www.databricks.com/customers/stardog)

### Inferences
- "Show N related per link type, with links" is a simple rule for keeping profile pages readable.
- Marking where an answer came from (the graph or the model) is a trust pattern worth copying in a chat answer.

### Gaps
- I did not verify a Stardog Designer visual schema description, and some Explorer docs are archived (8.x), so the details may be out of date.

## metaphactory

### Takeaway
Every resource gets its own templated wiki-style HTML page. There are three default views per resource: Graph, Statements (a list of facts) and Page. There is also a visual ontology-modelling diagram (OWL/SHACL) aimed at business and technical experts working together.

### Cited Findings
- Each URI resource is rendered as its own HTML page built from templates (semantic wiki approach) — [Semantic Web Journal paper on metaphactory](https://www.semantic-web-journal.net/system/files/swj2149.pdf)
- In the AWS Neptune walkthrough, a resource offers Graph, Statements and Page views, with Graph as the default in that setup — [AWS blog: metaphactory + Neptune](https://aws.amazon.com/blogs/database/visualize-and-explore-knowledge-graphs-quickly-by-connecting-metaphactory-to-amazon-neptune); [AWS Neptune docs](https://docs.aws.amazon.com/neptune/latest/userguide/visualization-metaphacts.html)
- The product has visual ontology modelling with OWL/SHACL and table- and graph-based views. Marketing describes the modelling environment as shared by business and technical experts (vendor claim) — [metaphacts product](https://metaphacts.com/product); [Ontodia](https://metaphacts.com/ontodia)

### Inferences
- Offering the same entity as a page, as a list of statements (the "sentence view of facts") and as a graph, switchable by tabs, is a strong and simple pattern.

### Gaps
- I found no 2024–2026 release notes describing changes to these views.

## Atlan, Collibra (catalogs / glossaries)

### Takeaway
Catalogs lead with an asset or term **profile page**: definition, owners, tags, linked assets, related terms. Graphs show up only as lineage or as a small relationship widget. Collibra's current docs list relations as a **table or tiles**; older versions also had a diagram option.

### Cited Findings
- An Atlan glossary term page brings together definitions, metadata, relationships, tags and linked assets. Related terms (related-to, synonyms, antonyms; for example "User" preferred over "Customer") can be placed in set sections of the page — [Atlan glossary term page demo](https://atlan.com/demos/glossary-term-page.md); [Atlan glossary docs](https://docs.atlan.com/product/capabilities/governance/glossary/concepts/what-is-a-glossary)
- An Atlan release note added an **interactive relationship-graph widget** for term relationships: click a term to expand its associations. The term sidebar was reorganised around semantic relationships. I found no date for this note. A separate note adds multi-level "business lineage" on a Data Product's Lineage tab — [Atlan: relationship graph for associated terms](https://shipped.atlan.com/view-relationship-graph-for-associated-terms-3ykiYg); [Atlan: multi-level business lineage](https://shipped.atlan.com/navigate-your-data-estate-better-with-multi-level-business-lineage-3MC1va)
- Collibra asset pages (2026.02 docs) show relations of the same type "as a table or as a set of tiles". Administrators set the page layout per asset type. Older docs (2023.08) had a diagram in each asset page's tab pane and relation views shown as diagrams (nodes movable, editing limited) — [Collibra asset pages 2026.02](https://productresources.collibra.com/docs/collibra/2026.02/Content/Assets/co_asset-pages.htm); [Collibra diagrams 2023.08](https://productresources.collibra.com/docs/collibra/2023.08/Content/Assets/Diagrams/to_diagrams.htm)

### Inferences
- Collibra's 2026 docs list relations only as a table or tiles, which may mean a move away from diagrams for everyday relation viewing. I could not confirm that the diagram was removed.
- Relations grouped by type, each group shown as tiles, is directly buildable.

### Gaps
- Alation, data.world, Timbr and TopBraid EDG were not researched within the call budget, so I have no cited findings for them.

## Kumu

### Takeaway
Kumu is a full-map tool, but it ships "focus" and "showcase" modes and data-driven decorations so that readers are not shown the whole map at once.

### Cited Findings
- Focus concentrates on chosen elements and their connections and loops, hiding the rest. A "prompted" mode gives readers a search box instead of the full map — [Kumu focus](https://docs.kumu.io/guides/focus)
- Showcase highlights a selection and fades the rest, in normal, loose or strict modes with a configurable fade — [Kumu showcase](https://docs.kumu.io/guides/showcase)
- Decorations can be direct or data-driven (styled automatically from profile data). Saved settings are called "views" — [Kumu decorate](https://docs.kumu.io/guides/decorate); [Kumu views](https://docs.kumu.io/guides/views)

### Inferences
- "Prompted focus" (start from search, show the ego network n steps out) is the same search-first, ego-network answer the enterprise tools reach.

## Consumer patterns: the Google Knowledge Panel (one entity card)

### Takeaway
The Knowledge Panel is a single card on the search results page: description, key attributes, key people or social links, and a "People also search for" strip of related entities. It is the standard example of showing related entities without drawing a graph.

### Cited Findings
- Typical components are a description, attributes, key people, social profiles and related entities ("People also search for"). That section can appear below the panel and again at the bottom of the page, and has been shown as a scrollable widget — [Search Engine Land](https://searchengineland.com/guides/knowledge-graph); [SERoundtable: pairing panels and PASF](https://www.seroundtable.com/google-pairing-knowledge-panels-28949.html); [SERoundtable: scrollable PASF](https://www.seroundtable.com/google-knowledge-panel-people-also-search-for-scrollable-unit-31616.html)
- A 2023 report saw "data overlays" on related-entity cards that show the same fact (for example, age) for each related person — [SERoundtable: data overlays](https://www.seroundtable.com/google-knowledge-panel-cards-data-overlays-36259.html)
- Verified owners can claim a panel and suggest edits — [G2 Learn](https://learn.g2.com/google-knowledge-panel)
- Caveat: all of these are SEO commentary, not Google documentation.

### Gaps
- I did not research or cite Wikipedia or LinkedIn infoboxes.

## Recurring patterns, and evidence on hairballs and "too technical" views

### Takeaway
Across vendors the default is **search, then a list or table, then a profile card or page**, with related records grouped by link type and counted. The graph is opt-in, starts empty or as one entity's neighbourhood, and grows on demand. Research interviews back this up: end users found node-link diagrams ineffective at real KG scale and preferred tables and cards.

### Cited Findings
- An interview study of KG practitioners (Li et al.) found node-link diagrams ineffective at the scale of real KGs. One team's end users **preferred simple table-based views over custom interactive graph interfaces**. The authors propose **"knowledge cards"** ("like a baseball card", the most essential data for an entity), possibly used as the nodes of a node-link diagram. Card content was very domain-specific. They describe three personas: Builders, Analysts and Consumers; business users are Consumers — [Li et al., Knowledge Graphs in Practice (arXiv 2304.01311)](https://arxiv.org/abs/2304.01311v1)
- Cambridge Intelligence (a graph-visualization vendor, so biased toward graphs) defines a hairball as showing every node and link of a densely connected graph. Its fixes:
  - Build a view around the workflow rather than the full KG (for example, a people-only view).
  - Draw derived links through shared intermediates, such as two people linked by a shared claim.
  - Size nodes by centrality.
  - Filter, aggregate, and use an organic layout.
  — [Cambridge Intelligence: how to fix hairballs](https://cambridge-intelligence.com/how-to-fix-hairballs/)
- Vendor responses that match those fixes:
  - **Card as node**: Palantir's object-card node style.
  - **Transactions folded into edges**: Palantir's group-into-edge.
  - **Start from search, not the whole graph**: Neo4j's scene.
  - **Instances only after a query**: Fabric's type-only graph.
  - **Readers start from a search prompt**: Kumu's prompted focus.
  - **Relations as tables or tiles in current docs**: Collibra.
  — sources as cited in the sections above.

### Inferences (pattern catalogue for a small React team)
1. **Search box first** with typed suggestions (Bloom pattern grammar, Palantir keyword search, Kumu prompted focus).
2. **Set view = table** with a facet or histogram filter that you click to filter (Object Explorer, Vertex histogram).
3. **Profile card or page per record** that is auto-generated from the schema (Palantir Standard Object View). Header and key facts at the top. **Related records grouped by link type, with counts, first N shown** (Stardog shows 10). Each related item is a small card you can click.
4. **Compact "panel" version** of the same card for hovers and side panels (Palantir Panel view, Bloom Inspector).
5. **Statements/sentence view**: list the facts as "subject, verb, object" lines (metaphactory Statements tab).
6. **Schema view separate from the instance view**, with a "Neighborhood" ego view of one type (Fabric IQ).
7. **Opt-in graph**: starts with one entity and expands one link type at a time, showing the count before you expand (Vertex right-click). Colour by type, captions from the business name (Perspective), and optionally draw nodes as mini cards.
8. **Collapse middle records into edges or aggregates** to avoid hairballs.
9. **Chat answers paired with an entity panel** that marks graph-sourced facts separately from model-generated text (Voicebox).

### Gaps
- I found no G2 or Reddit quotes specifically complaining about hairballs in Bloom, Vertex or other named products. The hairball evidence comes from academic interviews and a vendor blog.
- WebVOWL and Protégé OntoGraf were not researched, so the "too technical" contrast is not backed by citations here.
- Timeline views (Palantir events and time series, a Vertex time window) are only partly covered. The display-options page confirms time windows restyle the graph, but it does not describe a separate timeline widget.
