# TMDB Genre ID and Name Mapping
# Using ID as key for better lookup performance
GENRE_ID_MAP = {
    28: "动作",
    12: "冒险",
    16: "动画",
    35: "喜剧",
    80: "犯罪",
    99: "纪录片",
    18: "剧情",
    10751: "家庭",
    14: "奇幻",
    36: "历史",
    27: "恐怖",
    10402: "音乐",
    9648: "悬疑",
    10749: "爱情",
    878: "科幻",
    10770: "电视电影",
    53: "惊悚",
    10752: "战争",
    37: "西部",
    10759: "动作冒险",
    10762: "Kids",
    10763: "News",
    10764: "Reality",
    10765: "科幻奇幻",
    10766: "Soap",
    10767: "Talk",
    10768: "战争政治"
}

# Reverse mapping for convenience if needed
GENRE_NAME_MAP = {v: k for k, v in GENRE_ID_MAP.items()}

# Country Code and Name Mapping (ISO 3166-1 Alpha-2)
COUNTRY_CODE_MAP = {
    "US": "美国",
    "GB": "英国",
    "FR": "法国",
    "DE": "德国",
    "IT": "意大利",
    "ES": "西班牙",
    "CA": "加拿大",
    "AU": "澳大利亚",
    "JP": "日本",
    "KR": "韩国",
    "CN": "中国大陆",
    "HK": "中国香港",
    "TW": "中国台湾",
    "RU": "俄罗斯",
    "IN": "印度",
    "BR": "巴西",
    "MX": "墨西哥",
    "SE": "瑞典",
    "DK": "丹麦",
    "NO": "挪威",
    "NL": "荷兰",
    "BE": "比利时",
    "IE": "爱尔兰",
    "PL": "波兰",
    "TH": "泰国"
}
