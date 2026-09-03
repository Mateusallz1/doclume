from __future__ import annotations

from pathlib import Path

import uvicorn


def run() -> None:
    """Start the local development server with reload enabled."""

    uvicorn.run(
        "doc_extractor_pydantic.main:app",
        host="127.0.0.1",
        port=8788,
        env_file=Path.cwd() / ".env",
        reload=True,
    )
