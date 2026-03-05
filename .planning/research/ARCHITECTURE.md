# Architecture Research

**Domain:** LLM-powered marketplace listing analysis integrated into async scraping pipeline
**Researched:** 2026-03-05
**Confidence:** HIGH

## System Overview

The generic query scanner adds three new components alongside the existing pipeline. The existing `scanner.py` device-specific pipeline remains untouched. The new generic scanner is a parallel pipeline that shares the scraping infrastructure but has its own query generation, detail scraping, LLM analysis, and output.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Data Schema Layer                            │
│  ┌──────────────┐  ┌──────────────────────┐                         │
│  │ schema.json  │  │ Generic Query Config │                         │
│  │ (existing)   │  │ (mislabels + extras) │                         │
│  └──────┬───────┘  └──────────┬───────────┘                         │
│         │                     │                                     │
├─────────┼─────────────────────┼─────────────────────────────────────┤
│         │   Pipeline Layer    │                                     │
│         ▼                     ▼                                     │
│  ┌─────────────┐    ┌──────────────────┐                            │
│  │ scanner.py  │    │ generic_scanner  │                            │
│  │ (existing,  │    │ (NEW module)     │                            │
│  │  untouched) │    │                  │                            │
│  └──────┬──────┘    └───────┬──────────┘                            │
│         │                   │                                       │
│         │           ┌───────┼──────────────────┐                    │
│         │           ▼       ▼                  ▼                    │
│         │    ┌──────────┐ ┌──────────────┐ ┌────────────────┐       │
│         │    │ Search   │ │ Detail Page  │ │ LLM Analyzer   │       │
│         │    │ Results  │ │ Scraper      │ │ (OpenRouter)   │       │
│         │    │ Scraper  │ │ (NEW)        │ │ (NEW)          │       │
│         │    └──────────┘ └──────────────┘ └────────────────┘       │
│         │                                                           │
├─────────┼───────────────────────────────────────────────────────────┤
│         │   Shared Infrastructure                                   │
│         ▼                                                           │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ Bright Data + Playwright (shared scraping infrastructure)│       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                     Persistence Layer                                │
│  ┌──────────────────┐  ┌──────────────────────┐                     │
│  │ results/         │  │ results/              │                     │
│  │ scan_DATE.json   │  │ generic_scan_DATE.json│                     │
│  │ (existing)       │  │ (NEW)                 │                     │
│  └──────────────────┘  └──────────────────────┘                     │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                   Web Presentation Layer                             │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ web.py + templates (existing, extended for generic view) │       │
│  └──────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| **Query Generator** | Deduplicate mislabels from `schema.json`, merge with hardcoded German generic queries, build search URLs with 500 EUR price cap | Pure function in `generic_scanner.py`, reads `schema.json` `common_mislabels` fields |
| **Search Results Scraper** | Fetch listing cards from Kleinanzeigen.de search pages for generic queries | Reuses existing `fetch_page()` and `parse_listings()` from `scanner.py` (import or extract to shared module) |
| **Detail Page Scraper** | Navigate to individual listing URLs to get full descriptions and high-res images | New async function using existing Playwright/Bright Data infrastructure |
| **LLM Analyzer** | Send listing images + description to OpenRouter vision API, get structured identification | New module `llm_analyzer.py` using `openai` SDK with `AsyncOpenAI` pointed at OpenRouter |
| **Result Aggregator** | Collect all analyzed listings, write `generic_scan_DATE.json` | Part of `generic_scanner.py` main loop |

## Recommended Project Structure

```
analog_scanner/
├── scanner.py                # Existing device-specific scanner (UNCHANGED)
├── generic_scanner.py        # NEW: Generic query scanner entry point
├── llm_analyzer.py           # NEW: LLM analysis via OpenRouter
├── scraping.py               # NEW: Shared scraping utilities extracted from scanner.py
├── schema.json               # Existing device catalog (read-only)
├── web.py                    # Existing Flask dashboard (extended)
├── templates/
│   └── index.html            # Existing template (extended for generic results)
├── results/
│   ├── scan_*.json           # Existing device scan results
│   └── generic_scan_*.json   # NEW: Generic scan results
└── .env                      # Existing env vars + LLM_API_KEY, LLM_MODEL
```

### Structure Rationale

- **Flat module structure:** Matches the existing codebase convention. No packages, no `src/` directory. Every Python file is a root-level module.
- **`scraping.py` extraction:** The existing `fetch_page()` and `parse_listings()` functions in `scanner.py` need to be importable by `generic_scanner.py`. Extract them to a shared module. This is the only change to the existing pipeline -- `scanner.py` imports from `scraping.py` instead of defining them inline.
- **`llm_analyzer.py` as separate module:** Keeps LLM concerns (prompt construction, API calls, response parsing) isolated from scraping logic. Makes it testable independently and swappable.
- **`generic_scanner.py` as entry point:** Parallel to `scanner.py` -- same CLI pattern (`python generic_scanner.py [limit]`), same async structure, same output convention.

## Architectural Patterns

### Pattern 1: OpenAI SDK as OpenRouter Client

**What:** Use the official `openai` Python SDK with `AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=LLM_API_KEY)` instead of raw HTTP requests or the OpenRouter SDK. OpenRouter's API is OpenAI-compatible.
**When to use:** Always for this project. The `openai` SDK is well-maintained, has native async support via `AsyncOpenAI`, handles retries, and supports structured outputs.
**Trade-offs:** Adds `openai` as a dependency. Upside: battle-tested, typed, async-native. The OpenRouter-specific SDK is less mature.

**Example:**
```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("LLM_API_KEY"),
)

response = await client.chat.completions.create(
    model=os.getenv("LLM_MODEL", "anthropic/claude-opus-4.5"),
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }
    ],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "listing_analysis",
            "strict": True,
            "schema": ANALYSIS_SCHEMA,
        },
    },
)
```

### Pattern 2: Sequential Scrape-Then-Analyze Pipeline

**What:** Scrape all search results first, then scrape detail pages, then run LLM analysis. Three distinct sequential phases within a single scan run.
**When to use:** When scraping and LLM calls have different rate-limiting and failure characteristics. Scraping is Bright Data rate-limited; LLM calls are token-budget-limited.
**Trade-offs:** Uses more memory (holds all scraped data before analysis), but simplifies error handling and makes it easy to retry just the LLM phase if it fails. Also allows deduplication between scrape and analyze phases.

**Example pipeline:**
```python
async def run_generic_scan():
    # Phase 1: Generate queries from schema mislabels
    queries = build_generic_queries(schema)

    # Phase 2: Scrape search results for all queries
    all_listings = []
    for query in queries:
        listings = await scrape_search_results(query)
        all_listings.extend(listings)

    # Phase 3: Deduplicate by URL
    unique_listings = deduplicate(all_listings)

    # Phase 4: Scrape detail pages for full info
    for listing in unique_listings:
        listing["detail"] = await scrape_detail_page(listing["url"])

    # Phase 5: LLM analysis
    for listing in unique_listings:
        listing["analysis"] = await analyze_listing(listing)

    # Phase 6: Save results
    save_results(unique_listings)
```

### Pattern 3: Structured JSON Output via Response Format

**What:** Use OpenRouter's `response_format` with `json_schema` type to enforce the LLM returns exactly the fields needed (device name, confidence, reasoning, estimated value, is_candidate_valuable).
**When to use:** Always. Do not rely on prompt instructions alone for JSON structure -- use the API's schema enforcement.
**Trade-offs:** Not all models support `json_schema` mode. Claude models on OpenRouter support it. If the model does not support strict mode, fall back to `json_object` mode with schema instructions in the prompt.

**Analysis output schema:**
```python
ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "identified_device": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reasoning": {"type": "string"},
        "estimated_value_eur": {"type": ["number", "null"]},
        "is_candidate_valuable": {"type": "boolean"},
    },
    "required": [
        "identified_device", "confidence", "reasoning",
        "estimated_value_eur", "is_candidate_valuable"
    ],
    "additionalProperties": False,
}
```

## Data Flow

### Generic Scan Pipeline

```
schema.json (common_mislabels per device)
    │
    ▼
Query Generator ──► ["altes Keyboard", "80s synth", "Roland keyboard", ...]
    │                 (deduplicated, + hardcoded German queries)
    │
    ▼
Search URL Builder ──► kleinanzeigen.de/s-preis:0:500/altes-keyboard/k0
    │
    ▼
Search Results Scraper (Playwright + Bright Data)
    │
    ▼
Listing Cards [title, price, url, thumbnail, snippet...]
    │
    ▼
Deduplication (by URL, since multiple queries hit same listings)
    │
    ▼
Detail Page Scraper (navigate to each listing URL)
    │
    ▼
Enriched Listings [+ full description, high-res images]
    │
    ▼
LLM Analyzer (OpenRouter vision API)
    │   Input: high-res image(s) + full description + listing title + price
    │   Output: structured JSON analysis
    ▼
Analyzed Listings [+ identified_device, confidence, reasoning, estimated_value, is_candidate_valuable]
    │
    ▼
Result Writer ──► results/generic_scan_2026-03-05_1430.json
```

### LLM Analysis Detail Flow

```
Per listing:
    ┌─────────────────────────────────────────────────┐
    │ Construct prompt:                                │
    │  - System: "You are a vintage synthesizer       │
    │    expert identifying devices from images"       │
    │  - User: listing title + price + description     │
    │  - User: image_url (high-res from detail page)   │
    └────────────────────┬────────────────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────────────────┐
    │ OpenRouter API call:                             │
    │  model: LLM_MODEL from .env                     │
    │  response_format: json_schema (strict)           │
    │  content: [text prompt, image_url]               │
    └────────────────────┬────────────────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────────────────┐
    │ Parse response:                                  │
    │  - Validate JSON against schema                  │
    │  - Extract structured fields                     │
    │  - Attach to listing dict                        │
    └─────────────────────────────────────────────────┘
```

### Key Data Flows

1. **Query generation:** `schema.json` -> extract all `common_mislabels` arrays -> flatten -> deduplicate -> add hardcoded German terms -> list of search queries
2. **Image URL chain:** Search page thumbnail (`image_url` from listing card) -> Detail page high-res image(s) -> Sent to LLM as `image_url` content block. Use the detail page image, not the thumbnail -- higher resolution gives the LLM better signal for device identification.
3. **Result output:** Different shape from existing scan results. Generic results include `analysis` block with LLM fields. Saved to separate `generic_scan_*.json` files.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| ~50 queries, ~200 listings | Current sequential approach works fine. ~200 LLM calls at ~2s each = ~7 minutes. Acceptable for batch. |
| ~200 queries, ~1000 listings | Add concurrency for LLM calls (asyncio.Semaphore with 3-5 concurrent). Add progress tracking. Consider caching analyzed listings by URL to skip re-analysis on repeated runs. |
| ~500+ queries, ~5000 listings | Pre-filter listings before LLM (e.g., skip if price > 500 EUR already handled by URL, but also skip duplicates across scan runs). Consider chunked processing with intermediate saves. |

### Scaling Priorities

1. **First bottleneck: LLM API latency.** Each listing requires one API call with image. At 2-5 seconds per call sequentially, 200 listings = 7-17 minutes. Fix with bounded concurrency (asyncio.Semaphore).
2. **Second bottleneck: LLM API cost.** Claude Opus 4.5 with vision is expensive. For initial experimentation this is fine, but at scale consider switching `LLM_MODEL` to a cheaper vision model (e.g., `anthropic/claude-sonnet-4` or `google/gemini-2.0-flash`) after validating quality.

## Anti-Patterns

### Anti-Pattern 1: Interleaving Scraping and LLM Calls

**What people do:** Scrape a listing, immediately call LLM, scrape next listing, call LLM, etc.
**Why it's wrong:** Different failure modes and rate limits. If the LLM API goes down mid-scan, you lose all progress. If Bright Data rate-limits you, LLM calls sit idle.
**Do this instead:** Scrape all listings first (with intermediate saves), then run LLM analysis as a separate phase. This way you can re-run just the analysis phase if it fails.

### Anti-Pattern 2: Sending Thumbnails Instead of Full Images

**What people do:** Use the `image_url` from the search results page (small thumbnail) for LLM vision analysis.
**Why it's wrong:** Thumbnails are low-resolution, often cropped. The LLM cannot reliably identify a specific synthesizer model from a 200px thumbnail.
**Do this instead:** Navigate to the full listing page, extract the high-resolution image URL(s), and send those to the LLM.

### Anti-Pattern 3: Prompt-Only JSON Structure

**What people do:** Ask the LLM to "return JSON with these fields" in the prompt without using `response_format`.
**Why it's wrong:** LLMs sometimes add markdown fencing, extra text, or miss fields. Parsing breaks unpredictably.
**Do this instead:** Use OpenRouter's `response_format: { type: "json_schema", json_schema: {...} }` to enforce structure at the API level.

### Anti-Pattern 4: Modifying scanner.py Directly

**What people do:** Add generic scanning logic directly into the existing `scanner.py`.
**Why it's wrong:** Different data shapes, different query logic, different output format. Mixing them creates a tangled module that is hard to maintain and debug.
**Do this instead:** Keep `generic_scanner.py` as a separate entry point. Extract shared utilities (scraping functions) to `scraping.py` if needed.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| OpenRouter API | `AsyncOpenAI(base_url="https://openrouter.ai/api/v1")` with `LLM_API_KEY` | OpenAI-compatible. Supports vision via `image_url` content blocks. Supports `response_format` for structured output. |
| Bright Data Scraping Browser | Playwright CDP connection via `BRIGHTDATA_ENDPOINT` | Shared with existing scanner. Same browser session pattern. |
| Kleinanzeigen.de | HTTP via Bright Data proxy | Search pages + individual listing detail pages (new). |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `generic_scanner.py` <-> `scraping.py` | Direct function import | Shared `fetch_page()`, `parse_listings()`. Extracted from `scanner.py`. |
| `generic_scanner.py` <-> `llm_analyzer.py` | Direct function import | `analyze_listing(listing_data) -> AnalysisResult` |
| `scanner.py` <-> `scraping.py` | Direct function import | After extraction, `scanner.py` imports from `scraping.py` instead of defining inline. Minimal change. |
| `web.py` <-> `results/` | Filesystem read | `web.py` reads both `scan_*.json` and `generic_scan_*.json` files. |

## Build Order (Dependencies)

The components have clear dependencies that dictate build order:

```
Phase 1: Extract shared scraping utilities
         scraping.py (extract from scanner.py)
         ├── fetch_page()
         ├── parse_listings()
         └── scanner.py updated to import from scraping.py
         WHY FIRST: Foundation for everything. Low risk. Verifiable immediately.

Phase 2: Generic query generation + search scraping
         generic_scanner.py (query builder + search phase)
         ├── build_generic_queries() from schema.json mislabels
         ├── build_generic_search_url() with 500 EUR cap
         ├── scrape search results using scraping.py
         └── deduplication logic
         WHY SECOND: Can test independently -- produces listing cards. No LLM needed yet.

Phase 3: Detail page scraper
         scraping.py (add detail page function)
         ├── scrape_detail_page(url) -> {full_description, image_urls}
         └── HTML parsing for individual listing pages
         WHY THIRD: Depends on having listing URLs from Phase 2. Testable independently.

Phase 4: LLM analyzer
         llm_analyzer.py
         ├── AsyncOpenAI client setup
         ├── Prompt construction (system + user with image)
         ├── Structured output schema
         ├── analyze_listing() function
         └── Error handling (rate limits, timeouts, malformed responses)
         WHY FOURTH: Depends on enriched listings from Phase 3. Most complex, highest risk.

Phase 5: End-to-end integration + output
         generic_scanner.py (complete pipeline)
         ├── Wire all phases together
         ├── Result aggregation and JSON output
         ├── Progress logging
         └── CLI entry point
         WHY FIFTH: Integration of all prior components.

Phase 6: Dashboard extension (optional)
         web.py + templates
         ├── Read generic_scan_*.json files
         ├── Display LLM analysis fields
         └── Filtering by confidence, is_candidate_valuable
         WHY LAST: Nice-to-have. Results are useful as JSON files without dashboard.
```

## Sources

- [OpenRouter Quickstart](https://openrouter.ai/docs/quickstart) -- API basics, Python integration
- [OpenRouter Image Inputs](https://openrouter.ai/docs/guides/overview/multimodal/images) -- Vision API message format
- [OpenRouter Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs) -- `response_format` with `json_schema`
- [OpenAI Python SDK](https://github.com/openai/openai-python) -- `AsyncOpenAI` client, async patterns
- [OpenRouter Python SDK docs](https://openrouter.ai/docs/sdks/python) -- Native SDK (less mature than OpenAI SDK)
- [Instructor + OpenRouter](https://python.useinstructor.com/integrations/openrouter/) -- Structured output with Pydantic (alternative approach)

---
*Architecture research for: LLM-powered marketplace listing analysis*
*Researched: 2026-03-05*
