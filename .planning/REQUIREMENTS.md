# Requirements: Analog Scanner — Generic Query LLM Analysis

**Defined:** 2026-03-05
**Core Value:** Surface hidden gems — listings where a valuable vintage device is sold under a vague generic title at a low price

## v1 Requirements

### Query Generation

- [ ] **QGEN-01**: System collects unique generic search queries by deduplicating `common_mislabels` across all devices in schema.json
- [ ] **QGEN-02**: System includes additional German-language generic queries (e.g. "alter Synthesizer", "Keyboard gebraucht", "altes Keyboard", "Vintage Synthesizer", "Drumcomputer alt")
- [ ] **QGEN-03**: Generic queries are searchable on Kleinanzeigen.de with a 500 EUR price cap (no minimum)

### Scraping

- [ ] **SCRP-01**: System searches Kleinanzeigen.de for each generic query using existing Bright Data + Playwright infrastructure
- [ ] **SCRP-02**: System navigates to each listing's detail page to fetch high-res images and full description text
- [ ] **SCRP-03**: System deduplicates listings across queries (same listing URL analyzed only once)
- [ ] **SCRP-04**: System filters out listings older than MAX_LISTING_AGE_DAYS (reuse existing constant)

### LLM Analysis

- [ ] **LLM-01**: System sends listing image(s) and description to LLM via OpenRouter API (using LLM_API_KEY and LLM_MODEL from .env)
- [ ] **LLM-02**: LLM uses broad knowledge of vintage music gear to identify devices (not constrained to schema.json catalog)
- [ ] **LLM-03**: LLM returns structured JSON with: identified_device_name, brand, confidence (0-1), reasoning, estimated_value_eur, is_candidate_valuable boolean
- [ ] **LLM-04**: LLM accounts for German marketplace context in analysis (understands "VB", "Bastler", "Defekt" etc.)
- [ ] **LLM-05**: If identified device matches a schema.json entry, system cross-references for precise market price and profit estimate

### Output

- [ ] **OUT-01**: Generic scan results saved to separate JSON file (`results/generic_scan_DATE.json`)
- [ ] **OUT-02**: Each result includes: listing data (title, price, URL, location, date, images) + LLM analysis (device ID, confidence, reasoning, estimated value, is_candidate_valuable)
- [ ] **OUT-03**: Results sorted by candidate value (is_candidate_valuable first, then by estimated profit/value)

### Experiment

- [ ] **EXP-01**: Run generic scanner on all unique mislabels + additional German queries to validate LLM analysis quality
- [ ] **EXP-02**: Review experiment results to assess identification accuracy and false positive rate
- [ ] **EXP-03**: Iterate on generic query list based on experiment findings (add/remove queries that produce good/poor results)

## v2 Requirements

### Dashboard

- **DASH-01**: Generic scan results viewable in existing web dashboard with LLM analysis details
- **DASH-02**: Dashboard shows listing image, identified device, confidence score, estimated value, reasoning

### Enhanced Analysis

- **EANA-01**: Multi-image analysis (2-5 images per listing) for higher identification accuracy
- **EANA-02**: Cost tracking per scan run (tokens used, estimated API cost)
- **EANA-03**: Confidence threshold filtering (hide low-confidence results)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Modifying existing device-specific scanner | Separate pipeline, don't break what works |
| Real-time/continuous scanning | Batch is fine; deals stay up for days on Kleinanzeigen |
| Auto-purchasing or messaging sellers | Legal/ethical issues, requires human judgment |
| Fine-tuned vision model | General-purpose VLM with good prompting is sufficient for this use case |
| Price prediction / trend analysis | Static market prices from schema.json are sufficient |
| Constraining LLM to only schema devices | Defeats the purpose of discovery — must identify ANY potentially valuable gear |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| QGEN-01 | Phase ? | Pending |
| QGEN-02 | Phase ? | Pending |
| QGEN-03 | Phase ? | Pending |
| SCRP-01 | Phase ? | Pending |
| SCRP-02 | Phase ? | Pending |
| SCRP-03 | Phase ? | Pending |
| SCRP-04 | Phase ? | Pending |
| LLM-01 | Phase ? | Pending |
| LLM-02 | Phase ? | Pending |
| LLM-03 | Phase ? | Pending |
| LLM-04 | Phase ? | Pending |
| LLM-05 | Phase ? | Pending |
| OUT-01 | Phase ? | Pending |
| OUT-02 | Phase ? | Pending |
| OUT-03 | Phase ? | Pending |
| EXP-01 | Phase ? | Pending |
| EXP-02 | Phase ? | Pending |
| EXP-03 | Phase ? | Pending |

**Coverage:**
- v1 requirements: 18 total
- Mapped to phases: 0
- Unmapped: 18

---
*Requirements defined: 2026-03-05*
*Last updated: 2026-03-05 after initial definition*
