from fastapi import APIRouter, Request, status

from app.api.deps import CurrentUser, DbSession, LimiterDep, SettingsDep, client_ip
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, RegisterRequest, TokenOut, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    request: Request,
    db: DbSession,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> UserOut:
    limiter.hit(
        f"register:{client_ip(request)}",
        settings.register_rate_limit_attempts,
        settings.register_rate_limit_window_seconds,
    )
    user = auth_service.register_user(
        db, email=body.email, password=body.password, display_name=body.display_name
    )
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenOut)
def login(
    body: LoginRequest,
    request: Request,
    db: DbSession,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> TokenOut:
    limiter.hit(
        f"login:{client_ip(request)}:{body.email}",
        settings.login_rate_limit_attempts,
        settings.login_rate_limit_window_seconds,
    )
    user = auth_service.authenticate(db, email=body.email, password=body.password)
    token = create_access_token(user.id, settings.secret_key, settings.access_token_expire_minutes)
    return TokenOut(access_token=token, expires_in=settings.access_token_expire_minutes * 60)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
