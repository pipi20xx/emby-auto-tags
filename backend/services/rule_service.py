import json
import os
from typing import List, Dict, Any, Optional

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

def generate_tags(countries: List[str], genre_ids: List[int], media_year: Optional[int], item_type: str) -> List[str]:
    """
    根据国家、类型 ID、年份和媒体类型生成标签。
    item_type: "movie", "series", "all"
    media_year: 媒体的发布年份或首播年份
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
        # 新增：是否所有条件都必须匹配 (默认为 False，即模糊匹配)
        match_all_conditions = rule.get("match_all_conditions", False)

        rule_years = conditions.get("years", [])

        # 如果规则中既没有国家、类型也没有年份，则跳过
        if not rule_countries and not rule_genre_ids and not rule_years:
            continue

        # 检查国家匹配
        # 如果规则中定义了国家，则根据 match_all_conditions 判断匹配方式
        if rule_countries:
            if match_all_conditions:
                # 必须所有国家都严格匹配（集合相等）
                country_match = (set(countries) == set(rule_countries))
            else:
                # 只要有一个国家匹配
                country_match = any(c in rule_countries for c in countries)
        else:
            country_match = True # 如果规则中未定义国家，则视为通过

        # 检查类型匹配
        # 如果规则中定义了类型，则根据 match_all_conditions 判断匹配方式
        if rule_genre_ids:
            if match_all_conditions:
                # 必须所有类型都严格匹配（集合相等）
                genre_match = (set(genre_ids) == set(rule_genre_ids))
            else:
                # 只要有一个类型匹配
                genre_match = any(gid in rule_genre_ids for gid in genre_ids)
        else:
            genre_match = True # 如果规则中未定义类型，则视为通过

        # 检查媒体类型匹配
        # 如果规则的 item_type 是 "all"，或者与当前 item_type 匹配，则通过
        # 特殊处理：如果 rule_item_type 是 "series"，则 item_type 为 "series" 或 "tv" 都算匹配
        if rule_item_type == "series":
            type_match = (item_type == "series") or (item_type == "tv")
        else:
            type_match = (rule_item_type == "all") or (rule_item_type == item_type)

        # 检查年份匹配
        year_match = True
        if rule_years and media_year:
            year_match = (media_year in rule_years)
        elif rule_years and not media_year:
            year_match = False # 规则有年份要求但媒体没有年份信息，则不匹配

        # 必须同时满足国家、类型、年份和媒体类型条件（如果它们被定义的话）
        if country_match and genre_match and year_match and type_match:
            generated_tags.add(rule["tag"])
    return list(generated_tags)
