"""FastAPI backend for TradeOps AI."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.schemas import InvestigationResponse, TradeListItem
from mcp_tools.db import get_engine
from workflow.graph import investigate

app = FastAPI(
    title="TradeOps AI",
    description="AI-powered failed trade investigation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/trades", response_model=list[TradeListItem])
def list_trades():
    """Return all 50 trades — used by the frontend to browse and select a trade."""
    with get_engine().connect() as conn:
        rows = conn.execute(
            text("""
                SELECT trade_id, status, instrument, instrument_type,
                       failure_reason, notional_value, currency, trade_date, counterparty
                FROM trades
                ORDER BY trade_id
            """)
        ).mappings().fetchall()
    return [dict(r) for r in rows]


@app.post("/investigate/{trade_id}", response_model=InvestigationResponse)
def run_investigation(trade_id: str):
    """
    Run a full AI investigation for a failed trade.
    The agent retrieves trade details, execution logs, and relevant policies,
    then returns a structured report with root cause, evidence, confidence
    score, and recommended next steps.
    """
    tid = trade_id.upper()

    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT status FROM trades WHERE trade_id = :tid"),
            {"tid": tid},
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Trade '{tid}' not found.")

    if row[0] != "FAILED":
        raise HTTPException(
            status_code=400,
            detail=f"Trade '{tid}' has status '{row[0]}'. Only FAILED trades can be investigated.",
        )

    report = investigate(tid)
    return InvestigationResponse(trade_id=tid, report=report)
