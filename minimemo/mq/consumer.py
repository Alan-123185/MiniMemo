import json
import aio_pika
from loguru import logger
from minimemo.config.data import settings
from minimemo.mq.topology import DEAD_LETTER_EXCHANGE, EPISODIC, names
from minimemo.mq.watermark import get_ready_memory
from minimemo.service.consolidationService import consolidationService


"""
情景抽取的消费者

消息里只有会话标识，真正的判断与取数都回库做，所以重复投递是安全的：
水位不达标就丢，达标了在锁内重新捞一遍未归档原文，
上一轮已经归档的话这一轮捞到空集，自然跳过。
"""


def _retry_count(message: aio_pika.IncomingMessage) -> int:
    """
    读 x-death 里累积的死亡次数，0 表示首次投递
    RabbitMQ 把死亡记录按 (队列, 原因) 聚合，同一队列重试多次只累加 count
    """
    deaths = (message.headers or {}).get("x-death") or []
    queue_name = names(EPISODIC)["queue"]
    return max((int(d.get("count", 0)) for d in deaths if d.get("queue") == queue_name), default=0)


async def _forward_to_dlq(message: aio_pika.IncomingMessage):
    """
    超限的消息只能手动转发进死信队列
    主队列的死信交换机指向的是重试交换机，再用 nack 只会无限循环
    """
    exchange = await message.channel.declare_exchange(
        DEAD_LETTER_EXCHANGE,
        aio_pika.ExchangeType.DIRECT,
        durable=True,
    )
    body = message.body
    forwarded = aio_pika.Message(
        body=body,
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        content_type=message.content_type,
        headers=dict(message.headers or {}),
    )
    await exchange.publish(forwarded, routing_key=names(EPISODIC)["dead_key"])


async def on_episodic_message(message: aio_pika.IncomingMessage):
    """
    一条触发信号的处理流程：超限判定 → 水位判定 → 抽取 → 确认
    抽取成功才 ack，中途进程挂掉消息会被重投，重投走的还是这条路径
    """
    if _retry_count(message) >= settings.MQ_MAX_RETRY:
        logger.error(f"消息重试已达上限，转发进死信队列: {message.body!r}")
        await _forward_to_dlq(message)
        await message.ack()
        return

    payload = json.loads(message.body)
    agent_id = payload["agent_id"]
    session_id = payload["session_id"]

    try:
        ready = await get_ready_memory(agent_id,mode="episodic")
        if session_id not in ready:
            logger.info(f"会话未达水位，丢弃触发消息 agent_id={agent_id} session_id={session_id}")
            await message.ack()
            return
        await consolidationService.consolidate_episodics(agent_id, session_id)
        await message.ack()
    except Exception as e:
        logger.error(f"情景记忆抽取失败，稍后重试 agent_id={agent_id} session_id={session_id}: {e!r}")
        # requeue=False 让消息走死信，进重试队列压 TTL，到期再回主队列
        await message.nack(requeue=False)
