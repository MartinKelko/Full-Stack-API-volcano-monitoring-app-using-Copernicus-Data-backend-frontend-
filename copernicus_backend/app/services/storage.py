from pathlib import Path
from app.config import settings

def save_png(aoi_id: str, date_str: str, png_bytes: bytes) -> str:
    out_dir = Path(settings.output_dir) / aoi_id
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{date_str}_false_color.png"
    out_path = out_dir / filename
    out_path.write_bytes(png_bytes)

    # vrátime relatívnu cestu (na URL)
    return str(out_path).replace("\\", "/")
