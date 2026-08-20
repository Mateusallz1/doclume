from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "AGENTS.md",
    "ARCHITECTURE.md",
    "docs/README.md",
    "docs/QUALITY.md",
    "docs/RELIABILITY.md",
    "docs/SECURITY.md",
    "docs/exec-plans/README.md",
)
REQUIRED_MAP_LINKS = (
    "ARCHITECTURE.md",
    "docs/README.md",
    "docs/QUALITY.md",
    "docs/RELIABILITY.md",
    "docs/SECURITY.md",
    "docs/exec-plans/README.md",
)


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required knowledge file: {relative}")

    agents = ROOT / "AGENTS.md"
    if agents.is_file():
        lines = agents.read_text(encoding="utf-8").splitlines()
        if len(lines) > 120:
            errors.append(f"AGENTS.md is too large: {len(lines)} lines (max 120)")
        for target in REQUIRED_MAP_LINKS:
            if target not in agents.read_text(encoding="utf-8"):
                errors.append(f"AGENTS.md does not route to: {target}")

        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", agents.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#")):
                continue
            if not (ROOT / target).is_file():
                errors.append(f"broken AGENTS.md link: {target}")

    if errors:
        print("HARNESS_CHECK_FAILED")
        print("\n".join(f"- {error}" for error in errors))
        return 1

    print("HARNESS_CHECK_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
