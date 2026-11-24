import sys

from common.memoryInfo import originContentMemoryInfo
from config.modelConfig import modelPool
from db.session import create_session
from judgeMent.bot.TalkContext import TalkContext
from repository.agentRepository import agentRepository
from repository.originContentRepository import originContentRepository
from repository.userRepository import userRepository
from service.modelService import modelService


async def save_dialog(messages:list[dict], context:TalkContext):
    memories=[]
    for message in messages:
        fields=await embed_content(message["content"], context.user_id)
        memories.append(originContentMemoryInfo(**fields, role=message["role"], session_id=context.session_id))
    async with create_session() as session:
        await originContentRepository(session).add_memory(memories, context.agent_id)


async def embed_content(content:str, user_id:str):
    async with create_session() as session:
        config=await userRepository(session).get_models(user_id)
    model=modelPool(**config.model_dump(exclude_none=True)).embedding
    embedding=await modelService.embedding(content, model)
    return dict(content=content, embedding=embedding, embedding_model=model.model_name)




async def delete_agent(agent_name:str, user_id:str):
    async with create_session() as session:
        await agentRepository(session).delete_agent(agent_name, user_id)


if __name__ == "__main__":
    import asyncio

    if sys.platform == "win32":
        asyncio.run(delete_agent("girlfriend1", "徐姝"),loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(delete_agent("girlfriend1", "徐姝"))
