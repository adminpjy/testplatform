from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


def check_database(db: Session) -> dict:
    db.execute(text("SELECT 1"))
    return {
        "connected": True,
        "dialect": settings.database_dialect,
        "url": settings.safe_database_url,
    }
