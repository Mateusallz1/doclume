from __future__ import annotations

import socket
import threading
from collections.abc import Iterator

import pytest
import uvicorn

from doc_extractor_pydantic.main import app


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="session")
def live_server() -> Iterator[str]:
    """Serve the real page on loopback so the browser exercises the real flow."""

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(200):
            if server.started:
                break
            threading.Event().wait(0.05)
        else:
            pytest.fail("o servidor de teste não subiu")
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
