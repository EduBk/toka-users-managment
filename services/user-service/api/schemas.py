"""Request and response schemas (Pydantic at the system boundary)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from domain.user.entity import User
from domain.user.value_objects import UserStatus


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=120)
    profile: dict[str, Any] = Field(default_factory=dict)


class UserUpdateRequest(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=254)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    profile: dict[str, Any] | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UserUpdateRequest":
        if self.email is None and self.name is None and self.profile is None:
            raise ValueError("provide at least one field to update")
        return self


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    status: UserStatus
    profile: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email.value,
            name=user.name.value,
            status=user.status,
            profile=user.profile.value,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
