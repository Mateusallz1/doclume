# Architecture

## Scope

Local pilot for extracting RG and CNH data from images and PDFs. There is no
database, message queue, permanent storage, or automated submission to external
systems.

## Main Flow

```text
browser
  -> FastAPI /api/extract
  -> local upload validation
  -> DocumentExtractor
  -> primary embedded image as support, when present
  -> PydanticAI Agent
  -> configured multimodal provider
  -> DocumentExtraction validated by Pydantic
  -> structured response for human review
```

## Layers

- `main.py`: HTTP runtime, health checks, and error mappings.
- `extractor.py`: upload handling, PDF metadata, embedded images, multimodal
  input, and API contract.
- `models.py`: Pydantic models and semantic field validations.
- `prompts.py`: extraction instructions and rules preventing data hallucination.
- `static/index.html`, `static/app.css`, `static/app.js`: local interface, zoomed
  detail view, review, and copying. Split into three files so the CSP does not
  require `'unsafe-inline'`.
- `tests/`: tests running without external calls to the provider.

## Dependency Boundaries

- The frontend interface must not know provider details, prompts, or credentials.
- The model must not be treated as a source of truth without validation and review.
- The backend must not persist uploaded documents.
- Security and privacy rules must be mechanically enforceable by tests or checks
  whenever possible.
