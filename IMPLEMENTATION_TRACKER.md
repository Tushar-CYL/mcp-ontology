# Strata Implementation Tracker
# Based on "Strata final plan: the 4 layers, shown simply"

## Phase 1: Foundations (Prerequisites for all layers)
- [ ] **1.1** Readable record names, one-sentence summary per record, icon per thing type (M)
  - Files: `knowledge_graph/explore.py`, `ontology/simple.py` (store chosen name field)
  - [ ] Store `name_field` in class definition
  - [ ] Add `summary_template` per class for one-sentence summaries
  - [ ] Add `icon` field per class type
  - [ ] Update UI to use these fields

- [ ] **1.2** Shared legend and marks - one status function, one component (S)
  - Files: `api/trust.py`, `frontend/src/components/ProofMark.tsx`, `Legend.tsx`
  - [ ] Create unified status function in `api/trust.py`
  - [ ] Create `ProofMark` component for ✓ ? ↻ ✗ Person ◆
  - [ ] Create `Legend` component
  - [ ] Apply to all 4 pages

- [ ] **1.3** Running example picked from data, "Following..." strip, 4-step top bar (S)
  - Files: `ontology/example.py`, `frontend/src/components/LayerBar.tsx`
  - [ ] Create `ontology/example.py` to pick running example from data
  - [ ] Create `LayerBar` component with 4 steps
  - [ ] Add "Following [Record]" strip
  - [ ] Unified top bar across all 4 pages

- [ ] **1.4** Evidence drawer for any fact (M)
  - Files: `api/evidence.py`, `components/EvidenceDrawer.tsx`
  - [ ] Create `api/evidence.py` reusing `trust.py`, `review.py`, `business_rules.py`, `report_check.py`
  - [ ] Create `EvidenceDrawer.tsx` component
  - [ ] Show source, check, count, date, approver, agreed by N

## Phase 2: The Four Cards (Core product)
- [ ] **2.1** Record card as default KG view; globes as overview; picture on request (M)
  - Files: `pages/graph/KnowledgeGraphTool.tsx`, `GraphPicture.tsx`

- [ ] **2.2** Thing card, 3-part trust bar, tabs from 5 to 3 (M)
  - Files: `pages/ontology/SimpleOntology.tsx`, `OntologyView.tsx`

- [ ] **2.3** Meaning card, ◆ mark, "AI would assume" line, maths check (M)
  - Files: `semantic/model.py`, `pages/semantic/SemanticTool.tsx`

- [ ] **2.4** Answer card: "I read it as" chips, fact chips, "I left out", "Is this right?" (M)
  - Files: `context/engine.py`, `api/ctx_routes.py`, `pages/context/ContextTool.tsx`

## Phase 3: Learning and Trust
- [ ] **3.1** Rules as switches; rule results drawn dashed with "worked out from" (M)
- [ ] **3.2** Misreads inbox: corrected chips → "Make it a company meaning" (M)
- [ ] **3.3** Trust line in header + "what got better/worse" after change (S)
- [ ] **3.3** Conflict card: two values/definitions side by side, person picks one (M)
- [ ] **3.5** Decision log: who decided what, when, why; CSV/JSON download (S)
- [ ] **3.6** "As of" replay of answer + honest scope line (M)
- [ ] **3.7** 5-step tour on running example (S)
- [ ] **Later**: Duplicate check, record history, multi-step "why" reports (L)

## Phase 4: Enhanced Context & Semantic (from research)
- [ ] **Context improvements:**
  - [ ] Question-first context with metric detection
  - [ ] Metric catalog with health checks
  - [ ] Period comparison with contributors
  - [ ] Trend analysis
  - [ ] Source row evidence
  - [ ] Coverage scoring
  - [ ] Evidence drawer with citations

- [ ] **Semantic improvements:**
  - [ ] Metric catalog with health checks
  - [ ] Period comparison with contributors
  - [ ] Trend analysis
  - [ ] Metric insights (trend, contributors, dimension analysis)
  - [ ] Metric health checks

## Current Status
- [x] Server running at http://127.0.0.1:8000
- [x] Sources loaded: kaggledata, revenue_huge
- [x] Basic ontology, graph, semantic, context layers working
- [x] Agent Studio, Certification, Solutions pages working
- [ ] **NEXT: Start Phase 1 Foundations (1.1 - 1.4)**

## Implementation Order (per plan)
1. Start with **1.2** (Legend/ProofMark) - needed everywhere
2. Then **1.3** (LayerBar, running example) - provides navigation context
3. Then **1.1** (Record names, summaries, icons) - data foundation
4. Then **1.4** (Evidence drawer) - trust mechanism
5. Then **2.1-2.4** (Four cards) - core product
6. Then **3.1-3.7** (Learning & trust) - differentiation