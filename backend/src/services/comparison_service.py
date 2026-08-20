import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import SessionLocal
from ..models.evaluation import Comparison, Evaluation, EvaluationStatus
from .eval_service import EvaluationService


class ComparisonService:
    """
    Runs the same prompts against 2-5 models concurrently and ranks them.

    Each model is a normal Evaluation row (linked back via
    Evaluation.comparison_id), so results, warnings and per-prompt responses
    reuse the existing evaluation storage and detail view rather than a
    parallel structure.
    """

    # Metrics where a smaller value wins. Everything else defaults to
    # "higher wins" except NO_WINNER_METRICS below.
    LOWER_IS_BETTER = {
        "mean_latency_ms", "p50_latency_ms", "p95_latency_ms", "p99_latency_ms",
        "total_cost_usd", "input_cost_usd", "output_cost_usd",
        "cost_per_1k_tokens", "cost_per_example",
    }

    # Dollar figures are meaningless for a model with no known list price;
    # excluded from winner selection rather than letting a $0.00 placeholder
    # win every cost row.
    COST_METRICS = {
        "total_cost_usd", "input_cost_usd", "output_cost_usd",
        "cost_per_1k_tokens", "cost_per_example",
    }

    # Token counts are informational, not a competition -- more or fewer
    # tokens is neither better nor worse, so no winner is ever marked.
    NO_WINNER_METRICS = {"input_tokens", "output_tokens", "total_tokens"}

    def __init__(self):
        self.settings = get_settings()
        self.eval_service = EvaluationService()

    def build(
        self,
        db: Session,
        name: str,
        models: List[Dict[str, str]],
        evaluator_names: List[str],
        examples: List[Dict[str, Any]],
        config_dict: Dict[str, Any] | None,
    ) -> Comparison:
        """
        Create the comparison row and one pending Evaluation per model.

        Runs synchronously inside the request so the comparison and its
        children exist -- and GET /comparisons/{id} works -- before the
        background task starts.
        """
        comparison = Comparison(
            id=str(uuid.uuid4()),
            name=name,
            evaluators=evaluator_names,
            examples=examples,
            config=config_dict or {},
            status=EvaluationStatus.PENDING,
        )
        db.add(comparison)

        for spec in models:
            db.add(Evaluation(
                id=str(uuid.uuid4()),
                name=f"{name} — {spec['provider']}/{spec['model']}",
                provider=spec["provider"],
                model=spec["model"],
                evaluators=evaluator_names,
                examples=examples,
                config=config_dict or {},
                status=EvaluationStatus.PENDING,
                progress=0.0,
                comparison_id=comparison.id,
            ))

        db.commit()
        db.refresh(comparison)
        return comparison

    async def run(self, comparison_id: str) -> None:
        """
        Execute every model's evaluation concurrently.

        Opens its own DB session: this runs as a FastAPI BackgroundTask after
        the response has already been sent, by which point the request-scoped
        session from ``get_db`` is closed.
        """
        db = SessionLocal()
        try:
            comparison = (
                db.query(Comparison).filter(Comparison.id == comparison_id).first()
            )
            if comparison is None:
                return

            children = (
                db.query(Evaluation)
                .filter(Evaluation.comparison_id == comparison_id)
                .all()
            )

            comparison.status = EvaluationStatus.RUNNING
            db.commit()

            # One semaphore shared across every model in the comparison, so
            # total in-flight requests stays at max_concurrent_requests
            # regardless of how many models are being compared.
            semaphore = asyncio.Semaphore(self.settings.max_concurrent_requests)

            def make_on_progress():
                return lambda: db.commit()

            results = await asyncio.gather(
                *(
                    self.eval_service._execute(
                        child, semaphore=semaphore, on_progress=make_on_progress()
                    )
                    for child in children
                ),
                return_exceptions=True,
            )

            succeeded = sum(1 for r in results if not isinstance(r, Exception))
            comparison.status = (
                EvaluationStatus.COMPLETED if succeeded > 0 else EvaluationStatus.FAILED
            )
            if succeeded == 0:
                comparison.error = "Every model in this comparison failed"
            comparison.completed_at = datetime.utcnow()
            db.commit()
        finally:
            db.close()

    def compute_winners(self, children: List[Evaluation]) -> Dict[str, str | None]:
        """
        Best evaluation id per metric across every completed, comparable
        child.

        A metric gets no winner (None) rather than a misleading one when
        fewer than two children have a comparable value for it -- because
        models failed, are still running, or (for cost metrics) have no
        known list price.
        """
        candidates = [
            c for c in children if c.status == EvaluationStatus.COMPLETED and c.results
        ]

        # metric -> [(evaluation_id, value), ...]
        values: Dict[str, List[Tuple[str, float]]] = {}
        for child in candidates:
            for evaluator_result in child.results.values():
                metadata = evaluator_result.get("metadata", {})
                priced = metadata.get("pricing_known", True)
                for metric, value in evaluator_result.get("aggregated_metrics", {}).items():
                    if metric in self.NO_WINNER_METRICS:
                        continue
                    if metric in self.COST_METRICS and not priced:
                        continue
                    if not isinstance(value, (int, float)):
                        continue
                    values.setdefault(metric, []).append((child.id, value))

        winners: Dict[str, str | None] = {}
        for metric, pairs in values.items():
            if len(pairs) < 2:
                winners[metric] = None
                continue

            reverse = metric not in self.LOWER_IS_BETTER
            best_id, best_value = sorted(pairs, key=lambda p: p[1], reverse=reverse)[0]

            # A tie has no winner. Without this, models that all scored an
            # identical 0.0 would still crown whichever happened to sort
            # first, presenting an arbitrary pick as the best result.
            if sum(1 for _, value in pairs if value == best_value) > 1:
                winners[metric] = None
                continue

            winners[metric] = best_id

        return winners
