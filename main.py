from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from common.exceptions import BusinessException
from common.exceptionHandlers import (
    business_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
from db.Base import init_tables
from db.session import engine
from mq.publisher import get_publisher
from router.agentRouter import router as agent_router
from router.modelRouter import router as model_router
from router.memoryRouter import router as memory_router
from router.sessionRouter import router as session_router
from router.userRouter import router as user_router
import log


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code here
    await init_tables(engine)
    # 触发信号的生产者，连不上只告警不阻断：API 没了 MQ 也照样能写库
    await get_publisher().start()
    yield
    # Shutdown code here
    await get_publisher().close()

app = FastAPI(lifespan=lifespan)

app.add_exception_handler(BusinessException, business_exception_handler) # type: ignore
app.add_exception_handler(HTTPException, http_exception_handler) # type: ignore
app.add_exception_handler(RequestValidationError, validation_exception_handler) # type: ignore
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(model_router)
app.include_router(agent_router)
app.include_router(memory_router)
app.include_router(session_router)
app.include_router(user_router)

@app.get("/MiniMemo/hello")
async def hello():
    return {"message": "Hello, World!"}

if __name__ == "__main__":
    import sys
    import uvicorn

    # Windows 开发机上 psycopg async 需要 SelectorEventLoop；
    # Linux 生产环境默认就是 Selector，走 auto 即可。
    loop = "asyncio:SelectorEventLoop" if sys.platform == "win32" else "auto"

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=True,
        loop=loop,
    )
