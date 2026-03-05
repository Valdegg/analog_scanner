# Analog Scanner — Generic Query LLM Analysis

## What This Is

An extension to the existing Kleinanzeigen.de deal scanner that finds underpriced vintage synthesizers and keyboards listed under generic terms (e.g. "altes Keyboard", "80s synth") where sellers don't know what they have. Uses an LLM with vision (via OpenRouter) to analyze listing images and descriptions, identify the actual device, and judge whether it's a potentially valuable find.

## Core Value

Surface hidden gems — listings where a valuable vintage device is sold under a vague generic title at a low price, and the seller doesn't realize what they have.

## Current Milestone: v1.1 Dashboard Filters

**Goal:** Make the web dashboard more usable by adding filters for category, brand, and opportunity score.

**Target features:**
- Category filter (synthesizer, keyboard, drum machine, etc.)
- Brand filter (Roland, Korg, Moog, etc.)
- Combined opportunity score filter (rarity + liquidity + mispricing)
- Filters apply to both Best Deals and By Device views

## Requirements

### Validated

- ✓ Device-specific scanning with keyword matching and price-based deal rating — existing
- ✓ HTML scraping of Kleinanzeigen.de via Bright Data + Playwright — existing
- ✓ Schema-driven device catalog with market prices and deal detection thresholds — existing
- ✓ Web dashboard for browsing scan results — existing
- ✓ `common_mislabels` defined per device in schema.json — existing

### Active

- [ ] Category filter on dashboard (synthesizer, keyboard, drum machine, drum synth, effect, sampler, microphone)
- [ ] Brand filter on dashboard (populated from scan results)
- [ ] Combined opportunity score filter (sum of rarity + liquidity + mispricing from schema.json, min threshold)
- [ ] web.py merges opportunity scores from schema.json at render time
- [ ] Filters apply to both Best Deals and By Device views

### Future

- [ ] Generic query scanner that searches deduplicated mislabels and additional generic/German queries
- [ ] Full listing page scraping (navigate to each result for high-res images + full description)
- [ ] LLM analysis via OpenRouter with vision to identify devices from images and descriptions
- [ ] Structured JSON output from LLM: identified device name, confidence, reasoning, estimated value
- [ ] Separate results file for generic scan output
- [ ] Price cap at 500€ for generic queries
- [ ] German-language queries alongside English

### Out of Scope

- Modifying the existing device-specific scanner pipeline — keep it as-is
- Real-time notifications or alerts — batch scan only
- User authentication for the web dashboard
- Automatic purchasing or bidding

## Context

- Existing scanner (`scanner.py`) searches Kleinanzeigen.de for 76 specific devices by name/keyword, rates deals by price vs market value
- `schema.json` contains `common_mislabels` per device — terms sellers use when they don't know the device name (e.g. "Roland keyboard", "80s keyboard", "old synth")
- OpenRouter API key and model already configured in `.env` (`LLM_API_KEY`, `LLM_MODEL=anthropic/claude-opus-4.5`)
- Marketplace is Kleinanzeigen.de (Germany) — listings are in German
- Bright Data Scraping Browser provides proxy/anti-detection for scraping
- Existing scraper already extracts: title, price, VB flag, description snippet, location, date, image_url from listing cards

## Constraints

- **API**: Must use OpenRouter API (compatible with OpenAI SDK format) with `LLM_API_KEY` and `LLM_MODEL` from `.env`
- **Cost**: LLM calls cost tokens — analyze all listings from generic queries but be mindful of prompt size
- **Infrastructure**: Reuse existing Bright Data + Playwright scraping infrastructure
- **Language**: Python, matching existing codebase style (flat modules, async, no frameworks beyond Flask)
- **Output**: Generic scan results go to separate JSON files in `results/` (e.g. `generic_scan_DATE.json`)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Scrape full listing pages (not just thumbnails) | Higher-res images + full descriptions give LLM better signal | — Pending |
| LLM analyzes all listings (no pre-filter) | Even listings with brand names might be mislabeled/undervalued | — Pending |
| Open discovery (not schema-constrained) | LLM uses broad vintage gear knowledge, not just our 76-device catalog; schema used only for cross-referencing known devices after identification | — Pending |
| 500€ price cap for generic queries | Sellers who don't know value price low; above 500€ they likely know what they have | — Pending |
| Separate results file for generic scans | Different data shape (LLM analysis fields) and don't pollute device-specific results | — Pending |
| German + English queries | Kleinanzeigen.de is German marketplace; sellers use German terms | — Pending |

---
| Merge opportunity scores in web.py (not scanner) | Works with existing scan results, no re-scan needed | — Pending |

---
*Last updated: 2026-03-05 after milestone v1.1 started*
