from sqlalchemy import select

from app.core.security import create_access_token
from app.models import AuditLog, OrganizationMember, Role, User
from tests.conftest import PASSWORD

REG = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


def _register(client, email="ana@example.com", password=PASSWORD, name="Ana"):
    return client.post(REG, json={"email": email, "password": password, "display_name": name})


def test_register_creates_user_and_owned_personal_org(client, db):
    r = _register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "ana@example.com" and "password" not in str(body)
    user = db.scalar(select(User))
    membership = db.scalar(select(OrganizationMember).where(OrganizationMember.user_id == user.id))
    assert membership.role == Role.owner


def test_password_is_stored_hashed(client, db):
    _register(client)
    stored = db.scalar(select(User.password_hash))
    assert stored != PASSWORD and stored.startswith("$argon2")


def test_duplicate_email_is_rejected_case_insensitively(client):
    assert _register(client, email="ana@example.com").status_code == 201
    r = _register(client, email="ANA@Example.com")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_already_registered"


def test_short_password_rejected_and_never_echoed(client):
    r = _register(client, password="short")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert "short" not in r.text.replace("too short", "").replace("String should", "")
    assert "input" not in r.json()["error"]["details"][0]


def test_login_returns_working_token(client):
    _register(client)
    r = client.post(LOGIN, json={"email": "ana@example.com", "password": PASSWORD})
    assert r.status_code == 200
    token = r.json()
    assert token["token_type"] == "bearer" and token["expires_in"] > 0
    me = client.get(ME, headers={"Authorization": f"Bearer {token['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "ana@example.com"


def test_wrong_password_and_unknown_email_look_identical(client):
    _register(client)
    wrong = client.post(LOGIN, json={"email": "ana@example.com", "password": "x" * 12})
    unknown = client.post(LOGIN, json={"email": "nobody@example.com", "password": "x" * 12})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_me_requires_a_valid_token(client, make_actor, app):
    assert client.get(ME).status_code == 401
    assert client.get(ME, headers={"Authorization": "Bearer nonsense"}).status_code == 401
    ana = make_actor("Ana")
    tampered = {"Authorization": ana.headers["Authorization"][:-3] + "abc"}
    assert client.get(ME, headers=tampered).status_code == 401


def test_expired_token_is_rejected(client, make_actor):
    import uuid
    from datetime import UTC, datetime, timedelta

    ana = make_actor("Ana")
    old = datetime.now(UTC) - timedelta(hours=2)
    token = create_access_token(
        uuid.UUID(ana.user["id"]), "test-only-secret-key-that-is-at-least-32-chars", 5, now=old
    )
    assert client.get(ME, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_for_deleted_user_is_rejected(client, make_actor, db):
    ana = make_actor("Ana")
    db.delete(db.scalar(select(User)))
    db.commit()
    assert client.get(ME, headers=ana.headers).status_code == 401


def test_login_is_rate_limited(client, app):
    _register(client)
    statuses = [
        client.post(LOGIN, json={"email": "ana@example.com", "password": "x" * 12}).status_code
        for _ in range(12)
    ]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    last = client.post(LOGIN, json={"email": "ana@example.com", "password": "x" * 12})
    assert last.status_code == 429 and "retry-after" in last.headers


def test_register_is_rate_limited(client):
    codes = [_register(client, email=f"u{i}@example.com").status_code for i in range(6)]
    assert codes == [201] * 5 + [429]


def test_auth_events_are_audited(client, db):
    _register(client)
    client.post(LOGIN, json={"email": "ana@example.com", "password": "x" * 12})
    client.post(LOGIN, json={"email": "ana@example.com", "password": PASSWORD})
    actions = [a for (a,) in db.execute(select(AuditLog.action)).all()]
    assert {"auth.register", "organization.create", "auth.login_failed", "auth.login"} <= set(
        actions
    )
    for log in db.scalars(select(AuditLog)):
        assert PASSWORD not in str(log.details)
