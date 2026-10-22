from contextlib import asynccontextmanager
from fastapi import FastAPI
from db.Base import Base
from db.session import engine
from router.agentRouter import router as agent_router
from router.modelRouter import router as model_router
from router.memoryRouter import router as memory_router

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

