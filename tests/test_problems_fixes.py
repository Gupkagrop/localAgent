"""
Модульные тесты для проверки исправлений из problems.md (BUG-001 - BUG-009).
"""
import unittest
from unittest.mock import patch, MagicMock
from core.decision_engine import DecisionEngine
from core.executor import CommandExecutor
import core.app_controller as app_controller


class TestProblemsFixes(unittest.TestCase):
    def setUp(self):
        self.engine = DecisionEngine()
        self.executor = CommandExecutor()

    def test_bug_001_app_controller_any_imported(self):
        """BUG-001: Any импортирован в app_controller и доступен."""
        self.assertTrue(hasattr(app_controller, "Any"))
        self.assertIsNotNone(app_controller.Any)

    def test_bug_002_volume_unmute(self):
        """BUG-002: Команда unmute корректно обрабатывается в _handle_volume."""
        with patch.object(self.executor, "_send_key") as mock_send_key:
            success, msg = self.executor._handle_volume("unmute", {})
            self.assertTrue(success)
            self.assertEqual(msg, "Звук включен")
            mock_send_key.assert_called_once()

    def test_bug_003_lock_workstation(self):
        """BUG-003: Команда lock_workstation блокирует компьютер через ctypes."""
        with patch("ctypes.windll.user32.LockWorkStation", return_value=1) as mock_lock:
            cmd = {
                "action": "system_action",
                "target": "lock_workstation",
                "parameters": {}
            }
            success, msg = self.executor.execute(cmd)
            self.assertTrue(success)
            self.assertEqual(msg, "Компьютер заблокирован")
            mock_lock.assert_called_once()

    def test_bug_006_github_repositories_url(self):
        """BUG-006: URL репозиториев github валиден."""
        cmd = self.engine.parse_command("Открой репозитории гитхаб")
        self.assertEqual(cmd["action"], "open_url")
        self.assertEqual(cmd["target"], "https://github.com/settings/repositories")

    def test_bug_008_vision_auto_focus_browser_setting(self):
        """BUG-008: Настройка vision_auto_focus_browser=False отключает автофокус браузера."""
        executor_no_autofocus = CommandExecutor(
            vision_manager=MagicMock(),
            settings={"vision_auto_focus_browser": False}
        )
        with patch.object(executor_no_autofocus.app_controller, "launch_or_focus") as mock_focus:
            cmd = {
                "action": "vision_agent",
                "target": "computer_use",
                "parameters": {"prompt": "На ютубе включи музыку"}
            }
            executor_no_autofocus._handle_vision_agent(cmd)
            mock_focus.assert_not_called()

        executor_with_autofocus = CommandExecutor(
            vision_manager=MagicMock(),
            settings={"vision_auto_focus_browser": True}
        )
        with patch.object(executor_with_autofocus.app_controller, "launch_or_focus") as mock_focus:
            cmd = {
                "action": "vision_agent",
                "target": "computer_use",
                "parameters": {"prompt": "На ютубе включи музыку"}
            }
            executor_with_autofocus._handle_vision_agent(cmd)
            mock_focus.assert_called_once()

    def test_bug_009_multi_word_urls_from_commands_json(self):
        """BUG-009: Составные URL из commands.json корректно обрабатываются Fast-Path."""
        vk_music = self.engine.parse_command("Открой музыка вк")
        self.assertEqual(vk_music["action"], "open_url")
        self.assertEqual(vk_music["target"], "https://vk.com/audios")

        vk_news = self.engine.parse_command("Перейди на новости вк")
        self.assertEqual(vk_news["action"], "open_url")
        self.assertEqual(vk_news["target"], "https://vk.com/feed")

        yt_history = self.engine.parse_command("Открой история ютуб")
        self.assertEqual(yt_history["action"], "open_url")
        self.assertEqual(yt_history["target"], "https://www.youtube.com/feed/history")


if __name__ == "__main__":
    unittest.main()
