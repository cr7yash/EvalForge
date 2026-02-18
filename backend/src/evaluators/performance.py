import numpy as np
from typing import List
from ..providers.base import GenerationResult
from .base import BaseEvaluator, EvalExample, EvalResult, EvaluatorResult


class PerformanceEvaluator(BaseEvaluator):
    """Evaluates performance metrics (latency, throughput)."""

    @property
    def name(self) -> str:
        return "performance"

    @property
    def metrics(self) -> List[str]:
        return ["mean_latency_ms", "p50_latency_ms", "p95_latency_ms", "p99_latency_ms", "tokens_per_second"]

    async def evaluate(
        self,
        examples: List[EvalExample],
        responses: List[str],
        generation_results: List[GenerationResult] | None = None,
        **kwargs
    ) -> EvaluatorResult:
        """Evaluate performance metrics from generation results."""
        if not generation_results:
            raise ValueError("PerformanceEvaluator requires generation_results")

        latencies = [r.latency_ms for r in generation_results]
        token_rates = [
            r.output_tokens / (r.latency_ms / 1000)
            for r in generation_results
            if r.latency_ms > 0
        ]

        results = []
        for example, gen_result in zip(examples, generation_results):
            results.append(EvalResult(
                example_id=example.id,
                metrics={
                    "latency_ms": gen_result.latency_ms,
                    "tokens_per_second": gen_result.output_tokens / (gen_result.latency_ms / 1000) if gen_result.latency_ms > 0 else 0.0
                },
                details={
                    "input_tokens": gen_result.input_tokens,
                    "output_tokens": gen_result.output_tokens
                }
            ))

        aggregated = {
            "mean_latency_ms": float(np.mean(latencies)),
            "p50_latency_ms": float(np.percentile(latencies, 50)),
            "p95_latency_ms": float(np.percentile(latencies, 95)),
            "p99_latency_ms": float(np.percentile(latencies, 99)),
            "tokens_per_second": float(np.mean(token_rates)) if token_rates else 0.0
        }

        return EvaluatorResult(
            evaluator_name=self.name,
            results=results,
            aggregated_metrics=aggregated
        )
