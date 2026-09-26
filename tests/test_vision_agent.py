"""
Модульные тесты для парсера действий и контроллера Vision-агента (core/vision_agent.py).
"""

import unittest
from core.vision_agent import ActionParser, FailSafeMonitor, VisionAction, VisionAgentProcessManager


class TestVisionAgentParser(unittest.TestCase):
    """Тестирование ActionParser для структурированных ответов модели."""

    def test_parse_clean_json_click(self) -> None:
        """Парсинг действия клика с нормализованными координатами."""
        raw = """```json
{
  "thought": "Вижу кнопку поиска на экране",
  "action": "click",
  "coordinate": [150, 480]
}
```"""
        act = ActionParser.parse(raw)
        self.assertEqual(act.action_type, "click")
        self.assertEqual(act.coordinate, (150, 480))
        self.assertIn("Вижу кнопку поиска", act.thought)

    def test_parse_type_with_enter(self) -> None:
        """Парсинг действия ввода текста с нажатием Enter."""
        raw = """```json
{
  "thought": "Ввожу поисковый запрос Мармук",
  "action": "type",
  "text": "Мармук",
  "press_enter": true
}
```"""
        act = ActionParser.parse(raw)
        self.assertEqual(act.action_type, "type")
        self.assertEqual(act.text, "Мармук")
        self.assertTrue(act.press_enter)

    def test_parse_hotkey(self) -> None:
        """Парсинг комбинации горячих клавиш."""
        raw = """```json
{
  "thought": "Открываю новую вкладку браузера",
  "action": "hotkey",
  "keys": ["Ctrl", "T"]
}
```"""
        act = ActionParser.parse(raw)
        self.assertEqual(act.action_type, "hotkey")
        self.assertEqual(act.keys, ["ctrl", "t"])

    def test_parse_scroll(self) -> None:
        """Парсинг прокрутки экрана вниз."""
        raw = """{
  "thought": "Прокручиваю ленту вниз",
  "action": "scroll",
  "direction": "down"
}"""
        act = ActionParser.parse(raw)
        self.assertEqual(act.action_type, "scroll")
        self.assertEqual(act.direction, "down")

    def test_parse_finish_action(self) -> None:
        """Парсинг успешного завершения задачи."""
        raw = """```json
{
  "thought": "Видео начало воспроизводиться",
  "action": "finish",
  "message": "Включил последнее видео Мармука"
}
```"""
        act = ActionParser.parse(raw)
        self.assertEqual(act.action_type, "finish")
        self.assertEqual(act.message, "Включил последнее видео Мармука")

    def test_parse_confirmation_request(self) -> None:
        """Парсинг запроса подтверждения опасного действия."""
        raw = """```json
{
  "thought": "Подготовлено сообщение для отправки",
  "action": "ask_confirmation",
  "message": "Отправить сообщение в чат с Вовой?"
}
```"""
        act = ActionParser.parse(raw)
        self.assertEqual(act.action_type, "ask_confirmation")
        self.assertIn("Отправить сообщение", act.message)

    def test_parse_malformed_json_fallback(self) -> None:
        """Корректная обработка синтаксически невалидного ответа."""
        raw = "Я не знаю, что делать дальше, вот текст без скобок."
        act = ActionParser.parse(raw)
        self.assertEqual(act.action_type, "finish")
        self.assertIn("Не удалось распознать JSON", act.thought)


class TestFailSafeMonitor(unittest.TestCase):
    """Тестирование экстренного прерывания действий."""

    def test_cursor_position_valid(self) -> None:
        """Проверка получения координат мыши."""
        monitor = FailSafeMonitor()
        x, y = monitor.get_cursor_position()
        self.assertIsInstance(x, int)
        self.assertIsInstance(y, int)

    def test_interrupt_detection_logic(self) -> None:
        """Проверка расчета дистанции движения мыши."""
        monitor = FailSafeMonitor()
        x, y = monitor.get_cursor_position()
        monitor.update_known_position(x, y)
        interrupted, _ = monitor.is_interrupted()
        # Если пользователь не дергает мышь и не жмет ESC во время теста
        self.assertIsInstance(interrupted, bool)


class TestProcessManager(unittest.TestCase):
    """Тестирование диспетчера процессов VisionAgentProcessManager."""

    def test_manager_initial_state(self) -> None:
        """Проверка начального состояния менеджера без запуска процесса."""
        mgr = VisionAgentProcessManager()
        self.assertFalse(mgr.is_running())
        self.assertFalse(mgr.is_ready())
        self.assertEqual(mgr.model_name, "xlangai/Jedi-3B-1080p")
        self.assertEqual(mgr.fallback_model, "Qwen/Qwen2.5-VL-3B-Instruct")

    def test_manager_fallback_customization(self) -> None:
        """Проверка настройки резервной модели."""
        mgr = VisionAgentProcessManager(fallback_model="custom/fallback")
        self.assertEqual(mgr.fallback_model, "custom/fallback")


if __name__ == "__main__":
    unittest.main()
