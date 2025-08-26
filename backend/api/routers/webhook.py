from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any
from services import config_service, tmdb_service, rule_service, emby_service
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/webhook/{token}", tags=["Webhook"])
async def receive_webhook(token: str, payload: Dict[Any, Any] = Body(...)):
    """
    接收 Emby Webhook 通知，验证 token 并根据配置进行自动化处理。
    """
    # 1. 验证 Token 和启用状态
    webhook_config = config_service.get_config().get('WEBHOOK', {})
    is_enabled = webhook_config.get('enabled', 'false').lower() == 'true'
    secret_token = webhook_config.get('secret_token')

    if not is_enabled:
        logger.warning("Webhook 接收器当前已禁用，忽略请求。")
        raise HTTPException(status_code=403, detail="Webhook receiver is disabled.")

    if not secret_token or token != secret_token:
        logger.warning(f"收到无效的 Webhook token: {token}")
        raise HTTPException(status_code=401, detail="Invalid webhook token.")

    # 2. 记录接收到的数据
    logger.info("--- 收到有效的 Webhook 请求 ---")
    try:
        pretty_payload = json.dumps(payload, indent=2, ensure_ascii=False)
        logger.debug(pretty_payload)
    except Exception as e:
        logger.error(f"无法格式化为 JSON，记录原始数据: {e}")
        logger.debug(payload)
    
    # 3. 检查自动化是否启用
    automation_enabled = webhook_config.get('automation_enabled', 'false').lower() == 'true'
    if not automation_enabled:
        logger.info("Webhook 自动化处理当前已禁用，仅记录数据。")
        return {"status": "received", "message": "Webhook received, but automation is disabled."}

    # 4. 开始自动化处理
    logger.info("--- 开始自动化处理 ---")
    try:
        item = payload.get('Item', {})
        if not item:
            logger.warning("Webhook payload 中缺少 'Item' 信息，跳过处理。")
            return {"status": "skipped", "message": "Missing 'Item' in payload."}

        tmdb_id = item.get('ProviderIds', {}).get('Tmdb')
        item_type = item.get('Type')  # "Movie" or "Series"
        item_id = item.get('Id')      # Emby Item ID

        if not all([tmdb_id, item_type, item_id]):
            logger.warning(f"缺少关键信息 (TMDB ID, Item Type, or Item ID)，跳过处理。TMDB_ID: {tmdb_id}, Type: {item_type}, ItemID: {item_id}")
            return {"status": "skipped", "message": "Missing key information."}
        
        logger.info(f"提取信息成功: Emby ID='{item_id}', TMDB ID='{tmdb_id}', Type='{item_type}'")

        media_type_tmdb = 'movie' if item_type == 'Movie' else 'tv' if item_type == 'Series' else None
        if not media_type_tmdb:
            logger.warning(f"不支持的媒体类型: {item_type}，跳过处理。")
            return {"status": "skipped", "message": f"Unsupported media type: {item_type}"}

        logger.info(f"正在从 TMDB 获取 '{tmdb_id}' ({media_type_tmdb}) 的详细信息...")
        details = tmdb_service.get_tmdb_details(tmdb_id, media_type_tmdb)
        if not details:
            raise Exception("Failed to get TMDB details.")

        genre_ids = [genre['id'] for genre in details.get('genres', [])]
        countries = [country['iso_3166_1'] for country in details.get('production_countries', [])]
        
        media_year = None
        if item_type == 'Movie':
            release_date = details.get('release_date')
            if release_date:
                media_year = int(release_date.split('-')[0])
        elif item_type == 'Series':
            first_air_date = details.get('first_air_date')
            if first_air_date:
                media_year = int(first_air_date.split('-')[0])

        logger.info(f"提取的 TMDB 信息: Genres={genre_ids}, Countries={countries}, Year={media_year}")
        
        generated_tags = rule_service.generate_tags(countries, genre_ids, media_year, media_type_tmdb)
        logger.info(f"根据规则生成的标签: {generated_tags}")

        if not generated_tags:
            logger.info("未生成任何标签，处理结束。")
            return {"status": "success", "message": "No tags generated."}

        write_mode = webhook_config.get('write_mode', 'merge')
        logger.info(f"准备以 '{write_mode}' 模式向 Emby 项目 '{item_id}' 写入标签: {generated_tags}")
        
        success = emby_service.update_item_metadata(
            item_id=item_id,
            tags_to_set=generated_tags,
            mode=write_mode
        )

        if success:
            logger.info("成功更新 Emby 项目的标签。")
            return {"status": "success", "message": f"Tags {generated_tags} applied successfully."}
        else:
            raise Exception("Failed to update Emby item.")

    except Exception as e:
        logger.error(f"自动化处理过程中发生错误: {e}", exc_info=True)
        return {"status": "error", "message": "An error occurred during processing.", "detail": str(e)}
    finally:
        logger.info("--- 自动化处理结束 ---")
