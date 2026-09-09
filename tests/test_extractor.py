from __future__ import annotations

import asyncio
import base64
from io import BytesIO

import pytest
from PIL import Image
from pydantic_ai.exceptions import ModelHTTPError
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

import doc_extractor_pydantic.extractor as extractor_module
from doc_extractor_pydantic.config import Settings
from doc_extractor_pydantic.extractor import (
    DocumentExtractor,
    ProviderUnavailableError,
    UploadValidationError,
    extract_pdf_previews,
    media_type_for,
    to_api_response,
    validate_upload,
)
from doc_extractor_pydantic.limits import (
    MAX_PDF_PAGES,
    MAX_PREVIEW_IMAGES,
    MAX_PREVIEW_SCAN_PAGES,
    PROVIDER_RETRIES,
)
from doc_extractor_pydantic.models import DocumentExtraction, ExtractedField
from doc_extractor_pydantic.prompts import EXTRACTION_INSTRUCTIONS

PNG = b"\x89PNG\r\n\x1a\n" + b"test"
JPEG = b"\xff\xd8\xff" + b"test"


def make_pdf(pages: int = 1) -> bytes:
    stream = BytesIO()
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    writer.write(stream)
    return stream.getvalue()


def make_image_pdf(pages: int = 1, size: tuple[int, int] = (420, 300)) -> bytes:
    """Synthetic PDF where every page carries one embedded image."""

    images = [
        Image.new("RGB", size, (30 * (index + 1) % 256, 120, 200)) for index in range(pages)
    ]
    stream = BytesIO()
    images[0].save(stream, format="PDF", save_all=True, append_images=images[1:])
    return stream.getvalue()


PDF = make_pdf()
INVALID_PDF = b"%PDF-1.7\nnot-a-complete-pdf"


def test_default_settings_match_the_local_pilot() -> None:
    settings = Settings()
    assert settings.model == "google:gemini-3.5-flash-lite"
    assert settings.port == 8788


def test_settings_refuse_a_host_outside_loopback(monkeypatch) -> None:
    monkeypatch.setenv("HOST", "localhost")
    assert Settings.from_env().host == "localhost"

    monkeypatch.setenv("HOST", "0.0.0.0")
    with pytest.raises(ValueError, match="não é loopback"):
        Settings.from_env()


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


def test_validation_returns_the_only_parsed_pdf() -> None:
    assert validate_upload("doc.png", PNG, 1024) is None
    document = validate_upload("doc.pdf", PDF, 1024)
    assert document is not None
    assert len(document.pages) == 1


def test_rejects_a_pdf_with_more_pages_than_the_local_limit() -> None:
    oversized = make_pdf(pages=MAX_PDF_PAGES + 1)
    validate_upload("doc.pdf", make_pdf(pages=MAX_PDF_PAGES), len(oversized))

    with pytest.raises(UploadValidationError, match="limite local é de"):
        validate_upload("doc.pdf", oversized, len(oversized))


def test_validation_rejects_password_protected_pdf() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("secret-password")
    stream = BytesIO()
    writer.write(stream)
    encrypted_pdf = stream.getvalue()

    with pytest.raises(UploadValidationError, match="protegido por senha"):
        validate_upload("protected.pdf", encrypted_pdf, len(encrypted_pdf) + 1024)


def test_extraction_parses_the_pdf_only_once(monkeypatch) -> None:
    readers = []
    original_reader = extractor_module.PdfReader

    def counting_reader(*args, **kwargs):
        readers.append(1)
        return original_reader(*args, **kwargs)

    monkeypatch.setattr(extractor_module, "PdfReader", counting_reader)
    asyncio.run(
        DocumentExtractor(settings=Settings(model="test:model"), agent=FakeAgent()).extract(
            "doc.pdf", make_image_pdf()
        )
    )

    assert len(readers) == 1


def test_previews_stop_at_the_scan_and_encode_limits(monkeypatch) -> None:
    encoded = []
    original_encode = extractor_module._encode_preview

    def counting_encode(document, candidate):
        encoded.append(candidate["page"])
        return original_encode(document, candidate)

    monkeypatch.setattr(extractor_module, "_encode_preview", counting_encode)
    document = validate_upload("doc.pdf", make_image_pdf(pages=MAX_PREVIEW_SCAN_PAGES + 2), 10**7)
    previews = extract_pdf_previews(document)

    assert len(previews) == MAX_PREVIEW_IMAGES
    assert len(encoded) == MAX_PREVIEW_IMAGES
    assert max(encoded) <= MAX_PREVIEW_SCAN_PAGES
    assert [preview["label"] for preview in previews] == ["Frente", "Verso", "Detalhe", "Detalhe"]
    assert previews[0]["primary"] is True
    assert previews[0]["src"].startswith("data:image/")


def test_repeated_references_to_one_image_produce_a_single_preview() -> None:
    document = validate_upload("doc.pdf", make_image_pdf(), 10**7)
    assert document is not None
    page = document.pages[0]
    repeated = DecodedStreamObject()
    repeated.set_data(b"\n".join([b"q 420 0 0 300 0 0 cm /image Do Q"] * 500))
    page[NameObject("/Contents")] = repeated

    previews = extract_pdf_previews(document)

    assert len(previews) == 1
    assert previews[0]["label"] == "Frente"


def test_previews_are_empty_without_a_pdf() -> None:
    assert extract_pdf_previews(None) == []


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


def test_rg_does_not_warn_about_fields_a_rg_does_not_have() -> None:
    extraction = DocumentExtraction(
        kind="rg",
        warnings=[
            "Não foi possível localizar o número de registro.",
            "A categoria de habilitação não foi encontrada.",
            "A validade não está legível.",
            "A data de emissão não está legível.",
        ],
    )

    assert extraction.warnings == ["A data de emissão não está legível."]


def test_cnh_keeps_the_warning_about_its_own_registration() -> None:
    extraction = DocumentExtraction(
        kind="cnh",
        warnings=["Não foi possível localizar o número de registro."],
    )

    assert extraction.warnings == ["Não foi possível localizar o número de registro."]


def test_unknown_document_keeps_every_warning() -> None:
    extraction = DocumentExtraction(
        kind="unknown",
        warnings=["Não foi possível localizar o número de registro."],
    )

    assert len(extraction.warnings) == 1


def test_an_invalid_value_still_warns_even_when_the_kind_does_not_expect_it() -> None:
    extraction = DocumentExtraction(
        kind="rg",
        fields={"registration": {"value": "ABC123", "confidence": "high"}},
    )

    assert extraction.fields.registration is None
    assert extraction.warnings == ["O registro não pôde ser confirmado."]


def test_prompt_tells_the_model_not_to_warn_about_absent_field_types() -> None:
    assert "Só avise sobre campos que o documento identificado realmente possui" in (
        EXTRACTION_INSTRUCTIONS
    )


def test_api_response_lists_the_expected_fields_that_were_not_found() -> None:
    extraction = DocumentExtraction(
        kind="cnh",
        fields={"name": ExtractedField(value="MARIA DE TESTE", confidence="low")},
    )

    result = to_api_response(extraction, pages=1, duration_ms=42)
    missing = [field["key"] for field in result["missing"]]

    assert "name" not in missing
    assert missing == ["cpf", "birthDate", "issueDate", "validity", "registration",
                       "category", "parentage"]
    assert result["missing"][0]["label"] == "CPF"
    assert result["fields"]["name"]["confidence"] == "low"


def test_expected_fields_follow_the_document_kind() -> None:
    rg = to_api_response(DocumentExtraction(kind="rg"), pages=1, duration_ms=1)
    unknown = to_api_response(DocumentExtraction(kind="unknown"), pages=1, duration_ms=1)

    assert "category" not in [field["key"] for field in rg["missing"]]
    assert [field["key"] for field in unknown["missing"]] == ["name", "cpf", "birthDate"]


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


def test_slow_provider_is_cut_by_the_local_timeout(monkeypatch) -> None:
    class SlowAgent:
        async def run(self, messages):
            await asyncio.sleep(5)

    monkeypatch.setattr(extractor_module, "EXTRACTION_TIMEOUT_SECONDS", 0.05)
    extractor = DocumentExtractor(settings=Settings(model="test:model"), agent=SlowAgent())

    with pytest.raises(extractor_module.ExtractionTimeoutError, match="tempo limite"):
        asyncio.run(extractor.extract("doc.png", PNG))


def test_agent_keeps_a_single_extra_attempt(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    agent = DocumentExtractor(Settings(model="google:gemini-3.5-flash-lite"))._build_agent()
    assert PROVIDER_RETRIES == 1
    assert agent._max_output_retries == PROVIDER_RETRIES


def test_transient_provider_503_uses_one_backoff_retry(monkeypatch) -> None:
    class FlakyAgent:
        def __init__(self) -> None:
            self.calls = 0

        async def run(self, messages):
            self.calls += 1
            if self.calls == 1:
                raise ModelHTTPError(503, "test:model", {"status": "unavailable"})
            return type("FakeResult", (), {"output": DocumentExtraction(kind="unknown")})()

    agent = FlakyAgent()
    monkeypatch.setattr(extractor_module, "PROVIDER_BACKOFF_SECONDS", 0)
    result = asyncio.run(
        DocumentExtractor(settings=Settings(model="test:model"), agent=agent).extract(
            "doc.png", PNG
        )
    )

    assert agent.calls == 2
    assert result["kind"] == "unknown"


def test_exhausted_provider_503_becomes_provider_unavailable(monkeypatch) -> None:
    class UnavailableAgent:
        async def run(self, messages):
            raise ModelHTTPError(503, "test:model", {"status": "unavailable"})

    monkeypatch.setattr(extractor_module, "PROVIDER_BACKOFF_SECONDS", 0)
    with pytest.raises(ProviderUnavailableError, match="temporariamente indisponível"):
        asyncio.run(
            DocumentExtractor(
                settings=Settings(model="test:model"), agent=UnavailableAgent()
            ).extract("doc.png", PNG)
        )


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


def test_pydantic_output_removes_future_dates() -> None:
    extraction = DocumentExtraction(
        fields={
            "birth_date": {"value": "01/01/2099", "confidence": "high"},
            "issue_date": {"value": "01/01/2099", "confidence": "high"},
        },
    )
    assert extraction.fields.birth_date is None
    assert extraction.fields.issue_date is None
    assert any("futuro" in w for w in extraction.warnings)


def test_pydantic_output_removes_incoherent_birth_and_validity() -> None:
    extraction = DocumentExtraction(
        fields={
            "birth_date": {"value": "10/02/2025", "confidence": "high"},
            "validity": {"value": "10/02/2024", "confidence": "high"},
        },
    )
    assert extraction.fields.birth_date is None
    assert extraction.fields.validity is None
    assert any("incompatíveis" in w for w in extraction.warnings)


def test_rg_keeps_warning_about_registro_geral() -> None:
    extraction = DocumentExtraction(
        kind="rg",
        warnings=["O registro geral está parcialmente ilegível."],
    )
    assert extraction.warnings == ["O registro geral está parcialmente ilegível."]


def test_rg_accepts_check_digit_x() -> None:
    extraction_upper = DocumentExtraction(
        kind="rg",
        fields={"registration": {"value": "12.345.678-X", "confidence": "high"}},
    )
    assert extraction_upper.fields.registration is not None
    assert extraction_upper.fields.registration.value == "12.345.678-X"

    extraction_lower = DocumentExtraction(
        kind="rg",
        fields={"registration": {"value": "12.345.678-x", "confidence": "high"}},
    )
    assert extraction_lower.fields.registration is not None
    assert extraction_lower.fields.registration.value == "12.345.678-x"


def test_rg_rejects_x_in_middle_or_invalid_letters() -> None:
    extraction = DocumentExtraction(
        kind="rg",
        fields={"registration": {"value": "12X345678", "confidence": "high"}},
    )
    assert extraction.fields.registration is None
    assert any("registro" in w for w in extraction.warnings)
