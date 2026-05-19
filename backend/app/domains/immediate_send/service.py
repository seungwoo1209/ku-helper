from app.domains.immediate_send.models import ImmediateSendRequest
from app.domains.immediate_send.repository import ImmediateSendRepository
from app.domains.immediate_send.schemas import TransitDispatchRequest
from app.domains.notifications.models import NotificationType
from app.domains.users.models import User


class ImmediateSendService:
    def __init__(self, repository: ImmediateSendRepository) -> None:
        self._repository = repository

    async def request_lunch_dispatch(self, user: User) -> ImmediateSendRequest:
        # 사용자 상태(ACTIVE) 검증은 get_current_user 의존성이 이미 수행.
        # 활성 LUNCH 구독 유무는 검증하지 않는다 — 즉시 발송은 구독과 독립이다.
        return await self._repository.create(
            user_id=user.id,
            type_=NotificationType.LUNCH,
            payload={},
        )

    async def request_transit_dispatch(
        self, user: User, body: TransitDispatchRequest
    ) -> ImmediateSendRequest:
        # station_name·line 은 봇 워커가 SubwayClient.fetch_arrivals + embed 빌더로 전달한다.
        # 활성 TRANSIT 구독 유무는 검증하지 않는다 — 즉시 발송은 구독과 독립이다.
        return await self._repository.create(
            user_id=user.id,
            type_=NotificationType.TRANSIT,
            payload={"station_name": body.station_name, "line": body.line},
        )
