import json
from pathlib import Path
from typing import List
from app.models import AOI

AOI_FILE = Path("data/aois.json")

def load_aois() -> List[AOI]:
    if not AOI_FILE.exists():
        return []
    data = json.loads(AOI_FILE.read_text(encoding="utf-8"))
    return [AOI(**x) for x in data]

def get_aoi(aoi_id: str) -> AOI | None:
    for aoi in load_aois():
        if aoi.id == aoi_id:
            return aoi
    return None

