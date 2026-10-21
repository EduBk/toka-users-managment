import pytest

from domain.role.exceptions import (
    InvalidPermissionName,
    InvalidRoleDescription,
    InvalidRoleName,
)
from domain.role.value_objects import (
    PermissionName,
    RoleDescription,
    RoleName,
)


@pytest.mark.parametrize("value", ["Admin", "  ADMIN  ", "read_only"])
def test_role_name_is_normalized(value: str) -> None:
    assert RoleName(value).value == value.strip().lower()


@pytest.mark.parametrize("value", ["", "   ", "admin role", "x" * 61, "-admin"])
def test_role_name_rejects_invalid_values(value: str) -> None:
    with pytest.raises(InvalidRoleName):
        RoleName(value)


def test_role_description_is_trimmed() -> None:
    assert RoleDescription("  System administrator  ").value == "System administrator"


def test_role_description_rejects_too_long_values() -> None:
    with pytest.raises(InvalidRoleDescription):
        RoleDescription("x" * 256)


@pytest.mark.parametrize("value", ["Users:Write", " ai:use "])
def test_permission_name_is_normalized(value: str) -> None:
    assert PermissionName(value).value == value.strip().lower()


@pytest.mark.parametrize("value", ["", "users write", "1users:read", "users:"])
def test_permission_name_rejects_invalid_values(value: str) -> None:
    with pytest.raises(InvalidPermissionName):
        PermissionName(value)
