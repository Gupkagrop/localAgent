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

    def test_youtube_search_complex(self):
        res = self.engine.parse_command("Открой, пожалуйста, ютубчик и включи там видео мармука.")
        self.assertEqual(res["action"], "open_url")
        self.assertIn("youtube.com/results?search_query=", res["target"])
        self.assertIn("мармука", res["target"])

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
        # Проверка намерения прямого воспроизведения последнего ролика
        res = self.engine.parse_command("На ютуб включить последнее видео мармука")
        self.assertEqual(res["action"], "open_url")
        self.assertTrue(res["parameters"].get("direct_play"))
        self.assertTrue(res["parameters"].get("sort_by_date"))
        self.assertIn("мармук", res["parameters"]["query"])
        self.assertIn("sp=CAI", res["target"])

    def test_youtube_direct_play_without_keyword_youtube(self):
        # Проверка включения ролика без явного произнесения слова «ютуб»
        res = self.engine.parse_command("Включи последнее видео мармука")
        self.assertEqual(res["action"], "open_url")
        self.assertTrue(res["parameters"].get("direct_play"))
        self.assertTrue(res["parameters"].get("sort_by_date"))
        self.assertIn("мармук", res["parameters"]["query"])

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
        # Проверка универсального поиска на Кинопоиске
        res = self.engine.parse_command("На Кинопоиске найди фильм Начало")
        self.assertEqual(res["action"], "chrome_cdp")
        self.assertEqual(res["parameters"]["site"], "кинопоиск")
        self.assertEqual(res["parameters"]["query"], "фильм Начало")

    def test_universal_site_search_avito(self):
        # Проверка универсального поиска на Авито
        res = self.engine.parse_command("Найди на Авито велосипед")
        self.assertEqual(res["action"], "chrome_cdp")
        self.assertEqual(res["parameters"]["site"], "авито")
        self.assertEqual(res["parameters"]["query"], "велосипед")

    def test_universal_site_search_wikipedia(self):
        # Проверка универсального поиска в Википедии
        res = self.engine.parse_command("В Википедии найди квантовую физику")
        self.assertEqual(res["action"], "chrome_cdp")
        self.assertEqual(res["parameters"]["site"], "википедия")
        self.assertEqual(res["parameters"]["query"], "квантовую физику")

    def test_universal_site_search_ozon(self):
        # Проверка универсального поиска на Озоне
        res = self.engine.parse_command("На Озоне найди кофеварку")
        self.assertEqual(res["action"], "chrome_cdp")
        self.assertEqual(res["parameters"]["site"], "озон")
        self.assertEqual(res["parameters"]["query"], "кофеварку")

    def test_universal_site_search_wildberries(self):
        # Проверка универсального поиска на Wildberries
        res = self.engine.parse_command("На wildberries найди кроссовки")
        self.assertEqual(res["action"], "chrome_cdp")
        self.assertEqual(res["parameters"]["site"], "wildberries")
        self.assertEqual(res["parameters"]["query"], "кроссовки")

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
        # Проверка поиска внутри приложения
        res = self.engine.parse_command("В телеграме найди проект")
        self.assertEqual(res["action"], "app_type")
        self.assertEqual(res["target"], "search")
        self.assertEqual(res["parameters"]["app_name"], "телеграм")
        self.assertTrue(res["parameters"]["search_mode"])

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

    def test_chrome_cdp_controller_known_pattern(self):
        import urllib.parse
        from core.chrome_cdp import ChromeCDPController
        cdp = ChromeCDPController()
        ok, msg, url = cdp.execute_site_search("кинопоиск", "Начало")
        self.assertTrue(ok)
        self.assertIn("kinopoisk.ru", url)
        self.assertIn("Начало", urllib.parse.unquote(url))


    def test_chrome_cdp_controller_is_available_mocked(self):
        from core.chrome_cdp import ChromeCDPController
        cdp = ChromeCDPController()
        import io
        import unittest.mock as mock
        class MockResp:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        with mock.patch("urllib.request.urlopen", return_value=MockResp()):
            self.assertTrue(cdp.is_cdp_available())

    def test_executor_chrome_cdp_execution(self):
        executor = CommandExecutor()
        cmd = {
            "action": "chrome_cdp",
            "target": "search",
            "parameters": {"site": "авито", "query": "велосипед", "click_first": False}
        }
        import unittest.mock as mock
        with mock.patch("webbrowser.open") as mock_open:
            ok, msg = executor.execute(cmd)
            self.assertTrue(ok)
            mock_open.assert_called_once()
            args, _ = mock_open.call_args
            self.assertIn("avito.ru", args[0])

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
