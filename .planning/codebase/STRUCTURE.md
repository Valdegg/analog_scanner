# Codebase Structure

**Analysis Date:** 2026-03-05

## Directory Layout

```
analog_scanner/
├── scanner.py          # Main scraping pipeline (CLI entry point)
├── web.py              # Flask web dashboard (web entry point)
├── songkick_events.py  # Songkick event scraper (separate/unrelated module)
├── schema.json         # Device catalog with market data (large, ~76 devices)
├── SCHEMA.md           # Documentation for schema.json format
├── README.md           # Project readme
├── requirements.txt    # Python dependencies
├── .env                # Environment config (secrets, not committed)
├── results/            # Scan output JSON files (generated)
│   └── scan_*.json     # Timestamped scan results
└── templates/          # Flask/Jinja2 HTML templates
    └── index.html      # Dashboard single-page template (900 lines, CSS+HTML+JS)
```

## Directory Purposes

**`results/`:**
- Purpose: Stores output from each scan run
- Contains: JSON files named `scan_YYYY-MM-DD_HHMM.json`
- Key files: Most recent `scan_*.json` is auto-loaded by dashboard
- Generated: Yes, by `scanner.py`
- Committed: Contains scan data files; may or may not be committed

**`templates/`:**
- Purpose: Flask Jinja2 templates for the web dashboard
- Contains: Single template `index.html` that is a self-contained SPA (inline CSS + JS)
- Key files: `templates/index.html`

## Key File Locations

**Entry Points:**
- `scanner.py`: CLI scanner -- run with `python scanner.py [limit]`
- `web.py`: Web dashboard -- run with `python web.py` (serves on port 5001)

**Configuration:**
- `schema.json`: Device catalog defining what to scan and price thresholds
- `.env`: Environment variables (Bright Data credentials)
- `requirements.txt`: Python package dependencies

**Core Logic:**
- `scanner.py`: All scraping, parsing, scoring, and output logic
- `web.py`: Dashboard server with scan file loading

**Presentation:**
- `templates/index.html`: Full dashboard UI with two views (Best Deals, By Device), filtering, sorting

**Documentation:**
- `SCHEMA.md`: Explains schema.json structure and scoring methodology
- `README.md`: Project overview

**Unrelated/Legacy:**
- `songkick_events.py`: Songkick event scraper from a different project context

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `scanner.py`, `web.py`, `songkick_events.py`)
- Config/data: lowercase with extension (e.g., `schema.json`, `requirements.txt`)
- Documentation: UPPERCASE.md (e.g., `SCHEMA.md`, `README.md`)
- Scan outputs: `scan_YYYY-MM-DD_HHMM.json`

**Functions (Python):**
- `snake_case` for all functions (e.g., `build_search_url`, `parse_listings`, `rate_deal`, `calc_profit`)
- Prefixes: `parse_*` for extraction, `is_*` for boolean checks, `load_*` for file reading, `build_*` for URL construction

**Variables (Python):**
- Constants: `UPPER_SNAKE_CASE` (e.g., `BASE_URL`, `MAX_RETRIES`, `NAV_TIMEOUT_MS`, `VB_DISCOUNT`)
- Local variables: `snake_case`

**CSS/HTML:**
- CSS classes: `kebab-case` (e.g., `device-header`, `listing-price`, `badge-steal`)
- CSS variables: `--kebab-case` (e.g., `--neon-pink`, `--steal-glow`)
- JavaScript: `camelCase` for functions and variables (e.g., `applyFilters`, `applySorting`, `parseDDMMYYYY`)

## Where to Add New Code

**New scraping target / marketplace:**
- Add a new Python module at root: e.g., `marktplaats_scanner.py`
- Follow the pattern in `scanner.py`: async main, `fetch_page`, `parse_listings`, `scan_device`
- Reuse `schema.json` for device definitions

**New deal scoring logic:**
- Modify `scanner.py` functions: `rate_deal()`, `calc_profit()`, `is_relevant()`
- Update rating thresholds or add new rating tiers

**New dashboard view or feature:**
- Edit `templates/index.html` -- add new tab div, new view section, corresponding JS
- For new API endpoints, add routes in `web.py`

**New device to scan:**
- Add entry to `schema.json` `devices` array following the schema documented in `SCHEMA.md`

**Utilities/shared code:**
- Currently no shared utility module exists. If extracting shared logic (e.g., Bright Data connection, price parsing), create a `utils.py` or `brightdata.py` at root level.

**Tests:**
- No test directory or test files exist currently. Create `tests/` directory at root with `test_scanner.py`, `test_web.py`, etc.

## Special Directories

**`results/`:**
- Purpose: Generated scan output storage
- Generated: Yes, created by `scanner.py` (`output_dir.mkdir(exist_ok=True)`)
- Committed: Contains data files; gitignore status unknown

**`.planning/`:**
- Purpose: Project planning and codebase analysis documents
- Generated: By tooling
- Committed: Typically yes

**`.claude/`:**
- Purpose: Claude Code configuration, commands, and GSD workflow tooling
- Generated: By Claude Code setup
- Committed: Typically yes

---

*Structure analysis: 2026-03-05*
