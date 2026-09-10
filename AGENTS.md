# AGENTS.md

This file is the concise map of the repository. Detailed documentation and
versioned decisions are the system of record; consult them before expanding
scope.

## Routing

- [ARCHITECTURE.md](ARCHITECTURE.md): system flow, layers, and boundaries.
- [docs/README.md](docs/README.md): project documentation index.
- [docs/QUALITY.md](docs/QUALITY.md): gates, acceptance criteria, and testing gaps.
- [docs/RELIABILITY.md](docs/RELIABILITY.md): local operation and known risks.
- [docs/SECURITY.md](docs/SECURITY.md): personal data, providers, and secrets.
- [docs/exec-plans/README.md](docs/exec-plans/README.md): versioned execution plans.

## Work Loop

1. Read the map and the affected domain document.
2. Make the smallest change that preserves documented invariants.
3. Run `uv run python scripts/check_harness.py` and all quality gates.
4. Review the diff, staged files, and untracked/ignored files before proposing a commit.

## Invariants

- The default pipeline uses `google:gemini-3.5-flash-lite` with `thinking_level=MINIMAL`.
- The local server runs on `127.0.0.1:8788`.
- Real documents do not enter tests or benchmarks without explicit authorization.
- The file name is never sent to the model; only the content is analyzed.
- No text, field value, document, file name, or secret goes into logs.
- Invalid values are not corrected by inference: they are discarded and flagged with warnings.
- Commit, push, merge, and deploy are separate decisions.

## Quick Gates

```powershell
uv run pytest
uv run ruff check src tests
uv run python -m compileall -q src tests
uv lock --check
uv pip check
node --check src/doc_extractor_pydantic/static/app.js
```
