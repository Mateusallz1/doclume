"""Browser tests for the flows that string checks cannot observe."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("playwright.sync_api")

from playwright.sync_api import Page  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"synthetic"

RESULT = {
    "kind": "cnh",
    "pages": 1,
    "fields": {
        "name": {"value": "MARIA DE TESTE", "confidence": "high", "label": "Nome"},
        "cpf": {"value": "123.456.789-09", "confidence": "medium", "label": "CPF"},
        "birthDate": {
            "value": "10/02/1990",
            "confidence": "low",
            "label": "Data de nascimento",
        },
    },
    "missing": [
        {"key": "validity", "label": "Validade"},
        {"key": "category", "label": "Categoria"},
    ],
    "text": "DOCUMENTO: CNH\nNome: MARIA DE TESTE",
    "warnings": ["A categoria não pôde ser confirmada.", "Confira a data de emissão."],
    "durationMs": 12,
    "previews": [],
}


def upload(page: Page, name: str = "doc.png") -> None:
    page.set_input_files(
        "#document",
        files=[{"name": name, "mimeType": "image/png", "buffer": PNG}],
    )


def answer(page: Page, body: dict | None = None, status: int = 200) -> None:
    page.route(
        "**/api/extract",
        lambda route: route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps(body if body is not None else RESULT),
        ),
    )


def analyze(page: Page) -> None:
    page.click("#submit")
    page.wait_for_selector("#result:not(.hidden)")


@pytest.fixture
def page_at_home(page: Page, live_server: str) -> Page:
    page.goto(live_server)
    return page


def test_the_page_runs_without_tripping_the_content_security_policy(
    page: Page, live_server: str
) -> None:
    messages: list[str] = []
    page.on("console", lambda message: messages.append(message.text))
    page.goto(live_server)
    answer(page)
    upload(page)
    analyze(page)

    blocked = [text for text in messages if "Content Security Policy" in text]
    assert blocked == []


def test_extraction_renders_fields_warnings_and_placeholders(page_at_home: Page) -> None:
    page = page_at_home
    answer(page)
    upload(page)
    analyze(page)

    assert page.locator('.field-card[data-found="true"]').count() == 3
    assert page.locator('.field-card[data-found="false"]').count() == 2
    assert page.locator('[data-field-label="validity"] .field-value').inner_text() == (
        "Não identificado"
    )
    assert page.locator('[data-field-label="cpf"] .field-confidence').inner_text() == "conferir"
    assert page.locator('[data-field-label="birthDate"] .field-confidence').inner_text() == (
        "conferir com atenção"
    )
    assert page.locator('[data-field-label="name"] .field-confidence').count() == 0


def test_warnings_render_inside_one_visible_alert(page_at_home: Page) -> None:
    page = page_at_home
    answer(page)
    upload(page)
    analyze(page)

    alert = page.locator("#warning-box")
    assert alert.is_visible()
    assert page.locator("#warnings li").count() == 2
    assert "categoria" in page.locator("#warnings li").first.inner_text()


def test_result_without_warnings_hides_the_alert(page_at_home: Page) -> None:
    page = page_at_home
    answer(page, {**RESULT, "warnings": []})
    upload(page)
    analyze(page)

    assert not page.locator("#warning-box").is_visible()


def test_a_response_in_flight_cannot_land_on_a_new_selection(page_at_home: Page) -> None:
    page = page_at_home
    held = []
    page.route("**/api/extract", lambda route: held.append(route))

    upload(page, "primeiro.png")
    page.click("#submit")
    for _ in range(100):
        if held:
            break
        page.wait_for_timeout(50)
    assert held, "a requisição não chegou a ser feita"

    upload(page, "segundo.png")
    try:
        held[0].fulfill(
            status=200, content_type="application/json", body=json.dumps(RESULT)
        )
    except Exception:
        pass  # The abort already killed the request, which is the point.
    page.wait_for_timeout(300)

    assert page.locator("#result").is_hidden()
    assert page.locator(".field-card").count() == 0
    assert "Tudo certo" not in page.locator("#status").inner_text()
    assert not page.locator("#submit").is_disabled()


def test_selecting_a_new_file_clears_the_previous_result(page_at_home: Page) -> None:
    page = page_at_home
    answer(page)
    upload(page)
    analyze(page)
    assert page.locator(".field-card").count() > 0

    upload(page, "outro.png")

    assert page.locator("#result").is_hidden()
    assert page.locator(".field-card").count() == 0
    assert page.locator("#raw-text").inner_text() == ""


def test_error_detail_from_the_api_reaches_the_status_line(page_at_home: Page) -> None:
    page = page_at_home
    answer(page, {"detail": "O arquivo excede o limite local de 15 MB."}, status=413)
    upload(page)
    page.click("#submit")
    page.wait_for_selector("#status.error")

    assert "excede o limite local" in page.locator("#status").inner_text()
    assert page.locator("#result").is_hidden()
    assert not page.locator("#submit").is_disabled()


def test_result_survives_a_narrow_viewport_without_sideways_scroll(page_at_home: Page) -> None:
    page = page_at_home
    answer(page)
    upload(page)
    analyze(page)

    page.set_viewport_size({"width": 620, "height": 780})
    page.wait_for_timeout(200)

    assert page.locator("#result").is_visible()
    assert page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )


def test_copying_all_data_skips_the_fields_that_were_not_found(page_at_home: Page) -> None:
    page = page_at_home
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    answer(page)
    upload(page)
    analyze(page)

    page.click("#copy")
    page.wait_for_timeout(200)
    copied = page.evaluate("navigator.clipboard.readText()")

    assert "Nome: MARIA DE TESTE" in copied
    assert "Não identificado" not in copied
    assert "Validade" not in copied
