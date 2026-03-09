# Analog Deal Scanner

Scrapes [Kleinanzeigen.de](https://www.kleinanzeigen.de) for underpriced vintage synthesizers, drum machines, effects, and other analog gear. Compares listing prices against known market values to surface buy-and-resell opportunities.

## How it works

1. **`schema.json`** defines ~55 devices with market prices and search keywords (see [`SCHEMA.md`](SCHEMA.md) for details)
2. **`scanner.py`** searches Kleinanzeigen for each device via [Bright Data Scraping Browser](https://brightdata.com/products/scraping-browser), filters irrelevant results, and rates each listing as `steal` / `good_deal` / `market_price` / `above_market`
3. **`web.py`** serves a retro dashboard to browse results sorted by deal quality

## Quick start

```bash
pip install -r requirements.txt
```

Configure Bright Data credentials in `.env`:

```
BRIGHTDATA_ENDPOINT=wss://brd-customer-...:password@brd.superproxy.io:9222
```

Run a scan:

```bash
python scanner.py        # all devices (~55 searches, ~3 min)
python scanner.py 10     # first 10 devices only
```

View results:

```bash
python web.py            # http://localhost:5001
```

## Project structure

```
scanner.py           Scraper — Bright Data + Playwright + BeautifulSoup
web.py               Flask dashboard
templates/index.html Retro 80s UI
schema.json          Device catalog with market prices and search keywords
SCHEMA.md            Source data documentation
results/             Scan output (JSON per run)
.env                 Bright Data credentials (not committed)
```

## Deal rating

Listings are rated by comparing the asking price against thresholds from `schema.json`. When a listing is marked VB (Verhandlungsbasis / negotiable), the effective price is discounted 15% for rating purposes.

| Rating | Meaning |
|---|---|
| `steal` | At or below steal price — rare, act fast |
| `good_deal` | Below good-deal threshold — solid margin |
| `market_price` | Fair price, limited upside |
| `above_market` | Overpriced |

Search URLs also use Kleinanzeigen price filters (`s-preis:min:max`) to pre-filter results, and a fuzzy title check removes unrelated listings that slip through.
