from fastapi import APIRouter, HTTPException, Body
from typing import Dict
from services import config_service
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/config", tags=["Configuration"])

@router.get("/")
async def get_current_config():
    """获取当前配置"""
    return JSONResponse(content=config_service.get_config())

@router.post("/")
async def save_config(config_data: Dict[str, Dict[str, str]] = Body(...)):
    """保存配置"""
    if config_service.update_config(config_data):
        # 需要想办法让应用重新加载配置
        return {"status": "success", "message": "配置已保存。请注意，部分配置可能需要重启应用才能生效。"}
    else:
        raise HTTPException(status_code=500, detail="保存配置文件失败。")
