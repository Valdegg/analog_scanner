"""
Kleinanzeigen.de Deal Scanner

Reads devices from schema.json, searches Kleinanzeigen.de via Bright Data
Scraping Browser, and saves structured results to results/scan_DATE.json.
"""
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

BASE_URL = "https://www.kleinanzeigen.de"
PAUSE_SECONDS = 2
MAX_RETRIES = 3
NAV_TIMEOUT_MS = 60_000
VB_DISCOUNT = 0.15
MAX_LISTING_AGE_DAYS = 365


def normalize(text: str) -> str:
    """Strip all non-alphanumeric chars and lowercase for fuzzy comparison."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def build_search_url(keyword: str, market: dict) -> str:
    slug = keyword.lower().replace(" ", "-")
    price_min = int(market["steal_price_eur"])
    price_max = int(market["avg_market_price_eur"])
    return f"{BASE_URL}/s-preis:{price_min}:{price_max}/{slug}/k0"


def is_relevant(title: str, device: dict) -> bool:
    """Check that the listing title approximately matches the device."""
    if not title:
        return False
    norm_title = normalize(title)
    keywords = device["deal_detection"]["search_keywords"]
    for kw in keywords:
        if normalize(kw) in norm_title:
            return True
    if normalize(device["name"]) in norm_title:
        return True
    return False


def parse_price(text: str) -> tuple[float | None, bool]:
    """Extract numeric price and VB flag from a price string like '1.199 € VB'."""
    if not text:
        return None, False
    is_vb = "VB" in text
    cleaned = text.replace("VB", "").replace("€", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned), is_vb
    except ValueError:
        return None, is_vb


def parse_listing_date(text: str) -> datetime | None:
    """Parse Kleinanzeigen date strings like '03.08.2024', 'Heute, 14:04', 'Gestern, 17:03'."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("Heute"):
        return datetime.now()
    if t.startswith("Gestern"):
        return datetime.now() - timedelta(days=1)
    try:
        return datetime.strptime(t[:10], "%d.%m.%Y")
    except (ValueError, IndexError):
        return None


def is_too_old(date_text: str) -> bool:
    d = parse_listing_date(date_text)
    if d is None:
        return False
    return (datetime.now() - d).days > MAX_LISTING_AGE_DAYS


def rate_deal(price: float | None, is_vb: bool, market: dict) -> str:
    if price is None:
        return "unknown"
    effective = price * (1 - VB_DISCOUNT) if is_vb else price
    if effective <= market["steal_price_eur"]:
        return "steal"
    if effective <= market["good_deal_price_eur"]:
        return "good_deal"
    if effective <= market["avg_market_price_eur"]:
        return "market_price"
    return "above_market"


def calc_profit(price: float | None, is_vb: bool, avg_price: float) -> float | None:
    if price is None:
        return None
    effective = price * (1 - VB_DISCOUNT) if is_vb else price
    return round(avg_price - effective)


def parse_listings(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    results = []

    for article in soup.select("article.aditem"):
        title_el = article.select_one("h2 a.ellipsis")
        title = title_el.get_text(strip=True) if title_el else None

        href = article.get("data-href", "")
        url = f"{BASE_URL}{href}" if href else None

        price_el = article.select_one(
            ".aditem-main--middle--price-shipping--price"
        )
        price_text = price_el.get_text(strip=True) if price_el else ""
        price_eur, is_vb = parse_price(price_text)

        old_price_el = article.select_one(
            ".aditem-main--middle--price-shipping--old-price"
        )
        original_price_eur = None
        if old_price_el:
            original_price_eur, _ = parse_price(old_price_el.get_text(strip=True))

        desc_el = article.select_one(".aditem-main--middle--description")
        description = desc_el.get_text(strip=True) if desc_el else None

        loc_el = article.select_one(".aditem-main--top--left")
        location = loc_el.get_text(strip=True) if loc_el else None

        date_el = article.select_one(".aditem-main--top--right")
        date = date_el.get_text(strip=True) if date_el else None

        img_el = article.select_one(".aditem-image .imagebox img")
        image_url = None
        if img_el:
            image_url = img_el.get("srcset") or img_el.get("src")

        results.append({
            "title": title,
            "price_eur": price_eur,
            "is_vb": is_vb,
            "original_price_eur": original_price_eur,
            "description": description,
            "location": location,
            "date": date,
            "url": url,
            "image_url": image_url,
        })

    return results


def load_schema(path: str = "schema.json") -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["devices"]


async def fetch_page(pw, endpoint: str, url: str) -> str:
    """Connect to Bright Data, navigate, grab HTML, close -- one session per page."""
    browser = await pw.chromium.connect_over_cdp(endpoint)
    try:
        page = await browser.new_page()
        await page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        return await page.content()
    finally:
        await browser.close()


async def scan_device(pw, endpoint: str, device: dict) -> dict:
    keyword = device["deal_detection"]["search_keywords"][0]
    market = device["market"]
    search_url = build_search_url(keyword, market)

    html = ""
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

    raw_listings = parse_listings(html)
    avg_price = market["avg_market_price_eur"]

    listings = []
    filtered_count = 0
    old_count = 0
    for listing in raw_listings:
        if not is_relevant(listing["title"], device):
            filtered_count += 1
            continue
        if is_too_old(listing.get("date")):
            old_count += 1
            continue
        listing["deal_rating"] = rate_deal(listing["price_eur"], listing["is_vb"], market)
        listing["est_profit_eur"] = calc_profit(listing["price_eur"], listing["is_vb"], avg_price)
        listings.append(listing)

    if filtered_count or old_count:
        parts = []
        if filtered_count:
            parts.append(f"{filtered_count} irrelevant")
        if old_count:
            parts.append(f"{old_count} older than {MAX_LISTING_AGE_DAYS}d")
        print(f"  ({', '.join(parts)} filtered out)")

    prices = [l["price_eur"] for l in listings if l.get("price_eur")]
    ka_avg = round(sum(prices) / len(prices)) if prices else None

    return {
        "device": device["name"],
        "brand": device["brand"],
        "category": device.get("category", "other"),
        "search_keyword": keyword,
        "search_url": search_url,
        "market": {
            "avg_price_eur": avg_price,
            "good_deal_eur": market["good_deal_price_eur"],
            "steal_eur": market["steal_price_eur"],
            "ka_avg_eur": ka_avg,
            "ka_listing_count": len(prices),
            "price_references": market.get("price_references", []),
        },
        "listings": listings,
    }


async def main():
    endpoint = os.getenv("BRIGHTDATA_ENDPOINT")
    if not endpoint:
        print("Error: BRIGHTDATA_ENDPOINT not set in .env")
        sys.exit(1)

    devices = load_schema()

    limit = None
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
        devices = devices[:limit]

    print(f"Scanning {len(devices)} devices via Bright Data Scraping Browser...")

    results = []
    total_listings = 0

    async with async_playwright() as pw:
        for i, device in enumerate(devices):
            keyword = device["deal_detection"]["search_keywords"][0]
            print(f"[{i+1}/{len(devices)}] {device['brand']} {device['name']} ({keyword})")

            result = await scan_device(pw, endpoint, device)
            n = len(result["listings"])
            total_listings += n

            deals = [l for l in result["listings"] if l["deal_rating"] in ("steal", "good_deal")]
            if deals:
                for d in deals:
                    print(f"  ** {d['deal_rating'].upper()}: {d['title']} — {d['price_eur']}€{' VB' if d['is_vb'] else ''} (est. profit: {d['est_profit_eur']}€)")
            elif n:
                print(f"  {n} listing(s), no deals below market")
            else:
                print(f"  no relevant listings")

            results.append(result)

            if i < len(devices) - 1:
                await asyncio.sleep(PAUSE_SECONDS)

    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)
    scan_date = datetime.now().isoformat(timespec="seconds")
    output_path = output_dir / f"scan_{datetime.now().strftime('%Y-%m-%d_%H%M')}.json"

    output = {
        "scan_date": scan_date,
        "total_devices_searched": len(devices),
        "total_listings_found": total_listings,
        "results": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nDone. {total_listings} listings across {len(devices)} devices.")
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
