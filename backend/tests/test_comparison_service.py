"""
Tests for side-by-side model comparison.

Three things matter here that a normal evaluation doesn't need to worry
about: the concurrency bound must apply across *all* models in the
comparison combined rather than per model, one model failing must not take
down the others, and winner selection must never let an unpriced model's
implied $0.00 beat a model with real pricing.
"""

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import Settings
from src.core.database import Base
from src.models.evaluation import (
    Comparison,
    ComparisonCreate,
    ComparisonModelSpec,
    Evaluation,
    EvaluationStatus,
)
from src.providers.base import GenerationResult
from src.services import comparison_service as comparison_service_module
from src.services.comparison_service import ComparisonService
from src.services.eval_service import EvaluationService


# ---------------------------------------------------------------------------
# ComparisonCreate validation
# ---------------------------------------------------------------------------

def test_requires_at_least_two_models():
    with pytest.raises(ValidationError):
        ComparisonCreate(
            name="x",
            models=[ComparisonModelSpec(provider="openai", model="gpt-4o-mini")],
            evaluators=["accuracy"],
            examples=[{"prompt": "hi"}],
        )


def test_allows_at_most_five_models():
    models = [ComparisonModelSpec(provider="openai", model=f"m{i}") for i in range(6)]
    with pytest.raises(ValidationError):
        ComparisonCreate(name="x", models=models, evaluators=["accuracy"],
                         examples=[{"prompt": "hi"}])


def test_rejects_duplicate_model_pairs():
    models = [ComparisonModelSpec(provider="openai", model="gpt-4o-mini")] * 2
    with pytest.raises(ValidationError, match="unique"):
        ComparisonCreate(name="x", models=models, evaluators=["accuracy"],
                         examples=[{"prompt": "hi"}])


def test_accepts_two_to_five_distinct_models():
    models = [ComparisonModelSpec(provider="openai", model=f"m{i}") for i in range(3)]
    created = ComparisonCreate(name="x", models=models, evaluators=["accuracy"],
                               examples=[{"prompt": "hi"}])
    assert len(created.models) == 3


# ---------------------------------------------------------------------------
# compute_winners: pure function, no DB or provider involved
# ---------------------------------------------------------------------------

def child(id_, status=EvaluationStatus.COMPLETED, results=None):
    return SimpleNamespace(id=id_, status=status, results=results)


def cost_result(total, pricing_known=True):
    return {
        "aggregated_metrics": {
            "total_cost_usd": total,
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
        },
        "metadata": {"pricing_known": pricing_known},
    }


def perf_result(latency):
    return {
        "aggregated_metrics": {
            "mean_latency_ms": latency,
            "tokens_per_second": 1000 / latency,
        },
        "metadata": {},
    }


def accuracy_result(score):
    return {"aggregated_metrics": {"exact_match": score}, "metadata": {}}


def test_lower_latency_wins():
    svc = ComparisonService()
    winners = svc.compute_winners([
        child("a", results={"performance": perf_result(100)}),
        child("b", results={"performance": perf_result(50)}),
    ])
    assert winners["mean_latency_ms"] == "b"


def test_higher_throughput_wins():
    svc = ComparisonService()
    winners = svc.compute_winners([
        child("a", results={"performance": perf_result(100)}),  # 10 tok/s
        child("b", results={"performance": perf_result(50)}),   # 20 tok/s
    ])
    assert winners["tokens_per_second"] == "b"


def test_higher_accuracy_wins():
    svc = ComparisonService()
    winners = svc.compute_winners([
        child("a", results={"accuracy": accuracy_result(0.5)}),
        child("b", results={"accuracy": accuracy_result(0.9)}),
    ])
    assert winners["exact_match"] == "b"


def test_lower_cost_wins_among_priced_models():
    svc = ComparisonService()
    winners = svc.compute_winners([
        child("a", results={"cost": cost_result(0.002)}),
        child("b", results={"cost": cost_result(0.001)}),
    ])
    assert winners["total_cost_usd"] == "b"


def test_token_counts_never_get_a_winner():
    """More or fewer tokens is neither better nor worse; never highlighted."""
    svc = ComparisonService()
    winners = svc.compute_winners([
        child("a", results={"cost": cost_result(0.001)}),
        child("b", results={"cost": cost_result(0.002)}),
    ])
    for metric in ("input_tokens", "output_tokens", "total_tokens"):
        assert metric not in winners


def test_unpriced_model_excluded_from_cost_winner():
    """
    A model with no known list price reports $0.00, which would otherwise
    win every cost row. With only one priced candidate remaining, there is
    nothing to compare it against, so no winner is marked at all.
    """
    svc = ComparisonService()
    winners = svc.compute_winners([
        child("a", results={"cost": cost_result(0.0, pricing_known=False)}),
        child("b", results={"cost": cost_result(0.002, pricing_known=True)}),
    ])
    assert winners["total_cost_usd"] is None


def test_unpriced_model_excluded_even_when_others_can_still_be_compared():
    svc = ComparisonService()
    winners = svc.compute_winners([
        child("a", results={"cost": cost_result(0.0, pricing_known=False)}),
        child("b", results={"cost": cost_result(0.002, pricing_known=True)}),
        child("c", results={"cost": cost_result(0.003, pricing_known=True)}),
    ])
    assert winners["total_cost_usd"] == "b"  # cheapest priced model, not a's fake $0


def test_failed_models_excluded_from_every_metric():
    svc = ComparisonService()
    winners = svc.compute_winners([
        child("a", status=EvaluationStatus.FAILED, results=None),
        child("b", results={"performance": perf_result(50)}),
    ])
    assert winners.get("mean_latency_ms") is None


def test_all_models_tied_produces_no_winner():
    """
    Four models all scoring 0.0 is the common real case (a prompt none of
    them got right). Crowning whichever sorted first presented an arbitrary
    pick as the best result.
    """
    svc = ComparisonService()
    winners = svc.compute_winners([
        child("a", results={"accuracy": accuracy_result(0.0)}),
        child("b", results={"accuracy": accuracy_result(0.0)}),
        child("c", results={"accuracy": accuracy_result(0.0)}),
        child("d", results={"accuracy": accuracy_result(0.0)}),
    ])
    assert winners["exact_match"] is None


def test_tie_for_best_produces_no_winner_even_when_others_are_worse():
    svc = ComparisonService()
    winners = svc.compute_winners([
        child("a", results={"accuracy": accuracy_result(0.9)}),
        child("b", results={"accuracy": accuracy_result(0.9)}),
        child("c", results={"accuracy": accuracy_result(0.2)}),
    ])
    assert winners["exact_match"] is None


def test_tie_below_the_winner_still_leaves_a_winner():
    """Only a tie *for first place* removes the winner."""
    svc = ComparisonService()
    winners = svc.compute_winners([
        child("a", results={"accuracy": accuracy_result(0.9)}),
        child("b", results={"accuracy": accuracy_result(0.5)}),
        child("c", results={"accuracy": accuracy_result(0.5)}),
    ])
    assert winners["exact_match"] == "a"


def test_tie_on_lower_is_better_metric_produces_no_winner():
    svc = ComparisonService()
    winners = svc.compute_winners([
        child("a", results={"performance": perf_result(100)}),
        child("b", results={"performance": perf_result(100)}),
    ])
    assert winners["mean_latency_ms"] is None


def test_no_winner_with_only_one_comparable_value():
    svc = ComparisonService()
    winners = svc.compute_winners([child("a", results={"performance": perf_result(50)})])
    assert winners["mean_latency_ms"] is None


def test_no_children_produces_no_winners():
    assert ComparisonService().compute_winners([]) == {}


# ---------------------------------------------------------------------------
# build() + run(): a real (temp file) SQLite DB, a fake provider standing in
# for the network. Only the "performance" evaluator is used so tests don't
# pull in the SentenceTransformer accuracy depends on.
# ---------------------------------------------------------------------------

class Tracker:
    def __init__(self):
        self.in_flight = 0
        self.max_in_flight = 0


class TrackedProvider:
    """Fake provider that records peak concurrency and can fail on demand."""

    def __init__(self, name, tracker, delay=0.03, fail_models=None):
        self._name = name
        self.tracker = tracker
        self.delay = delay
        self.fail_models = fail_models or set()

    @property
    def name(self):
        return self._name

    def get_cost_per_1k_tokens(self, model):
        return {"input": 0.0, "output": 0.0}

    async def generate(self, prompt, model, config=None, system_prompt=None):
        if model in self.fail_models:
            raise RuntimeError(f"synthetic failure for {model}")
        self.tracker.in_flight += 1
        self.tracker.max_in_flight = max(self.tracker.max_in_flight, self.tracker.in_flight)
        try:
            await asyncio.sleep(self.delay)
        finally:
            self.tracker.in_flight -= 1
        return GenerationResult(
            text=f"answer for {model}", input_tokens=5, output_tokens=3,
            latency_ms=1.0, model=model, finish_reason="stop",
        )


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    """An isolated SQLite file, with comparison_service.SessionLocal
    redirected to it so run()'s background-task session lands here too."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(comparison_service_module, "SessionLocal", factory)
    return factory


def make_service(tracker, max_concurrent=8, delay=0.03, fail_models=None):
    svc = ComparisonService()
    svc.settings = Settings(max_concurrent_requests=max_concurrent, _env_file=None)
    svc.eval_service._get_provider = lambda name: TrackedProvider(
        name, tracker, delay=delay, fail_models=fail_models
    )
    return svc


async def test_shared_semaphore_bounds_total_concurrency_across_models(session_factory):
    """
    5 models x 4 examples = 20 calls. A per-model semaphore would allow up
    to 5x the configured limit in flight at once; the whole point of sharing
    one semaphore across every child evaluation is that total in-flight
    requests stays at max_concurrent_requests regardless of model count.
    """
    tracker = Tracker()
    svc = make_service(tracker, max_concurrent=4, delay=0.05)

    db = session_factory()
    examples = [{"id": str(i), "prompt": f"p{i}"} for i in range(4)]
    models = [{"provider": "openai", "model": f"m{i}"} for i in range(5)]
    comparison = svc.build(db, "bounded", models, ["performance"], examples, None)
    db.close()

    await svc.run(comparison.id)

    assert tracker.max_in_flight <= 4


async def test_partial_failure_leaves_other_models_completed(session_factory):
    tracker = Tracker()
    svc = make_service(tracker, fail_models={"bad-model"})

    db = session_factory()
    examples = [{"id": "1", "prompt": "hi"}]
    models = [
        {"provider": "openai", "model": "good-1"},
        {"provider": "openai", "model": "bad-model"},
        {"provider": "openai", "model": "good-2"},
    ]
    comparison = svc.build(db, "partial", models, ["performance"], examples, None)
    db.close()

    await svc.run(comparison.id)

    db2 = session_factory()
    refreshed = db2.query(Comparison).filter(Comparison.id == comparison.id).first()
    children = {
        c.model: c
        for c in db2.query(Evaluation).filter(Evaluation.comparison_id == comparison.id)
    }

    assert refreshed.status == EvaluationStatus.COMPLETED
    assert children["good-1"].status == EvaluationStatus.COMPLETED
    assert children["good-2"].status == EvaluationStatus.COMPLETED
    assert children["bad-model"].status == EvaluationStatus.FAILED
    assert "bad-model" in children["bad-model"].error
    db2.close()


async def test_total_failure_marks_comparison_failed(session_factory):
    tracker = Tracker()
    svc = make_service(tracker, fail_models={"bad-1", "bad-2"})

    db = session_factory()
    examples = [{"id": "1", "prompt": "hi"}]
    models = [
        {"provider": "openai", "model": "bad-1"},
        {"provider": "openai", "model": "bad-2"},
    ]
    comparison = svc.build(db, "total fail", models, ["performance"], examples, None)
    db.close()

    await svc.run(comparison.id)

    db2 = session_factory()
    refreshed = db2.query(Comparison).filter(Comparison.id == comparison.id).first()
    assert refreshed.status == EvaluationStatus.FAILED
    assert "failed" in refreshed.error.lower()
    db2.close()


async def test_build_creates_one_pending_evaluation_per_model(session_factory):
    tracker = Tracker()
    svc = make_service(tracker)

    db = session_factory()
    examples = [{"id": "1", "prompt": "hi"}]
    models = [
        {"provider": "openai", "model": "m1"},
        {"provider": "openai", "model": "m2"},
        {"provider": "anthropic", "model": "m3"},
    ]
    comparison = svc.build(db, "fresh", models, ["performance"], examples, None)

    children = (
        db.query(Evaluation).filter(Evaluation.comparison_id == comparison.id).all()
    )
    assert len(children) == 3
    assert all(c.status == EvaluationStatus.PENDING for c in children)
    assert all(c.progress == 0.0 for c in children)
    assert comparison.status == EvaluationStatus.PENDING
    db.close()


# ---------------------------------------------------------------------------
# Progress persistence: the mechanism a polling client relies on
# ---------------------------------------------------------------------------

async def test_on_progress_fires_incrementally_not_just_at_the_end():
    """
    The comparison runner commits inside on_progress so a polling client can
    observe partial progress mid-run. Confirm the hook fires as each example
    finishes and again as each evaluator finishes, with progress increasing
    monotonically to completion -- not a single call once everything is done.
    """
    tracker = Tracker()
    provider = TrackedProvider("openai", tracker, delay=0.01)
    service = EvaluationService()
    service._get_provider = lambda name: provider

    evaluation = Evaluation(
        id="e1", name="t", provider="openai", model="m",
        evaluators=["performance"],
        examples=[{"id": str(i), "prompt": f"p{i}"} for i in range(4)],
        config={}, status=EvaluationStatus.PENDING, progress=0.0,
    )

    snapshots = []
    await service._execute(evaluation, on_progress=lambda: snapshots.append(evaluation.progress))

    assert len(snapshots) >= 4          # at least one per generated example
    assert snapshots == sorted(snapshots)
    assert snapshots[-1] == 1.0
    assert evaluation.status == EvaluationStatus.COMPLETED
