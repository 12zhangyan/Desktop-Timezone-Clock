"""定位 Windows 11 的 XAML 时钟，兼容没有 TrayClockWClass 的任务栏。

仅查询 Windows 自带的 UI Automation，不注入 Explorer，不需要新增依赖。
接口槽位对应 Windows SDK 的 UIAutomationClient.h。
"""
import ctypes
import re
import threading
import time
from ctypes import wintypes
from uuid import UUID

import win32gui

_POINTER = ctypes.c_void_p
_POINTER_OUT = ctypes.POINTER(_POINTER)


def _method(pointer, slot, *argtypes):
    vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(_POINTER))).contents
    return ctypes.WINFUNCTYPE(ctypes.c_long, _POINTER, *argtypes)(vtable[slot])


def _call(pointer, slot, argtypes, *args):
    result = _method(pointer, slot, *argtypes)(pointer, *args)
    if result < 0:
        raise OSError(f"UI Automation HRESULT: 0x{result & 0xffffffff:08x}")


def _release(pointer):
    if pointer:
        _method(pointer, 2)(pointer)


def _string_property(pointer, slot):
    value = _POINTER()
    _call(pointer, slot, (_POINTER_OUT,), ctypes.byref(value))
    try:
        return ctypes.wstring_at(value) if value else ""
    finally:
        oleaut32 = ctypes.WinDLL("oleaut32")
        oleaut32.SysFreeString.argtypes = [_POINTER]
        oleaut32.SysFreeString(value)


def _query_modern_clock_rect(taskbar_hwnd):
    """返回实际时钟的屏幕像素矩形；隐藏或无法识别时返回 None。"""
    ole32 = ctypes.OleDLL("ole32")
    ole32.CoInitializeEx.argtypes = [_POINTER, wintypes.DWORD]
    ole32.CoInitializeEx.restype = ctypes.c_long
    # Tk 主线程可能已初始化 COM；RPC_E_CHANGED_MODE 时沿用现有 apartment。
    try:
        initialized = ole32.CoInitializeEx(None, 0) in (0, 1)
    except OSError:
        initialized = False
    automation, root, condition, elements = (_POINTER() for _ in range(4))
    try:
        clsid = (ctypes.c_byte * 16).from_buffer_copy(
            UUID("ff48dba4-60ef-4201-aa87-54103eef594e").bytes_le)
        iid = (ctypes.c_byte * 16).from_buffer_copy(
            UUID("30cbe57d-d9d0-452a-ab13-7ac5ac4825ee").bytes_le)
        ole32.CoCreateInstance.argtypes = [_POINTER, _POINTER, wintypes.DWORD,
                                         _POINTER, _POINTER_OUT]
        ole32.CoCreateInstance(clsid, None, 1, iid, ctypes.byref(automation))
        _call(automation, 6, (wintypes.HWND, _POINTER_OUT),
              taskbar_hwnd, ctypes.byref(root))
        _call(automation, 21, (_POINTER_OUT,), ctypes.byref(condition))
        _call(root, 6, (ctypes.c_int, _POINTER, _POINTER_OUT),
              4, condition, ctypes.byref(elements))  # TreeScope_Descendants
        count = ctypes.c_int()
        _call(elements, 3, (ctypes.POINTER(ctypes.c_int),), ctypes.byref(count))
        for index in range(count.value):
            element = _POINTER()
            try:
                _call(elements, 4, (ctypes.c_int, _POINTER_OUT),
                      index, ctypes.byref(element))
                class_name = _string_property(element, 30)
                if class_name not in ("SystemTray.OmniButton", "SystemTray.DateTimeIcon"):
                    continue
                offscreen = wintypes.BOOL()
                _call(element, 38, (ctypes.POINTER(wintypes.BOOL),), ctypes.byref(offscreen))
                if offscreen.value:
                    continue
                name = _string_property(element, 23)
                # OmniButton 也可能用于其他系统按钮，仅接受含时间的时钟控件。
                if not re.search(r"\d{1,2}:\d{2}", name):
                    continue
                rect = wintypes.RECT()
                _call(element, 43, (ctypes.POINTER(wintypes.RECT),), ctypes.byref(rect))
                left, top, right, bottom = win32gui.GetWindowRect(taskbar_hwnd)
                if (left <= rect.left < rect.right <= right
                        and top <= rect.top < rect.bottom <= bottom):
                    return rect.left, rect.top, rect.right, rect.bottom
            finally:
                _release(element)
    except (OSError, ValueError):
        return None
    finally:
        for pointer in (elements, condition, root, automation):
            _release(pointer)
        if initialized:
            ole32.CoUninitialize()
    return None


_cache_lock = threading.Lock()
_clock_cache = {}


def find_modern_clock_rect(taskbar_hwnd):
    """异步查询并返回缓存，避免 UIA 遍历自身 Tk 子窗口时阻塞界面线程。"""
    if not taskbar_hwnd:
        return None
    with _cache_lock:
        cached = _clock_cache.setdefault(taskbar_hwnd, {
            "rect": None, "expires": 0, "running": False,
        })
        if not cached["running"] and time.monotonic() >= cached["expires"]:
            cached["running"] = True
            def refresh():
                rect = None
                try:
                    rect = _query_modern_clock_rect(taskbar_hwnd)
                finally:
                    with _cache_lock:
                        cached.update(rect=rect, expires=time.monotonic() + 2, running=False)
            threading.Thread(target=refresh, daemon=True, name="taskbar-clock-query").start()
        return cached["rect"]


def enumerate_taskbars():
    """枚举当前所有屏幕的任务栏，主任务栏排在前面。"""
    taskbars = []
    def visit(hwnd, unused):
        if win32gui.GetClassName(hwnd) in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
            taskbars.append(hwnd)
    win32gui.EnumWindows(visit, None)
    return sorted(taskbars, key=lambda hwnd: (
        win32gui.GetClassName(hwnd) != "Shell_TrayWnd",
        win32gui.GetWindowRect(hwnd)[:2],
    ))


def get_window_dpi(hwnd):
    """返回窗口所在屏幕的 DPI，避免多个 Tk 窗口共用主屏字体缩放。"""
    try:
        function = ctypes.WinDLL("user32").GetDpiForWindow
        function.argtypes = [wintypes.HWND]
        function.restype = wintypes.UINT
        return function(hwnd) or 96
    except (AttributeError, OSError):
        return 96
