"""MCP tool: retrieve execution logs for a trade from the database."""

from langchain_core.tools import tool
from sqlalchemy import text
from .db import get_engine


@tool
def get_execution_logs(trade_id: str) -> str:
    """
    Retrieve all execution logs for a trade given its Trade ID (e.g. 'TRD-003').
    Logs are ordered by timestamp and include the system, severity, event type,
    and message for each step. Use this to trace exactly what happened during
    trade execution and settlement, and to identify where the failure occurred.
    """
    with get_engine().connect() as conn:
        rows = conn.execute(
            text("""
                SELECT log_id, timestamp, system, severity, event_type, message
                FROM execution_logs
                WHERE trade_id = :tid
                ORDER BY timestamp ASC
            """),
            {"tid": trade_id.upper()},
        ).mappings().fetchall()

    if not rows:
        return f"No execution logs found for trade '{trade_id}'."

    lines = [f"Execution logs for {trade_id.upper()} ({len(rows)} entries):\n"]
    for row in rows:
        lines.append(
            f"[{row['timestamp']}] [{row['severity']}] [{row['system']}] {row['event_type']}\n"
            f"  {row['message']}"
        )

    return "\n\n".join(lines)
