"""
Модульные тесты для парсера действий и контроллера Vision-агента (core/vision_agent.py).
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from core.vision_agent import (
    ActionParser,
    FailSafeMonitor,
    VisionAction,
    VisionAgentProcessManager,
    build_computer_use_prompt,
    COMPUTER_USE_SYSTEM_PROMPT,
)
from gui.main_window import MainWindow


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
        """Корректная обработка синтаксически невалидного ответа (возвращает action_type=error)."""
        raw = "Я не знаю, что делать дальше, вот текст без скобок."
        act = ActionParser.parse(raw)
        self.assertEqual(act.action_type, "error")
        self.assertIn("Синтаксическая ошибка в JSON", act.thought)

    def test_parse_json_repair_unescaped_quotes(self) -> None:
        """Восстановление JSON с неэкранированными кавычками внутри мысли (thought)."""
        raw = '{"thought": "Нажимаю на кнопку "Пуск" на панели задач", "action": "click", "coordinate": [30, 980]}'
        act = ActionParser.parse(raw)
        self.assertEqual(act.action_type, "click")
        self.assertEqual(act.coordinate, (30, 980))
        self.assertIn("Пуск", act.thought)

    def test_parse_json_repair_trailing_comma(self) -> None:
        """Восстановление JSON с завершающей запятой перед скобкой."""
        raw = '{"thought": "Клик по кнопке", "action": "click", "coordinate": [120, 340],}'
        act = ActionParser.parse(raw)
        self.assertEqual(act.action_type, "click")
        self.assertEqual(act.coordinate, (120, 340))

    def test_parse_json_repair_single_quotes(self) -> None:
        """Восстановление ответа в стиле Python словаря с одинарными кавычками."""
        raw = "{'thought': 'Ожидание загрузки', 'action': 'wait'}"
        act = ActionParser.parse(raw)
        self.assertEqual(act.action_type, "wait")
        self.assertEqual(act.thought, "Ожидание загрузки")

    def test_parse_json_surrounding_text(self) -> None:
        """Извлечение JSON из текста с вводными и заключительными фразами."""
        raw = 'Конечно! Вот моё действие:\n```json\n{"thought": "Готово", "action": "finish", "message": "Задача выполнена"}\n```\nНадеюсь помог!'
        act = ActionParser.parse(raw)
        self.assertEqual(act.action_type, "finish")
        self.assertEqual(act.message, "Задача выполнена")

    def test_parse_json_infer_click_from_coordinates(self) -> None:
        """Автоматическое определение клика, если action не указан, но есть координаты."""
        raw = '{"thought": "Нажимаю на поле ввода", "coordinate": [450, 200]}'
        act = ActionParser.parse(raw)
        self.assertEqual(act.action_type, "click")
        self.assertEqual(act.coordinate, (450, 200))

    def test_parse_alias_normalization(self) -> None:
        """Нормализация синонимов и алиасов действий модели в ActionParser."""
        # left_click -> click
        act_click = ActionParser.parse('{"thought": "Клик", "action": "left_click", "coordinate": [100, 200]}')
        self.assertEqual(act_click.action_type, "click")

        # right-click -> right_click
        act_right = ActionParser.parse('{"thought": "Контекстное меню", "action": "right-click", "coordinate": [200, 300]}')
        self.assertEqual(act_right.action_type, "right_click")

        # write -> type
        act_write = ActionParser.parse('{"thought": "Ввод текста", "action": "write", "text": "тестовая строка"}')
        self.assertEqual(act_write.action_type, "type")

        # done -> finish
        act_done = ActionParser.parse('{"thought": "Завершение", "action": "done", "message": "задача выполнена"}')
        self.assertEqual(act_done.action_type, "finish")

    def test_dangerous_hotkeys_detected(self) -> None:
        """Программные guardrails: выявление опасных системных шорткатов и их синонимов."""
        self.assertTrue(ActionParser.is_dangerous_hotkey(["shift", "delete"]))
        self.assertTrue(ActionParser.is_dangerous_hotkey(["win", "r"]))
        self.assertTrue(ActionParser.is_dangerous_hotkey(["ctrl", "alt", "delete"]))
        # Проверка алиасов клавиш
        self.assertTrue(ActionParser.is_dangerous_hotkey(["windows", "r"]))
        self.assertTrue(ActionParser.is_dangerous_hotkey(["control", "alt", "delete"]))
        self.assertTrue(ActionParser.is_dangerous_hotkey(["shift", "del"]))

    def test_safe_hotkeys_allowed(self) -> None:
        """Безопасные шорткаты не блокируются guardrails."""
        self.assertFalse(ActionParser.is_dangerous_hotkey(["ctrl", "c"]))
        self.assertFalse(ActionParser.is_dangerous_hotkey(["ctrl", "v"]))
        self.assertFalse(ActionParser.is_dangerous_hotkey(["ctrl", "t"]))
        self.assertFalse(ActionParser.is_dangerous_hotkey(["alt", "tab"]))
        self.assertFalse(ActionParser.is_dangerous_hotkey([]))

    def test_build_computer_use_prompt_dimensions(self) -> None:
        """Проверка динамического формирования системного промпта с точным разрешением входного кадра."""
        prompt = build_computer_use_prompt(1260, 784)
        self.assertIn("The screen screenshot resolution is 1260x784.", prompt)
        self.assertIn("x: 0..1260, y: 0..784", prompt)
        self.assertIn('"double_click"', prompt)
        self.assertIn("double_click", prompt)

        # Обратная совместимость с дефолтным промптом
        self.assertIn("1920x1080", COMPUTER_USE_SYSTEM_PROMPT)

    def test_parse_double_click_actions(self) -> None:
        """Парсинг двойного клика для запуска приложений с рабочего стола."""
        # Прямое указание double_click
        raw1 = '{"thought": "Двойной клик на Obsidian", "action": "double_click", "coordinate": [36, 278]}'
        act1 = ActionParser.parse(raw1)
        self.assertEqual(act1.action_type, "double_click")
        self.assertEqual(act1.coordinate, (36, 278))

        # Алиас double-click
        raw2 = '{"thought": "Запуск программы", "action": "double-click", "coordinate": [50, 100]}'
        act2 = ActionParser.parse(raw2)
        self.assertEqual(act2.action_type, "double_click")

        # Алиас doubleclick
        raw3 = '{"thought": "Запуск программы", "action": "doubleclick", "coordinate": [50, 100]}'
        act3 = ActionParser.parse(raw3)
        self.assertEqual(act3.action_type, "double_click")


class TestFailSafeMonitor(unittest.TestCase):
    """Тестирование экстренного прерывания действий."""

    def test_cursor_position_valid(self) -> None:
        """Проверка получения координат мыши."""
        monitor = FailSafeMonitor()
        x, y = monitor.get_cursor_position()
        self.assertIsInstance(x, int)
        self.assertIsInstance(y, int)

    def test_interrupt_detection_esc_pressed(self) -> None:
        """Нажатие клавиши ESC (0x1B) прерывает выполнение агента."""
        monitor = FailSafeMonitor()
        with patch.object(monitor.user32, "GetAsyncKeyState", return_value=0x8000):
            interrupted, reason = monitor.is_interrupted()
            self.assertTrue(interrupted)
            self.assertIn("ESC", reason)

    def test_interrupt_detection_mouse_delta_exceeded(self) -> None:
        """Физическое смещение мыши более чем на 40 px прерывает выполнение агента."""
        monitor = FailSafeMonitor()
        monitor.update_known_position(100, 100)
        with patch.object(monitor.user32, "GetAsyncKeyState", return_value=0):
            with patch.object(monitor, "get_cursor_position", return_value=(150, 100)):
                interrupted, reason = monitor.is_interrupted()
                self.assertTrue(interrupted)
                self.assertIn("мыши", reason)

    def test_interrupt_detection_mouse_delta_within_threshold(self) -> None:
        """Незначительное смещение мыши (<= 40 px) не прерывает выполнение агента."""
        monitor = FailSafeMonitor()
        monitor.update_known_position(100, 100)
        with patch.object(monitor.user32, "GetAsyncKeyState", return_value=0):
            with patch.object(monitor, "get_cursor_position", return_value=(110, 100)):
                interrupted, reason = monitor.is_interrupted()
                self.assertFalse(interrupted)
                self.assertEqual(reason, "")


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

    @patch("core.vision_agent.mp.Process")
    def test_manager_is_loading(self, mock_process_cls) -> None:
        """Проверка метода is_loading() (при старте True, при ready False, при stop False)."""
        mock_proc = MagicMock()
        mock_proc.is_alive.return_value = True
        mock_process_cls.return_value = mock_proc

        mgr = VisionAgentProcessManager()
        # До старта: процесс не запущен
        self.assertFalse(mgr.is_loading())

        # 1. При старте: процесс запущен, веса модели еще не готовы
        mgr.start()
        self.assertTrue(mgr.is_running())
        self.assertTrue(mgr.is_loading())

        # 2. При ready: модель загружена в GPU
        mgr._is_ready = True
        self.assertFalse(mgr.is_loading())
        self.assertTrue(mgr.is_ready())

        # 3. При stop: процесс остановлен
        mock_proc.is_alive.return_value = False
        mgr.stop()
        self.assertFalse(mgr.is_loading())
        self.assertFalse(mgr.is_running())

    @patch("core.vision_agent.mp.Process")
    def test_manager_detects_worker_crash(self, mock_process_cls) -> None:
        """При краше процесса воркера во время занятости сбрасывается _is_busy и генерируется ошибка."""
        mock_proc = MagicMock()
        mock_proc.is_alive.return_value = False
        mock_process_cls.return_value = mock_proc

        mgr = VisionAgentProcessManager()
        mgr._process = mock_proc
        mgr._is_busy = True
        mgr._status_queue = MagicMock()
        mgr._status_queue.get_nowait.side_effect = Exception("Queue empty")

        events = mgr.poll_status()
        self.assertFalse(mgr.is_busy())
        self.assertTrue(any(ev.get("type") == "error" and "неожиданно завершился" in ev.get("message", "") for ev in events))


class TestMainWindowStatus(unittest.TestCase):
    """Тестирование метода set_llm_status в MainWindow для состояний 'loading', 'ready', 'error', 'not_installed'."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_set_llm_status(self) -> None:
        """Проверка установки статусов 'loading', 'ready', 'error', 'not_installed'."""
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "settings.json")
        window = MainWindow(config_path)

        # 1. Состояние 'loading'
        window.set_llm_status("loading")
        self.assertEqual(window.card_ai.status_label.text(), "Загрузка в GPU...")
        self.assertIn("#F59E0B", window.card_ai.status_label.styleSheet())
        self.assertEqual(window.btn_download_llm.text(), "⏳ Загрузка в VRAM...")
        self.assertFalse(window.btn_download_llm.isEnabled())

        # 2. Состояние 'ready'
        window.set_llm_status("ready")
        self.assertEqual(window.card_ai.status_label.text(), "Jedi-3B (Готова / Warm)")
        self.assertIn("#34D399", window.card_ai.status_label.styleSheet())
        self.assertEqual(window.btn_download_llm.text(), "✓ Jedi-3B (1080p) готова")
        self.assertFalse(window.btn_download_llm.isEnabled())

        # 3. Состояние 'error'
        window.set_llm_status("error")
        self.assertEqual(window.card_ai.status_label.text(), "Ошибка загрузки")
        self.assertIn("#EF4444", window.card_ai.status_label.styleSheet())
        self.assertEqual(window.btn_download_llm.text(), "⚠ Ошибка Vision-модели")
        self.assertTrue(window.btn_download_llm.isEnabled())

        # 4. Состояние 'not_installed'
        window.set_llm_status("not_installed")
        self.assertEqual(window.card_ai.status_label.text(), "Fast-Path (0 мс, 0 МБ)")
        self.assertIn("#60A5FA", window.card_ai.status_label.styleSheet())
        self.assertEqual(window.btn_download_llm.text(), "📥 Скачать Jedi-3B (1080p)")
        self.assertTrue(window.btn_download_llm.isEnabled())


class TestTorchIsolation(unittest.TestCase):
    """Тестирование архитектурной изоляции PyTorch от основного процесса."""

    def test_torch_not_in_sys_modules(self) -> None:
        """PyTorch не должен импортироваться в адресное пространство основного процесса."""
        # Основной процесс UI и Fast-Path не должен зависеть от тяжелого Torch runtime
        self.assertNotIn(
            "torch",
            sys.modules,
            "Критическая ошибка архитектуры: PyTorch импортирован в основной процесс!"
        )


if __name__ == "__main__":
    unittest.main()

