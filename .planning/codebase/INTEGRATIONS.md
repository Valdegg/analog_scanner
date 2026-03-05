# External Integrations

**Analysis Date:** 2026-03-05

## APIs & External Services

**Web Scraping Proxy:**
- Bright Data Scraping Browser - Anti-detection browser proxy for scraping JS-heavy sites
  - SDK/Client: Playwright connects via CDP (Chrome DevTools Protocol) over WebSocket
  - Auth: `BRIGHTDATA_ENDPOINT` env var (WebSocket URL with embedded credentials)
  - Additional auth: `BRIGHTDATA_AUTH` env var (extracted or provided separately)
  - Connection pattern: `pw.chromium.connect_over_cdp(endpoint)` in `scanner.py` line 171
  - Endpoint format: `wss://{AUTH}@brd.superproxy.io:9222` (constructed in `songkick_events.py` line 58)

**Scraped Data Sources:**

- **Kleinanzeigen.de** - German classifieds marketplace (primary deal scanner target)
  - Base URL: `https://www.kleinanzeigen.de`
  - Used in: `scanner.py`
  - Purpose: Find underpriced analog synth/audio equipment listings
  - Search URL pattern: `/s-preis:{min}:{max}/{keyword}/k0`
  - Rate limiting: 2-second pause between devices, 3-second page load wait, max 3 retries with 5s backoff

- **Songkick** - Concert/event listings
  - Base URL: `https://www.songkick.com/metro-areas/[city]`
  - Used in: `songkick_events.py`
  - Purpose: Cultural scene scoring based on event density and genre alignment
  - Separate integration, appears to be from a different project context

**Price References (informational, not scraped):**
- Reverb.com - Market price references stored in `schema.json`
- eBay.de - Sold listing price references stored in `schema.json`

## Data Storage

**Databases:**
- None - all data stored as flat JSON files

**File Storage:**
- Local filesystem only
  - Scan results: `results/scan_YYYY-MM-DD_HHMM.json`
  - Device catalog: `schema.json` (hand-maintained)
  - Results loaded by Flask dashboard from `results/` directory

**Caching:**
- None - each scan run fetches fresh data

## Authentication & Identity

**Auth Provider:**
- None - no user authentication on the Flask dashboard
- Dashboard is open/unauthenticated on localhost

## Monitoring & Observability

**Error Tracking:**
- None - errors printed to stdout via `print()` in `scanner.py`
- Python `logging` module used in `songkick_events.py` but no configured handlers

**Logs:**
- Console output only (`print()` statements in `scanner.py`)
- `logging.getLogger(__name__)` in `songkick_events.py`

## CI/CD & Deployment

**Hosting:**
- Local development only - Flask dev server on port 5001
- No deployment configuration detected

**CI Pipeline:**
- None - no CI/CD configuration files present

## Environment Configuration

**Required env vars:**
- `BRIGHTDATA_ENDPOINT` - WebSocket URL for Bright Data Scraping Browser (required for `scanner.py`)
- `BRIGHTDATA_AUTH` - Bright Data authentication string (used by `songkick_events.py`, can be extracted from endpoint)

**Secrets location:**
- `.env` file at project root (loaded by `python-dotenv`)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## API Endpoints (Internal Flask Dashboard)

**`GET /`** - Main dashboard page
- Query param: `?scan=filename` to view a specific scan
- Returns: Rendered HTML template with scan results
- File: `web.py` line 30

**`GET /api/scan`** - JSON API for scan data
- Query param: `?file=filename` to fetch specific scan
- Returns: JSON scan data
- File: `web.py` line 42

---

*Integration audit: 2026-03-05*
