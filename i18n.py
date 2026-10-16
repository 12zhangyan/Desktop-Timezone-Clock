LANGUAGES = {
    "zh": {
        # ── 通用 ──────────────────────────────────────────────────────────────
        "app_title":         "桌面多时区时钟",
        "app_subtitle":      "桌面时区时钟",
        "settings":          "设置",
        "exit":              "退出",
        "save_apply":        "保存并应用",
        "cancel":            "取消",
        "check_update":      "检查更新",

        # ── 设置窗口章节 ──────────────────────────────────────────────────────
        "clock_settings":    "时钟设置",
        "preview":           "预览",
        "timezone_section":  "时区",
        "appearance":        "外观",
        "system_section":    "系统",
        "support_section":   "支持作者",
        "sponsor_github":    "GitHub Sponsor",
        "sponsor_coffee":    "Buy Me a Coffee",

        # ── 行标签 ────────────────────────────────────────────────────────────
        "language_label":    "语言",
        "font_size_label":   "字体大小",
        "system_format_label": "跟随 Windows 时间格式",
        "show_date_label":   "显示日期",
        "font_color_row":    "文字颜色",
        "bg_color_row":      "背景颜色",
        "autostart_label":   "开机自动启动",

        # ── 颜色模式 ──────────────────────────────────────────────────────────
        "color_auto":        "自动",
        "color_custom":      "自定义",
        "color_system":      "跟随系统",

        # ── 时区选择器 ────────────────────────────────────────────────────────
        "search_tz":         "搜寻时区…",

        # ── 时间标签 ──────────────────────────────────────────────────────────
        "local_time":        "本地时间:",

        # ── 颜色对话框标题 ────────────────────────────────────────────────────
        "choose_font_color": "选择文字颜色",
        "choose_bg_color":   "选择背景颜色",

        # ── 旧版兼容 ──────────────────────────────────────────────────────────
        "target_tz":         "选择目标时区:",
        "font_size":         "字体大小:",
        "show_date":         "显示日期",
        "autostart":         "随开机自动启动",
        "add_clock":         "新增时钟",
        "delete_clock":      "删除时钟",
        "language":          "语言:",
        "time_preview":      "时间预览",
        "font_color_label":  "字色:",
        "bg_color_label":    "背景:",
    },
    "en": {
        # ── General ───────────────────────────────────────────────────────────
        "app_title":         "Desktop Timezone Clock",
        "app_subtitle":      "Desktop Timezone Clock",
        "settings":          "Settings",
        "exit":              "Exit",
        "save_apply":        "Save & Apply",
        "cancel":            "Cancel",
        "check_update":      "Check for Updates",

        # ── Settings window sections ──────────────────────────────────────────
        "clock_settings":    "Clock Settings",
        "preview":           "Preview",
        "timezone_section":  "Timezone",
        "appearance":        "Appearance",
        "system_section":    "System",
        "support_section":   "Support",
        "sponsor_github":    "GitHub Sponsor",
        "sponsor_coffee":    "Buy Me a Coffee",

        # ── Row labels ────────────────────────────────────────────────────────
        "language_label":    "Language",
        "font_size_label":   "Font Size",
        "system_format_label": "Windows Time Format",
        "show_date_label":   "Show Date",
        "font_color_row":    "Font Color",
        "bg_color_row":      "Background Color",
        "autostart_label":   "Launch on Startup",

        # ── Color mode ────────────────────────────────────────────────────────
        "color_auto":        "Auto",
        "color_custom":      "Custom",
        "color_system":      "System",

        # ── Timezone picker ───────────────────────────────────────────────────
        "search_tz":         "Search timezone…",

        # ── Time labels ───────────────────────────────────────────────────────
        "local_time":        "Local:",

        # ── Color dialog titles ───────────────────────────────────────────────
        "choose_font_color": "Font Color",
        "choose_bg_color":   "Background Color",

        # ── Legacy compatibility ──────────────────────────────────────────────
        "target_tz":         "Target Timezone:",
        "font_size":         "Font Size:",
        "show_date":         "Show Date",
        "autostart":         "Auto-start on Boot",
        "add_clock":         "Add Clock",
        "delete_clock":      "Delete Clock",
        "language":          "Language:",
        "time_preview":      "Time Preview",
        "font_color_label":  "Font:",
        "bg_color_label":    "Bg:",
    }
}


class I18n:
    def __init__(self, lang_code="zh"):
        self.lang_code    = lang_code if lang_code in LANGUAGES else "en"
        self.translations = LANGUAGES[self.lang_code]

    def get(self, key: str) -> str:
        return self.translations.get(key, key)
