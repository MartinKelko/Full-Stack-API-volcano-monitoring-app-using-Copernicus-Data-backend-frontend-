import httpx

from app.config import settings
from app.services.token import get_access_token

FALSE_COLOR_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: ["B12", "B11", "B04"],
    output: { bands: 3, sampleType: "AUTO" }
  };
}
function evaluatePixel(sample) {
  // False color: B12->R, B11->G, B04->B
  return [sample.B12, sample.B11, sample.B04];
}
"""

async def fetch_false_color_png(
    bbox: list[float],
    time_from: str,
    time_to: str,
    width: int = 1024,
    height: int = 1024
) -> bytes:
    """
    Zavolá Sentinel Hub Process API a vráti PNG bytes.
    bbox: [minLon, minLat, maxLon, maxLat] v EPSG:4326
    time_from/time_to: ISO string s 'Z' (napr. 2026-01-20T10:00:00Z)
    """
    token = await get_access_token()
    url = f"{settings.sh_base_url}/api/v1/process"

    payload = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {"timeRange": {"from": time_from, "to": time_to}}
                }
            ]
        },
        "output": {
            "width": width,
            "height": height,
            "responses": [{"identifier": "default", "format": {"type": "image/png"}}]
        },
        "evalscript": FALSE_COLOR_EVALSCRIPT
    }

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.content
