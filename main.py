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


@app.post("/admin/set-person-name")
async def set_person_name(
    agentId: str,
    personKey: str,
    personName: str,
):
    """Set or update a person's name in the database."""
    from app.database import get_db
    from datetime import datetime, timezone

    db = get_db()
    now = datetime.now(timezone.utc)
    result = await db["agentMemoryRecords"].insert_one(
        {
            "agentId": agentId,
            "personKeyType": "phone",
            "personKey": personKey,
            "personName": personName,
            "personId": None,
            "topicId": "_identity",
            "topicName": "_identity",
            "coachingTemplateCode": None,
            "recordKind": "data",
            "conversationId": None,
            "sequence": None,
            "text": f"Person identity record for {personName}.",
            "data": {"name": personName, "phone": personKey},
            "createdAt": now,
            "updatedAt": now,
        }
    )
    return {"success": True, "recordId": str(result.inserted_id)}
