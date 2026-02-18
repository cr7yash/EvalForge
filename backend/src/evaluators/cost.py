from typing import List
from ..providers.base import LLMProvider, GenerationResult
from .base import BaseEvaluator, EvalExample, EvalResult, EvaluatorResult


class CostEvaluator(BaseEvaluator):
    """Evaluates cost metrics based on token usage."""

    def __init__(self, provider: LLMProvider, model: str):
        """
        Initialize cost evaluator.

        Args:
            provider: LLM provider for pricing information
            model: Model identifier
        """
        self.provider = provider
        self.model = model
        self.pricing = provider.get_cost_per_1k_tokens(model)

    @property
    def name(self) -> str:
        return "cost"

    @property
    def metrics(self) -> List[str]:
        return ["total_cost_usd", "cost_per_1k_tokens", "cost_per_example"]

    async def evaluate(
        self,
        examples: List[EvalExample],
        responses: List[str],
        generation_results: List[GenerationResult] | None = None,
        **kwargs
    ) -> EvaluatorResult:
        """Evaluate cost metrics from generation results."""
        if not generation_results:
            raise ValueError("CostEvaluator requires generation_results")

        results = []
        total_input = 0
        total_output = 0

        for example, gen_result in zip(examples, generation_results):
            input_cost = (gen_result.input_tokens / 1000) * self.pricing["input"]
            output_cost = (gen_result.output_tokens / 1000) * self.pricing["output"]
            example_cost = input_cost + output_cost

            total_input += gen_result.input_tokens
            total_output += gen_result.output_tokens

            results.append(EvalResult(
                example_id=example.id,
                metrics={"cost_usd": example_cost},
                details={
                    "input_tokens": gen_result.input_tokens,
                    "output_tokens": gen_result.output_tokens,
                    "input_cost_usd": input_cost,
                    "output_cost_usd": output_cost
                }
            ))

        total_tokens = total_input + total_output
        total_cost = (
            (total_input / 1000) * self.pricing["input"] +
            (total_output / 1000) * self.pricing["output"]
        )

        aggregated = {
            "total_cost_usd": total_cost,
            "cost_per_1k_tokens": (total_cost / total_tokens * 1000) if total_tokens > 0 else 0,
            "cost_per_example": total_cost / len(examples) if examples else 0,
        }

        return EvaluatorResult(
            evaluator_name=self.name,
            results=results,
            aggregated_metrics=aggregated,
            metadata={
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "model": self.model,
                "pricing": self.pricing
            }
        )
