from sqlalchemy import Column, String, Integer, Float, Text, JSON, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from pydantic import BaseModel, Field
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
