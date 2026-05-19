from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LunchDispatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: int
    requested_at: datetime
