from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ...core.database import get_db
from ...models.evaluation import (
    Comparison,
    ComparisonCreate,
    ComparisonDetail,
    ComparisonEvaluation,
    ComparisonList,
    ComparisonSummary,
    Evaluation,
)
from ...services.comparison_service import ComparisonService

router = APIRouter()


def _load_children(db: Session, comparison_id: str) -> List[Evaluation]:
    return (
        db.query(Evaluation)
        .filter(Evaluation.comparison_id == comparison_id)
        .all()
    )


def _to_detail(comparison: Comparison, children: List[Evaluation]) -> ComparisonDetail:
    service = ComparisonService()
    return ComparisonDetail(
        **ComparisonSummary.model_validate(comparison).model_dump(),
        examples=comparison.examples or [],
        evaluations=[ComparisonEvaluation.model_validate(c) for c in children],
        winners=service.compute_winners(children),
    )


@router.post("/", response_model=ComparisonDetail, status_code=202)
async def create_comparison(
    request: ComparisonCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create a side-by-side comparison of 2-5 models on the same prompts.

    Generation for a multi-model comparison can take tens of seconds, so this
    returns immediately (202) once the comparison and its per-model
    evaluations exist, and the run itself continues in the background.
    Poll GET /{comparison_id} to observe progress and, eventually, results.
    """
    service = ComparisonService()

    try:
        comparison = service.build(
            db=db,
            name=request.name,
            models=[m.model_dump() for m in request.models],
            evaluator_names=request.evaluators,
            examples=request.examples,
            config_dict=request.config,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    background_tasks.add_task(service.run, comparison.id)

    children = _load_children(db, comparison.id)
    return _to_detail(comparison, children)


@router.get("/", response_model=ComparisonList)
def list_comparisons(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all comparisons with pagination."""
    comparisons = db.query(Comparison).offset(skip).limit(limit).all()
    total = db.query(Comparison).count()

    return ComparisonList(
        comparisons=[ComparisonSummary.model_validate(c) for c in comparisons],
        total=total
    )


@router.get("/{comparison_id}", response_model=ComparisonDetail)
def get_comparison(
    comparison_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a comparison by id, including every model's evaluation and, once
    they've completed, the per-metric winners.
    """
    comparison = db.query(Comparison).filter(Comparison.id == comparison_id).first()
    if not comparison:
        raise HTTPException(status_code=404, detail="Comparison not found")

    children = _load_children(db, comparison_id)
    return _to_detail(comparison, children)


@router.delete("/{comparison_id}", status_code=204)
def delete_comparison(
    comparison_id: str,
    db: Session = Depends(get_db)
):
    """Delete a comparison and every model's evaluation within it."""
    comparison = db.query(Comparison).filter(Comparison.id == comparison_id).first()
    if not comparison:
        raise HTTPException(status_code=404, detail="Comparison not found")

    for child in _load_children(db, comparison_id):
        db.delete(child)
    db.delete(comparison)
    db.commit()

    return None
