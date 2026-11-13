import asyncio
import sys
import aio_pika
import log  # noqa: F401  引入即完成日志配置，worker 的日志要落到和 API 同一个 logs 目录
from loguru import logger
from config.data import settings
from config.modelConfig import set_pool
from db.session import create_session
from mq.consumer import on_episodic_message, on_semantic_message
from mq.publisher import get_publisher
from mq.topology import EPISODIC, SEMANTIC, names, setup_topology
from mq.watermark import get_ready_memory
from repository.agentRepository import agentRepository
from tools.backgroundTask import spawn


"""
记忆抽取的独立进程入口

API 只负责落库和发触发信号，真正的抽取在这里跑：
LLM 调用动辄数秒，放在 API 进程里会拖住事件循环。

除了消费队列，这里还跑一个兜底扫描器：写入触发是即时的，
但消息可能因为 MQ 短暂不可用而没发出去，而且「会话超过一段时间没新内容」
这种时间水位根本没有对应的写入事件，只能靠定期扫一遍来找。

    python worker.py
"""


async def run_scanner(stop: asyncio.Event):
    """
    定期扫描情景和语义水位，分别给会话和 agent 补发触发消息

    只发消息不抽取，抽取永远发生在 consumer 侧，
    所以这里和写入触发发出来的消息是完全等价的，重复也无害。
    """
    publisher = get_publisher()
    while not stop.is_set():
        try:
            session = create_session()
            try:
                agents = await agentRepository(session).get_agents()
            finally:
                await session.close()
            for agent in agents:
                for session_id in await get_ready_memory(agent.id,mode="episodic"):
                    logger.info(f"扫描器补发情景触发消息 agent_id={agent.id} session_id={session_id}")
                    await publisher.publish_episodic_trigger(agent.id, session_id, source="scanner")
        except Exception as e:
            logger.warning(f"情景记忆兜底扫描出错，下一轮再试: {e!r}")
        try:
            # 语义水位按 agent 聚合，一轮只需统计一次，不放进上面的 agent 循环。
            for agent_id in await get_ready_memory(mode="semantic"):
                logger.info(f"扫描器补发语义触发消息 agent_id={agent_id}")
                await publisher.publish_semantic_trigger(agent_id, source="scanner")
        except Exception as e:
            logger.warning(f"语义记忆兜底扫描出错，下一轮再试: {e!r}")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.MQ_SCAN_INTERVAL)
        except asyncio.TimeoutError:
            pass


async def main():
    # 抽取要用大模型，模型池必须先就位，否则 get_pool() 会直接抛 RuntimeError
    set_pool()

    connection = await aio_pika.connect_robust(
        host=settings.MQ_HOST,
        port=settings.MQ_PORT,
        virtualhost=settings.MQ_VHOST,
        login=settings.MQ_USER,
        password=settings.MQ_PASSWORD,
    )
    try:
        channel = await connection.channel()
        _, queues = await setup_topology(channel)
        # 行锁分别保证会话级和 agent 级互斥，prefetch 限制每个消费者的在途消息数。
        await channel.set_qos(prefetch_count=settings.MQ_PREFETCH)
        #创建一个连接
        await get_publisher().start()
        stop = asyncio.Event()
        scanner = spawn(run_scanner(stop))

        await queues[EPISODIC].consume(on_episodic_message, no_ack=False)
        await queues[SEMANTIC].consume(on_semantic_message, no_ack=False)
        logger.info(
            f"worker 就绪，监听 {names(EPISODIC)['queue']} 和 {names(SEMANTIC)['queue']}，"
            f"扫描间隔 {settings.MQ_SCAN_INTERVAL}s"
        )

        try:
            await stop.wait()
        finally:
            stop.set()
            scanner.cancel()
            await get_publisher().close()
    finally:
        await connection.close()

  
if __name__ == "__main__":
    import sys
    import asyncio

    if sys.platform == "win32":
        asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(main())
