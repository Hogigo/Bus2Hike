from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Any
from typing import Optional, List

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


class FilterParams(BaseModel):
    longitude: Optional[float] = Query(default=11.33982, ge=-180, le=180)
    latitude: Optional[float] = Query(default=46.49067, ge=-90, le=90)
    range_km: Optional[float] = Query(default=100, gt=0)

    def all_query_params_missing(self) -> bool:
        all_values = self.model_dump().values()
        return all(value is None for value in all_values)

    def all_query_params_present(self) -> bool:
        all_values = self.model_dump().values()
        return all(v is not None for v in all_values)