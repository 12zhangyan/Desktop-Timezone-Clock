import copy
import ctypes
import tkinter as tk
import webbrowser
from tkinter import colorchooser, ttk
import customtkinter as ctk
from timezone_utils import get_current_time_in_tz, get_all_timezones_with_offset
from utils import set_autostart
from i18n import I18n
from datetime import datetime
from clock_format import format_clock

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ── Tech-Dark 调色盘（无蓝色）──────────────────────────────────────────────────
BG      = "#0D0D10"   # 底色
SURFACE = "#141418"   # 次底
CARD    = "#1B1B1F"   # 卡片
CARD2   = "#232328"   # 输入框 / 按钮
BORDER  = "#2E2E36"   # 边线
TEXT    = "#E8E8EE"   # 主文字
SUB     = "#B8B8C2"   # 副文字（提高可读性）
MUTED   = "#888888"   # 提高亮度以确保在深色背景可见
SEL_BG  = "#2C2C34"   # 选中行背景
HOVER   = "#252530"   # hover
SW_ON   = "#00BFA5"   # 开启：亮青绿
SW_OFF  = "#4D4D54"   # 关闭：中灰（提高对比度）

GITHUB_SPONSOR_URL = "https://github.com/sponsors/Kanaoda"
BUY_ME_A_COFFEE_URL = "https://www.buymeacoffee.com/kanaoda"


def _dark_title(hwnd: int):
    try:
        val = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# 自定义时区选择弹窗（带搜寻 + 固定高度可卷动列表）
# ─────────────────────────────────────────────────────────────────────────────
class _TZPicker:
    """点击时区栏后弹出的小窗口，带搜寻过滤与固定高度滚动列表。"""

    def __init__(self, parent_win, displays: list, names: list,
                 current_display: str, on_select,
                 search_placeholder: str = "Search timezone…"):
        self._displays  = displays
        self._names     = names
        self._on_select = on_select
        self._win       = ctk.CTkToplevel(parent_win)
        self._win.overrideredirect(True)
        self._win.configure(fg_color=CARD)
        self._win.attributes("-topmost", True)
        self._win.resizable(False, False)

        # 搜寻列
        top = ctk.CTkFrame(self._win, fg_color=CARD2, corner_radius=0)
        top.pack(fill="x")
        self._search_var = ctk.StringVar()
        entry = ctk.CTkEntry(
            top, textvariable=self._search_var,
            placeholder_text=search_placeholder,
            fg_color=CARD2, border_color=BORDER, text_color=TEXT,
            placeholder_text_color=MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=34, corner_radius=0,
        )
        entry.pack(fill="x", padx=8, pady=6)
        entry.focus()
        self._search_var.trace_add("write", lambda *_: self._refresh())

        # 分隔线
        ctk.CTkFrame(self._win, height=1, fg_color=BORDER,
                     corner_radius=0).pack(fill="x")

        # 可卷动列表
        self._scroll = ctk.CTkScrollableFrame(
            self._win, fg_color=CARD, corner_radius=0,
            width=340, height=280,
            scrollbar_button_color=CARD2,
            scrollbar_button_hover_color=HOVER,
        )
        self._scroll.pack(fill="both", expand=True)

        self._btn_map: dict[str, ctk.CTkButton] = {}
        self._current = current_display
        self._refresh()

        # 点外关闭
        self._win.bind("<FocusOut>", self._maybe_close)
        self._win.bind("<Escape>",   lambda e: self._win.destroy())

    def place_near(self, x: int, y: int, w: int):
        self._win.update_idletasks()
        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        ww = 356
        wh = 320
        if x + ww > sw:
            x = sw - ww - 4
        if y + wh > sh:
            y = y - wh - 4
        self._win.geometry(f"{ww}x{wh}+{x}+{y}")

    def _refresh(self):
        q = self._search_var.get().strip().lower()
        for w in self._scroll.winfo_children():
            w.destroy()
        self._btn_map.clear()
        for disp in self._displays:
            if q and q not in disp.lower():
                continue
            is_sel = (disp == self._current)
            btn = ctk.CTkButton(
                self._scroll,
                text=disp,
                anchor="w",
                height=30,
                fg_color=SEL_BG if is_sel else "transparent",
                hover_color=HOVER,
                text_color=TEXT if is_sel else SUB,
                font=ctk.CTkFont(
                    family="Segoe UI",
                    size=11,
                    weight="bold" if is_sel else "normal",
                ),
                corner_radius=4,
                command=lambda d=disp: self._pick(d),
            )
            btn.pack(fill="x", padx=4, pady=1)
            self._btn_map[disp] = btn

    def _pick(self, display: str):
        self._on_select(display)
        self._win.destroy()

    def _maybe_close(self, e=None):
        self._win.after(150, self._check_focus)

    def _check_focus(self):
        try:
            focused = self._win.focus_get()
            if focused is None:
                self._win.destroy()
        except Exception:
            try:
                self._win.destroy()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# 辅助组件
# ─────────────────────────────────────────────────────────────────────────────
class _Sep(ctk.CTkFrame):
    """行分隔线。"""
    def __init__(self, parent):
        super().__init__(parent, height=1, fg_color=BORDER, corner_radius=0)
        self.pack(fill="x", padx=14)


class _SectionLabel(ctk.CTkLabel):
    """章节标题（比行内文字更大、更粗）。"""
    def __init__(self, parent, text: str):
        super().__init__(
            parent, text=text,
            text_color=TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            anchor="w",
        )
        self.pack(anchor="w", padx=24, pady=(14, 4))


class _Row(ctk.CTkFrame):
    """一行设置列：左侧标签 + 右侧控件。"""
    def __init__(self, parent, label: str, h: int = 44):
        super().__init__(parent, fg_color=CARD, corner_radius=0, height=h)
        self.pack(fill="x")
        self.pack_propagate(False)
        ctk.CTkLabel(
            self, text=label, text_color=SUB, anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).pack(side="left", padx=14)
        self._right = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0)
        self._right.pack(side="right", padx=12)

    @property
    def right(self):
        return self._right


class _Card(ctk.CTkFrame):
    """带圆角的卡片容器（无标题——改用 _SectionLabel 在外部放置）。"""
    def __init__(self, parent):
        super().__init__(parent, fg_color=CARD, corner_radius=10,
                         border_width=1, border_color=BORDER)
        self.pack(fill="x", padx=20, pady=(0, 2))


class _TechToggle(ctk.CTkFrame):
    """小型方形开关（纯 CTk，避免 tk.Canvas 兼容性问题）。"""
    def __init__(self, parent, variable: tk.BooleanVar, command=None):
        super().__init__(parent, fg_color=CARD, corner_radius=0, width=34, height=18)
        self.pack_propagate(False)
        self._var = variable
        self._command = command

        self._track = ctk.CTkFrame(
            self, fg_color=SW_OFF, corner_radius=4, width=34, height=18
        )
        self._track.pack(fill="both", expand=True)
        self._track.pack_propagate(False)

        self._knob = ctk.CTkFrame(
            self._track, fg_color="#FFFFFF", corner_radius=3, width=14, height=14
        )
        self._knob.place(x=2, y=2)

        for w in (self, self._track, self._knob):
            w.bind("<Button-1>", self._toggle)

        self._var.trace_add("write", lambda *_: self._render())
        self._render()

    def _render(self):
        is_on = bool(self._var.get())
        self._track.configure(fg_color=SW_ON if is_on else SW_OFF)
        self._knob.configure(fg_color="#FFFFFF" if is_on else "#AAAAAA")
        self._knob.place(x=18 if is_on else 2, y=2)

    def _toggle(self, _event=None):
        self._var.set(not bool(self._var.get()))
        if self._command:
            self._command()


# ─────────────────────────────────────────────────────────────────────────────
# 主窗口
# ─────────────────────────────────────────────────────────────────────────────
class SettingsWindow:
    def __init__(self, current_config, on_save_callback,
                 on_preview_callback=None, on_close_callback=None, parent=None):
        self.config           = copy.deepcopy(current_config)
        self._original_config = copy.deepcopy(current_config)
        self.on_save          = on_save_callback
        self.on_preview       = on_preview_callback
        self.on_close         = on_close_callback
        self.parent           = parent
        self.i18n             = I18n(self.config.get("language", "zh"))
        self._update_timer    = None
        self._closed          = False

        self.root = (ctk.CTkToplevel(self.parent)
                     if self.parent is not None else ctk.CTk())
        self.root.title(self.i18n.get("clock_settings"))
        self.root.geometry("420x640")
        self.root.resizable(False, False)
        self.root.configure(fg_color=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_window)
        self.root.after(120, self._apply_dark_title)

        self.clock_idx    = 0
        self.clock_config = self.config["clocks"][self.clock_idx]
        self._reload_timezone_data()

        self._build_ui()
        self.root.update_idletasks()
        self._place_window()
        self._tick()

    # ── 深色标题列 ────────────────────────────────────────────────────────────
    def _apply_dark_title(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            _dark_title(hwnd or self.root.winfo_id())
        except Exception:
            pass

    def _place_window(self):
        """固定置中屏幕，避免父窗口座标造成跑位。"""
        w, h = 420, 640
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.root.lift()
        self.root.focus_force()

    def _reload_timezone_data(self):
        lang_code = self.config.get("language", "zh")
        self.tz_data = get_all_timezones_with_offset(lang_code=lang_code)
        self.tz_displays_all = [t["display"] for t in self.tz_data]
        self.tz_names_all = [t["name"] for t in self.tz_data]

    # ── 建构 UI ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ttk 原生下拉样式（即时展开，含 scrollbar）
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Dark.TCombobox",
            fieldbackground=CARD2,
            background=CARD2,
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            arrowcolor=TEXT,
            selectbackground=HOVER,
            selectforeground=TEXT,
            relief="flat",
            padding=6,
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", CARD2), ("disabled", CARD2)],
            background=[("readonly", CARD2), ("disabled", CARD2)],
            foreground=[("readonly", TEXT), ("disabled", SUB)],
            selectbackground=[("readonly", CARD2)],
            selectforeground=[("readonly", TEXT)],
        )
        self.root.option_add("*TCombobox*Listbox.background", CARD2)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", HOVER)
        self.root.option_add("*TCombobox*Listbox.selectForeground", TEXT)

        scroll = ctk.CTkScrollableFrame(
            self.root, fg_color=BG, corner_radius=0,
            scrollbar_button_color=CARD2,
            scrollbar_button_hover_color=HOVER,
        )
        scroll.pack(fill="both", expand=True)

        # 顶部保留间距（移除页首标题区块）
        ctk.CTkFrame(scroll, height=10, fg_color=BG, corner_radius=0).pack(fill="x")

        # ── 预览 ──────────────────────────────────────────────────────────────
        _SectionLabel(scroll, self.i18n.get("preview"))
        pv = _Card(scroll)
        self.preview_frame = ctk.CTkFrame(pv, fg_color=CARD, corner_radius=10)
        self.preview_frame.pack(fill="x", padx=0, pady=0)
        info = ctk.CTkFrame(self.preview_frame, fg_color="transparent", corner_radius=0)
        info.pack(fill="x", padx=16, pady=14)

        self.local_time_label = ctk.CTkLabel(
            info, text="", text_color=SUB, anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
        self.local_time_label.pack(anchor="w")

        self.preview_clock = ctk.CTkLabel(
            info, text="", text_color=TEXT, anchor="w",
            font=ctk.CTkFont(family="Segoe UI Semibold", size=28, weight="bold"))
        self.preview_clock.pack(anchor="w", pady=(2, 0))
        self.target_time_label = self.preview_clock

        self.target_tz_label = ctk.CTkLabel(
            info, text="", text_color=TEXT, anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=13))
        self.target_tz_label.pack(anchor="w")

        # ── 时区 ──────────────────────────────────────────────────────────────
        _SectionLabel(scroll, self.i18n.get("timezone_section"))
        tz_card = _Card(scroll)

        current_tz = self.clock_config.get("target_timezone", "Asia/Shanghai")
        self.tz_display_var = ctk.StringVar()
        try:
            idx = self.tz_names_all.index(current_tz)
            self.tz_display_var.set(self.tz_displays_all[idx])
        except ValueError:
            self.tz_display_var.set(current_tz)

        # 即时下拉选单（非自定义弹窗）
        tz_row = ctk.CTkFrame(tz_card, fg_color=CARD, corner_radius=0, height=44)
        tz_row.pack(fill="x")
        tz_row.pack_propagate(False)

        self.tz_combo = ttk.Combobox(
            tz_row,
            textvariable=self.tz_display_var,
            values=self.tz_displays_all,
            state="readonly",
            style="Dark.TCombobox",
            height=12,
            font=("Segoe UI", 9),
        )
        self.tz_combo.pack(fill="x", padx=12, pady=6)
        self.tz_combo.bind("<<ComboboxSelected>>", self._on_tz_change)

        # ── 外观 ──────────────────────────────────────────────────────────────
        _SectionLabel(scroll, self.i18n.get("appearance"))
        app_card = _Card(scroll)
        ab = app_card

        self.lang_var        = ctk.StringVar(value=self.config.get("language", "zh"))
        self.size_var        = ctk.IntVar(value=self.clock_config.get("font_size", 9))
        self.date_var        = ctk.BooleanVar(value=self.clock_config.get("show_date", True))
        raw_fc = self.clock_config.get("font_color", "system")
        self.font_color_mode  = ctk.StringVar(value="system" if raw_fc == "system" else "custom")
        self.font_color_value = ctk.StringVar(value=raw_fc if raw_fc != "system" else "#FFFFFF")
        raw_bc = self.clock_config.get("bg_color", "system")
        self.bg_color_mode  = ctk.StringVar(value="system" if raw_bc == "system" else "custom")
        self.bg_color_value = ctk.StringVar(value=raw_bc if raw_bc != "system" else "#000000")

        # 语言
        r_lang = _Row(ab, self.i18n.get("language_label"))
        self._lang_seg = ctk.CTkSegmentedButton(
            r_lang.right, values=["中文", "EN"],
            command=self._on_seg_lang,
            width=100, height=26,
            fg_color=CARD2,
            selected_color=SW_ON,
            selected_hover_color=SW_ON,
            unselected_color=CARD2,
            unselected_hover_color=HOVER,
            text_color=TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self._lang_seg.pack()
        self._lang_seg.set("中文" if self.lang_var.get() == "zh" else "EN")
        _Sep(ab)

        # Windows 区域格式；关闭后兼容原有自定义格式。
        self.system_format_var = ctk.BooleanVar(
            value=self.clock_config.get("format_style", "windows") == "windows")
        r_format = _Row(ab, self.i18n.get("system_format_label"))
        _TechToggle(r_format.right, self.system_format_var, self._fire_preview).pack()
        _Sep(ab)

        # 字体大小
        r_sz = _Row(ab, self.i18n.get("font_size_label"))
        sz = ctk.CTkFrame(r_sz.right, fg_color=CARD, corner_radius=0)
        sz.pack()
        ctk.CTkButton(sz, text="−", width=26, height=26, corner_radius=5,
                      fg_color=CARD2, hover_color=HOVER, text_color=TEXT,
                      font=ctk.CTkFont(size=13),
                      command=lambda: self._adj_size(-1)).pack(side="left", padx=(0, 4))
        ctk.CTkLabel(sz, textvariable=self.size_var, width=26,
                     text_color=TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
                     ).pack(side="left")
        ctk.CTkButton(sz, text="+", width=26, height=26, corner_radius=5,
                      fg_color=CARD2, hover_color=HOVER, text_color=TEXT,
                      font=ctk.CTkFont(size=13),
                      command=lambda: self._adj_size(1)).pack(side="left", padx=(4, 0))
        _Sep(ab)

        # 显示日期
        r_date = _Row(ab, self.i18n.get("show_date_label"))
        self._date_sw = _TechToggle(r_date.right, self.date_var, command=self._fire_preview)
        self._date_sw.pack()
        _Sep(ab)

        # 文字颜色
        r_fc = _Row(ab, self.i18n.get("font_color_row"))
        self._build_color_row(
            r_fc.right, self.font_color_mode, self.font_color_value,
            self._pick_font_color, is_bg=False)
        _Sep(ab)

        # 背景颜色
        r_bc = _Row(ab, self.i18n.get("bg_color_row"))
        self._build_color_row(
            r_bc.right, self.bg_color_mode, self.bg_color_value,
            self._pick_bg_color, is_bg=True)

        # ── 系统 ──────────────────────────────────────────────────────────────
        _SectionLabel(scroll, self.i18n.get("system_section"))
        sys_card = _Card(scroll)
        self.auto_var = ctk.BooleanVar(value=self.config.get("autostart", False))
        r_auto = _Row(sys_card, self.i18n.get("autostart_label"))
        _TechToggle(r_auto.right, self.auto_var, command=self._fire_preview).pack()

        # ── 按钮 ──────────────────────────────────────────────────────────────
        ctk.CTkFrame(scroll, height=14, fg_color=BG,
                     corner_radius=0).pack()
        btn_row = ctk.CTkFrame(scroll, fg_color=BG, corner_radius=0)
        btn_row.pack(fill="x", padx=20, pady=(0, 24))
        ctk.CTkButton(
            btn_row, text=self.i18n.get("cancel"),
            width=108, height=34, corner_radius=7,
            fg_color=CARD2, hover_color=HOVER,
            text_color=SUB, border_width=1, border_color=BORDER,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._on_close_window,
        ).pack(side="left")
        ctk.CTkButton(
            btn_row, text=self.i18n.get("save_apply"),
            width=136, height=34, corner_radius=7,
            fg_color=CARD2, hover_color=SEL_BG,
            text_color=TEXT, border_width=1, border_color=SUB,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._save,
        ).pack(side="right")

        # ── 支持作者（底部亮色按钮）───────────────────────────────────────────
        _SectionLabel(scroll, self.i18n.get("support_section"))
        support_card = _Card(scroll)
        support_row = ctk.CTkFrame(support_card, fg_color=CARD, corner_radius=0)
        support_row.pack(fill="x", padx=12, pady=10)

        ctk.CTkButton(
            support_row,
            text=self.i18n.get("sponsor_github"),
            height=34,
            corner_radius=8,
            fg_color="#FF4FA3",
            hover_color="#FF2F91",
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=lambda: self._open_support_url(GITHUB_SPONSOR_URL),
        ).pack(fill="x")

        ctk.CTkButton(
            support_row,
            text=self.i18n.get("sponsor_coffee"),
            height=34,
            corner_radius=8,
            fg_color="#FFDD00",
            hover_color="#FFD000",
            text_color="#1B1B1F",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=lambda: self._open_support_url(BUY_ME_A_COFFEE_URL),
        ).pack(fill="x", pady=(8, 0))

        # Trace
        for v in (self.size_var, self.date_var, self.lang_var,
                  self.font_color_mode, self.bg_color_mode,
                  self.font_color_value, self.bg_color_value):
            v.trace_add("write", lambda *_: self._fire_preview())

    # ── 颜色选色列 ─────────────────────────────────────────────────────────────
    def _build_color_row(self, parent, mode_var, value_var, pick_cb, is_bg=False):
        # 增加图标，强化「自动 / 手动」的视觉区别
        lbl_auto   = "⚡ " + self.i18n.get("color_auto")
        lbl_custom = "🎨 " + self.i18n.get("color_custom")

        # 使用 transparent 背景确保对齐
        wrap = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
        wrap.pack(side="right")

        seg = ctk.CTkSegmentedButton(
            wrap, values=[lbl_auto, lbl_custom],
            command=lambda v: (
                mode_var.set("system" if v == lbl_auto else "custom"),
                self._fire_preview()),
            width=140, height=28,
            fg_color=CARD2,
            selected_color=SW_ON,
            selected_hover_color="#00A892",
            unselected_color=CARD2,
            unselected_hover_color=HOVER,
            text_color=TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        )
        seg.pack(side="left", padx=(0, 8))

        def _get_lbl():
            return lbl_auto if mode_var.get() == "system" else lbl_custom

        seg.set(_get_lbl())
        mode_var.trace_add("write", lambda *_: seg.set(_get_lbl()))

        dot = ctk.CTkButton(
            wrap, text="", width=24, height=24, corner_radius=4,
            fg_color=CARD2, hover_color=HOVER,
            border_width=1, border_color=BORDER,
            command=pick_cb,
        )
        dot.pack(side="left")

        def _sync(*_):
            from utils import sample_taskbar_color, get_system_theme
            mode = mode_var.get()
            if mode == "custom":
                c = value_var.get()
                dot.configure(fg_color=c if isinstance(c, str) and c.startswith("#") else CARD2)
            else:
                # 自动模式下，反映真实获取的颜色
                if is_bg:
                    sampled = sample_taskbar_color()
                    dot.configure(fg_color=sampled if sampled else CARD2)
                else:
                    fg, _ = get_system_theme()
                    dot.configure(fg_color=fg if fg else TEXT)
                    
        value_var.trace_add("write", _sync)
        mode_var.trace_add("write",  _sync)
        _sync()
        # 定期刷新自动模式的色块
        parent.after(5000, _sync)

    def _on_tz_change(self, _event=None):
        self._update_target_time()
        self._fire_preview()

    # ── 其他控件逻辑 ───────────────────────────────────────────────────────────
    def _adj_size(self, d: int):
        self.size_var.set(max(6, min(24, self.size_var.get() + d)))

    def _on_seg_lang(self, value):
        new_lang = "zh" if value == "中文" else "en"
        # 先同步到目前设置，避免重建 UI 后语言状态回弹
        self.config["language"] = new_lang
        self.lang_var.set(new_lang)
        self.i18n = I18n(new_lang)
        self._reload_timezone_data()
        self.root.title(self.i18n.get("clock_settings"))

        # 语言切换后重建 UI，确保所有标签即时更新
        snapshot = {
            "tz_display": self.tz_display_var.get() if hasattr(self, "tz_display_var") else "",
            "size": self.size_var.get() if hasattr(self, "size_var") else 9,
            "show_date": self.date_var.get() if hasattr(self, "date_var") else True,
            "system_format": self.system_format_var.get(),
            "font_color_mode": self.font_color_mode.get() if hasattr(self, "font_color_mode") else "system",
            "font_color_value": self.font_color_value.get() if hasattr(self, "font_color_value") else "#FFFFFF",
            "bg_color_mode": self.bg_color_mode.get() if hasattr(self, "bg_color_mode") else "system",
            "bg_color_value": self.bg_color_value.get() if hasattr(self, "bg_color_value") else "#000000",
            "autostart": self.auto_var.get() if hasattr(self, "auto_var") else False,
        }

        for child in self.root.winfo_children():
            child.destroy()
        self._build_ui()

        # 还原用户当前值（避免重建后被重置）
        self.size_var.set(snapshot["size"])
        self.date_var.set(snapshot["show_date"])
        self.system_format_var.set(snapshot["system_format"])
        self.font_color_mode.set(snapshot["font_color_mode"])
        self.font_color_value.set(snapshot["font_color_value"])
        self.bg_color_mode.set(snapshot["bg_color_mode"])
        self.bg_color_value.set(snapshot["bg_color_value"])
        self.auto_var.set(snapshot["autostart"])
        if snapshot["tz_display"] in self.tz_displays_all:
            self.tz_display_var.set(snapshot["tz_display"])
        self.lang_var.set(new_lang)
        if hasattr(self, "_lang_seg"):
            self._lang_seg.set("中文" if new_lang == "zh" else "EN")

        self._update_target_time()
        self._fire_preview()

    # ── 内部逻辑与事件 ───────────────────────────────────────────────────────────
    def _pick_font_color(self):
        self._pick_color(self.font_color_value, self.font_color_mode, self.i18n.get("choose_font_color"))

    def _pick_bg_color(self):
        self._pick_color(self.bg_color_value, self.bg_color_mode, self.i18n.get("choose_bg_color"))

    def _pick_color(self, value_var, mode_var, title=""):
        mode_var.set("custom")
        cur = value_var.get()
        if not (isinstance(cur, str) and cur.startswith("#")):
            cur = "#FFFFFF"
        result = colorchooser.askcolor(
            title=title, initialcolor=cur, parent=self.root)[1]
        if result:
            value_var.set(result)
            self._fire_preview()

    def _open_support_url(self, url: str):
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _tick(self):
        if self._closed:
            return
        try:
            now_local = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            self.local_time_label.configure(
                text=f"{self.i18n.get('local_time')} {now_local}")
            self._update_target_time()
        except Exception:
            pass
        self._update_timer = self.root.after(1000, self._tick)

    def _update_target_time(self):
        dv = self.tz_display_var.get()
        try:
            idx = self.tz_displays_all.index(dv)
            tz  = self.tz_names_all[idx]
            config = self._get_current_clock_cfg()
            time_text, date_text = format_clock(
                get_current_time_in_tz(tz), config, self.config.get("language", "zh"))
            self.target_time_label.configure(
                text=f"{time_text}\n{date_text}" if config["show_date"] else time_text)
            self.target_tz_label.configure(text=tz)
        except Exception:
            self.target_time_label.configure(text="--:--:--")
            self.target_tz_label.configure(text="")

    def _get_current_clock_cfg(self):
        dv = self.tz_display_var.get()
        try:
            tz = self.tz_names_all[self.tz_displays_all.index(dv)]
        except ValueError:
            tz = self.clock_config.get("target_timezone", "Asia/Shanghai")
        return {
            "target_timezone": tz,
            "format_style": "windows" if self.system_format_var.get() else "custom",
            "font_size":  self.size_var.get(),
            "show_date":  self.date_var.get(),
            "font_color": ("system" if self.font_color_mode.get() == "system"
                           else self.font_color_value.get()),
            "bg_color":   ("system" if self.bg_color_mode.get()   == "system"
                           else self.bg_color_value.get()),
            "font_family":  self.clock_config.get("font_family", "Segoe UI"),
            "time_format":  self.clock_config.get("time_format", "%H:%M"),
            "date_format":  self.clock_config.get("date_format", "%Y/%m/%d"),
            "position":     self.clock_config.get("position",    "overlay_taskbar"),
        }

    def _fire_preview(self, *_):
        if self._closed:
            return

        # 1. 更新主程序预览 (Overlay Window)
        if self.on_preview:
            try:
                tmp = copy.deepcopy(self.config)
                tmp["clocks"][self.clock_idx] = self._get_current_clock_cfg()
                self.on_preview(tmp)
            except Exception:
                pass

        # 2. 更新设置窗口内部的「预览时钟」样式
        from utils import sample_taskbar_color, get_system_theme
        
        # 决定背景色
        if self.bg_color_mode.get() == "system":
            bg = sample_taskbar_color()
        else:
            bg = self.bg_color_value.get()
        
        # 决定文字色
        if self.font_color_mode.get() == "system":
            fg, _ = get_system_theme()
        else:
            fg = self.font_color_value.get()

        # 应用到预览组件
        if hasattr(self, 'target_time_label'):
            self.target_time_label.configure(text_color=fg)
        if hasattr(self, 'local_time_label'):
            self.local_time_label.configure(text_color=fg)
        if hasattr(self, 'target_tz_label'):
            self.target_tz_label.configure(text_color=fg)
            
        if hasattr(self, 'preview_frame'):
            # 视觉修正：当背景非常亮时，加上边框以避免「视觉黑洞/白洞」感
            is_very_light = False
            if bg and bg.startswith("#"):
                try:
                    r = int(bg[1:3], 16)
                    g = int(bg[3:5], 16)
                    b = int(bg[5:7], 16)
                    if (r*0.299 + g*0.587 + b*0.114) > 200:
                        is_very_light = True
                except: pass

            self.preview_frame.configure(
                fg_color=bg if bg else CARD,
                border_width=1 if is_very_light else 0,
                border_color="#444444"
            )

    def _save(self):
        self.config["language"]  = self.lang_var.get()
        self.config["autostart"] = self.auto_var.get()
        self.config["clocks"][self.clock_idx] = self._get_current_clock_cfg()
        set_autostart(self.config["autostart"])
        self.on_save(self.config)
        self._close_clean()

    def _on_close_window(self):
        if self.on_close is not None:
            self.on_close()
        self._close_clean()

    def _close_clean(self, saved=False):
        self._closed = True
        if self._update_timer:
            try:
                self.root.after_cancel(self._update_timer)
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.focus_force()
        if self.parent is None:
            self.root.mainloop()
