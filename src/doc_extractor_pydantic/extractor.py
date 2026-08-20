from __future__ import annotations

import base64
import time
from io import BytesIO
from pathlib import PurePath
from typing import Any

from pydantic_ai import Agent, BinaryContent
from pypdf import PdfReader
from pypdf.generic import ContentStream

from .config import Settings
from .models import DocumentExtraction
from .prompts import EXTRACTION_INSTRUCTIONS

IMAGE_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
ALLOWED_EXTENSIONS = {".pdf", *IMAGE_MEDIA_TYPES}
MAX_PREVIEW_IMAGES = 4


class UploadValidationError(ValueError):
    """Raised when an upload is not a supported document."""


class ProviderNotConfiguredError(RuntimeError):
    """Raised before a request when provider credentials are missing."""


class DocumentExtractor:
    def __init__(self, settings: Settings | None = None, agent: Any | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.agent = agent

    def _build_agent(self) -> Agent:
        model_settings: dict[str, object] | None = None
        if self.settings.model.lower().startswith("google:"):
            model_settings = {
                "google_thinking_config": {"thinking_level": "MINIMAL"}
            }
        return Agent(
            model=self.settings.model,
            output_type=DocumentExtraction,
            instructions=EXTRACTION_INSTRUCTIONS,
            model_settings=model_settings,
            retries=2,
        )

    async def extract(
        self,
        file_name: str,
        content: bytes,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        validate_upload(
            file_name=file_name,
            content=content,
            max_upload_bytes=self.settings.max_upload_bytes,
        )
        if not self.settings.provider_configured():
            raise ProviderNotConfiguredError(
                f"Configure as credenciais do provedor para {self.settings.model}."
            )

        if self.agent is None:
            self.agent = self._build_agent()

        media_type = media_type_for(file_name, content_type)
        pages = page_count(file_name, content)
        previews = extract_pdf_previews(file_name, content)
        prompt = (
            "Extraia os campos do documento usando somente o conteúdo visível. "
            "Quando houver uma imagem complementar da frente, use-a para ler os "
            "campos pequenos com prioridade. Não invente valores."
        )
        message_parts: list[object] = [
            prompt,
            BinaryContent(data=content, media_type=media_type),
        ]
        if previews:
            message_parts.append(_preview_binary_content(previews[0]))
        started = time.perf_counter()
        result = await self.agent.run(message_parts)
        extraction = result.output
        if not isinstance(extraction, DocumentExtraction):
            extraction = DocumentExtraction.model_validate(extraction)
        duration_ms = round((time.perf_counter() - started) * 1000)
        return to_api_response(
            extraction,
            pages=pages,
            duration_ms=duration_ms,
            previews=previews,
        )


def validate_upload(file_name: str | None, content: bytes, max_upload_bytes: int) -> None:
    if not file_name:
        raise UploadValidationError("Selecione um arquivo.")

    extension = PurePath(file_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise UploadValidationError("Formato não suportado. Use PDF, JPG, JPEG ou PNG.")
    if not content:
        raise UploadValidationError("O arquivo está vazio.")
    if len(content) > max_upload_bytes:
        limit_mb = max_upload_bytes / (1024 * 1024)
        raise UploadValidationError(f"O arquivo excede o limite local de {limit_mb:g} MB.")

    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise UploadValidationError("O arquivo não parece ser um PDF válido.")
        try:
            pages = len(PdfReader(BytesIO(content)).pages)
        except Exception as error:
            raise UploadValidationError("O arquivo não parece ser um PDF válido.") from error
        if pages < 1:
            raise UploadValidationError("O PDF não contém nenhuma página válida.")
    if extension == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise UploadValidationError("O arquivo não parece ser um PNG válido.")
    if extension in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise UploadValidationError("O arquivo não parece ser uma imagem JPEG válida.")


def media_type_for(file_name: str, content_type: str | None = None) -> str:
    extension = PurePath(file_name).suffix.lower()
    if extension == ".pdf":
        return "application/pdf"
    return IMAGE_MEDIA_TYPES[extension]


def page_count(file_name: str, content: bytes) -> int:
    if PurePath(file_name).suffix.lower() != ".pdf":
        return 1
    try:
        return len(PdfReader(BytesIO(content)).pages)
    except Exception:
        return 0


def _multiply_matrix(
    left: tuple[float, float, float, float, float, float],
    right: tuple[float, float, float, float, float, float],
) -> tuple[float, float, float, float, float, float]:
    la, lb, lc, ld, le, lf = left
    ra, rb, rc, rd, re, rf = right
    return (
        la * ra + lc * rb,
        lb * ra + ld * rb,
        la * rc + lc * rd,
        lb * rc + ld * rd,
        la * re + lc * rf + le,
        lb * re + ld * rf + lf,
    )


def extract_pdf_previews(file_name: str, content: bytes) -> list[dict[str, Any]]:
    """Extract prominent embedded PDF images for a local, zoomable preview."""

    if PurePath(file_name).suffix.lower() != ".pdf":
        return []
    try:
        reader = PdfReader(BytesIO(content))
        previews: list[dict[str, Any]] = []
        for page_number, page in enumerate(reader.pages, start=1):
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            images = {
                str(image.name).split(".", maxsplit=1)[0].lstrip("/"): image
                for image in page.images
            }
            if not images:
                continue

            ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
            stack: list[tuple[float, float, float, float, float, float]] = []
            for operands, operator in ContentStream(page.get_contents(), reader).operations:
                if operator == b"q":
                    stack.append(ctm)
                elif operator == b"Q":
                    ctm = stack.pop() if stack else (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
                elif operator == b"cm":
                    ctm = _multiply_matrix(ctm, tuple(float(value) for value in operands))
                elif operator == b"Do":
                    image_name = str(operands[0]).lstrip("/")
                    image = images.get(image_name)
                    if image is None:
                        continue
                    image_width = int(image.image.width)
                    image_height = int(image.image.height)
                    if min(image_width, image_height) < 200:
                        continue
                    a, b, c, d, e, f = ctm
                    points = (
                        (e, f),
                        (a + e, b + f),
                        (c + e, d + f),
                        (a + c + e, b + d + f),
                    )
                    left = max(0.0, min(point[0] for point in points))
                    right = min(page_width, max(point[0] for point in points))
                    y_values = [point[1] for point in points]
                    top = min(y_values) if d < 0 else page_height - max(y_values)
                    bottom = max(y_values) if d < 0 else page_height - min(y_values)
                    top = max(0.0, min(page_height, top))
                    bottom = max(0.0, min(page_height, bottom))
                    if right <= left or bottom <= top:
                        continue
                    image_format = (getattr(image.image, "format", None) or "").lower()
                    if image_format in {"jpeg", "jpg"}:
                        image_data = image.data
                        media_type = "image/jpeg"
                    else:
                        image_stream = BytesIO()
                        image.image.save(image_stream, format="PNG")
                        image_data = image_stream.getvalue()
                        media_type = "image/png"
                    image_src = (
                        f"data:{media_type};base64,"
                        f"{base64.b64encode(image_data).decode('ascii')}"
                    )
                    previews.append(
                        {
                            "page": page_number,
                            "label": image_name,
                            "primary": False,
                            "src": image_src,
                            "left": round(left / page_width, 4),
                            "top": round(top / page_height, 4),
                            "width": round((right - left) / page_width, 4),
                            "height": round((bottom - top) / page_height, 4),
                            "sourceWidth": image_width,
                            "sourceHeight": image_height,
                        }
                    )

        previews.sort(
            key=lambda item: (
                item["page"],
                -item["sourceWidth"] * item["sourceHeight"],
                item["top"],
            )
        )
        previews = previews[:MAX_PREVIEW_IMAGES]
        for index, preview in enumerate(previews):
            preview["primary"] = index == 0
            preview["label"] = "Frente" if index == 0 else "Verso" if index == 1 else "Detalhe"
        return previews
    except Exception:
        return []


def _preview_binary_content(preview: dict[str, Any]) -> BinaryContent:
    source = str(preview["src"])
    media_header, encoded = source.split(",", maxsplit=1)
    media_type = media_header.removeprefix("data:").split(";", maxsplit=1)[0]
    return BinaryContent(
        data=base64.b64decode(encoded),
        media_type=media_type,
    )


FIELD_LABELS = {
    "name": "Nome",
    "cpf": "CPF",
    "birth_date": "Data de nascimento",
    "issue_date": "Data de emissão",
    "validity": "Validade",
    "registration": "Registro",
    "category": "Categoria",
    "birth_place": "Local de nascimento",
    "nationality": "Nacionalidade",
    "parentage": "Filiação",
}
API_FIELD_NAMES = {
    "birth_date": "birthDate",
    "issue_date": "issueDate",
    "birth_place": "birthPlace",
}


def to_api_response(
    extraction: DocumentExtraction,
    pages: int,
    duration_ms: int,
    previews: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fields: dict[str, dict[str, Any]] = {}
    for key, value in extraction.fields.populated().items():
        api_key = API_FIELD_NAMES.get(key, key)
        fields[api_key] = {
            "value": value.value,
            "confidence": value.confidence,
            "label": FIELD_LABELS[key],
        }
    return {
        "kind": extraction.kind,
        "pages": pages,
        "fields": fields,
        "text": format_text(extraction),
        "warnings": extraction.warnings,
        "durationMs": duration_ms,
        "previews": previews or [],
    }


def format_text(extraction: DocumentExtraction) -> str:
    kind_label = extraction.kind.upper()
    lines = [f"DOCUMENTO: {kind_label}"]
    structured = [
        f"{FIELD_LABELS[key]}: {value.value}"
        for key, value in extraction.fields.populated().items()
        if value.value
    ]
    if structured:
        lines.extend(["", "DADOS ESTRUTURADOS", *structured])
    if extraction.transcription:
        lines.extend(["", "TRANSCRIÇÃO RECONHECIDA", extraction.transcription])
    return "\n".join(lines)
