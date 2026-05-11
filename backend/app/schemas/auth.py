from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50, examples=["admin"])
    password: str = Field(..., min_length=1, examples=["changeme"])


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class TelegramBindCodeResponse(BaseModel):
    code: str = Field(..., examples=["12345678"])
    expires_at: datetime
    bot_username: str | None = None


class TelegramBindStatus(BaseModel):
    chat_id: int | None
    bound: bool


class UserMe(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_active: bool
    telegram_chat_id: int | None = None
    created_at: datetime


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def _new_must_differ(self) -> "ChangePasswordRequest":
        if self.new_password == self.old_password:
            raise ValueError("New password must differ from old password")
        return self
