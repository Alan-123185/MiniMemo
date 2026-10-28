from loguru import logger
from sqlalchemy.orm import Session

from  minimemo.models.agent import Agent


class agentRepository:
    def __init__(self , session : Session):
        self.session = session



    def register_agent(self,agent_id:str) -> None:
        # Check if the agent already exists
        existing_agent = self.session.query(Agent).filter_by(id=agent_id).first()
        if existing_agent:
            logger.info(f"Agent with id {agent_id} already exists. Skipping registration.")
            return

        # Create a new agent instance
        new_agent = Agent(id=agent_id)

        # Add the new agent to the session and commit
        self.session.add(new_agent)
        self.session.commit()


    def get_agents(self) -> list[Agent]:
        """
        获取所有被记忆接管的智能体列表
        """
        return self.session.query(Agent).all()
