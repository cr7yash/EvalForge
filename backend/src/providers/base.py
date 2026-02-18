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


@dataclass
class GenerationResult:
    """Result from a text generation call."""
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    time_to_first_token_ms: float | None = None
    model: str = ""

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self.input_tokens + self.output_tokens


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
