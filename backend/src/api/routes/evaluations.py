from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ...core.database import get_db
from ...models.evaluation import (
    Evaluation,
    EvaluationCreate,
    EvaluationResponse,
    EvaluationDetail,
    EvaluationList,
    EvaluationStatus
)
from ...services.eval_service import EvaluationService

router = APIRouter()


@router.post("/", response_model=EvaluationResponse, status_code=201)
async def create_evaluation(
    request: EvaluationCreate,
    db: Session = Depends(get_db)
):
    """
    Create and run a new evaluation.

    This endpoint:
    1. Validates the request
    2. Runs the LLM against all examples
    3. Computes all requested metrics
    4. Stores results in database
    5. Returns the completed evaluation
    """
    service = EvaluationService()

    try:
        # Run evaluation
        evaluation = await service.run_evaluation(
            name=request.name,
            provider_name=request.provider,
            model=request.model,
            examples=request.examples,
            evaluator_names=request.evaluators,
            config_dict=request.config
        )

        # Save to database
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)

        return evaluation

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.get("/", response_model=EvaluationList)
def list_evaluations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all evaluations with pagination.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
    """
    evaluations = db.query(Evaluation).offset(skip).limit(limit).all()
    total = db.query(Evaluation).count()

    return EvaluationList(
        evaluations=[EvaluationResponse.model_validate(e) for e in evaluations],
        total=total
    )


@router.get("/{evaluation_id}", response_model=EvaluationDetail)
def get_evaluation(
    evaluation_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific evaluation by ID.

    Returns full evaluation results including all metrics, plus the prompts
    that were sent and the responses the model returned.
    """
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()

    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return EvaluationDetail.model_validate(evaluation)


@router.delete("/{evaluation_id}", status_code=204)
def delete_evaluation(
    evaluation_id: str,
    db: Session = Depends(get_db)
):
    """Delete an evaluation."""
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()

    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    db.delete(evaluation)
    db.commit()

    return None
