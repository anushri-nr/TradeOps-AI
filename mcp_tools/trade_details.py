"""MCP tool: retrieve full details for a single trade from the database."""

from langchain_core.tools import tool
from sqlalchemy import text
from .db import get_engine


@tool
def get_trade_details(trade_id: str) -> str:
    """
    Retrieve complete details for a trade given its Trade ID (e.g. 'TRD-003').
    Returns trade metadata including status, instrument, counterparty, notional
    value, and failure reason. Use this as the first step in any investigation.
    """
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT * FROM trades WHERE trade_id = :tid"),
            {"tid": trade_id.upper()},
        ).mappings().fetchone()

    if row is None:
        return f"No trade found with ID '{trade_id}'. Verify the trade ID and try again."

    failure_line = f"\nFailure Reason : {row['failure_reason']}" if row["failure_reason"] else ""

    return (
        f"Trade ID       : {row['trade_id']}\n"
        f"Status         : {row['status']}{failure_line}\n"
        f"Instrument     : {row['instrument']} ({row['instrument_type']})\n"
        f"Trade Date     : {row['trade_date']}\n"
        f"Settlement Date: {row['settlement_date']}\n"
        f"Quantity       : {int(row['quantity']):,}\n"
        f"Price          : {float(row['price']):.4f} {row['currency']}\n"
        f"Notional       : {float(row['notional_value']):,.2f} {row['currency']}\n"
        f"Counterparty   : {row['counterparty']}\n"
        f"Trader ID      : {row['trader_id']}\n"
        f"Broker         : {row['broker']}\n"
        f"Created At     : {row['created_at']}"
    )
