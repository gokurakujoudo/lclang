"""ASGI fixture records startup, request, background work, and shutdown."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI

from lclang.logger import use_logger


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Exercise factory admission during both lifespan phases."""
    logger = await use_logger(name=__name__)
    logger.info("service-startup")
    yield
    logger.info("service-shutdown")


app = FastAPI(lifespan=lifespan)


async def background() -> None:
    """Exercise factory lookup in a server-owned request task."""
    logger = await use_logger(name=__name__)
    logger.info("service-background")


@app.get("/")
async def endpoint(tasks: BackgroundTasks) -> dict[str, bool]:
    """Serve a deterministic local response and schedule background logging."""
    logger = await use_logger(name=__name__)
    logger.info("service-request")
    tasks.add_task(background)
    return {"ok": True}
