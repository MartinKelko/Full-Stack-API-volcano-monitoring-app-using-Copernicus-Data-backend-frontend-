import os
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.services.aoi_repo import load_aois, get_aoi
from app.services.catalog import find_latest_s2_scene
from app.services.process import fetch_false_color_png
from app.services.storage import save_png

app = FastAPI(title="Copernicus Backend", version="0.5")

# -----------------------------------------------------------------------------
# Static: serve exactly settings.output_dir (save_png writes under this root)
# -----------------------------------------------------------------------------
OUTPUT_DIR = Path(settings.output_dir).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount(f"/{OUTPUT_DIR.name}", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def parse_datetime_utc(datetime_utc: str) -> datetime:
    try:
        dt = datetime.fromisoformat(datetime_utc.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Invalid datetime_utc. Use ISO format e.g. 2026-01-23T10:15:00Z",
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def to_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

# -----------------------------------------------------------------------------
# BASIC
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return {
        "name": "Copernicus Backend",
        "version": app.version,
        "health": "/health",
        "docs": "/docs",
        "output_url_prefix": f"/{OUTPUT_DIR.name}/",
        "batch": ["/latest-scenes", "/latest-fc-all"],
    }

@app.get("/health")
def health():
    return {"status": "ok"}

# -----------------------------------------------------------------------------
# DEBUG
# -----------------------------------------------------------------------------
@app.get("/debug/env")
def debug_env():
    return {
        "sh_base_url": settings.sh_base_url,
        "sh_token_url": settings.sh_token_url,
        "sh_client_id_present": bool(settings.sh_client_id),
        "sh_client_secret_present": bool(settings.sh_client_secret),
        "output_dir": str(OUTPUT_DIR),
    }

@app.get("/debug/upstream")
def debug_upstream():
    return {
        "catalog_search_url": f"{settings.sh_base_url}/api/v1/catalog/1.0.0/search",
        "process_url": f"{settings.sh_base_url}/api/v1/process",
    }

# -----------------------------------------------------------------------------
# AOI
# -----------------------------------------------------------------------------
@app.get("/aois")
def list_aois():
    aois = load_aois()
    return [a.model_dump() for a in aois]

@app.get("/aois/{aoi_id}")
def read_aoi(aoi_id: str):
    aoi = get_aoi(aoi_id)
    if not aoi:
        raise HTTPException(status_code=404, detail="AOI not found")
    return aoi.model_dump()

# -----------------------------------------------------------------------------
# LATEST S2 SCENE (single AOI)
# -----------------------------------------------------------------------------
@app.get("/aois/{aoi_id}/latest-scene")
async def latest_scene(
    aoi_id: str,
    days: int = Query(30, ge=1, le=365),
    cloud: float = Query(100.0, ge=0.0, le=100.0),
):
    aoi = get_aoi(aoi_id)
    if not aoi:
        raise HTTPException(status_code=404, detail="AOI not found")

    try:
        feature = await find_latest_s2_scene(aoi.bbox, days=days, max_cloud=cloud)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail={
                "where": "catalog.search",
                "upstream_status": e.response.status_code,
                "upstream_body": e.response.text[:1200],
            },
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail={"where": "catalog.search", "error": str(e)})

    if not feature:
        return {"aoi_id": aoi_id, "scene": None}

    props = feature.get("properties", {})
    return {
        "aoi_id": aoi_id,
        "datetime": props.get("datetime"),
        "cloud_cover": props.get("eo:cloud_cover"),
        "scene_id": feature.get("id"),
    }

# -----------------------------------------------------------------------------
# FALSE COLOR (manual) - PNG bytes
# -----------------------------------------------------------------------------
@app.get("/aois/{aoi_id}/fc.png")
async def fc_png(aoi_id: str, datetime_utc: str):
    aoi = get_aoi(aoi_id)
    if not aoi:
        raise HTTPException(status_code=404, detail="AOI not found")

    dt = parse_datetime_utc(datetime_utc)
    time_from = to_z(dt - timedelta(hours=1))
    time_to = to_z(dt + timedelta(hours=1))

    try:
        png = await fetch_false_color_png(
            bbox=aoi.bbox,
            time_from=time_from,
            time_to=time_to,
            width=1024,
            height=1024,
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail={
                "where": "process",
                "upstream_status": e.response.status_code,
                "upstream_body": e.response.text[:1200],
            },
        )

    return Response(content=png, media_type="image/png")

# -----------------------------------------------------------------------------
# FALSE COLOR SAVE (manual) - saves PNG and returns URL
# -----------------------------------------------------------------------------
@app.get("/aois/{aoi_id}/fc")
async def fc_save(aoi_id: str, datetime_utc: str):
    aoi = get_aoi(aoi_id)
    if not aoi:
        raise HTTPException(status_code=404, detail="AOI not found")

    dt = parse_datetime_utc(datetime_utc)
    time_from = to_z(dt - timedelta(hours=1))
    time_to = to_z(dt + timedelta(hours=1))

    png = await fetch_false_color_png(
        bbox=aoi.bbox,
        time_from=time_from,
        time_to=time_to,
        width=1024,
        height=1024,
    )

    file_path = save_png(aoi_id, dt.date().isoformat(), png).replace("\\", "/")
    return {"aoi_id": aoi_id, "datetime": to_z(dt), "file": file_path, "url": f"/{file_path}"}

# -----------------------------------------------------------------------------
# LATEST FALSE COLOR (AUTO, single AOI)
# -----------------------------------------------------------------------------
@app.get("/aois/{aoi_id}/latest-fc")
async def latest_fc(
    aoi_id: str,
    days: int = Query(30, ge=1, le=365),
    cloud: float = Query(100.0, ge=0.0, le=100.0),
):
    aoi = get_aoi(aoi_id)
    if not aoi:
        raise HTTPException(status_code=404, detail="AOI not found")

    try:
        feature = await find_latest_s2_scene(aoi.bbox, days=days, max_cloud=cloud)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail={"where": "catalog.search", "upstream_status": e.response.status_code, "upstream_body": e.response.text[:1200]},
        )

    if not feature:
        return {"aoi_id": aoi_id, "datetime": None, "file": None, "url": None}

    dt_str = feature.get("properties", {}).get("datetime")
    if not dt_str:
        return {"aoi_id": aoi_id, "datetime": None, "file": None, "url": None}

    dt = parse_datetime_utc(dt_str)
    time_from = to_z(dt - timedelta(hours=1))
    time_to = to_z(dt + timedelta(hours=1))

    try:
        png = await fetch_false_color_png(
            bbox=aoi.bbox,
            time_from=time_from,
            time_to=time_to,
            width=1024,
            height=1024,
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail={"where": "process", "upstream_status": e.response.status_code, "upstream_body": e.response.text[:1200]},
        )

    file_path = save_png(aoi_id, dt.date().isoformat(), png).replace("\\", "/")
    return {"aoi_id": aoi_id, "datetime": dt_str, "file": file_path, "url": f"/{file_path}"}

# -----------------------------------------------------------------------------
# BATCH: latest scenes for ALL AOIs
# -----------------------------------------------------------------------------
@app.get("/latest-scenes")
async def latest_scenes(
    days: int = Query(30, ge=1, le=365),
    cloud: float = Query(100.0, ge=0.0, le=100.0),
    concurrency: int = Query(4, ge=1, le=20),
):
    aois = load_aois()
    sem = asyncio.Semaphore(concurrency)

    async def one(a):
        async with sem:
            try:
                feature = await find_latest_s2_scene(a.bbox, days=days, max_cloud=cloud)
                if not feature:
                    return {"aoi_id": a.id, "name": a.name, "scene": None}

                props = feature.get("properties", {})
                return {
                    "aoi_id": a.id,
                    "name": a.name,
                    "scene": {
                        "datetime": props.get("datetime"),
                        "cloud_cover": props.get("eo:cloud_cover"),
                        "scene_id": feature.get("id"),
                    },
                }
            except httpx.HTTPStatusError as e:
                return {
                    "aoi_id": a.id,
                    "name": a.name,
                    "error": {"where": "catalog.search", "status": e.response.status_code, "body": e.response.text[:400]},
                }
            except Exception as e:
                return {"aoi_id": a.id, "name": a.name, "error": {"message": str(e)}}

    results = await asyncio.gather(*(one(a) for a in aois))
    return {"count": len(results), "results": results}

# -----------------------------------------------------------------------------
# BATCH: latest false color for ALL AOIs (find scene -> process -> save -> url)
# -----------------------------------------------------------------------------
@app.get("/latest-fc-all")
async def latest_fc_all(
    days: int = Query(30, ge=1, le=365),
    cloud: float = Query(100.0, ge=0.0, le=100.0),
    concurrency: int = Query(2, ge=1, le=10),  # process je ťažší, dávam nižšie default
):
    aois = load_aois()
    sem = asyncio.Semaphore(concurrency)

    async def one(a):
        async with sem:
            try:
                feature = await find_latest_s2_scene(a.bbox, days=days, max_cloud=cloud)
                if not feature:
                    return {"aoi_id": a.id, "name": a.name, "datetime": None, "file": None, "url": None}

                dt_str = (feature.get("properties", {}) or {}).get("datetime")
                if not dt_str:
                    return {"aoi_id": a.id, "name": a.name, "error": {"message": "scene missing datetime"}}

                dt = parse_datetime_utc(dt_str)
                time_from = to_z(dt - timedelta(hours=1))
                time_to = to_z(dt + timedelta(hours=1))

                png = await fetch_false_color_png(
                    bbox=a.bbox,
                    time_from=time_from,
                    time_to=time_to,
                    width=1024,
                    height=1024,
                )

                file_path = save_png(a.id, dt.date().isoformat(), png).replace("\\", "/")
                return {"aoi_id": a.id, "name": a.name, "datetime": dt_str, "file": file_path, "url": f"/{file_path}"}

            except httpx.HTTPStatusError as e:
                # môže byť z catalog alebo process; process chyby chytíš ako HTTPStatusError tiež
                return {
                    "aoi_id": a.id,
                    "name": a.name,
                    "error": {"status": e.response.status_code, "body": e.response.text[:400]},
                }
            except Exception as e:
                return {"aoi_id": a.id, "name": a.name, "error": {"message": str(e)}}

    results = await asyncio.gather(*(one(a) for a in aois))
    return {"count": len(results), "results": results}
