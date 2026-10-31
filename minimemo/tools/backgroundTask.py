import asyncio
from loguru import logger

_bg_tasks: set[asyncio.Task] = set()

def _on_done(task: asyncio.Task):
    _bg_tasks.discard(task)
    if task.cancelled():
        return
    if exc := task.exception():
        logger.error(f"后台任务失败: {exc!r}", exc_info=exc)

def spawn(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_on_done)
    return task

async def drain_bg_tasks(timeout: float = 30):
    if _bg_tasks:
        await asyncio.wait(_bg_tasks, timeout=timeout)