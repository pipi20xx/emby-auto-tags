from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from services import rule_service

router = APIRouter(prefix="/rules", tags=["Rules"])

class RuleCondition(BaseModel):
    countries: Optional[List[str]] = Field(default_factory=list)
    genre_ids: Optional[List[int]] = Field(default_factory=list)
    years: Optional[List[int]] = Field(default_factory=list) # Add years field

class Rule(BaseModel):
    name: str
    tag: str
    conditions: RuleCondition = Field(default_factory=RuleCondition)
    item_type: str = "all" # movie, series, all
    match_all_conditions: bool = False

@router.get("/", response_model=List[Rule])
async def get_all_rules():
    """获取所有规则"""
    # rule_service.load_rules_from_file() 应该返回符合 Rule 模型的字典列表
    # FastAPI 会自动将这些字典转换为 Rule 模型的实例
    return rule_service.load_rules_from_file()

@router.post("/")
async def save_all_rules(rules: List[Rule] = Body(...)):
    """保存所有规则"""
    # Pydantic 模型会自动处理验证和默认值，所以不再需要手动设置 item_type 默认值
    # 将 Pydantic 模型列表转换为字典列表以便保存
    rules_data = [rule.model_dump(mode='json') for rule in rules]
    
    if rule_service.save_rules_to_file(rules_data):
        return {"status": "success", "message": "规则已成功保存。"}
    else:
        raise HTTPException(status_code=500, detail="保存规则文件失败。")
