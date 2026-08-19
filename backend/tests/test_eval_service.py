"""
Tests for evaluation orchestration.

The focus is concurrent generation: results must stay aligned with their
examples even when calls finish out of order, concurrency must stay bounded,
and warnings must be reported in example order rather than completion order.
"""

import asyncio

import pytest

from src.core.config import Settings
from src.providers.base import GenerationConfig, GenerationResult
from src.evaluators.base import EvalExample
from src.services.eval_service import EvaluationService


class FakeProvider:
    """Provider that records concurrency and can vary per-call duration."""

    def __init__(self, delays=None, texts=None, finish_reasons=None):
        self.delays = delays or {}
        self.texts = texts or {}
        self.finish_reasons = finish_reasons or {}
        self.in_flight = 0
        self.max_in_flight = 0
        self.calls = []

    @property
    def name(self):
        return "fake"

    async def generate(self, prompt, model, config=None, system_prompt=None):
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        self.calls.append(prompt)
        try:
            await asyncio.sleep(self.delays.get(prompt, 0.01))
        finally:
            self.in_flight -= 1
        return GenerationResult(
            text=self.texts.get(prompt, f"answer-{prompt}"),
            input_tokens=5,
            output_tokens=3,
            latency_ms=1.0,
            model=model,
            finish_reason=self.finish_reasons.get(prompt, "stop"),
        )


def make_service(max_concurrent=8):
    service = EvaluationService()
    service.settings = Settings(
        portkey_api_key="test", max_concurrent_requests=max_concurrent,
        _env_file=None,
    )
    return service


def examples(*prompts):
    return [EvalExample(id=str(i), prompt=p) for i, p in enumerate(prompts)]


class DummyEvaluation:
    progress = 0.0


async def generate(service, provider, exs):
    return await service._generate_all(
        provider, "test-model", GenerationConfig(), exs, DummyEvaluation()
    )


async def test_generation_runs_concurrently():
    """Four 100ms calls should take ~100ms in total, not ~400ms."""
    provider = FakeProvider(delays={p: 0.1 for p in "abcd"})
    service = make_service()

    start = asyncio.get_running_loop().time()
    await generate(service, provider, examples(*"abcd"))
    elapsed = asyncio.get_running_loop().time() - start

    assert elapsed < 0.25, f"took {elapsed:.2f}s — looks serial"
    assert provider.max_in_flight == 4


async def test_results_keep_example_order_despite_completion_order():
    """The slowest call is first; its result must still come back first."""
    provider = FakeProvider(delays={"a": 0.15, "b": 0.01, "c": 0.05})
    service = make_service()

    results = await generate(service, provider, examples("a", "b", "c"))

    assert [r.text for r in results] == ["answer-a", "answer-b", "answer-c"]


async def test_concurrency_is_bounded_by_the_setting():
    provider = FakeProvider(delays={str(i): 0.05 for i in range(20)})
    service = make_service(max_concurrent=3)

    await generate(service, provider, examples(*[str(i) for i in range(20)]))

    assert provider.max_in_flight <= 3


async def test_every_example_is_generated_exactly_once():
    provider = FakeProvider()
    service = make_service()

    await generate(service, provider, examples(*"abcdef"))

    assert sorted(provider.calls) == list("abcdef")


async def test_progress_reaches_the_generation_share():
    provider = FakeProvider()
    service = make_service()
    evaluation = DummyEvaluation()

    await service._generate_all(
        provider, "m", GenerationConfig(), examples(*"abcd"), evaluation
    )

    assert evaluation.progress == pytest.approx(0.7)


async def test_a_failing_call_propagates():
    class Boom(FakeProvider):
        async def generate(self, prompt, model, config=None, system_prompt=None):
            if prompt == "b":
                raise RuntimeError("upstream 500")
            return await super().generate(prompt, model, config, system_prompt)

    service = make_service()
    with pytest.raises(RuntimeError, match="upstream 500"):
        await generate(service, Boom(), examples("a", "b", "c"))


def test_warnings_follow_example_order():
    exs = examples("a", "b", "c")
    results = [
        GenerationResult(text="fine", input_tokens=1, output_tokens=1,
                         latency_ms=1.0, finish_reason="stop"),
        GenerationResult(text="", input_tokens=1, output_tokens=64,
                         latency_ms=1.0, finish_reason="stop",
                         reasoning_tokens=64),
        GenerationResult(text="cut", input_tokens=1, output_tokens=9,
                         latency_ms=1.0, finish_reason="length"),
    ]

    warnings = EvaluationService._collect_warnings(exs, results)

    assert len(warnings) == 2
    assert warnings[0].startswith("Example 1:")
    assert "reasoning" in warnings[0]
    assert warnings[1].startswith("Example 2:")
    assert "cut off" in warnings[1]


def test_no_warnings_when_every_response_is_clean():
    exs = examples("a", "b")
    results = [
        GenerationResult(text="ok", input_tokens=1, output_tokens=1,
                         latency_ms=1.0, finish_reason="stop")
        for _ in exs
    ]
    assert EvaluationService._collect_warnings(exs, results) == []
