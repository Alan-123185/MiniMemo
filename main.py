import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from minimemo.db.Base import init_tables
from minimemo.db.session import engine
from minimemo.mq.publisher import get_publisher
from minimemo.router.agentRouter import router as agent_router
from minimemo.router.modelRouter import router as model_router
from minimemo.router.memoryRouter import router as memory_router
from minimemo.router.sessionRouter import router as session_router
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

app.include_router(model_router)
app.include_router(agent_router)
app.include_router(memory_router)
app.include_router(session_router)

@app.get("/MiniMemo/hello")
async def hello():
    return {"message": "Hello, World!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, log_level="info",reload=True)
    