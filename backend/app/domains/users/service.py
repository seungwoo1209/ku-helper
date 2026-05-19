from app.domains.notifications.repository import NotificationRepository
from app.domains.users.models import User
from app.domains.users.repository import UserRepository


class UserService:
    def __init__(
        self,
        repository: UserRepository,
        notification_repository: NotificationRepository,
    ) -> None:
        self._repository = repository
        self._notifications = notification_repository

    async def delete_account(self, user: User) -> None:
        # 소프트 삭제 + 알림 도메인 cascade 정리. DB-level ON DELETE CASCADE는
        # 현재 사용자 자체가 보존되므로 발동하지 않는다. notification_history는
        # notification_id가 ON DELETE SET NULL이라 notifications만 지우면 row가
        # 잔존하므로 별도로 지운다 (개인정보 최소화: history도 물리 삭제).
        await self._notifications.delete_history_for_user(user.id)
        await self._notifications.delete_all_for_user(user.id)
        await self._repository.soft_delete(user)
