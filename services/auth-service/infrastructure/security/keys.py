"""Load the RS256 key pair mounted into the container (E2.4)."""

from pathlib import Path

_GENERATE_HINT = (
    "run 'py scripts/generate_jwt_keys.py' from the repository root and mount "
    "infra/keys/ into the container"
)


def read_key_pair(
    private_key_path: str, public_key_path: str
) -> tuple[str, str]:
    return _read(private_key_path), _read(public_key_path)


def _read(path: str) -> str:
    key_file = Path(path)
    if not key_file.is_file():
        raise RuntimeError(f"JWT key not found at '{path}'; {_GENERATE_HINT}")
    return key_file.read_text(encoding="utf-8")
