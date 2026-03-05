# Technology Stack

**Analysis Date:** 2026-03-05

## Languages

**Primary:**
- Python 3.12+ - All application code (type hints use `X | Y` union syntax requiring 3.10+)

**Secondary:**
- HTML/CSS/Jinja2 - Dashboard template (`templates/index.html`)
- JSON - Schema definitions and scan result storage

## Runtime

**Environment:**
- Python (CPython) - no version pinned via `.python-version`
- Async event loop via `asyncio` for browser automation

**Package Manager:**
- pip
- Lockfile: missing (only `requirements.txt` with unpinned dependencies)

## Frameworks

**Core:**
- Flask - Web dashboard server (`web.py`)
- Playwright (async API) - Browser automation for scraping (`scanner.py`, `songkick_events.py`)
- BeautifulSoup4 + lxml - HTML parsing of scraped pages

**Testing:**
- Not detected - no test framework in `requirements.txt` or test files present

**Build/Dev:**
- No build tooling - pure Python scripts, run directly

## Key Dependencies

**Critical (from `requirements.txt`):**
- `playwright` - Headless browser automation connecting to Bright Data Scraping Browser via CDP
- `beautifulsoup4` - HTML parsing of Kleinanzeigen.de and Songkick listing pages
- `lxml` - Fast HTML/XML parser backend for BeautifulSoup
- `flask` - Lightweight web framework for the dashboard UI
- `python-dotenv` - Loads `.env` file for secrets (Bright Data credentials)

**Additional (imported in `songkick_events.py` but not in `requirements.txt`):**
- `pandas` - Data manipulation for Songkick events processing

## Configuration

**Environment:**
- `.env` file present at project root - loaded via `python-dotenv` with `override=True`
- Key env vars: `BRIGHTDATA_ENDPOINT`, `BRIGHTDATA_AUTH`
- Never read `.env` contents directly - existence noted only

**Build:**
- No build configuration - scripts run directly with `python scanner.py` and `python web.py`

**Schema:**
- `schema.json` - Device catalog with market prices, search keywords, and deal thresholds (schema version 1.0)
- `SCHEMA.md` - Schema documentation

## Platform Requirements

**Development:**
- Python 3.10+ (union type syntax `X | Y` used throughout)
- Playwright browsers installed (`playwright install chromium`)
- Bright Data Scraping Browser account with WebSocket endpoint

**Production:**
- Flask dev server on port 5001 (`web.py` runs `app.run(debug=True, port=5001)`)
- No production WSGI/ASGI server configured
- `results/` directory for JSON scan output (created automatically)

---

*Stack analysis: 2026-03-05*
