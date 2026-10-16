import json
import os
import copy
import sys

DEFAULT_CLOCK_CONFIG = {
    "target_timezone": "Asia/Shanghai",
    "font_family": "Segoe UI",
    "font_size": 9,
    "font_color": "system",
    "bg_color": "system",
    "show_date": True,
    "format_style": "windows",
    "time_format": "%H:%M",
    "date_format": "%Y/%m/%d",
    "position": "overlay_taskbar" # overlay_taskbar or custom
}

DEFAULT_CONFIG = {
    "clocks": [DEFAULT_CLOCK_CONFIG],
    "autostart": False,
    "language": "zh",
    "version": "1.1.1"
}

def get_app_base_path():
    """取得应用程序根目录，兼容于脚本执行与 PyInstaller 打包后的 EXE"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的 EXE
        return os.path.dirname(sys.executable)
    else:
        # 如果是脚本执行
        return os.path.dirname(os.path.abspath(__file__))

def get_config_file_path():
    """取得设置档的绝对路径。优先使用 %APPDATA%（解决安装在 Program Files 时的无写入权限问题），并自动从旧路径迁移。"""
    app_dir_config = os.path.join(get_app_base_path(), "config.json")
    appdata = os.environ.get("APPDATA")
    if appdata:
        config_dir = os.path.join(appdata, "DesktopTimezoneClock")
        try:
            os.makedirs(config_dir, exist_ok=True)
            appdata_config = os.path.join(config_dir, "config.json")
            # 自动迁移：如果 APPDATA 内没有设置档，但应用程序根目录下有旧设置档，则将其复制过去
            if not os.path.exists(appdata_config) and os.path.exists(app_dir_config):
                try:
                    import shutil
                    shutil.copy2(app_dir_config, appdata_config)
                    print(f"[config] Migrated config from {app_dir_config} to {appdata_config}")
                except Exception as e:
                    print(f"[config] Migration failed: {e}")
            return appdata_config
        except Exception:
            pass
    return app_dir_config

# 锁定设置档绝对路径，防范开机自启动时 CWD 偏移
CONFIG_FILE = get_config_file_path()

def load_config():
    if not os.path.exists(CONFIG_FILE):
        initial = copy.deepcopy(DEFAULT_CONFIG)
        save_config(initial)
        return initial
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            # 确保所有默认键都存在
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = copy.deepcopy(value)

            # 确保 clocks 内每个时钟都补齐默认键
            normalized_clocks = []
            for clock_cfg in config.get("clocks", []):
                merged = copy.deepcopy(DEFAULT_CLOCK_CONFIG)
                if isinstance(clock_cfg, dict):
                    merged.update(clock_cfg)
                    if "format_style" not in clock_cfg:
                        legacy_default = (
                            clock_cfg.get("font_family") == "Microsoft JhengHei UI"
                            and clock_cfg.get("time_format") == "%#I:%M %p"
                            and clock_cfg.get("date_format") == "%#d/%#m/%Y"
                        )
                        if legacy_default:
                            # 仅迁移原项目的默认组合，保留用户自定义的其他设置。
                            for name in ("font_family", "time_format", "date_format"):
                                merged[name] = DEFAULT_CLOCK_CONFIG[name]
                            if merged["target_timezone"] == "Asia/Hong_Kong":
                                merged["target_timezone"] = DEFAULT_CLOCK_CONFIG["target_timezone"]
                        elif "time_format" in clock_cfg or "date_format" in clock_cfg:
                            merged["format_style"] = "custom"

                # 兼容旧版本：旧默认 white/black 视为「跟随系统」
                if (
                    isinstance(clock_cfg, dict)
                    and "font_color" in clock_cfg
                    and "bg_color" in clock_cfg
                    and clock_cfg.get("font_color") == "white"
                    and str(clock_cfg.get("bg_color")).lower() in ("black", "#000000")
                ):
                    merged["font_color"] = "system"
                    merged["bg_color"] = "system"

                normalized_clocks.append(merged)
            if not normalized_clocks:
                normalized_clocks = [copy.deepcopy(DEFAULT_CLOCK_CONFIG)]
            config["clocks"] = normalized_clocks
            return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return copy.deepcopy(DEFAULT_CONFIG)

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving config: {e}")
