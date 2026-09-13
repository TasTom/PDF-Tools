"""Schemas Pydantic pour l'authentification (requetes / reponses)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Le mot de passe doit faire au moins 8 caracteres")
        if not any(c.isupper() for c in v):
            raise ValueError("Le mot de passe doit contenir au moins 1 majuscule")
        if not any(c.isdigit() for c in v):
            raise ValueError("Le mot de passe doit contenir au moins 1 chiffre")
        return v

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.isalnum():
            raise ValueError("Le nom d'utilisateur ne doit contenir que des lettres et chiffres")
        if len(v) < 3:
            raise ValueError("Le nom d'utilisateur doit faire au moins 3 caracteres")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    auth_provider: str
    daily_usage: int = 0
    daily_limit: int = 20
    created_at: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    user_id: Optional[int] = None


class UsageInfo(BaseModel):
    """Quota quotidien d'operations (anti-abus)."""

    daily_usage: int
    daily_limit: int
    remaining: int
