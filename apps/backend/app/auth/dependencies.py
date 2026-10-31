from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.sessions import get_session_user
from app.config import get_settings
from app.database import get_db
from app.models import AuthSession, User


@dataclass
class CurrentAuth:
    user: User
    session: AuthSession


def get_current_auth(request: Request, db: Session = Depends(get_db)) -> CurrentAuth:
    token = request.cookies.get(get_settings().session_cookie_name)
    found = get_session_user(db, token)
    if found is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ابتدا وارد شوید.")
    session, user = found
    return CurrentAuth(user=user, session=session)


def get_current_user(auth: CurrentAuth = Depends(get_current_auth)) -> User:
    return auth.user
