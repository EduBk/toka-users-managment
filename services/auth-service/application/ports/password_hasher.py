"""Password hashing port.

The application never sees the plain password after hashing or verifying it;
the algorithm is an infrastructure detail.
"""

from typing import Protocol


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...
