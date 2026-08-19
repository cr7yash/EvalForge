from typing import Any, Dict, List
import time

from openai import AsyncOpenAI

from .base import LLMProvider, GenerationResult, GenerationConfig
from .portkey_catalog import find, models_for_family


class PortkeyProvider(LLMProvider):
    """
    Access models through the Portkey AI gateway.

    Portkey speaks the OpenAI chat-completions protocol for every upstream
    vendor, so a single client covers all of them. One instance is created per
    vendor family (openai, anthropic, google, ...) so the existing
    provider/model UI keeps working, with the gateway route hidden behind the
    catalog.

    Requests are assembled per model rather than uniformly: the gateway
    forwards unsupported parameters straight to the upstream vendor, which
    rejects them with a 400. See ``portkey_catalog`` for the measured matrix.
    """

    def __init__(self, family: str, api_key: str, base_url: str):
        """
        Args:
            family: Vendor family key, e.g. "openai" or "anthropic"
            api_key: Portkey API key
            base_url: Portkey gateway URL
        """
        self.family = family
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    @property
    def name(self) -> str:
        return self.family

    @property
    def available_models(self) -> List[str]:
        return [spec.slug for spec in models_for_family(self.family)]

    def _resolve(self, model: str):
        spec = find(self.family, model)
        if spec is None:
            raise ValueError(
                f"Unknown model '{model}' for provider '{self.family}'. "
                f"Available: {', '.join(self.available_models)}"
            )
        return spec

    async def generate(
        self,
        prompt: str,
        model: str,
        config: GenerationConfig | None = None,
        system_prompt: str | None = None
    ) -> GenerationResult:
        """Generate text through the Portkey gateway."""
        config = config or GenerationConfig()
        spec = self._resolve(model)
        caps = spec.caps

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Always max_completion_tokens: reasoning models reject max_tokens
        # outright, and every model on every route accepts this form.
        kwargs: Dict[str, Any] = {
            "model": spec.model_id,
            "messages": messages,
            "max_completion_tokens": max(config.max_tokens, caps.min_output_tokens),
        }
        if caps.temperature:
            kwargs["temperature"] = config.temperature
        if caps.top_p:
            kwargs["top_p"] = config.top_p
        if caps.stop and config.stop_sequences:
            kwargs["stop"] = config.stop_sequences
        if caps.reasoning_effort and config.reasoning_effort:
            kwargs["reasoning_effort"] = config.reasoning_effort

        start = time.perf_counter()
        response = await self.client.chat.completions.create(**kwargs)
        latency = (time.perf_counter() - start) * 1000

        choice = response.choices[0]
        usage = response.usage

        # Some routes return null content rather than an empty string.
        text = choice.message.content or ""

        # completion_tokens_details is absent on several upstream routes.
        details = getattr(usage, "completion_tokens_details", None)
        reasoning_tokens = getattr(details, "reasoning_tokens", 0) or 0

        return GenerationResult(
            text=text,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            latency_ms=latency,
            model=model,
            finish_reason=choice.finish_reason,
            reasoning_tokens=reasoning_tokens,
        )

    def is_priced(self, model: str) -> bool:
        """Whether list pricing is known for this model."""
        spec = find(self.family, model)
        return spec is not None and spec.pricing is not None

    def get_cost_per_1k_tokens(self, model: str) -> Dict[str, float]:
        """Pricing per 1K tokens, or zeros when unknown (see is_priced)."""
        spec = find(self.family, model)
        if spec is None or spec.pricing is None:
            return {"input": 0.0, "output": 0.0}
        return dict(spec.pricing)
