from sqlalchemy import Column, String, Integer, JSON, DateTime, Text
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime

from ..core.database import Base


class Dataset(Base):
    """SQLAlchemy model for evaluation datasets."""
    __tablename__ = "datasets"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)

    # Store examples as JSON
    examples = Column(JSON)  # List of {id, prompt, expected_output, context, metadata} dicts

    # Metadata
    size = Column(Integer)  # Number of examples
    tags = Column(JSON)  # List of tag strings

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# Pydantic schemas

class DatasetCreate(BaseModel):
    """Schema for creating a new dataset."""
    name: str
    description: str | None = None
    examples: List[Dict[str, Any]]
    tags: List[str] = []


class DatasetResponse(BaseModel):
    """Schema for dataset API responses."""
    id: str
    name: str
    description: str | None = None
    size: int
    tags: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DatasetDetail(DatasetResponse):
    """Schema for detailed dataset response with examples."""
    examples: List[Dict[str, Any]]
