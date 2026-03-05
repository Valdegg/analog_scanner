# Architecture

**Analysis Date:** 2026-03-05

## Pattern Overview

**Overall:** Pipeline-based scraper with web dashboard -- a data acquisition pipeline that scrapes marketplace listings, scores them against a static schema, persists results as JSON files, and presents them through a Flask web UI.

**Key Characteristics:**
- Flat module structure with no package hierarchy -- all Python modules live at the project root
- Schema-driven scanning: `schema.json` defines what to scan, with market prices, keywords, and scoring thresholds
- Stateless pipeline: each scan run produces an independent JSON file in `results/`; no database
- Two independent entry points: CLI scanner (`scanner.py`) and web dashboard (`web.py`)
- Async scraping via Playwright + Bright Data proxy browser

## Layers

**Data Schema Layer:**
- Purpose: Define the catalog of devices to scan, with market pricing and deal detection rules
- Location: `schema.json`
- Contains: Array of 76 device objects with identity, market pricing, opportunity scores, and search keywords
- Depends on: Nothing (static data, manually maintained)
- Used by: `scanner.py` (loads at scan time)

**Scraping Layer:**
- Purpose: Fetch HTML from Kleinanzeigen.de via Bright Data Scraping Browser (Playwright over CDP)
- Location: `scanner.py` (functions `fetch_page`, `scan_device`)
- Contains: Browser session management, page navigation, retry logic
- Depends on: Bright Data endpoint (env var `BRIGHTDATA_ENDPOINT`), Playwright
- Used by: `scanner.py` main loop

**Parsing & Scoring Layer:**
- Purpose: Extract structured listing data from HTML and classify deals
- Location: `scanner.py` (functions `parse_listings`, `parse_price`, `is_relevant`, `rate_deal`, `calc_profit`)
- Contains: BeautifulSoup HTML parsing, price extraction, relevance filtering, deal rating logic
- Depends on: Schema data (market prices, search keywords)
- Used by: `scan_device` function

**Persistence Layer:**
- Purpose: Store scan results as timestamped JSON files
- Location: `results/` directory, written by `scanner.py` main function
- Contains: JSON files named `scan_YYYY-MM-DD_HHMM.json`
- Depends on: Nothing (filesystem only)
- Used by: `web.py` (reads latest or selected scan file)

**Web Presentation Layer:**
- Purpose: Serve a dashboard UI to browse and filter scan results
- Location: `web.py` (Flask app), `templates/index.html` (Jinja2 template)
- Contains: Two routes (HTML dashboard + JSON API), scan file selector, client-side filtering/sorting
- Depends on: `results/` directory (reads JSON scan files)
- Used by: End user via browser

**Songkick Events Module (separate/unrelated):**
- Purpose: Scrape Songkick event listings for city cultural scoring (appears to be from a different project)
- Location: `songkick_events.py`
- Contains: BrightData-based event scraping, scoring logic, pandas data processing
- Depends on: `BRIGHTDATA_ENDPOINT`, `BRIGHTDATA_AUTH` env vars
- Used by: Not integrated with the main scanner pipeline

## Data Flow

**Scan Pipeline:**

1. `scanner.py` loads device catalog from `schema.json` via `load_schema()`
2. For each device, builds a Kleinanzeigen.de search URL with price range filters from market data
3. Connects to Bright Data Scraping Browser via Playwright CDP, navigates to search URL, captures HTML
4. Parses HTML with BeautifulSoup to extract listing cards (title, price, VB flag, location, date, image)
5. Filters out irrelevant listings (title mismatch) and old listings (>365 days)
6. Rates each listing as `steal`, `good_deal`, `market_price`, or `above_market` based on price vs schema thresholds
7. Calculates estimated profit per listing
8. Aggregates all device results into a single JSON output saved to `results/scan_DATE.json`

**Web Dashboard:**

1. `web.py` reads the most recent (or user-selected) scan JSON from `results/`
2. Passes full scan data to Jinja2 template `templates/index.html`
3. Template renders two views: "Best Deals" (flat sorted list) and "By Device" (grouped by category/device)
4. Client-side JavaScript handles filtering (price range, age), sorting (profit, discount, price), and tab switching

**State Management:**
- No persistent state beyond filesystem JSON files
- No user sessions or authentication
- All filtering/sorting happens client-side in the browser

## Key Abstractions

**Device Schema:**
- Purpose: Represents a scannable vintage music device with market pricing data
- Examples: Each object in `schema.json` `devices` array
- Pattern: Static JSON configuration with nested `market`, `deal_detection`, `opportunity_scores` sections

**Listing:**
- Purpose: A single marketplace listing extracted from HTML
- Examples: Dicts returned by `parse_listings()` in `scanner.py`
- Pattern: Dictionary with keys: `title`, `price_eur`, `is_vb`, `original_price_eur`, `description`, `location`, `date`, `url`, `image_url`, `deal_rating`, `est_profit_eur`

**Deal Rating:**
- Purpose: Classifies a listing's value relative to market price
- Examples: `"steal"`, `"good_deal"`, `"market_price"`, `"above_market"`
- Pattern: Threshold-based classification in `rate_deal()` using schema-defined price tiers. VB (Verhandlungsbasis/negotiable) listings get a 15% discount applied before comparison.

**Scan Result:**
- Purpose: Complete output of one scan run
- Examples: Files in `results/scan_*.json`
- Pattern: Top-level envelope with `scan_date`, `total_devices_searched`, `total_listings_found`, and `results` array of per-device results

## Entry Points

**Scanner CLI (`scanner.py`):**
- Location: `scanner.py`
- Triggers: `python scanner.py [limit]` -- optional integer arg limits number of devices scanned
- Responsibilities: Load schema, iterate devices, scrape Kleinanzeigen, parse/score listings, save JSON output
- Requires: `BRIGHTDATA_ENDPOINT` env var set in `.env`

**Web Dashboard (`web.py`):**
- Location: `web.py`
- Triggers: `python web.py` starts Flask dev server on port 5001
- Responsibilities: Serve dashboard at `/`, provide JSON API at `/api/scan`
- Routes:
  - `GET /` -- HTML dashboard, accepts `?scan=filename` query param
  - `GET /api/scan` -- JSON endpoint, accepts `?file=filename` query param

**Songkick Events (`songkick_events.py`):**
- Location: `songkick_events.py`
- Triggers: `python songkick_events.py [--debug] [--local]`
- Responsibilities: Scrape Songkick metro area events, compute cultural scores
- Note: Appears to be from a different project context; not integrated with the deal scanner

## Error Handling

**Strategy:** Minimal -- retry with backoff for network failures, print to stdout, continue on error

**Patterns:**
- Network/browser errors in `fetch_page()`: retry up to `MAX_RETRIES` (3) with 5-second sleep between attempts
- Price parsing: returns `(None, False)` on unparseable prices via try/except ValueError
- Date parsing: returns `None` on unparseable dates, which causes `is_too_old()` to return False (keep the listing)
- Missing scan files in `web.py`: returns empty result dict with zero counts
- No structured error logging or error aggregation

## Cross-Cutting Concerns

**Logging:** Print statements to stdout only. No logging framework used in `scanner.py`. `songkick_events.py` uses Python `logging` module but is a separate concern.

**Validation:** No input validation on schema.json. No validation on scan result integrity. Price/date parsing silently handles malformed data.

**Authentication:** None. Web dashboard has no auth. Bright Data authentication is via the CDP endpoint URL (contains credentials).

**Configuration:** Environment variables loaded from `.env` via `python-dotenv`. Constants defined at module top level (`PAUSE_SECONDS`, `MAX_RETRIES`, `NAV_TIMEOUT_MS`, `VB_DISCOUNT`, `MAX_LISTING_AGE_DAYS`).

---

*Architecture analysis: 2026-03-05*
