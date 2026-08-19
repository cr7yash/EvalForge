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
        # Not every gateway model has a known list price. Track it so the
        # report can say "unpriced" instead of implying the run was free.
        is_priced = getattr(provider, "is_priced", None)
        self.pricing_known = (
            is_priced(model) if callable(is_priced)
            else any(self.pricing.values())
        )

    @property
    def name(self) -> str:
        return "cost"

    @property
    def metrics(self) -> List[str]:
        return [
            "total_cost_usd",
            "input_cost_usd",
            "output_cost_usd",
            "cost_per_1k_tokens",
            "cost_per_example",
            "input_tokens",
            "output_tokens",
            "total_tokens",
        ]

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
                metrics={
                    "cost_usd": example_cost,
                    "input_tokens": gen_result.input_tokens,
                    "output_tokens": gen_result.output_tokens,
                    "total_tokens": gen_result.total_tokens,
                },
                details={
                    "input_tokens": gen_result.input_tokens,
                    "output_tokens": gen_result.output_tokens,
                    "input_cost_usd": input_cost,
                    "output_cost_usd": output_cost,
                    # Reasoning tokens are billed as output but produce no
                    # visible text, so surface them separately.
                    "reasoning_tokens": gen_result.reasoning_tokens,
                }
            ))

        total_tokens = total_input + total_output
        input_cost = (total_input / 1000) * self.pricing["input"]
        output_cost = (total_output / 1000) * self.pricing["output"]
        total_cost = input_cost + output_cost

        aggregated = {
            "total_cost_usd": total_cost,
            "input_cost_usd": input_cost,
            "output_cost_usd": output_cost,
            "cost_per_1k_tokens": (total_cost / total_tokens * 1000) if total_tokens > 0 else 0,
            "cost_per_example": total_cost / len(examples) if examples else 0,
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_tokens,
        }

        return EvaluatorResult(
            evaluator_name=self.name,
            results=results,
            aggregated_metrics=aggregated,
            metadata={
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_reasoning_tokens": sum(
                    r.reasoning_tokens for r in generation_results
                ),
                "model": self.model,
                "pricing": self.pricing,
                "pricing_known": self.pricing_known,
                "pricing_note": (
                    None if self.pricing_known
                    else f"No list price on record for '{self.model}'; "
                         "cost figures are not meaningful for this model."
                )
            }
        )
