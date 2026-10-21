"""Search versioned files for credential patterns (E2.11).

Skips the paths ignored by ``.gitignore`` that hold local secrets (``.env``,
``infra/keys/``) and build artifacts. ``change-me`` placeholders and test
fixtures under ``tests/`` are allowed. Exits with 1 if anything is found.
"""

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

_SKIP_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "coverage",
    "htmlcov",
    "__pycache__",
    ".pytest_cache",
    "keys",
}
_SKIP_FILES = {".env"}
_SKIP_SUFFIXES = {".pyc", ".svg", ".png", ".jpg", ".pdf", ".lock"}

_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "openai key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "aws key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "url credentials": re.compile(r"://[^:/\s\"'$]+:(?!change-me@)[^@\s\"'$]+@"),
    "assigned secret": re.compile(
        r"(?i)\b(password|passwd|secret|api_key|apikey)\s*[:=]\s*[\"'](?!change-me)[^\"'\s]{8,}[\"']"
    ),
}


def _candidates() -> list[Path]:
    files: list[Path] = []
    for path in _REPO_ROOT.rglob("*"):
        relative = path.relative_to(_REPO_ROOT)
        if not path.is_file() or any(part in _SKIP_DIRS for part in relative.parts):
            continue
        if path.name in _SKIP_FILES or path.suffix in _SKIP_SUFFIXES:
            continue
        if ".egg-info" in str(relative) or "tests" in relative.parts:
            continue
        files.append(path)
    return files


def main() -> int:
    findings: list[str] = []
    for path in _candidates():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for name, pattern in _PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{path.relative_to(_REPO_ROOT)}:{number}: {name}")

    for finding in findings:
        print(finding)
    print(f"{len(findings)} potential secret(s) found")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
