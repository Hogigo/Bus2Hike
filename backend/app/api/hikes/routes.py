from typing import Optional, List
from fastapi import APIRouter, Query
from  .crud import *
from .schemas import HikeGetDto

router = APIRouter(prefix="/hikes", tags=["hikes"])


@router.get("")
def list_hikes():
    return get_all_hikes()
