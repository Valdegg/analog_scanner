# Stack Research

**Domain:** LLM-powered marketplace listing analysis (vision + structured output via OpenRouter)
**Researched:** 2026-03-05
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `openai` (Python SDK) | >=2.24.0 | OpenRouter API client | OpenRouter is explicitly OpenAI-compatible. The official SDK handles auth, retries, async, streaming, and structured output natively. No wrapper libraries needed. Already includes `httpx` as its HTTP transport. |
| `pydantic` | >=2.12.5 | Structured LLM output schemas | Define the LLM response shape (device name, confidence, reasoning, estimated value, is_candidate_valuable) as validated Python models. The OpenAI SDK's structured output support is built on Pydantic. |
| `python-dotenv` | (existing) | Load LLM_API_KEY, LLM_MODEL from .env | Already in the project. No change needed. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` | (bundled with openai) | Download listing images for base64 encoding | When fetching full-resolution images from listing pages before sending to LLM. No separate install needed -- `openai` depends on it already. Use `httpx.AsyncClient` for async image downloads. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| None new needed | Existing setup is sufficient | Project runs scripts directly with `python`. No build tooling required for this addition. |

## Core Integration Pattern

### OpenRouter via OpenAI SDK

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("LLM_API_KEY"),
)
```

The `LLM_MODEL` env var (currently `anthropic/claude-opus-4.5`) is passed as the `model` parameter. OpenRouter model IDs use `provider/model-name` format.

### Vision (Image Analysis)

Images are sent as base64-encoded data URLs in the message content array:

```python
import base64

# Download image (httpx comes with openai)
async with httpx.AsyncClient() as http:
    resp = await http.get(image_url)
    b64 = base64.b64encode(resp.content).decode("utf-8")

completion = await client.chat.completions.create(
    model=os.getenv("LLM_MODEL"),
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {
                "url": f"data:image/jpeg;base64,{b64}"
            }}
        ]
    }],
    response_format=response_format,
)
```

**Why base64 instead of image URLs:** Kleinanzeigen.de image URLs may require authentication or have anti-hotlinking protections. Downloading via the scraper's existing infrastructure and encoding to base64 is more reliable. Also avoids the LLM provider needing to fetch from a potentially geo-restricted German site.

### Structured Output

Use `response_format` with `json_schema` type -- this is OpenRouter's supported approach:

```python
response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "listing_analysis",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "identified_device": {"type": "string", "description": "Specific device name identified"},
                "confidence": {"type": "number", "description": "0.0-1.0 confidence in identification"},
                "reasoning": {"type": "string", "description": "Why this identification was made"},
                "estimated_value_eur": {"type": "number", "description": "Estimated market value in EUR"},
                "is_candidate_valuable": {"type": "boolean", "description": "True if listing is a potential underpriced find"},
            },
            "required": ["identified_device", "confidence", "reasoning", "estimated_value_eur", "is_candidate_valuable"],
            "additionalProperties": False,
        }
    }
}
```

**Important:** Do NOT use `client.beta.chat.completions.parse()` -- this is an OpenAI-specific beta method that is not reliably supported through OpenRouter's proxy. Use the standard `client.chat.completions.create()` with `response_format` parameter instead. Parse the JSON string from `completion.choices[0].message.content` with `json.loads()`, then validate with Pydantic if desired.

**Pydantic integration pattern** (optional but recommended for validation):

```python
from pydantic import BaseModel

class ListingAnalysis(BaseModel):
    identified_device: str
    confidence: float
    reasoning: str
    estimated_value_eur: float
    is_candidate_valuable: bool

# After getting completion:
raw = json.loads(completion.choices[0].message.content)
result = ListingAnalysis(**raw)  # Validates types
```

## Installation

```bash
# New dependencies only (add to requirements.txt)
pip install openai>=2.24.0 pydantic>=2.12.5
```

That is it. `httpx` comes bundled with `openai`. `python-dotenv` is already installed. No other new dependencies needed.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `openai` SDK directly | `instructor` library (v1.14.5) | If you need automatic retry-on-validation-failure or complex nested extraction. For this project, the schema is simple (5 flat fields) and OpenRouter's native structured output is sufficient. Instructor adds a dependency and abstraction layer that is unnecessary here. |
| `openai` SDK directly | `litellm` | If you plan to switch between many LLM providers with different APIs. OpenRouter already handles multi-provider routing, making litellm redundant. |
| `openai` SDK directly | `langchain` | Never for this use case. Massive dependency tree, abstractions add complexity without value for a single API call pattern. |
| `response_format` (json_schema) | `response_format` (json_object) | `json_object` mode only guarantees valid JSON, not schema adherence. Use `json_schema` for guaranteed field structure. |
| Base64 image encoding | Passing image URL directly | Only if images are publicly accessible without auth. Kleinanzeigen.de images may not be. Base64 is more reliable. |
| `AsyncOpenAI` | `OpenAI` (sync) | Only if integrating into sync-only code. The existing scanner is async (Playwright), so use `AsyncOpenAI` to match. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `langchain` / `langchain-openai` | Enormous dependency tree (100+ packages), unnecessary abstraction for a straightforward API call. Slower iteration, harder debugging. | `openai` SDK directly |
| `requests` for image downloads | The project is async. `requests` is synchronous and would block the event loop. | `httpx` (already bundled with `openai`) |
| `client.beta.chat.completions.parse()` | OpenAI-specific beta endpoint. Not guaranteed to work through OpenRouter's proxy layer. May break silently. | `client.chat.completions.create()` with `response_format` parameter |
| `instructor` | Adds unnecessary abstraction for a 5-field flat schema. Its value is in complex nested extraction with retries. Overkill here. | Direct `response_format` + Pydantic validation |
| `anthropic` SDK | Anthropic's native SDK uses a different API format. Since we route through OpenRouter (OpenAI-compatible), use `openai` SDK. | `openai` SDK with OpenRouter base_url |
| `aiohttp` for HTTP | `httpx` is already a transitive dependency via `openai`. Adding `aiohttp` duplicates functionality. | `httpx.AsyncClient` |

## Stack Patterns by Variant

**If LLM_MODEL changes to a model without structured output support:**
- Fall back to `response_format: {"type": "json_object"}` with schema instructions in the prompt
- Add JSON parsing with try/except and manual validation
- Check model capabilities on OpenRouter's models page first

**If image analysis quality is poor with current model:**
- Switch `LLM_MODEL` in `.env` to a stronger vision model (e.g., `google/gemini-2.5-pro`)
- No code changes needed -- the model is read from env
- OpenRouter handles routing to the right provider

**If token costs become a concern:**
- Resize images before base64 encoding (e.g., max 1024px wide) to reduce input tokens
- Use `detail: "low"` in image_url to request lower-resolution processing (if model supports it)
- Consider cheaper models for initial screening, expensive models for high-confidence candidates

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `openai>=2.24.0` | Python 3.9+ | Requires `httpx`, `pydantic` (both auto-installed as dependencies) |
| `pydantic>=2.12.5` | Python 3.9+ | `openai` SDK already depends on pydantic, but pinning ensures compatible version |
| `httpx` (via openai) | Python 3.9+ | No separate install. Async support built in. |
| Existing stack (playwright, bs4, flask) | No conflicts | `openai` and `pydantic` have no known conflicts with any existing dependencies |

## Cost Considerations

| Model (via OpenRouter) | Input (per 1M tokens) | Output (per 1M tokens) | Image cost | Notes |
|------------------------|----------------------|------------------------|------------|-------|
| anthropic/claude-opus-4.5 | $3.00 | $15.00 | ~$0.0048/image | Currently configured. Strong vision + reasoning. |
| anthropic/claude-sonnet-4 | $3.00 | $15.00 | ~$0.0048/image | Similar pricing, good alternative. |
| google/gemini-2.5-flash | Much cheaper | Much cheaper | Varies | Good for high-volume screening if cost is a concern. |

OpenRouter adds a 5.5% platform fee on top of model pricing.

**Estimated cost per generic scan run:** With ~50-100 listings at ~1 image each, expect $0.50-$2.00 per scan run with Claude Opus 4.5. Manageable for batch usage.

## Sources

- [OpenRouter Quickstart](https://openrouter.ai/docs/quickstart) -- Python SDK integration pattern (HIGH confidence)
- [OpenRouter Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs) -- json_schema response_format support (HIGH confidence)
- [OpenAI Python SDK on PyPI](https://pypi.org/project/openai/) -- v2.24.0, Python 3.9+ (HIGH confidence)
- [Pydantic on PyPI](https://pypi.org/project/pydantic/) -- v2.12.5 stable (HIGH confidence)
- [OpenAI Vision docs](https://developers.openai.com/api/docs/guides/images-vision/) -- base64 image format (HIGH confidence)
- [Instructor + OpenRouter guide](https://python.useinstructor.com/integrations/openrouter/) -- evaluated and rejected for this use case (MEDIUM confidence)
- [OpenRouter pricing](https://openrouter.ai/pricing) -- Claude Sonnet 4.5 pricing (MEDIUM confidence, prices change)
- [OpenAI SDK GitHub releases](https://github.com/openai/openai-python/releases) -- version history (HIGH confidence)

---
*Stack research for: LLM-powered marketplace listing analysis*
*Researched: 2026-03-05*
