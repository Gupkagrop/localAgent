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
        self.assertEqual(x, dims.left + dims.width)
        self.assertEqual(y, dims.top + dims.height)

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
        self.assertEqual(x, dims.left + dims.width)
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


if __name__ == "__main__":
    unittest.main()
