"""Generate the RS256 key pair used by auth-service (E2.4).

Keys are written to ``infra/keys/`` and never versioned (see .gitignore).
"""

import argparse
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_OUTPUT = _REPO_ROOT / "infra" / "keys"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="directory where jwt_private.pem and jwt_public.pem are written",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite the keys if they already exist",
    )
    args = parser.parse_args()

    private_path = args.output_dir / "jwt_private.pem"
    public_path = args.output_dir / "jwt_public.pem"
    if private_path.exists() and not args.force:
        print(f"{private_path} already exists; use --force to overwrite")
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    private_path.chmod(0o600)

    print(f"wrote {private_path}")
    print(f"wrote {public_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
