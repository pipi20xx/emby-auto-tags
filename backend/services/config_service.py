import configparser
import secrets
from core.config import CONFIG_FILE_PATH

def get_config() -> dict:
    """
    读取配置文件并返回一个字典。
    如果 webhook 配置不存在，则自动生成并保存。
    """
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH, encoding='utf-8')

    # --- Webhook 配置自动生成 ---
    needs_saving = False
    if not config.has_section('WEBHOOK'):
        config.add_section('WEBHOOK')
        needs_saving = True
    
    if not config.has_option('WEBHOOK', 'enabled'):
        config.set('WEBHOOK', 'enabled', 'false')
        needs_saving = True

    if not config.has_option('WEBHOOK', 'secret_token'):
        # 生成一个安全的随机 token
        token = secrets.token_hex(32)
        config.set('WEBHOOK', 'secret_token', token)
        needs_saving = True

    # --- TMDB 限流配置自动生成 ---
    if not config.has_section('TMDB'):
        config.add_section('TMDB')
        needs_saving = True
    if not config.has_option('TMDB', 'rate_limit_period'):
        config.set('TMDB', 'rate_limit_period', '1.0') # 默认1秒1次，0表示不限制
        needs_saving = True

    if needs_saving:
        try:
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as configfile:
                config.write(configfile)
            print("已自动生成并保存 Webhook/TMDB 限流配置。")
        except IOError as e:
            print(f"自动保存 Webhook/TMDB 限流配置时出错: {e}")
    
    config_dict = {section: dict(config.items(section)) for section in config.sections()}
    
    # 中文化 TMDB 配置项
    if 'TMDB' in config_dict and 'rate_limit_period' in config_dict['TMDB']:
        config_dict['TMDB']['TMDB 访问频率限制周期'] = config_dict['TMDB'].pop('rate_limit_period')
        
    return config_dict

def update_config(config_data: dict):
    """用给定的字典更新配置文件"""
    config = configparser.ConfigParser()
    
    # 从字典数据填充 configparser 对象
    for section, values in config_data.items():
        # 处理 TMDB 配置项的中文化转换
        if section == 'TMDB' and 'TMDB 访问频率限制周期' in values:
            values['rate_limit_period'] = values.pop('TMDB 访问频率限制周期')
        config[section] = values
        
    # 将更新后的配置写回文件
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        return True
    except IOError as e:
        print(f"写入配置文件时出错: {e}")
        return False
