import copy
import unittest
from unittest.mock import Mock, patch

import main
import taskbar_clock
from calendar_popup import CalendarPopup
from config_manager import DEFAULT_CONFIG
from overlay_window import ClockOverlay, _find_tray_clock_window


class MultiMonitorTests(unittest.TestCase):
    def app(self):
        app = main.DesktopClockApp.__new__(main.DesktopClockApp)
        app.config = copy.deepcopy(DEFAULT_CONFIG)
        app._display_config = app.config
        app._overlay_by_taskbar = {}
        app.overlays = []
        app.root = Mock()
        app._settings_win = None
        return app

    def test_all_taskbars_are_enumerated_with_primary_first(self):
        classes = {10: 'Shell_SecondaryTrayWnd', 20: 'NotATaskbar',
                   30: 'Shell_TrayWnd', 40: 'Shell_SecondaryTrayWnd'}
        rects = {10: (-1920, 1040, 0, 1080), 30: (0, 1040, 1920, 1080),
                 40: (1920, 1040, 3840, 1080)}
        def visit(callback, data):
            for hwnd in classes:
                callback(hwnd, data)
        with patch.object(taskbar_clock.win32gui, 'EnumWindows', side_effect=visit), \
                patch.object(taskbar_clock.win32gui, 'GetClassName', side_effect=classes.__getitem__), \
                patch.object(taskbar_clock.win32gui, 'GetWindowRect', side_effect=rects.__getitem__):
            self.assertEqual(taskbar_clock.enumerate_taskbars(), [30, 10, 40])

    def test_clock_discovery_stays_on_requested_secondary_taskbar(self):
        with patch('overlay_window.win32gui.FindWindow') as primary, \
                patch('overlay_window.win32gui.FindWindowEx', side_effect=[400, 500]) as find:
            self.assertEqual(_find_tray_clock_window(200), 500)
            self.assertEqual(find.call_args_list[0].args[0], 200)
            primary.assert_not_called()

    def test_connect_disconnect_and_explorer_restart_sync_windows(self):
        app = self.app()
        with patch('main.enumerate_taskbars', return_value=[100]) as taskbars, \
                patch('main.ClockOverlay') as factory:
            factory.side_effect = lambda *args, **kwargs: Mock(clock_index=kwargs['clock_index'])
            app._sync_taskbars()
            primary = app.overlays[0]
            taskbars.return_value = [100, 200]
            app._sync_taskbars()
            secondary = app.overlays[1]
            self.assertIs(app.overlays[0], primary)
            self.assertEqual(factory.call_args.kwargs['taskbar_hwnd'], 200)
            self.assertIs(factory.call_args.kwargs['parent'], app.root)
            app._sync_taskbars()
            self.assertEqual(factory.call_count, 2)
            taskbars.return_value = [100]
            app._sync_taskbars()
            secondary.close.assert_called_once()
            primary.close.assert_not_called()
            taskbars.return_value = []
            app._sync_taskbars()
            self.assertEqual(app.overlays, [])
            primary.close.assert_called_once()
            app.root.destroy.assert_not_called()
            taskbars.return_value = [300, 400]
            app._sync_taskbars()
            self.assertEqual(set(app._overlay_by_taskbar), {(300, 0), (400, 0)})

    def test_settings_apply_to_every_screen_with_correct_clock_index(self):
        app = self.app()
        app.config['clocks'].append(copy.deepcopy(app.config['clocks'][0]))
        with patch('main.enumerate_taskbars', return_value=[100, 200]), \
                patch('main.ClockOverlay') as factory:
            factory.side_effect = lambda *args, **kwargs: Mock(clock_index=kwargs['clock_index'])
            app._sync_taskbars()
            config = copy.deepcopy(app.config)
            config['clocks'][0]['font_size'] = 12
            config['clocks'][1]['target_timezone'] = 'America/New_York'
            app._apply_config_to_overlays(config)
            self.assertEqual(len(app.overlays), 4)
            for overlay in app.overlays:
                overlay.update_config.assert_called_once_with(config['clocks'][overlay.clock_index])
                self.assertIs(overlay.global_config, config)
            config['clocks'].pop()
            app._apply_config_to_overlays(config)
            self.assertEqual(set(app._overlay_by_taskbar), {(100, 0), (200, 0)})

    def test_each_screen_uses_its_own_dpi_font(self):
        overlay = ClockOverlay.__new__(ClockOverlay)
        overlay.config = {'font_family': 'Segoe UI', 'font_size': 9}
        overlay._hwnd = 42
        overlay._font_metrics = None
        overlay.label = Mock()
        with patch('overlay_window.get_window_dpi', side_effect=[120, 96]):
            overlay._update_font_for_dpi()
            self.assertEqual(overlay.label.config.call_args.kwargs['font'], ('Segoe UI', -15))
            overlay._update_font_for_dpi()
            self.assertEqual(overlay.label.config.call_args.kwargs['font'], ('Segoe UI', -12))

    def test_popup_uses_clicked_monitor_including_negative_coordinates(self):
        popup = CalendarPopup.__new__(CalendarPopup)
        popup._taskbar_wnd = 200
        popup._w, popup._h = 300, 400
        with patch('calendar_popup.win32api.MonitorFromWindow', return_value=77) as monitor, \
                patch('calendar_popup.win32api.GetMonitorInfo', return_value={'Work': (-1920, -1080, 0, -40)}):
            self.assertEqual(popup._calc_position(), (-308, -448))
            self.assertEqual(monitor.call_args.args[0], 200)

    def test_popup_and_overlay_move_using_absolute_win32_coordinates(self):
        popup = CalendarPopup.__new__(CalendarPopup)
        popup.root = Mock()
        popup.root.winfo_id.return_value = 50
        with patch('calendar_popup.win32gui.GetParent', return_value=60), \
                patch('calendar_popup.win32gui.SetWindowPos') as move:
            popup._move_to(-308, -448)
            self.assertEqual(move.call_args.args[2:4], (-308, -448))
            popup.root.geometry.assert_not_called()

        overlay = ClockOverlay.__new__(ClockOverlay)
        overlay._clock_wnd = 200
        overlay._hwnd = 60
        overlay._modern_clock = True
        overlay.root = Mock()
        overlay.root.winfo_width.return_value = 80
        overlay.root.winfo_height.return_value = 40
        overlay._fullscreen_covers_taskbar = Mock(return_value=False)
        overlay._update_font_for_dpi = Mock()
        with patch('overlay_window.win32gui.IsWindow', return_value=True), \
                patch('overlay_window.win32gui.IsWindowVisible', return_value=True), \
                patch('overlay_window.find_modern_clock_rect', return_value=(-88, -40, -8, 0)), \
                patch('overlay_window.win32api.MonitorFromWindow', return_value=77), \
                patch('overlay_window.win32api.GetMonitorInfo', return_value={'Monitor': (-1920, -1080, 0, 0)}), \
                patch('overlay_window.win32gui.SetWindowPos') as move:
            overlay.position_overlay()
            self.assertEqual(move.call_args.args[2:6], (-88, -40, 80, 40))
            overlay.root.geometry.assert_not_called()


if __name__ == '__main__':
    unittest.main()
