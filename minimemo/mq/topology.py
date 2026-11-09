import aio_pika

from minimemo.config.data import settings


"""
RabbitMQ 拓扑声明的唯一真源

一条消息的生命周期：
  publish → minimemo.exchange --(minimemo.episodic)--> 主队列
                                                          |
                                          消费失败 nack(requeue=False)
                                                          ↓
                                          minimemo.rx --(minimemo.episodic.retry)--> 重试队列
                                                          |
                                     TTL 到期经死信回源，重新投回主队列 → 再消费
                                                          |
                                              超过 MQ_MAX_RETRY 次
                                                          ↓
                                          consumer 显式转发到 minimemo_dlx --> 死信队列

注意主队列的 x-dead-letter-exchange 指向重试交换机而不是死信交换机：
nack 的去路是「先重试」，所以死信队列没有自动入口，
只能由 consumer 数够 x-death 次数后自己 publish 过去。
"""

EXCHANGE = "minimemo.exchange"
RETRY_EXCHANGE = "minimemo.rx"
DEAD_LETTER_EXCHANGE = "minimemo_dlx"

EPISODIC = "episodic"


def names(task: str) -> dict[str, str]:
    """
    一个任务组的队列名与路由键，加任务就在 EPISODIC 旁边加一个常量
    """
    return {
        "queue": f"minimemo.{task}.queue",
        "key": f"minimemo.{task}",
        "retry_queue": f"minimemo.{task}.retry",
        "retry_key": f"minimemo.{task}.retry",
        "dlq": f"minimemo.{task}.dlq",
        "dead_key": f"minimemo.{task}.failed",
    }


async def setup_topology(
    channel: aio_pika.abc.AbstractChannel,
) -> tuple[aio_pika.abc.AbstractExchange, aio_pika.abc.AbstractQueue]:
    """
    幂等声明全部交换机、队列与绑定，返回业务交换机与主队列
    声明是幂等的，worker 和 API 进程各自启动时都调一遍不会有副作用
    但队列参数必须与 broker 上已存在的一致，否则 RabbitMQ 会直接报 PRECONDITION_FAILED
    """
    #返回对应记忆的交换机和队列名   这里写死了 情景记忆 f:到时候要改
    n = names(EPISODIC)
    #声明主交换机  路由策略为 direct
    exchange = await channel.declare_exchange(
        EXCHANGE,
        aio_pika.ExchangeType.DIRECT,
        durable=True,
    )
    #声明重试交换机  路由策略为 direct
    retry_exchange = await channel.declare_exchange(
        RETRY_EXCHANGE,
        aio_pika.ExchangeType.DIRECT,
        durable=True,
    )
    #声明死信交换机  路由策略为 direct
    dead_letter_exchange = await channel.declare_exchange(
        DEAD_LETTER_EXCHANGE,
        aio_pika.ExchangeType.DIRECT,
        durable=True,
    )

    # 主队列：消费失败的消息经重试交换机进重试队列，不直接进死信
    queue = await channel.declare_queue(
        n["queue"],
        durable=True,
        arguments={
            "x-dead-letter-exchange": RETRY_EXCHANGE,
            "x-dead-letter-routing-key": n["retry_key"],
        },
    )
    await queue.bind(exchange, routing_key=n["key"])

    # 重试队列：只负责压住 TTL，到期后经死信回源，重新投回主队列
    retry_queue = await channel.declare_queue(
        n["retry_queue"],
        durable=True,
        arguments={
            "x-message-ttl": settings.MQ_RETRY_TTL_MS,
            "x-dead-letter-exchange": EXCHANGE,
            "x-dead-letter-routing-key": n["key"],
        },
    )
    await retry_queue.bind(retry_exchange, routing_key=n["retry_key"])

    # 死信队列：没有自动入口，靠 consumer 数够 x-death 次数后手动转发进来
    dead_letter_queue = await channel.declare_queue(n["dlq"], durable=True)
    await dead_letter_queue.bind(dead_letter_exchange, routing_key=n["dead_key"])

    return exchange, queue
