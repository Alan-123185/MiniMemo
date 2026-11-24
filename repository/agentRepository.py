from typing import Sequence
from loguru import logger
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from common.exceptions import NotFoundException
from models.agent import Agent
from models.episodeOriginLink import episodeOriginLink
from models.memoryModel.episodicMemory import episodicMemory
from models.memoryModel.memory import Memory
from models.memoryModel.origin_content import originContent
from models.memoryModel.semanticMemory import semanticMemory
from models.memoryVector import memoryVector
from models.session import Session as SessionModel


class agentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def register_agent(self, agent_name: str, user_id: str) -> str|None:
        existing_agent = (
            await self.session.execute(
                select(Agent).filter_by(user_id=user_id, agent_name=agent_name)
            )
        ).scalars().first()
        if existing_agent:
            logger.info(
                f"Agent already exists for user_id={user_id}, agent_name={agent_name}. Skipping registration."
            )
            return None  # Return the existing agent's ID instead of None

        new_agent = Agent(agent_name=agent_name, user_id=user_id)

        self.session.add(new_agent)
        await self.session.flush()
        self.session.add(SessionModel(agent_id=new_agent.id, session_id="default"))
        await self.session.commit()
        return new_agent.id


    async def get_agent(self, agent_name: str, user_id: str) -> Agent | None:
        """按所属用户与对外名称查找 Agent。"""
        agent = (
            await self.session.execute(
                select(Agent).filter_by(user_id=user_id, agent_name=agent_name)
            )
        ).scalars().first()
        if not agent:
            raise NotFoundException(
                f"Agent not found for user_id={user_id}, agent_name={agent_name}"
            )
        return agent

    async def get_agents(self, user_id: str | None = None) -> Sequence[Agent]:
        """
        指定用户时只获取其 Agent；不传用户供后台扫描全部 Agent。
        """
        query = select(Agent)
        if user_id is not None:
            query = query.where(Agent.user_id == user_id)
        return (await self.session.execute(query)).scalars().all()

    #删除这个智能体和相关的所有记忆
    async def delete_agent(self, agent_name: str, user_id: str) -> None:
        """物理删除 Agent，以及它名下的会话、记忆和向量。"""
        agent = await self.get_agent(agent_name, user_id)
        memory_ids = (
            await self.session.execute(
                select(Memory.id).where(Memory.agent_id == agent.id)
            )
        ).scalars().all()

        if memory_ids:
            await self.session.execute(
                delete(episodeOriginLink).where(
                    or_(
                        episodeOriginLink.episode_id.in_(memory_ids),
                        episodeOriginLink.origin_content_id.in_(memory_ids),
                    )
                )
            )
            await self.session.execute(
                delete(memoryVector).where(
                    memoryVector.agent_id == agent.id
                )
            )
            await self.session.execute(
                delete(originContent).where(originContent.id.in_(memory_ids))
            )
            await self.session.execute(
                delete(episodicMemory).where(episodicMemory.id.in_(memory_ids))
            )
            await self.session.execute(
                delete(semanticMemory).where(semanticMemory.id.in_(memory_ids))
            )
            await self.session.execute(
                delete(Memory).where(Memory.agent_id == agent.id)
            )
        await self.session.execute(
            delete(SessionModel).where(SessionModel.agent_id == agent.id)
        )
        await self.session.delete(agent)
        await self.session.commit()