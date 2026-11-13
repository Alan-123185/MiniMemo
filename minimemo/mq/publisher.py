import asyncio
import json
import aio_pika
from loguru import logger
from minimemo.config.data import settings
from minimemo.mq import topology
from minimemo.mq.topology import EPISODIC, SEMANTIC, names


"""
触发信号的生产者

只发「哪个 agent 的哪个会话该看一眼了」，消息体里不带原文与向量：
数据库才是唯一真相源，consumer 收到后回库自己捞，
这样重投递天然安全，原文后续被改动也不会用到消息里的旧数据。

发布失败一律只告警不抛出：写入接口的成功与否由数据库落库决定，
消息丢了顶多让抽取晚一点，还有兜底扫描器负责补发。
"""


class eventPublisher:
    def __init__(self):
        self._connection: aio_pika.abc.AbstractConnection | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None
        self._reconnect_task: asyncio.Task | None = None

    async def start(self):
        """
        建立长连接并声明拓扑
        连不上不能让调用方起不来（API 没了 MQ 也该能写库），只转后台重连
        """
        self._reconnect_task = asyncio.create_task(self._connect_forever())

    async def _connect_forever(self):
        while True:
            try:
                self._connection = await aio_pika.connect_robust(
                    host=settings.MQ_HOST,
                    port=settings.MQ_PORT,
                    virtualhost=settings.MQ_VHOST,
                    login=settings.MQ_USER,
                    password=settings.MQ_PASSWORD,
                )
                channel = await self._connection.channel(publisher_confirms=True)
                self._exchange, _ = await topology.setup_topology(channel)
                logger.info(f"MQ 生产者已连接 {settings.MQ_HOST}:{settings.MQ_PORT}")
                return
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"MQ 连接失败，30 秒后重试，期间触发消息依赖扫描器兜底: {e}")
                self._connection = None
                self._exchange = None
                await asyncio.sleep(30)

    async def close(self):
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()
        self._connection = None
        self._exchange = None

    async def publish_episodic_trigger(self, agent_id: str, session_id: str, source: str = "api"):
        """
        发一条情景抽取的触发信号
        source 只用于排障，区分这条消息是写入时发的还是扫描器补发的
        """
        await self._publish_trigger(EPISODIC, {"agent_id": agent_id, "session_id": session_id}, source)

    async def publish_semantic_trigger(self, agent_id: str, source: str = "scanner"):
        """发一条跨会话的语义提炼触发信号，互斥和水位粒度均为 agent。"""
        await self._publish_trigger(SEMANTIC, {"agent_id": agent_id}, source)

    async def _publish_trigger(self, task: str, payload: dict[str, str], source: str):
        if self._exchange is None:
            logger.warning(f"MQ 未连接，触发消息未发出，等待扫描器补发 task={task} payload={payload}")
            return
        message = aio_pika.Message(
            body=json.dumps(payload).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers={"source": source},
        )
        try:
            await self._exchange.publish(message, routing_key=names(task)["key"])
        except Exception as e:
            logger.warning(f"MQ 发布失败，不影响写入，等待扫描器补发: {e}")


_publisher: eventPublisher | None = None


def get_publisher() -> eventPublisher:
    """
    进程内单例，跟随 config/modelConfig.py 里模型池的写法
    生命周期由宿主管理：API 在 lifespan 里 start/close，worker 由 main 管理
    """
    global _publisher
    if _publisher is None:
        _publisher = eventPublisher()
    return _publisher
