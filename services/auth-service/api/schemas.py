"""Request and response schemas (Pydantic at the system boundary)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from application.dto import AuthenticationResult
from domain.auth.entity import Account


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=72)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        # bcrypt only considers the first 72 bytes; reject longer inputs instead
        # of silently truncating them.
        if len(value.encode("utf-8")) > 72:
            raise ValueError("password must be at most 72 bytes")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class AccountResponse(BaseModel):
    id: UUID
    email: str
    is_active: bool
    created_at: datetime

    @classmethod
    def from_domain(cls, account: Account) -> "AccountResponse":
        return cls(
            id=account.id,
            email=account.email.value,
            is_active=account.is_active,
            created_at=account.created_at,
        )


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

    @classmethod
    def from_result(cls, result: AuthenticationResult) -> "TokenResponse":
        return cls(
            access_token=result.access_token.token,
            refresh_token=result.refresh_token.token,
            expires_in=result.access_token.expires_in,
        )
