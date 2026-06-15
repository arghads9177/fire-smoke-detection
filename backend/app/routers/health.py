# GET /health — liveness check (plan §3.3 REST API table).
# GET /system/info — server LAN IP, used by the dashboard to build the
# phone RTMP publish URL (PHONE_CAMERA_MEDIAMTX_PLAN.md step 5).

import socket

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


def get_lan_ip() -> str:
    """Best-effort LAN IP of this host (the address phones on the same
    Wi-Fi should use), without requiring any outbound connectivity."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


@router.get("/system/info")
async def system_info() -> dict:
    return {"lanIp": get_lan_ip()}
