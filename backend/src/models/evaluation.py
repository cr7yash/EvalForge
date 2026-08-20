from sqlalchemy import Column, String, Integer, Float, Text, JSON, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, List
from datetime import datetime
import enum

from ..core.database import Base


class EvaluationStatus(str, enum.Enum):
    """Evaluation status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Evaluation(Base):
    """SQLAlchemy model for evaluation runs."""
    __tablename__ = "evaluations"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    status = Column(SQLEnum(EvaluationStatus), default=EvaluationStatus.PENDING)
    provider = Column(String)
    model = Column(String)
    progress = Column(Float, default=0.0)

    # Set when this evaluation is one model in a side-by-side comparison;
    # null for a standalone run.
    comparison_id = Column(String, index=True, nullable=True)

    # JSON fields for examples and results
    examples = Column(JSON)  # List of EvalExample dicts
    responses = Column(JSON)  # List of response strings
    results = Column(JSON)  # Dict of evaluator results

    # Metadata
    evaluators = Column(JSON)  # List of evaluator names
    config = Column(JSON)  # Generation config
    error = Column(Text, nullable=True)
    warnings = Column(JSON, nullable=True)  # Non-fatal generation issues

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class Comparison(Base):
    """
    SQLAlchemy model for a side-by-side comparison of 2-5 models.

    The shared prompts live here once; each model's run is a normal
    Evaluation row linked back via Evaluation.comparison_id, so results,
    warnings and per-prompt responses reuse the existing evaluation storage
    and detail view rather than a parallel structure.
    """
    __tablename__ = "comparisons"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    status = Column(SQLEnum(EvaluationStatus), default=EvaluationStatus.PENDING)
    examples = Column(JSON)     # shared prompts, stored once
    evaluators = Column(JSON)
    config = Column(JSON)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


# Pydantic schemas for API requests/responses

class EvaluationCreate(BaseModel):
    """Schema for creating a new evaluation."""
    name: str
    provider: str
    model: str
    evaluators: List[str]
    examples: List[Dict[str, Any]]  # List of EvalExample-like dicts
    config: Dict[str, Any] | None = None


class EvaluationResponse(BaseModel):
    """Schema for evaluation API responses."""
    id: str
    name: str
    status: EvaluationStatus
    provider: str
    model: str
    progress: float
    results: Dict[str, Any] | None = None
    evaluators: List[str]
    error: str | None = None
    warnings: List[str] | None = None
    created_at: datetime
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class EvaluationDetail(EvaluationResponse):
    """
    Single-evaluation response, including the prompts and what the model
    replied. Kept out of the list schema so listing many evaluations does not
    ship every prompt and response body.
    """
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    responses: List[str] = Field(default_factory=list)
    config: Dict[str, Any] | None = None


class EvaluationList(BaseModel):
    """Schema for list of evaluations."""
    evaluations: List[EvaluationResponse]
    total: int


class ComparisonModelSpec(BaseModel):
    """One model slot in a comparison request."""
    provider: str
    model: str


class ComparisonCreate(BaseModel):
    """Schema for creating a new side-by-side comparison."""
    name: str
    models: List[ComparisonModelSpec] = Field(min_length=2, max_length=5)
    evaluators: List[str]
    examples: List[Dict[str, Any]]
    config: Dict[str, Any] | None = None

    @field_validator("models")
    @classmethod
    def no_duplicate_models(cls, v: List[ComparisonModelSpec]):
        seen = {(m.provider, m.model) for m in v}
        if len(seen) != len(v):
            raise ValueError("Each (provider, model) pair must be unique")
        return v


class ComparisonEvaluation(EvaluationResponse):
    """
    One model's run inside a comparison, carrying what it replied.

    Deliberately excludes ``examples``: every model in a comparison runs the
    same prompts, which are already on the parent comparison, so repeating
    them per model would bloat a payload that gets polled.
    """
    responses: List[str] = Field(default_factory=list)

    @field_validator("responses", mode="before")
    @classmethod
    def none_becomes_empty(cls, v):
        # A pending or running evaluation has no responses yet and stores
        # NULL. default_factory only applies when the key is missing, not
        # when it is present and None, so coerce it here -- otherwise every
        # comparison 500s at creation time, before any model has replied.
        return [] if v is None else v


class ComparisonSummary(BaseModel):
    """Schema for a comparison in list views."""
    id: str
    name: str
    status: EvaluationStatus
    evaluators: List[str]
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class ComparisonDetail(ComparisonSummary):
    """Full comparison, including every model's evaluation and the winners."""
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    evaluations: List[ComparisonEvaluation] = Field(default_factory=list)
    # metric_name -> id of the evaluation with the best value, or None when
    # fewer than two models have a comparable value for that metric.
    winners: Dict[str, str | None] = Field(default_factory=dict)


class ComparisonList(BaseModel):
    """Schema for list of comparisons."""
    comparisons: List[ComparisonSummary]
    total: int
