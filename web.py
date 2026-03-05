"""Deal Scanner Dashboard -- Flask web interface for scan results."""
import json
from pathlib import Path

from flask import Flask, render_template, jsonify, request

app = Flask(__name__)
RESULTS_DIR = Path(__file__).parent / "results"


def load_schema() -> dict:
    """Load schema.json and build a lookup dict keyed by lowercase device name."""
    schema_path = Path(__file__).parent / "schema.json"
    if not schema_path.exists():
        return {}
    with open(schema_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    lookup: dict[str, dict] = {}
    for device in data.get("devices", []):
        name = device.get("name", "").lower()
        if name:
            lookup[name] = device.get("opportunity", {})
            lookup[name]["_brand"] = device.get("brand", "")
            lookup[name]["_category"] = device.get("category", "")
    return lookup


SCHEMA_LOOKUP = load_schema()


def merge_opportunity(data: dict) -> dict:
    """Merge opportunity scores from schema into scan results."""
    for result in data.get("results", []):
        device_name = result.get("device", "").lower()
        opp = SCHEMA_LOOKUP.get(device_name, {})
        if opp:
            rarity = opp.get("rarity_score", 0)
            liquidity = opp.get("liquidity_score", 0)
            mispricing = opp.get("mispricing_frequency", 0)
            result["opportunity_score"] = rarity + liquidity + mispricing
            result["rarity_score"] = rarity
            result["liquidity_score"] = liquidity
            result["mispricing_frequency"] = mispricing
        else:
            result["opportunity_score"] = 0
            result["rarity_score"] = 0
            result["liquidity_score"] = 0
            result["mispricing_frequency"] = 0
    return data


def _schema_values() -> tuple[list[str], list[str]]:
    """Extract sorted unique categories and brands from schema."""
    categories: set[str] = set()
    brands: set[str] = set()
    for opp in SCHEMA_LOOKUP.values():
        cat = opp.get("_category", "")
        brand = opp.get("_brand", "")
        if cat:
            categories.add(cat)
        if brand:
            brands.add(brand)
    return sorted(categories), sorted(brands)


CATEGORIES, BRANDS = _schema_values()


def load_scan(filename: str | None = None) -> dict:
    if filename:
        path = RESULTS_DIR / filename
    else:
        scans = sorted(RESULTS_DIR.glob("scan_*.json"), reverse=True)
        if not scans:
            return {"scan_date": "N/A", "total_devices_searched": 0,
                    "total_listings_found": 0, "results": []}
        path = scans[0]
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_scans() -> list[str]:
    return sorted(
        [p.name for p in RESULTS_DIR.glob("scan_*.json")], reverse=True
    )


@app.route("/")
def index():
    scan_file = request.args.get("scan")
    data = load_scan(scan_file)
    merge_opportunity(data)
    scans = list_scans()
    current_scan = scan_file or (scans[0] if scans else None)
    return render_template(
        "index.html", data=data, scans=scans, current_scan=current_scan,
        categories=CATEGORIES, brands=BRANDS,
    )


@app.route("/api/scan")
def api_scan():
    scan_file = request.args.get("file")
    return jsonify(load_scan(scan_file))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
