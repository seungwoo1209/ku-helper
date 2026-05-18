from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.models import User, UserStatus


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_discord_id(self, discord_id: int) -> User | None:
        stmt = select(User).where(User.discord_id == discord_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_by_discord_id(
        self, discord_id: int, discord_username: str
    ) -> tuple[User, bool]:
        existing = await self.get_by_discord_id(discord_id)
        if existing is not None:
            existing.discord_username = discord_username
            # 탈퇴 후 동일 Discord 계정으로 재로그인하면 ACTIVE로 복귀.
            if existing.status == UserStatus.DELETED:
                existing.status = UserStatus.ACTIVE
            await self._session.flush()
            return existing, False
        user = User(discord_id=discord_id, discord_username=discord_username)
        self._session.add(user)
        await self._session.flush()
        return user, True

    async def soft_delete(self, user: User) -> None:
        # get_current_user가 별도 세션에서 가져온 User 객체를 받는 경우가 있어
        # ORM 속성 대입 + flush로는 변경이 영속화되지 않는다. 명시 UPDATE로 처리.
        stmt = update(User).where(User.id == user.id).values(status=UserStatus.DELETED)
        await self._session.execute(stmt)
        await self._session.flush()
