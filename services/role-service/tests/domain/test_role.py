from domain.role.entity import Permission, Role
from domain.role.value_objects import PermissionName, RoleName


def test_create_builds_the_role_with_sorted_permissions() -> None:
    role = Role.create(
        name=RoleName("admin"),
        permissions=frozenset(
            {
                Permission(PermissionName("users:write")),
                Permission(PermissionName("users:read")),
            }
        ),
    )

    assert role.name.value == "admin"
    assert role.permission_names() == ("users:read", "users:write")


def test_update_permissions_replaces_the_set() -> None:
    role = Role.create(
        name=RoleName("auditor"),
        permissions=frozenset(
            {Permission(PermissionName("audit:read"))}
        ),
    )

    role.update_permissions(
        frozenset({Permission(PermissionName("audit:read")), Permission(PermissionName("ai:use"))})
    )

    assert role.permission_names() == ("ai:use", "audit:read")


def test_update_with_the_same_permissions_keeps_the_timestamp() -> None:
    role = Role.create(
        name=RoleName("user"),
        permissions=frozenset({Permission(PermissionName("ai:use"))}),
    )
    updated_at = role.updated_at

    role.update_permissions(
        frozenset({Permission(PermissionName("ai:use"))})
    )

    assert role.updated_at == updated_at
