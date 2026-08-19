from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from dataclasses import dataclass


class GenerationConfig(BaseModel):
    """Configuration for text generation."""
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1000, ge=1, le=100000)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    stop_sequences: List[str] = Field(default_factory=list)
    reasoning_effort: str | None = Field(
        default=None,
        description="Reasoning budget hint; only sent to models that accept it."
    )


@dataclass
class GenerationResult:
    """Result from a text generation call."""
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    time_to_first_token_ms: float | None = None
    model: str = ""

    # Diagnostics. Reasoning models can consume the whole output budget on
    # hidden thinking and return no text at all; without these an empty
    # response is indistinguishable from a genuinely wrong answer.
    finish_reason: str | None = None
    reasoning_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self.input_tokens + self.output_tokens

    @property
    def truncated(self) -> bool:
        """Whether generation stopped because it hit the token cap."""
        return self.finish_reason == "length"

    @property
    def is_empty(self) -> bool:
        """Whether the model returned no usable text."""
        return not self.text.strip()


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'openai', 'anthropic')."""
        pass

    @property
    @abstractmethod
    def available_models(self) -> List[str]:
        """List of available model identifiers."""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        config: GenerationConfig | None = None,
        system_prompt: str | None = None
    ) -> GenerationResult:
        """
        Generate text from the LLM.

        Args:
            prompt: User prompt
            model: Model identifier
            config: Generation configuration
            system_prompt: Optional system prompt

        Returns:
            GenerationResult with text and metadata
        """
        pass

    def get_cost_per_1k_tokens(self, model: str) -> Dict[str, float]:
        """
        Get cost per 1K tokens for input and output.

        Args:
            model: Model identifier

        Returns:
            Dict with 'input' and 'output' costs in USD
        """
        return {"input": 0.0, "output": 0.0}
