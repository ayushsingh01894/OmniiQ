import uuid
from datetime import UTC, datetime, timedelta

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

KEY = "k" * 40


def test_password_hash_is_salted_and_verifiable():
    h1, h2 = hash_password("a-long-password"), hash_password("a-long-password")
    assert h1 != h2 and h1.startswith("$argon2")
    assert verify_password("a-long-password", h1)
    assert not verify_password("wrong-password", h1)
    assert not verify_password("anything", "not-a-hash")


def test_token_roundtrip_expiry_and_tampering():
    uid = uuid.uuid4()
    assert decode_access_token(create_access_token(uid, KEY, 5), KEY) == uid

    past = datetime.now(UTC) - timedelta(hours=1)
    assert decode_access_token(create_access_token(uid, KEY, 5, now=past), KEY) is None

    token = create_access_token(uid, KEY, 5)
    assert decode_access_token(token, "other-key-" + "x" * 30) is None
    assert decode_access_token(token[:-2] + "xx", KEY) is None
    assert decode_access_token("garbage", KEY) is None
