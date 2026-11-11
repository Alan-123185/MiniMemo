from typing import Sequence

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from  minimemo.models.agent import Agent
from minimemo.models.session import Session as SessionModel


class agentRepository:
    def __init__(self , session : AsyncSession):
        self.session = session



    async def register_agent(self,agent_id:str) -> None:
        # Check if the agent already exists
        existing_agent = (
            await self.session.execute(select(Agent).filter_by(id=agent_id))
        ).scalars().first()
        if existing_agent:
            logger.info(f"Agent with id {agent_id} already exists. Skipping registration.")
            return

        # Create a new agent instance
        new_agent = Agent(id=agent_id)

        # Add the new agent to the session and commit
        self.session.add(new_agent)
        # 注册智能体时顺带建一个 default 会话，与智能体同一个事务落库
        self.session.add(SessionModel(agent_id=agent_id, session_id="default"))
        await self.session.commit()



    async def get_agents(self) -> Sequence[Agent]:
        """
        获取所有被记忆接管的智能体列表
        """
        return (await self.session.execute(select(Agent))).scalars().all()
