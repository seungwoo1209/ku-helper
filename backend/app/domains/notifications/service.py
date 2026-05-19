from app.domains.notifications.exceptions import (
    NotificationForbidden,
    NotificationNotFound,
)
from app.domains.notifications.models import Notification, NotificationType
from app.domains.notifications.repository import NotificationRepository
from app.domains.notifications.schemas import (
    LibraryUpdate,
    LunchUpdate,
    NotificationCreate,
    TransitUpdate,
)


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

    async def _get_owned(self, user_id: int, notification_id: int) -> Notification:
        notification = await self._repository.get_by_id(notification_id)
        if notification is None:
            raise NotificationNotFound()
        if notification.user_id != user_id:
            raise NotificationForbidden()
        return notification
