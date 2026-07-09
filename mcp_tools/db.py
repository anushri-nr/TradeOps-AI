"""Shared SQLAlchemy engine — imported by trade_details and execution_logs tools."""

import os
from sqlalchemy import create_engine, Engine
from dotenv import load_dotenv

load_dotenv()

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///./tradeops.db"))
    return _engine
