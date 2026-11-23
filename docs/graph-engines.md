# Do we need Neo4j? (one page)

**Short answer: no.** Strata's knowledge graph is *virtual*: it reads the live tables through the
links the ontology proved, so there is no copy, nothing goes stale, and there is no licence to buy.
On the SAP SALT data it builds 4.7 million records and 11.7 million connections in about
10 seconds on a laptop (our own measurement).

A graph database is worth adding only when questions need **very deep chains** (5+ hops, such as
fraud rings or multi-tier supply paths), **graph algorithms** (PageRank, community detection), or
**sub-second traversal under heavy concurrent load**. Finance and sales questions (totals over
facts with 1–3 joins) rarely look like that.

If a client already runs one, Strata exports the graph for it: Neo4j import CSVs, RDF (Turtle) and
a JSON graph (Knowledge graph → Use it).

## The options, checked November 2026

| Option | What it is | Licence / cost | Fit |
|---|---|---|---|
| **Strata virtual graph** (DuckDB) | Virtual, over the live tables | Our code, no licence | The default |
| DuckPGQ | Graph queries (SQL:2023 SQL/PGQ) inside DuckDB | Community extension | If we need path queries, with no new engine |
| Ontop | Virtual knowledge graph, SPARQL | Apache 2.0 (v5.5.0, Feb 2026), Java | Reference design |
| Timbr | Virtual SQL ontology over existing tables | No public price | Closest commercial product to our approach |
| Neo4j Community | Native graph database | GPLv3, one server, no role-based access | Free, but limited |
| Neo4j Enterprise / AuraDB | Same, with clustering, roles and the algorithms library | Self-hosted prices on request only; AuraDB Business Critical lists about $292/month for 2 GB | Costly at scale |
| Apache AGE | Graph on PostgreSQL | Apache 2.0 | If the client already runs Postgres |
| Memgraph | Native graph | BSL; Enterprise from $25k/year (vendor price) | Commercial |
| TigerGraph Community | Native graph | Free but proprietary; 200 GB cap, no high availability | Pilots only |
| ArangoDB | Multi-model | Community licence; 100 GiB limit; commercial use restricted | Avoid |
| FalkorDB | Native graph | SSPLv1 | Avoid for bundling |
| Kùzu | Embedded graph | Project archived October 2025 | Avoid |

**On "market leader":** Neo4j is first on the DB-Engines graph ranking. That ranking measures
popularity (search interest, job ads, questions), not market share or fit.

**Do not repeat** the "$75k–100k per month" Neo4j figure from a forum post (AI-generated, not a
price), Timbr's "$599 per user per month" (unverified), or that Apple bought Kùzu (unconfirmed).

Sources: the research report `reports/Enterprise Context Factory roadmap.md` (Neo4j pricing and
operations manual, Neo4j Aura pricing, DB-Engines, Memgraph, TigerGraph, ArangoDB and FalkorDB
licence pages, Ontop releases, DuckDB community extensions, The Register on Kùzu).
