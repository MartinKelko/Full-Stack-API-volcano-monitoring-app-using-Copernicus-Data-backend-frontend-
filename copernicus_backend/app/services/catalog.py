# app/services/catalog.py
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

import httpx

from app.config import settings
from app.services.token import get_access_token


def _parse_dt(dt_str: str) -> datetime:
    # dt_str býva napr. "2026-01-20T10:15:00Z"
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(timezone.utc)


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


async def _post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    json: dict,
    headers: dict,
    tries: int = 4,
) -> httpx.Response:
    for i in range(tries):
        r = await client.post(url, json=json, headers=headers)
        if r.status_code in (502, 503, 504) and i < tries - 1:
            await asyncio.sleep(1.5 * (i + 1))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r


async def find_latest_s2_scene(
    bbox: List[float],
    days: int = 3,
    max_cloud: float = 100.0,
) -> Optional[Dict[str, Any]]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now - timedelta(days=days)
    datetime_range = f"{_iso_z(start)}/{_iso_z(now)}"

    # ✅ CDSE Catalog endpoint
    url = f"{settings.sh_base_url}/api/v1/catalog/1.0.0/search"

    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    # ✅ CDSE používa `filter` ako string (CQL2 text) v príkladoch
    # Cloud cover filter:
    cloud_filter = f"eo:cloud_cover <= {max_cloud}"

    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": bbox,
        "datetime": datetime_range,
        "limit": 50,              # vyberieme latest u nás
        "filter": cloud_filter,   # string filter
        # voliteľné: skráti response (menej dát = menej šancí na timeout)
        "fields": {"include": ["id", "properties.datetime", "properties.eo:cloud_cover"]},
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await _post_with_retry(client, url, json=payload, headers=headers, tries=4)
        data = r.json()
        features = data.get("features") or []
        if not features:
            return None

        # vyber newest podľa properties.datetime
        def key_fn(f: Dict[str, Any]) -> datetime:
            dt_str = (f.get("properties") or {}).get("datetime") or "1970-01-01T00:00:00Z"
            return _parse_dt(dt_str)

        return max(features, key=key_fn)
