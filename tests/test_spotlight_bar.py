"""
Модульные тесты поисковой строки SpotlightBar (gui/spotlight_bar.py).
Проверяют инициализацию, показ/скрытие, живые подсказки, историю ввода и эмит сигналов команд.
"""
import os
import unittest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

os.environ["QT_QPA_PLATFORM"] = "offscreen"
app = QApplication.instance() or QApplication(["SpotlightBarTest"])

from gui.spotlight_bar import SpotlightBar, SpotlightLineEdit


class TestSpotlightBar(unittest.TestCase):
    """Тестирование класса SpotlightBar."""

    def setUp(self):
        self.bar = SpotlightBar()

    def tearDown(self):
        self.bar.hide()
        self.bar.deleteLater()

    def test_init_properties(self):
        """Проверка геометрических параметров и флагов окна."""
        self.assertEqual(self.bar.width(), 640)
        flags = self.bar.windowFlags()
        self.assertTrue(flags & Qt.WindowType.FramelessWindowHint)
        self.assertTrue(flags & Qt.WindowType.WindowStaysOnTopHint)
        self.assertTrue(flags & Qt.WindowType.Tool)
        self.assertGreater(len(self.bar._known_commands), 0)

    def test_show_spotlight_resets_state(self):
        """Метод show_spotlight очищает поле ввода и скрывает список подсказок."""
        self.bar.line_edit.setText("старый текст")
        self.bar.show_spotlight()

        self.assertEqual(self.bar.line_edit.text(), "")
        self.assertFalse(self.bar.list_suggestions.isVisible())
        self.assertTrue(self.bar.hints_container.isVisible())
        self.assertTrue(self.bar.isVisible())

    def test_text_changed_shows_suggestions(self):
        """Ввод текста фильтрует известные команды и показывает выпадающий список."""
        self.bar.show_spotlight()
        # Вводим слово "громкость"
        self.bar.line_edit.setText("громкость")

        self.assertTrue(self.bar.list_suggestions.isVisible())
        self.assertFalse(self.bar.hints_container.isVisible())
        self.assertGreater(self.bar.list_suggestions.count(), 0)

        # Очищаем поле ввода — подсказки скрываются, чипы возвращаются
        self.bar.line_edit.setText("")
        self.assertFalse(self.bar.list_suggestions.isVisible())
        self.assertTrue(self.bar.hints_container.isVisible())

    def test_submit_command_emits_signal_and_saves_history(self):
        """Нажатие Enter эмитит сигнал command_submitted, добавляет команду в историю и скрывает окно."""
        self.bar.show_spotlight()
        self.bar.line_edit.setText("Открой браузер")

        emitted_commands: list[str] = []
        self.bar.command_submitted.connect(emitted_commands.append)

        self.bar._on_enter()

        self.assertEqual(len(emitted_commands), 1)
        self.assertEqual(emitted_commands[0], "Открой браузер")
        self.assertIn("Открой браузер", self.bar.history)
        self.assertFalse(self.bar.isVisible())

    def test_submit_empty_command_does_nothing(self):
        """Нажатие Enter при пустой строке не эмитит сигнал и оставляет окно открытым."""
        self.bar.show_spotlight()
        self.bar.line_edit.setText("   ")

        emitted_commands: list[str] = []
        self.bar.command_submitted.connect(emitted_commands.append)

        self.bar._on_enter()

        self.assertEqual(len(emitted_commands), 0)
        self.assertTrue(self.bar.isVisible())

    def test_select_suggestion_and_submit(self):
        """Выбор подсказки из списка стрелками и нажатие Enter отправляет выбранную команду."""
        self.bar.show_spotlight()
        self.bar.line_edit.setText("открой")
        self.assertTrue(self.bar.list_suggestions.count() > 0)

        # Перемещаемся стрелкой вниз на первую подсказку
        self.bar._on_down_pressed()
        self.assertEqual(self.bar.list_suggestions.currentRow(), 0)

        selected_text = self.bar.list_suggestions.currentItem().text().strip()

        emitted: list[str] = []
        self.bar.command_submitted.connect(emitted.append)
        self.bar._on_enter()

        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0], selected_text)

    def test_history_navigation(self):
        """Стрелки вверх/вниз при скрытых подсказках листают историю команд."""
        self.bar.history = ["команда 1", "команда 2", "команда 3"]
        self.bar.show_spotlight()

        # Стрелка вверх — переход к последней выполненной
        self.bar._on_up_pressed()
        self.assertEqual(self.bar.line_edit.text(), "команда 3")

        # Еще раз вверх — к предыдущей
        self.bar._on_up_pressed()
        self.assertEqual(self.bar.line_edit.text(), "команда 2")

        # Стрелка вниз — возвращение вперед
        self.bar._on_down_pressed()
        self.assertEqual(self.bar.line_edit.text(), "команда 3")

    def test_escape_hides_bar(self):
        """Сигнал esc_pressed скрывает панель поиска."""
        self.bar.show_spotlight()
        self.assertTrue(self.bar.isVisible())

        self.bar.line_edit.esc_pressed.emit()
        self.assertFalse(self.bar.isVisible())


if __name__ == "__main__":
    unittest.main()
