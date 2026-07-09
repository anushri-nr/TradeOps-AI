"""LangGraph state and report schema for the trade investigation workflow."""

from __future__ import annotations
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class InvestigationReport(BaseModel):
    root_cause: str = Field(
        description="One-sentence root cause of the trade failure"
    )
    evidence: list[str] = Field(
        description="3-5 specific evidence points from logs and trade data"
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in the root cause assessment (0.0–1.0)"
    )
    recommended_next_steps: list[str] = Field(
        description="3-5 actionable steps for operations to resolve this failure"
    )


class InvestigationState(TypedDict):
    trade_id: str
    messages: Annotated[list, add_messages]
    report: dict | None
