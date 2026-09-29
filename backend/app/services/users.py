from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def get_or_create(
    session: AsyncSession, telegram_id: int, username: str | None, first_name: str | None
) -> User:
    stmt = (
        insert(User)
        .values(telegram_id=telegram_id, username=username, first_name=first_name)
        .on_conflict_do_update(
            index_elements=[User.telegram_id],
            set_={"username": username, "first_name": first_name},
        )
        .returning(User)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()
