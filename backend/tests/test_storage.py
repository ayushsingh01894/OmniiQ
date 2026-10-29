import io

import pytest

from app.storage.base import InvalidStorageKey
from app.storage.local import LocalStorage


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path / "root")


def test_roundtrip_exists_delete(storage):
    storage.save("datasets/abc/original.csv", io.BytesIO(b"hello"))
    assert storage.exists("datasets/abc/original.csv")
    with storage.open("datasets/abc/original.csv") as f:
        assert f.read() == b"hello"
    storage.delete("datasets/abc/original.csv")
    assert not storage.exists("datasets/abc/original.csv")
    storage.delete("datasets/abc/original.csv")  # deleting twice is fine


@pytest.mark.parametrize(
    "key",
    [
        "../escape",
        "a/../../escape",
        "/etc/passwd",
        "a//b",
        "",
        ".hidden",
        "a/.",
        "a b",
        "a\\b",
        "a/\x00b",
    ],
)
def test_unsafe_keys_are_rejected(storage, key):
    for action in (
        lambda: storage.save(key, io.BytesIO(b"x")),
        lambda: storage.open(key),
        lambda: storage.delete(key),
    ):
        with pytest.raises(InvalidStorageKey):
            action()


def test_symlink_cannot_escape_root(storage, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (storage.root / "link").symlink_to(outside)
    with pytest.raises(InvalidStorageKey):
        storage.save("link/stolen.txt", io.BytesIO(b"x"))
    assert not (outside / "stolen.txt").exists()


def test_failed_write_leaves_no_partial_file(storage):
    class Exploding:
        def __init__(self):
            self.sent = False

        def read(self, _n=-1):
            if not self.sent:
                self.sent = True
                return b"partial"
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        storage.save("datasets/x/original.csv", Exploding())
    assert not storage.exists("datasets/x/original.csv")
    assert list((storage.root / "datasets" / "x").iterdir()) == []  # temp file removed too
