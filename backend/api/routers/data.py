from fastapi import APIRouter
from core.constants import GENRE_ID_MAP, COUNTRY_CODE_MAP

router = APIRouter(prefix="/data", tags=["Data"])

@router.get("/maps")
async def get_data_maps():
    """获取用于前端选择的映射数据"""
    return {
        "countries": COUNTRY_CODE_MAP,
        "genres": GENRE_ID_MAP
    }
