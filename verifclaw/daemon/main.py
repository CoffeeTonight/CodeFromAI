import asyncio
import logging
from datetime import datetime
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager

from core.graph import verifclaw_graph

# ==================== Logging 설정 ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("verifclaw")

# ==================== FastAPI Lifespan (on_event deprecation 해결) ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    scheduler.add_job(heartbeat, "interval", minutes=5)
    logger.info("VerifClaw daemon started - Heartbeat every 5 minutes")
    yield
    scheduler.shutdown()
    logger.info("VerifClaw daemon shutdown")

app = FastAPI(title="VerifClaw - Persistent Verification Agent", lifespan=lifespan)
scheduler = AsyncIOScheduler()

# ==================== Heartbeat (5분마다 실행) ====================
async def heartbeat():
    logger.info("HEARTBEAT - Checking regression farm...")
    state = {"task": "poll_regression"}
    await verifclaw_graph.ainvoke(
        state,
        config={"configurable": {"thread_id": "verifclaw-main"}}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)