import re
import secrets


def unique_slug(name: str) -> str:
    """URL-safe slug with a random suffix, so two organizations can share a display name."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "workspace"
    return f"{base}-{secrets.token_hex(3)}"
