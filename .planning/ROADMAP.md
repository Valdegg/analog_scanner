# Roadmap: Analog Scanner

## Milestones

- 📋 **v1.0 Generic Scanner** - Phases 1-3 (planned)
- 🚧 **v1.1 Dashboard Filters** - Phases 4-5 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>v1.0 Generic Scanner (Phases 1-3)</summary>

- [ ] **Phase 1: Query Pipeline & Scraping** - Generate generic search queries and scrape full listing details from Kleinanzeigen.de
- [ ] **Phase 2: LLM Analysis & Results** - Identify devices from images/descriptions via OpenRouter and produce structured output files
- [ ] **Phase 3: Validation Experiment** - Run end-to-end scan, assess LLM quality, iterate on queries

</details>

### v1.1 Dashboard Filters

- [ ] **Phase 4: Data & Filter Controls** - Merge opportunity scores in web.py and add category, brand, opportunity, and text search filter UI
- [ ] **Phase 5: Cross-View Filter Integration** - Ensure all filters work across both views and combine with existing filters

## Phase Details

<details>
<summary>v1.0 Generic Scanner (Phases 1-3)</summary>

### Phase 1: Query Pipeline & Scraping
**Goal**: Users can run the generic scanner to search Kleinanzeigen.de with deduplicated mislabel queries and retrieve full listing data (high-res images + descriptions) ready for analysis
**Depends on**: Nothing (first phase)
**Requirements**: QGEN-01, QGEN-02, QGEN-03, SCRP-01, SCRP-02, SCRP-03, SCRP-04
**Success Criteria** (what must be TRUE):
  1. Running the generic scanner produces a deduplicated list of search queries from schema.json mislabels plus German generic terms
  2. Each query searches Kleinanzeigen.de with a 500 EUR price cap using existing Bright Data + Playwright infrastructure
  3. The scanner navigates to each listing's detail page and extracts high-res images and full description text
  4. Duplicate listings across queries are detected and analyzed only once
  5. Listings older than MAX_LISTING_AGE_DAYS are filtered out
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD

### Phase 2: LLM Analysis & Results
**Goal**: Each scraped listing is analyzed by an LLM with vision to identify the actual device, and results are saved as structured JSON sorted by value
**Depends on**: Phase 1
**Requirements**: LLM-01, LLM-02, LLM-03, LLM-04, LLM-05, OUT-01, OUT-02, OUT-03
**Success Criteria** (what must be TRUE):
  1. Each listing's images and description are sent to the LLM via OpenRouter API using credentials from .env
  2. The LLM uses open discovery (broad vintage gear knowledge) to identify devices -- not constrained to the 76-device schema.json catalog
  3. Each analysis returns structured JSON with: identified device name, brand, confidence, reasoning, estimated value, and is_candidate_valuable flag
  4. The LLM correctly interprets German marketplace conventions (VB, Bastler, Defekt, etc.) in its analysis
  5. When an identified device matches a schema.json entry, the system cross-references for precise market price and profit estimate
  6. Results are saved to a separate file (results/generic_scan_DATE.json) sorted by candidate value
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: Validation Experiment
**Goal**: The complete pipeline is run end-to-end on real data to validate LLM identification quality and refine the query list based on findings
**Depends on**: Phase 2
**Requirements**: EXP-01, EXP-02, EXP-03
**Success Criteria** (what must be TRUE):
  1. A full scan runs successfully across all unique mislabels plus German queries, producing a complete results file
  2. Results are reviewed to assess identification accuracy -- the user can see which identifications are correct, uncertain, or wrong
  3. The query list is updated based on findings: queries producing good results are kept, queries producing noise are removed or refined
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

</details>

### Phase 4: Data & Filter Controls
**Goal**: Users can narrow down dashboard listings using category, brand, opportunity score, and text search filters
**Depends on**: Phase 3 (or can run independently -- no dependency on v1.0 scanner phases)
**Requirements**: DATA-01, FILT-01, FILT-02, FILT-03, FILT-04
**Success Criteria** (what must be TRUE):
  1. The dashboard displays a combined opportunity score (rarity + liquidity + mispricing, range 3-15) for each listing, sourced from schema.json
  2. User can select a device category from a dropdown and only listings matching that category are shown
  3. User can select a brand from a dynamically populated dropdown and only listings from that brand are shown
  4. User can set a minimum opportunity score threshold and only listings at or above that score are shown
  5. User can type text into a search box and only listings whose device name or listing title match are shown
**Plans:** 1 plan

Plans:
- [ ] 04-01-PLAN.md -- Merge opportunity scores and add category/brand/opportunity/text filters

### Phase 5: Cross-View Filter Integration
**Goal**: All filters work consistently across both dashboard views and combine correctly with each other and with existing filters
**Depends on**: Phase 4
**Requirements**: XCUT-01, XCUT-02
**Success Criteria** (what must be TRUE):
  1. Switching between Best Deals and By Device views preserves active filter selections
  2. All four new filters (category, brand, opportunity, text) apply equally to both Best Deals and By Device views
  3. New filters combine correctly with existing price range and age filters -- activating multiple filters shows only listings matching ALL active criteria
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Query Pipeline & Scraping | v1.0 | 0/0 | Not started | - |
| 2. LLM Analysis & Results | v1.0 | 0/0 | Not started | - |
| 3. Validation Experiment | v1.0 | 0/0 | Not started | - |
| 4. Data & Filter Controls | v1.1 | 0/1 | Planning complete | - |
| 5. Cross-View Filter Integration | v1.1 | 0/0 | Not started | - |
