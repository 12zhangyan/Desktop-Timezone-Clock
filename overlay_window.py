"""桌面时钟 overlay：覆盖于 Windows 任务栏原生时钟位置上方。

Windows 10 嵌入 TrayClockWClass；Windows 11 查询 XAML 时钟区域后精确覆盖。
时钟随任务栏显示、隐藏和缩放，点击事件由 Tkinter 处理。
"""
import time
import tkinter as tk
import win32gui
import win32con
import win32api

from timezone_utils import get_current_time_in_tz
from clock_format import format_clock
from taskbar_clock import find_modern_clock_rect
from utils import get_system_theme, sample_taskbar_color
from calendar_popup import CalendarPopup


def _find_tray_clock_window():
    shell_tray = win32gui.FindWindow("Shell_TrayWnd", None)
    if not shell_tray:
        return 0
    tray_notify = win32gui.FindWindowEx(shell_tray, 0, "TrayNotifyWnd", None)
    if tray_notify:
        clk = win32gui.FindWindowEx(tray_notify, 0, "TrayClockWClass", None)
        if clk:
            return clk
    clocks = []
    def _cb(hwnd, acc):
        try:
            if win32gui.GetClassName(hwnd) == "TrayClockWClass":
                acc.append(hwnd)
        except Exception:
            pass
        return True
    win32gui.EnumChildWindows(shell_tray, _cb, clocks)
    return clocks[0] if clocks else 0


def _embed_tk_in_native_parent(hwnd, parent_hwnd, w, h, x=0, y=0):
    """按 SetParent 要求先设置子窗口样式，再挂到任务栏。"""
    previous_style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    try:
        style = (previous_style & ~win32con.WS_POPUP) | win32con.WS_CHILD
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
        win32gui.SetParent(hwnd, parent_hwnd)
        win32gui.SetWindowPos(
            hwnd, win32con.HWND_TOP, x, y, w, h,
            win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW | win32con.SWP_FRAMECHANGED,
        )
        return True
    except Exception as error:
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, previous_style)
        print(f"[overlay] embed failed: {error}")
        return False


def _tray_clock_client_size(clock_wnd):
    """使用父窗口 *客户区* 宽高，与我们覆盖的区域一致，避免边界裁切与点击偏位。"""
    try:
        l, t, r, b = win32gui.GetClientRect(clock_wnd)
        w = max(r - l, 1)
        h = max(b - t, 1)
        return w, h
    except Exception:
        left, top, right, bottom = win32gui.GetWindowRect(clock_wnd)
        return max(right - left, 1), max(bottom - top, 1)


class ClockOverlay:
    def __init__(self, clock_config, global_config, on_open_settings=None):
        self.config = clock_config.copy()
        self.global_config = global_config
        self.on_open_settings = on_open_settings
        self.root = tk.Tk()

        self.sys_fg, self.sys_bg = get_system_theme()
        self._calendar_popup = None
        self._single_click_job = None
        self._last_click_time  = 0.0   # 用于双击计时（不依赖 WM_LBUTTONDBLCLK）
        self._embedded = False       # 是否已完成 SetParent 嵌入
        self._modern_clock = False
        self._clock_rect = None
        self._clock_wnd = 0          # TrayClockWClass hwnd 快取

        bg = self._resolve_bg_color()
        fg = self._resolve_font_color()
        print(f"[overlay] init  bg={bg}  fg={fg}  tz={self.config.get('target_timezone')}")

        self.root.geometry("1x1-10000-10000")  # 初始将窗口定位于极远的屏幕外，避免在 (0,0) 处短暂映射
        self.root.overrideredirect(True)
        # 移除起始的 -topmost 属性，避免 DWM 在 (0,0) 留下置顶点击穿透与拦截阴影。
        # 置顶状态将仅在 fallback（非嵌入模式）中透过 Win32 HWND_TOPMOST 或 attributes("-topmost") 启用。
        self.root.config(bg=bg, borderwidth=0, highlightthickness=0)

        self.label = tk.Label(
            self.root,
            text="",
            font=(self.config["font_family"], self.config["font_size"]),
            fg=fg,
            bg=bg,
            anchor="e",
            justify="right",
            padx=4,
            pady=0,
            borderwidth=0,
            highlightthickness=0,
        )
        self.label.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 只绑 <Button-1>，内部用时间差区分单/双击（整面积由 label 覆盖，避免重复绑定）
        self.label.bind("<Button-1>", self._on_click_raw)

        # 先让 Tk 建好窗口 (HWND 必须存在才能呼叫 win32 API)
        self.root.update_idletasks()
        self._hwnd = win32gui.GetParent(self.root.winfo_id()) or self.root.winfo_id()

        # 设置基本样式（不启用 layered，避免 DWM Z-order 问题）
        self._apply_base_styles()

        # 尝试嵌入任务栏
        self._try_embed()

        self.update_clock()
        self.root.update()
        self.sync_theme()
        self.force_topmost()
        print(f"[overlay] ready  embedded={self._embedded}  geometry={self.root.geometry()}")

    # ------------------------------------------------------------------ #
    #  EMBED INTO TASKBAR                                                  #
    # ------------------------------------------------------------------ #

    def _apply_base_styles(self):
        """设置 WS_EX_NOACTIVATE（不抢 focus）。不加 WS_EX_LAYERED 以避免 Z-order 问题。"""
        hwnd = self._hwnd
        ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        ex |= win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex)

        bg = self._resolve_bg_color()
        self.root.config(bg=bg, borderwidth=0, highlightthickness=0)
        self.label.config(
            bg=bg, fg=self._resolve_font_color(),
            borderwidth=0, highlightthickness=0,
        )

    def _try_embed(self):
        """Windows 10 嵌入原生窗口；Windows 11 覆盖 UIA 返回的时钟矩形。"""
        clock_wnd = _find_tray_clock_window()
        self._modern_clock = not bool(clock_wnd)
        if not clock_wnd:
            self._clock_wnd = win32gui.FindWindow("Shell_TrayWnd", None)
            self.position_overlay()
            return
        self._clock_wnd = clock_wnd
        w, h = _tray_clock_client_size(clock_wnd)
        self.root.deiconify()
        self.root.geometry(f"{w}x{h}+0+0")
        self.root.update_idletasks()
        self._embedded = _embed_tk_in_native_parent(self._hwnd, clock_wnd, w, h)
        if self._embedded:
            print(f"[overlay] embedded size={w}x{h}")
        else:
            self.root.withdraw()

    def force_topmost(self):
        """跟随任务栏布局；全屏应用或任务栏隐藏时收起 Windows 11 覆盖窗口。"""
        try:
            if self._clock_wnd and not win32gui.IsWindow(self._clock_wnd):
                self._embedded = False
                self._clock_wnd = 0
            if not self._clock_wnd:
                self._try_embed()
            else:
                self.position_overlay()
        except Exception as error:
            print(f"[overlay] position error: {error}")
        self.root.after(500, self.force_topmost)

    def _fullscreen_covers_taskbar(self):
        foreground = win32gui.GetForegroundWindow()
        if not foreground or foreground in (self._hwnd, self._clock_wnd):
            return False
        if win32gui.GetClassName(foreground) in ("Progman", "WorkerW"):
            return False
        monitor = win32api.MonitorFromWindow(self._clock_wnd, win32con.MONITOR_DEFAULTTONEAREST)
        left, top, right, bottom = win32api.GetMonitorInfo(monitor)["Monitor"]
        fl, ft, fr, fb = win32gui.GetWindowRect(foreground)
        return fl <= left and ft <= top and fr >= right and fb >= bottom

    def sync_theme(self):
        new_fg, new_bg = get_system_theme()
        if new_fg != self.sys_fg or new_bg != self.sys_bg:
            self.sys_fg = new_fg
            self.sys_bg = new_bg
            self._apply_base_styles()
        self.root.after(10000, self.sync_theme)

    # ------------------------------------------------------------------ #
    #  COLOR HELPERS                                                       #
    # ------------------------------------------------------------------ #

    def _resolve_font_color(self):
        v = self.config.get("font_color", "system")
        if v in ("system", "auto", None, ""):
            return self.sys_fg if self.sys_fg in ("white", "black") or (
                isinstance(self.sys_fg, str) and self.sys_fg.startswith("#")
            ) else "white"
        return v

    def _resolve_bg_color(self):
        v = self.config.get("bg_color", "system")
        if v in ("system", "auto", None, ""):
            sampled = sample_taskbar_color()
            if sampled:
                # 这里更新 sys_bg 和 sys_fg，确保字体颜色能即时跟随背景采样更新
                self.sys_bg = sampled
                from utils import get_color_brightness
                brightness = get_color_brightness(sampled)
                self.sys_fg = "black" if brightness > 140 else "white"
                return sampled
            return self.sys_bg if isinstance(self.sys_bg, str) and self.sys_bg.startswith(
                "#") else "#000000"
        return self._norm(v)

    def _norm(self, value):
        if isinstance(value, str) and len(value) == 7 and value.startswith("#"):
            try:
                int(value[1:], 16)
                return value
            except ValueError:
                pass
        return "#000000"

    def _current_language(self):
        try:
            return str(self.global_config.get("language", "zh")).lower()
        except Exception:
            return "zh"

    # ------------------------------------------------------------------ #
    #  CLICK → CALENDAR POPUP                                              #
    # ------------------------------------------------------------------ #

    # ── 单击 / 双击侦测（纯 <Button-1>，在嵌入子窗口中最可靠）─────────────────

    _DBLCLICK_MS = 450   # 双击间隔门槛（ms），略宽以符合一般操作节奏

    def _on_click_raw(self, event=None):
        """所有点击都从这里进入：用时间差区分单击 / 双击。"""
        now = time.time()
        gap = (now - self._last_click_time) * 1000  # ms
        self._last_click_time = now

        if gap < self._DBLCLICK_MS:
            # ── 双击：取消延迟的单击，改为开设置 ──────────────────────────
            self._last_click_time = 0.0   # 重置，防止第三次点击被视为双击
            if self._single_click_job is not None:
                try:
                    self.root.after_cancel(self._single_click_job)
                except Exception:
                    pass
                self._single_click_job = None
            # print("[overlay] double-click → open settings")
            if callable(self.on_open_settings):
                self.root.after(0, self.on_open_settings)
        else:
            # ── 单击：延迟执行，给双击留时间取消 ──────────────────────────
            if self._single_click_job is not None:
                try:
                    self.root.after_cancel(self._single_click_job)
                except Exception:
                    pass
            self._single_click_job = self.root.after(
                self._DBLCLICK_MS, self._do_single_click)
        return "break"

    def _do_single_click(self):
        self._single_click_job = None
        # print("[overlay] single click → toggle calendar")
        self.toggle_calendar()

    def toggle_calendar(self):
        """供 overlay 单击与托盘单击共用：切换日历开/关。"""
        try:
            inst = CalendarPopup._instance

            if inst is not None and getattr(inst, "_closed", True):
                CalendarPopup._instance = None
                self._calendar_popup = None
                inst = None

            if inst is not None:
                try:
                    inst.close()
                except Exception:
                    pass
                CalendarPopup._instance = None
                self._calendar_popup = None
                print("[overlay] popup closed (toggle)")
                return

            tz_name  = self.config.get("target_timezone", "Asia/Shanghai")
            language = self.global_config.get("language", "zh")
            self._calendar_popup = CalendarPopup(
                parent=self.root, tz_name=tz_name, language=language)
            print("[overlay] popup created")
        except Exception as e:
            print(f"[overlay] on_click error: {e}")
            CalendarPopup._instance = None

    # ------------------------------------------------------------------ #
    #  CLOCK UPDATE                                                        #
    # ------------------------------------------------------------------ #

    def update_clock(self):
        tz_name = self.config.get("target_timezone", "Asia/Shanghai")
        now = get_current_time_in_tz(tz_name)

        time_str, date_str = format_clock(now, self.config, self._current_language())
        text = f"{time_str}\n{date_str}" if self.config.get("show_date", True) else time_str
        self.label.config(text=text)

        self.root.after(1000, self.update_clock)

    # ------------------------------------------------------------------ #
    #  POSITION (公开，供 apply_window_styles 呼叫)                         #
    # ------------------------------------------------------------------ #

    def position_overlay(self):
        """使用实际像素矩形，避免固定坐标偏移和覆盖相邻托盘按钮。"""
        if not self._clock_wnd or not win32gui.IsWindow(self._clock_wnd):
            return
        if self._modern_clock:
            rect = find_modern_clock_rect(self._clock_wnd)
            if (not rect or not win32gui.IsWindowVisible(self._clock_wnd)
                    or self._fullscreen_covers_taskbar()):
                self.root.withdraw()
                return
            left, top, right, bottom = rect
            # 自动隐藏时任务栏可能只剩 1～2 像素，不能将整个时钟浮在屏幕上。
            monitor = win32api.MonitorFromWindow(self._clock_wnd, win32con.MONITOR_DEFAULTTONEAREST)
            ml, mt, mr, mb = win32api.GetMonitorInfo(monitor)["Monitor"]
            if left < ml or top < mt or right > mr or bottom > mb:
                self.root.withdraw()
                return
            self._clock_rect = rect
            w, h = right - left, bottom - top
            geometry = f"{w}x{h}{left:+d}{top:+d}"
            if self.root.state() == "withdrawn":
                self.root.deiconify()
            if self.root.geometry() != geometry:
                self.root.geometry(geometry)
                self.root.update_idletasks()
            win32gui.SetWindowPos(
                self._hwnd, win32con.HWND_TOPMOST, left, top, w, h,
                win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
            )
        elif self._embedded:
            w, h = _tray_clock_client_size(self._clock_wnd)
            self.root.geometry(f"{w}x{h}+0+0")
            self.root.update_idletasks()
            win32gui.SetWindowPos(
                self._hwnd, win32con.HWND_TOP, 0, 0, w, h,
                win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
            )

    # ------------------------------------------------------------------ #
    #  CONFIG UPDATE                                                       #
    # ------------------------------------------------------------------ #

    def update_config(self, new_config):
        self.config = new_config.copy()
        self.sys_fg, self.sys_bg = get_system_theme()
        self.label.config(
            font=(self.config["font_family"], self.config["font_size"]),
            fg=self._resolve_font_color(),
            bg=self._resolve_bg_color(),
        )
        self.root.config(bg=self._resolve_bg_color())
        self.position_overlay()
        time_text, date_text = format_clock(
            get_current_time_in_tz(self.config.get("target_timezone", "Asia/Shanghai")),
            self.config, self._current_language())
        self.label.config(text=f"{time_text}\n{date_text}" if self.config.get("show_date", True) else time_text)

    def apply_window_styles(self):
        """供外部 update_config 呼叫的兼容方法。"""
        self.update_config(self.config)

    def run(self):
        self.root.mainloop()

    def close(self):
        try:
            if self._calendar_popup is not None:
                self._calendar_popup.close()
        except Exception:
            pass
        self.root.destroy()
