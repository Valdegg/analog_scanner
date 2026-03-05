# Coding Conventions

**Analysis Date:** 2026-03-05

## Naming Patterns

**Files:**
- Use `snake_case.py` for all Python modules: `scanner.py`, `web.py`, `songkick_events.py`
- Single HTML template: `templates/index.html`
- Data schema: `schema.json`

**Functions:**
- Use `snake_case` for all functions: `parse_price()`, `build_search_url()`, `rate_deal()`
- Async functions use the same naming: `fetch_page()`, `scan_device()`
- Prefix boolean-returning functions with `is_`: `is_relevant()`, `is_too_old()`
- Use verb-first naming: `load_schema()`, `parse_listings()`, `calc_profit()`

**Variables:**
- Use `snake_case` for all variables: `price_eur`, `is_vb`, `filtered_count`
- Use `UPPER_SNAKE_CASE` for module-level constants: `BASE_URL`, `PAUSE_SECONDS`, `MAX_RETRIES`, `NAV_TIMEOUT_MS`
- Short loop variables are acceptable: `l`, `d`, `i`, `t`

**Types:**
- Use Python 3.10+ union syntax: `float | None`, `str | None`
- Use `typing` module types in `songkick_events.py`: `List`, `Dict`, `Optional` (older style, inconsistent with `scanner.py`)
- Prefer built-in generics in new code: `list[dict]`, `tuple[float | None, bool]`

## Code Style

**Formatting:**
- No formatter configuration detected (no `pyproject.toml`, `.flake8`, `setup.cfg`)
- Indentation: 4 spaces (standard Python)
- Max line length: approximately 120 characters (no strict enforcement)
- String quotes: double quotes `"` preferred for strings throughout

**Linting:**
- No linting configuration detected
- No type checker configured (no mypy, pyright)

**Type Hints:**
- Use type hints on function signatures: `def normalize(text: str) -> str:`
- Use return type annotations consistently: `-> str`, `-> bool`, `-> list[dict]`, `-> dict`
- `scanner.py` uses modern union syntax (`float | None`); `songkick_events.py` uses `Optional[str]`
- **Prescriptive:** Use modern union syntax (`X | None`) for new code, matching `scanner.py` style

## Import Organization

**Order:**
1. Standard library (`asyncio`, `json`, `os`, `re`, `sys`, `time`)
2. Third-party packages (`bs4`, `dotenv`, `flask`, `playwright`, `pandas`)
3. No internal/relative imports (flat module structure)

**Style:**
- One import per line for standard library
- Group `from` imports from the same package: `from flask import Flask, render_template, jsonify, request`
- `load_dotenv()` called immediately after imports at module level

**Example from `scanner.py`:**
```python
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv(override=True)
```

## Error Handling

**Patterns:**

1. **Try/except with retry loops** (primary pattern for network operations):
```python
for attempt in range(1, MAX_RETRIES + 1):
    try:
        html = await fetch_page(pw, endpoint, search_url)
        break
    except Exception as e:
        if attempt == MAX_RETRIES:
            print(f"  FAILED after {MAX_RETRIES} attempts: {e}")
        else:
            print(f"  Retry {attempt}/{MAX_RETRIES} for {keyword}: {e}")
            await asyncio.sleep(5)
```

2. **Silent fallback for parsing failures** -- return `None` or safe default:
```python
try:
    return float(cleaned), is_vb
except ValueError:
    return None, is_vb
```

3. **Broad exception catching** -- `except Exception as e` used everywhere, never specific exception types

4. **`songkick_events.py` uses logging + re-raise** for critical failures:
```python
except Exception as e:
    logger.error(f"Error saving events data: {e}")
    raise
```

5. **Environment validation at startup** -- check required env vars and `sys.exit(1)`:
```python
endpoint = os.getenv("BRIGHTDATA_ENDPOINT")
if not endpoint:
    print("Error: BRIGHTDATA_ENDPOINT not set in .env")
    sys.exit(1)
```

**Prescriptive rules:**
- Use broad `except Exception` for scraping/network code (external HTML can fail unpredictably)
- Return `None` for unparseable data rather than raising
- Validate required env vars early in `main()` and exit with a clear message
- Log errors with `logger.error()` in library-style code (`songkick_events.py`); use `print()` in script-style code (`scanner.py`)

## Logging

**Framework:** Mixed -- `print()` in `scanner.py` and `web.py`, `logging` module in `songkick_events.py`

**Patterns:**
- `scanner.py`: Uses `print()` with progress indicators like `[1/10]` prefix
- `songkick_events.py`: Uses `logging.getLogger(__name__)` with emoji prefixes in messages
- Log levels used: `logger.info()`, `logger.warning()`, `logger.error()`
- Logging configured at `__main__` block: `logging.basicConfig(level=logging.INFO)`

**Prescriptive:** For new modules, use `logging.getLogger(__name__)`. Reserve `print()` for CLI output only.

## Comments

**When to Comment:**
- Module-level docstrings describe the script's purpose (both `scanner.py` and `songkick_events.py` have them)
- Function docstrings on most public functions, using triple-quote format
- Inline comments for non-obvious logic steps

**Docstring Style:**
- `scanner.py`: Single-line docstrings for simple functions
- `songkick_events.py`: Google-style docstrings with `Args:` and `Returns:` sections

**Example (simple, from `scanner.py`):**
```python
def normalize(text: str) -> str:
    """Strip all non-alphanumeric chars and lowercase for fuzzy comparison."""
```

**Example (detailed, from `songkick_events.py`):**
```python
async def build_songkick_url(city: str, start_date: datetime, end_date: datetime, genre: Optional[str] = None) -> str:
    """
    Build Songkick search URL with proper parameters

    Args:
        city: City name to search events for
        start_date: Start date for event search
        end_date: End date for event search
        genre: Optional genre filter (e.g., 'hip-hop', 'electronic')

    Returns:
        str: Formatted Songkick search URL
    """
```

**Prescriptive:** Use Google-style docstrings with `Args:` / `Returns:` for functions with multiple parameters. Single-line docstrings are acceptable for simple utility functions.

## Function Design

**Size:**
- Most functions are 5-30 lines
- `fetch_songkick_events_brightdata()` is the largest at ~250 lines (should be split)
- `main()` functions are 50-150 lines

**Parameters:**
- Use keyword arguments with type hints
- Default values for optional parameters: `path: str = "schema.json"`, `max_retries: int = 1`
- Use `dict` for complex nested data (no dataclasses or Pydantic models)

**Return Values:**
- Return `dict` for structured data
- Return `None` for "not found" / parse failures
- Return `tuple` for multiple values: `tuple[float | None, bool]`
- Return `bool` for check functions

## Module Design

**Exports:**
- No `__all__` defined in any module
- Each `.py` file is a standalone script with `if __name__ == "__main__":` block
- Functions are importable but modules are designed as scripts

**Barrel Files:**
- Not used (flat structure, no packages)

## Data Structures

**Primary data format:** Plain `dict` and `list[dict]` -- no dataclasses, NamedTuples, or Pydantic models

**JSON I/O pattern:**
```python
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
# ... and ...
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
```

**Prescriptive:** Always use `encoding="utf-8"` with `open()`. Use `ensure_ascii=False` when writing JSON (German/Unicode content). Use `indent=2` for human-readable output.

## Async Patterns

**Framework:** `asyncio` with Playwright async API

**Entry point pattern:**
```python
if __name__ == "__main__":
    asyncio.run(main())
```

**Concurrency control:** `asyncio.Semaphore` for limiting parallel requests (see `songkick_events.py`)

**Browser session pattern:** Open browser, do work in `try`, close in `finally`:
```python
browser = await pw.chromium.connect_over_cdp(endpoint)
try:
    page = await browser.new_page()
    # ... work ...
finally:
    await browser.close()
```

---

*Convention analysis: 2026-03-05*
