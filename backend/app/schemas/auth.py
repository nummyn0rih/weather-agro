from datetime import datetime

from pydantic import BaseModel, Field


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
