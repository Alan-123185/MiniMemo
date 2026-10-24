from sqlalchemy.orm import Session

from  minimemo.models.agent import Agent


class agentRepository:
    def __init__(self , session : Session):
        self.session = session



    async def register_agent(self,agent:Agent) -> None:
        # Check if the agent already exists
        existing_agent = self.session.query(Agent).filter_by(id=agent.id).first()
        if existing_agent:
            raise ValueError(f"Agent with ID {agent.id} already exists.")

        # Create a new agent instance
        new_agent = Agent(id=agent.id)

        # Add the new agent to the session and commit
        self.session.add(new_agent)
        self.session.commit()


    async def get_agents(self):
        """
        获取所有被记忆接管的智能体列表
        """
        return self.session.query(Agent).all()

