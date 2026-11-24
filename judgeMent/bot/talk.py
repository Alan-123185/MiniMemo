"""
简易智能伴侣，用来测试分层记忆。用户和伴侣的原话自动保存，
Agent 可以主动添加情景和语义记忆、搜索记忆，也可以按用户要求删除某条记忆。

在 PyCharm 里直接运行本文件，按提示输入已注册的用户名和 Agent 名称即可聊天。
"""
import asyncio
import sys
from pathlib import Path
from typing import Annotated
from langchain.agents import create_agent
from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from common.exceptions import NotFoundException
from common.memoryInfo import episodicMemoryInfo, semanticMemoryInfo
from common.requestSchema.searchRequest import searchRequest
from config.data import settings
from db.session import create_session, engine
from judgeMent.bot.Prompt import system_prompt
from judgeMent.bot.TalkContext import TalkContext
from models.memoryModel.memory import Memory
from repository.agentRepository import agentRepository
from repository.embeddingRepository import embeddingRepository
from repository.episodicMemoryRepository import episodicMemoryRepository
from repository.memoryRepository import memoryRepository
from repository.semanticMemoryRepository import semanticMemoryRepository
from repository.userRepository import userRepository
from service.searchService import searchService
from judgeMent.bot.utils import embed_content, save_dialog



@tool
async def add_episodic_memory(
    content: Annotated[str, "一件具体经历，写清楚谁经历了什么，只写对话中已知的细节"],
    runtime: ToolRuntime[TalkContext],
):
    """记下一件值得回忆的具体经历。"""
    fields=await embed_content(content, runtime.context.user_id)
    async with create_session() as session:
        await episodicMemoryRepository(session).add_memory([episodicMemoryInfo(**fields)], runtime.context.agent_id)
    return "已保存这段经历"


@tool
async def add_semantic_memory(
    content: Annotated[str, "一条已确认的事实或偏好，写完整，脱离对话也能读懂"],
    runtime: ToolRuntime[TalkContext],
):
    """记下一条以后聊天还用得上的事实或偏好。"""
    fields=await embed_content(content, runtime.context.user_id)
    async with create_session() as session:
        await semanticMemoryRepository(session).add_memory([semanticMemoryInfo(**fields)], runtime.context.agent_id)
    return "已保存这条事实或偏好"


@tool
async def search_memory(
    query: Annotated[str, "一句完整的陈述句表明你要查询的东西，例如「上次说的出差地点」"],
    runtime: ToolRuntime[TalkContext],
):
    """回忆以前聊过的事，返回匹配的记忆及其 memory_id。"""
    context=runtime.context
    request=searchRequest(query=query, user_id=context.user_id, agent_id=context.agent_id)
    async with create_session() as session:
        repo=memoryRepository(session)
        service=searchService(embeddingRepository(session), repo, userRepository(session))
        # 搜索接口的最终结果省略了 id，这里保留精排后的原对象，删除时用得上
        ids=await service.pre_ranking(request)
        # 原文不参与回忆：库里的原文都已经归档成情景和语义记忆，信息不缺；
        # 而原文里混着助手自己的回复，召回后会被当成「我记得的事」复述出来
        memories=[m for m in await repo.search_memory(ids) if m.memory_type!="origin"]
        ranked=await service.fine_ranking(request, memories)
        return [
            {"memory_id":m.id, "memory_type":m.memory_type, "content":m.content, "update_time":m.update_time.isoformat()}
            for m in ranked[:request.return_count]
        ]


@tool
async def delete_memory(
    memory_id: Annotated[str, "要删除的记忆 id，取自 search_memory 返回结果里的 memory_id"],
    runtime: ToolRuntime[TalkContext],
):
    """用户明确要求忘记某条记忆时删除它。"""
    agent_id=runtime.context.agent_id
    async with create_session() as session:
        memory=await session.get(Memory, memory_id)
        if memory is None or memory.agent_id!=agent_id or memory.is_delete:
            return "没有找到这条记忆"
        repo=semanticMemoryRepository(session) if memory.memory_type=="semantic" else memoryRepository(session)
        await repo.kill_memory(memory_id, agent_id=agent_id)
        await repo.commit()
    return "已删除这条记忆"


def build_agent(saver:AsyncSqliteSaver):
    return create_agent(
        model=ChatOpenAI(
            api_key=settings.DEFAULT_API_KEY,
            model=settings.DEFAULT_MODEL,
            base_url=settings.DEFAULT_BASE_URL,
        ),
        tools=[add_episodic_memory, add_semantic_memory, search_memory, delete_memory],
        checkpointer=saver,
        context_schema=TalkContext,
        system_prompt=system_prompt
    )




async def talk(user_id:str, agent_name:str, session_id:str="default"):
    async with create_session() as session:
        try:
            companion=await agentRepository(session).get_agent(agent_name, user_id)
            agent_id = companion.id
        except NotFoundException as exc:
            agent_id = await agentRepository(session).register_agent(agent_name, user_id)
        context=TalkContext(user_id, agent_id, session_id)

    config={"configurable":{"thread_id":f"{context.agent_id}:{session_id}"}}
    db_path=Path(__file__).with_name("talk.sqlite3")
    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
        agent=build_agent(saver)
        print(f"正在和 {agent_name} 聊天，输入 /exit 退出")
        while True:
            content=input("你：").strip()
            if content=="/exit":
                break
            if not content:
                continue

            messages=[{"role":"user", "content":content}]
            try:
                result=await agent.ainvoke({"messages":messages}, config=config, context=context)
                reply=result["messages"][-1].text
                print(f"{agent_name}：{reply}")
                messages.append({"role":"assistant", "content":reply})
            except Exception as exc:
                print(f"本轮对话失败：{exc}")
            # 聊完再一起存原话，避免搜索往事时召回用户刚问的这句话
            try:
                await save_dialog(messages, context)
            except Exception as exc:
                print(f"本轮原文保存出错：{exc}")


if __name__=="__main__":
    # Windows 下 psycopg 的异步连接需要 SelectorEventLoop
    loop=asyncio.SelectorEventLoop if sys.platform=="win32" else None
    with asyncio.Runner(loop_factory=loop) as runner:
        try:
            runner.run(talk(user_id="徐姝", agent_name="girlfriend1", session_id="default"))
        except (KeyboardInterrupt, EOFError):
            pass
        except NotFoundException as exc:
            print(f"{exc}\n")
        finally:
            runner.run(engine.dispose())