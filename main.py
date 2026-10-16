import copy
import queue
import threading
import time
import tkinter as tk
import pystray
from pystray import _win32 as pystray_win32
from pystray._util import win32 as tray_win32
import win32con
from PIL import Image, ImageDraw
import sys
import ctypes

try:
    # 优先尝试 Windows 10 1703+ 的 Per-Monitor V2 DPI awareness
    # -4 代表 DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    try:
        # 尝试 Windows 8.1+ 的 Per-Monitor DPI awareness
        # 2 代表 PROCESS_PER_MONITOR_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            # 备用为 System DPI awareness
            # 1 代表 PROCESS_SYSTEM_DPI_AWARE
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

from config_manager import load_config, save_config
from overlay_window import ClockOverlay
from taskbar_clock import enumerate_taskbars
from settings_window import SettingsWindow

from i18n import I18n
from utils import is_already_running, is_autostart_enabled


class DesktopTrayIcon(pystray_win32.Icon):
    """自定义 Windows 托盘事件：单击 / 双击分流。"""
    _DBLCLICK_SEC = 0.35
    _WM_LBUTTONDBLCLK = getattr(win32con, "WM_LBUTTONDBLCLK", 0x0203)

    def __init__(self, *args, on_single_left_click=None, on_double_left_click=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_single_left_click = on_single_left_click
        self._on_double_left_click = on_double_left_click
        self._single_click_timer = None
        self._last_left_up_ts = 0.0

    def _cancel_single_timer(self):
        if self._single_click_timer is not None:
            self._single_click_timer.cancel()
            self._single_click_timer = None

    def _fire_single_click(self):
        self._single_click_timer = None
        if callable(self._on_single_left_click):
            self._on_single_left_click(self)
        else:
            self()

    def _fire_double_click(self):
        self._cancel_single_timer()
        if callable(self._on_double_left_click):
            self._on_double_left_click(self)

    def _on_notify(self, wparam, lparam):
        # Windows 可能送 WM_LBUTTONDBLCLK，也可能只送两次 WM_LBUTTONUP，两者都处理
        if lparam == self._WM_LBUTTONDBLCLK:
            self._fire_double_click()
            return
        if lparam == tray_win32.WM_LBUTTONUP:
            now = time.time()
            if now - self._last_left_up_ts <= self._DBLCLICK_SEC:
                self._last_left_up_ts = 0.0
                self._fire_double_click()
                return
            self._last_left_up_ts = now
            self._cancel_single_timer()
            self._single_click_timer = threading.Timer(self._DBLCLICK_SEC, self._fire_single_click)
            self._single_click_timer.daemon = True
            self._single_click_timer.start()
            return
        return super()._on_notify(wparam, lparam)


class DesktopClockApp:
    def __init__(self):
        if is_already_running():
            sys.exit(0)

        print("\n" + "="*40)
        print(">>> Desktop Timezone Clock v1.1.1 Starting...")
        
        self.config = load_config()
        
        # 同步开机启动状态与注册表 (解决安装时勾选自动启动但设置页未同步的问题)
        try:
            from utils import is_autostart_enabled
            registry_enabled = is_autostart_enabled()
            if self.config.get("autostart") != registry_enabled:
                self.config["autostart"] = registry_enabled
                save_config(self.config)
        except Exception:
            pass
        self.overlays = []
        self._overlay_by_taskbar = {}
        self._display_config = self.config
        self.root = None
        self._exiting = False
        self.tray_icon = None
        self._settings_win = None
        self._ui_actions = queue.Queue()
        self.i18n = I18n(self.config.get("language", "zh"))

    def _post_ui_action(self, fn):
        self._ui_actions.put(fn)

    def _drain_ui_actions(self):
        if self._exiting:
            return
        try:
            while True:
                fn = self._ui_actions.get_nowait()
                try:
                    fn()
                except Exception as e:
                    print(f"[ui] action error: {e}")
        except queue.Empty:
            pass
        if not self._exiting:
            self.root.after(50, self._drain_ui_actions)

    def create_tray_image(self):
        width, height = 64, 64
        image = Image.new('RGB', (width, height), color=(255, 255, 255))
        dc = ImageDraw.Draw(image)
        dc.ellipse([8, 8, 56, 56], outline=(0, 0, 0), width=4)
        dc.line([32, 32, 32, 16], fill=(0, 0, 0), width=4)
        dc.line([32, 32, 48, 32], fill=(0, 0, 0), width=4)
        return image

    # ------------------------------------------------------------------ #
    #  SETTINGS WINDOW                                                     #
    # ------------------------------------------------------------------ #

    def on_settings(self, icon, item):
        self._post_ui_action(self._open_settings_window)

    def _open_settings_window(self):
        # Prevent duplicate windows
        if self._settings_win is not None:
            try:
                if self._settings_win.root.winfo_exists():
                    self._settings_win.root.lift()
                    self._settings_win.root.focus_force()
                    return
            except Exception:
                pass
            self._settings_win = None

        parent = self.root

        def on_settings_closed():
            self._restore_config()
            self._settings_win = None

        self._settings_win = SettingsWindow(
            self.config,
            on_save_callback=self._on_settings_saved,
            on_preview_callback=self._preview_config,
            on_close_callback=on_settings_closed,
            parent=parent,
        )
        self._settings_win.run()

    def _on_settings_saved(self, new_config):
        self._settings_win = None
        self.update_config(new_config)

    def update_config(self, new_config):
        self.config = copy.deepcopy(new_config)
        self.i18n = I18n(self.config.get("language", "zh"))
        save_config(self.config)
        self._apply_config_to_overlays(self.config)

    def _preview_config(self, temp_config):
        self._apply_config_to_overlays(temp_config)

    def _restore_config(self):
        self._apply_config_to_overlays(self.config)

    def _apply_config_to_overlays(self, cfg):
        self._display_config = cfg
        self._sync_taskbars()
        for overlay in self.overlays:
            overlay.global_config = cfg
            overlay.update_config(cfg["clocks"][overlay.clock_index])

    def _sync_taskbars(self):
        """每个任务栏创建一组时钟；屏幕或 Explorer 变化时移除旧窗口并补齐。"""
        cfg = self._display_config
        desired = [(hwnd, index) for hwnd in enumerate_taskbars()
                   for index in range(len(cfg["clocks"]))]
        desired_set = set(desired)
        for key in list(self._overlay_by_taskbar):
            if key not in desired_set:
                self._overlay_by_taskbar.pop(key).close()
        for hwnd, index in desired:
            key = (hwnd, index)
            if key not in self._overlay_by_taskbar:
                self._overlay_by_taskbar[key] = ClockOverlay(
                    cfg["clocks"][index], cfg,
                    on_open_settings=self._open_settings_window,
                    taskbar_hwnd=hwnd, parent=self.root, clock_index=index,
                )
        self.overlays = [self._overlay_by_taskbar[key] for key in desired]

    def _refresh_taskbars(self):
        if self._exiting:
            return
        try:
            self._sync_taskbars()
        except Exception as error:
            print(f"[taskbar] refresh error: {error}")
        self.root.after(2000, self._refresh_taskbars)

    # ------------------------------------------------------------------ #
    #  TRAY                                                                #
    # ------------------------------------------------------------------ #

    def on_exit(self, icon, item=None):
        icon.stop()
        self._post_ui_action(self._shutdown)

    def _shutdown(self):
        self._exiting = True
        for overlay in self.overlays:
            overlay.close()
        self.overlays.clear()
        self._overlay_by_taskbar.clear()
        self.root.destroy()

    def _on_tray_single_click(self, icon):
        self._post_ui_action(self._toggle_first_calendar)

    def _toggle_first_calendar(self):
        if self.overlays:
            self.overlays[0].toggle_calendar()

    def _on_tray_double_click(self, icon):
        self._post_ui_action(self._open_settings_window)

    def run_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem(self.i18n.get("settings"),      self.on_settings),
            pystray.MenuItem(self.i18n.get("exit"),          self.on_exit),
        )
        self.tray_icon = DesktopTrayIcon(
            "DesktopClock",
            self.create_tray_image(),
            self.i18n.get("app_title"),
            menu,
            on_single_left_click=self._on_tray_single_click,
            on_double_left_click=self._on_tray_double_click,
        )
        self.tray_icon.run()

    # ------------------------------------------------------------------ #
    #  ENTRY POINT                                                         #
    # ------------------------------------------------------------------ #

    def run(self):
        # 控制根窗口不依赖任何屏幕；断开副屏或重启 Explorer 时保留事件循环。
        self.root = tk.Tk()
        self.root.withdraw()
        self._refresh_taskbars()
        self.root.after(50, self._drain_ui_actions)
        tray_thread = threading.Thread(target=self.run_tray, daemon=True)
        tray_thread.start()
        self.root.mainloop()


if __name__ == "__main__":
    app = DesktopClockApp()
    app.run()
