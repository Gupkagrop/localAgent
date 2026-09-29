"""
Тесты для модуля управления экраном core/screen_tools.py.
"""

import unittest
from PIL import Image
from core.screen_tools import ScreenController, ScreenDimensions, VK_MAP


class TestScreenTools(unittest.TestCase):
    """Тестирование координатной сетки и захвата экрана."""

    def setUp(self) -> None:
        self.controller = ScreenController()

    def test_screen_dimensions_valid(self) -> None:
        """Проверка получения физического разрешения монитора."""
        dims = self.controller.dimensions
        self.assertGreater(dims.width, 0)
        self.assertGreater(dims.height, 0)

    def test_denormalize_coordinate_corners(self) -> None:
        """Проверка крайних точек координатной сетки 0..1000."""
        dims = self.controller.dimensions
        # Верхний левый угол
        x, y = self.controller.denormalize_coordinate(norm_y=0, norm_x=0)
        self.assertEqual(x, dims.left)
        self.assertEqual(y, dims.top)

        # Нижний правый угол
        x, y = self.controller.denormalize_coordinate(norm_y=1000, norm_x=1000)
        self.assertEqual(x, dims.left + dims.width - 1)
        self.assertEqual(y, dims.top + dims.height - 1)

    def test_denormalize_coordinate_center(self) -> None:
        """Проверка центра экрана (500, 500)."""
        dims = self.controller.dimensions
        x, y = self.controller.denormalize_coordinate(norm_y=500, norm_x=500)
        self.assertAlmostEqual(x, dims.left + dims.width // 2, delta=2)
        self.assertAlmostEqual(y, dims.top + dims.height // 2, delta=2)

    def test_denormalize_coordinate_clamping(self) -> None:
        """Проверка отсечения координат за пределами диапазона 0..1000."""
        dims = self.controller.dimensions
        x, y = self.controller.denormalize_coordinate(norm_y=-100, norm_x=1200)
        self.assertEqual(x, dims.left + dims.width - 1)
        self.assertEqual(y, dims.top)

    def test_active_monitor_detection(self) -> None:
        """Проверка определения активного монитора."""
        left, top, w, h = self.controller.get_active_monitor_rect()
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)
        self.assertIsInstance(left, int)
        self.assertIsInstance(top, int)

    def test_vk_map_contains_essentials(self) -> None:
        """Проверка наличия ключевых клавиш в таблице виртуальных кодов."""
        for key in ["enter", "esc", "ctrl", "alt", "win", "tab", "space"]:
            self.assertIn(key, VK_MAP)
            self.assertIsInstance(VK_MAP[key], int)

    def test_capture_screen_returns_image(self) -> None:
        """Проверка захвата экрана в формате PIL.Image."""
        img = self.controller.capture_screen()
        self.assertIsInstance(img, Image.Image)
        self.assertGreater(img.width, 0)
        self.assertGreater(img.height, 0)

    def test_fallback_capture_mss(self) -> None:
        """Проверка резервного захвата экрана через mss/fallback без падения и без AttributeError."""
        img = self.controller._fallback_capture()
        self.assertIsInstance(img, Image.Image)
        self.assertGreater(img.width, 0)
        self.assertGreater(img.height, 0)

    def test_denormalize_negative_monitor_coordinates(self) -> None:
        """Проверка корректной денормализации на дополнительном левом мониторе с отрицательными координатами."""
        # Монитор слева от основного: left = -1920, top = 0, width = 1920, height = 1080
        self.controller._current_monitor = (-1920, 0, 1920, 1080)
        
        # Левый верхний угол
        x, y = self.controller.denormalize_coordinate(norm_x=0, norm_y=0)
        self.assertEqual(x, -1920)
        self.assertEqual(y, 0)

        # Центр левого монитора
        x, y = self.controller.denormalize_coordinate(norm_x=500, norm_y=500)
        self.assertEqual(x, -960)
        self.assertEqual(y, 540)

        # Правый нижний угол левого монитора
        x, y = self.controller.denormalize_coordinate(norm_x=1000, norm_y=1000)
        self.assertEqual(x, -1)
        self.assertEqual(y, 1079)

    def test_type_text_short_uses_direct_input(self) -> None:
        """Короткий текст (<= 20 символов) отправляется напрямую через _type_chars_direct."""
        from unittest.mock import patch
        with patch.object(self.controller, "_type_chars_direct") as mock_direct:
            with patch.object(self.controller, "hotkey") as mock_hotkey:
                self.controller.type_text("Привет, мир!", press_enter=False)
                mock_direct.assert_called_once_with("Привет, мир!")
                mock_hotkey.assert_not_called()

    def test_type_text_long_uses_clipboard(self) -> None:
        """Длинный текст (> 20 символов) передается через буфер обмена Windows и hotkey Ctrl+V."""
        from unittest.mock import patch
        long_text = "Этот текст точно длиннее двадцати символов для тестирования"
        with patch.object(self.controller, "_type_chars_direct") as mock_direct:
            with patch.object(self.controller, "hotkey") as mock_hotkey:
                self.controller.type_text(long_text, press_enter=False)
                mock_hotkey.assert_called_once_with(["ctrl", "v"])
                mock_direct.assert_not_called()


if __name__ == "__main__":
    unittest.main()
