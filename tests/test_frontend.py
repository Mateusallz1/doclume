from __future__ import annotations

from pathlib import Path

INDEX_HTML = (
    Path(__file__).parents[1]
    / "src"
    / "doc_extractor_pydantic"
    / "static"
    / "index.html"
).read_text(encoding="utf-8")


def test_extracted_fields_are_display_only_and_have_copy_icon() -> None:
    assert 'document.createElement("input")' not in INDEX_HTML
    assert 'querySelectorAll("input[data-field]")' not in INDEX_HTML
    assert 'className = "field-value"' in INDEX_HTML
    assert 'class="copy-icon"' in INDEX_HTML
    assert '.field-card[data-field-label="parentage"] { grid-column: 1 / -1; }' in INDEX_HTML
    assert "white-space: pre-wrap" in INDEX_HTML


def test_pdf_uses_embedded_detail_instead_of_full_viewer() -> None:
    assert 'id="pdf-viewer"' not in INDEX_HTML
    assert 'id="pdf-preview"' not in INDEX_HTML
    assert "pdfViewer" not in INDEX_HTML
    assert "updatePdfPreview" not in INDEX_HTML
    assert 'id="focus-image"' in INDEX_HTML
    assert 'id="focus-zoom-in"' in INDEX_HTML
    assert 'id="focus-zoom-out"' in INDEX_HTML


def test_pdf_result_exposes_main_embedded_image_preview() -> None:
    assert 'id="focus-panel"' in INDEX_HTML
    assert 'id="focus-image"' in INDEX_HTML
    assert 'id="focus-thumbnails"' in INDEX_HTML
    assert "renderFocusPreviews(data.previews)" in INDEX_HTML


def test_selecting_a_new_file_clears_previous_result() -> None:
    change_handler = INDEX_HTML.split('input.addEventListener("change"', maxsplit=1)[1]
    change_handler = change_handler.split('form.addEventListener("submit"', maxsplit=1)[0]
    assert "lastData = null;" in change_handler
    assert 'result.classList.add("hidden");' in change_handler
    assert "fields.replaceChildren();" in change_handler
    assert 'rawText.textContent = "";' in change_handler


def test_copy_failure_has_a_friendly_message() -> None:
    assert "Não foi possível copiar." in INDEX_HTML
    assert "Selecione o texto e copie manualmente." in INDEX_HTML
