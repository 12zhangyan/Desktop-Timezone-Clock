from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # 备退方案 (如果 Python 版本较低，但这里应该是 3.12)
    from backports.zoneinfo import ZoneInfo
import zoneinfo

_TZ_PART_ZH = {
    "Africa": "非洲",
    "America": "美洲",
    "Antarctica": "南极洲",
    "Arctic": "北极",
    "Asia": "亚洲",
    "Atlantic": "大西洋",
    "Australia": "大洋洲",
    "Europe": "欧洲",
    "Indian": "印度洋",
    "Pacific": "太平洋",
    "UTC": "世界协调时间",
    "GMT": "格林威治",
    "Hong": "香港",
    "Kong": "香港",
    "Taipei": "台北",
    "Tokyo": "东京",
    "Seoul": "首尔",
    "Shanghai": "北京时间",
    "Singapore": "新加坡",
    "Macau": "澳门",
    "Bangkok": "曼谷",
    "Manila": "马尼拉",
    "London": "伦敦",
    "Paris": "巴黎",
    "Berlin": "柏林",
    "Rome": "罗马",
    "Madrid": "马德里",
    "Lisbon": "里斯本",
    "Moscow": "莫斯科",
    "Dubai": "迪拜",
    "Istanbul": "伊斯坦布尔",
    "Kolkata": "加尔各答",
    "New": "新",
    "York": "约克",
    "Los": "洛杉矶",
    "Angeles": "安吉利斯",
    "Chicago": "芝加哥",
    "Denver": "丹佛",
    "Phoenix": "凤凰城",
    "Toronto": "多伦多",
    "Vancouver": "温哥华",
    "Sao": "圣保罗",
    "Paulo": "保罗",
    "Mexico": "墨西哥",
    "City": "市",
}


def _translate_timezone_name_zh(tz_name: str) -> str:
    parts = tz_name.split("/")
    zh_parts = []
    for part in parts:
        tokens = part.split("_")
        zh_tokens = [_TZ_PART_ZH.get(token, token) for token in tokens]
        zh_parts.append("_".join(zh_tokens))
    return "/".join(zh_parts)


def get_current_time_in_tz(tz_name):
    try:
        now = datetime.now(timezone.utc)
        target_tz = ZoneInfo(tz_name)
        return now.astimezone(target_tz)
    except Exception as e:
        print(f"Timezone error: {e}")
        return datetime.now()

def get_all_timezones_with_offset(lang_code="zh"):
    # 获取所有时区并计算目前的偏移量
    now = datetime.now(timezone.utc)
    tz_list = []
    for tz_name in zoneinfo.available_timezones():
        try:
            tz = ZoneInfo(tz_name)
            offset = now.astimezone(tz).utcoffset()
            offset_hours = offset.total_seconds() / 3600
            offset_str = f"GMT{'+' if offset_hours >= 0 else ''}{int(offset_hours)}:{'30' if offset_hours % 1 != 0 else '00'}"
            if lang_code == "zh":
                zh_name = _translate_timezone_name_zh(tz_name)
                display_name = f"{zh_name} ({tz_name})" if zh_name != tz_name else tz_name
            else:
                display_name = tz_name

            tz_list.append({
                "name": tz_name,
                "offset": offset_hours,
                "display": f"({offset_str}) {display_name}"
            })
        except Exception:
            continue
    
    # 根据偏移量排序
    tz_list.sort(key=lambda x: x["offset"])
    return tz_list
