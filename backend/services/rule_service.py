import json
import os
from typing import List, Dict, Any

# --- 规则文件路径 ---
RULES_FILE_PATH = "/app/config/rules.json"

def load_rules_from_file() -> List[Dict[str, Any]]:
    """从文件加载规则"""
    if not os.path.exists(RULES_FILE_PATH):
        print(f"警告：规则文件未找到: {RULES_FILE_PATH}")
        return []
    try:
        with open(RULES_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("rules", [])
    except (json.JSONDecodeError, IOError) as e:
        print(f"加载或解析 rules.json 时出错: {e}")
        return []

def save_rules_to_file(rules: List[Dict[str, Any]]) -> bool:
    """将规则列表保存到文件"""
    try:
        with open(RULES_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump({"rules": rules}, f, ensure_ascii=False, indent=2)
        return True
    except IOError as e:
        print(f"写入 rules.json 时出错: {e}")
        return False

def generate_tags(countries: List[str], genre_ids: List[int], item_type: str) -> List[str]:
    """
    根据国家、类型 ID 和媒体类型生成标签。
    item_type: "movie", "series", "all"
    """
    rules = load_rules_from_file()
    generated_tags = set()

    if not rules:
        return []

    for rule in rules:
        conditions = rule.get("conditions", {})
        rule_countries = conditions.get("countries", [])
        rule_genre_ids = conditions.get("genre_ids", [])
        rule_item_type = rule.get("item_type", "all") # 默认为 "all"

        # 如果规则中既没有国家也没有类型，则跳过
        if not rule_countries and not rule_genre_ids:
            continue

        # 检查国家匹配
        # 如果规则中定义了国家，则必须匹配；如果未定义，则视为通过
        country_match = (not rule_countries) or any(c in rule_countries for c in countries)

        # 检查类型匹配
        # 如果规则中定义了类型，则必须匹配；如果未定义，则视为通过
        genre_match = (not rule_genre_ids) or any(gid in rule_genre_ids for gid in genre_ids)

        # 检查媒体类型匹配
        # 如果规则的 item_type 是 "all"，或者与当前 item_type 匹配，则通过
        # 特殊处理：如果 rule_item_type 是 "series"，则 item_type 为 "series" 或 "tv" 都算匹配
        if rule_item_type == "series":
            type_match = (item_type == "series") or (item_type == "tv")
        else:
            type_match = (rule_item_type == "all") or (rule_item_type == item_type)

        # 必须同时满足国家、类型和媒体类型条件（如果它们被定义的话）
        if country_match and genre_match and type_match:
            generated_tags.add(rule["tag"])

    return list(generated_tags)
