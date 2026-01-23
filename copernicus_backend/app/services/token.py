import time
import httpx

from app.config import settings

_token_cache = {
    "access_token": None,
    "expires_at": 0.0,
}

async def get_access_token() -> str:
    now = time.time()

    # použij cache, ak ešte neexpiroval
    if _token_cache["access_token"] and (_token_cache["expires_at"] - now) > 60:
        return _token_cache["access_token"]

    data = {
        "client_id": settings.sh_client_id,
        "client_secret": settings.sh_client_secret,
        "grant_type": "client_credentials",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(settings.sh_token_url, data=data)
        r.raise_for_status()
        payload = r.json()

    _token_cache["access_token"] = payload["access_token"]
    _token_cache["expires_at"] = now + float(payload.get("expires_in", 3600))

    return _token_cache["access_token"]
