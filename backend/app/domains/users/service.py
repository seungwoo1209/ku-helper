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
        # 소프트 삭제 + 알림 설정 cascade 정리. DB-level ON DELETE CASCADE는
        # 현재 사용자 자체가 보존되므로 발동하지 않는다.
        await self._notifications.delete_all_for_user(user.id)
        await self._repository.soft_delete(user)
