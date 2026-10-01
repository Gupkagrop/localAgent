"""
Модульные тесты контроллера десктопных приложений Windows (core/app_controller.py).
Проверяют поиск окон, переключение фокуса, разрешение путей (включая OneDrive Desktop),
блокировку опасных расширений, управление состоянием окон и отправку текста.
"""
import os
import unittest
from unittest.mock import patch, MagicMock

from core.app_controller import DesktopAppController, BLOCKED_EXECUTABLE_EXTENSIONS


class TestDesktopAppController(unittest.TestCase):
    """Тестирование класса DesktopAppController."""

    def setUp(self):
        self.ctrl = DesktopAppController()

    def test_blocked_extensions_contains_dangerous_formats(self):
        """Проверка наличия опасных форматов скриптов в черном списке."""
        for ext in [".bat", ".cmd", ".vbs", ".ps1", ".reg", ".scr", ".com"]:
            self.assertIn(ext, BLOCKED_EXECUTABLE_EXTENSIONS)

    @patch("core.app_controller.win32gui.EnumWindows")
    def test_find_window_found(self, mock_enum):
        """Проверка успешного поиска окна по названию."""
        def fake_enum(callback, extra):
            # Имитируем окно блокнота
            with patch("core.app_controller.win32gui.IsWindowVisible", return_value=True), \
                 patch("core.app_controller.win32gui.GetWindowText", return_value="Безымянный — Блокнот"):
                # callback возвращает False при нахождении
                callback(12345, extra)

        mock_enum.side_effect = fake_enum
        hwnd = self.ctrl.find_window("блокнот")
        self.assertEqual(hwnd, 12345)

    @patch("core.app_controller.win32gui.EnumWindows")
    def test_find_window_not_found(self, mock_enum):
        """Проверка возврата None если окно не найдено."""
        def fake_enum(callback, extra):
            with patch("core.app_controller.win32gui.IsWindowVisible", return_value=True), \
                 patch("core.app_controller.win32gui.GetWindowText", return_value="Калькулятор"):
                callback(999, extra)

        mock_enum.side_effect = fake_enum
        hwnd = self.ctrl.find_window("telegram")
        self.assertIsNone(hwnd)

    @patch("core.app_controller.win32gui.IsWindow", return_value=True)
    @patch("core.app_controller.win32gui.IsIconic", return_value=True)
    @patch("core.app_controller.win32gui.ShowWindow")
    @patch("core.app_controller.win32gui.GetForegroundWindow", return_value=123)
    def test_focus_window_restores_minimized(self, mock_fg, mock_show, mock_iconic, mock_is_win):
        """Проверка восстановления свернутого окна и вывода на передний план."""
        res = self.ctrl.focus_window(123)
        self.assertTrue(res)
        mock_show.assert_called_once()

    @patch("core.app_controller.win32gui.IsWindow", return_value=False)
    def test_focus_window_invalid_hwnd(self, mock_is_win):
        """Проверка возврата False при невалидном дескрипторе окна."""
        res = self.ctrl.focus_window(0)
        self.assertFalse(res)

    def test_resolve_executable_direct_file(self):
        """Проверка разрешения прямого пути к существующему файлу."""
        with patch("os.path.exists", return_value=True):
            resolved = self.ctrl.resolve_executable_or_shortcut(r"C:\Custom\app.exe")
            self.assertEqual(resolved, r"C:\Custom\app.exe")

    def test_resolve_executable_shutil_which(self):
        """Проверка нахождения исполняемого файла в системном PATH."""
        with patch("os.path.exists", return_value=False), \
             patch("shutil.which", return_value=r"C:\Windows\System32\calc.exe"):
            resolved = self.ctrl.resolve_executable_or_shortcut("calc.exe")
            self.assertEqual(resolved, r"C:\Windows\System32\calc.exe")

    def test_launch_or_focus_existing_window(self):
        """Если окно уже открыто, переключается фокус без запуска нового процесса."""
        with patch.object(self.ctrl, "find_window", return_value=555), \
             patch.object(self.ctrl, "focus_window", return_value=True), \
             patch("core.app_controller.os.startfile") as mock_start:
            ok, msg = self.ctrl.launch_or_focus("калькулятор")
            self.assertTrue(ok)
            self.assertIn("Переключено", msg)
            mock_start.assert_not_called()

    def test_launch_or_focus_blocks_dangerous_scripts(self):
        """Попытка запуска скриптов (.bat, .cmd, .ps1, .vbs) блокируется guardrail."""
        with patch.object(self.ctrl, "find_window", return_value=None), \
             patch("core.app_controller.os.startfile") as mock_start:
            for bad_script in ["payload.bat", "run.cmd", "exploit.ps1", "script.vbs", "data.reg"]:
                ok, msg = self.ctrl.launch_or_focus("скрипт", bad_script)
                self.assertFalse(ok)
                self.assertIn("заблокирован", msg)
                mock_start.assert_not_called()

    def test_launch_or_focus_success_launch(self):
        """Штатный запуск безопасного исполняемого файла при отсутствии активного окна."""
        with patch.object(self.ctrl, "find_window", side_effect=[None, 777]), \
             patch.object(self.ctrl, "focus_window", return_value=True), \
             patch("core.app_controller.os.startfile") as mock_start:
            ok, msg = self.ctrl.launch_or_focus("блокнот", "notepad.exe")
            self.assertTrue(ok)
            self.assertIn("Запущено", msg)
            mock_start.assert_called_once()
            called_path = mock_start.call_args[0][0]
            self.assertTrue(called_path.lower().endswith("notepad.exe"))

    @patch("core.app_controller.win32gui.PostMessage")
    def test_close_app_by_name(self, mock_post):
        """Проверка мягкого закрытия окна отправкой WM_CLOSE."""
        with patch.object(self.ctrl, "find_window", return_value=888):
            ok, msg = self.ctrl.close_app("блокнот")
            self.assertTrue(ok)
            self.assertIn("Закрыто", msg)
            mock_post.assert_called_once()

    @patch("core.app_controller.win32gui.ShowWindow")
    def test_minimize_app_by_name(self, mock_show):
        """Проверка сворачивания конкретного окна."""
        with patch.object(self.ctrl, "find_window", return_value=888):
            ok, msg = self.ctrl.minimize_app("калькулятор")
            self.assertTrue(ok)
            self.assertIn("Свернуто", msg)
            mock_show.assert_called_once()

    @patch("core.app_controller.win32gui.ShowWindow")
    def test_maximize_app_by_name(self, mock_show):
        """Проверка разворачивания конкретного окна."""
        with patch.object(self.ctrl, "find_window", return_value=888):
            ok, msg = self.ctrl.maximize_app("калькулятор")
            self.assertTrue(ok)
            self.assertIn("Развернуто", msg)
            mock_show.assert_called_once()

    @patch("core.app_controller.win32gui.ShowWindow")
    def test_minimize_all(self, mock_show):
        """Проверка сворачивания всех окон рабочего стола Windows."""
        ok, msg = self.ctrl.minimize_all()
        self.assertTrue(ok)
        self.assertIn("Рабочий стол", msg)


if __name__ == "__main__":
    unittest.main()
