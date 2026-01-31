from pydantic import BaseModel, ConfigDict
from datetime import datetime
from decimal import Decimal
from typing import Any

GeoJSON = dict[str, Any]
class HikeGetDto(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    odh_id: str
    difficulty: str | None = None
    length_km: float | None = None
    duration_minutes: int | None = None
    elevation_gain_m: int | None = None
    elevation_loss_m: int | None = None
    description: str | None = None

    geometry: GeoJSON | None = None
    start_point: GeoJSON | None = None
    end_point: GeoJSON | None = None

    circular: bool
    created_at: datetime
    updated_at: datetime

    start_point_distance_from_selected_point: float | None = None

    @classmethod
    def from_row(cls, row: dict) -> "HikeGetDto":
        if isinstance(row.get("length_km"), Decimal):
            row["length_km"] = float(row["length_km"])
        return cls.model_validate(row)