from typing import Optional, Any
from pydantic import BaseModel, Field, model_validator

class AOI(BaseModel):
    id: str
    name: str
    bbox: Optional[list[float]] = None
    geometry: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def ensure_bbox(self):
        # Ak bbox chýba, ale máme geometry Polygon -> vypočítaj bbox
        if (self.bbox is None) and self.geometry:
            if self.geometry.get("type") != "Polygon":
                raise ValueError("geometry.type must be 'Polygon'")
            coords = self.geometry["coordinates"][0]
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            self.bbox = [min(lons), min(lats), max(lons), max(lats)]

        # Na konci musí existovať bbox
        if not self.bbox or len(self.bbox) != 4:
            raise ValueError("AOI must have bbox (either directly or computed from geometry)")

        return self
