# schema.json — Vintage Music Gear Deal Database

A structured catalog of 76 vintage analog and electromechanical music devices that are commonly underpriced on local classifieds (Kleinanzeigen, Marktplaats, Leboncoin, Gumtree, etc.).

The goal: identify listings where a seller doesn't know what they have — a €1,200 synthesizer listed as "old keyboard €150" — and surface those as deal opportunities.

## What's in it

| Category | Count | Examples |
|---|---|---|
| Synthesizer | 37 | Roland Juno-60, Korg Polysix, Moog Prodigy, Oberheim Matrix-1000 |
| Effect | 16 | Roland RE-201 Space Echo, Eventide H3000, Boss CE-1 |
| Drum machine | 8 | Roland TR-707, Oberheim DMX, Boss DR-110 |
| Keyboard | 7 | Wurlitzer 200A, Fender Rhodes Stage 73, Hohner Clavinet D6 |
| Microphone | 4 | Neumann U87, Sennheiser MD 421, Shure SM7 |
| Sampler | 2 | Akai S950, S900 |
| Drum synth | 2 | Simmons SDS-V, SDS-9 |

Market prices range from €350 (MXR Distortion+) to €4,800 (Roland MKS-80 Super Jupiter), with a median of €1,000.

## Schema structure

Each device entry has four sections:

### Identity

```json
{
    "name": "JX-3P",
    "brand": "Roland",
    "category": "synthesizer",
    "subtype": "analog polyphonic",
    "year_range": [1983, 1985],
    "architecture": "DCO analog subtractive"
}
```

### Market pricing (EUR)

Three price tiers for classifying a listing:

```json
{
    "avg_market_price_eur": 1000,
    "good_deal_price_eur": 650,
    "steal_price_eur": 400
}
```

- **avg_market_price** — fair market value based on Reverb/eBay sold prices (as of early 2026).
- **good_deal_price** — roughly 65% of market; a solid buy worth acting on.
- **steal_price** — roughly 40% of market; drop everything and go get it.
- **price_references** — direct links to verify current prices:
  - Reverb product/price guide page (global sold prices)
  - eBay.de completed+sold listings (European market data)

### Opportunity scores (1–5)

```json
{
    "rarity_score": 3,
    "liquidity_score": 4,
    "mispricing_frequency": 3
}
```

| Score | Meaning |
|---|---|
| **rarity_score** | 1 = common on the used market, 5 = rarely appears |
| **liquidity_score** | 1 = slow to resell, 5 = sells within days |
| **mispricing_frequency** | 1 = almost always priced correctly, 5 = regularly listed far below value |

The best deal targets combine high mispricing_frequency with high liquidity — cheap to acquire, fast to flip.

### Deal detection

The most operationally useful section — designed to power search and classification:

```json
{
    "common_mislabels": ["Roland keyboard", "80s keyboard", "old synth", "MIDI keyboard"],
    "search_keywords": ["JX-3P", "JX3P", "Roland JX"],
    "missing_keywords": ["analog", "vintage", "synthesizer"]
}
```

- **common_mislabels** — what uninformed sellers actually title their listings. Includes German terms where relevant ("altes Klavier", "Schlagzeugcomputer", "Effektgerät").
- **search_keywords** — exact terms and spelling variants to search for on marketplaces.
- **missing_keywords** — terms that *should* appear in a properly-priced listing but are absent in underpriced ones. A listing that says "Roland keyboard" but not "analog" or "synthesizer" is a signal.

### Notes

Free-text field with context on why mispricing happens and what to watch for:

> "Often sold as a generic 80s keyboard; PG-200 programmer (if included) adds value."

## How the scores interact

The highest-value scan targets are devices where:

- **mispricing_frequency ≥ 4** — listings regularly appear below market
- **liquidity_score ≥ 4** — you can resell quickly if you buy
- **steal_price is reachable** — realistic that someone would list at this level

Top arbitrage candidates by this logic:

| Device | Avg | Steal | Misprice | Liquidity |
|---|---|---|---|---|
| Wurlitzer 200A | €2,500 | €900 | 5 | 5 |
| Roland Alpha Juno 1 | €800 | €350 | 4 | 5 |
| Roland Alpha Juno 2 | €950 | €380 | 4 | 5 |
| Ensoniq ESQ-1 | €700 | €250 | 4 | 4 |
| Roland MKS-50 | €850 | €320 | 4 | 4 |
| Korg DW-6000 | €600 | €220 | 4 | 3 |
| Boss DR-110 | €500 | €150 | 4 | 4 |
| Roland SDE-1000/2000 | €500 | €180 | 4 | 4 |
