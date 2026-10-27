from functools import lru_cache

from app.core.config import get_settings
from app.storage.base import Storage
from app.storage.local import LocalStorage


@lru_cache
def get_storage() -> Storage:
    # S3-compatible storage can be added later behind the same Storage protocol.
    return LocalStorage(get_settings().storage_root)
