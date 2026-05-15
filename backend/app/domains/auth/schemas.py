from pydantic import BaseModel, ConfigDict


class LoginUrlRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    authorization_url: str
    state: str


class TokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
