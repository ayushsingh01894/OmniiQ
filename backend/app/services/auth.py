from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, conflict
from app.core.security import burn_password_check, hash_password, verify_password
from app.models import Organization, OrganizationMember, Role, User
from app.services import audit
from app.utils.slug import unique_slug


def register_user(db: Session, *, email: str, password: str, display_name: str) -> User:
    """Creates the user plus a personal organization they own, in one transaction."""
    if db.scalar(select(User.id).where(User.email == email)):
        raise conflict("email_already_registered", "An account with this email already exists.")

    user = User(email=email, password_hash=hash_password(password), display_name=display_name)
    org = Organization(name=f"{display_name}'s workspace", slug=unique_slug(display_name))
    db.add_all([user, org])
    try:
        db.flush()
    except IntegrityError:
        # Lost a race with a concurrent registration of the same email.
        db.rollback()
        raise conflict(
            "email_already_registered", "An account with this email already exists."
        ) from None
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=Role.owner))
    audit.record(
        db, action="auth.register", resource_type="user", actor_id=user.id, resource_id=user.id
    )
    audit.record(
        db,
        action="organization.create",
        resource_type="organization",
        actor_id=user.id,
        organization_id=org.id,
        resource_id=org.id,
        details={"personal": True},
    )
    db.commit()
    return user


def authenticate(db: Session, *, email: str, password: str) -> User:
    """Same error and similar timing whether the email is unknown or the password is wrong."""
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        burn_password_check(password)
    ok = user is not None and verify_password(password, user.password_hash)
    if user is None or not ok or not user.is_active:
        audit.record(
            db,
            action="auth.login_failed",
            resource_type="user",
            actor_id=user.id if user else None,
            details={"email": email},
        )
        db.commit()
        raise AppError(
            401,
            "invalid_credentials",
            "Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    audit.record(
        db, action="auth.login", resource_type="user", actor_id=user.id, resource_id=user.id
    )
    db.commit()
    return user
