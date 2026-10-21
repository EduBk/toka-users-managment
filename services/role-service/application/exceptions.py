"""Expected errors raised while executing role use cases."""


class RoleNotFound(Exception):
    """No role exists with the requested id."""


class RoleAlreadyExists(Exception):
    """A role with the same name already exists."""
