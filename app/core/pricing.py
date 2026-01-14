from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from app.config.logger import get_logger

LOGGER = get_logger("usage_service.pricing")

@dataclass(frozen=True)
class PricingConfig:
    """Pricing configuration for a single model in USD per 1M tokens."""

    model: str
    input_per_1m: float
    output_per_1m: float
    currency: str = "USD"


DEFAULT_PRICING: Dict[str, PricingConfig] = {
    # Google Gemini (Flash family) — token pricing per 1M (USD)
    # Reference: https://ai.google.dev/gemini-api/docs/pricing?hl=tr
    "gemini-2.5-flash": PricingConfig(
        model="gemini-2.5-flash",
        input_per_1m=0.10,
        output_per_1m=0.40,
    ),
    "gemini-3-flash-preview": PricingConfig(
        model="gemini-3-flash-preview",
        input_per_1m=0.10,
        output_per_1m=0.40,
    ),
    "gemini-2.5-flash-image": PricingConfig(
        model="gemini-2.5-flash-image",
        input_per_1m=0.10,
        output_per_1m=0.40,
    ),
    # Router/search/doc/ppt/pdf all use flash-tier pricing
    "gemini-router": PricingConfig(
        model="gemini-router",
        input_per_1m=0.10,
        output_per_1m=0.40,
    ),
    "gemini-search": PricingConfig(
        model="gemini-search",
        input_per_1m=0.10,
        output_per_1m=0.40,
    ),
    "gemini-doc": PricingConfig(
        model="gemini-doc",
        input_per_1m=0.10,
        output_per_1m=0.40,
    ),
    "gemini-pptx": PricingConfig(
        model="gemini-pptx",
        input_per_1m=0.10,
        output_per_1m=0.40,
    ),
    # Legacy entry kept for compatibility
    "gemini-1.5-pro": PricingConfig(
        model="gemini-1.5-pro",
        input_per_1m=3.50,
        output_per_1m=10.50,
    ),
    # OpenAI vision model (per 1M token-equivalent)
    "gpt-4-vision-preview": PricingConfig(
        model="gpt-4-vision-preview",
        input_per_1m=10.00,
        output_per_1m=30.00,
    ),
    # Fallback to keep existing mini entry
    "gpt-4o-mini": PricingConfig(
        model="gpt-4o-mini",
        input_per_1m=0.15,
        output_per_1m=0.60,
    ),
}


def calculate_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    pricing: Optional[Dict[str, PricingConfig]] = None,
) -> Tuple[float, float, float]:
    """Return (input_cost_usd, output_cost_usd, total_cost_usd).

    Raises:
        KeyError: if the model does not exist in pricing config.
    """

    pricing = pricing or DEFAULT_PRICING
    normalized = model.replace("models/", "", 1)
    if normalized not in pricing:
        LOGGER.warning(
            "Pricing model missing; returning zero cost",
            extra={"model": model, "normalized": normalized, "available": list(pricing.keys())},
        )
        return 0.0, 0.0, 0.0
    config = pricing[normalized]
    input_cost = (input_tokens / 1_000_000) * config.input_per_1m
    output_cost = (output_tokens / 1_000_000) * config.output_per_1m
    LOGGER.info(
        "Pricing calculated",
        extra={
            "model": model,
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "inputCost": input_cost,
            "outputCost": output_cost,
            "totalCost": input_cost + output_cost,
        },
    )
    return input_cost, output_cost, input_cost + output_cost
