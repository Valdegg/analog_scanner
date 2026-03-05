"""
Generic Kleinanzeigen.de Scanner

Generates search queries from schema.json mislabels and German generic terms,
searches Kleinanzeigen.de with a 500 EUR price cap via Bright Data + Playwright,
deduplicates listings across queries, and filters old/no-photo/over-budget items.

Output: results/generic_scrape_DATE.json with scraped listing data.
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from scanner import (
    BASE_URL,
    MAX_RETRIES,
    PAUSE_SECONDS,
    fetch_page,
    is_too_old,
    load_schema,
    parse_listings,
)

load_dotenv(override=True)

logger = logging.getLogger(__name__)

GENERIC_MAX_PRICE_EUR = 500

GERMAN_GENERIC_TERMS = [
    "altes Keyboard",
    "alter Synthesizer",
    "vintage Synth",
    "80er Keyboard",
    "analoger Synthesizer",
    "altes Mischpult",
    "Drummachine",
    "altes Effektgerät",
    "Studiomikrofon vintage",
    "altes Klavier elektrisch",
]


def generate_queries(devices: list[dict]) -> list[str]:
    """Extract all common_mislabels from devices, deduplicate, add German generic terms.

    Returns a sorted list of unique query strings.
    """
    mislabels = set()
    for device in devices:
        for label in device.get("deal_detection", {}).get("common_mislabels", []):
            mislabels.add(label.lower().strip())

    mislabel_count = len(mislabels)

    # Add German generic terms (normalized)
    for term in GERMAN_GENERIC_TERMS:
        mislabels.add(term.lower().strip())

    queries = sorted(mislabels)
    logger.info(
        "%d unique queries generated from %d mislabels + German generics",
        len(queries),
        mislabel_count,
    )
    return queries


def build_generic_search_url(query: str, max_price: int = GENERIC_MAX_PRICE_EUR) -> str:
    """Build a Kleinanzeigen.de search URL with no minimum price and max_price ceiling.

    URL format: {BASE_URL}/s-preis::{max_price}/{slug}/k0
    """
    slug = query.lower().replace(" ", "-")
    return f"{BASE_URL}/s-preis::{max_price}/{slug}/k0"


async def search_query(pw, endpoint: str, query: str) -> list[dict]:
    """Search a single query on Kleinanzeigen.de and return filtered listings."""
    url = build_generic_search_url(query)

    html = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            html = await fetch_page(pw, endpoint, url)
            break
        except Exception as e:
            if attempt == MAX_RETRIES:
                logger.error("FAILED after %d attempts for '%s': %s", MAX_RETRIES, query, e)
            else:
                logger.warning("Retry %d/%d for '%s': %s", attempt, MAX_RETRIES, query, e)
                await asyncio.sleep(5)

    raw_listings = parse_listings(html)
    total = len(raw_listings)

    # Filter: old listings, no photo, over budget, no price
    filtered = []
    for listing in raw_listings:
        if is_too_old(listing.get("date")):
            continue
        if not listing.get("image_url"):
            continue
        if listing.get("price_eur") is None:
            continue
        if listing["price_eur"] > GENERIC_MAX_PRICE_EUR:
            continue
        listing["source_query"] = query
        filtered.append(listing)

    logger.info("Query '%s': %d results, %d after filtering", query, total, len(filtered))
    return filtered


def deduplicate_listings(all_listings: list[dict]) -> list[dict]:
    """Deduplicate listings by URL, keeping the first occurrence."""
    seen_urls = set()
    unique = []
    for listing in all_listings:
        url = listing.get("url")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(listing)

    removed = len(all_listings) - len(unique)
    logger.info(
        "Deduplicated: %d -> %d listings (%d duplicates)",
        len(all_listings),
        len(unique),
        removed,
    )
    return unique


async def main():
    """Full generic search pipeline: generate queries, scrape, deduplicate, save."""
    endpoint = os.getenv("BRIGHTDATA_ENDPOINT")
    if not endpoint:
        print("Error: BRIGHTDATA_ENDPOINT not set in .env")
        sys.exit(1)

    devices = load_schema()
    queries = generate_queries(devices)

    limit = None
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
        queries = queries[:limit]

    print(f"Searching {len(queries)} generic queries via Bright Data Scraping Browser...")

    all_listings = []

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        for i, query in enumerate(queries):
            print(f"[{i + 1}/{len(queries)}] Searching: {query}")

            results = await search_query(pw, endpoint, query)
            all_listings.extend(results)

            if i < len(queries) - 1:
                await asyncio.sleep(PAUSE_SECONDS)

    before_dedup = len(all_listings)
    listings = deduplicate_listings(all_listings)

    # Save results
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)
    scrape_date = datetime.now().isoformat(timespec="seconds")
    output_path = output_dir / f"generic_scrape_{datetime.now().strftime('%Y-%m-%d_%H%M')}.json"

    output = {
        "scrape_date": scrape_date,
        "total_queries": len(queries),
        "total_listings": len(listings),
        "listings": listings,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nDone. {len(queries)} queries searched.")
    print(f"Listings: {before_dedup} total -> {len(listings)} after dedup")
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
    asyncio.run(main())
