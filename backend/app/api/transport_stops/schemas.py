from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Any

GeoJSON = dict[str, Any]


class TransportStopGetDto(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str | None = None
    geometry: GeoJSON | None = None
    created_at: datetime

    @classmethod
    def from_row(cls, row: dict) -> "TransportStopGetDto":
        return cls.model_validate(row)
