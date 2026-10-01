"""
Комплексный сквозной тест (E2E) для Vision-агента компьютерного управления (Jarvis Vision Agent).
Проверяет жизненный цикл рабочего процесса, межпроцессное взаимодействие (IPC),
парсер команд модели, математику координат экранов, защиту от зацикливания и программные guardrails.
"""

import multiprocessing as mp
import os
import queue
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

from core.screen_tools import ScreenController, ScreenDimensions
from core.vision_agent import (
    ActionParser,
    FailSafeMonitor,
    VisionAction,
    VisionAgentProcessManager,
    build_computer_use_prompt,
)


class TestVisionAgentE2E(unittest.TestCase):
    """Сквозное тестирование архитектуры и логики Vision-агента."""

    def setUp(self) -> None:
        self.screen = ScreenController()
        # Инициализация тестовой геометрии монитора: 1920x1080
        self.screen._dimensions = ScreenDimensions(width=1920, height=1080, left=0, top=0)
        self.screen._current_monitor = (0, 0, 1920, 1080)

    # =========================================================================
    # 1. ActionParser & Jedi-3B / Qwen2.5-VL Tool-Call Compatibility
    # =========================================================================

    def test_parse_jedi_tool_call_double_click(self) -> None:
        """Проверка парсинга нативного tool_call Jedi-3B для двойного клика."""
        response = """
<tool_call>
{"name": "computer_use", "arguments": {"thought": "Вижу ярлык Obsidian на рабочем столе", "action": "double_click", "coordinate": [38, 920]}}
</tool_call>
"""
        action = ActionParser.parse(response)
        self.assertEqual(action.action_type, "double_click")
        self.assertEqual(action.coordinate, (38, 920))
        self.assertIn("Obsidian", action.thought)

    def test_parse_jedi_tool_call_mouse_move(self) -> None:
        """Проверка нормализации действия mouse_move в клик с координатами."""
        response = """
<tool_call>
{"name": "computer_use", "arguments": {"thought": "Навожусь на строку поиска", "action": "mouse_move", "coordinate": [540, 1050]}}
</tool_call>
"""
        action = ActionParser.parse(response)
        self.assertEqual(action.action_type, "click")
        self.assertEqual(action.coordinate, (540, 1050))

    def test_parse_jedi_tool_call_terminate_success(self) -> None:
        """Проверка завершения задачи через terminate со статусом success."""
        response = """
<tool_call>
{"name": "computer_use", "arguments": {"thought": "Приложение успешно запущено", "action": "terminate", "status": "success", "message": "Obsidian открыт"}}
</tool_call>
"""
        action = ActionParser.parse(response)
        self.assertEqual(action.action_type, "finish")
        self.assertEqual(action.message, "Obsidian открыт")

    def test_parse_nested_parameters_dict(self) -> None:
        """Поддержка альтернативного ключа parameters вместо arguments."""
        response = """
<tool_call>
{"name": "computer_use", "parameters": {"thought": "Клик по кнопке", "action": "click", "coordinate": [100, 200]}}
</tool_call>
"""
        action = ActionParser.parse(response)
        self.assertEqual(action.action_type, "click")
        self.assertEqual(action.coordinate, (100, 200))

    def test_parse_all_coordinate_formats(self) -> None:
        """Проверка всех возможных представлений координат от различных VLM."""
        # 1. point [x, y]
        a1 = ActionParser.parse('{"action": "click", "point": [150, 250]}')
        self.assertEqual(a1.coordinate, (150, 250))

        # 2. coordinates [x, y]
        a2 = ActionParser.parse('{"action": "click", "coordinates": [350, 450]}')
        self.assertEqual(a2.coordinate, (350, 450))

        # 3. location [x, y]
        a3 = ActionParser.parse('{"action": "click", "location": [550, 650]}')
        self.assertEqual(a3.coordinate, (550, 650))

        # 4. point dictionary {"x": x, "y": y}
        a4 = ActionParser.parse('{"action": "click", "point": {"x": 750, "y": 850}}')
        self.assertEqual(a4.coordinate, (750, 850))

        # 5. raw x and y keys
        a5 = ActionParser.parse('{"action": "click", "x": 120, "y": 340}')
        self.assertEqual(a5.coordinate, (120, 340))

        # 6. string numbers in list
        a6 = ActionParser.parse('{"action": "click", "coordinate": ["200", "400"]}')
        self.assertEqual(a6.coordinate, (200, 400))

    # =========================================================================
    # 2. Coordinate Scaling & Multi-Monitor Math
    # =========================================================================

    def test_denormalize_pixel_coordinates_1080p(self) -> None:
        """Пиксельные координаты на 1080p мониторе преобразуются 1:1 без искажений."""
        screen_x, screen_y = self.screen.denormalize_coordinate(
            norm_x=38, norm_y=920, image_size=(1920, 1080)
        )
        self.assertEqual(screen_x, 38)
        self.assertEqual(screen_y, 920)

    def test_denormalize_scaled_vit_patch_coordinates(self) -> None:
        """Масштабирование координат из сетки патчей ViT (1904x1064) в 1920x1080."""
        # Точка по центру сетки: 952x532 -> должна стать ровно 960x540
        screen_x, screen_y = self.screen.denormalize_coordinate(
            norm_x=952, norm_y=532, image_size=(1904, 1064)
        )
        self.assertEqual(screen_x, 960)
        self.assertEqual(screen_y, 540)

    def test_denormalize_relative_1000_range(self) -> None:
        """Нормализованные координаты 0..1000 корректно проецируются на монитор."""
        # 500 из 1000 по ширине 1920 -> 960
        # 250 из 1000 по высоте 1080 -> 270
        screen_x, screen_y = self.screen.denormalize_coordinate(
            norm_x=500, norm_y=250, image_size=None
        )
        self.assertEqual(screen_x, 960)
        self.assertEqual(screen_y, 270)

    def test_denormalize_multi_monitor_offset(self) -> None:
        """Учет смещения левого/верхнего края для второго монитора."""
        self.screen._current_monitor = (1920, 0, 1920, 1080)
        screen_x, screen_y = self.screen.denormalize_coordinate(
            norm_x=100, norm_y=200, image_size=(1920, 1080)
        )
        self.assertEqual(screen_x, 2020)  # 1920 + 100
        self.assertEqual(screen_y, 200)

    def test_denormalize_negative_multi_monitor_offset(self) -> None:
        """Корректная обработка монитора с отрицательными координатами (слева от главного)."""
        self.screen._current_monitor = (-1920, 0, 1920, 1080)
        screen_x, screen_y = self.screen.denormalize_coordinate(
            norm_x=500, norm_y=500, image_size=(1920, 1080)
        )
        self.assertEqual(screen_x, -1420)  # -1920 + 500
        self.assertEqual(screen_y, 500)

    # =========================================================================
    # 3. Guardrails & Safety Defenses
    # =========================================================================

    def test_guardrails_destructive_commands(self) -> None:
        """Блокировка ввода опасных системных команд Windows."""
        dangerous_commands = [
            "format D: /fs:ntfs",
            "diskpart /s script.txt",
            "del /s /q C:\\*",
            "Remove-Item -Recurse -Force C:\\Windows",
            "powershell.exe -enc JABhID0A...",
            "cmd.exe /c shutdown /s /t 0",
            "reg delete HKCU\\Software /f",
            "bcdedit /set {default} bootstatuspolicy ignoreallfailures",
        ]
        for cmd in dangerous_commands:
            with self.subTest(command=cmd):
                self.assertTrue(
                    ActionParser.is_dangerous_command_text(cmd),
                    f"Команда '{cmd}' должна быть заблокирована guardrails!"
                )

    def test_guardrails_safe_commands(self) -> None:
        """Разрешение безопасных пользовательских запросов и команд."""
        safe_commands = [
            "hello world",
            "https://www.youtube.com",
            "открой obsidian",
            "calc",
            "notepad.exe",
            "python main.py",
            "git status",
        ]
        for cmd in safe_commands:
            with self.subTest(command=cmd):
                self.assertFalse(
                    ActionParser.is_dangerous_command_text(cmd),
                    f"Команда '{cmd}' не должна ложно блокироваться!"
                )

    def test_guardrails_destructive_hotkeys(self) -> None:
        """Блокировка потенциально опасных горячих клавиш."""
        self.assertTrue(ActionParser.is_dangerous_hotkey(["shift", "delete"]))
        self.assertTrue(ActionParser.is_dangerous_hotkey(["win", "r"]))
        self.assertTrue(ActionParser.is_dangerous_hotkey(["ctrl", "alt", "delete"]))
        self.assertTrue(ActionParser.is_dangerous_hotkey(["windows", "r"]))
        self.assertTrue(ActionParser.is_dangerous_hotkey(["control", "alt", "delete"]))

    # =========================================================================
    # 4. Process Manager Lifecycle & Queue IPC
    # =========================================================================

    def test_process_manager_lifecycle(self) -> None:
        """Тестирование инициализации, очередей IPC, выполнения задачи и завершения менеджера."""
        mgr = VisionAgentProcessManager()
        self.assertFalse(mgr.is_running())
        self.assertFalse(mgr.is_ready())
        self.assertFalse(mgr.is_busy())

        # Имитируем состояние запущенного процесса
        mock_process = MagicMock()
        mock_process.is_alive.return_value = True
        mgr._process = mock_process
        mgr._task_queue = MagicMock()
        mgr._status_queue = MagicMock()
        mgr._stop_event = MagicMock()
        mgr._cancel_event = MagicMock()

        self.assertTrue(mgr.is_running())
        self.assertTrue(mgr.is_loading())

        # Имитируем отправку статуса ready от воркера
        mgr._status_queue.get_nowait.side_effect = [
            {"type": "ready", "message": "Vision-модель готова"},
            queue.Empty()
        ]
        events = mgr.poll_status()
        self.assertTrue(mgr.is_ready())
        self.assertFalse(mgr.is_loading())
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "ready")

        # Отправка задачи на исполнение
        res = mgr.execute_task("Кликни на Obsidian", max_steps=5)
        self.assertTrue(res)
        self.assertTrue(mgr.is_busy())
        mgr._task_queue.put.assert_called_once()
        sent_task = mgr._task_queue.put.call_args[0][0]
        self.assertEqual(sent_task["type"], "execute")
        self.assertEqual(sent_task["prompt"], "Кликни на Obsidian")
        self.assertEqual(sent_task["max_steps"], 5)

        # Проверка экстренного прерывания
        mgr.abort_task()
        self.assertFalse(mgr.is_busy())
        mgr._cancel_event.set.assert_called_once()

        # Проверка завершения
        mgr.stop()
        self.assertFalse(mgr.is_running())
        self.assertFalse(mgr.is_ready())
        self.assertFalse(mgr.is_busy())

    def test_process_manager_poll_task_completion(self) -> None:
        """Проверка обработки событий завершения задачи в очереди."""
        mgr = VisionAgentProcessManager()
        mock_process = MagicMock()
        mock_process.is_alive.return_value = True
        mgr._process = mock_process
        mgr._is_ready = True
        mgr._is_busy = True
        mgr._status_queue = MagicMock()

        mgr._status_queue.get_nowait.side_effect = [
            {"type": "step_status", "step": 1, "status": "Захват экрана..."},
            {"type": "action_decided", "step": 1, "action": "click", "coordinate": [100, 200]},
            {"type": "click_performed", "x": 100, "y": 200, "button": "click"},
            {"type": "task_completed", "success": True, "message": "Задача выполнена"},
            queue.Empty()
        ]

        events = mgr.poll_status()
        self.assertEqual(len(events), 4)
        self.assertFalse(mgr.is_busy())
        self.assertEqual(events[-1]["type"], "task_completed")
        self.assertTrue(events[-1]["success"])

    def test_interruption_does_not_block_subsequent_tasks(self) -> None:
        """Сквозная проверка: прерывание первой задачи не блокирует повторный запуск агента."""
        failsafe = FailSafeMonitor()

        # Задача 1: агент выполнил клик в координаты (150, 300)
        failsafe.update_known_position(150, 300)

        # Пользователь прервал задачу 1, дернув мышь в координаты (650, 800)
        with patch.object(failsafe.user32, "GetAsyncKeyState", return_value=0):
            with patch.object(failsafe, "get_cursor_position", return_value=(650, 800)):
                interrupted1, reason1 = failsafe.is_interrupted()
                self.assertTrue(interrupted1)
                self.assertIn("мыши", reason1)

                # Завершение задачи 1 вызывает failsafe.reset()
                failsafe.reset()

                # Пользователь запускает Задачу 2. Курсор мыши все еще в (650, 800)
                # Проверяем, что Шаг 1 Задачи 2 НЕ прерывается
                interrupted2, reason2 = failsafe.is_interrupted()
                self.assertFalse(interrupted2)
                self.assertEqual(reason2, "")

    def test_process_manager_abort_and_subsequent_execute(self) -> None:
        """Проверка сброса cancel_event при запуске новой задачи после abort_task."""
        mgr = VisionAgentProcessManager()
        mock_process = MagicMock()
        mock_process.is_alive.return_value = True
        mgr._process = mock_process
        mgr._is_ready = True
        mgr._task_queue = MagicMock()
        mgr._cancel_event = MagicMock()

        # Запуск задачи 1
        mgr.execute_task("Задача 1")
        self.assertTrue(mgr.is_busy())

        # Пользователь экстренно отменяет задачу 1
        mgr.abort_task()
        self.assertFalse(mgr.is_busy())
        mgr._cancel_event.set.assert_called()

        # Пользователь запускает задачу 2
        ok = mgr.execute_task("Задача 2")
        self.assertTrue(ok)
        self.assertTrue(mgr.is_busy())
        mgr._cancel_event.clear.assert_called()


if __name__ == "__main__":
    unittest.main()
