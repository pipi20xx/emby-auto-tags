from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import List, Literal
from services import tmdb_service, emby_service, rule_service

router = APIRouter(prefix="/test", tags=["Tests"])

@router.post("/clear-all-tags")
async def clear_all_emby_tags():
    """
    清除 Emby 媒体库中所有电影和剧集的标签。
    """
    result = emby_service.clear_all_item_tags()
    if result["success"]:
        return {
            "status": "success",
            "message": f"成功清除 {result['cleared_count']} 个项目的标签，{result['failed_count']} 个项目清除失败。",
            "cleared_count": result['cleared_count'],
            "failed_count": result['failed_count']
        }
    else:
        raise HTTPException(status_code=500, detail="清除所有标签时发生错误。")

@router.post("/tmdb")
async def test_tmdb_fetch(tmdb_id: str = Body(..., embed=True), media_type: str = Body(..., embed=True)):
    """测试 TMDB 信息获取并返回提取后的关键信息"""
    details = tmdb_service.get_tmdb_details(tmdb_id, media_type)
    if not details:
        raise HTTPException(status_code=404, detail=f"无法从 TMDB 获取 TMDB ID 为 {tmdb_id} 的信息。")
    
    # 提取关键信息
    genres = details.get('genres', [])
    countries = details.get('production_countries', [])
    
    return {
        "raw_details": details,
        "extracted_info": {
            "genres": genres,
            "countries": countries
        }
    }

class EmbyWriteRequest(BaseModel):
    tmdb_id: str
    tags: List[str]
    media_type: str # 'Movie' or 'Series'
    mode: Literal['merge', 'overwrite'] = 'merge'
    is_test: bool = True

@router.post("/emby")
async def test_emby_write(request: EmbyWriteRequest = Body(...)):
    """
    测试向 Emby 写入标签，支持合并/覆盖和预览/写入模式。
    """
    emby_items = emby_service.find_emby_items_by_tmdb_id(request.tmdb_id, item_type=request.media_type)
    if not emby_items:
        raise HTTPException(status_code=404, detail=f"在 Emby 中未找到 TMDB ID 为 {request.tmdb_id} 且类型为 {request.media_type} 的项目。")

    updated_items_details = []
    failed_items_details = []
    
    for item in emby_items:
        item_id = item['Id']
        item_name = item.get('Name', '未知名称')
        
        if request.is_test:
            # 预览模式：不实际写入，只模拟结果
            # --- 借鉴桌面脚本的逻辑，确保从 Tags 和 TagItems 中都能提取标签 ---
            original_tags = []
            if "Tags" in item and item["Tags"]:
                original_tags = item["Tags"]
            elif "TagItems" in item:
                original_tags = [t.get('Name') for t in item["TagItems"] if t.get('Name')]
            
            if request.mode == 'merge':
                final_tags = sorted(list(set(original_tags + request.tags)))
            else: # overwrite
                final_tags = sorted(list(set(request.tags)))
            
            updated_items_details.append({
                "id": item_id,
                "name": item_name,
                "original_tags": original_tags,
                "final_tags": final_tags
            })
        else:
            # 写入模式：实际调用更新函数
            success = emby_service.update_item_metadata(
                item_id=item_id,
                tags_to_set=request.tags,
                mode=request.mode
            )
            if success:
                updated_items_details.append({"id": item_id, "name": item_name})
            else:
                failed_items_details.append({"id": item_id, "name": item_name})

    return {
        "status": "success",
        "action": "preview" if request.is_test else "write",
        "mode": request.mode,
        "found_items_count": len(emby_items),
        "updated_items_count": len(updated_items_details),
        "failed_items_count": len(failed_items_details),
        "tags_provided": request.tags,
        "updated_items": updated_items_details,
        "failed_items": failed_items_details
    }

class FullFlowRequest(BaseModel):
    tmdb_id: str
    media_type: str # 'movie' or 'tv'

@router.post("/full-flow-preview")
async def test_full_flow_preview(request: FullFlowRequest = Body(...)):
    """
    整合测试第一步：根据 TMDB ID 获取信息并生成标签（预览）
    """
    # 1. 获取 TMDB 详细信息
    # 注意：emby_service.find_emby_items_by_tmdb_id 需要 'Movie' 或 'Series'
    media_type_emby = 'Movie' if request.media_type == 'movie' else 'Series'
    details = tmdb_service.get_tmdb_details(request.tmdb_id, request.media_type)
    if not details:
        raise HTTPException(status_code=404, detail=f"无法从 TMDB 获取 TMDB ID 为 {request.tmdb_id} 的信息。")

    # 2. 提取所需数据
    genre_ids = [genre['id'] for genre in details.get('genres', [])]
    countries = [country['iso_3166_1'] for country in details.get('production_countries', [])]
    
    # 3. 根据规则生成标签
    generated_tags = rule_service.generate_tags(countries, genre_ids)

    # 4. 查找 Emby 项目以提供更丰富的预览信息
    emby_items = emby_service.find_emby_items_by_tmdb_id(request.tmdb_id, item_type=media_type_emby)
    
    emby_item_info = []
    if emby_items:
        for item in emby_items:
            original_tags = []
            if "Tags" in item and item["Tags"]:
                original_tags = item["Tags"]
            elif "TagItems" in item:
                original_tags = [t.get('Name') for t in item["TagItems"] if t.get('Name')]
            
            emby_item_info.append({
                "id": item.get('Id'),
                "name": item.get('Name', '未知名称'),
                "original_tags": original_tags
            })

    return {
        "status": "success",
        "tmdb_id": request.tmdb_id,
        "media_type": media_type_emby,
        "generated_tags": generated_tags,
        "emby_items_found": emby_item_info,
        "tmdb_details": {
            "title": details.get('title') or details.get('name'),
            "release_date": details.get('release_date') or details.get('first_air_date'),
            "genres": [g['name'] for g in details.get('genres', [])],
            "countries": [c['name'] for c in details.get('production_countries', [])]
        }
    }
