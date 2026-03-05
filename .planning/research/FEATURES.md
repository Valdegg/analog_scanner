# Feature Research

**Domain:** LLM-powered marketplace listing analysis for vintage synth/keyboard identification
**Researched:** 2026-03-05
**Confidence:** HIGH (well-understood domain; vision LLM capabilities are mature; existing codebase provides clear constraints)

## Feature Landscape

### Table Stakes (Users Expect These)

Features the system must have or the core value proposition ("surface hidden gems") fails entirely.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Full listing page scraping | Thumbnails from search results are too low-res for LLM vision; full descriptions contain critical clues (brand mentions, condition, accessories) | MEDIUM | Navigate to each listing URL via Playwright/Bright Data, extract high-res images + full description text. Existing `fetch_page` pattern can be reused. |
| LLM vision analysis of listing images | Core value -- identifying what device is in the photo when the title says "altes Keyboard" | HIGH | Send image(s) + description to Claude via OpenRouter. Must handle: multiple images per listing, varying image quality, images showing multiple items. |
| Structured JSON output from LLM | Results must be machine-parseable for filtering, sorting, and dashboard display | MEDIUM | Use OpenRouter's `response_format: { type: "json_schema" }` with strict mode. Schema: device name, confidence, reasoning, estimated value, is_candidate_valuable. Claude Opus 4.5 supports structured outputs via OpenRouter. |
| Confidence scoring per identification | Not all identifications are equal -- blurry photo of a keyboard in a dark room vs. clear shot of a Roland JX-3P front panel | LOW | Part of the LLM prompt design. Ask for confidence as float 0-1 with reasoning. LLMs are reasonably well-calibrated on "how sure are you" when prompted correctly. |
| Price cap filtering (500 EUR) | Sellers who know what they have price above 500 EUR; filtering before LLM analysis saves API cost | LOW | Simple pre-filter on `price_eur` before sending to LLM. Already decided in PROJECT.md. |
| Generic search query generation | Must search mislabel terms and German-language generic queries to find listings where sellers don't know what they have | LOW | Deduplicate `common_mislabels` across all devices in schema.json, add hardcoded German generics ("alter Synthesizer", "Keyboard gebraucht", etc.). Straightforward string collection. |
| Separate results storage | Generic scan results have different shape (LLM analysis fields) and must not pollute device-specific scan results | LOW | Write to `results/generic_scan_DATE.json` with schema including LLM analysis fields alongside listing data. |
| Deduplication of listings | Same listing appears under multiple generic search queries; must not analyze (and pay for) the same listing twice | MEDIUM | Track seen listing URLs across queries within a scan run. Simple set-based dedup before LLM analysis. |

### Differentiators (Competitive Advantage)

Features that make this tool significantly more effective than manual browsing or basic keyword scrapers.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Schema-aware identification | LLM prompt includes the full device catalog (76 devices with brands, model names, year ranges, visual characteristics) so it can match against known valuable devices rather than guessing blindly | MEDIUM | Inject relevant schema data into the system prompt. The catalog is small enough (~76 devices) to fit in context. This is the key differentiator -- the LLM knows exactly which devices are valuable and what to look for. |
| Estimated value comparison | LLM identifies device, system looks up market price from schema.json, computes potential profit margin | LOW | After LLM returns identified device name, fuzzy-match against schema.json devices, pull `avg_market_price_eur`, compare to listing price. High-value output for the user. |
| Reasoning trace per listing | LLM explains WHY it thinks a listing is a specific device ("visible Roland logo, sliders match JX-3P layout, date-appropriate housing style") | LOW | Part of prompt design. Ask for `reasoning` field in structured output. Lets the user quickly validate whether to pursue a listing without re-analyzing the images themselves. |
| Multi-image analysis | Analyze all available images from a listing, not just the first one | MEDIUM | Some listings have 1 image, some have 10+. Side/back/detail shots may reveal model numbers, serial plates, or distinctive features not visible in the hero image. Must balance cost vs. coverage -- cap at 3-5 images. |
| Cross-reference with mislabel patterns | Use the `common_mislabels` and `missing_keywords` fields from schema.json to boost identification accuracy ("this listing says 'Roland keyboard' which is a known mislabel for JX-3P, JX-8P, Juno-106...") | LOW | Prompt engineering -- include mislabel context so the LLM can reason about which mislabel pattern this listing matches. |
| Dashboard integration for generic scan results | View LLM-analyzed generic scan results in the existing web dashboard with identification details, confidence scores, and estimated profit | MEDIUM | Extend `web.py` to load `generic_scan_*.json` files. New view showing: listing image, LLM identification, confidence, estimated value, profit margin, reasoning. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time continuous scanning | "I want to be first to find deals" | Bright Data costs per request, LLM API costs per analysis, Kleinanzeigen may rate-limit or block. Continuous scanning is expensive and unnecessary for a market where listings stay up for days/weeks. | Batch scanning on a schedule (daily or twice-daily). Deals on Kleinanzeigen don't disappear in minutes like eBay auctions. |
| Automatic purchasing/messaging | "Auto-contact the seller when a deal is found" | Legal/ethical issues with automated marketplace interactions, risk of account bans, seller communication requires human judgment (negotiation, asking about condition) | Surface deals to the user with all analysis; let them decide and contact manually. |
| Fine-tuned vision model for synths | "Train a custom model on synth images" | Massive effort, needs labeled training data (thousands of images per device), maintenance burden, and the general-purpose VLMs (Claude, GPT-4o) are already excellent at identifying products from images when given context | Use general-purpose VLM with rich prompt context (device catalog, mislabel patterns, visual descriptions). Prompt engineering beats fine-tuning for 76-device catalogs. |
| Price prediction / market trend analysis | "Predict what this synth will be worth next month" | Requires historical price data collection over months, complex modeling, and the existing schema.json market prices are sufficient reference points | Use static market prices from schema.json with periodic manual updates. The tool finds deals against known prices, not predicts future prices. |
| Analyzing listings above 500 EUR | "What if someone lists a 2000 EUR synth that's actually worth 5000 EUR?" | At higher prices, sellers almost always know what they have. LLM analysis cost scales linearly with listings analyzed. The value proposition is specifically about low-priced generic listings. | Keep the 500 EUR cap. If a user wants to explore higher-priced listings, they can use the existing device-specific scanner which already handles that. |
| OCR / text extraction from images | "Read model numbers and serial plates from photos" | Modern VLMs already do this natively -- they read text in images without separate OCR. Adding a separate OCR step adds complexity for no benefit. | Let the VLM handle text-in-image reading as part of its standard vision analysis. Claude and GPT-4o are excellent at reading text in photos. |

## Feature Dependencies

```
[Generic search query generation]
    |
    v
[Full listing page scraping]
    |
    v
[Deduplication of listings] -----> [Price cap filtering (500 EUR)]
    |                                       |
    v                                       v
[LLM vision analysis] <---- [Schema-aware identification prompt]
    |
    |---> [Structured JSON output]
    |         |
    |         v
    |     [Confidence scoring]
    |     [Reasoning trace]
    |
    v
[Estimated value comparison] (matches LLM output against schema.json)
    |
    v
[Separate results storage]
    |
    v
[Dashboard integration] (optional, enhances usability)
```

### Dependency Notes

- **LLM vision analysis requires full listing page scraping:** Can't analyze images you haven't fetched. The listing card thumbnails from search results are insufficient.
- **Structured JSON output requires LLM vision analysis:** The structured output is the format of the LLM response.
- **Estimated value comparison requires structured JSON output:** Must parse the identified device name to look up market price.
- **Deduplication must happen before LLM analysis:** Dedup saves API cost. Analyze each listing only once regardless of how many queries surfaced it.
- **Schema-aware identification enhances LLM analysis:** Providing the device catalog in the prompt dramatically improves identification accuracy. This is prompt design, not a separate feature, but is the single most important quality factor.
- **Dashboard integration requires separate results storage:** Can't display what isn't saved in a readable format.

## MVP Definition

### Launch With (v1)

Minimum viable: can the LLM actually identify devices from generic listings?

- [ ] Generic search query generation from deduplicated mislabels + German generics -- the input pipeline
- [ ] Full listing page scraping (high-res images + full description) -- the data collection
- [ ] Deduplication across queries -- cost control
- [ ] Price cap filtering at 500 EUR -- scope control
- [ ] LLM vision analysis with schema-aware prompt -- the core analysis
- [ ] Structured JSON output (device name, confidence, reasoning, estimated value, is_candidate_valuable) -- machine-readable results
- [ ] Estimated value comparison against schema.json market prices -- the deal signal
- [ ] Separate results file (generic_scan_DATE.json) -- persistence

### Add After Validation (v1.x)

Features to add once core identification quality is validated.

- [ ] Multi-image analysis (2-5 images per listing) -- triggered when single-image identification has low confidence or when listings commonly have revealing secondary images
- [ ] Dashboard view for generic scan results -- triggered when the batch of results is large enough that scanning JSON files manually is painful
- [ ] Confidence thresholds and filtering -- triggered when there are too many low-confidence results cluttering output
- [ ] Cost tracking per scan run (tokens used, estimated API cost) -- triggered when running regularly and needing to budget

### Future Consideration (v2+)

- [ ] Scheduled automated scans -- defer until manual runs prove the tool finds real deals worth pursuing
- [ ] Notification system (email/Telegram when high-confidence deals found) -- defer until scanning is automated
- [ ] Historical tracking of analyzed listings to avoid re-analyzing on subsequent runs -- defer until running frequently enough that overlap matters
- [ ] Expanding device catalog beyond 76 devices -- defer until current catalog coverage proves the concept

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| LLM vision analysis with schema-aware prompt | HIGH | HIGH | P1 |
| Full listing page scraping | HIGH | MEDIUM | P1 |
| Structured JSON output | HIGH | MEDIUM | P1 |
| Generic search query generation | HIGH | LOW | P1 |
| Deduplication of listings | MEDIUM | LOW | P1 |
| Price cap filtering | MEDIUM | LOW | P1 |
| Estimated value comparison | HIGH | LOW | P1 |
| Separate results storage | MEDIUM | LOW | P1 |
| Reasoning trace | HIGH | LOW | P1 |
| Confidence scoring | MEDIUM | LOW | P1 |
| Multi-image analysis | MEDIUM | MEDIUM | P2 |
| Dashboard integration | MEDIUM | MEDIUM | P2 |
| Cost tracking | LOW | LOW | P2 |
| Confidence threshold filtering | LOW | LOW | P2 |
| Scheduled scans | MEDIUM | MEDIUM | P3 |
| Notifications | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch -- these compose the end-to-end pipeline
- P2: Should have, add when the pipeline is proven
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Deals-Scraper (GitHub) | Apify FB Marketplace Deal Finder | eBay Deal Finder (Apify) | Our Approach |
|---------|------------------------|----------------------------------|--------------------------|--------------|
| Search by keywords | Yes, multi-platform | Yes, FB Marketplace only | Yes, eBay only | Yes, Kleinanzeigen.de with German-language queries |
| Price filtering | Min/max range | Yes | Yes | 500 EUR cap for generic queries |
| AI product identification | No -- keyword matching only | GPT-4o-mini for brand/model from title text | No | Claude Opus 4.5 vision analysis of IMAGES + description text |
| Visual analysis | No | No (text-only) | No | Yes -- this is the key differentiator. Most tools analyze titles; we analyze photos. |
| Domain-specific knowledge | No | Generic product categories | No | 76-device vintage synth catalog with market prices, mislabels, and visual characteristics |
| Value estimation | No | Compares to average sold prices | Compares active vs. sold prices | Compares to curated market prices per device from schema.json |
| Structured output | JSON file | Actor output | Actor output | Structured JSON with identification, confidence, reasoning, and profit estimate |
| Deal scoring | No scoring | Price comparison | Price comparison | Deal rating (steal/good_deal/market_price) reusing existing rating logic |

**Key insight:** Existing marketplace deal finders work on text (titles, prices). None use vision to identify what's actually IN the listing photos. This is our primary differentiator -- a listing titled "altes Keyboard 50 EUR" with a photo of a Roland Juno-106 is invisible to text-based tools but obvious to vision-based analysis.

## Sources

- [OpenRouter Structured Outputs documentation](https://openrouter.ai/docs/guides/features/structured-outputs) -- confirmed json_schema response_format support with strict mode
- [Claude Vision API documentation](https://platform.claude.com/docs/en/build-with-claude/vision) -- confirmed vision capabilities across Claude models
- [Claude Structured Outputs documentation](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) -- confirmed structured output support for Claude Opus/Sonnet
- [Deals-Scraper (GitHub)](https://github.com/JustSxm/Deals-Scraper) -- keyword-based deal scraper, no AI analysis
- [Apify Facebook Marketplace Deal Finder](https://apify.com/webdatalabs/facebook-marketplace-deal-finder) -- GPT-4o-mini for text-based product identification
- [Apify eBay Deal Finder](https://apify.com/barrierefix/ebay-deal-finder/api/mcp) -- price comparison without AI identification
- [Top 10 Vision Language Models 2026](https://dextralabs.com/blog/top-10-vision-language-models/) -- VLM landscape overview

---
*Feature research for: LLM-powered vintage synth identification on Kleinanzeigen.de*
*Researched: 2026-03-05*
