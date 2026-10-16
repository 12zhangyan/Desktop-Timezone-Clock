import winreg
import sys
import os
import win32event
import win32api
import win32con
import win32gui
import win32security
import winerror

APP_NAME = "DesktopTimezoneClock"
_mutex = None

def is_already_running():
    global _mutex
    sa = win32security.SECURITY_ATTRIBUTES()
    sa.bInheritHandle = 0
    _mutex = win32event.CreateMutex(sa, False, f"Global\\{APP_NAME}_Mutex")
    if win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS:
        return False
    try:
        import win32process
        our_pid = os.getpid()
        clock_wnd = win32gui.FindWindow("Shell_TrayWnd", None)
        if clock_wnd:
            children = []
            def _cb(hwnd, acc):
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid != our_pid:
                        acc.append(hwnd)
                except Exception:
                    pass
                return True
            win32gui.EnumChildWindows(clock_wnd, _cb, children)
            if children:
                return True
    except Exception:
        pass
    return False

def _get_dwm_accent_hex():
    # 尝试从 Windows 注册表获取 DWM 颜色 (ARGB 格式)
    try:
        import winreg
        # DWM 颜色通常比 StartColorMenu 更接近视觉上的任务栏颜色
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM")
        val, _ = winreg.QueryValueEx(key, "ColorizationColor")
        # val 是 0xAABBGGRR 或 0AARRGGBB，视版本而定。
        # 通常 DWM 会把 Accent 色与 Taskbar 混合。
        # 我们取后 6 位作为基础
        color_hex = f"#{val & 0xFFFFFF:06x}"
        return color_hex
    except Exception:
        return None

_taskbar_color_cache = {"color": None, "expiry": 0}

def sample_taskbar_color():
    """采样任务栏背景颜色（使用众数法，优先采样时钟周边区域）。增加快取以优化效能。"""
    global _taskbar_color_cache
    import time
    now = time.time()
    if _taskbar_color_cache["color"] and now < _taskbar_color_cache["expiry"]:
        return _taskbar_color_cache["color"]

    try:
        # 1. 优先尝试从注册表获取 DWM 核心颜色（最准确的主题色基础）
        import win32gui, win32api
        
        # 1. 定位任务栏与时钟
        shell_tray = win32gui.FindWindow("Shell_TrayWnd", None)
        target_wnd = 0
        if shell_tray:
            tray_notify = win32gui.FindWindowEx(shell_tray, 0, "TrayNotifyWnd", None)
            if tray_notify:
                target_wnd = win32gui.FindWindowEx(tray_notify, 0, "TrayClockWClass", None)
        
        if not target_wnd: target_wnd = shell_tray
        if not target_wnd: return "#202020"
            
        rect = win32gui.GetWindowRect(target_wnd)
        if target_wnd == shell_tray:
            from taskbar_clock import find_modern_clock_rect
            rect = find_modern_clock_rect(shell_tray) or rect
        taskbar_rect = win32gui.GetWindowRect(shell_tray)
        hdc = win32gui.GetDC(0)
        
        # 2. 多点采样 (避开边界与文字中心)
        # 由于已开启 DPI Awareness，这里获得的座标与 GetPixel 要求的物理像素一致
        # 在时钟外、任务栏内部取样，避免采到覆盖层本身而无法跟随主题变化。
        sample_points = [
            (max(taskbar_rect[0], rect[0] - dx), rect[1] + 2)
            for dx in (2, 4, 6, 8)
        ]

        from collections import Counter
        colors = []
        for x, y in sample_points:
            try:
                # 确保座标在主屏幕范围内
                p = win32gui.GetPixel(hdc, x, y)
                if p != -1:
                    colors.append(((p & 0xff), (p >> 8) & 0xff, (p >> 16) & 0xff))
            except: continue
        
        win32gui.ReleaseDC(0, hdc)
        
        if not colors: return "#202020"
        
        # 取众数
        most_common = Counter(colors).most_common(1)
        r, g, b = most_common[0][0]
        color_hex = f"#{r:02x}{g:02x}{b:02x}"
        
        _taskbar_color_cache = {"color": color_hex, "expiry": now + 5}
        return color_hex
        
    except Exception:
        return "#202020"

def sample_pixel(x, y):
    """采样指定屏幕座标的物理像素颜色。"""
    try:
        hdc = win32gui.GetDC(0)
        p = win32gui.GetPixel(hdc, int(x), int(y))
        win32gui.ReleaseDC(0, hdc)
        if p == -1: return "#000000"
        return f"#{p & 0xff:02x}{(p >> 8) & 0xff:02x}{(p >> 16) & 0xff:02x}"
    except Exception:
        return "#000000"

def get_color_brightness(hex_color: str) -> float:
    """计算 HEX 颜色的亮度 (0-255)。"""
    if not hex_color or not hex_color.startswith("#") or len(hex_color) != 7:
        return 0
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        return (r * 299 + g * 587 + b * 114) / 1000
    except ValueError:
        return 0

def get_system_theme():
    sampled = sample_taskbar_color()
    if sampled:
        brightness = get_color_brightness(sampled)
        fg = "black" if brightness > 140 else "white"
        return fg, sampled

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
        system_light, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
        color_prevalence, _ = winreg.QueryValueEx(key, "ColorPrevalence")
        winreg.CloseKey(key)
        if color_prevalence == 1:
            accent = _get_dwm_accent_hex()
            if accent:
                r = int(accent[1:3], 16)
                g = int(accent[3:5], 16)
                b = int(accent[5:7], 16)
                brightness = (r * 299 + g * 587 + b * 114) / 1000
                fg = "black" if brightness > 140 else "white"
                return fg, accent
        return ("white", "#000000") if system_light == 0 else ("black", "#FFFFFF")
    except Exception:
        return "white", "#000000"

def _find_tray_clock_window():
    shell_tray = win32gui.FindWindow("Shell_TrayWnd", None)
    if not shell_tray: return 0
    tray_notify = win32gui.FindWindowEx(shell_tray, 0, "TrayNotifyWnd", None)
    if tray_notify:
        clock_wnd = win32gui.FindWindowEx(tray_notify, 0, "TrayClockWClass", None)
        if clock_wnd: return clock_wnd
    clocks = []
    def find_clock(hwnd, acc):
        try:
            if win32gui.GetClassName(hwnd) == "TrayClockWClass": acc.append(hwnd)
        except Exception: pass
        return True
    win32gui.EnumChildWindows(shell_tray, find_clock, clocks)
    if clocks: return clocks[0]
    win32gui.EnumWindows(find_clock, clocks)
    return clocks[0] if clocks else 0

def _make_lparam(x, y):
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)

def trigger_win_calendar():
    try:
        clock_wnd = _find_tray_clock_window()
        if clock_wnd:
            left, top, right, bottom = win32gui.GetWindowRect(clock_wnd)
            cx, cy = (right - left) // 2, (bottom - top) // 2
            lp = _make_lparam(cx, cy)
            win32gui.PostMessage(clock_wnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
            win32gui.PostMessage(clock_wnd, win32con.WM_LBUTTONUP, 0, lp)
            return
        win32api.keybd_event(win32con.VK_LWIN, 0, 0, 0)
        win32api.keybd_event(ord("N"), 0, 0, 0)
        win32api.keybd_event(ord("N"), 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(win32con.VK_LWIN, 0, win32con.KEYEVENTF_KEYUP, 0)
    except Exception: pass

def set_autostart(enabled):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        if enabled:
            executable = sys.executable
            script_path = os.path.abspath(sys.argv[0])
            cmd = f'"{executable}" "{script_path}"' if script_path.endswith(".py") else f'"{script_path}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try: winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError: pass
        winreg.CloseKey(key)
        return True
    except Exception: return False

def is_autostart_enabled():
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, APP_NAME)
            enabled = True
        except FileNotFoundError: enabled = False
        winreg.CloseKey(key)
        return enabled
    except Exception: return False