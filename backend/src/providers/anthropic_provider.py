from typing import List, Dict
import time
from anthropic import AsyncAnthropic
from .base import LLMProvider, GenerationResult, GenerationConfig


class AnthropicProvider(LLMProvider):
    """Anthropic LLM provider implementation."""

    PRICING = {
        "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
        "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
        "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.004},
    }

    def __init__(self, api_key: str | None = None):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key (if None, uses ANTHROPIC_API_KEY env var)
        """
        self.client = AsyncAnthropic(api_key=api_key)

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def available_models(self) -> List[str]:
        return list(self.PRICING.keys())

    async def generate(
        self,
        prompt: str,
        model: str,
        config: GenerationConfig | None = None,
        system_prompt: str | None = None
    ) -> GenerationResult:
        """Generate text using Anthropic API."""
        config = config or GenerationConfig()
        start = time.perf_counter()

        response = await self.client.messages.create(
            model=model,
            max_tokens=config.max_tokens,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}],
            temperature=config.temperature,
            top_p=config.top_p,
            stop_sequences=config.stop_sequences if config.stop_sequences else None,
        )
        latency = (time.perf_counter() - start) * 1000

        return GenerationResult(
            text=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency,
            model=model
        )

    def get_cost_per_1k_tokens(self, model: str) -> Dict[str, float]:
        """Get pricing for the specified model."""
        return self.PRICING.get(model, {"input": 0.0, "output": 0.0})
