from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AdminHealthRead(BaseModel):
    """`GET /admin/health` 응답. require_role(ADMIN) 가드가 통과했음을 알리는 ping."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"examples": [{"status": "ok"}]},
    )

    status: Literal["ok"] = Field(
        description="가드 통과 시 항상 'ok'. 본 엔드포인트는 권한 검증 진입점만 검증한다.",
        examples=["ok"],
    )
