"""Build the database engine from the DATABASE_URL setting."""

import os

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine

# Same value as .env.example, so a fresh clone works with the docker-compose database.
DEFAULT_DATABASE_URL = "postgresql+psycopg://anipulse:anipulse@localhost:5432/anipulse"


def database_url() -> str:
    """Read DATABASE_URL from the environment (or .env), falling back to the default."""
    load_dotenv()
    return os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


def get_engine(url: str | None = None) -> Engine:
    """Create an engine. pool_pre_ping drops dead connections instead of failing on them."""
    return create_engine(url or database_url(), pool_pre_ping=True)
