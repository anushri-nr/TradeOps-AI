"""
Creates the SQLite schema and seeds it with synthetic trades and execution logs.
Safe to re-run — uses INSERT OR IGNORE so existing rows are skipped.
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from synthetic import get_all_data

load_dotenv()

CREATE_TRADES = """
CREATE TABLE IF NOT EXISTS trades (
    trade_id        TEXT PRIMARY KEY,
    trade_date      TEXT NOT NULL,
    settlement_date TEXT NOT NULL,
    status          TEXT NOT NULL,
    instrument      TEXT NOT NULL,
    instrument_type TEXT NOT NULL,
    quantity        INTEGER NOT NULL,
    price           REAL NOT NULL,
    notional_value  REAL NOT NULL,
    currency        TEXT NOT NULL,
    counterparty    TEXT NOT NULL,
    trader_id       TEXT NOT NULL,
    broker          TEXT NOT NULL,
    failure_reason  TEXT,
    created_at      TEXT NOT NULL
);
"""

CREATE_LOGS = """
CREATE TABLE IF NOT EXISTS execution_logs (
    log_id      TEXT PRIMARY KEY,
    trade_id    TEXT NOT NULL REFERENCES trades(trade_id),
    timestamp   TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    message     TEXT NOT NULL,
    severity    TEXT NOT NULL,
    system      TEXT NOT NULL
);
"""


def seed():
    trades, logs, _ = get_all_data()

    engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///./tradeops.db"))

    with engine.connect() as conn:
        conn.execute(text(CREATE_TRADES))
        conn.execute(text(CREATE_LOGS))

        conn.execute(
            text("""
                INSERT OR IGNORE INTO trades
                    (trade_id, trade_date, settlement_date, status, instrument,
                     instrument_type, quantity, price, notional_value, currency,
                     counterparty, trader_id, broker, failure_reason, created_at)
                VALUES
                    (:trade_id, :trade_date, :settlement_date, :status, :instrument,
                     :instrument_type, :quantity, :price, :notional_value, :currency,
                     :counterparty, :trader_id, :broker, :failure_reason, :created_at)
            """),
            [
                {**t, "trade_date": str(t["trade_date"]), "settlement_date": str(t["settlement_date"]),
                 "created_at": str(t["created_at"])}
                for t in trades
            ],
        )

        conn.execute(
            text("""
                INSERT OR IGNORE INTO execution_logs
                    (log_id, trade_id, timestamp, event_type, message, severity, system)
                VALUES
                    (:log_id, :trade_id, :timestamp, :event_type, :message, :severity, :system)
            """),
            [{**l, "timestamp": str(l["timestamp"])} for l in logs],
        )

        conn.commit()

    print(f"Seeded {len(trades)} trades and {len(logs)} execution logs into SQLite.")


if __name__ == "__main__":
    seed()
