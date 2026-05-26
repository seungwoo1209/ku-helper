from datetime import date, datetime, time, timedelta, timezone

from app.domains.notifications.exceptions import (
    InvalidHistoryDateRange,
    NotificationForbidden,
    NotificationNotFound,
)
from app.domains.notifications.models import (
    Notification,
    NotificationDeliveryStatus,
    NotificationType,
)
from app.domains.notifications.repository import (
    NotificationHistoryView,
    NotificationRepository,
)
from app.domains.notifications.schemas import (
    LibraryUpdate,
    LunchUpdate,
    NotificationCreate,
    TransitUpdate,
)

# F-17 정책 상수.
_HISTORY_MAX_WINDOW = timedelta(days=30)


class NotificationService:
    def __init__(self, repository: NotificationRepository) -> None:
        self._repository = repository

    async def list_for_user(self, user_id: int) -> list[Notification]:
        return await self._repository.list_by_user(user_id)

    async def list_for_user_by_type(
        self, user_id: int, type_: NotificationType
    ) -> list[Notification]:
        return await self._repository.list_by_user_and_type(user_id, type_)

    async def get_for_user(self, user_id: int, notification_id: int) -> Notification:
        return await self._get_owned(user_id, notification_id)

    async def create_for_user(
        self, user_id: int, body: NotificationCreate
    ) -> Notification:
        # body는 Pydantic discriminated union으로 라우터 단에서 이미 검증됨.
        # model_dump(mode="json")은 time/Enum 같은 값을 JSONB에 안전한 형태로 정규화한다.
        config = body.config.model_dump(mode="json")  # type: ignore[union-attr]
        return await self._repository.create(
            user_id=user_id,
            type_=body.type,  # type: ignore[union-attr]
            enabled=body.enabled,  # type: ignore[union-attr]
            config=config,
        )

    async def update_for_user(
        self,
        user_id: int,
        notification_id: int,
        expected_type: NotificationType,
        body: TransitUpdate | LunchUpdate | LibraryUpdate,
    ) -> Notification:
        notification = await self._get_owned(user_id, notification_id)
        # 다른 type 엔드포인트로 접근한 경우. 정보 누출 방지를 위해 404로 마스킹.
        if notification.type != expected_type:
            raise NotificationNotFound()
        config = body.config.model_dump(mode="json") if body.config else None
        return await self._repository.update(
            notification, enabled=body.enabled, config=config
        )

    async def delete_for_user(self, user_id: int, notification_id: int) -> None:
        notification = await self._get_owned(user_id, notification_id)
        await self._repository.delete(notification)

    async def list_history(
        self,
        user_id: int,
        *,
        date_from: date | None,
        date_to: date | None,
        type_: NotificationType | None,
        status: NotificationDeliveryStatus | None,
        limit: int,
    ) -> list[NotificationHistoryView]:
        """F-17 알림 발송 이력 조회. 30일 상한·역순 범위는 도메인 예외로 거절한다.

        윈도우 규칙:
        - 둘 다 미지정: `now - 30d ~ now` (최근 30일).
        - `date_to` 만 지정: `date_to - 30d ~ date_to`.
        - `date_from` 만 지정: `date_from ~ date_from + 30d`.
        - 둘 다 지정: 그대로 사용하되 `from < to` + 범위 ≤ 30d 검증.
        - `date_to` 는 inclusive 의미라 다음 자정으로 +1d 한 뒤 `<` 비교(repository).
        """
        sent_at_from, sent_at_to = self._resolve_window(date_from, date_to)
        return await self._repository.list_history_for_user(
            user_id,
            sent_at_from=sent_at_from,
            sent_at_to=sent_at_to,
            type_=type_,
            status=status,
            limit=limit,
        )

    @staticmethod
    def _resolve_window(
        date_from: date | None, date_to: date | None
    ) -> tuple[datetime, datetime]:
        # 모든 비교는 UTC 기준. PG 컬럼이 `DateTime(timezone=True)` 라 tz-aware 가
        # 필요하다.
        now = datetime.now(tz=timezone.utc)
        if date_from is None and date_to is None:
            return now - _HISTORY_MAX_WINDOW, now

        if date_from is not None and date_to is None:
            sent_at_from = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
            return sent_at_from, sent_at_from + _HISTORY_MAX_WINDOW

        if date_from is None and date_to is not None:
            # date_to 는 inclusive day → 다음 자정 직전을 상한으로 잡기 위해 +1d.
            sent_at_to = datetime.combine(
                date_to + timedelta(days=1), time.min, tzinfo=timezone.utc
            )
            return sent_at_to - _HISTORY_MAX_WINDOW, sent_at_to

        # 둘 다 지정. (date_from, date_to 모두 not None)
        assert date_from is not None and date_to is not None
        if date_from > date_to:
            raise InvalidHistoryDateRange()
        sent_at_from = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        sent_at_to = datetime.combine(
            date_to + timedelta(days=1), time.min, tzinfo=timezone.utc
        )
        if sent_at_to - sent_at_from > _HISTORY_MAX_WINDOW:
            raise InvalidHistoryDateRange()
        return sent_at_from, sent_at_to

    async def _get_owned(self, user_id: int, notification_id: int) -> Notification:
        notification = await self._repository.get_by_id(notification_id)
        if notification is None:
            raise NotificationNotFound()
        if notification.user_id != user_id:
            raise NotificationForbidden()
        return notification
