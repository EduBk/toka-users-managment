"""Expected errors raised while executing auth use cases."""


class InvalidCredentials(Exception):
    """The email/password pair is not valid or the account is inactive."""


class InvalidToken(Exception):
    """The token is malformed, expired, revoked or of the wrong type."""


class AccountNotFound(Exception):
    """No account is registered with the requested email."""
