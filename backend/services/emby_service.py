import requests
import json
from typing import List, Optional, Literal
from core import config

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
def update_item_tags(item_id: str, new_tags: List[str]):
    """
    更新指定 Emby 项目的标签（简化版，总是使用合并模式）。
    """
    return update_item_metadata(item_id, new_tags, mode='merge')
