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
        # 新增：是否为负向匹配模式 (默认为 False)
        is_negative_match = rule.get("is_negative_match", False)

        rule_years = conditions.get("years", [])

        # 如果规则中既没有国家、类型也没有年份，则跳过
        if not rule_countries and not rule_genre_ids and not rule_years:
            continue

        # 检查国家匹配
        # 如果规则中定义了国家，则根据 is_negative_match 和 match_all_conditions 判断匹配方式
        if rule_countries:
            if is_negative_match:
                if match_all_conditions:
                    # 负向严格匹配：媒体国家集合不是规则国家集合的子集
                    country_match = not set(countries).issubset(set(rule_countries))
                else:
                    # 负向模糊匹配：媒体国家集合与规则国家集合没有交集
                    country_match = not any(c in rule_countries for c in countries)
            else: # 正向匹配
                if match_all_conditions:
                    # 正向严格匹配：媒体国家集合完全等于规则国家集合
                    country_match = (set(countries) == set(rule_countries))
                else:
                    # 正向模糊匹配：媒体国家集合与规则国家集合有交集
                    country_match = any(c in rule_countries for c in countries)
        else:
            country_match = True # 如果规则中未定义国家，则视为通过

        # 检查类型匹配
        # 如果规则中定义了类型，则根据 is_negative_match 和 match_all_conditions 判断匹配方式
        if rule_genre_ids:
            if is_negative_match:
                if match_all_conditions:
                    # 负向严格匹配：媒体类型集合不是规则类型集合的子集
                    genre_match = not set(genre_ids).issubset(set(rule_genre_ids))
                else:
                    # 负向模糊匹配：媒体类型集合与规则类型集合没有交集
                    genre_match = not any(gid in rule_genre_ids for gid in genre_ids)
            else: # 正向匹配
                if match_all_conditions:
                    # 正向严格匹配：媒体类型集合完全等于规则类型集合
                    genre_match = (set(genre_ids) == set(rule_genre_ids))
                else:
                    # 正向模糊匹配：媒体类型集合与规则类型集合有交集
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
            if is_negative_match:
                # 负向匹配：媒体年份不在规则年份列表中
                year_match = (media_year not in rule_years)
            else:
                # 正向匹配：媒体年份在规则年份列表中
                year_match = (media_year in rule_years)
        elif rule_years and not media_year:
            year_match = False # 规则有年份要求但媒体没有年份信息，则不匹配

        # 组合判断逻辑
        overall_match = False
        
        # 收集所有有效的匹配结果
        individual_matches = []
        if rule_countries:
            individual_matches.append(country_match)
        if rule_genre_ids:
            individual_matches.append(genre_match)
        if rule_years:
            individual_matches.append(year_match)
        # 媒体类型匹配总是需要考虑，除非规则的item_type是"all"
        if rule_item_type != "all":
            individual_matches.append(type_match)
        
        # 如果没有定义任何条件，则默认不匹配
        if not individual_matches:
            overall_match = False
        else:
            # 无论 match_all_conditions 是 True 还是 False，不同条件之间总是“与”关系
            overall_match = all(individual_matches)

        if overall_match:
            generated_tags.add(rule["tag"])
    return list(generated_tags)
