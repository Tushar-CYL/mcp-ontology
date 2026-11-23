# Graph literacy and explanation techniques for non-expert (business) users

Scope: how lay users read node-link and concept visuals, and which explanation patterns help an ontology or knowledge graph make sense at a glance. Evidence quality is noted for each section. About 20 search and fetch calls; several full texts (PDFs) could not be read, so some figures come from abstracts or secondary write-ups, as flagged.

## 1. Graph literacy, the hairball, readable node counts, matrix vs node-link, focus+context, progressive disclosure, entity pages

### Takeaway
Node-link diagrams fail fast as they grow. In a controlled study, readers struggled with path-finding above about 50 nodes in dense graphs and about 100 in sparse ones. Novices also lack the conventions to read them. The strongest pattern is to start from one entity (search, then show context, then expand on demand) and show a small, task-shaped subgraph, with list, table or entity-page views as the main surface for lay users.

### Cited Findings
**Node-count limits (strongest numbers available)**
- Yoghourdjian et al. (IEEE InfoVis 2020, 22 participants, with EEG, heart rate and pupil measures) found that "people have significant difficulty finding the shortest path in high-density node-link diagrams with more than 50 nodes and even low-density graphs with more than 100 nodes." Cognitive load rose with difficulty and then dropped, which the authors read as people giving up. — [Harvard VCG paper page](https://vcg.seas.harvard.edu/publications/20201001-scalability-of-network-visualisation-from-a-cognitive-load-perspective); [arXiv 2008.07944](https://web3.arxiv.org/abs/2008.07944?context=cs)
- Caveat: these thresholds come from a shortest-path task only. A companion survey found most empirical graph-vis studies use small, sparse graphs. — [Yoghourdjian et al. 2018 survey, arXiv 1809.00270](https://arxiv.org/abs/1809.00270v1)

**Matrix vs node-link**
- Ghoniem, Fekete and Castagliola (InfoVis 2004) found that which view is better depends on graph size and density. Node-link performance dropped quickly as nodes increased, while matrix performance stayed nearly flat. Node-link was more accurate on 5 of 10 tasks and less accurate on 2. — summarised in [Okoe, Jianu, Kobourov, arXiv 1709.00293](https://arxiv.org/pdf/1709.00293.pdf) (secondary description; original not read)
- Okoe et al. re-ran the comparison on a real 258-node, 1,090-edge scale-free network. — [arXiv 1709.00293](https://ar5iv.labs.arxiv.org/html/1709.00293); see also [Kobourov TVCG18 PDF](https://smsf.cs.arizona.edu/~kobourov/NL-AM-TVCG18.pdf)
- Ware et al. found matrices supported tasks better than node-link for dense graphs (up to 100 nodes and 3,600 edges). — cited in [Yoghourdjian et al. 2020](https://vcg.seas.harvard.edu/publications/20201001-scalability-of-network-visualisation-from-a-cognitive-load-perspective)

**Layout aesthetics that matter**
- Ware, Purchase, Colpoys and McGill (Information Visualization 2002): for shortest-path finding, path length mattered most, followed by path continuity and edge crossings. — [Monash record](https://research.monash.edu/en/publications/cognitive-measurements-of-graph-aesthetics/); [UNH CCOM](https://ccom.unh.edu/publications/cognitive-measurements-graph-aesthetics)
- Earlier Purchase work found reducing edge crossings was the most important aesthetic. — as summarised in search results pointing to [Diehl et al. cae09](https://www.st.uni-trier.de/diehl/pubs/cae09.pdf) (secondary)

**Novice network literacy**
- Zoss's work on network visualization literacy notes that node-link diagrams, unlike axis-based charts, have no stable reference system. It also reports that museum visitors mostly struggled to explain how to read node-link images. — [Zoss 2018 dissertation, IU CNS](https://cns.iu.edu/docs/publications/2018-Zoss-NetworkVisualizationLiteracy.pdf); [Zoss NetSci 2018](https://cns.iu.edu/docs/publications/2018-NetSci-Zoss.pdf) (based on search snippets; the PDF did not parse)
- Node-link diagrams rely on implicit conventions (closeness means related, size means importance), and literacy studies ask whether users grasp these metaphors at all. — [Zoss NetSci 2018](https://cns.iu.edu/docs/publications/2018-NetSci-Zoss.pdf)

**Hairball (practitioner guidance)**
- Cambridge Intelligence defines a hairball as connections "so dense, they can't be usefully visualized." Their advice: design around the user's task and not the data model; show only the entities users care about and turn the rest into metadata; derive simpler links (for example, person-to-person via a shared claim); size nodes by centrality; filter and aggregate; keep the dense graph in the store and out of the UI. — [Cambridge Intelligence, How to fix hairballs](https://cambridge-intelligence.com/how-to-fix-hairballs/)
- Supernodes (very highly connected hubs) distort layouts and need separate handling. Showing only part of the data can mislead, so tell users what was filtered and let them control it. — [Cambridge Intelligence, dealing with starbursts](https://cambridge-intelligence.com/dealing-with-starbursts/); [fixing data hairballs](https://cambridge-intelligence.com/?p=24339)
- Further sources: [10 rules of great graph design](https://cambridge-intelligence.com/10-rules-great-graph-design/); [visualizing large networks](https://cambridge-intelligence.com/visualize-large-networks); Microsoft Research "Trimming the Hairball" (edge-cutting) — [MSR](https://www.microsoft.com/en-us/research/wp-json/wp/v2/msr-research-item/556776)

**Focus+context and degree-of-interest**
- van Ham and Perer, "Search, Show Context, Expand on Demand" (IEEE InfoVis 2009, TVCG 15(6)): adapts Furnas's degree-of-interest (DOI) from trees to graphs. It scores each node's relevance from attributes, topology and the user's search, extracts a maximal-interest subgraph around the focus, and lets users expand in the most interesting directions. It was demonstrated on a database of more than 3 million legal citations. — [CMU DIG page](https://dig.cmu.edu/publications/2009-doigraphs.html); [PDF](https://aviz.fr/wiki/uploads/Teaching2015/SearchShowContextArticle.pdf)

**Progressive disclosure (NN/g)**
- Progressive disclosure "defers advanced or rarely used features to a secondary screen." Designs with more than 2 levels usually have low usability: "If you have so many features that you need 3 or more levels, consider simplifying your design." Disclose everything users often need up front, keep the first view short, and leave out confusing features. — [NN/g, Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/)
- Staged disclosure (wizard, next and back) suits steps with little dependence on each other, and works poorly when users must move back and forth. — [NN/g](https://www.nngroup.com/articles/progressive-disclosure/)

**Entity pages, tables and lists vs graphs**
- Li et al., interviews with 19 KG practitioners: node-link diagrams "are often ineffective for both generating and delivering insights from large KGs." One team's end users ended up preferring simple tables over custom interactive graph interfaces. "Wikipedia-style" entity pages with entity hopping were preferred for open-ended exploration, and search for precise questions. — [Knowledge Graphs in Practice, arXiv 2304.01311](https://arxiv.org/html/2304.01311)
- Same study: one practitioner saw users disengage and distrust results once the on-screen graph got too complex. The authors suggest end users may not want knowledge shown in graph form. — [arXiv 2304.01311](https://arxiv.org/pdf/2304.01311)
- The "initial exploration problem": lay users do not know what questions are possible or how to map their needs onto the graph. — [McNamara, Hederman, O'Sullivan, arXiv 2602.21066](https://arxiv.org/html/2602.21066)
- In an LLM-assisted KG study (14 practitioners), participants used tables rather than graph views for results. — [arXiv 2505.21512](https://arxiv.org/abs/2505.21512)

### Inferences
- For an ontology screen aimed at managers, aim for well under 50 visible nodes by default (roughly 10 to 30 is a reasonable design target). This is an extrapolation from the 50/100 task thresholds, not a measured number.
- Default to an entity-first layout: search or pick one entity, show its 1-hop neighbourhood (an ego network) ranked by degree-of-interest, and offer "show more" per direction. Present the same content as a list or table next to the picture, or as the default.
- Hide hubs and generic relations (such as "has type" to a big class) behind aggregates ("42 customers") rather than drawing every edge.
- Keep disclosure to 2 levels: overview, then detail.

### Gaps
- No controlled study found that tests node-link against entity pages for lay business users. The evidence is interviews and qualitative work.
- No good peer-reviewed numbers on edge-label readability (how many labelled edges people can read) were found.
- The original Ghoniem 2004 figures were not checked against the primary text.
- Linkurious practitioner guidance was not reviewed.

## 2. Sentence-style facts, natural-language summaries, concept maps, storytelling and explorable explanations

### Takeaway
Text helps. Readers prefer charts with many annotations to minimalist ones, and concept maps (labelled node-link "propositions") improve learning by moderate amounts (d around 0.4 for studying ready-made maps). Narrative structures such as the martini glass (author-led steps, then free exploration) and Bret Victor's reactive documents are well-established design patterns, but rigorous comprehension evidence for scrollytelling is thin.

### Cited Findings
- Stokes, Setlur, Cogley, Satyanarayan and Hearst (IEEE VIS 2023): participants preferred charts with the most text annotations over charts with fewer annotations or text alone. Heavy annotation was not penalised. The kind of text (statistical or relational vs elemental) shaped what readers took away, and placement mattered: some information belongs in the title, some near the data. — [MIT Vis page](https://vis.mit.edu/pubs/vis-text-balance); [PDF](https://vis.mit.edu/pubs/vis-text-balance.pdf). The poster reports 302 survey participants — [Berkeley poster](https://epic.berkeley.edu/wiki/_media/retreats/2022fall/epic_stokes_poster.pdf) (preliminary)
- Concept maps meta-analysis, Nesbit and Adesope (Review of Educational Research 2006, 76:413-448): concept and knowledge maps were associated with better knowledge retention across settings. Effect sizes ranged from small to large depending on use. — [SFU](https://www.sfu.ca/~jcnesbit/research/nesbitadesope2006.htm). Secondary report: studying ready-made maps vs text gave d = 0.4, and building or modifying maps gave d = 0.82 (verify against the original).
- Schroeder, Nesbit, Anguiano and Adesope (2017) update: 142 effect sizes, overall g = 0.58 (p < 0.001) for learning with concept maps. — [Educational Psychology Review](https://link.springer.com/doi/10.1007/s10648-017-9403-9); [SFU summit](https://summit.sfu.ca/item/17789)
- Segel and Heer (2010), "Narrative Visualization": 7 genres and 3 interactive story structures. These are the martini glass (author-driven stem, then reader-driven bowl), the interactive slideshow, and the drill-down story. — [Heer PDF](https://homes.cs.washington.edu/~jheer/files/narrative.pdf)
- A 2026 study compares martini-glass scrollytelling with a reversed version (interactive first). The abstract does not report results. — [ICA abstract](https://ica-abs.copernicus.org/articles/12/22/2026/ica-abs-12-22-2026.pdf)
- Narrative-vis evaluation is rarely systematic, and standard metrics miss its experiential side. — [UTS 2025 paper](https://opus.lib.uts.edu.au/bitstream/10453/186527/2/s12650-025-01051-y.pdf); Microsoft Research storytelling techniques report — [MSR-TR-2016-14](https://microsoft.com/en-us/research/wp-content/uploads/2016/04/MSR-TR-2016-14-Storytelling-Techniques.pdf)
- Bret Victor, "Explorable Explanations" (2011): a reactive document lets the reader change the author's assumptions and see the results update, like a spreadsheet inside text (the Ten Brighter Ideas prototype, the Tangle library). The author must expose the model behind the argument. — [worrydream.com](https://worrydream.com/ExplorableExplanations/)
- The term dates to Brusilovsky (1994) and became popular after Victor. Alan Kay's "active essays" came earlier. Idyll is a later authoring tool. — [Wikipedia](https://en.wikipedia.org/wiki/Explorable_explanation); [Idyll paper](https://cj2017.northwestern.edu/documents/idyll-cj2017-paper-15.pdf); collection: [awesome-explorables](https://github.com/blob42/awesome-explorables)

### Inferences
- Sentence-style facts ("Stan attends South Park Elementary") are in effect the "propositions" of Novak-style concept maps (node, labelled link, node). The concept-map evidence supports showing labelled relations as readable statements. Combined with the Stokes result, a short plain-language summary of an entity next to (or above) the picture should help, not clutter.
- A martini-glass flow suits a "how this ontology was built" screen: 3 to 5 guided steps (sources, then things found, then links, then rules, then result), then free exploration. This fits the user's existing "build steps + result" preference.
- Victor's pattern maps onto "what if" controls, for example toggling a rule or source and watching the affected entities and metrics change.

### Gaps
- No controlled study was found that tests sentence or triple lists against node-link for KG comprehension specifically.
- No study was found that tests auto-generated natural-language entity summaries with lay users (Google-style knowledge panels lack published user studies in what was found).
- Distill.pub, Nicky Case and Observable explainers were not fetched. They are well-known design exemplars but not empirical evidence, and no claims about them are made here.
- Scrollytelling comprehension or retention effects remain unverified.

## 3. Showing uncertainty, provenance, inferred vs stated facts, and trust

### Takeaway
Dashed and "sketchy" lines are tested, intuitive ways to mark uncertain or inferred links, and users subjectively prefer dashing. However, graph visuals can make people trust wrong answers more than they should. Provenance cues should explain ("worked out from X and Y") and not just decorate.

### Cited Findings
- Boukhelifa, Bezerianos, Isenberg and Fekete (IEEE InfoVis 2012, TVCG 18(12):2769-2778) compared sketchiness, blur, dashing and greyscale for showing qualitative uncertainty on lines. Sketchiness was as intuitive as blur. Participants subjectively preferred dashing over blur, greyscale and sketchiness. The study also looked at how many levels of each could be told apart. — [IEEE VIS 2012](https://ieeevis.org/year/2012/paper/infovis/evaluating-sketchiness-visual-variable-depiction-qualitative-uncertainty); [Aviz project](https://aviz.fr/Research/UncertaintySketchy); [line attributes follow-up, arXiv 2308.04150](https://arxiv.org/pdf/2308.04150)
- In an LLM-assisted KG system study (14 practitioners), even KG experts tended to overtrust outputs because of the visualizations, even when the LLM was wrong. A reasoning-structure view helped non-experts check answers without reading the query. — [arXiv 2505.21512](https://arxiv.org/abs/2505.21512)
- Users disengaged and distrusted results when the graph became too complex. — [arXiv 2304.01311](https://arxiv.org/pdf/2304.01311)
- TRACE (MIT thesis) traces reasoning paths to build trust, and its user study found multi-hop paths hard to follow. — [MIT DSpace](https://dspace.mit.edu/server/api/core/bitstreams/32132935-fd7e-4117-b251-9912522dbad2/content)
- Prior provenance tools (such as Probe-It!) were evaluated with experts, not lay users. — [UTEP TR07-43](https://www.cs.utep.edu/vladik/2007/tr07-43.pdf)
- Cambridge Intelligence: say plainly what was filtered or left out, to avoid misleading partial views. — [dealing with starbursts](https://cambridge-intelligence.com/dealing-with-starbursts/)

### Inferences
- Use solid lines for stated (source-backed) facts and dashed lines for inferred ones, since dashing is the preferred and intuitive cue. Add a small badge or caption, "worked out from X and Y", that opens the 1- to 2-step reasoning path. Keep paths short, since multi-hop paths were hard to follow.
- Because visuals inflate trust, pair every inferred or AI-made fact with an explicit status word (confirmed, inferred, needs review) and its source. Do not rely on line style alone.

### Gaps
- No study was found that tests provenance badges or "worked out from" captions with lay business users.
- Evidence on how many uncertainty levels lay users can tell apart was not retrieved (the Boukhelifa experiment 2 numbers are unread).

## 4. Explaining abstraction levels (class vs instance, schema vs data) to beginners

### Takeaway
Learning-science evidence ("concreteness fading") supports starting with concrete examples and then moving explicitly to the abstract type. For an ontology, that means showing real records (for example "Stan, Kyle") before the class "Student". The evidence comes from maths and science teaching, not ontology UIs, and its generality is debated.

### Cited Findings
- Fyfe, McNeil, Son and Goldstone (2014, Educational Psychology Review 26:9-25), systematic review: begin with concrete instances and explicitly fade toward abstract symbols, as a way past the concrete-vs-abstract debate. — [IU PDF of McNeil & Fyfe](https://pcl.sitehost.iu.edu/rgoldsto/courses/cogscilearning/McNeilFyfe12.pdf); [IU scholarworks](https://scholarworks.iu.edu/dspace/items/f1ea5994-0d9f-4215-abec-152a03149277)
- Goldstone and Son (2005): going from concrete to abstract improved transfer compared with staying concrete or going abstract to concrete. — as summarised in [McNeil & Fyfe 2012](https://pcl.sitehost.iu.edu/rgoldsto/courses/cogscilearning/McNeilFyfe12.pdf)
- Counterpoint: a 2020 analysis argues concreteness fading "may not be as generalizable as has been suggested." — [Educational Psychology Review 2020](https://link.springer.com/article/10.1007/s10648-020-09581-7)
- Lay KG users face an "initial exploration problem" (not knowing what is in the graph or what to ask), which points to concrete entry points. — [arXiv 2602.21066](https://arxiv.org/html/2602.21066)

### Inferences
- Entity cards first ("Stan: attends South Park Elementary, in class 4B"), then "Stan is one of 412 Students", then the Student type card (fields, links). This fades from instance to class in 2 levels, consistent with NN/g's 2-level guidance.
- Label schema views in business words ("kinds of things" and "the actual records") rather than "class" and "instance".

### Gaps
- No HCI study was found that tests instance-first vs schema-first ontology presentation with business users.

## 5. How many nodes and labels people can handle; pictures and icons on nodes

### Takeaway
The firmest number is about 50 nodes (dense) or about 100 (sparse) before shortest-path reading breaks down. Pictographs that represent data carry no measured cost and some benefits, while decorative images can distract. There is no strong study on icons on graph nodes specifically.

### Cited Findings
- Thresholds of 50 and 100 nodes for path-finding. — [Yoghourdjian et al. 2020](https://vcg.seas.harvard.edu/publications/20201001-scalability-of-network-visualisation-from-a-cognitive-load-perspective)
- Node-link performance falls quickly with node count, while matrices hold steady. — [Okoe et al. summarising Ghoniem 2004](https://ar5iv.labs.arxiv.org/html/1709.00293)
- Haroz, Kosara and Franconeri (CHI 2015, ISOTYPE): "superfluous images can distract," but there were "no user costs – and some intriguing benefits" when pictographs represent the data. They measured working memory, search speed and engagement. — [Tableau Research page](https://tableau.com/research/publications/isotype-visualization-working-memory-performance-and-engagement-pictographs); [PDF](https://tableau.com/sites/default/files/2023-01/Haroz_CHI_2015.pdf)
- Practitioner advice: size nodes by importance (centrality) to bring the key entities forward. — [Cambridge Intelligence](https://cambridge-intelligence.com/how-to-fix-hairballs/)

### Inferences
- Use one meaningful icon per entity type (person, product, invoice) as a type cue, since the icon encodes data (the type). Avoid decorative imagery.
- Label every visible node, but cap the default view so labels do not collide. A target of 10 to 30 labelled nodes is an inference, not a measured limit.

### Gaps
- No peer-reviewed numbers were found for maximum readable edge labels, or for icons vs text-only nodes in node-link diagrams.
- Borkin et al.'s memorability work (recognisable objects help recall) was not fetched, so it is not cited.
- Working-memory figures such as "7 plus or minus 2" or "about 4 chunks" are often quoted for graph UIs, but no source tying them to graph reading was retrieved.
