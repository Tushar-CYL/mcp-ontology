# Industry-standard ontologies for enterprise data, and aligning an AI-made ontology to them

Context: a manager's concern, "clients won't trust an LLM-made ontology; we must use industry-standard ontologies accepted worldwide." These notes cover which standards can actually be used, what their licences allow, what they cover (CPG, finance, R2R/P2P/O2C on SAP data), how mapping to them is automated and how accurate that is, what vendors do, and how to explain ontology terms in plain language.

Research date: 2026-11-18. About 20 searches and fetches. Many licence pages could not be fetched in full; where only a snippet or a secondary source was available, that is noted.

## 1. Which standards fit: domain, format, licence, maturity, size, users

### Takeaway
Only a handful are both open and machine-readable as ontologies: FIBO (MIT), GS1 Web Vocabulary (Apache 2.0), schema.org, gist (CC BY 4.0), BFO/CCO (CC BY 4.0 / BSD-3) and Microsoft CDM (CC BY 4.0 content, MIT code). Product and commodity classifications are a mix: GPC can be downloaded, UNSPSC's PDF is free but other formats are paid, and ECLASS is paid. The IFRS taxonomy is free only for non-commercial use, so a vendor product that embeds it needs a licence. None of these standards models an SAP R2R/P2P/O2C transaction end to end, so a client-specific extension layer will always be needed.

### Cited Findings
**FIBO (EDM Council, finance)**
- FIBO uses the MIT open-source licence for all of its ontologies. — [FIBO ONTOLOGY_GUIDE](https://www.github.com/edmcouncil/fibo/blob/master/ONTOLOGY_GUIDE.md)
- FIBO OWL is published as two releases (Development and Production). The Production release comes out at the end of each calendar quarter and is built only from sources at "Release" maturity. — [FIBO OWL page](https://spec.edmcouncil.org/fibo/page/owl); [Development process](https://spec.edmcouncil.org/fibo/page/development-process)
- The 2022Q2 release contained 290 ontologies using 380 prefixes. A claim of "17,000+ classes" comes only from a low-quality secondary site and is unverified. — search summary of a 2023 FIBO/Crunchbase paper ([crunchbase-fibo](https://github.imc.re/ElisaKendall/crunchbase-fibo)); [domainmodel.pages.dev (unreliable)](https://domainmodel.pages.dev/chapter5.html)
- Loader files are LoadFIBODev.rdf and LoadFIBOProd.ttl, and each ontology is also served at a dereferenceable URI. — [FIBO OWL page](https://spec.edmcouncil.org/fibo/page/owl)

**GS1 Web Vocabulary (CPG / retail product master data)**
- Released under Apache 2.0, with a further licence statement inside the vocabulary files. The current ratified version is at ref.gs1.org/voc. Archived immutable versions include 1.12.1 (published 2024-09-27), 1.12.0 and 1.11.0. Downloads are JSON-LD (gs1Voc.jsonld) and Turtle. — [GS1 WebVoc GitHub](https://github.com/gs1/WebVoc); [ref.gs1.org/voc](https://ref.gs1.org/voc/); [archive](https://ref.gs1.org/voc/data/archive)
- Classes are subclassed; for example, gs1:FoodBeverageTobaccoProduct is a subclass of gs1:Product. — [gs1.org/voc/Product](https://gs1.org/voc/Product)
- Also listed on BioPortal as GS1WEBVOC. — [BioPortal](https://bioportal.bioontology.org/ontologies/GS1WEBVOC)

**GS1 GPC (Global Product Classification)**
- Published schemas can be downloaded per segment or as a "Combined Published Schema". — [GS1 GPC get started](https://gs1.org/gpc-get-started)
- GS1 Egypt's browser page lists JSON, XML and XLSX downloads. — [GS1 Egypt GPC Browser](https://gs1eg.org/?p=38598)
- A GS1 news headline gives the size of one release as 2,857 Bricks, 4,405 Attributes and 32,020 Values. An earlier release had 1,636 bricks. — [GS1 article](https://www.gs1.org/articles/gpc-publishes-2857-bricks-4405-attributes-32020-values); [earlier](https://www.gs1.org/articles/gpc-publishes-1636-bricks-3144-attributes-25081-values)
- A secondary source says GPC is updated twice a year and is freely available. GS1's own explicit data licence text was not found. — [OKFN](https://product.okfn.org/gs1-product-classification)

**schema.org**
- Not re-fetched in this session. schema.org's terms page states that schema.org content is licensed under Creative Commons Attribution-ShareAlike 3.0 (from background knowledge; verify). — [schema.org terms](https://schema.org/docs/terms.html)

**gist (Semantic Arts, minimalist enterprise upper ontology)**
- Free under CC BY 4.0, and the GitHub repository carries the same licence. An older v1 page said CC BY-SA 3.0, which the newer pages supersede. — [gist page](https://semanticarts.com/gist); [GitHub](https://github.com/semanticarts/gist)
- Size figures conflict across Semantic Arts' own pages: "211 concepts (98 classes, 113 properties)", "just over 135 classes and about 140 properties", and "roughly 100 classes". Core classes include Event, Agreement and Organization. First developed in 2007. A BFO-ready version exists. — [What is gist](https://semanticarts.com/?p=185); [gist v1](https://www.semanticarts.com/?p=8525); [BFO-ready gist](https://www.semanticarts.com/?p=9893)

**BFO / CCO (top-level and mid-level, defence and industry)**
- BFO is standardised as ISO/IEC 21838-2:2021 and is used by over 700 open-source ontology initiatives. BFO-2020 content is CC BY 4.0. CCO is BSD-3 on GitHub (CUBRC). — [Beverley et al., arXiv 2404.17758](https://arxiv.org/pdf/2404.17758v1); [CUBRC](https://www.cubrc.org/data-science-information-fusion/specialized-data-ontology-development/); [ISO/IEC 21838-2](https://iteh.es/catalog/standards/iso/1cac031c-2e73-4e51-a4f1-5e4075f26d27/iso-iec-21838-2-2021)

**Microsoft Common Data Model**
- Standard entities are open source under a Creative Commons licence on GitHub (a mirror lists CC BY 4.0 for content and MIT for code). The financial-services data models are MIT. Entity definitions use major/minor versioning, and existing versions persist unchanged. Preview entities were merged or removed at 1.0 GA (around 2020). — [CDM FAQ](https://learn.microsoft.com/en-us/common-data-model/faq); [mirror licence](https://github.com/fErten/CDM); [FS data model](https://learn.microsoft.com/en-us/dynamics365/industry/financial-services/overview-data-model)

**SAP One Domain Model (ODM)**
- A harmonised domain model and "taxonomy" for SAP business objects, defined in CDS format. The December 2020 release made the CDS sources available for the first time. Early scope covered Recruit-to-Retire and Lead-to-Cash, with business objects such as cost centres. SAP flags the pages as partly outdated. An OData vocabulary namespace exists: com.sap.vocabularies.ODM.v1. — [SAP ODM Dec 2020 update](https://blogs.sap.com/t5/technology-blogs-by-sap/sap-one-domain-model-december-2020-update/ba-p/13465536); [ODM vocabulary](https://sap.github.io/odata-vocabularies/vocabularies/ODM.html); [CSN interop spec](https://sap.github.io/csn-interop-specification/primer)

**IFRS Accounting Taxonomy / US GAAP (XBRL)**
- IFRS digital taxonomies are free for non-commercial purposes, such as preparing corporate disclosures. Embedding them in products, data services or commercial applications needs prior written permission and a commercial licence (contact licenses@ifrs.org). The 2025 taxonomy includes IFRS 18 and IFRS 19. — [IFRS licensing](https://www.ifrs.org/products-and-services/ifrs-accounting-licensing/); [Taxonomy architecture 2026](https://www.ifrs.org/content/dam/ifrs/standards/taxonomy/general-resources/ifrs-taxonomy-architecture/taxonomy-architecture-2026.pdf); [terms](https://ifrs.org/content/dam/ifrs/about-us/legal-and-governance/legal-docs/taxonomy/taxonomy-terms-and-conditions.pdf); [XBRL Intl news](https://www.xbrl.org/news/ifrs-accounting-taxonomy-2025-published-incorporating-ifrs-18-and-ifrs-19-disclosures/)
- The FASB maintains the US GAAP Financial Reporting Taxonomy for SEC filers, and a 2026 GRT has been released. Its licence terms were not found. — [XBRL US taxonomies](https://xbrl.us/standards/taxonomies/)

**UNSPSC / ECLASS (product and commodity classification)**
- UNSPSC: anyone can download the current codeset as a free PDF. Excel downloads and subscriptions are paid (a Solution Provider subscription was $775 on a 2022 page). — [UNSPSC subscribe](https://unspsc.org/subscribe); [FAQ](https://unspsc.org/faqs)
- ECLASS: use requires a licence bought from the shop or ECLASS e.V. membership. The price scales with employee count, and the current release is free for research and education. — [ECLASS licences](https://eclass.eu/en/eclass-standard/licenses); [prices](https://eclass.eu/en/eclass-standard/prices)

**OAGIS, UN/CEFACT, ISO 8000, ISO 15926, OMG Commons, GDSN**
- OAGIS: the only licence reference found says the terms are in a LICENSE.TXT on the OAGi site (seen in an OAGIS 8.0 schema). OAGIS 10 terms were not found. — [OAGIS 8 invoice xsd](https://schemas.liquid-technologies.com/HR-XML/2007-04-15/invoice_xsd.html)
- UN/CEFACT, ISO 8000, ISO 15926, OMG Commons and GDSN were not researched in depth (see Gaps).

### Inferences
- If the manager wants standards that are "accepted worldwide", the defensible open set is FIBO (finance and legal entities), GS1 WebVoc and GPC (CPG products, which is what Unilever and Kellogg's use through GDSN/GTIN), schema.org (generic Organization, Order, Invoice, Offer, Product), gist (enterprise upper layer) and BFO (ISO top level). CDM and ODM are vendor models, not neutral standards, but they are closest to ERP tables.
- The IFRS licence matters for us. Showing IFRS taxonomy elements inside a commercial product counts as commercial use, so we need a licence or must reference IFRS concepts only by ID.
- ECLASS and paid UNSPSC formats cannot be bundled. The client must bring its own licence.

### Gaps
- Current FIBO class count and latest Production release tag (use the GitHub releases page or run a SPARQL count).
- Exact GPC data licence text, schema.org licence (not re-verified in this session), OAGIS 10 licence, UN/CEFACT CCL/BSP RDF availability, OMG Commons licence, ISO 8000/15926 (ISO documents are paid; ISO 15926 has OWL parts), and the GS1 WebVoc term count.

## 2. Coverage of R2R, P2P and O2C on SAP data

### Takeaway
No single standard covers ERP process objects. GL accounts, journal entries and cost centres are weakly covered: FIBO is about instruments, contracts and parties, not bookkeeping, and IFRS/XBRL covers reporting line items, not postings. P2P and O2C documents (PO, invoice, order, delivery) are covered as message schemas by UN/CEFACT, OAGIS and GS1 EDI, and lightly by schema.org (Order, Invoice). Customers, vendors and legal entities map well to FIBO (LEI/BE), gist and schema.org Organization. Products map to GS1/GPC.

### Cited Findings
- SAP SALT is a real ERP dataset from SAP's NeurIPS'24 Table Representation Workshop paper. It contains I_SalesDocument, I_SalesDocumentItem, customer and address tables, with train/test parquet splits. Licence: CC BY-NC-SA 4.0, gated behind a non-commercial-use-only agreement. It was added to RelBench as rel-salt in July 2025. SALT-KG also exists. — [HF SAP/SALT](https://huggingface.co/datasets/SAP/SALT); [arXiv 2501.03413](https://arxiv.org/html/2501.03413v1); [SAP news](https://news.sap.com/2025/04/sap-salt-real-erp-dataset-enterprise-ai-research); [RelBench](https://relbench.stanford.edu/datasets/rel-salt); [SALT-KG](https://huggingface.co/datasets/SAP/SALT-KG)
- SAP ODM covers Lead-to-Cash and business objects such as cost centres, in CDS. — [SAP ODM blog](https://blogs.sap.com/t5/technology-blogs-by-sap/sap-one-domain-model-december-2020-update/ba-p/13465536)
- IFRS taxonomy elements are disclosure and reporting concepts. — [IFRS digital financial reporting](https://www.ifrs.org/digital-financial-reporting/)

### Inferences
- Suggested mapping for SAP objects (my judgement, to validate):
  - I_Customer → schema.org Organization or Person, fibo-be LegalEntity, gist Organization.
  - I_SalesDocument → schema.org Order, gist Agreement or Commitment, OAGIS SalesOrder.
  - Billing → schema.org Invoice.
  - Material → gs1:Product plus a GPC brick.
  - GL account → IFRS/XBRL element (for reporting roll-up).
  - Journal entry and cost centre → client or ODM extension.
- The SALT dataset is non-commercial. It can be used for internal benchmarking of our mapping feature, but not shipped in the product or used for commercial demos without checking the licence.

### Gaps
- No open OWL ontology for GL, journal entries or cost centres was found. REA-based accounting ontologies and the UN/CEFACT Buy-Ship-Pay model were not verified in this session.

## 3. How data-derived ontologies are aligned to standards, and how accurate it is

### Takeaway
The state of the art is a pipeline: embedding retrieval of the top-k candidates, then LLM verification (yes/no plus confidence), then a one-to-one or logical-consistency filter, then human review. Accuracy varies a lot by domain. On easy, well-labelled pairs F1 is around 0.85 to 0.94. On hard, large, or poorly labelled pairs it can fall to 0.25 to 0.5. LLMs tend to confuse subclass with equivalence, and to force a match when none exists. So auto-accept must be thresholded, and review is mandatory.

### Cited Findings
- LLMs4OM (TIB, 2024) uses a retriever (TF-IDF, SBERT, SPECTER2, OpenAI Ada) to return the top-5 candidates, then a zero-shot yes/no LLM prompt. Post-processing keeps pairs with LLM confidence above 0.7 and retriever score above 0.9, and enforces 1:1 matching. Across 20 OAEI tasks it beat the OAEI 2023 best on 9. Example P/R/F1:
  - Anatomy: 90.8/87.5/89.1 (OAEI best 94.1)
  - Nell-DBpedia: 100/89.1/94.3
  - YAGO-Wikidata: 100/85.5/92.2
  - MI-EMMO: 96.7/92.1/94.3
  - SNOMED-FMA: 21.1/32.6/25.6 (OAEI best 78.5)
  - MI-MatOnto: F1 33.0

  Retriever recall at k=5: Ada 90.9%, SBERT 86.1%, SPECTER2 82.1%, TF-IDF 75.2%. Average recall rises from 82.1% at k=5 to 86.8% at k=20. — [LLMs4OM arXiv 2404.10317](https://arxiv.org/html/2404.10317v1)
- OLaLa (Hertling and Paulheim, 2023) relies only on textual descriptions and ranks among the top 3 OAEI systems in many test cases. — [arXiv 2311.03837](https://arxiv.org/pdf/2311.03837)
- LogMap with an LLM Oracle validating a subset of mappings came top-2 overall in the OAEI 2025 Bio-ML track. — [arXiv 2508.08500](https://arxiv.org/html/2508.08500v2)
- GenOM (2025) generates definitions, retrieves candidates with embeddings and uses exact-match tools to protect precision. It reports competitive Bio-ML results. — [arXiv 2508.10703](https://arxiv.org/html/2508.10703v1)
- Known failure modes:
  - GPT-4 alignment showed high recall but lower precision because it classified subclass relations as equivalence.
  - In KG matching, the expansion step had low precision because the LLM picks a candidate even when no correct match exists.
  - DogMa argues that precision and recall are underestimated when the gold alignments are incomplete.

  — [ceur Vol-4085 paper32](https://ceur-ws.org/Vol-4085/paper32.pdf); [OM2025 DogMa](https://ceur-ws.org/Vol-4144/om2025-oaei-paper12.pdf)
- Non-LLM baseline: in OAEI 2025 Anatomy, Matcha had the highest recall+ (0.82). — [OAEI 2025 Anatomy](https://oaei.ontologymatching.org/2025/results/anatomy/index.html)
- Agent-OM (2023) reports the best P/R/F1 on the OAEI 2022/2023 MSE track against 4 systems. — [arXiv 2312.00326](https://arxiv.org/pdf/2312.00326)
- RIGOR (arXiv 2506.01232, June 2025) turns relational schemas into OWL table by table along foreign keys. It uses RAG over (a) the schema and its documentation, (b) a repository of domain ontologies, and (c) the growing core ontology. It produces provenance-tagged "delta ontology" fragments, which a judge LLM or a human refines. Tested on medical DBs with Llama 3.1, DeepSeek 67B and Mistral 3.1, it was better than schema-only and non-iterative baselines. — [RIGOR arXiv](https://arxiv.org/html/2506.01232v1)

### Inferences
- Because RIGOR retrieves from domain ontologies during generation, it directly answers the manager's concern. The answer is to generate the ontology anchored to standards, so each new class is linked to FIBO/GS1/schema.org at creation time, rather than "LLM invents, then maps".
- A realistic target for enterprise labels such as SAP field names (cryptic, abbreviated): precision close to the stronger OAEI cases only after enriching labels with descriptions, sample values and the CDS annotations, plus human sign-off. Treat roughly 0.7 confidence as "suggest", not "accept". This is an inference; no benchmark exists for SAP-to-FIBO/GS1.

### Gaps
- No published benchmark for mapping ERP schemas (SAP) to FIBO, GS1 or schema.org was found. We would need our own gold set (for example, SALT tables to schema.org/GS1 terms) to quote accuracy.
- MILA and the R2RML tooling were not researched in this session.

## 4. How vendors let customers import or reuse standard ontologies

### Takeaway
RDF-native vendors (Stardog, TopQuadrant, PoolParty, Neo4j through n10s) import OWL, including FIBO, directly. Palantir and Microsoft Fabric IQ use their own object-type models. Their OWL/RDF import is limited, brings in only the type schema, or comes from third-party tools. Vendor claims are marketing-heavy.

### Cited Findings
- Palantir's documented route: ontology schema is exported and imported as a JSON file, and Palantir warns that the JSON format may change. A white paper claims native RDF/OWL import and export, but this is unconfirmed in the docs. Third-party converters turn the JSON into OWL 2 and SHACL. — [Palantir export/import](https://palantir.com/docs/foundry/ontology-manager/export-import/); [community thread](https://community.palantir.com/t/is-there-a-native-rdf-or-owl-export-for-the-ontology/7187)
- Microsoft Fabric IQ: Gartner says ontologies can now import and export RDF definitions, but that RDF support "does not guarantee OWL-level semantic richness", and that the product is optimised as a Power BI extension. Third-party tooling notes that OWL import brings in only the type schema unless a data source is bound. W3C list members (April 2026) are sceptical. — [Gartner First Take](https://www.gartner.com/en/insights/gartner-first-takes/microsoft-fabric-iq); [W3C list](https://lists.w3.org/Archives/Public/semantic-web/2026Apr/0004.html); [MS Learn](https://learn.microsoft.com/en-gb/training/modules/fabric-prepare-semantic-layer/5-enterprise-ontology)
- Stardog collaborated on FIBO (2017 press release, "first FIBO-aware KG platform"). FIBO documentation gives an OWL zip import path. — [Stardog PR](https://stardog.com/news/stardog-collaborates-with-the-edm-council-on-the-fibo-financial-data-standard); [FIBO tools](https://spec.edmcouncil.org/fibo/page/ontology-tools)
- Timbr lists a FIBO ontology among its industry ontology models for NL2SQL. The import mechanism is not documented in the sources found. — [Timbr ontology models](https://timbr.ai/?p=31550)
- Neo4j neosemantics did not follow nested owl:imports at the time of the thread, so FIBO files had to be merged first. — [Neo4j community](https://community.neo4j.com/t/fibo-ontology-with-neosemantics/21620)
- TopQuadrant blog covers approaches to using and extending FIBO, and PoolParty sells financial-services knowledge models. OpenMetadata has an ontology studio library. — [TopQuadrant](https://topquadrant.com/blog/best-approaches-for-using-and-extending-fibo-vocabulary); [PoolParty](https://www.poolparty.biz/knowledge-models-financial-services/); [OpenMetadata](https://docs.open-metadata.org/v2.1.x-SNAPSHOT/how-to-guides/ontology/studio/library)

### Inferences
- Even market leaders (Palantir, Fabric) do not force standard ontologies. They let customers build their own types. Offering "map to standard + extend" would compete well with them.

### Gaps
- data.world, Collibra and Informatica standard-ontology import were not researched in this session.

## 5. Plain-language definitions: class, type, object/instance, property, relationship; SHACL

### Takeaway
A class (also called a type) is a kind of thing, for example "Customer". An instance (object, individual) is one real thing of that kind, for example customer 0001000123. Properties describe instances. Relationships link instances. SHACL is the W3C rule language that checks that instances follow the shape rules.

### Cited Findings
- GS1 example of a class hierarchy: FoodBeverageTobaccoProduct is a subclass of Product. — [gs1.org/voc](https://ref.gs1.org/voc/)
- Palantir terms: "object types", with links and properties. Fabric IQ terms: "entity types" and relationships. — [Palantir docs](https://palantir.com/docs/foundry/ontology-manager/export-import/); [MS Learn](https://learn.microsoft.com/en-gb/training/modules/fabric-prepare-semantic-layer/5-enterprise-ontology)
- Not re-fetched in this session: OWL 2 defines classes, individuals, object properties (between individuals) and datatype properties (to literal values) — [W3C OWL 2 Primer](https://www.w3.org/TR/owl2-primer/). SHACL validates RDF graphs against "shapes", for example "every SalesOrder must have exactly one soldTo Customer", and produces a validation report — [W3C SHACL](https://www.w3.org/TR/shacl/).

### Inferences
Suggested glossary for the manager:

| Term | OWL/RDF | Property graph / Palantir / Fabric | SAP example |
|---|---|---|---|
| Class / Type | owl:Class | Node label / object type / entity type | Sales Document |
| Object / Instance | individual (rdf:type) | node / object | Sales order 4711 |
| Attribute | datatype property | node property | NetAmount, Currency |
| Relationship | object property | edge / link type | soldTo → Customer |
| Subclass | rdfs:subClassOf | (label inheritance, often absent) | StandardOrder ⊂ SalesDocument |
| Mapping to a standard | owl:equivalentClass / skos:exactMatch / skos:closeMatch / rdfs:subClassOf | (none native) | SalesDocument skos:closeMatch schema:Order |
| Validation | SHACL shape | constraints | each order has 1 customer |

### Gaps
- The W3C definitions above were not re-verified in this session.

## 6. Practical recommendation: a "standards mapping" feature

### Takeaway
Keep the data-derived ontology, which fits the client's real tables, but anchor every class and property to a standard term. Show the standard term, the match type, the confidence and the evidence, and require human approval. Anything that does not map becomes a marked client extension under the nearest standard parent. This answers the trust concern: the vocabulary is standard, and the fit to the data is shown.

### Cited Findings
- The pattern used: retrieve the top-k candidates with embeddings (k=5 to 20 gives about 82% to 87% recall), verify with an LLM (accept only above a confidence threshold), enforce 1:1 matching, then review. — [LLMs4OM](https://arxiv.org/html/2404.10317v1)
- LLMs confuse subclass with equivalence, so the match type has to be modelled explicitly. — [ceur Vol-4085](https://ceur-ws.org/Vol-4085/paper32.pdf)
- Anchoring at generation time, with RAG over domain ontologies and provenance-tagged deltas, is the RIGOR approach. — [RIGOR](https://arxiv.org/html/2506.01232v1)
- Logic-based repair (LogMap) combined with an LLM oracle performs at the top of OAEI. — [arXiv 2508.08500](https://arxiv.org/html/2508.08500v2)

### Inferences (design proposal)
1. **Standards packs**, loaded offline and with licences respected:
   - Bundled: FIBO (MIT), GS1 WebVoc (Apache 2.0), schema.org, gist (CC BY 4.0), BFO/CCO.
   - Client supplies: GPC download, UNSPSC Excel, ECLASS (paid), IFRS taxonomy (commercial licence needed if we embed it).
2. **Per class and field**, show the matched term (with IRI and a link), the match type (exact / close / broader (subclass of) / related / none), confidence (0 to 1), and evidence: label and definition similarity, sample values, the parent/child context, and the LLM rationale.
3. **Thresholds**: auto-suggest only. Pre-tick when confidence is 0.9 or above and the match is exact. Anything below 0.7 shows "no confident match → propose extension". Never auto-accept equivalence without review.
4. **Extensions**: a client namespace, each class rdfs:subClassOf its nearest standard parent (for example clientX:CostCentre ⊂ gist:Organization or an ODM concept), flagged "client-specific".
5. **Validation**: export SHACL shapes generated from the approved ontology and run them on instances. Report a coverage score: the share of classes and fields mapped to a standard, broken down by pack.
6. **Evaluation**: build a gold set from SAP SALT (internal, non-commercial use only) mapped to schema.org/GS1/FIBO. Report P/R/F1 per pack and re-run on model change. Report "coverage %" and "precision of accepted suggestions" to clients.
7. **Pitch to the manager**: "We don't replace standards with an LLM. The LLM proposes, the standards define the terms, a human approves, and SHACL checks it." Note that FIBO alone will not cover CPG or ERP transactions, so a mix of packs is required.

### Gaps
- No empirical accuracy figure exists yet for SAP field to standard term. It must be measured on our own gold set before giving clients numbers.
