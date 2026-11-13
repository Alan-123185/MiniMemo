from fastapi import HTTPException

from repository.agentRepository import agentRepository


async def resolve_agent_id(user_id: str, agent_name: str, agent_rep: agentRepository) -> str:
    """将用户下的对外 Agent 名称解析为业务内部使用的主键。"""
    agent = await agent_rep.get_agent(agent_name, user_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="该用户下不存在此 Agent")
    return agent.id


