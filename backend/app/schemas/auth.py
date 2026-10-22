from pydantic import Field

from app.schemas.common import APIModel


class LoginIn(APIModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordIn(APIModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)
