"""用目标时区的日期时间应用 Windows 区域格式，不修改系统时钟或时区。"""
import ctypes
from ctypes import wintypes


class SYSTEMTIME(ctypes.Structure):
    _fields_ = [(name, wintypes.WORD) for name in (
        "year", "month", "weekday", "day", "hour", "minute", "second", "milliseconds"
    )]


def _windows_format(now, date=False):
    value = SYSTEMTIME(now.year, now.month, (now.weekday() + 1) % 7,
                       now.day, now.hour, now.minute, now.second, 0)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    name = "GetDateFormatEx" if date else "GetTimeFormatEx"
    function = getattr(kernel32, name)
    args = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(SYSTEMTIME),
            wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_int]
    if date:
        args.append(wintypes.LPCWSTR)
    function.argtypes = args
    function.restype = ctypes.c_int
    # DATE_SHORTDATE / TIME_NOSECONDS。None 使用当前用户的区域设置和自定义格式。
    flags = 1 if date else 2
    suffix = (None,) if date else ()
    size = function(None, flags, ctypes.byref(value), None, None, 0, *suffix)
    if not size:
        raise ctypes.WinError(ctypes.get_last_error())
    buffer = ctypes.create_unicode_buffer(size)
    if not function(None, flags, ctypes.byref(value), None, buffer, size, *suffix):
        raise ctypes.WinError(ctypes.get_last_error())
    return buffer.value


def format_clock(now, config, language="zh"):
    """返回时间、日期两行；Windows 格式保留系统的 12/24 小时制和日期顺序。"""
    if config.get("format_style", "windows") == "windows":
        try:
            return _windows_format(now), _windows_format(now, date=True)
        except (AttributeError, OSError):
            return now.strftime("%H:%M"), f"{now.year}/{now.month}/{now.day}"
    time_text = now.strftime(config.get("time_format", "%H:%M"))
    if language == "zh":
        time_text = time_text.replace("AM", "上午").replace("PM", "下午")
    return time_text, now.strftime(config.get("date_format", "%Y/%m/%d"))
