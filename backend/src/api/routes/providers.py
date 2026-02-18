from fastapi import APIRouter
from typing import List, Dict, Any

from ...services.eval_service import EvaluationService

router = APIRouter()


@router.get("/", response_model=List[Dict[str, Any]])
def list_providers():
    """
    List all available LLM providers and their models.

    Returns a list of providers with:
    - id: Provider identifier
    - name: Provider display name
    - models: List of available model identifiers
    """
    service = EvaluationService()
    return service.get_available_providers()


@router.get("/evaluators", response_model=List[Dict[str, Any]])
def list_evaluators():
    """
    List all available evaluators.

    Returns a list of evaluators with their descriptions and metrics.
    """
    return [
        {
            "id": "accuracy",
            "name": "Accuracy",
            "description": "Measures response accuracy using exact match, semantic similarity, BLEU, ROUGE-L, and F1 score",
            "metrics": ["exact_match", "semantic_similarity", "bleu", "rouge_l", "f1"]
        },
        {
            "id": "performance",
            "name": "Performance",
            "description": "Measures latency and throughput metrics",
            "metrics": ["mean_latency_ms", "p50_latency_ms", "p95_latency_ms", "p99_latency_ms", "tokens_per_second"]
        },
        {
            "id": "cost",
            "name": "Cost",
            "description": "Calculates token usage and cost metrics",
            "metrics": ["total_cost_usd", "cost_per_1k_tokens", "cost_per_example"]
        }
    ]
