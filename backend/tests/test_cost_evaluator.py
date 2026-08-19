"""Tests for the cost evaluator's token and spend breakdown."""

import pytest

from src.evaluators.base import EvalExample
from src.evaluators.cost import CostEvaluator
from src.providers.base import GenerationResult


class FakeProvider:
    def __init__(self, pricing, priced=True):
        self._pricing = pricing
        self._priced = priced

    @property
    def name(self):
        return "fake"

    def get_cost_per_1k_tokens(self, model):
        return self._pricing

    def is_priced(self, model):
        return self._priced


PRICING = {"input": 0.001, "output": 0.002}


def make(input_tokens, output_tokens, reasoning_tokens=0):
    return GenerationResult(
        text="x", input_tokens=input_tokens, output_tokens=output_tokens,
        latency_ms=1.0, reasoning_tokens=reasoning_tokens,
    )


async def run(results, pricing=PRICING, priced=True):
    evaluator = CostEvaluator(FakeProvider(pricing, priced), "m")
    examples = [EvalExample(id=str(i), prompt="p") for i in range(len(results))]
    return await evaluator.evaluate(examples, ["x"] * len(results), results)


async def test_input_and_output_costs_are_reported_separately():
    out = await run([make(1000, 500)])
    agg = out.aggregated_metrics

    assert agg["input_cost_usd"] == pytest.approx(0.001)    # 1000/1000 * 0.001
    assert agg["output_cost_usd"] == pytest.approx(0.001)   # 500/1000 * 0.002
    assert agg["total_cost_usd"] == pytest.approx(0.002)


async def test_split_costs_always_sum_to_the_total():
    out = await run([make(700, 250), make(1234, 99)])
    agg = out.aggregated_metrics

    assert agg["input_cost_usd"] + agg["output_cost_usd"] == pytest.approx(
        agg["total_cost_usd"]
    )


async def test_token_counts_are_aggregated():
    out = await run([make(100, 20), make(50, 10)])
    agg = out.aggregated_metrics

    assert agg["input_tokens"] == 150
    assert agg["output_tokens"] == 30
    assert agg["total_tokens"] == 180


async def test_token_counts_are_whole_numbers():
    """
    They share a card with dollar values, so they must never render with
    fractional parts. The schema types metrics as float, so assert the value
    is integral rather than the Python type.
    """
    out = await run([make(100, 20)])
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        assert out.aggregated_metrics[key].is_integer()


async def test_per_example_metrics_include_tokens():
    out = await run([make(10, 5), make(20, 8)])

    first = out.results[0].metrics
    assert first["input_tokens"] == 10
    assert first["output_tokens"] == 5
    assert first["total_tokens"] == 15
    assert out.results[1].metrics["total_tokens"] == 28


async def test_reasoning_tokens_surface_per_example_and_in_total():
    out = await run([make(10, 100, reasoning_tokens=80)])

    assert out.results[0].details["reasoning_tokens"] == 80
    assert out.metadata["total_reasoning_tokens"] == 80


async def test_cost_per_example_divides_by_example_count():
    out = await run([make(1000, 0), make(1000, 0)])
    agg = out.aggregated_metrics

    assert agg["total_cost_usd"] == pytest.approx(0.002)
    assert agg["cost_per_example"] == pytest.approx(0.001)


async def test_unpriced_model_reports_zero_cost_but_real_tokens():
    out = await run([make(500, 300)], pricing={"input": 0.0, "output": 0.0},
                    priced=False)
    agg = out.aggregated_metrics

    assert agg["total_cost_usd"] == 0.0
    assert agg["total_tokens"] == 800          # tokens stay meaningful
    assert out.metadata["pricing_known"] is False
    assert "No list price" in out.metadata["pricing_note"]


async def test_declared_metrics_match_what_is_produced():
    evaluator = CostEvaluator(FakeProvider(PRICING), "m")
    out = await run([make(10, 5)])

    assert set(evaluator.metrics) == set(out.aggregated_metrics)
