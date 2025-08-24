from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, List
from services import rule_service

router = APIRouter(prefix="/rules", tags=["Rules"])

@router.get("/")
async def get_all_rules():
    """获取所有规则"""
    return rule_service.load_rules_from_file()

@router.post("/")
async def save_all_rules(rules: List[Dict[str, Any]] = Body(...)):
    """保存所有规则"""
    if rule_service.save_rules_to_file(rules):
        return {"status": "success", "message": "规则已成功保存。"}
    else:
        raise HTTPException(status_code=500, detail="保存规则文件失败。")
