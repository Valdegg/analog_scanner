# Testing Patterns

**Analysis Date:** 2026-03-05

## Test Framework

**Runner:**
- No test framework detected
- No test configuration files found (`pytest.ini`, `pyproject.toml`, `setup.cfg`, `tox.ini`)
- No test runner in `requirements.txt`

**Assertion Library:**
- Not applicable (no tests exist)

**Run Commands:**
```bash
# No test commands configured
# Recommended setup:
pip install pytest pytest-asyncio
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest --cov=.            # Coverage (requires pytest-cov)
```

## Test File Organization

**Location:**
- No test files exist anywhere in the codebase
- No `tests/` directory, no `test_*.py` files, no `*_test.py` files, no `conftest.py`

**Recommended structure for new tests:**
```
analog_scanner/
├── tests/
│   ├── conftest.py           # Shared fixtures
│   ├── test_scanner.py       # Tests for scanner.py
│   ├── test_web.py           # Tests for web.py
│   └── test_songkick.py      # Tests for songkick_events.py
```

**Recommended naming:**
- `test_<module>.py` for test files
- `test_<function_name>` for test functions
- `Test<ClassName>` for test classes (if grouping)

## Test Structure

**No existing tests to reference. Recommended patterns based on codebase analysis:**

**Suite Organization:**
```python
# tests/test_scanner.py
import pytest
from scanner import normalize, parse_price, rate_deal, is_relevant, parse_listing_date, parse_listings


class TestNormalize:
    def test_strips_punctuation(self):
        assert normalize("JX-3P") == "jx3p"

    def test_lowercases(self):
        assert normalize("Roland JX") == "rolandjx"

    def test_empty_string(self):
        assert normalize("") == ""


class TestParsePrice:
    def test_simple_price(self):
        price, is_vb = parse_price("500 €")
        assert price == 500.0
        assert is_vb is False

    def test_vb_price(self):
        price, is_vb = parse_price("1.199 € VB")
        assert price == 1199.0
        assert is_vb is True

    def test_empty_string(self):
        price, is_vb = parse_price("")
        assert price is None
        assert is_vb is False

    def test_none_input(self):
        price, is_vb = parse_price(None)
        assert price is None
        assert is_vb is False
```

## Mocking

**Framework:** Not configured. Recommend `unittest.mock` (stdlib) or `pytest-mock`.

**What to mock:**
- Playwright browser connections (`pw.chromium.connect_over_cdp`)
- External HTTP requests (Bright Data scraping browser)
- File system reads/writes for `load_schema()`, `load_scan()`
- Environment variables (`os.getenv`)

**What NOT to mock:**
- Pure functions: `normalize()`, `parse_price()`, `rate_deal()`, `calc_profit()`, `is_relevant()`, `build_search_url()`
- HTML parsing: `parse_listings()` -- feed it real HTML fixtures instead

**Recommended mocking pattern:**
```python
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_fetch_page_retries_on_failure():
    with patch("scanner.async_playwright") as mock_pw:
        mock_browser = AsyncMock()
        mock_browser.new_page.return_value.content.side_effect = [
            Exception("timeout"),
            "<html>success</html>"
        ]
        mock_pw.return_value.__aenter__.return_value.chromium.connect_over_cdp.return_value = mock_browser
        # ... test retry logic
```

## Fixtures and Factories

**Test Data:**

The codebase has natural test data sources:
- `schema.json` contains real device definitions usable as fixtures
- `results/scan_*.json` files contain real scan output for integration test data

**Recommended fixtures:**
```python
# tests/conftest.py
import pytest
import json

@pytest.fixture
def sample_device():
    return {
        "name": "JX-3P",
        "brand": "Roland",
        "category": "synthesizer",
        "market": {
            "avg_market_price_eur": 1000,
            "good_deal_price_eur": 650,
            "steal_price_eur": 400,
            "price_references": []
        },
        "deal_detection": {
            "search_keywords": ["JX-3P", "JX3P", "Roland JX"],
            "common_mislabels": ["Roland keyboard"],
            "missing_keywords": ["analog"]
        }
    }

@pytest.fixture
def sample_listing_html():
    """Minimal Kleinanzeigen article HTML for parse_listings tests."""
    return '''
    <article class="aditem" data-href="/s-anzeige/test/123">
        <h2><a class="ellipsis">Roland JX-3P Synthesizer</a></h2>
        <div class="aditem-main--middle--price-shipping--price">650 € VB</div>
        <div class="aditem-main--middle--description">Great condition</div>
        <div class="aditem-main--top--left">Berlin</div>
        <div class="aditem-main--top--right">03.01.2026</div>
    </article>
    '''

@pytest.fixture
def sample_market():
    return {
        "avg_market_price_eur": 1000,
        "good_deal_price_eur": 650,
        "steal_price_eur": 400,
    }
```

**Location:**
- Shared fixtures: `tests/conftest.py`
- HTML fixtures for parsing tests: `tests/fixtures/` (create as needed)

## Coverage

**Requirements:** None enforced (no tests exist)

**Recommended setup:**
```bash
pip install pytest-cov
pytest --cov=. --cov-report=term-missing
```

**High-value coverage targets (pure functions, easy to test):**
- `scanner.py`: `normalize()`, `parse_price()`, `rate_deal()`, `calc_profit()`, `is_relevant()`, `build_search_url()`, `parse_listing_date()`, `is_too_old()`, `parse_listings()`
- `web.py`: `load_scan()`, `list_scans()`
- `songkick_events.py`: `parse_jsonld_performers()`, `parse_jsonld_dates()`, `build_songkick_url()`, `city_already_processed()`

## Test Types

**Unit Tests:**
- Not present. Should target pure functions in `scanner.py` (9 pure functions, all highly testable)
- `songkick_events.py` has several testable parser functions: `parse_jsonld_performers()`, `parse_jsonld_dates()`

**Integration Tests:**
- Not present. Should test `parse_listings()` with real HTML snippets from Kleinanzeigen
- Should test `load_scan()` / `list_scans()` with temp directories
- Should test Flask routes in `web.py` using Flask test client

**E2E Tests:**
- Not present
- Would require Bright Data credentials and live scraping (expensive, slow)
- Not recommended for automated CI; manual verification is the current approach

## Common Patterns

**Async Testing (recommended):**
```python
import pytest

@pytest.mark.asyncio
async def test_scan_device_handles_empty_html():
    # Use pytest-asyncio for async function testing
    pass
```

**Error Testing (recommended):**
```python
def test_parse_price_invalid_input():
    price, is_vb = parse_price("not a price")
    assert price is None

def test_parse_listing_date_invalid():
    result = parse_listing_date("invalid date")
    assert result is None
```

**Flask Route Testing (recommended):**
```python
import pytest
from web import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_index_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200

def test_api_scan_returns_json(client):
    response = client.get("/api/scan")
    assert response.content_type == "application/json"
```

## Testing Gaps Summary

| Module | Testable Functions | Tests | Priority |
|--------|--------------------|-------|----------|
| `scanner.py` | 9 pure functions + `parse_listings` | 0 | **High** |
| `web.py` | 2 helpers + 2 routes | 0 | Medium |
| `songkick_events.py` | 4 parsers + URL builder | 0 | Medium |

The codebase has zero test coverage. The highest-value starting point is unit-testing the pure functions in `scanner.py` -- they have clear inputs/outputs, no side effects, and represent the core business logic (price parsing, deal rating, relevance filtering).

---

*Testing analysis: 2026-03-05*
