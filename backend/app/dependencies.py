# Shared FastAPI dependencies: API-key header check for the AI-service
# endpoints (/detections, /cameras/{id}/heartbeat), DB handles, etc.

from fastapi import Header, HTTPException, status

from app.config import get_settings


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    """Dependency for AI-service endpoints: validates the X-API-Key header."""
    if x_api_key != get_settings().api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")
