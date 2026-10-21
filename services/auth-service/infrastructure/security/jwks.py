"""JWKS document built from the public RS256 key."""

import base64
import hashlib
import json

from cryptography.hazmat.primitives import serialization
from jwt.algorithms import RSAAlgorithm


def jwt_key_id(public_key_pem: str) -> str:
    """Stable key id derived from the public key (no key rotation in E2.4)."""

    public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    digest = hashlib.sha256(der).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_jwks(public_key_pem: str) -> dict[str, list[dict[str, str]]]:
    public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    jwk = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk.update({"kid": jwt_key_id(public_key_pem), "use": "sig", "alg": "RS256"})
    return {"keys": [jwk]}
