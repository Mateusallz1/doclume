from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse

from .config import Settings
from .extractor import (
    DocumentExtractor,
    ProviderNotConfiguredError,
    UploadValidationError,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

settings = Settings.from_env()
extractor = DocumentExtractor(settings)
static_index = Path(__file__).with_name("static") / "index.html"

app = FastAPI(
    title="Doc Extractor PydanticAI",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' blob: data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "form-action 'self'"
    )
    return response


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(static_index.read_text(encoding="utf-8"))


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "storage": "temporary-only",
        "model": settings.model,
        "providerConfigured": settings.provider_configured(),
    }


@app.post("/api/extract")
async def extract(document: UploadFile = File(...)) -> dict[str, object]:
    content = await document.read(settings.max_upload_bytes + 1)
    try:
        result = await extractor.extract(
            file_name=document.filename or "",
            content=content,
            content_type=document.content_type,
        )
    except UploadValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except ProviderNotConfiguredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logger.error(
            "document extraction failed: error_type=%s",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Não foi possível processar o documento.",
        ) from None
    finally:
        await document.close()

    logger.info(
        "document extraction completed: kind=%s pages=%s fields=%s duration_ms=%s",
        result["kind"],
        result["pages"],
        len(result["fields"]),
        result["durationMs"],
    )
    return result


def run() -> None:
    import uvicorn

    uvicorn.run(
        "doc_extractor_pydantic.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
