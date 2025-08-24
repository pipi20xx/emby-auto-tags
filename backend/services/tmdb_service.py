import requests
from typing import Optional
from core import config

def get_tmdb_details(tmdb_id: str, media_type: str) -> Optional[dict]:
    """
    根据 TMDB ID 和媒体类型获取详细信息。
    media_type: 'movie' 或 'tv'
    """
    if not config.TMDB_API_KEY:
        print("错误：TMDB_API_KEY 未在 config.ini 中设置。")
        return None

    url = f"{config.TMDB_API_BASE_URL}/{media_type}/{tmdb_id}"
    params = {
        'api_key': config.TMDB_API_KEY,
        'language': 'zh-CN'
    }
    
    proxies = {
        "http": config.HTTP_PROXY,
        "https": config.HTTP_PROXY,
    } if config.HTTP_PROXY else None

    try:
        response = requests.get(url, params=params, proxies=proxies)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求 TMDB API 时出错: {e}")
        if proxies:
            print(f"当前使用的代理是: {proxies}")
        return None
