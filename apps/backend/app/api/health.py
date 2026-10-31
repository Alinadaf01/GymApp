from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: process is up."""
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness: database reachable. Never leaks connection details."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "database": "error"}
    return {"status": "ok", "database": "ok"}
