from typing import List, Dict
import time
from openai import AsyncOpenAI
from .base import LLMProvider, GenerationResult, GenerationConfig


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider implementation."""

    PRICING = {
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    }

    def __init__(self, api_key: str | None = None):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (if None, uses OPENAI_API_KEY env var)
        """
        self.client = AsyncOpenAI(api_key=api_key)

    @property
    def name(self) -> str:
        return "openai"

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
        """Generate text using OpenAI API."""
        config = config or GenerationConfig()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start = time.perf_counter()
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            stop=config.stop_sequences if config.stop_sequences else None,
        )
        latency = (time.perf_counter() - start) * 1000

        return GenerationResult(
            text=response.choices[0].message.content or "",
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            latency_ms=latency,
            model=model
        )

    def get_cost_per_1k_tokens(self, model: str) -> Dict[str, float]:
        """Get pricing for the specified model."""
        return self.PRICING.get(model, {"input": 0.0, "output": 0.0})
