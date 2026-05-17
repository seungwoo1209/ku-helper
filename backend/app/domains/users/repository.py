from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.models import User


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
            await self._session.flush()
            return existing, False
        user = User(discord_id=discord_id, discord_username=discord_username)
        self._session.add(user)
        await self._session.flush()
        return user, True
