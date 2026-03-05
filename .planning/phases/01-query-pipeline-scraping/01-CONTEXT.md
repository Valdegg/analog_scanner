# Phase 1: Query Pipeline & Scraping - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Generate generic search queries from deduplicated mislabels + German terms, search Kleinanzeigen.de with 500 EUR price cap, navigate to each listing's detail page to extract high-res hero image and full description, deduplicate across queries, filter old listings. Output: scraped listing data ready for LLM analysis in Phase 2.

</domain>

<decisions>
## Implementation Decisions

### Detail page scraping
- Extract hero image only (first/main image) — single image per listing
- Download image and encode as base64 in memory — no files saved to disk
- Extract full seller description text from detail page (not just the search result snippet)
- Skip metadata like seller name, category, shipping info — not useful for device identification
- Skip listings with no photos entirely — without an image, identification is too unreliable

### Module structure
- New file: `generic_scanner.py` at project root — matches existing flat module pattern
- Import shared functions directly from `scanner.py` (fetch_page, parse_listings, parse_price, parse_listing_date, is_too_old, etc.)
- No refactoring of scanner.py needed — just import what exists
- Phase 2 LLM analysis will go in a separate `llm_analyzer.py` — plan for clean separation now

### Claude's Discretion
- Query deduplication strategy (how to normalize and deduplicate mislabels)
- German query selection (which additional German terms to include)
- CLI invocation design (args, progress output)
- Intermediate save strategy (save scraped data between queries for resilience)
- Search URL format for generic queries (no min price, 500 EUR max)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches matching existing scanner.py patterns.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scanner.py:fetch_page()` — Connects to Bright Data via CDP, navigates to URL, returns HTML
- `scanner.py:parse_listings()` — Parses search result HTML into list of listing dicts (title, price, URL, image_url, etc.)
- `scanner.py:parse_price()` — Extracts numeric price and VB flag from price strings
- `scanner.py:parse_listing_date()` — Parses German date strings (Heute, Gestern, DD.MM.YYYY)
- `scanner.py:is_too_old()` — Filters listings older than MAX_LISTING_AGE_DAYS
- `scanner.py:load_schema()` — Reads schema.json, returns device list (has common_mislabels per device)
- `scanner.py:build_search_url()` — Builds Kleinanzeigen search URL with price range (needs modification for generic: no min price, 500 EUR max)

### Established Patterns
- Async with `async_playwright` context manager
- Retry loop with MAX_RETRIES and sleep between attempts
- PAUSE_SECONDS between requests to avoid rate limiting
- Progress output via `print(f"[{i+1}/{total}] ...")`
- Results saved as JSON with `json.dump(output, f, indent=2, ensure_ascii=False)`
- Browser session: open in try, close in finally

### Integration Points
- `schema.json` — source of `common_mislabels` per device
- `.env` — BRIGHTDATA_ENDPOINT for Playwright CDP connection
- `results/` directory — output destination (will use `generic_scan_DATE.json` naming)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-query-pipeline-scraping*
*Context gathered: 2026-03-05*
