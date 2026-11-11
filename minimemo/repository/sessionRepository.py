from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from minimemo.models.session import Session as SessionModel


class sessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session


    async def register_session(self, agent_id: str, session_id: str) -> None:
        """
        把一个会话注册到指定智能体下，会话id由调用方传入
        """
        existing_session = (
            await self.session.execute(
                select(SessionModel).filter_by(agent_id=agent_id, session_id=session_id)
            )
        ).scalars().first()
        if existing_session:
            logger.info(f"Session with session_id {session_id} already exists. Skipping registration.")
            return

        self.session.add(SessionModel(agent_id=agent_id, session_id=session_id))
        await self.session.commit()
