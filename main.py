import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import close_db, connect_db
from app.routers import vapi_tools, vapi_webhooks

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="ExpertlyAI Coach",
    description="Accountability coaching backend with VAPI integration",
    lifespan=lifespan,
)

app.include_router(vapi_tools.router)
app.include_router(vapi_webhooks.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
