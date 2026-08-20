from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DocumentKind = Literal["cnh", "rg", "unknown"]
FieldConfidence = Literal["high", "medium", "low"]


def _cpf_is_valid(value: str) -> bool:
    if not re.fullmatch(r"\s*\d{3}[ .-]?\d{3}[ .-]?\d{3}[ .-]?\d{2}\s*", value):
        return False
    digits = re.sub(r"\D", "", value)
    if len(digits) != 11 or re.fullmatch(r"(\d)\1{10}", digits):
        return False
    for position in (9, 10):
        total = sum(
            int(digits[index]) * (position + 1 - index)
            for index in range(position)
        )
        remainder = (total * 10) % 11
        expected = 0 if remainder == 10 else remainder
        if expected != int(digits[position]):
            return False
    return True


def _br_date(value: str) -> date | None:
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", value.strip()):
        return None
    day, month, year = (int(part) for part in value.split("/"))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _registration_is_valid(value: str) -> bool:
    if not re.fullmatch(r"[\d .-]+", value):
        return False
    digits = re.sub(r"\D", "", value)
    return 8 <= len(digits) <= 11 and not re.fullmatch(r"(\d)\1+", digits)


def _category_is_valid(value: str) -> bool:
    return re.fullmatch(r"(?:[A-E]|A[BCDE]|ACC)", value.strip().upper()) is not None


class ExtractedField(BaseModel):
    """A value found in the document, with an explicit uncertainty level."""

    model_config = ConfigDict(extra="forbid")

    value: str | None = Field(
        default=None,
        description="Exact value visible in the document, or null when absent/illegible.",
    )
    confidence: FieldConfidence = Field(
        default="low",
        description="Confidence based on legibility and proximity to the field label.",
    )

    @field_validator("value", mode="before")
    @classmethod
    def blank_value_is_null(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class DocumentFields(BaseModel):
    """Known RG/CNH fields returned by the extraction agent."""

    model_config = ConfigDict(extra="forbid")

    name: ExtractedField | None = Field(default=None, description="Nome completo")
    cpf: ExtractedField | None = Field(default=None, description="CPF")
    birth_date: ExtractedField | None = Field(default=None, description="Data de nascimento")
    issue_date: ExtractedField | None = Field(default=None, description="Data de emissão")
    validity: ExtractedField | None = Field(default=None, description="Data de validade")
    registration: ExtractedField | None = Field(default=None, description="Número de registro")
    category: ExtractedField | None = Field(default=None, description="Categoria da habilitação")
    birth_place: ExtractedField | None = Field(default=None, description="Local de nascimento")
    nationality: ExtractedField | None = Field(default=None, description="Nacionalidade")
    parentage: ExtractedField | None = Field(default=None, description="Filiação")

    def sanitize(self) -> list[str]:
        """Drop semantically invalid values without guessing replacements."""

        issues: list[str] = []
        checks = (
            ("cpf", "O CPF", "confirmado", _cpf_is_valid),
            ("registration", "O registro", "confirmado", _registration_is_valid),
            ("category", "A categoria", "confirmada", _category_is_valid),
        )
        for attribute, label, verb, validator in checks:
            field = getattr(self, attribute)
            if field is None or field.value is None:
                continue
            if not validator(field.value):
                setattr(self, attribute, None)
                issues.append(f"{label} não pôde ser {verb}.")
            elif attribute == "category":
                field.value = field.value.strip().upper()

        if self.parentage and self.parentage.value:
            parentage = self.parentage.value.replace(r"\n", "\n")
            parentage = re.sub(r"\s*(?:;|\||\s/\s)\s*", "\n", parentage)
            parentage = re.sub(r"[ \t]+\n", "\n", parentage)
            parentage = re.sub(r"\n{2,}", "\n", parentage).strip()
            self.parentage.value = parentage

        date_fields = ("birth_date", "issue_date", "validity")
        date_labels = {
            "birth_date": "nascimento",
            "issue_date": "emissão",
            "validity": "validade",
        }
        parsed_dates: dict[str, date] = {}
        for attribute in date_fields:
            field = getattr(self, attribute)
            if field is None or field.value is None:
                continue
            parsed = _br_date(field.value)
            if parsed is None:
                setattr(self, attribute, None)
                issues.append(f"A data de {date_labels[attribute]} não pôde ser confirmada.")
            else:
                parsed_dates[attribute] = parsed

        birth_date = parsed_dates.get("birth_date")
        issue_date = parsed_dates.get("issue_date")
        validity = parsed_dates.get("validity")
        if birth_date and issue_date and birth_date >= issue_date:
            self.birth_date = None
            self.issue_date = None
            issues.append("As datas de nascimento e emissão são incompatíveis.")
        if issue_date and validity and validity <= issue_date:
            self.issue_date = None
            self.validity = None
            issues.append("As datas de emissão e validade são incompatíveis.")
        return issues

    def populated(self) -> dict[str, ExtractedField]:
        return {
            key: value
            for key, value in self
            if value is not None and value.value is not None
        }


class DocumentExtraction(BaseModel):
    """Structured result expected from PydanticAI."""

    model_config = ConfigDict(extra="forbid")

    kind: DocumentKind = Field(
        default="unknown",
        description="Classificação do documento: cnh, rg ou unknown.",
    )
    fields: DocumentFields = Field(default_factory=DocumentFields)
    transcription: str = Field(
        default="",
        description="Transcrição limpa do texto que está legível no documento.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Avisos de legibilidade, conflito ou campo não localizado.",
    )

    @field_validator("transcription", mode="before")
    @classmethod
    def normalize_transcription(cls, value: object) -> str:
        return value.strip() if isinstance(value, str) else ""

    @model_validator(mode="after")
    def validate_extracted_fields(self) -> DocumentExtraction:
        for issue in self.fields.sanitize():
            if issue not in self.warnings:
                self.warnings.append(issue)
        return self
