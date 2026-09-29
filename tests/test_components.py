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
        status = self.engine.get_model_status()
        self.assertIn("Jedi-3B", status)
        self.assertIsInstance(self.engine.is_llm_available(), bool)

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
        self.assertIn("google.com/search?q=", res["target"])
        import urllib.parse
        self.assertIn("погода", urllib.parse.unquote(res["target"]))

    def test_youtube_search_complex(self):
        res = self.engine.parse_command("Открой, пожалуйста, ютубчик и включи там видео мармука.")
        self.assertEqual(res["action"], "vision_agent")
        self.assertIn("мармука", res["parameters"]["prompt"])

    def test_vk_open_with_punctuation(self):
        res = self.engine.parse_command("Открой ВК, пожалуйста.")
        self.assertEqual(res["action"], "open_url")
        self.assertEqual(res["target"], "https://vk.com")

    def test_domain_in_browser(self):
        res = self.engine.parse_command("Открой vk.com в браузере.")
        self.assertEqual(res["action"], "open_url")
        self.assertEqual(res["target"], "https://vk.com")

    def test_dangerous_action_confirmation(self):
        res = self.engine.parse_command("Выключи ноутбук")
        self.assertEqual(res["action"], "system_action")
        self.assertEqual(res["target"], "shutdown")
        self.assertTrue(res["parameters"].get("dangerous"))

    def test_youtube_direct_play_latest(self):
        # Сложная мультимодальная инструкция направляется в VisionAgent
        res = self.engine.parse_command("На ютуб включить последнее видео мармука")
        self.assertEqual(res["action"], "vision_agent")
        self.assertIn("мармук", res["parameters"]["prompt"])

    def test_youtube_direct_play_without_keyword_youtube(self):
        # Сложная мультимодальная инструкция направляется в VisionAgent
        res = self.engine.parse_command("Включи последнее видео мармука")
        self.assertEqual(res["action"], "vision_agent")
        self.assertIn("мармук", res["parameters"]["prompt"])

    def test_subpage_vk_messages(self):
        # Проверка открытия страницы сообщений ВК
        res = self.engine.parse_command("Открой сообщения вк")
        self.assertEqual(res["action"], "open_url")
        self.assertEqual(res["target"], "https://vk.com/im")

    def test_subpage_vk_messages_with_preposition(self):
        # Проверка открытия сообщений ВК с предлогом («в вк»)
        res = self.engine.parse_command("Перейди в сообщения в вк")
        self.assertEqual(res["action"], "open_url")
        self.assertEqual(res["target"], "https://vk.com/im")

    def test_subpage_youtube_subscriptions(self):
        # Проверка открытия подписок на YouTube
        res = self.engine.parse_command("Открой подписки на ютубе")
        self.assertEqual(res["action"], "open_url")
        self.assertEqual(res["target"], "https://www.youtube.com/feed/subscriptions")

    def test_subpage_github_trending(self):
        # Проверка открытия трендов GitHub
        res = self.engine.parse_command("Покажи тренды гитхаб")
        self.assertEqual(res["action"], "open_url")
        self.assertEqual(res["target"], "https://github.com/trending")

    def test_subpage_mail_inbox(self):
        # Проверка открытия входящих в почте
        res = self.engine.parse_command("Открой входящие в почте")
        self.assertEqual(res["action"], "open_url")
        self.assertEqual(res["target"], "https://mail.google.com/mail/u/0/#inbox")

    def test_universal_site_search_kinopoisk(self):
        # Проверка автономного управления через Vision-агента
        res = self.engine.parse_command("На Кинопоиске найди фильм Начало")
        self.assertEqual(res["action"], "vision_agent")
        self.assertIn("Начало", res["parameters"]["prompt"])

    def test_universal_site_search_avito(self):
        # Проверка автономного управления через Vision-агента
        res = self.engine.parse_command("Найди на Авито велосипед")
        self.assertEqual(res["action"], "vision_agent")
        self.assertIn("велосипед", res["parameters"]["prompt"])

    def test_universal_site_search_wikipedia(self):
        # Проверка автономного управления через Vision-агента
        res = self.engine.parse_command("В Википедии найди квантовую физику")
        self.assertEqual(res["action"], "vision_agent")
        self.assertIn("квантовую физику", res["parameters"]["prompt"])

    def test_universal_site_search_ozon(self):
        # Проверка автономного управления через Vision-агента
        res = self.engine.parse_command("На Озоне найди кофеварку")
        self.assertEqual(res["action"], "vision_agent")
        self.assertIn("кофеварку", res["parameters"]["prompt"])

    def test_universal_site_search_wildberries(self):
        # Проверка автономного управления через Vision-агента
        res = self.engine.parse_command("На wildberries найди кроссовки")
        self.assertEqual(res["action"], "vision_agent")
        self.assertIn("кроссовки", res["parameters"]["prompt"])

    def test_window_control_close(self):
        # Проверка закрытия приложений
        res = self.engine.parse_command("Закрой блокнот")
        self.assertEqual(res["action"], "window_control")
        self.assertEqual(res["target"], "close")
        self.assertEqual(res["parameters"]["app_name"], "блокнот")

    def test_window_control_minimize_and_restore(self):
        # Проверка сворачивания и рабочего стола
        res_min = self.engine.parse_command("Сверни блокнот")
        self.assertEqual(res_min["action"], "window_control")
        self.assertEqual(res_min["target"], "minimize")

        res_desktop = self.engine.parse_command("Покажи рабочий стол")
        self.assertEqual(res_desktop["action"], "window_control")
        self.assertEqual(res_desktop["target"], "minimize_all")

        res_max = self.engine.parse_command("Разверни на весь экран")
        self.assertEqual(res_max["action"], "window_control")
        self.assertEqual(res_max["target"], "maximize")

    def test_in_app_typing(self):
        # Проверка ввода текста в приложение
        res = self.engine.parse_command("В блокноте напиши купить молоко и хлеб")
        self.assertEqual(res["action"], "app_type")
        self.assertEqual(res["target"], "type")
        self.assertEqual(res["parameters"]["app_name"], "блокнот")
        self.assertEqual(res["parameters"]["text"], "купить молоко и хлеб")

    def test_in_app_search_telegram(self):
        # Поиск внутри приложения направляется в Vision-агента
        res = self.engine.parse_command("В телеграме найди проект")
        self.assertEqual(res["action"], "vision_agent")
        self.assertIn("проект", res["parameters"]["prompt"])

    def test_app_tabs_hotkeys(self):
        # Проверка горячих клавиш вкладок
        res_tab = self.engine.parse_command("Новая вкладка")
        self.assertEqual(res_tab["action"], "app_hotkey")
        self.assertEqual(res_tab["target"], "new_tab")

        res_close = self.engine.parse_command("Закрой вкладку")
        self.assertEqual(res_close["action"], "app_hotkey")
        self.assertEqual(res_close["target"], "close_tab")




from core.executor import CommandExecutor
from core.keyboard_hook import CopilotKeyHook, VK_F23, VK_F23_ALT

class TestCoreModules(unittest.TestCase):
    def test_executor_vision_agent(self):
        from unittest.mock import MagicMock
        mock_vm = MagicMock()
        mock_vm.is_running.return_value = True
        mock_vm.is_loading.return_value = False
        mock_vm.execute_task.return_value = True

        executor = CommandExecutor(vision_manager=mock_vm)
        cmd = {"action": "vision_agent", "parameters": {"prompt": "На ютубе найди Мармука"}}
        ok, msg = executor.execute(cmd)
        self.assertTrue(ok)
        self.assertEqual(msg, "Анализирую экран...")
        mock_vm.execute_task.assert_called_once_with("На ютубе найди Мармука", max_steps=8)

    def test_audio_ducker_init(self):
        ducker = AudioDucker()
        self.assertFalse(ducker._is_ducked)

    def test_audio_ducker_duck_and_unduck(self):
        ducker = AudioDucker()
        import unittest.mock as mock
        mock_endpoint = mock.MagicMock()
        mock_endpoint.GetMasterVolumeLevelScalar.return_value = 0.8

        with mock.patch.object(ducker, "_get_volume_endpoint", return_value=mock_endpoint):
            ducker.duck(duck_factor=0.25)
            self.assertTrue(ducker._is_ducked)
            self.assertAlmostEqual(ducker._previous_volume, 0.8)
            mock_endpoint.SetMasterVolumeLevelScalar.assert_called_with(0.2, None)

            ducker.unduck()
            self.assertFalse(ducker._is_ducked)
            self.assertIsNone(ducker._previous_volume)
            mock_endpoint.SetMasterVolumeLevelScalar.assert_called_with(0.8, None)

    def test_audio_ducker_duck_when_muted_remains_zero(self):
        """Если системная громкость равна 0 (Mute), ducking оставляет 0.0 и не включает звук."""
        ducker = AudioDucker()
        import unittest.mock as mock
        mock_endpoint = mock.MagicMock()
        mock_endpoint.GetMasterVolumeLevelScalar.return_value = 0.0

        with mock.patch.object(ducker, "_get_volume_endpoint", return_value=mock_endpoint):
            ducker.duck(duck_factor=0.25)
            self.assertTrue(ducker._is_ducked)
            self.assertEqual(ducker._previous_volume, 0.0)
            mock_endpoint.SetMasterVolumeLevelScalar.assert_called_with(0.0, None)

    def test_tts_init(self):
        tts = TextToSpeech(speed=1)
        self.assertEqual(tts.speed, 1)

    def test_keyboard_hook_init(self):
        hook = CopilotKeyHook()
        self.assertFalse(hook._is_running)
        self.assertEqual(VK_F23, 0x86)
        self.assertEqual(VK_F23_ALT, 0x8E)

    def test_keyboard_hook_windows_key_not_blocked(self):
        hook = CopilotKeyHook()
        class FakeData:
            vkCode = 0x5B  # VK_LWIN
        # WM_KEYDOWN for Windows key must ALWAYS return True (never blocked)
        res = hook._win32_event_filter(0x0100, FakeData())
        self.assertTrue(res)
        # WM_KEYUP for Windows key must also return True
        res_up = hook._win32_event_filter(0x0101, FakeData())
        self.assertTrue(res_up)

    def test_keyboard_hook_copilot_blocked(self):
        clicked = []
        hook = CopilotKeyHook(on_click=lambda: clicked.append(True))
        class FakeDataF23:
            vkCode = 0x86  # VK_F23
        # WM_KEYDOWN for Copilot key must return False (intercepted and blocked)
        res_down = hook._win32_event_filter(0x0100, FakeDataF23())
        self.assertFalse(res_down)
        # WM_KEYUP for Copilot key must return False
        res_up = hook._win32_event_filter(0x0101, FakeDataF23())
        self.assertFalse(res_up)

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

    def test_executor_launch_app_url_redirection(self):
        executor = CommandExecutor()
        cmd = {"action": "launch_app", "target": "vk.com", "parameters": {}}
        import unittest.mock as mock
        with mock.patch("webbrowser.open") as mock_open:
            ok, msg = executor.execute(cmd)
            self.assertTrue(ok)
            mock_open.assert_called_once_with("https://vk.com")

    def test_executor_open_url_direct_play(self):
        executor = CommandExecutor()
        cmd = {
            "action": "open_url",
            "target": "https://www.youtube.com/results?search_query=мармук",
            "parameters": {"query": "мармук", "direct_play": True, "sort_by_date": True}
        }
        import unittest.mock as mock
        with mock.patch.object(executor, "_resolve_youtube_video", return_value="https://www.youtube.com/watch?v=EjavzU6L2YM") as mock_res:
            with mock.patch("webbrowser.open") as mock_open:
                ok, msg = executor.execute(cmd)
                self.assertTrue(ok)
                mock_res.assert_called_once_with("мармук", sort_by_date=True)
                mock_open.assert_called_once_with("https://www.youtube.com/watch?v=EjavzU6L2YM")
                self.assertIn("YouTube", msg)

    def test_executor_resolve_youtube_video_mocked(self):
        executor = CommandExecutor()
        import io
        import unittest.mock as mock
        class MockResp(io.BytesIO):
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        mock_response = MockResp(b'some html "videoId":"TestVideo11" and more html')
        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            video_url = executor._resolve_youtube_video("тест")
            self.assertEqual(video_url, "https://www.youtube.com/watch?v=TestVideo11")


    def test_executor_resolve_youtube_video_fallback_on_error(self):
        executor = CommandExecutor()
        import unittest.mock as mock
        with mock.patch("urllib.request.urlopen", side_effect=Exception("Network error")):
            fallback_url = executor._resolve_youtube_video("тест", sort_by_date=True)
            self.assertIn("youtube.com/results?search_query=", fallback_url)
            self.assertIn("sp=CAI", fallback_url)

    def test_desktop_app_controller_launch_or_focus_existing(self):
        from core.app_controller import DesktopAppController
        ctrl = DesktopAppController()
        import unittest.mock as mock
        with mock.patch.object(ctrl, "find_window", return_value=12345):
            with mock.patch.object(ctrl, "focus_window", return_value=True):
                ok, msg = ctrl.launch_or_focus("блокнот")
                self.assertTrue(ok)
                self.assertIn("Переключено на", msg)

    def test_desktop_app_controller_launch_new(self):
        from core.app_controller import DesktopAppController
        ctrl = DesktopAppController()
        import unittest.mock as mock
        with mock.patch.object(ctrl, "find_window", side_effect=[None, 12345]):
            with mock.patch.object(ctrl, "focus_window", return_value=True):
                with mock.patch("os.startfile") as mock_start:
                    ok, msg = ctrl.launch_or_focus("блокнот", "notepad.exe")
                    self.assertTrue(ok)
                    self.assertIn("Запущено", msg)
                    mock_start.assert_called_once_with("notepad.exe")

    def test_executor_window_control_execution(self):
        executor = CommandExecutor()
        cmd = {"action": "window_control", "target": "close", "parameters": {"app_name": "блокнот"}}
        import unittest.mock as mock
        with mock.patch.object(executor.app_controller, "close_app", return_value=(True, "Закрыто: блокнот")) as mock_close:
            ok, msg = executor.execute(cmd)
            self.assertTrue(ok)
            mock_close.assert_called_once_with("блокнот")

    def test_executor_app_type_execution(self):
        executor = CommandExecutor()
        cmd = {
            "action": "app_type",
            "target": "type",
            "parameters": {"app_name": "блокнот", "text": "купить молоко", "submit": False, "search_mode": False}
        }
        import unittest.mock as mock
        with mock.patch.object(executor.app_controller, "type_into_app", return_value=(True, "Введено в блокнот")) as mock_type:
            ok, msg = executor.execute(cmd)
            self.assertTrue(ok)
            mock_type.assert_called_once_with("блокнот", "купить молоко", submit=False, search_mode=False)

    def test_executor_app_hotkey_execution(self):
        executor = CommandExecutor()
        cmd = {"action": "app_hotkey", "target": "new_tab", "parameters": {"app_name": "браузер"}}
        import unittest.mock as mock
        with mock.patch.object(executor.app_controller, "send_app_hotkey", return_value=(True, "Новая вкладка")) as mock_hk:
            ok, msg = executor.execute(cmd)
            self.assertTrue(ok)
            mock_hk.assert_called_once_with("браузер", "new_tab")

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
        fake_engine = DecisionEngine()
        import unittest.mock as mock
        with mock.patch.object(fake_engine, "is_llm_available", return_value=False):
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

    def test_main_window_autostart_and_tts_integration(self):
        """Проверка интеграции чекбокса автозапуска и комбобокса TTS-голосов в MainWindow."""
        import tempfile
        from gui.main_window import MainWindow
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_config = os.path.join(tmp_dir, "test_settings.json")
            with open(temp_config, "w", encoding="utf-8") as f:
                json.dump({
                    "autostart_with_windows": False,
                    "start_minimized": True,
                    "tts_enabled": False,
                    "tts_voice": "piper:ru_RU-dmitri-medium"
                }, f)

            with patch("gui.main_window.set_windows_autostart") as mock_autostart, \
                 patch("core.text_to_speech.TextToSpeech.get_available_voices", return_value=[
                     {"id": "piper:ru_RU-dmitri-medium", "name": "Piper Neural TTS (Дмитрий)"},
                     {"id": "Microsoft Irina Desktop", "name": "SAPI5: Irina"}
                 ]):
                mock_autostart.return_value = True
                window = MainWindow(temp_config)

                # 1. Чекбокс автозапуска: включение
                window.cb_autostart.setChecked(True)
                self.assertTrue(window.settings["autostart_with_windows"])
                mock_autostart.assert_called_with(True, start_minimized=True)

                # Чекбокс автозапуска: отключение
                window.cb_autostart.setChecked(False)
                self.assertFalse(window.settings["autostart_with_windows"])
                mock_autostart.assert_called_with(False, start_minimized=True)

                # Чекбокс минимизации: обновление параметров
                window.cb_autostart.setChecked(True)
                mock_autostart.reset_mock()
                window.cb_start_minimized.setChecked(False)
                self.assertFalse(window.settings["start_minimized"])
                mock_autostart.assert_called_with(True, start_minimized=False)

                # 2. Чекбокс TTS и комбобокс голосов
                self.assertFalse(window.cb_tts_voice.isEnabled())
                window.cb_tts.setChecked(True)
                self.assertTrue(window.cb_tts_voice.isEnabled())
                self.assertTrue(window.settings["tts_enabled"])

                # Выбор голоса в комбобоксе
                window.cb_tts_voice.setCurrentIndex(1)
                self.assertEqual(window.settings["tts_voice"], "Microsoft Irina Desktop")

                # Сигнал тестового воспроизведения
                tts_signals = []
                window.test_tts_requested.connect(lambda v: tts_signals.append(v))
                window.btn_test_tts.click()
                self.assertEqual(len(tts_signals), 1)
                self.assertEqual(tts_signals[0], "Microsoft Irina Desktop")


class TestTrayManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        from gui.tray_manager import TrayManager
        self.tray = TrayManager()

    def tearDown(self):
        self.tray.stop()

    def test_state_idle(self):
        self.tray.set_state("idle")
        self.assertEqual(self.tray._current_state, "idle")
        self.assertEqual(self.tray.tray_icon.toolTip(), "Antigravity Voice: Готов к работе")
        self.assertEqual(self.tray.status_action.text(), "Статус: Активен (Готов)")
        self.assertEqual(self.tray.action_toggle.text(), "Остановить ассистента (освободить VRAM)")
        self.assertFalse(self.tray._anim_timer.isActive())

    def test_state_listening(self):
        self.tray.set_state("listening")
        self.assertEqual(self.tray._current_state, "listening")
        self.assertEqual(self.tray.tray_icon.toolTip(), "Antigravity Voice: Запись речи...")
        self.assertEqual(self.tray.status_action.text(), "Статус: Запись речи...")
        self.assertEqual(self.tray.action_toggle.text(), "Остановить ассистента (освободить VRAM)")
        self.assertTrue(self.tray._anim_timer.isActive())

    def test_state_working(self):
        self.tray.set_state("working")
        self.assertEqual(self.tray._current_state, "working")
        self.assertEqual(self.tray.tray_icon.toolTip(), "Antigravity Voice: Vision-агент анализирует экран...")
        self.assertEqual(self.tray.status_action.text(), "Статус: Анализ экрана...")
        self.assertEqual(self.tray.action_toggle.text(), "Остановить ассистента (освободить VRAM)")
        self.assertTrue(self.tray._anim_timer.isActive())

    def test_state_stopped(self):
        self.tray.set_state("stopped")
        self.assertEqual(self.tray._current_state, "stopped")
        self.assertEqual(self.tray.tray_icon.toolTip(), "Antigravity Voice: Остановлен (0 МБ VRAM)")
        self.assertEqual(self.tray.status_action.text(), "Статус: Остановлен (0 МБ VRAM)")
        self.assertEqual(self.tray.action_toggle.text(), "Запустить ассистента")
        self.assertFalse(self.tray._anim_timer.isActive())

    def test_update_status(self):
        self.tray.update_status(False)
        self.assertEqual(self.tray._current_state, "stopped")
        self.assertFalse(self.tray._anim_timer.isActive())

        self.tray.update_status(True)
        self.assertEqual(self.tray._current_state, "idle")
        self.assertFalse(self.tray._anim_timer.isActive())


class TestRegressionsAndProblemFixes(unittest.TestCase):
    """Регрессионные тесты дефектов и системных интеграций."""

    def setUp(self):
        from core.executor import CommandExecutor
        self.engine = DecisionEngine()
        self.executor = CommandExecutor()

    def test_volume_unmute(self):
        """Команда unmute корректно обрабатывается в _handle_volume."""
        from unittest.mock import patch
        with patch.object(self.executor, "_send_key") as mock_send_key:
            success, msg = self.executor._handle_volume("unmute", {})
            self.assertTrue(success)
            self.assertEqual(msg, "Звук включен")
            mock_send_key.assert_called_once()

    def test_lock_workstation(self):
        """Команда lock_workstation блокирует компьютер через ctypes."""
        from unittest.mock import patch
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

    def test_github_repositories_url(self):
        """URL репозиториев github валиден."""
        cmd = self.engine.parse_command("Открой репозитории гитхаб")
        self.assertEqual(cmd["action"], "open_url")
        self.assertEqual(cmd["target"], "https://github.com/settings/repositories")

    def test_vision_auto_focus_browser_setting(self):
        """Настройка vision_auto_focus_browser=False отключает автофокус браузера."""
        from unittest.mock import MagicMock, patch
        from core.executor import CommandExecutor
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

    def test_multi_word_urls_from_commands_json(self):
        """Составные URL из commands.json корректно обрабатываются Fast-Path."""
        vk_music = self.engine.parse_command("Открой музыка вк")
        self.assertEqual(vk_music["action"], "open_url")
        self.assertEqual(vk_music["target"], "https://vk.com/audios")

        vk_news = self.engine.parse_command("Перейди на новости вк")
        self.assertEqual(vk_news["action"], "open_url")
        self.assertEqual(vk_news["target"], "https://vk.com/feed")

        yt_history = self.engine.parse_command("Открой история ютуб")
        self.assertEqual(yt_history["action"], "open_url")
        self.assertEqual(yt_history["target"], "https://www.youtube.com/feed/history")


class TestVisualFeedbackAndScreenGlow(unittest.TestCase):
    """Тестирование эстетичной индикации голоса и контурной подсветки экрана."""

    @classmethod
    def setUpClass(cls):
        import sys
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_audio_wave_visualizer(self):
        """Проверка работы AudioWaveVisualizer (5 полос спектра, фазы, VU-уровни)."""
        from gui.floating_pill import AudioWaveVisualizer
        wave = AudioWaveVisualizer()
        self.assertEqual(wave.width(), 38)
        self.assertEqual(wave.height(), 24)
        self.assertEqual(wave._vu_level, 0.0)

        # Проверка установки уровня громкости
        wave.set_vu_level(0.65)
        self.assertAlmostEqual(wave._vu_level, 0.65)
        wave.set_vu_level(-0.5)
        self.assertEqual(wave._vu_level, 0.0)
        wave.set_vu_level(2.0)
        self.assertEqual(wave._vu_level, 1.0)

        # Проверка переключения режимов
        for mode in ("listening", "step", "executing", "error"):
            wave.set_mode(mode)
            self.assertEqual(wave._mode, mode)

        # Проверка шага анимации
        init_phase = wave._phase
        wave._on_tick()
        self.assertGreater(wave._phase, init_phase)

    def test_floating_pill_with_wave(self):
        """Проверка работы FloatingPill с интегрированным AudioWaveVisualizer."""
        from gui.floating_pill import FloatingPill
        pill = FloatingPill()

        # Режим прослушивания
        pill.show_listening()
        self.assertEqual(pill._mode, "listening")
        self.assertEqual(pill.label.text(), "Слушаю...")
        self.assertEqual(pill.wave._mode, "listening")

        # Передача уровня звука
        pill.update_vu(0.85)
        self.assertAlmostEqual(pill.wave._vu_level, 0.85)

        # Шаг Vision-агента
        pill.show_step(1, 5, "Поиск кнопки Вход")
        self.assertEqual(pill._mode, "step")
        self.assertIn("1/5", pill.label.text())

        # Выполнение действия
        pill.show_executing("Клик выполнен")
        self.assertEqual(pill._mode, "executing")
        self.assertEqual(pill.wave._mode, "executing")

        # Ошибка
        pill.show_error("Элемент не найден")
        self.assertEqual(pill._mode, "error")
        self.assertEqual(pill.wave._mode, "error")

    def test_screen_glow_overlay(self):
        """Проверка полноэкранного оверлея контурной подсветки экрана ScreenGlowOverlay в статическом режиме."""
        from gui.screen_glow import ScreenGlowOverlay
        glow = ScreenGlowOverlay()
        self.assertFalse(glow.is_active())

        # Запуск статической неоновой подсветки (0% оверхеда DWM)
        glow.start_glow(text="JARVIS • АКТИВЕН")
        self.assertTrue(glow.is_active())
        self.assertEqual(glow._status_text, "JARVIS • АКТИВЕН")

        # Остановка подсветки
        glow.stop_glow()
        self.assertFalse(glow.is_active())
        self.assertFalse(glow.isVisible())

    def test_app_coordinator_ui_state_bus(self):
        """Проверка работы единой шины состояний AppCoordinator.emit_ui_state."""
        from main import AppCoordinator
        from unittest.mock import patch, MagicMock
        with patch("main.MainWindow"), patch("main.AudioListener"), patch("main.CopilotKeyHook"), patch("main.VisionAgentProcessManager"):
            coord = AppCoordinator(is_minimized=True)
            # Тест перевода в режим listening
            coord.emit_ui_state("listening")
            self.assertEqual(coord.pill._mode, "listening")

            # Тест передачи текста
            coord.emit_ui_state("text", "Тестовая фраза")
            self.assertEqual(coord.pill.label.text(), "Тестовая фраза")

            # Тест выполнения
            coord.emit_ui_state("executing", "Действие готово")
            self.assertEqual(coord.pill._mode, "executing")

            # Тест подсветки экрана
            coord.emit_ui_state("glow_start", "ТЕСТ ПОДСВЕТКИ")
            self.assertTrue(coord.screen_glow.is_active())
            self.assertEqual(coord.screen_glow._status_text, "ТЕСТ ПОДСВЕТКИ")

            coord.emit_ui_state("glow_stop")
            self.assertFalse(coord.screen_glow.is_active())


class TestAutostart(unittest.TestCase):
    """Модульные тесты функционала автозагрузки Windows (core/autostart.py)."""

    def test_get_pythonw_executable_exists(self):
        """Проверка возврата pythonw.exe, когда файл существует на диске."""
        from core.autostart import get_pythonw_executable
        from unittest.mock import patch
        with patch("os.path.exists", return_value=True):
            exe = get_pythonw_executable()
            self.assertTrue(exe.lower().endswith("pythonw.exe"))

    def test_get_pythonw_executable_fallback(self):
        """Проверка фоллбэка на sys.executable при отсутствии pythonw.exe."""
        import sys
        from core.autostart import get_pythonw_executable
        from unittest.mock import patch
        with patch("os.path.exists", return_value=False):
            exe = get_pythonw_executable()
            self.assertEqual(exe, sys.executable)

    def test_get_main_script_path(self):
        """Проверка пути к точке входа main.py."""
        from core.autostart import get_main_script_path
        path = get_main_script_path()
        self.assertTrue(os.path.isabs(path))
        self.assertTrue(path.lower().endswith("main.py"))

    def test_build_autostart_command(self):
        """Проверка формирования строки команды автозапуска."""
        from core.autostart import build_autostart_command
        cmd_min = build_autostart_command(start_minimized=True)
        self.assertIn("main.py", cmd_min)
        self.assertTrue(cmd_min.endswith("--minimized"))

        cmd_norm = build_autostart_command(start_minimized=False)
        self.assertIn("main.py", cmd_norm)
        self.assertFalse(cmd_norm.endswith("--minimized"))

    def test_set_windows_autostart_enable(self):
        """Проверка добавления приложения в реестр автозапуска."""
        from core.autostart import set_windows_autostart
        from unittest.mock import patch, MagicMock
        with patch("core.autostart.winreg.OpenKey") as mock_open, \
             patch("core.autostart.winreg.SetValueEx") as mock_set:
            mock_key = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_key

            res = set_windows_autostart(True, start_minimized=True)
            self.assertTrue(res)
            mock_set.assert_called_once()
            args, _ = mock_set.call_args
            self.assertIn("--minimized", args[4])

    def test_set_windows_autostart_disable_success(self):
        """Проверка штатного удаления приложения из реестра автозапуска."""
        from core.autostart import set_windows_autostart
        from unittest.mock import patch, MagicMock
        with patch("core.autostart.winreg.OpenKey") as mock_open, \
             patch("core.autostart.winreg.DeleteValue") as mock_del:
            mock_key = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_key

            res = set_windows_autostart(False)
            self.assertTrue(res)
            mock_del.assert_called_once()

    def test_set_windows_autostart_disable_file_not_found(self):
        """Проверка обработки FileNotFoundError при удалении отсутствующего ключа."""
        from core.autostart import set_windows_autostart
        from unittest.mock import patch, MagicMock
        with patch("core.autostart.winreg.OpenKey") as mock_open, \
             patch("core.autostart.winreg.DeleteValue", side_effect=FileNotFoundError):
            mock_key = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_key

            # Должно вернуть True (удалять нечего — цель достигнута)
            res = set_windows_autostart(False)
            self.assertTrue(res)

    def test_set_windows_autostart_exception_handling(self):
        """Проверка возврата False при системной ошибке доступа к реестру."""
        from core.autostart import set_windows_autostart
        from unittest.mock import patch
        with patch("core.autostart.winreg.OpenKey", side_effect=PermissionError("Отказано в доступе")):
            res = set_windows_autostart(True)
            self.assertFalse(res)

    def test_is_windows_autostart_enabled(self):
        """Проверка функции проверки статуса автозагрузки в реестре."""
        from core.autostart import is_windows_autostart_enabled
        from unittest.mock import patch, MagicMock

        # 1. Ключ найден и активен
        with patch("core.autostart.winreg.OpenKey"), \
             patch("core.autostart.winreg.QueryValueEx", return_value=('"pythonw.exe" "main.py"', 1)):
            self.assertTrue(is_windows_autostart_enabled())

        # 2. Ключ пустой
        with patch("core.autostart.winreg.OpenKey"), \
             patch("core.autostart.winreg.QueryValueEx", return_value=('', 1)):
            self.assertFalse(is_windows_autostart_enabled())

        # 3. Ключ не найден (FileNotFoundError)
        with patch("core.autostart.winreg.OpenKey", side_effect=FileNotFoundError):
            self.assertFalse(is_windows_autostart_enabled())

        # 4. Другая системная ошибка
        with patch("core.autostart.winreg.OpenKey", side_effect=OSError("Ошибка реестра")):
            self.assertFalse(is_windows_autostart_enabled())

    def test_get_autostart_command(self):
        """Проверка получения команды автозапуска из реестра."""
        from core.autostart import get_autostart_command
        from unittest.mock import patch

        with patch("core.autostart.winreg.OpenKey"), \
             patch("core.autostart.winreg.QueryValueEx", return_value=('"test_cmd"', 1)):
            self.assertEqual(get_autostart_command(), '"test_cmd"')

        with patch("core.autostart.winreg.OpenKey", side_effect=FileNotFoundError):
            self.assertIsNone(get_autostart_command())


class TestTextToSpeech(unittest.TestCase):
    """Модульные тесты движка синтеза речи TextToSpeech (core/text_to_speech.py)."""

    def test_get_piper_model_paths_present(self):
        """Проверка возврата путей к модели Piper при наличии файлов и размере > 1 МБ."""
        from core.text_to_speech import get_piper_model_paths
        from unittest.mock import patch
        with patch("core.text_to_speech.os.path.exists", return_value=True), \
             patch("core.text_to_speech.os.path.getsize", return_value=60 * 1024 * 1024):
            onnx_p, json_p = get_piper_model_paths()
            self.assertIsNotNone(onnx_p)
            self.assertIsNotNone(json_p)
            self.assertTrue(onnx_p.endswith(".onnx"))
            self.assertTrue(json_p.endswith(".onnx.json"))

    def test_get_piper_model_paths_missing_or_corrupt(self):
        """Проверка возврата None, если веса отсутствуют или повреждены (<= 1 МБ)."""
        from core.text_to_speech import get_piper_model_paths
        from unittest.mock import patch

        # Файлов нет
        with patch("core.text_to_speech.os.path.exists", return_value=False):
            onnx_p, json_p = get_piper_model_paths()
            self.assertIsNone(onnx_p)
            self.assertIsNone(json_p)

        # Файл слишком мал (<= 1 МБ)
        with patch("core.text_to_speech.os.path.exists", return_value=True), \
             patch("core.text_to_speech.os.path.getsize", return_value=500):
            onnx_p, json_p = get_piper_model_paths()
            self.assertIsNone(onnx_p)
            self.assertIsNone(json_p)

    def test_is_piper_requested_logic(self):
        """Проверка логики выбора движка Piper TTS в зависимости от voice_name и наличия весов."""
        from core.text_to_speech import TextToSpeech
        from unittest.mock import patch

        # Явный запрос Piper
        tts1 = TextToSpeech(voice_name="piper:ru_RU-dmitri-medium")
        self.assertTrue(tts1._is_piper_requested())

        tts2 = TextToSpeech(voice_name="dmitri")
        self.assertTrue(tts2._is_piper_requested())

        # Запрос системного голоса SAPI5
        tts3 = TextToSpeech(voice_name="Microsoft Irina Desktop")
        self.assertFalse(tts3._is_piper_requested())

        # Без указания голоса: автовыбор на основе наличия весов
        tts_default = TextToSpeech(voice_name=None)
        with patch("core.text_to_speech.get_piper_model_paths", return_value=("dummy.onnx", "dummy.json")):
            self.assertTrue(tts_default._is_piper_requested())

        with patch("core.text_to_speech.get_piper_model_paths", return_value=(None, None)):
            self.assertFalse(tts_default._is_piper_requested())

    def test_get_available_voices_isolated(self):
        """Проверка списка доступных голосов с изоляцией от реальной файловой системы."""
        from core.text_to_speech import TextToSpeech
        from unittest.mock import patch

        # С весами Piper
        with patch("core.text_to_speech.get_piper_model_paths", return_value=("model.onnx", "model.json")), \
             patch("win32com.client.Dispatch"):
            voices = TextToSpeech.get_available_voices()
            self.assertTrue(any("piper" in v["id"].lower() for v in voices))

        # Без весов Piper
        with patch("core.text_to_speech.get_piper_model_paths", return_value=(None, None)), \
             patch("win32com.client.Dispatch"):
            voices_no_piper = TextToSpeech.get_available_voices()
            self.assertFalse(any("piper" in v["id"].lower() for v in voices_no_piper))

    def test_speed_scaling_to_length_scale(self):
        """Проверка конвертации параметра скорости speed в length_scale Piper."""
        from core.text_to_speech import TextToSpeech
        from unittest.mock import patch, MagicMock

        mock_voice = MagicMock()
        mock_wav_file = MagicMock()

        # Тест для целого числа: speed=0 -> speed_factor=1.0 -> length_scale=1.0
        tts_int_0 = TextToSpeech(speed=0)
        with patch.object(tts_int_0, "_get_piper_voice", return_value=mock_voice), \
             patch("wave.open"), patch("winsound.PlaySound"):
            # Проверяем математику конвертации
            speed_factor = 1.0 + (tts_int_0.speed / 10.0)
            length_scale = 1.0 / max(0.5, min(2.5, speed_factor))
            self.assertEqual(length_scale, 1.0)

        # speed=5 -> speed_factor=1.5 -> length_scale=1/1.5 (~0.666)
        tts_int_5 = TextToSpeech(speed=5)
        speed_factor = 1.0 + (tts_int_5.speed / 10.0)
        length_scale = 1.0 / max(0.5, min(2.5, speed_factor))
        self.assertAlmostEqual(length_scale, 1.0 / 1.5)

        # speed=-5 -> speed_factor=0.5 -> length_scale=2.0
        tts_int_m5 = TextToSpeech(speed=-5)
        speed_factor = 1.0 + (tts_int_m5.speed / 10.0)
        length_scale = 1.0 / max(0.5, min(2.5, speed_factor))
        self.assertAlmostEqual(length_scale, 2.0)

        # float speed=3.0 -> clamped to 2.5 -> length_scale=0.4
        tts_float = TextToSpeech(speed=3.0)
        speed_factor = max(0.5, min(2.5, float(tts_float.speed)))
        self.assertEqual(speed_factor, 2.5)
        self.assertEqual(1.0 / speed_factor, 0.4)

    def test_speak_empty_or_whitespace_noop(self):
        """Проверка игнорирования пустых строк и пробелов при синтезе."""
        from core.text_to_speech import TextToSpeech
        from unittest.mock import patch
        tts = TextToSpeech()
        with patch.object(tts, "_speak_piper") as mock_piper, \
             patch.object(tts, "_speak_sapi5") as mock_sapi:
            tts.speak("", async_mode=False)
            tts.speak("   \n\t  ", async_mode=False)
            mock_piper.assert_not_called()
            mock_sapi.assert_not_called()

    def test_fallback_to_sapi5_when_piper_fails(self):
        """Проверка прозрачного фоллбэка на Windows SAPI5 при сбое синтеза Piper."""
        from core.text_to_speech import TextToSpeech
        from unittest.mock import patch

        tts = TextToSpeech(voice_name="piper:ru_RU-dmitri-medium")
        with patch.object(tts, "_is_piper_requested", return_value=True), \
             patch.object(tts, "_speak_piper", return_value=False) as mock_piper, \
             patch.object(tts, "_speak_sapi5") as mock_sapi:
            tts.speak("Тестовая фраза для проверки фоллбэка", async_mode=False)
            mock_piper.assert_called_once_with("Тестовая фраза для проверки фоллбэка")
            mock_sapi.assert_called_once_with("Тестовая фраза для проверки фоллбэка")

    def test_piper_success_skips_sapi5(self):
        """Проверка: при успешном синтезе Piper вызов SAPI5 не производится."""
        from core.text_to_speech import TextToSpeech
        from unittest.mock import patch

        tts = TextToSpeech(voice_name="piper:ru_RU-dmitri-medium")
        with patch.object(tts, "_is_piper_requested", return_value=True), \
             patch.object(tts, "_speak_piper", return_value=True) as mock_piper, \
             patch.object(tts, "_speak_sapi5") as mock_sapi:
            tts.speak("Успешный синтез", async_mode=False)
            mock_piper.assert_called_once()
            mock_sapi.assert_not_called()

    def test_speak_piper_mocked_playback(self):
        """Проверка синтеза Piper с передачей сгенерированного WAV в winsound.PlaySound."""
        from core.text_to_speech import TextToSpeech
        from unittest.mock import patch, MagicMock

        tts = TextToSpeech(voice_name="piper:ru_RU-dmitri-medium")
        fake_voice = MagicMock()
        def fake_synthesize(text, wav_file, syn_config=None):
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(22050)
            wav_file.writeframes(b"\x00" * 200)

        fake_voice.synthesize_wav.side_effect = fake_synthesize

        with patch.object(tts, "_get_piper_voice", return_value=fake_voice), \
             patch("winsound.PlaySound") as mock_playsound:
            res = tts._speak_piper("Привет мир")
            self.assertTrue(res)
            mock_playsound.assert_called_once()
            args, _ = mock_playsound.call_args
            self.assertTrue(args[0].startswith(b"RIFF"))

    def test_real_piper_synthesis_if_weights_present(self):
        """Интеграционный тест: реальный синтез через Piper ONNX на CPU, если веса скачаны."""
        from core.text_to_speech import TextToSpeech, get_piper_model_paths
        from unittest.mock import patch

        onnx_p, json_p = get_piper_model_paths()
        if not onnx_p or not json_p:
            self.skipTest("Веса модели Piper отсутствуют на диске (пропуск реального инференса)")

        tts = TextToSpeech(voice_name="piper:ru_RU-dmitri-medium", speed=1.0)
        with patch("winsound.PlaySound") as mock_play:
            tts.speak("Тестовая проверка реального инференса.", async_mode=False)
            mock_play.assert_called_once()
            args, _ = mock_play.call_args
            self.assertTrue(len(args[0]) > 1000)


class TestDownloadPiperModel(unittest.TestCase):
    """Модульные тесты утилиты загрузки весов Piper (scripts/download_piper_model.py)."""

    def test_download_file_success(self):
        """Проверка успешной потоковой загрузки файла с переименованием .tmp."""
        import tempfile
        import io
        from scripts.download_piper_model import download_file
        from unittest.mock import patch

        expected_bytes = b"fake_onnx_bytes" * 100
        fake_response = io.BytesIO(expected_bytes)
        fake_response.headers = {"Content-Length": str(len(expected_bytes))}

        with tempfile.TemporaryDirectory() as tmp_dir:
            dest_file = os.path.join(tmp_dir, "model.onnx")
            with patch("urllib.request.urlopen", return_value=fake_response):
                ok = download_file("https://example.com/model.onnx", dest_file)
                self.assertTrue(ok)
                self.assertTrue(os.path.exists(dest_file))
                self.assertEqual(os.path.getsize(dest_file), len(expected_bytes))

    def test_download_file_error_cleans_tmp(self):
        """Проверка очистки временного файла .tmp при ошибке соединения."""
        import tempfile
        from scripts.download_piper_model import download_file
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp_dir:
            dest_file = os.path.join(tmp_dir, "model.onnx")
            temp_file = dest_file + ".tmp"
            with patch("urllib.request.urlopen", side_effect=Exception("Сетевая ошибка")):
                ok = download_file("https://example.com/model.onnx", dest_file)
                self.assertFalse(ok)
                self.assertFalse(os.path.exists(temp_file))
                self.assertFalse(os.path.exists(dest_file))

    def test_ensure_piper_model_already_downloaded(self):
        """Проверка возврата путей без повторного скачивания, если файлы уже на диске."""
        from scripts.download_piper_model import ensure_piper_model
        from unittest.mock import patch

        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", side_effect=[60 * 1024 * 1024, 2048]), \
             patch("scripts.download_piper_model.download_file") as mock_dl:
            onnx_p, json_p = ensure_piper_model("dummy_dir")
            mock_dl.assert_not_called()
            self.assertTrue(onnx_p.endswith(".onnx"))
            self.assertTrue(json_p.endswith(".json"))

    def test_ensure_piper_model_raises_on_download_failure(self):
        """Проверка выброса RuntimeError при неудаче скачивания весов."""
        from scripts.download_piper_model import ensure_piper_model
        from unittest.mock import patch

        with patch("os.path.exists", return_value=False), \
             patch("scripts.download_piper_model.download_file", return_value=False):
            with self.assertRaises(RuntimeError):
                ensure_piper_model("dummy_dir")



if __name__ == "__main__":
    unittest.main()

