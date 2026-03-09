"""Deal Scanner Dashboard -- Flask web interface for scan results."""
import json
import re
from pathlib import Path

import pgeocode
from flask import Flask, render_template, jsonify, request

_nomi = pgeocode.Nominatim('de')

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

_plz_cache: dict[str, tuple[float, float] | None] = {}


def _extract_plz(location: str | None) -> str | None:
    """Extract 5-digit German PLZ from a location string like '59065 Hamm'."""
    if not location:
        return None
    m = re.match(r"(\d{5})", location.strip())
    return m.group(1) if m else None


def geocode_plz_set(plz_codes: set[str]) -> dict[str, list[float]]:
    """Resolve a set of PLZ codes to {plz: [lat, lng]} via pgeocode (cached)."""
    result = {}
    to_lookup = []
    for plz in plz_codes:
        if plz in _plz_cache:
            if _plz_cache[plz]:
                result[plz] = list(_plz_cache[plz])
        else:
            to_lookup.append(plz)
    if to_lookup:
        df = _nomi.query_postal_code(to_lookup)
        for i, plz in enumerate(to_lookup):
            row = df.iloc[i] if len(to_lookup) > 1 else df
            lat, lng = float(row["latitude"]), float(row["longitude"])
            if lat != lat:  # NaN check
                _plz_cache[plz] = None
            else:
                _plz_cache[plz] = (lat, lng)
                result[plz] = [lat, lng]
    return result


def build_plz_coords(*datasets) -> dict[str, list[float]]:
    """Extract all PLZ codes from listing datasets and geocode them."""
    plz_codes = set()
    for data in datasets:
        if not data:
            continue
        # Scan results: data.results[].listings[].location
        for r in data.get("results", []):
            if isinstance(r, dict) and "listings" in r:
                for l in r["listings"]:
                    plz = _extract_plz(l.get("location"))
                    if plz:
                        plz_codes.add(plz)
            else:
                # Analysis results: flat list with .location
                plz = _extract_plz(r.get("location"))
                if plz:
                    plz_codes.add(plz)
    return geocode_plz_set(plz_codes)


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


def load_analysis(filename: str | None = None) -> dict:
    """Load the most recent generic scan analysis."""
    if filename:
        path = RESULTS_DIR / filename
    else:
        analyses = sorted(RESULTS_DIR.glob("analysis_*.json"), reverse=True)
        if not analyses:
            return {"results": [], "total_analyzed": 0}
        path = analyses[0]
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_analyses() -> list[str]:
    return sorted(
        [p.name for p in RESULTS_DIR.glob("analysis_*.json")], reverse=True
    )


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
    analysis_file = request.args.get("analysis")
    analysis = load_analysis(analysis_file)
    analyses = list_analyses()
    current_analysis = analysis_file or (analyses[0] if analyses else None)
    plz_coords = build_plz_coords(data, analysis)
    return render_template(
        "index.html", data=data, scans=scans, current_scan=current_scan,
        categories=CATEGORIES, brands=BRANDS,
        analysis=analysis, analyses=analyses, current_analysis=current_analysis,
        plz_coords=plz_coords,
    )


@app.route("/api/scan")
def api_scan():
    scan_file = request.args.get("file")
    return jsonify(load_scan(scan_file))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
