"""Expected errors raised by the user management domain."""


class UserDomainError(Exception):
    """Base class for user domain errors."""


class InvalidEmail(UserDomainError):
    """The email does not satisfy the value object rules."""


class InvalidUserName(UserDomainError):
    """The name is empty or longer than the allowed limit."""


class InvalidProfile(UserDomainError):
    """The profile is not a JSON object."""


class InvalidUserStatus(UserDomainError):
    """The status is not one of the supported values."""


class EmailAlreadyExists(UserDomainError):
    """A user with the same email already exists (active or inactive)."""


class InvalidUserState(UserDomainError):
    """The requested state transition is not allowed."""
