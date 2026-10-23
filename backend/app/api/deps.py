from typing import Annotated

from fastapi import BackgroundTasks, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import unauthorized
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.storage import get_storage
from app.storage.base import Storage
from app.workers.dispatch import Enqueue, make_enqueue

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_limiter(request: Request) -> SlidingWindowLimiter:
    limiter: SlidingWindowLimiter = request.app.state.limiter
    return limiter


LimiterDep = Annotated[SlidingWindowLimiter, Depends(get_limiter)]


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def get_current_user(
    db: DbSession,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise unauthorized()
    user_id = decode_access_token(credentials.credentials, settings.secret_key)
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise unauthorized("Invalid or expired token.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


StorageDep = Annotated[Storage, Depends(get_storage)]


def get_enqueue(background_tasks: BackgroundTasks, settings: SettingsDep) -> Enqueue:
    return make_enqueue(settings, background_tasks)


EnqueueDep = Annotated[Enqueue, Depends(get_enqueue)]
