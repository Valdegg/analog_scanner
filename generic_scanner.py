"""
Generic Kleinanzeigen.de Scanner

Generates search queries from schema.json mislabels and German generic terms,
searches Kleinanzeigen.de with a 500 EUR price cap via Bright Data + Playwright,
deduplicates listings across queries, filters old/no-photo/over-budget items,
then scrapes each listing's detail page for hero image (base64) and full description.

Output: results/generic_scrape_DATE.json with enriched listing data.
"""
import asyncio
import base64
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from scanner import (
    BASE_URL,
    MAX_RETRIES,
    NAV_TIMEOUT_MS,
    PAUSE_SECONDS,
    fetch_page,
    load_schema,
    parse_listing_date,
    parse_listings,
)

load_dotenv(override=True)

logger = logging.getLogger(__name__)

GENERIC_MAX_PRICE_EUR = 500
GENERIC_MAX_AGE_DAYS = 5
SCRAPE_CONCURRENCY = 5  # parallel Bright Data sessions


def is_too_old_generic(date_str: str | None) -> bool:
    """Filter listings older than GENERIC_MAX_AGE_DAYS."""
    if not date_str:
        return True
    d = parse_listing_date(date_str)
    if d is None:
        return True
    return (datetime.now() - d).days > GENERIC_MAX_AGE_DAYS

GERMAN_GENERIC_TERMS = [
    "alter Synthesizer",
    "vintage Synth",
    "80er Keyboard",
    "analoger Synthesizer",
    "Drummachine",
    "altes Effektgerät",
]

# Queries that return mostly junk (consumer gear, acoustic pianos, toys, non-music items)
QUERY_BLOCKLIST = {
    "altes klavier", "altes klavier elektrisch", "altes keyboard", "altes mischpult",
    "altes e-piano", "alter synthesizer",
    "tastatur", "schlagzeug", "workstation", "e-piano", "stage piano", "home keyboard",
    "beat box", "drum kit", "drum pads", "digital drums", "electronic drums",
    "midi keyboard", "wah pedal", "stage keyboard",
    "akai keyboard", "korg keyboard", "yamaha keyboard", "roland piano",
    "kawai keyboard", "hohner klavier", "hohner keyboard",
    "guitar effect", "guitar delay", "guitar echo", "guitar distortion", "guitar filter",
    "studio mic", "studio microphone", "studio condenser", "recording mic",
    "radio microphone", "broadcast mic", "sennheiser microphone", "shure mic",
    "neumann microphone", "studiomikrofon vintage",
    "cembalo", "electric piano", "fender piano", "rhodes keyboard", "rhodes piano",
    "old keyboard", "old piano", "old organ", "old pedal",
    "old electric piano", "old electronic drums", "old drum pads",
    "old kawai", "old korg", "old korg piano", "old moog", "old mxr pedal",
    "old boss pedal", "old delay pedal", "old effect pedal",
    "old rack sampler", "old rack synth", "old sampler", "old stage piano",
    "old studio effect", "old studio keyboard", "old synth",
    "old tape machine", "old workstation", "old yamaha",
    "small moog", "small synth", "patch synth", "polyphonic keyboard",
    "hohner organ", "wurlitzer klavier",
}


def generate_queries(devices: list[dict]) -> list[str]:
    """Extract all common_mislabels from devices, deduplicate, add German generic terms.

    Returns a sorted list of unique query strings, filtered by blocklist.
    """
    mislabels = set()
    for device in devices:
        for label in device.get("deal_detection", {}).get("common_mislabels", []):
            mislabels.add(label.lower().strip())

    mislabel_count = len(mislabels)

    for term in GERMAN_GENERIC_TERMS:
        mislabels.add(term.lower().strip())

    # Remove junk queries
    mislabels -= QUERY_BLOCKLIST

    queries = sorted(mislabels)
    logger.info(
        "%d unique queries generated from %d mislabels + German generics (%d blocked)",
        len(queries),
        mislabel_count,
        len(QUERY_BLOCKLIST),
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
        if is_too_old_generic(listing.get("date")):
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


async def scrape_detail_page(pw, endpoint: str, listing_url: str) -> dict | None:
    """Navigate to a listing's detail page, extract hero image as base64 and full description.

    Returns {"image_base64": str, "full_description": str, "image_content_type": str}
    or None if no image is found (listing should be skipped).
    """
    for attempt in range(1, MAX_RETRIES + 1):
        browser = None
        try:
            browser = await pw.chromium.connect_over_cdp(endpoint)
            page = await browser.new_page()
            await page.goto(
                listing_url,
                timeout=NAV_TIMEOUT_MS,
                wait_until="domcontentloaded",
            )
            await page.wait_for_timeout(3000)

            # --- Extract hero image URL (try multiple selectors) ---
            image_url = None
            image_selectors = [
                "img#viewad-image",
                "img.galleryimage-element",
                "#viewad-image img",
                ".galleryimage-element img",
                "#viewad-product img",
                ".ad-keydetails img",
            ]
            for selector in image_selectors:
                el = await page.query_selector(selector)
                if el:
                    image_url = await el.get_attribute("src")
                    if not image_url:
                        image_url = await el.get_attribute("data-imgsrc")
                    if image_url:
                        logger.info("Found image with selector '%s': %s", selector, image_url[:80])
                        break

            if not image_url:
                # Broader fallback: first large image in the gallery/ad area
                el = await page.query_selector(
                    "#viewad-product img, .is-hero img, [data-testid='viewad-image'] img"
                )
                if el:
                    image_url = await el.get_attribute("src")

            if not image_url:
                logger.warning("No image found on detail page: %s", listing_url)
                return None

            # --- Download image and encode as base64 via in-browser fetch ---
            image_data = await page.evaluate(
                """async (url) => {
                    try {
                        const resp = await fetch(url);
                        if (!resp.ok) return null;
                        const blob = await resp.blob();
                        return await new Promise((resolve, reject) => {
                            const reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result);
                            reader.onerror = reject;
                            reader.readAsDataURL(blob);
                        });
                    } catch (e) {
                        return null;
                    }
                }""",
                image_url,
            )

            if not image_data:
                logger.warning("Failed to fetch image from %s", image_url)
                return None

            # Parse data URL: "data:image/jpeg;base64,/9j/4AAQ..."
            match = re.match(r"data:(image/[^;]+);base64,(.+)", image_data, re.DOTALL)
            if match:
                image_content_type = match.group(1)
                image_bytes = base64.b64decode(match.group(2))
            else:
                # Fallback: treat entire string as raw base64, assume jpeg
                image_content_type = "image/jpeg"
                image_bytes = base64.b64decode(image_data)

            # --- Extract full description ---
            full_description = ""
            desc_selectors = [
                "#viewad-description-text",
                "[data-testid='viewad-description'] p",
                ".ad-keydetails--description",
                "#viewad-description",
            ]
            for selector in desc_selectors:
                el = await page.query_selector(selector)
                if el:
                    full_description = (await el.inner_text()).strip()
                    if full_description:
                        logger.info(
                            "Found description with selector '%s' (%d chars)",
                            selector,
                            len(full_description),
                        )
                        break

            if not full_description:
                logger.warning("No description found on detail page: %s", listing_url)

            # --- Extract seller name ---
            seller_name = ""
            seller_selectors = [
                "#viewad-contact .iconcard-title",
                "[data-testid='viewad-contact'] .iconcard-title",
                "#viewad-contact .userprofile-vip a",
                ".ad-contact .userprofile-vip a",
                "#viewad-contact a[href*='/s-bestandsliste']",
            ]
            for selector in seller_selectors:
                el = await page.query_selector(selector)
                if el:
                    seller_name = (await el.inner_text()).strip()
                    if seller_name:
                        break
            if not seller_name:
                # Fallback: try JS extraction
                seller_name = await page.evaluate("""() => {
                    const el = document.querySelector('#viewad-contact');
                    if (!el) return '';
                    const title = el.querySelector('.iconcard-title');
                    if (title) return title.innerText.trim();
                    const link = el.querySelector('a');
                    if (link) return link.innerText.trim();
                    return '';
                }""") or ""

            # --- Scam flags ---
            scam_flags = []
            name_lower = seller_name.lower().strip()
            if name_lower in ("privat", "private", "privater nutzer", ""):
                scam_flags.append("anonymous_seller")
            # Check account age / number of ads if available
            active_since = await page.evaluate("""() => {
                const el = document.querySelector('#viewad-contact .iconcard-subtitle, [data-testid=\\"viewad-contact\\"] .textcontent');
                return el ? el.innerText.trim() : '';
            }""") or ""
            if active_since:
                import re as _re
                year_match = _re.search(r'20(\\d{2})', active_since)
                if year_match and int('20' + year_match.group(1)) >= 2026:
                    scam_flags.append("new_account")

            return {
                "image_bytes": image_bytes,
                "full_description": full_description,
                "image_content_type": image_content_type,
                "seller_name": seller_name,
                "scam_flags": scam_flags,
            }

        except Exception as e:
            if attempt == MAX_RETRIES:
                logger.error(
                    "FAILED after %d attempts scraping detail page %s: %s",
                    MAX_RETRIES,
                    listing_url,
                    e,
                )
                return None
            else:
                logger.warning(
                    "Retry %d/%d for detail page %s: %s",
                    attempt,
                    MAX_RETRIES,
                    listing_url,
                    e,
                )
                await asyncio.sleep(5)
        finally:
            if browser:
                await browser.close()

    return None


async def main():
    """Full generic search pipeline: generate queries, scrape, deduplicate, enrich, save."""
    endpoint = os.getenv("BRIGHTDATA_ENDPOINT")
    if not endpoint:
        print("Error: BRIGHTDATA_ENDPOINT not set in .env")
        sys.exit(1)

    devices = load_schema()
    queries = generate_queries(devices)

    limit = None
    query_filter = None
    search_only = "--search-only" in sys.argv
    for arg in sys.argv[1:]:
        if arg.startswith("--queries="):
            query_filter = [q.strip().lower() for q in arg.split("=", 1)[1].split(",")]
        elif arg == "--search-only":
            continue
        else:
            limit = int(arg)

    if query_filter:
        queries = [q for q in queries if q in query_filter]
    elif limit:
        queries = queries[:limit]

    print(f"Searching {len(queries)} generic queries via Bright Data Scraping Browser (concurrency: {SCRAPE_CONCURRENCY})...")

    from playwright.async_api import async_playwright

    # --- Phase 1: Parallel search queries ---
    sem = asyncio.Semaphore(SCRAPE_CONCURRENCY)
    search_done = 0

    async def run_search(pw, query: str) -> list[dict]:
        nonlocal search_done
        async with sem:
            results = await search_query(pw, endpoint, query)
            search_done += 1
            print(f"[{search_done}/{len(queries)}] Searched: {query} -> {len(results)} results")
            return results

    async with async_playwright() as pw:
        tasks = [run_search(pw, q) for q in queries]
        search_results = await asyncio.gather(*tasks)

    all_listings = [listing for batch in search_results for listing in batch]

    before_dedup = len(all_listings)
    listings = deduplicate_listings(all_listings)

    # Prepare output directories
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)

    if search_only:
        enriched = listings
        skipped = 0
        print(f"\n--search-only: skipping detail page scraping, {len(listings)} listings from search results")
    else:
        # --- Phase 2: Parallel detail page scraping ---
        print(f"\nScraping detail pages for {len(listings)} listings (concurrency: {SCRAPE_CONCURRENCY})...")

        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)

        detail_done = 0
        detail_sem = asyncio.Semaphore(SCRAPE_CONCURRENCY)

        async def run_detail(pw, listing: dict) -> dict | None:
            nonlocal detail_done
            async with detail_sem:
                detail = await scrape_detail_page(pw, endpoint, listing["url"])
                detail_done += 1
                title_preview = (listing.get("title") or "")[:50]

                if detail is None:
                    print(f"[{detail_done}/{len(listings)}] Skip (no image): {title_preview}")
                    return None

                # Save image to disk
                ext = detail["image_content_type"].split("/")[-1]
                if ext == "jpeg":
                    ext = "jpg"
                url_id = listing["url"].rstrip("/").split("/")[-1].split("-")[0]
                image_filename = f"{url_id}.{ext}"
                image_path = images_dir / image_filename
                image_path.write_bytes(detail["image_bytes"])

                listing["image_path"] = str(image_path)
                listing["full_description"] = detail["full_description"]
                listing["image_content_type"] = detail["image_content_type"]
                listing["seller_name"] = detail.get("seller_name", "")
                listing["scam_flags"] = detail.get("scam_flags", [])
                flags = f" [SCAM: {', '.join(detail['scam_flags'])}]" if detail.get("scam_flags") else ""
                print(f"[{detail_done}/{len(listings)}] Enriched: {title_preview}{flags}")
                return listing

        async with async_playwright() as pw:
            tasks = [run_detail(pw, listing) for listing in listings]
            detail_results = await asyncio.gather(*tasks)

        enriched = [r for r in detail_results if r is not None]
        skipped = len(listings) - len(enriched)

        print(f"\n{len(enriched)} listings enriched with detail page data, {skipped} skipped (no image)")

    # Save results
    scrape_date = datetime.now().isoformat(timespec="seconds")
    output_path = output_dir / f"generic_scrape_{datetime.now().strftime('%Y-%m-%d_%H%M')}.json"

    output = {
        "scrape_date": scrape_date,
        "total_queries": len(queries),
        "total_listings": len(enriched),
        "listings_skipped_no_image": skipped,
        "listings": enriched,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nDone. {len(queries)} queries searched.")
    print(f"Listings: {before_dedup} total -> {len(listings)} after dedup -> {len(enriched)} enriched")
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
    asyncio.run(main())
