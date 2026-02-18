from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pydantic import BaseModel, Field


class EvalExample(BaseModel):
    """An evaluation example with prompt and expected output."""
    id: str
    prompt: str
    expected_output: str | None = None
    context: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvalResult(BaseModel):
    """Result for a single evaluation example."""
    example_id: str
    metrics: Dict[str, float]
    details: Dict[str, Any] = Field(default_factory=dict)


class EvaluatorResult(BaseModel):
    """Results from running an evaluator on multiple examples."""
    evaluator_name: str
    results: List[EvalResult]
    aggregated_metrics: Dict[str, float]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseEvaluator(ABC):
    """Abstract base class for all evaluators."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Evaluator name (e.g., 'accuracy', 'performance')."""
        pass

    @property
    @abstractmethod
    def metrics(self) -> List[str]:
        """List of metric names this evaluator computes."""
        pass

    @abstractmethod
    async def evaluate(
        self,
        examples: List[EvalExample],
        responses: List[str],
        **kwargs
    ) -> EvaluatorResult:
        """
        Evaluate responses against examples.

        Args:
            examples: List of evaluation examples
            responses: LLM responses for each example
            **kwargs: Additional data (e.g., generation_results)

        Returns:
            EvaluatorResult with metrics
        """
        pass
