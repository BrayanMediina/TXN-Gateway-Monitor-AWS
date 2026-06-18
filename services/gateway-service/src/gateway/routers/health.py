from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check del servicio")
async def health_check() -> dict:
    return {
        "status": "healthy",
        "service": "gateway-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
