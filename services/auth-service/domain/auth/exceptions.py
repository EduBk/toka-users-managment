"""Expected errors raised by the identity domain."""


class AuthDomainError(Exception):
    """Base class for identity domain errors."""


class InvalidEmail(AuthDomainError):
    """The email does not satisfy the value object rules."""


class InvalidAccount(AuthDomainError):
    """The account cannot be built with the given data."""


class EmailAlreadyRegistered(AuthDomainError):
    """An account with the same email already exists."""
