from app.domains.users.models import User
from app.domains.users.repository import UserRepository


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def delete_account(self, user: User) -> None:
        # 현재는 status만 DELETED로 전환. 알림 설정·발송 이력 등 cascade 대상
        # 도메인이 추가되면 여기서 추가 정리를 호출한다.
        await self._repository.soft_delete(user)
