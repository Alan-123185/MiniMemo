from typing import Sequence

from fastapi import HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions import NotFoundException
from  models.agent import Agent
from models.session import Session as SessionModel


class agentRepository:
    def __init__(self , session : AsyncSession):
        self.session = session



    async def register_agent(self, agent_name: str, user_id: str) -> None:
        existing_agent = await self.get_agent(agent_name, user_id)
        if existing_agent:
            logger.info(f"Agent already exists for user_id={user_id}, agent_name={agent_name}. Skipping registration.")
            return

        # Create a new agent instance
        new_agent = Agent(agent_name=agent_name, user_id=user_id)

        # Add the new agent to the session and commit
        self.session.add(new_agent)
        await self.session.flush()
        # 注册智能体时顺带建一个 default 会话，与智能体同一个事务落库
        self.session.add(SessionModel(agent_id=new_agent.id, session_id="default"))
        await self.session.commit()



    async def get_agent(self, agent_name: str, user_id: str) -> Agent | None:
        """按所属用户与对外名称查找 Agent。"""
        return (
            await self.session.execute(
                select(Agent).filter_by(user_id=user_id, agent_name=agent_name)
            )
        ).scalars().first()



    async def get_agents(self, user_id: str | None = None) -> Sequence[Agent]:
        """
        指定用户时只获取其 Agent；不传用户供后台扫描全部 Agent。
        """         
        query = select(Agent)
        if user_id is not None:
            query = query.where(Agent.user_id == user_id)
        return (await self.session.execute(query)).scalars().all()


    async def resolve_agent_id(self, user_id: str, agent_name: str) -> str:
        """将用户下的对外 Agent 名称解析为业务内部使用的主键。"""
        agent = await self.get_agent(agent_name, user_id)
        if agent is None:
            raise NotFoundException(f"Agent not found for user_id={user_id}, agent_name={agent_name}")
        return agent.id

