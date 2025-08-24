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

    if needs_saving:
        try:
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as configfile:
                config.write(configfile)
            print("已自动生成并保存 Webhook 配置。")
        except IOError as e:
            print(f"自动保存 Webhook 配置时出错: {e}")
    
    config_dict = {section: dict(config.items(section)) for section in config.sections()}
    return config_dict

def update_config(config_data: dict):
    """用给定的字典更新配置文件"""
    config = configparser.ConfigParser()
    
    # 从字典数据填充 configparser 对象
    for section, values in config_data.items():
        config[section] = values
        
    # 将更新后的配置写回文件
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        return True
    except IOError as e:
        print(f"写入配置文件时出错: {e}")
        return False
