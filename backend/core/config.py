import configparser
import os
from datetime import datetime, timezone, timedelta

# --- 配置文件路径 ---
# 在容器内的路径
CONFIG_FILE_PATH = "/app/config/config.ini"

def get_current_time() -> str:
    """
    获取当前时间，并格式化为 ISO 8601 字符串，包含时区信息。
    """
    # 使用 UTC 时间，并转换为上海时区 (UTC+8)
    utc_now = datetime.now(timezone.utc)
    shanghai_tz = timezone(timedelta(hours=8))
    shanghai_now = utc_now.astimezone(shanghai_tz)
    return shanghai_now.isoformat()


# --- 默认配置 ---
def create_default_config(path):
    """创建默认的配置文件"""
    config_obj = configparser.ConfigParser()
    config_obj['EMBY'] = {
        'server_url': 'http://localhost:8096',
        'api_key': 'your_emby_api_key',
        'user_id': 'your_emby_user_id'
    }
    config_obj['TMDB'] = {
        'api_key': 'your_tmdb_api_key',
        'rate_limit_period': '1.0' # 默认1秒1次，0表示不限制
    }
    config_obj['PROXY'] = {
        'http_proxy': ''
    }
    
    # 确保目录存在
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    with open(path, 'w', encoding='utf-8') as configfile:
        config_obj.write(configfile)
    print(f"默认配置文件已创建: {path}")


# --- 读取配置 ---
config = configparser.ConfigParser()

# 检查配置文件是否存在，如果不存在则创建
if not os.path.exists(CONFIG_FILE_PATH):
    print(f"配置文件未找到，正在创建默认配置文件: {CONFIG_FILE_PATH}")
    create_default_config(CONFIG_FILE_PATH)

config.read(CONFIG_FILE_PATH, encoding='utf-8')

# --- Emby 配置 ---
EMBY_SERVER_URL = config.get('EMBY', 'server_url', fallback=None)
EMBY_API_KEY = config.get('EMBY', 'api_key', fallback=None)
EMBY_USER_ID = config.get('EMBY', 'user_id', fallback=None)

# --- TMDB 配置 ---
TMDB_API_KEY = config.get('TMDB', 'api_key', fallback=None)
TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
TMDB_RATE_LIMIT_PERIOD = float(config.get('TMDB', 'rate_limit_period', fallback='1.0'))

# --- 代理配置 ---
HTTP_PROXY = config.get('PROXY', 'http_proxy', fallback=None)

# --- 检查关键配置是否存在 ---
if not EMBY_SERVER_URL or not EMBY_API_KEY or not TMDB_API_KEY or 'your_' in EMBY_API_KEY or 'your_' in TMDB_API_KEY:
    print("警告：Emby 或 TMDB 的配置不完整或为默认值，请检查 config.ini 文件。")
