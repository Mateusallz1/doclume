from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass

DEFAULT_MAX_UPLOAD_BYTES = 15 * 1024 * 1024
DEFAULT_MODEL = "google:gemini-3.5-flash-lite"


def is_loopback(host: str | None) -> bool:
    """Whether an address or hostname points back at this machine."""

    if not host:
        return False
    candidate = host.strip().strip("[]")
    if candidate.lower() in {"localhost", "testserver"}:
        return True
    try:
        return ipaddress.ip_address(candidate).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class Settings:
    model: str = DEFAULT_MODEL
    host: str = "127.0.0.1"
    port: int = 8788
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES

    @classmethod
    def from_env(cls) -> Settings:
        host = os.getenv("HOST", "127.0.0.1")
        if not is_loopback(host):
            raise ValueError(
                f"HOST={host!r} não é loopback. Este piloto só atende 127.0.0.1 ou ::1; "
                "publicar em rede exige autenticação, rate limit e host permitido."
            )
        return cls(
            model=os.getenv("PYDANTIC_AI_MODEL", DEFAULT_MODEL),
            host=host,
            port=_positive_int(os.getenv("PORT"), 8788),
            max_upload_bytes=_positive_int(
                os.getenv("MAX_UPLOAD_BYTES"), DEFAULT_MAX_UPLOAD_BYTES
            ),
        )

    def provider_configured(self) -> bool:
        provider = self.model.split(":", maxsplit=1)[0].lower()
        if provider in {"openai", "openai-responses"}:
            return bool(os.getenv("OPENAI_API_KEY"))
        if provider == "anthropic":
            return bool(os.getenv("ANTHROPIC_API_KEY"))
        if provider in {"google", "google-gla", "google-vertex"}:
            return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        return True


def _positive_int(value: str | None, fallback: int) -> int:
    if not value:
        return fallback
    try:
        parsed = int(value)
    except ValueError:
        return fallback
    return parsed if parsed > 0 else fallback
