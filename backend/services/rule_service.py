import json
import os
import re
from typing import List, Dict, Any, Optional, Set

# --- 规则文件路径 ---
RULES_FILE_PATH = "/app/config/rules.json"

def _parse_years_from_string(year_str: str) -> List[int]:
    """
    从年份字符串解析年份列表。
    支持格式：
    - "2020" (单个年份)
    - "2000-2010" (年份范围，包含起始和结束)
    - "2000,2005,2010" (逗号分隔的年份列表)
    """
    years_list: Set[int] = set()
    parts = year_str.split(',')

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if '-' in part:
            try:
                start_year_str, end_year_str = part.split('-')
                start_year = int(start_year_str.strip())
                end_year = int(end_year_str.strip())
                if start_year <= end_year:
                    years_list.update(range(start_year, end_year + 1))
            except ValueError:
                print(f"警告：无效的年份范围格式 '{part}'")
        else:
            try:
                years_list.add(int(part))
            except ValueError:
                print(f"警告：无效的年份格式 '{part}'")
    return sorted(list(years_list))

def load_rules_from_file() -> List[Dict[str, Any]]:
    """从文件加载规则"""
    if not os.path.exists(RULES_FILE_PATH):
        print(f"警告：规则文件未找到: {RULES_FILE_PATH}")
        return []
    try:
        with open(RULES_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            rules = data.get("rules", [])
            # 在加载时处理年份范围字符串，填充到 years 列表中
            for rule in rules:
                conditions = rule.get("conditions", {})
                year_range_display = conditions.get("year_range_display")
                if year_range_display and not conditions.get("years"):
                    conditions["years"] = _parse_years_from_string(year_range_display)
            return rules
    except (json.JSONDecodeError, IOError) as e:
        print(f"加载或解析 rules.json 时出错: {e}")
        return []

def save_rules_to_file(rules: List[Dict[str, Any]]) -> bool:
    """将规则列表保存到文件"""
    try:
        # 在保存前，如果 year_range_display 存在，清空 years 列表，避免重复存储
        # 这样可以确保 year_range_display 是主要来源，years 是解析结果
        rules_to_save = []
        for rule in rules:
            rule_copy = rule.copy()
            conditions = rule_copy.get("conditions", {})
            if conditions.get("year_range_display"):
                conditions["years"] = [] # 清空 years 列表，只保留 year_range_display
            rules_to_save.append(rule_copy)

        with open(RULES_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump({"rules": rules_to_save}, f, ensure_ascii=False, indent=2)
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
        match_all_conditions = rule.get("match_all_conditions", False)
        is_negative_match = rule.get("is_negative_match", False)

        rule_years = conditions.get("years", []) # 此时 rule_years 已经包含了从 year_range_display 解析的年份

        # 如果规则中既没有国家、类型也没有年份，则跳过
        if not rule_countries and not rule_genre_ids and not rule_years and rule_item_type == "all":
            continue

        # --- 计算每个条件的正向匹配结果 ---
        country_match = True
        if rule_countries:
            if match_all_conditions:
                # 正向严格匹配：媒体国家集合完全等于规则国家集合
                country_match = (set(countries) == set(rule_countries))
            else:
                # 正向模糊匹配：媒体国家集合与规则国家集合有交集
                country_match = any(c in rule_countries for c in countries)

        genre_match = True
        if rule_genre_ids:
            if match_all_conditions:
                # 正向严格匹配：媒体类型集合完全等于规则类型集合
                genre_match = (set(genre_ids) == set(rule_genre_ids))
            else:
                # 正向模糊匹配：媒体类型集合与规则类型集合有交集
                genre_match = any(gid in rule_genre_ids for gid in genre_ids)

        # 检查媒体类型匹配
        # 特殊处理：如果 rule_item_type 是 "series"，则 item_type 为 "series" 或 "tv" 都算匹配
        if rule_item_type == "series":
            type_match = (item_type == "series") or (item_type == "tv")
        else:
            type_match = (rule_item_type == "all") or (rule_item_type == item_type)

        year_match = True
        if rule_years: # 规则有年份要求
            if media_year is not None: # 媒体有年份信息
                year_match = (media_year in rule_years)
            else: # 规则有年份要求但媒体没有年份信息，则不匹配
                year_match = False

        # 收集所有有效的正向匹配结果
        individual_positive_matches = []
        if rule_countries:
            individual_positive_matches.append(country_match)
        if rule_genre_ids:
            individual_positive_matches.append(genre_match)
        if rule_years:
            individual_positive_matches.append(year_match)
        # 如果没有定义任何条件，则默认不匹配
        if not individual_positive_matches:
            pre_overall_match = False
        else:
            # 无论 match_all_conditions 是 True 还是 False，不同条件之间总是“与”关系
            pre_overall_match = all(individual_positive_matches)

        # --- 根据 is_negative_match 反转初步匹配结果 ---
        overall_match_excluding_type = pre_overall_match
        if is_negative_match:
            overall_match_excluding_type = not pre_overall_match

        # 最终匹配结果：在考虑负向匹配后，还需要满足媒体类型匹配（如果规则定义了媒体类型）
        # 媒体类型匹配不参与负向匹配的反转
        overall_match = overall_match_excluding_type
        if rule_item_type != "all":
            overall_match = overall_match and type_match

        if overall_match:
            generated_tags.add(rule["tag"])
    return list(generated_tags)
