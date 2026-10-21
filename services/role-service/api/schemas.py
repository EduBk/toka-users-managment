"""Request and response schemas (Pydantic at the system boundary)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from domain.role.entity import Role


class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=255)
    permissions: list[str] = Field(default_factory=list)


class RolePermissionsRequest(BaseModel):
    permissions: list[str] = Field(default_factory=list)


class AssignmentRequest(BaseModel):
    role_id: UUID


class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: str
    permissions: list[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, role: Role) -> "RoleResponse":
        return cls(
            id=role.id,
            name=role.name.value,
            description=role.description.value,
            permissions=list(role.permission_names()),
            created_at=role.created_at,
            updated_at=role.updated_at,
        )


class UserPermissionsResponse(BaseModel):
    user_id: UUID
    permissions: list[str]
