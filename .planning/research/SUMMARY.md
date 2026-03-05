# Project Research Summary

**Project:** Analog Scanner -- Generic Query LLM Analysis
**Domain:** LLM vision-powered marketplace listing analysis for vintage synthesizer identification
**Researched:** 2026-03-05
**Confidence:** HIGH

## Executive Summary

This project extends an existing Kleinanzeigen.de deal scanner with LLM-powered vision analysis to identify underpriced vintage synthesizers listed under generic terms. The recommended approach uses the OpenAI Python SDK pointed at OpenRouter's API, which provides OpenAI-compatible access to Claude Opus 4.5 for vision analysis with structured JSON output. The stack is minimal -- only `openai` and `pydantic` are new dependencies -- and the architecture adds three new files (`generic_scanner.py`, `llm_analyzer.py`, `scraping.py`) alongside the existing untouched `scanner.py`. This is a well-understood integration pattern with high-quality documentation from both OpenRouter and the OpenAI SDK.

The key differentiator over existing marketplace deal-finding tools is vision-based identification. Competing tools analyze listing titles and prices; this system analyzes the actual photos. A listing titled "altes Keyboard 50 EUR" with a photo of a Roland Juno-106 is invisible to text-based tools but obvious to vision-based analysis. The 76-device catalog in `schema.json` (with market prices, mislabels, and visual characteristics) provides domain-specific context that general-purpose tools lack.

The primary risks are LLM hallucination on ambiguous images (confidently misidentifying devices), uncontrolled API costs from un-resized images, and pipeline fragility if scraping and LLM analysis are not decoupled. All three are preventable with upfront design decisions: strong prompt engineering with explicit uncertainty language, mandatory image resizing before API calls, and a two-phase architecture that saves scraped data before running LLM analysis. The cost per scan run is estimated at $0.50-$2.00 with Claude Opus 4.5, which is manageable for batch usage.

## Key Findings

### Recommended Stack

Two new dependencies, both well-maintained and conflict-free with the existing stack. The project's async Playwright infrastructure maps cleanly to `AsyncOpenAI` for non-blocking LLM calls.

**Core technologies:**
- `openai` SDK (>=2.24.0): OpenRouter API client -- OpenRouter is OpenAI-compatible, so this battle-tested SDK handles auth, retries, async, and structured output natively
- `pydantic` (>=2.12.5): LLM response validation -- defines the analysis output schema and validates every response before processing
- `httpx` (bundled with openai): Image downloading for base64 encoding -- no separate install, async-native

**Critical integration notes:**
- Use `AsyncOpenAI(base_url="https://openrouter.ai/api/v1")`, NOT the Anthropic SDK or OpenRouter's native SDK
- Use `client.chat.completions.create()` with `response_format`, NOT `client.beta.chat.completions.parse()` (OpenAI-specific, unreliable through OpenRouter)
- Send images as base64, NOT as URLs (Kleinanzeigen.de may block external fetches)

### Expected Features

**Must have (table stakes):**
- Full listing page scraping (high-res images + full description, not thumbnails)
- LLM vision analysis with schema-aware prompt (76-device catalog in context)
- Structured JSON output (device name, confidence, reasoning, estimated value, is_candidate_valuable)
- Generic search query generation from deduplicated mislabels + German terms
- Deduplication across queries before LLM analysis (cost control)
- Price cap filtering at 500 EUR
- Estimated value comparison against schema.json market prices
- Separate results storage (generic_scan_DATE.json)

**Should have (differentiators):**
- Multi-image analysis (2-5 images per listing for low-confidence identifications)
- Dashboard integration for generic scan results
- Cross-reference with mislabel patterns in prompt
- Reasoning trace per listing (why the LLM made this identification)

**Defer (v2+):**
- Scheduled automated scans
- Notification system (email/Telegram)
- Historical listing tracking across scan runs
- Expanding device catalog beyond 76 devices

### Architecture Approach

The system adds a parallel pipeline alongside the existing `scanner.py` -- the existing device-specific scanner is untouched. Three new modules are introduced: `scraping.py` (shared utilities extracted from `scanner.py`), `generic_scanner.py` (pipeline orchestrator), and `llm_analyzer.py` (LLM concerns isolated). The pipeline is sequential with decoupled phases: scrape all listings first (save intermediate data), then run LLM analysis as a separate step.

**Major components:**
1. **Query Generator** -- deduplicates mislabels from schema.json, merges with hardcoded German generics, builds search URLs with 500 EUR cap
2. **Detail Page Scraper** -- navigates to individual listing URLs via Playwright/Bright Data to get high-res images and full descriptions
3. **LLM Analyzer** -- sends images + description to OpenRouter, enforces structured output schema, validates with Pydantic
4. **Result Aggregator** -- collects analyzed listings, writes `generic_scan_DATE.json`
5. **Shared Scraping Module** -- extracted `fetch_page()` and `parse_listings()` from `scanner.py` for reuse

### Critical Pitfalls

1. **Confident hallucination on ambiguous images** -- explicitly instruct the model to return "unidentifiable" for low-quality images; use confidence thresholds; validate with 20+ real listings before scaling
2. **Uncontrolled cost explosion from image tokens** -- resize all images to max 1568px before sending; cap at 2-3 images per listing; log token usage per run; set `max_tokens` on output
3. **Structured output fragility via OpenRouter** -- always use `strict: true` with `additionalProperties: false`; validate every response with Pydantic; make uncertain fields nullable; gracefully skip on parse failure
4. **Pipeline coupling creates cascading failures** -- decouple scraping from analysis with intermediate data file; implement incremental saving; add retry with exponential backoff
5. **German language blindness in prompts** -- include Kleinanzeigen-specific conventions in system prompt (VB, Bastler, Defekt, Abholung); add condition field to output schema; test with real German listings

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Shared Scraping Foundation
**Rationale:** Everything depends on the scraping infrastructure. Extract shared utilities first -- this is the lowest-risk change and unblocks all subsequent phases.
**Delivers:** `scraping.py` module with `fetch_page()`, `parse_listings()` extracted from `scanner.py`. Existing scanner verified still working.
**Addresses:** Shared infrastructure requirement from ARCHITECTURE.md
**Avoids:** Anti-Pattern 4 (modifying scanner.py directly)

### Phase 2: Generic Query Pipeline (Search + Scrape)
**Rationale:** Query generation and search result scraping are independent of LLM integration. Building this first allows testing the input pipeline without API costs.
**Delivers:** `generic_scanner.py` with query generation from schema.json mislabels, search URL building with 500 EUR cap, search result scraping, deduplication, and detail page scraping with high-res image extraction.
**Addresses:** Query generation, full listing page scraping, deduplication, price cap filtering
**Avoids:** Deduplication failure (Pitfall 6), thumbnail quality gap (Pitfall 7)

### Phase 3: LLM Analysis Core
**Rationale:** This is the highest-complexity, highest-risk phase. It depends on having real scraped data from Phase 2 to test against. Must nail prompt engineering, structured output, image handling, and cost controls simultaneously.
**Delivers:** `llm_analyzer.py` with OpenRouter integration, schema-aware prompt with German marketplace context, structured output with Pydantic validation, image resizing, token logging, and error handling with retries.
**Addresses:** LLM vision analysis, structured JSON output, confidence scoring, reasoning trace, estimated value comparison
**Avoids:** Hallucination (Pitfall 1), cost explosion (Pitfall 2), structured output fragility (Pitfall 3), German language blindness (Pitfall 5)

### Phase 4: End-to-End Integration
**Rationale:** Wire all components together into a runnable pipeline. This is where pipeline architecture decisions (decoupled phases, intermediate saves, resume capability) are implemented.
**Delivers:** Complete `generic_scanner.py` pipeline: search -> scrape -> save intermediate -> analyze -> save results. CLI entry point. Progress logging. Cost summary per run.
**Addresses:** Pipeline coupling (Pitfall 4), result storage, VB discount handling (Pitfall 9)
**Avoids:** Cascading failures from coupled pipeline

### Phase 5: Dashboard Extension
**Rationale:** Results are usable as JSON files from Phase 4. Dashboard is a usability enhancement, not a functional requirement. Build only after the core pipeline is validated.
**Delivers:** Extended `web.py` with generic scan results view showing LLM identification, confidence, reasoning, estimated profit. Separate from device-specific results.
**Addresses:** Dashboard integration feature
**Avoids:** Mixing generic and device-specific results (UX pitfall)

### Phase Ordering Rationale

- Phases 1-2 have zero LLM cost and validate the data pipeline independently
- Phase 3 is isolated to `llm_analyzer.py` and can be tested against saved data from Phase 2 without re-scraping
- Phase 4 integration depends on all prior components being individually validated
- Phase 5 is optional and decoupled -- the system is fully functional without it
- This ordering means a failure in LLM integration (Phase 3) does not waste scraping work, and prompt iteration is cheap because scraped data is reusable

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (LLM Analysis Core):** Prompt engineering for vintage synth identification is domain-specific and must be validated empirically. The exact prompt wording, confidence calibration, and German marketplace context will need iteration against real listings. Plan for 2-3 prompt iterations.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Shared Scraping Foundation):** Simple module extraction, well-understood Python pattern
- **Phase 2 (Generic Query Pipeline):** Extends existing scraping patterns already working in scanner.py
- **Phase 4 (End-to-End Integration):** Standard async pipeline orchestration
- **Phase 5 (Dashboard Extension):** Extends existing Flask app with new data source

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | OpenRouter docs, OpenAI SDK docs, PyPI versions all verified. Minimal new dependencies. |
| Features | HIGH | Clear feature landscape with well-defined MVP. Competitor analysis confirms vision-based ID is a genuine differentiator. |
| Architecture | HIGH | Flat module structure matches existing codebase. Build order is dependency-driven and verifiable at each phase. |
| Pitfalls | HIGH | Verified against Claude vision docs, OpenRouter structured output docs, and existing codebase patterns. All pitfalls have concrete prevention strategies. |

**Overall confidence:** HIGH

### Gaps to Address

- **Prompt quality for synth identification:** No research can predict how well Claude Opus 4.5 actually identifies vintage synths from German marketplace photos. Must validate with a test batch of 20-30 real listings during Phase 3. Plan for prompt iteration.
- **OpenRouter structured output reliability at scale:** Verified that structured outputs work in principle, but behavior under rate limiting or with edge-case images (no device visible, stock photos, multiple devices) needs testing during Phase 3.
- **Detail page HTML structure:** The exact Kleinanzeigen.de listing page DOM for extracting high-res images and full descriptions has not been researched. Phase 2 will need to inspect actual page structures. This is routine scraping work but may require iteration.
- **Cost at actual scan volume:** Estimated $0.50-$2.00 per run with ~100 listings, but actual query count from deduplicated mislabels and resulting listing volume is unknown until Phase 2 produces real data.

## Sources

### Primary (HIGH confidence)
- [OpenRouter Quickstart](https://openrouter.ai/docs/quickstart) -- Python SDK integration, API compatibility
- [OpenRouter Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs) -- json_schema support, strict mode
- [OpenAI Python SDK (PyPI)](https://pypi.org/project/openai/) -- v2.24.0, AsyncOpenAI, response_format
- [Pydantic (PyPI)](https://pypi.org/project/pydantic/) -- v2.12.5, validation patterns
- [Claude Vision Documentation](https://platform.claude.com/docs/en/build-with-claude/vision) -- image size limits, token costs, limitations

### Secondary (MEDIUM confidence)
- [OpenRouter Pricing](https://openrouter.ai/pricing) -- cost estimates (prices change)
- [Instructor + OpenRouter](https://python.useinstructor.com/integrations/openrouter/) -- evaluated and rejected
- [Top 10 VLMs 2026](https://dextralabs.com/blog/top-10-vision-language-models/) -- landscape context

### Tertiary (LOW confidence)
- Cost per scan run estimates -- depends on actual listing volume and image sizes, needs validation in Phase 2-3

---
*Research completed: 2026-03-05*
*Ready for roadmap: yes*
