# Codebase Concerns

**Analysis Date:** 2026-03-05

## Tech Debt

**No test suite exists:**
- Issue: Zero test files in the entire project. No test framework configured, no test command in `requirements.txt`.
- Files: All source files (`scanner.py`, `web.py`, `songkick_events.py`)
- Impact: Any change to parsing logic, price calculations, or deal rating can silently break without detection. The `parse_price`, `rate_deal`, `parse_listing_date`, and `is_relevant` functions are all pure functions that are trivially testable but untested.
- Fix approach: Add `pytest` to `requirements.txt`. Write unit tests for all pure functions in `scanner.py` (there are at least 7). Add integration tests for `parse_listings` with sample HTML fixtures.

**No `.gitignore` file:**
- Issue: Project has no `.gitignore`. The `.env` file containing `BRIGHTDATA_ENDPOINT` and `BRIGHTDATA_AUTH` secrets is unprotected from accidental commits. The `results/` directory with scan JSON files could also bloat the repo.
- Files: Project root (missing `.gitignore`)
- Impact: Secrets could be committed to version control. Result files accumulate in repo.
- Fix approach: Create `.gitignore` with entries for `.env`, `results/`, `__pycache__/`, `*.pyc`, `data/debug_html/`.

**`songkick_events.py` appears to be from a different project:**
- Issue: This 1026-line file references a completely different data directory structure (`../data/sources/`, `../data/production/cities.csv`), uses `pandas`, and has its own BrightData configuration pattern. It seems transplanted from another project and shares no code with `scanner.py` or `web.py`.
- Files: `songkick_events.py`
- Impact: Confusing project scope. The file imports `pandas` which is not in `requirements.txt`, so it would fail on a fresh install. Dead code if not actively used.
- Fix approach: Either remove it or document its purpose and add `pandas` to `requirements.txt`. If it belongs to another project, move it there.

**No dependency pinning:**
- Issue: `requirements.txt` lists packages without version pins (`playwright`, `beautifulsoup4`, `python-dotenv`, `lxml`, `flask`). No lockfile exists.
- Files: `requirements.txt`
- Impact: Builds are not reproducible. A breaking change in any dependency could silently break the scanner.
- Fix approach: Pin all dependencies to specific versions (e.g., `flask==3.1.0`). Consider using `pip freeze > requirements.txt` or switching to `pyproject.toml` with `pip-tools`.

**Monolithic HTML template:**
- Issue: `templates/index.html` is a 903-line single file containing all CSS, HTML, and JavaScript. No separation of concerns.
- Files: `templates/index.html`
- Impact: Difficult to maintain or extend the dashboard. All styling, structure, and interactivity in one file.
- Fix approach: For a project this size, this is acceptable but should be split if the dashboard grows. Extract CSS to a static file and JS to a separate file.

## Security Considerations

**Path traversal in `load_scan`:**
- Risk: The `load_scan` function in `web.py` accepts a `filename` parameter directly from the query string (`request.args.get("scan")`) and joins it with `RESULTS_DIR` without any sanitization.
- Files: `web.py` (lines 11-21)
- Current mitigation: None. An attacker could pass `../../etc/passwd` or similar paths.
- Recommendations: Validate that the filename matches the expected pattern (`scan_*.json`), use `Path.resolve()` to check the resolved path stays within `RESULTS_DIR`, or reject filenames containing `..` or `/`.

**Flask debug mode enabled in production:**
- Risk: `app.run(debug=True)` is hardcoded at `web.py` line 48. Debug mode exposes the Werkzeug debugger which allows arbitrary code execution.
- Files: `web.py` (line 48)
- Current mitigation: None.
- Recommendations: Use an environment variable to control debug mode: `app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")`. For production, use a WSGI server like gunicorn.

**`.env` file not git-ignored:**
- Risk: No `.gitignore` exists, so `.env` containing `BRIGHTDATA_ENDPOINT` and `BRIGHTDATA_AUTH` credentials could be committed.
- Files: `.env` (exists in project root)
- Current mitigation: None.
- Recommendations: Create `.gitignore` immediately with `.env` entry. Audit git history for any previously committed secrets.

**API endpoint has no authentication:**
- Risk: The `/api/scan` endpoint in `web.py` serves scan data with no authentication or rate limiting.
- Files: `web.py` (lines 41-44)
- Current mitigation: Likely only run locally.
- Recommendations: If exposed publicly, add basic auth or API key middleware.

## Performance Bottlenecks

**Sequential device scanning:**
- Problem: `scanner.py` scans devices one at a time in a serial loop with a 2-second pause between each plus a 3-second wait per page load.
- Files: `scanner.py` (lines 262-283, line 175)
- Cause: Each device requires a separate Bright Data browser session. The `PAUSE_SECONDS = 2` delay and `page.wait_for_timeout(3000)` add ~5 seconds per device minimum.
- Improvement path: Use `asyncio.Semaphore` for concurrent scanning (similar to how `songkick_events.py` does it with `process_city_with_semaphore`). Even 3-5 concurrent connections would significantly reduce total scan time.

**New browser connection per page fetch:**
- Problem: `fetch_page` creates and closes a new browser connection via CDP for every single page request.
- Files: `scanner.py` (lines 169-178)
- Cause: Each call to `pw.chromium.connect_over_cdp(endpoint)` establishes a new WebSocket connection to Bright Data.
- Improvement path: Reuse browser connections across multiple page fetches. Open one connection and create multiple pages, or use a connection pool.

**Full page content loaded for every scan:**
- Problem: The scanner loads full page content including images and tracking scripts, then waits a fixed 3 seconds regardless of whether content is ready.
- Files: `scanner.py` (line 175)
- Cause: No resource blocking and a fixed timeout instead of waiting for specific selectors.
- Improvement path: Block unnecessary resources (images, ads, analytics) like `songkick_events.py` does (lines 325-332). Wait for the specific content selector (`article.aditem`) instead of a fixed 3-second delay.

## Fragile Areas

**HTML selector-based scraping:**
- Files: `scanner.py` (lines 110-160), `songkick_events.py` (lines 388-495)
- Why fragile: Both scrapers depend on specific CSS class names from Kleinanzeigen.de and Songkick.com (`article.aditem`, `.aditem-main--middle--price-shipping--price`, `.artists-venue-location-wrapper`). Any site redesign breaks the parser silently -- it returns 0 results instead of raising an error.
- Safe modification: When updating selectors, save sample HTML fixtures for regression testing. Add assertions that validate expected page structure before parsing.
- Test coverage: None. There are no tests for `parse_listings` or the Songkick event extraction.

**Price parsing logic:**
- Files: `scanner.py` (lines 55-65)
- Why fragile: `parse_price` handles German number formatting (`.` as thousands separator, `,` as decimal) by replacing all dots and commas. This could misparse edge cases like prices without thousands separators or unusual formatting.
- Safe modification: Add unit tests with various price string formats before changing.
- Test coverage: None.

**Date parsing for German locale:**
- Files: `scanner.py` (lines 68-80)
- Why fragile: `parse_listing_date` handles "Heute" (today) and "Gestern" (yesterday) as special cases, then falls back to `%d.%m.%Y`. If Kleinanzeigen adds other relative date formats (e.g., "Vor 2 Tagen"), they will be silently ignored (returns `None`, which means `is_too_old` returns `False` -- keeping potentially old listings).
- Safe modification: Add a catch-all log warning when date parsing fails for non-empty strings.
- Test coverage: None.

## Scaling Limits

**Scan results stored as individual JSON files:**
- Current capacity: Each scan generates a separate `results/scan_DATE.json` file. With daily scans, this produces ~365 files/year.
- Limit: Filesystem can handle this, but `list_scans()` does a glob and sorts all files on every page load. No cleanup mechanism exists.
- Scaling path: Add a scan retention policy (delete scans older than N days). For higher frequency scanning, consider SQLite or a proper database.

**Schema hardcoded in single JSON file:**
- Current capacity: `schema.json` contains all device definitions. Currently manageable but already large (34K+ tokens).
- Limit: Adding more devices makes the file unwieldy and increases scan time linearly.
- Scaling path: Split into per-category schema files or move to a database. Add ability to enable/disable devices without removing them.

## Dependencies at Risk

**Bright Data Scraping Browser:**
- Risk: The entire scanning capability depends on Bright Data's scraping browser service. If the service changes its API, pricing, or goes down, scanning stops completely.
- Impact: Both `scanner.py` and `songkick_events.py` are non-functional without it (unless using `--local` flag in songkick_events.py).
- Migration plan: `scanner.py` has no local browser fallback. Add a `--local` flag similar to `songkick_events.py` for development and testing without Bright Data.

**Kleinanzeigen.de page structure:**
- Risk: Scraping depends on the exact HTML structure of Kleinanzeigen.de search results. Site redesigns happen without notice.
- Impact: Silent failure -- returns empty results instead of errors.
- Migration plan: Add structural validation (assert expected elements exist on page). Consider Kleinanzeigen API if available. Log warnings when zero results are found for devices that historically had listings.

## Missing Critical Features

**No alerting/notification system:**
- Problem: The scanner runs manually and writes results to JSON files. There is no way to be notified when a "steal" or "good_deal" appears.
- Blocks: Real-time deal hunting. Users must manually run scans and check the dashboard.

**No scheduled/automated scanning:**
- Problem: No cron job, task scheduler, or daemon mode. Scans must be triggered manually via `python scanner.py`.
- Blocks: Continuous monitoring of the market.

**No error reporting or monitoring:**
- Problem: Errors are printed to stdout and lost. No persistent error logging, no tracking of scan success rates over time.
- Blocks: Understanding reliability of scans, diagnosing intermittent Bright Data failures.

**No data validation on schema.json:**
- Problem: `load_schema` does a raw `json.load` with no validation. If `schema.json` has a missing field (e.g., no `steal_price_eur`), the error surfaces deep in the scanning loop as a `KeyError`.
- Blocks: Safe schema editing. Contributors could easily introduce invalid entries.

## Test Coverage Gaps

**All application code is untested:**
- What's not tested: Every function in `scanner.py`, `web.py`, and `songkick_events.py`.
- Files: `scanner.py`, `web.py`, `songkick_events.py`
- Risk: Price parsing, deal rating, relevance filtering, date parsing, and profit calculation could all contain bugs that go undetected. The VB discount calculation (`price * 0.85`) applied to deal rating but also to profit estimation could produce incorrect results without anyone noticing.
- Priority: High -- the core value proposition (accurate deal detection) depends on these calculations being correct.

**Specific high-risk untested functions:**
- `parse_price` in `scanner.py`: Handles German price formatting -- edge cases likely exist
- `rate_deal` in `scanner.py`: Core deal classification logic
- `is_relevant` in `scanner.py`: Determines which listings are shown -- false negatives mean missed deals
- `calc_profit` in `scanner.py`: Financial calculation shown to users
- `parse_listings` in `scanner.py`: HTML parsing that could silently return incomplete data
- `load_scan` in `web.py`: File loading with path traversal risk
- Priority: High

---

*Concerns audit: 2026-03-05*
