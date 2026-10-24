from contextlib import asynccontextmanager
from fastapi import FastAPI
from minimemo.db.Base import Base
from minimemo.db.session import engine
from minimemo.router.agentRouter import router as agent_router
from minimemo.router.modelRouter import router as model_router
from minimemo.router.memoryRouter import router as memory_router

app = FastAPI()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code here
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown code here

app = FastAPI(lifespan=lifespan)

app.include_router(model_router)
app.include_router(agent_router)
app.include_router(memory_router)

@app.get("/MiniMemo/hello")
async def hello():
    return {"message": "Hello, World!"}

