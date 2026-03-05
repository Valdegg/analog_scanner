# Requirements: Analog Scanner

**Defined:** 2026-03-05
**Core Value:** Surface hidden gems — listings where a valuable vintage device is sold under a vague generic title at a low price

## v1.1 Requirements

Requirements for Dashboard Filters milestone. Each maps to roadmap phases.

### Filtering

- [ ] **FILT-01**: User can filter listings by device category (synthesizer, keyboard, drum machine, drum synth, effect, sampler, microphone)
- [ ] **FILT-02**: User can filter listings by brand (populated dynamically from scan results)
- [ ] **FILT-03**: User can filter listings by minimum combined opportunity score (rarity + liquidity + mispricing, range 3-15)
- [ ] **FILT-04**: User can search listings by text (matches device name and listing title)

### Data Integration

- [ ] **DATA-01**: web.py loads schema.json and merges opportunity scores into scan data at render time

### Cross-Cutting

- [ ] **XCUT-01**: All filters (category, brand, opportunity, text search) apply to both Best Deals and By Device views
- [ ] **XCUT-02**: All filters combine with existing price range and age filters

## Future Requirements

### Generic Scanner

- **SCAN-01**: Generic query scanner that searches deduplicated mislabels and additional generic/German queries
- **SCAN-02**: Full listing page scraping (navigate to each result for high-res images + full description)
- **SCAN-03**: LLM analysis via OpenRouter with vision to identify devices from images and descriptions
- **SCAN-04**: Structured JSON output from LLM: identified device name, confidence, reasoning, estimated value
- **SCAN-05**: Separate results file for generic scan output
- **SCAN-06**: Price cap at 500€ for generic queries
- **SCAN-07**: German-language queries alongside English

## Out of Scope

| Feature | Reason |
|---------|--------|
| Modifying the scanner pipeline | Keep existing scanner as-is for this milestone |
| Deal rating filter (steal/good/market) | Could add later but not requested |
| Saved filter presets | Over-engineering for current needs |
| URL-persisted filter state | Nice-to-have but not core |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FILT-01 | — | Pending |
| FILT-02 | — | Pending |
| FILT-03 | — | Pending |
| FILT-04 | — | Pending |
| DATA-01 | — | Pending |
| XCUT-01 | — | Pending |
| XCUT-02 | — | Pending |

**Coverage:**
- v1.1 requirements: 7 total
- Mapped to phases: 0
- Unmapped: 7 ⚠️

---
*Requirements defined: 2026-03-05*
*Last updated: 2026-03-05 after initial definition*
