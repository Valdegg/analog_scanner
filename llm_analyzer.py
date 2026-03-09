"""
LLM Analyzer for Generic Scanner Results

Sends each listing's image + description to an LLM with vision (via OpenRouter)
to identify the actual device, compare against schema.json market values,
and produce a ranked deals list.

Output: results/analysis_DATE.json with scored and sorted listings.
"""
import asyncio
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def load_device_catalog() -> list[dict]:
    """Load schema.json and build a compact reference for the LLM."""
    with open("schema.json") as f:
        data = json.load(f)
    return data["devices"]


def build_reference_table(devices: list[dict]) -> str:
    """Build a compact text table of known devices and their market values."""
    lines = []
    for d in devices:
        m = d.get("market", {})
        lines.append(
            f"- {d['brand']} {d['name']} ({d.get('category', '')}): "
            f"avg {m.get('avg_market_price_eur', '?')} EUR, "
            f"good deal <{m.get('good_deal_price_eur', '?')} EUR, "
            f"steal <{m.get('steal_price_eur', '?')} EUR"
        )
    return "\n".join(lines)


def build_prompt(listing: dict, reference_table: str) -> list[dict]:
    """Build the chat messages for analyzing a single listing."""
    # Support both modes: local image file or remote image URL
    image_url = None
    if listing.get("image_path"):
        image_path = Path(listing["image_path"])
        if not image_path.exists():
            return None
        image_bytes = image_path.read_bytes()
        content_type = listing.get("image_content_type", "image/jpeg")
        # Convert AVIF/WebP to JPEG since many vision APIs don't support them
        if content_type in ("image/avif", "image/webp") or image_path.suffix in (".avif", ".webp"):
            from PIL import Image
            import io
            try:
                import pillow_avif  # noqa: F401 — registers AVIF plugin
            except ImportError:
                pass
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            image_bytes = buf.getvalue()
            content_type = "image/jpeg"
        image_url = f"data:{content_type};base64,{base64.b64encode(image_bytes).decode()}"
    elif listing.get("image_url"):
        image_url = listing["image_url"]
    else:
        return None

    system_msg = f"""You are a skeptical expert in vintage synthesizers, drum machines, and electronic music equipment.
You identify devices from photos and descriptions, and assess deal quality.

CRITICAL RULES:
- ONLY identify what you can CONFIRM from the image. If the image is too small or blurry to read the model name, set confidence to "low".
- Do NOT assume a more valuable model when a cheaper one is equally likely. E.g. "Roland Juno" in the title could be a Juno-Di (worth 150 EUR) not a Juno-106 (worth 1000 EUR) — check the image carefully.
- Most listings are fairly priced. True steals (score >80) are extremely rare — maybe 1 in 50 listings.
- Consumer keyboards (Yamaha PSR, Casio CT, Bontempi) are almost never valuable. Score them low.
- "steal" means asking price is <40% of market value. "good_deal" means <70%. "fair" means roughly market price. Most things are "fair" or "overpriced".

KNOWN DEVICES AND MARKET VALUES:
{reference_table}

If the device matches one in the list above, use those market values.
If it's a device NOT in the list, estimate its market value based on your knowledge.
If it's not a music device or has no collectible value, say so."""

    user_content = [
        {
            "type": "image_url",
            "image_url": {"url": image_url},
        },
        {
            "type": "text",
            "text": f"""Analyze this Kleinanzeigen listing:

**Title:** {listing.get('title', 'Unknown')}
**Price:** {listing.get('price_eur', '?')} EUR {"(VB/negotiable)" if listing.get('is_vb') else ""}
**Seller:** {listing.get('seller_name', 'Unknown')}
**Scam flags from scraper:** {', '.join(listing.get('scam_flags', [])) or 'none'}
**Description:** {listing.get('full_description', listing.get('description', 'No description'))}

Respond with ONLY valid JSON (no markdown fences):
{{
  "identified_device": "Brand Model",
  "confidence": "high/medium/low",
  "is_known_device": true/false,
  "category": "synthesizer/drum_machine/keyboard/effects/mixer/other",
  "estimated_market_value_eur": 0,
  "asking_price_eur": 0,
  "deal_score": 0,
  "deal_rating": "steal/good_deal/fair/overpriced/not_interesting",
  "condition_notes": "brief condition assessment from photo + description",
  "scam_risk": "high/medium/low",
  "scam_reasons": "why you suspect scam or 'none'",
  "reasoning": "1-2 sentences on why this is or isn't a deal"
}}

SCAM DETECTION: Flag scam_risk as "high" if: seller name is "Privat"/anonymous, price is suspiciously low (>60% below market) on a desirable item, description is vague/generic, or scam flags are present. A real steal at 40% of market value is extremely rare — most "too good to be true" listings are scams.

deal_score: 0-100 where 100 = incredible steal. Consider: market value vs asking price, device desirability, condition, negotiability (VB). REDUCE score by 20-30 points if scam_risk is high.""",
        },
    ]

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_content},
    ]


CONCURRENCY = 20  # parallel API requests


async def analyze_listing(listing: dict, reference_table: str, client: httpx.AsyncClient, sem: asyncio.Semaphore) -> tuple[dict | None, dict]:
    """Send a listing to the LLM and parse the response."""
    empty_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
    messages = build_prompt(listing, reference_table)
    if messages is None:
        return None, empty_usage

    async with sem:
        resp = None
        for attempt in range(3):
            try:
                resp = await client.post(
                    OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {LLM_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": LLM_MODEL,
                        "messages": messages,
                        "max_tokens": 500,
                        "temperature": 0.1,
                    },
                    timeout=60,
                )
                if resp.status_code == 200:
                    break
                if resp.status_code in (429, 500, 502, 503):
                    await asyncio.sleep(3 * (attempt + 1))
                    continue
                return None, empty_usage
            except (httpx.TimeoutException, httpx.ConnectError):
                await asyncio.sleep(3 * (attempt + 1))
                continue

        if resp is None or resp.status_code != 200:
            return None, empty_usage

    data = resp.json()

    usage = data.get("usage", {})
    call_usage = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "cost_usd": 0.0,
    }
    if "total_cost" in usage:
        call_usage["cost_usd"] = float(usage["total_cost"])
    elif data.get("usage", {}).get("cost"):
        call_usage["cost_usd"] = float(data["usage"]["cost"])

    msg = data["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    if not content and msg.get("reasoning"):
        content = msg["reasoning"].strip()
    if not content:
        return None, empty_usage
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    try:
        analysis = json.loads(content)
    except json.JSONDecodeError:
        analysis = {"raw_response": content, "deal_score": 0}

    analysis["title"] = listing.get("title")
    analysis["url"] = listing.get("url")
    analysis["location"] = listing.get("location")
    analysis["date"] = listing.get("date")
    analysis["image_url"] = listing.get("image_url")
    analysis["asking_price_eur"] = listing.get("price_eur")
    analysis["image_path"] = listing.get("image_path")
    analysis["source_query"] = listing.get("source_query")

    return analysis, call_usage


async def async_main():
    if not LLM_API_KEY:
        print("Error: LLM_API_KEY not set in .env")
        sys.exit(1)

    scan_file = sys.argv[1] if len(sys.argv) > 1 else None
    if not scan_file:
        results = sorted(Path("results").glob("generic_scrape_*.json"), reverse=True)
        if not results:
            print("No scan results found in results/")
            sys.exit(1)
        scan_file = str(results[0])

    with open(scan_file) as f:
        scan_data = json.load(f)

    listings = scan_data["listings"]
    print(f"Analyzing {len(listings)} listings from {scan_file}")
    print(f"Using model: {LLM_MODEL} (concurrency: {CONCURRENCY})")

    devices = load_device_catalog()
    reference_table = build_reference_table(devices)

    sem = asyncio.Semaphore(CONCURRENCY)
    done_count = 0
    total = len(listings)

    async def process(i: int, listing: dict) -> tuple[dict | None, dict]:
        nonlocal done_count
        result, usage = await analyze_listing(listing, reference_table, client, sem)
        done_count += 1
        title = (listing.get("title") or "")[:50]
        if result:
            score = result.get("deal_score", 0)
            rating = result.get("deal_rating", "?")
            device = result.get("identified_device", "?")[:30]
            print(f"[{done_count}/{total}] {device} | {score} | {rating}")
        else:
            print(f"[{done_count}/{total}] skip: {title}")
        return result, usage

    async with httpx.AsyncClient() as client:
        tasks = [process(i, listing) for i, listing in enumerate(listings)]
        results_list = await asyncio.gather(*tasks)

    analyses = []
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
    for result, usage in results_list:
        total_usage["prompt_tokens"] += usage["prompt_tokens"]
        total_usage["completion_tokens"] += usage["completion_tokens"]
        total_usage["total_tokens"] += usage["total_tokens"]
        total_usage["cost_usd"] += usage["cost_usd"]
        if result:
            analyses.append(result)

    analyses.sort(key=lambda x: x.get("deal_score", 0), reverse=True)

    output_path = Path("results") / f"analysis_{datetime.now().strftime('%Y-%m-%d_%H%M')}.json"
    output = {
        "analysis_date": datetime.now().isoformat(timespec="seconds"),
        "model": LLM_MODEL,
        "source_file": scan_file,
        "total_analyzed": len(analyses),
        "api_usage": total_usage,
        "results": analyses,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"ANALYSIS COMPLETE - {len(analyses)} listings ranked")
    print(f"API cost: ${total_usage['cost_usd']:.4f} USD "
          f"({total_usage['prompt_tokens']:,} prompt + {total_usage['completion_tokens']:,} completion = {total_usage['total_tokens']:,} tokens)")
    print(f"{'='*60}\n")

    for i, a in enumerate(analyses[:10]):
        score = a.get("deal_score", 0)
        rating = a.get("deal_rating", "?")
        device = a.get("identified_device", "?")
        price = a.get("asking_price_eur", "?")
        market = a.get("estimated_market_value_eur", "?")
        print(f"#{i+1:2d} [{score:3d}] {device:<35s} {price} EUR (market ~{market} EUR) - {rating}")
        print(f"     {a.get('reasoning', '')[:100]}")
        print()

    print(f"Full results: {output_path}")


if __name__ == "__main__":
    asyncio.run(async_main())
