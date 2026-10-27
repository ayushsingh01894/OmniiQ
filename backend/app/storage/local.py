import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO

from app.storage.base import InvalidStorageKey

_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*$")


class LocalStorage:
    """Files on local disk under one root directory (owner-only permissions).

    Keys are validated and the resolved path must stay inside the root, so a bad key
    (`../x`, absolute paths, symlink tricks) can never read or write outside it.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _path(self, key: str) -> Path:
        if not _KEY_RE.match(key) or ".." in key.split("/"):
            raise InvalidStorageKey("invalid storage key")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise InvalidStorageKey("invalid storage key")
        return path

    def save(self, key: str, data: BinaryIO) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Write to a temp file in the same directory, then rename: readers never see a partial file.
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".upload-")
        try:
            with os.fdopen(fd, "wb") as out:
                shutil.copyfileobj(data, out, length=1024 * 1024)
            os.chmod(tmp_name, 0o600)
            os.replace(tmp_name, path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def open(self, key: str) -> BinaryIO:
        return self._path(key).open("rb")

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()
