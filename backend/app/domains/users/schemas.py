from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    discord_id: int
    discord_username: str
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    # TODO: 수정 가능한 필드는 후속 PR에서 정의.
    pass
