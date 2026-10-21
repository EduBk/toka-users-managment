"""Expected errors raised by the roles context."""


class InvalidRoleName(Exception):
    """The role name is empty, too long or has invalid characters."""


class InvalidRoleDescription(Exception):
    """The role description is too long."""


class InvalidPermissionName(Exception):
    """A permission name is empty, too long or has invalid characters."""
