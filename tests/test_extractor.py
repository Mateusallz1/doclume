from __future__ import annotations

import asyncio
import base64
from io import BytesIO

import pytest
from pypdf import PdfWriter

import doc_extractor_pydantic.extractor as extractor_module
from doc_extractor_pydantic.config import Settings
from doc_extractor_pydantic.extractor import (
    DocumentExtractor,
    UploadValidationError,
    media_type_for,
    page_count,
    to_api_response,
    validate_upload,
)
from doc_extractor_pydantic.models import DocumentExtraction, ExtractedField
from doc_extractor_pydantic.prompts import EXTRACTION_INSTRUCTIONS

PNG = b"\x89PNG\r\n\x1a\n" + b"test"
JPEG = b"\xff\xd8\xff" + b"test"


def make_pdf() -> bytes:
    stream = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(stream)
    return stream.getvalue()


PDF = make_pdf()
INVALID_PDF = b"%PDF-1.7\nnot-a-complete-pdf"


def test_default_settings_match_the_local_pilot() -> None:
    settings = Settings()
    assert settings.model == "google:gemini-3.5-flash-lite"
    assert settings.port == 8788


def test_prompt_maps_cnh_category_to_the_cat_hab_field() -> None:
    prompt = EXTRACTION_INSTRUCTIONS.lower()
    assert "9 cat hab" in prompt
    assert "acc" in prompt
    assert "tabelas de veículos" in prompt


def test_google_agent_uses_minimal_thinking_without_a_network_call(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    agent = DocumentExtractor(
        Settings(model="google:gemini-3.5-flash-lite")
    )._build_agent()
    assert agent.model_settings == {
        "google_thinking_config": {"thinking_level": "MINIMAL"}
    }


def test_validates_supported_uploads_and_signatures() -> None:
    validate_upload("document.png", PNG, 1024)
    validate_upload("document.jpg", JPEG, 1024)
    validate_upload("document.pdf", PDF, 1024)

    with pytest.raises(UploadValidationError, match="Formato não suportado"):
        validate_upload("document.exe", b"x", 1024)
    with pytest.raises(UploadValidationError, match="PNG válido"):
        validate_upload("document.png", b"x", 1024)
    with pytest.raises(UploadValidationError, match="PDF válido"):
        validate_upload("document.pdf", INVALID_PDF, 1024)
    with pytest.raises(UploadValidationError, match="excede"):
        validate_upload("document.jpg", JPEG, 2)


def test_infers_media_type_from_extension() -> None:
    assert media_type_for("doc.png", "application/octet-stream") == "image/png"
    assert media_type_for("doc.jpeg") == "image/jpeg"
    assert media_type_for("doc.pdf") == "application/pdf"


def test_page_count_is_one_for_images_and_zero_for_invalid_pdf() -> None:
    assert page_count("doc.png", PNG) == 1
    assert page_count("doc.pdf", PDF) == 1
    assert page_count("doc.pdf", INVALID_PDF) == 0


def test_pydantic_output_normalizes_blank_values() -> None:
    extraction = DocumentExtraction(
        kind="cnh",
        fields={"name": {"value": " ", "confidence": "high"}},
    )
    assert extraction.fields.name is not None
    assert extraction.fields.name.value is None


def test_pydantic_output_removes_semantically_invalid_values() -> None:
    extraction = DocumentExtraction(
        kind="cnh",
        fields={
            "cpf": {"value": "111.111.111-11", "confidence": "high"},
            "birth_date": {"value": "31/02/1990", "confidence": "high"},
            "registration": {"value": "ABC123", "confidence": "high"},
            "category": {"value": "Z", "confidence": "high"},
        },
    )
    assert extraction.fields.cpf is None
    assert extraction.fields.birth_date is None
    assert extraction.fields.registration is None
    assert extraction.fields.category is None
    assert len(extraction.warnings) == 4


def test_pydantic_output_removes_incoherent_date_pairs() -> None:
    extraction = DocumentExtraction(
        fields={
            "birth_date": {"value": "10/02/2020", "confidence": "high"},
            "issue_date": {"value": "10/02/2019", "confidence": "high"},
        },
    )
    assert extraction.fields.birth_date is None
    assert extraction.fields.issue_date is None
    assert "incompatíveis" in extraction.warnings[0]


def test_pydantic_output_keeps_valid_semantic_values() -> None:
    extraction = DocumentExtraction(
        fields={
            "cpf": {"value": "123.456.789-09", "confidence": "high"},
            "birth_date": {"value": "10/02/1990", "confidence": "high"},
            "issue_date": {"value": "12/03/2024", "confidence": "high"},
            "validity": {"value": "12/03/2034", "confidence": "high"},
            "registration": {"value": "12345678901", "confidence": "high"},
            "category": {"value": "ab", "confidence": "high"},
        },
    )
    assert set(extraction.fields.populated()) == {
        "cpf",
        "birth_date",
        "issue_date",
        "validity",
        "registration",
        "category",
    }
    assert extraction.fields.category.value == "AB"
    assert extraction.warnings == []


def test_parentage_normalizes_escaped_and_labeled_line_breaks() -> None:
    extraction = DocumentExtraction(
        fields={
            "parentage": {
                "value": r"PAI DA SILVA\n; MAE DE TESTE",
                "confidence": "high",
            }
        }
    )
    assert extraction.fields.parentage is not None
    assert extraction.fields.parentage.value == "PAI DA SILVA\nMAE DE TESTE"


def test_api_response_keeps_legacy_field_names_and_text() -> None:
    extraction = DocumentExtraction(
        kind="cnh",
        fields={
            "name": ExtractedField(value="MARIA DE TESTE", confidence="high"),
            "birth_date": ExtractedField(value="10/02/1990", confidence="medium"),
        },
        transcription="CARTEIRA NACIONAL DE HABILITAÇÃO",
        warnings=["Confira a data."],
    )
    result = to_api_response(extraction, pages=1, duration_ms=42)
    assert result["fields"]["birthDate"]["label"] == "Data de nascimento"
    assert result["previews"] == []
    assert "Nome: MARIA DE TESTE" in result["text"]
    assert "TRANSCRIÇÃO RECONHECIDA" in result["text"]


class FakeAgent:
    def __init__(self) -> None:
        self.messages = None

    async def run(self, messages):
        self.messages = messages
        return type(
            "FakeResult",
            (),
            {
                "output": DocumentExtraction(
                    kind="unknown",
                    warnings=["Documento de teste."],
                )
            },
        )()


def test_extractor_sends_multimodal_content_without_writing_file() -> None:
    fake = FakeAgent()
    settings = Settings(model="test:model")
    result = asyncio.run(
        DocumentExtractor(settings=settings, agent=fake).extract("doc.png", PNG)
    )
    assert result["pages"] == 1
    assert result["warnings"] == ["Documento de teste."]
    assert fake.messages[0].startswith("Extraia os campos")
    assert "nome do arquivo" not in fake.messages[0].lower()
    assert "doc.png" not in fake.messages[0]
    assert fake.messages[1].media_type == "image/png"
    assert fake.messages[1].data == PNG


def test_extractor_adds_only_the_primary_embedded_image_to_pdf_input(monkeypatch) -> None:
    fake = FakeAgent()
    preview = {
        "label": "Frente",
        "primary": True,
        "src": "data:image/jpeg;base64," + base64.b64encode(JPEG).decode("ascii"),
    }
    monkeypatch.setattr(extractor_module, "extract_pdf_previews", lambda *_: [preview])

    result = asyncio.run(
        DocumentExtractor(settings=Settings(model="test:model"), agent=fake).extract(
            "doc.pdf", PDF
        )
    )

    assert result["previews"] == [preview]
    assert fake.messages[1].media_type == "application/pdf"
    assert fake.messages[2].media_type == "image/jpeg"
    assert fake.messages[2].data == JPEG
