"""
Комплексный автоматизированный тест компонентов Antigravity Voice.
Проверяет все модули системы: DecisionEngine, AudioDucker, TextToSpeech,
конфигурационные файлы, горячие клавиши и схемы команд.
"""
import os
import json
import unittest

from core.decision_engine import DecisionEngine
from core.audio_ducking import AudioDucker
from core.text_to_speech import TextToSpeech
from core.keyboard_hook import CopilotKeyHook

class TestDecisionEngine(unittest.TestCase):
    def setUp(self):
        self.engine = DecisionEngine()

    def test_antigravity_gui_open(self):
        res = self.engine.parse_command("Открой Antigravity")
        self.assertEqual(res["action"], "antigravity_gui")
        self.assertEqual(res["target"], "open")

    def test_antigravity_gui_prompt(self):
        res = self.engine.parse_command("Джарвис, напиши в Antigravity создай новый проект на FastAPI")
        self.assertEqual(res["action"], "antigravity_gui")
        self.assertEqual(res["target"], "prompt")
        self.assertIn("FastAPI", res["parameters"]["prompt"])

    def test_antigravity_gui_new_chat(self):
        res = self.engine.parse_command("Создай новый чат в Antigravity")
        self.assertEqual(res["action"], "antigravity_gui")
        self.assertEqual(res["target"], "new_chat")

    def test_antigravity_cli_with_task(self):
        res = self.engine.parse_command("Запусти Antigravity CLI git status")
        self.assertEqual(res["action"], "antigravity_cli")
        self.assertIn("git status", res["parameters"]["prompt"])

    def test_model_status(self):
        has_file = os.path.exists(os.path.join(self.engine.models_dir, "qwen2.5-1.5b-instruct-q4_k_m.gguf"))
        self.assertEqual(self.engine.is_llm_available(), has_file)
        if has_file:
            self.assertIn("Локальная LLM", self.engine.get_model_status())
        else:
            self.assertIn("Fast-Path", self.engine.get_model_status())

    def test_antigravity_cli_plain(self):
        res = self.engine.parse_command("Открой терминал Antigravity")
        self.assertEqual(res["action"], "antigravity_cli")

    def test_volume_absolute(self):
        res = self.engine.parse_command("Сделай громкость 45%")
        self.assertEqual(res["action"], "set_volume")
        self.assertEqual(res["target"], "absolute")
        self.assertEqual(res["parameters"]["percent"], 45)

    def test_volume_step_down(self):
        res = self.engine.parse_command("Сделай потише")
        self.assertEqual(res["action"], "set_volume")
        self.assertEqual(res["target"], "step_down")

    def test_volume_step_up(self):
        res = self.engine.parse_command("Сделай громче")
        self.assertEqual(res["action"], "set_volume")
        self.assertEqual(res["target"], "step_up")

    def test_volume_mute(self):
        res = self.engine.parse_command("Выключи звук")
        self.assertEqual(res["action"], "set_volume")
        self.assertEqual(res["target"], "mute")

    def test_media_control(self):
        res = self.engine.parse_command("Следующий трек")
        self.assertEqual(res["action"], "media_control")
        self.assertEqual(res["target"], "next_track")

    def test_web_search(self):
        res = self.engine.parse_command("Найди в гугле погода Москва")
        self.assertEqual(res["action"], "open_url")
        self.assertIn("погода", res["target"])

    def test_dangerous_action_confirmation(self):
        res = self.engine.parse_command("Выключи ноутбук")
        self.assertEqual(res["action"], "system_action")
        self.assertEqual(res["target"], "shutdown")
        self.assertTrue(res["parameters"].get("dangerous"))

from core.executor import CommandExecutor
from core.keyboard_hook import CopilotKeyHook, VK_F23, VK_F23_ALT

class TestCoreModules(unittest.TestCase):
    def test_audio_ducker_init(self):
        ducker = AudioDucker()
        self.assertFalse(ducker._is_ducked)

    def test_tts_init(self):
        tts = TextToSpeech(speed=1)
        self.assertEqual(tts.speed, 1)

    def test_keyboard_hook_init(self):
        hook = CopilotKeyHook()
        self.assertFalse(hook._is_running)
        self.assertEqual(VK_F23, 0x86)
        self.assertEqual(VK_F23_ALT, 0x8E)

    def test_executor_general_answer(self):
        executor = CommandExecutor()
        cmd = {"action": "general_answer", "target": "answer", "parameters": {"text": "Тестовый ответ"}}
        ok, msg = executor.execute(cmd)
        self.assertTrue(ok)
        self.assertEqual(msg, "Тестовый ответ")

    def test_executor_dangerous_action_confirmation(self):
        executor = CommandExecutor()
        cmd = {"action": "system_action", "target": "shutdown", "parameters": {"dangerous": True}}
        ok, msg = executor.execute(cmd)
        self.assertFalse(ok)
        self.assertEqual(msg, "CONFIRM_REQUIRED")

    def test_executor_antigravity_config(self):
        executor = CommandExecutor()
        self.assertIn("Antigravity", executor.gui_window_names)
        self.assertEqual(executor.cli_executable, "agy")

class TestConfigs(unittest.TestCase):
    def test_settings_integrity(self):
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "settings.json")
        self.assertTrue(os.path.exists(config_path))
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("default_activation_mode", data)
        self.assertIn("close_behavior", data)
        self.assertIn("audio_ducking_enabled", data)
        self.assertIn("wake_word_enabled", data)

    def test_commands_integrity(self):
        commands_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "commands.json")
        self.assertTrue(os.path.exists(commands_path))
        with open(commands_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("apps", data)
        self.assertIn("urls", data)
        self.assertIn("antigravity", data)

    def test_commands_dynamic_loading(self):
        engine = DecisionEngine()
        self.assertIn("почта", engine.url_map)
        res = engine.parse_command("Открой почту")
        self.assertEqual(res["action"], "open_url")
        self.assertEqual(res["target"], "https://mail.google.com")

    def test_settings_wake_word(self):
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "settings.json")
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("wake_word", data)
        self.assertEqual(data["wake_word"].lower(), "джарвис")

    def test_decision_engine_load_model_failure(self):
        fake_engine = DecisionEngine(models_dir="C:/non_existent_path_xyz")
        self.assertFalse(fake_engine.load_model())

class TestMainWindowFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_main_window_check_all_and_wake_word(self):
        from gui.main_window import MainWindow
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "settings.json")
        window = MainWindow(config_path)

        # 1. Проверка наличия кнопки полной проверки всех систем
        self.assertTrue(hasattr(window, "btn_check_all_systems"))
        self.assertIn("Проверить все системы", window.btn_check_all_systems.text())

        # 2. Проверка поля настройки слова-триггера
        self.assertTrue(hasattr(window, "txt_wake_word"))
        self.assertEqual(window.txt_wake_word.text().lower(), "джарвис")

        # 3. Проверка изменения слова-триггера и сброса по умолчанию
        window.txt_wake_word.setText("Компьютер")
        self.assertEqual(window.settings.get("wake_word"), "компьютер")

        window._reset_wake_word()
        self.assertEqual(window.settings.get("wake_word"), "джарвис")
        self.assertEqual(window.txt_wake_word.text(), "Джарвис")

        # 4. Проверка обновления статусной карточки
        window.update_status_card("mic", "Тестовый статус", "#34D399")
        self.assertEqual(window.card_mic.status_label.text(), "Тестовый статус")

if __name__ == "__main__":
    unittest.main()
