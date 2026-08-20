import logging

from fastapi.testclient import TestClient

from doc_extractor_pydantic import main as main_module

app = main_module.app


def test_health_does_not_expose_credentials() -> None:
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "OPENAI_API_KEY" not in body
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_api_documentation_is_not_exposed() -> None:
    response = TestClient(app).get("/api/docs")
    assert response.status_code == 404


def test_rejects_unsupported_upload_before_provider_call() -> None:
    response = TestClient(app).post(
        "/api/extract",
        files={"document": ("malware.exe", b"MZ", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Formato não suportado" in response.json()["detail"]


def test_rejects_malformed_pdf_before_provider_call() -> None:
    response = TestClient(app).post(
        "/api/extract",
        files={"document": ("document.pdf", b"%PDF-1.7\nnot-a-complete-pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert "PDF válido" in response.json()["detail"]


class FakeExtractor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bytes, str | None]] = []

    async def extract(self, file_name: str, content: bytes, content_type: str | None) -> dict:
        self.calls.append((file_name, content, content_type))
        return {
            "kind": "cnh",
            "pages": 1,
            "fields": {
                "name": {
                    "value": "MARIA DE TESTE",
                    "confidence": "high",
                    "label": "Nome",
                }
            },
            "text": "DOCUMENTO: CNH\nNome: MARIA DE TESTE",
            "warnings": [],
            "durationMs": 12,
        }


def test_returns_extraction_result_without_calling_a_real_provider(monkeypatch) -> None:
    fake = FakeExtractor()
    monkeypatch.setattr(main_module, "extractor", fake)
    content = b"\x89PNG\r\n\x1a\nsynthetic"

    response = TestClient(app).post(
        "/api/extract",
        files={"document": ("test.png", content, "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["fields"]["name"]["value"] == "MARIA DE TESTE"
    assert fake.calls == [("test.png", content, "image/png")]


def test_provider_error_does_not_write_exception_details_to_logs(monkeypatch, caplog) -> None:
    class FailingExtractor:
        async def extract(self, file_name: str, content: bytes, content_type: str | None) -> dict:
            raise RuntimeError("private document value must not be logged")

    monkeypatch.setattr(main_module, "extractor", FailingExtractor())
    content = b"\x89PNG\r\n\x1a\nsynthetic"

    with caplog.at_level(logging.INFO):
        response = TestClient(app).post(
            "/api/extract",
            files={"document": ("test.png", content, "image/png")},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Não foi possível processar o documento."
    assert "private document value" not in caplog.text
