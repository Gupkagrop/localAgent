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
        self.assertTrue(self.engine.is_llm_available())

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

if __name__ == "__main__":
    unittest.main()
