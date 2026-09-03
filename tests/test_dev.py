from __future__ import annotations

from pathlib import Path

import doc_extractor_pydantic.dev as dev_module


def test_dev_entrypoint_uses_local_env_and_reload(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(app: str, **kwargs: object) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr(dev_module.uvicorn, "run", fake_run)
    dev_module.run()

    assert captured["app"] == "doc_extractor_pydantic.main:app"
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8788
    assert captured["env_file"] == Path.cwd() / ".env"
    assert captured["reload"] is True
