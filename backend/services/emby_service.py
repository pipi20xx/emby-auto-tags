import requests
import json
from typing import List, Optional, Literal
from core import config
import logging

logger = logging.getLogger(__name__)

def _get_headers():
    """构造 Emby API 请求头"""
    return {
        'X-Emby-Token': config.EMBY_API_KEY,
        'Content-Type': 'application/json',
    }

def _get_user_id():
    """
    获取 UserID，优先从配置中读取，如果未配置则尝试从 API 自动获取。
    严格遵循桌面版的逻辑。
    """
    # 1. 优先使用配置文件中指定的 UserID
    if config.EMBY_USER_ID:
        return config.EMBY_USER_ID

    # 2. 如果配置中没有，则尝试自动获取（带缓存）
    if hasattr(_get_user_id, "cached_auto_user_id"):
        return _get_user_id.cached_auto_user_id

    print("配置中未指定 user_id，尝试自动获取...")
    url = f"{config.EMBY_SERVER_URL}/emby/Users"
    try:
        response = requests.get(url, headers=_get_headers(), timeout=5)
        response.raise_for_status()
        users = response.json()
        if users:
            user_id = users[0]['Id']
            print(f"自动获取 UserID 成功: {user_id}")
            _get_user_id.cached_auto_user_id = user_id
            return user_id
        print("警告: Emby API 未返回任何用户，无法自动获取 UserID。")
        return None
    except requests.exceptions.RequestException as e:
        print(f"自动获取 Emby UserID 时出错: {e}")
        return None

def find_emby_items_by_tmdb_id(tmdb_id: str, item_type: str = "Movie,Series") -> List[dict]:
    """
    根据 Provider (TMDB) ID 查找 Emby 中的媒体项目。
    :param tmdb_id: TMDB ID
    :param item_type: Emby 的媒体类型, 例如 "Movie", "Series", 或 "Movie,Series"
    """
    if not config.EMBY_SERVER_URL:
        print("错误: EMBY_SERVER_URL 未配置")
        return []

    user_id = _get_user_id()
    if not user_id:
        print("错误: 无法获取 Emby UserID，无法继续查找。")
        return []

    # 使用 /Users/{UserId}/Items 端点进行更可靠的查询
    url = f"{config.EMBY_SERVER_URL}/emby/Users/{user_id}/Items"
    params = {
        'Recursive': 'true',
        'IncludeItemTypes': item_type,
        'Fields': 'ProviderIds,Tags,TagItems,LockedFields', # 增加了 TagItems
        'AnyProviderIdEquals': f"tmdb.{tmdb_id}" # 使用更可靠的查询参数
    }
    
    try:
        response = requests.get(url, headers=_get_headers(), params=params)
        response.raise_for_status()
        data = response.json()
        
        # API 可能返回多个结果，需要精确匹配
        exact_matches = []
        for item in data.get('Items', []):
            provider_ids = item.get('ProviderIds', {})
            if str(provider_ids.get('Tmdb')) == str(tmdb_id):
                exact_matches.append(item)
        
        return exact_matches
    except requests.exceptions.RequestException as e:
        print(f"查找 Emby 项目时出错 (TMDB ID: {tmdb_id}): {e}")
        return []

def update_item_metadata(
    item_id: str,
    tags_to_set: List[str],
    mode: Literal['merge', 'overwrite'] = 'merge'
) -> bool:
    """
    更新指定 Emby 项目的元数据（当前仅支持标签）。
    借鉴桌面脚本的稳定逻辑。

    :param item_id: Emby 媒体项目 ID
    :param tags_to_set: 要设置的标签列表
    :param mode: 'merge' (合并) 或 'overwrite' (覆盖)
    :return: 更新是否成功
    """
    if not config.EMBY_SERVER_URL:
        print("错误: EMBY_SERVER_URL 未配置")
        return False

    # 1. 获取项目的完整数据，这是更新所必需的
    item_url = f"{config.EMBY_SERVER_URL}/emby/Items/{item_id}"
    user_id = _get_user_id()
    if not user_id:
        print(f"错误: 无法获取 UserID，无法更新项目 {item_id}")
        return False
    
    # 使用 /Users/{UserId}/Items/{Id} 获取项目信息
    get_url = f"{config.EMBY_SERVER_URL}/emby/Users/{user_id}/Items/{item_id}"
    try:
        item_response = requests.get(get_url, headers=_get_headers())
        item_response.raise_for_status()
        item_data = item_response.json()
    except requests.exceptions.RequestException as e:
        print(f"获取项目 {item_id} 的详细信息时出错: {e}")
        return False

    # 2. 计算最终的标签列表
    original_tags = []
    if "Tags" in item_data and item_data["Tags"]:
        original_tags = item_data["Tags"]
    elif "TagItems" in item_data:
        original_tags = [t.get('Name') for t in item_data["TagItems"] if t.get('Name')]

    if mode == 'merge':
        final_tags = sorted(list(set(original_tags + tags_to_set)))
    else: # overwrite
        final_tags = sorted(list(set(tags_to_set)))

    # 如果标签没有变化，则无需更新
    if final_tags == sorted(original_tags):
        print(f"项目 {item_id} 的标签无需更新。")
        return True

    item_data['Tags'] = final_tags
    # Emby 需要 TagItems 字段来配合更新
    item_data['TagItems'] = [{"Name": tag} for tag in final_tags]

    # 3. 处理字段锁定
    locked_fields = set(item_data.get('LockedFields', []))
    if 'Tags' in locked_fields:
        print(f"项目 {item_id} 的 'Tags' 字段被锁定，将临时解锁。")
        locked_fields.remove('Tags')
        item_data['LockedFields'] = list(locked_fields)

    # 4. 发送 POST 请求更新项目
    update_url = f"{config.EMBY_SERVER_URL}/emby/Items/{item_id}"
    try:
        post_response = requests.post(update_url, headers=_get_headers(), json=item_data)
        post_response.raise_for_status()
        print(f"成功更新项目 {item_id} 的标签 ({mode}模式)。最终标签: {final_tags}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"更新 Emby 项目 {item_id} 标签时出错: {e}")
        # 尝试打印响应内容以获取更多信息
        if 'post_response' in locals() and post_response is not None:
            print(f"响应内容: {post_response.text}")
        return False

# 为了向后兼容旧的测试路由，保留此函数，但让它调用新的核心函数
def get_all_emby_items(item_type: str = "Movie,Series") -> List[dict]:
    """
    获取 Emby 中所有指定类型的媒体项目。
    :param item_type: Emby 的媒体类型, 例如 "Movie", "Series", 或 "Movie,Series"
    """
    if not config.EMBY_SERVER_URL:
        print("错误: EMBY_SERVER_URL 未配置")
        return []

    # 使用 /emby/Items 端点，与桌面版保持一致
    url = f"{config.EMBY_SERVER_URL}/emby/Items"
    params = {
        'Recursive': 'true',
        'IncludeItemTypes': item_type,
        'Fields': 'ProviderIds,Tags,TagItems,LockedFields',
        'Limit': 100, # 将 Limit 设置为较小的值，以便更好地观察分页
        'api_key': config.EMBY_API_KEY # 在参数中包含 api_key
    }
    
    all_items = []
    start_index = 0
    import logging
    logger = logging.getLogger(__name__) # 获取 logger 实例

    while True:
        current_params = params.copy()
        current_params['StartIndex'] = start_index
        try:
            logger.info(f"正在获取 Emby 项目: StartIndex={start_index}, Limit={params['Limit']}") # 新增日志
            # 同时使用请求头和查询参数，以确保兼容性
            response = requests.get(url, headers=_get_headers(), params=current_params)
            response.raise_for_status()
            data = response.json()
            items = data.get('Items', [])
            all_items.extend(items)
            
            total_count = data.get('TotalRecordCount', 0)
            logger.info(f"当前获取到 {len(items)} 个项目，总记录数: {total_count}，已获取总数: {len(all_items)}") # 新增日志

            if not items or len(all_items) >= total_count: # 如果当前页没有项目，或者已获取的项目数达到或超过总数，说明已经获取完所有项目
                break
            start_index += params['Limit']
        except requests.exceptions.RequestException as e:
            logger.error(f"获取所有 Emby 项目时出错: {e}") # 使用 logger.error
            return []
    return all_items

def get_favorite_emby_items(item_type: str = "Movie,Series") -> List[dict]:
    """
    获取 Emby 中所有指定类型的收藏媒体项目。
    :param item_type: Emby 的媒体类型, 例如 "Movie", "Series", 或 "Movie,Series"
    """
    if not config.EMBY_SERVER_URL:
        logger.error("错误: EMBY_SERVER_URL 未配置")
        return []

    user_id = _get_user_id()
    if not user_id:
        logger.error("错误: 无法获取 Emby UserID，无法继续查找收藏项目。")
        return []

    url = f"{config.EMBY_SERVER_URL}/emby/Users/{user_id}/Items"
    params = {
        'Recursive': 'true',
        'IncludeItemTypes': item_type,
        'Fields': 'ProviderIds,Tags,TagItems,LockedFields',
        'IsFavorite': 'true', # 关键参数：只获取收藏项目
        'Limit': 100,
        'api_key': config.EMBY_API_KEY
    }
    
    all_items = []
    start_index = 0

    while True:
        current_params = params.copy()
        current_params['StartIndex'] = start_index
        try:
            logger.info(f"正在获取 Emby 收藏项目: StartIndex={start_index}, Limit={params['Limit']}")
            response = requests.get(url, headers=_get_headers(), params=current_params)
            response.raise_for_status()
            data = response.json()
            items = data.get('Items', [])
            all_items.extend(items)
            
            total_count = data.get('TotalRecordCount', 0)
            logger.info(f"当前获取到 {len(items)} 个收藏项目，总记录数: {total_count}，已获取总数: {len(all_items)}")

            if not items or len(all_items) >= total_count:
                break
            start_index += params['Limit']
        except requests.exceptions.RequestException as e:
            logger.error(f"获取所有 Emby 收藏项目时出错: {e}")
            return []
    return all_items

def clear_all_item_tags() -> dict:
    """
    清除 Emby 媒体库中所有电影和剧集的标签。
    """
    print("开始清除所有 Emby 媒体项目的标签...")
    all_items = get_all_emby_items()
    
    cleared_count = 0
    failed_count = 0
    
    for item in all_items:
        item_id = item.get('Id')
        item_name = item.get('Name')
        if item_id:
            print(f"正在清除项目 '{item_name}' (ID: {item_id}) 的标签...")
            if update_item_metadata(item_id, [], mode='overwrite'):
                cleared_count += 1
            else:
                failed_count += 1
        else:
            print(f"警告: 发现一个没有 ID 的项目: {item}")

    print(f"清除完成。成功清除 {cleared_count} 个项目的标签，{failed_count} 个项目清除失败。")
    return {
        "success": True,
        "cleared_count": cleared_count,
        "failed_count": failed_count
    }

def clear_specific_item_tags(tags_to_remove: List[str]) -> dict:
    """
    从 Emby 媒体库中所有电影和剧集中移除指定的标签。
    """
    print(f"开始从所有 Emby 媒体项目中移除指定标签: {tags_to_remove}...")
    all_items = get_all_emby_items()
    
    processed_count = 0
    removed_from_count = 0
    failed_count = 0
    
    for item in all_items:
        item_id = item.get('Id')
        item_name = item.get('Name')
        if not item_id:
            print(f"警告: 发现一个没有 ID 的项目: {item}")
            continue

        processed_count += 1
        print(f"正在处理项目 '{item_name}' (ID: {item_id})...")

        original_tags = []
        if "Tags" in item and item["Tags"]:
            original_tags = item["Tags"]
        elif "TagItems" in item:
            original_tags = [t.get('Name') for t in item["TagItems"] if t.get('Name')]
        
        # 计算新的标签列表：移除所有 tags_to_remove 中的标签
        new_tags = [tag for tag in original_tags if tag not in tags_to_remove]

        # 如果标签列表有变化，才进行更新
        if sorted(new_tags) != sorted(original_tags):
            print(f"项目 '{item_name}' (ID: {item_id}) 的标签将从 {original_tags} 更新为 {new_tags}")
            if update_item_metadata(item_id, new_tags, mode='overwrite'):
                removed_from_count += 1
            else:
                failed_count += 1
        else:
            print(f"项目 '{item_name}' (ID: {item_id}) 不包含任何要移除的标签，跳过更新。")

    print(f"指定标签移除完成。总处理 {processed_count} 个项目，成功从 {removed_from_count} 个项目中移除标签，{failed_count} 个项目处理失败。")
    return {
        "success": True,
        "processed_count": processed_count,
        "removed_from_count": removed_from_count,
        "failed_count": failed_count
    }

async def tag_all_media_items(
    mode: Literal['merge', 'overwrite'] = 'merge',
    library_type: Literal['all', 'favorite'] = 'all'
) -> dict:
    """
    遍历所有 Emby 媒体库中的电影和剧集，根据规则进行打标签。
    处理多版本电影只打一个标签，多版本电视剧全部打标签的逻辑。
    :param mode: 'merge' (合并) 或 'overwrite' (覆盖)
    :param library_type: 'all' (全库) 或 'favorite' (最爱/收藏)
    """
    from services import tmdb_service, rule_service # 避免循环引用
    from collections import defaultdict

    logger.info(f"开始对 Emby 媒体项目进行打标签操作 (模式: {mode}, 库类型: {library_type})...")
    
    all_items = []
    if library_type == 'all':
        all_items = get_all_emby_items()
        logger.info(f"从 Emby API 获取到 {len(all_items)} 个全库媒体项目。")
    elif library_type == 'favorite':
        all_items = get_favorite_emby_items()
        logger.info(f"从 Emby API 获取到 {len(all_items)} 个收藏媒体项目。")

    processed_count = 0
    updated_count = 0
    failed_count = 0

    # 按 TMDB ID 和 ItemType 分组项目
    grouped_items: Dict[str, Dict[str, List[dict]]] = defaultdict(lambda: defaultdict(list))
    for item in all_items:
        tmdb_id = item.get('ProviderIds', {}).get('Tmdb')
        item_type = item.get('Type') # "Movie" or "Series"
        if tmdb_id and item_type:
            grouped_items[tmdb_id][item_type].append(item)
    
    # 新增日志：打印分组后的项目数量
    for tmdb_id, types_map in grouped_items.items():
        for item_type, items_list in types_map.items():
            logger.info(f"TMDB ID: {tmdb_id}, 类型: {item_type}, 包含 {len(items_list)} 个 Emby 项目。")

    for tmdb_id, types_map in grouped_items.items():
        for item_type, items_list in types_map.items():
            if item_type == 'Movie' or item_type == 'Series':
                # 对于电影和电视剧，处理所有项目
                for item in items_list:
                    processed_count += 1
                    if await _process_single_item_for_tagging(item, mode, logger, tmdb_service, rule_service):
                        updated_count += 1
                    else:
                        failed_count += 1
            else:
                # 对于其他未知类型，也处理所有项目（或者根据需求决定跳过）
                for item in items_list:
                    processed_count += 1
                    if await _process_single_item_for_tagging(item, mode, logger, tmdb_service, rule_service):
                        updated_count += 1
                    else:
                        failed_count += 1

    logger.info(f"所有媒体项目打标签完成。总处理 {processed_count} 个，成功更新 {updated_count} 个，失败 {failed_count} 个。")
    return {
        "status": "completed",
        "processed_count": processed_count,
        "updated_count": updated_count,
        "failed_count": failed_count,
        "mode": mode,
        "library_type": library_type
    }

async def _process_single_item_for_tagging(
    item: dict,
    mode: Literal['merge', 'overwrite'],
    logger,
    tmdb_service,
    rule_service
) -> bool:
    """
    处理单个 Emby 项目的标签生成和更新逻辑。
    返回 True 表示成功更新，False 表示失败或跳过。
    """
    item_id = item.get('Id')
    item_name = item.get('Name')
    item_type = item.get('Type') # "Movie" or "Series"
    tmdb_id = item.get('ProviderIds', {}).get('Tmdb')

    if not all([item_id, item_name, item_type, tmdb_id]):
        logger.warning(f"跳过项目 '{item_name}' (ID: {item_id})，缺少关键信息。")
        return False

    logger.info(f"正在处理项目 '{item_name}' (ID: {item_id}, TMDB ID: {tmdb_id}, 类型: {item_type})...")

    try:
        # 1. 从 TMDB 获取详细信息
        media_type_tmdb = 'movie' if item_type == 'Movie' else 'tv' if item_type == 'Series' else None
        if not media_type_tmdb:
            logger.warning(f"不支持的媒体类型: {item_type}，跳过处理。")
            return False

        details = tmdb_service.get_tmdb_details(tmdb_id, media_type_tmdb)
        if not details:
            logger.warning(f"无法从 TMDB 获取项目 '{item_name}' (TMDB ID: {tmdb_id}) 的信息，跳过。")
            return False

        # 2. 根据规则生成标签
        genre_ids = [genre['id'] for genre in details.get('genres', [])]
        
        countries = []
        origin_country = details.get('origin_country')
        if origin_country:
            if isinstance(origin_country, list):
                countries = origin_country
            elif isinstance(origin_country, str):
                countries = [origin_country]
        
        if not countries:
            original_language = details.get('original_language')
            if original_language:
                lang_to_country_map = {
                    "en": "US", "zh": "CN", "ja": "JP", "ko": "KR", "fr": "FR", "de": "DE",
                    "es": "ES", "it": "IT", "hi": "IN", "ar": "SA", "pt": "BR", "ru": "RU",
                    "th": "TH", "sv": "SE", "da": "DK", "no": "NO", "nl": "NL", "pl": "PL",
                }
                mapped_country = lang_to_country_map.get(original_language)
                if mapped_country:
                    countries = [mapped_country]
        
        media_year = None
        if media_type_tmdb == 'movie':
            release_date = details.get('release_date')
            if release_date and len(release_date) >= 4:
                media_year = int(release_date[:4])
        elif media_type_tmdb == 'tv':
            first_air_date = details.get('first_air_date')
            if first_air_date and len(first_air_date) >= 4:
                media_year = int(first_air_date[:4])
        
        rule_item_type = 'movie' if item_type == 'Movie' else 'series' if item_type == 'Series' else 'all'
        generated_tags = rule_service.generate_tags(countries, genre_ids, media_year, rule_item_type)

        if not generated_tags:
            logger.info(f"项目 '{item_name}' 未生成任何标签，跳过更新。")
            return False

        # 3. 更新 Emby 项目的元数据
        if update_item_metadata(item_id=item_id, tags_to_set=generated_tags, mode=mode):
            return True
        else:
            return False

    except Exception as e:
        logger.error(f"处理项目 '{item_name}' (ID: {item_id}) 时发生错误: {e}")
        return False



# 为了向后兼容旧的测试路由，保留此函数，但让它调用新的核心函数
def update_item_tags(item_id: str, new_tags: List[str]):
    """
    更新指定 Emby 项目的标签（简化版，总是使用合并模式）。
    """
    return update_item_metadata(item_id, new_tags, mode='merge')
