from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from gateway.config import get_settings
from gateway.middleware.logging import setup_logging
from gateway.routers import events, health, metrics

logger = structlog.get_logger(__name__)
settings = get_settings()

setup_logging(log_level=settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("gateway_service_starting", env=settings.app_env)
    yield
    logger.info("gateway_service_shutting_down")


app = FastAPI(
    title="TXN Gateway Monitor",
    description="Gateway de mensajería para procesamiento transaccional automatizado",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://d3q5sjqh5x3d32.cloudfront.net",
        "http://localhost:3000",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(events.router)
app.include_router(health.router)
app.include_router(metrics.router)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor"},
    )


if __name__ == "__main__":
    uvicorn.run("gateway.main:app", host="0.0.0.0", port=8000, reload=True)
