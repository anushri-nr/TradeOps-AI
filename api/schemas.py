"""Request/response Pydantic models for the FastAPI layer."""

from pydantic import BaseModel


class InvestigationReport(BaseModel):
    root_cause: str
    evidence: list[str]
    confidence_score: float
    recommended_next_steps: list[str]


class InvestigationResponse(BaseModel):
    trade_id: str
    report: InvestigationReport


class TradeListItem(BaseModel):
    trade_id: str
    status: str
    instrument: str
    instrument_type: str
    failure_reason: str | None
    notional_value: float
    currency: str
    trade_date: str
    counterparty: str
