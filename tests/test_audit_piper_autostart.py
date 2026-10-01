"""
Аудит практической работоспособности Piper TTS и автозапуска в Antigravity Voice Assistant.
"""
import io
import os
import sys
import wave
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Обеспечиваем корректную кодировку вывода на Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

class TestPiperAndAutostartAudit(unittest.TestCase):
    """Набор тестов для аудита компонентов Piper TTS и Windows Autostart."""

    def test_01_piper_files_and_weights_validity(self):
        """Проверка наличия и валидности весов ONNX и конфигурации JSON."""
        tts_dir = os.path.join(PROJECT_DIR, "models", "tts")
        onnx_file = os.path.join(tts_dir, "ru_RU-dmitri-medium.onnx")
        json_file = os.path.join(tts_dir, "ru_RU-dmitri-medium.onnx.json")

        self.assertTrue(os.path.exists(onnx_file), f"Файл весов не найден: {onnx_file}")
        self.assertTrue(os.path.exists(json_file), f"Файл конфига не найден: {json_file}")

        onnx_size = os.path.getsize(onnx_file)
        json_size = os.path.getsize(json_file)
        print(f"\n[Test 1] Веса ONNX: {onnx_size / (1024 * 1024):.2f} МБ")
        print(f"[Test 1] JSON конфиг: {json_size} байт")

        # Размер ONNX модели dmitri-medium ~60.27 МБ
        self.assertGreater(onnx_size, 50 * 1024 * 1024, "Размер ONNX модели меньше 50 МБ!")
        self.assertGreater(json_size, 500, "Размер JSON конфига меньше 500 байт!")

        # Чтение и валидация JSON структуры
        with open(json_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        self.assertIn("audio", cfg, "В JSON конфиге отсутствует секция 'audio'")
        sample_rate = cfg["audio"].get("sample_rate")
        self.assertEqual(sample_rate, 22050, f"Ожидался sample_rate 22050, получено: {sample_rate}")
        print(f"[Test 1] Частота дискретизации модели: {sample_rate} Гц")
        print(f"[Test 1] Espeak voice: {cfg.get('espeak', {}).get('voice')}")

        # Проверка ONNX графа через onnxruntime
        import onnxruntime as ort
        sess = ort.InferenceSession(onnx_file, providers=["CPUExecutionProvider"])
        input_names = [inp.name for inp in sess.get_inputs()]
        output_names = [out.name for out in sess.get_outputs()]
        print(f"[Test 1] ONNX inputs: {input_names}")
        print(f"[Test 1] ONNX outputs: {output_names}")
        self.assertIn("input", input_names)
        self.assertIn("output", output_names)

    def test_02_piper_voice_load_and_synthesize(self):
        """Проверка загрузки PiperVoice и реального синтеза русской речи."""
        from piper import PiperVoice
        from piper.config import SynthesisConfig
        from core.text_to_speech import TextToSpeech, get_piper_model_paths

        onnx_path, json_path = get_piper_model_paths()
        self.assertIsNotNone(onnx_path, "get_piper_model_paths вернул None для ONNX")
        self.assertIsNotNone(json_path, "get_piper_model_paths вернул None для JSON")

        # Загрузка PiperVoice
        voice = PiperVoice.load(onnx_path, json_path, use_cuda=False)
        self.assertIsNotNone(voice, "PiperVoice.load вернул None")
        print(f"\n[Test 2] PiperVoice успешно загружен в память CPU.")

        # Синтез тестовой фразы
        test_text = "Джарвис готов к работе. Все системы функционируют штатно."
        wav_io = io.BytesIO()
        syn_config = SynthesisConfig(length_scale=1.0)
        with wave.open(wav_io, "wb") as wav_out:
            voice.synthesize_wav(test_text, wav_out, syn_config=syn_config)

        wav_bytes = wav_io.getvalue()
        self.assertGreater(len(wav_bytes), 10000, "Размер сгенерированного WAV слишком мал!")
        
        # Проверка параметров WAV
        wav_io.seek(0)
        with wave.open(wav_io, "rb") as r:
            channels = r.getnchannels()
            sampwidth = r.getsampwidth()
            framerate = r.getframerate()
            frames = r.getnframes()
            duration = frames / framerate
            print(f"[Test 2] Синтезировано аудио: {duration:.2f} сек, {framerate} Гц, {channels} кан., {sampwidth*8}-бит PCM, размер: {len(wav_bytes)} байт")
            self.assertEqual(channels, 1)
            self.assertEqual(sampwidth, 2)
            self.assertEqual(framerate, 22050)
            self.assertGreater(duration, 1.5)

        # Проверка класса TextToSpeech
        tts = TextToSpeech(voice_name="piper:ru_RU-dmitri-medium", speed=1.0)
        self.assertTrue(tts._is_piper_requested(), "_is_piper_requested должно вернуть True")

        voices = TextToSpeech.get_available_voices()
        piper_in_voices = any(v["id"] == "piper:ru_RU-dmitri-medium" for v in voices)
        print(f"[Test 2] Доступных голосов обнаружено: {len(voices)}")
        self.assertTrue(piper_in_voices, "Piper voice отсутствует в get_available_voices()")

        with patch("winsound.PlaySound") as mock_playsound:
            success = tts._speak_piper("Тест интеграции TextToSpeech.")
            self.assertTrue(success, "_speak_piper вернул False")
            self.assertTrue(mock_playsound.called, "winsound.PlaySound не был вызван")
            played_bytes = mock_playsound.call_args[0][0]
            self.assertGreater(len(played_bytes), 5000)
            print(f"[Test 2] TextToSpeech._speak_piper успешно передал {len(played_bytes)} байт в winsound.")

    def test_03_autostart_functions_and_registry(self):
        """Проверка генерации команд, поиска pythonw.exe и работы с реестром Windows."""
        from core.autostart import (
            get_pythonw_executable,
            get_main_script_path,
            build_autostart_command,
            set_windows_autostart,
            is_windows_autostart_enabled,
            get_autostart_command
        )

        pythonw_path = get_pythonw_executable()
        print(f"\n[Test 3] Путь к pythonw: {pythonw_path}")
        self.assertTrue(os.path.exists(pythonw_path), f"Файл не существует: {pythonw_path}")
        self.assertTrue(pythonw_path.lower().endswith("pythonw.exe") or pythonw_path.lower().endswith("python.exe"))

        main_path = get_main_script_path()
        print(f"[Test 3] Путь к main.py: {main_path}")
        self.assertTrue(os.path.exists(main_path), f"main.py не существует: {main_path}")

        cmd_min = build_autostart_command(start_minimized=True)
        cmd_norm = build_autostart_command(start_minimized=False)
        print(f"[Test 3] Команда автозапуска (minimized): {cmd_min}")
        print(f"[Test 3] Команда автозапуска (normal): {cmd_norm}")

        self.assertIn("--minimized", cmd_min)
        self.assertNotIn("--minimized", cmd_norm)
        self.assertIn(pythonw_path, cmd_min)
        self.assertIn(main_path, cmd_min)

        # Тестирование записи, чтения и удаления в реестре с изоляцией от системного реестра
        test_app_key = "AntigravityVoice_UnitTestAudit"
        fake_registry: dict[str, tuple[str, int]] = {}

        class FakeKey:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        def fake_open_key(key, sub_key, reserved=0, access=0):
            return FakeKey()

        def fake_set_value_ex(key, name, reserved, reg_type, value):
            fake_registry[name] = (value, reg_type)

        def fake_query_value_ex(key, name):
            if name not in fake_registry:
                raise FileNotFoundError(f"Ключ {name} не найден")
            return fake_registry[name]

        def fake_delete_value(key, name):
            if name not in fake_registry:
                raise FileNotFoundError(f"Ключ {name} не найден")
            del fake_registry[name]

        with patch("core.autostart.winreg.OpenKey", side_effect=fake_open_key), \
             patch("core.autostart.winreg.SetValueEx", side_effect=fake_set_value_ex), \
             patch("core.autostart.winreg.QueryValueEx", side_effect=fake_query_value_ex), \
             patch("core.autostart.winreg.DeleteValue", side_effect=fake_delete_value):

            # 1. Запись True + minimized
            ok = set_windows_autostart(True, app_name=test_app_key, start_minimized=True)
            self.assertTrue(ok, "set_windows_autostart(True) вернул False")
            self.assertTrue(is_windows_autostart_enabled(app_name=test_app_key))
            reg_val = get_autostart_command(app_name=test_app_key)
            self.assertEqual(reg_val, cmd_min)
            print(f"[Test 3] Виртуальная запись в реестр HKCU Run успешна: {reg_val}")

            # 2. Обновление флага minimized=False
            ok = set_windows_autostart(True, app_name=test_app_key, start_minimized=False)
            self.assertTrue(ok)
            reg_val = get_autostart_command(app_name=test_app_key)
            self.assertEqual(reg_val, cmd_norm)
            print(f"[Test 3] Обновление параметра в реестре успешно: {reg_val}")

            # 3. Удаление
            ok = set_windows_autostart(False, app_name=test_app_key)
            self.assertTrue(ok, "set_windows_autostart(False) вернул False")
            self.assertFalse(is_windows_autostart_enabled(app_name=test_app_key))
            self.assertIsNone(get_autostart_command(app_name=test_app_key))
            print("[Test 3] Удаление параметра из реестра подтверждено.")

    def test_04_gui_signals_and_settings_integration(self):
        """Проверка связки сигналов в MainWindow: settings.json, автозапуск, смена голоса."""
        from PyQt6.QtWidgets import QApplication
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication.instance() or QApplication(["AntigravityAuditTest"])

        from gui.main_window import MainWindow

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_config = os.path.join(tmp_dir, "test_settings.json")
            initial_data = {
                "autostart_with_windows": False,
                "start_minimized": True,
                "tts_enabled": True,
                "tts_voice": "piper:ru_RU-dmitri-medium",
                "tts_speed": 1.0
            }
            with open(temp_config, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, ensure_ascii=False)

            with patch("gui.main_window.set_windows_autostart") as mock_autostart:
                mock_autostart.return_value = True

                win = MainWindow(config_path=temp_config)

                emitted_events = []
                win.settings_changed.connect(lambda s: emitted_events.append(dict(s)))

                # 1. Проверяем переключение чекбокса автозапуска
                print("\n[Test 4] Тестирование переключения автозапуска в GUI...")
                emitted_events.clear()
                mock_autostart.reset_mock()

                win.cb_autostart.setChecked(True)

                self.assertTrue(win.settings["autostart_with_windows"])
                mock_autostart.assert_called_once_with(True, start_minimized=True)
                self.assertGreaterEqual(len(emitted_events), 1)

                with open(temp_config, "r", encoding="utf-8") as f:
                    saved_cfg = json.load(f)
                self.assertTrue(saved_cfg["autostart_with_windows"])
                print("[Test 4] Чекбокс автозапуска обновил настройки, файл на диске и вызвал set_windows_autostart.")

                # 2. Проверяем смену голоса TTS
                print("[Test 4] Тестирование смены голоса в комбобоксе...")
                emitted_events.clear()
                items_count = win.cb_tts_voice.count()
                self.assertGreaterEqual(items_count, 1, "Комбобокс голосов пуст!")

                # Имитируем переключение на другой индекс или явный вызов _on_tts_voice_selected
                if items_count > 1:
                    target_idx = 1 if win.cb_tts_voice.currentIndex() == 0 else 0
                    target_id = win.cb_tts_voice.itemData(target_idx)
                    win.cb_tts_voice.setCurrentIndex(target_idx)
                else:
                    target_id = "Microsoft Irina Desktop - Russian"
                    win.cb_tts_voice.addItem("Microsoft Irina Desktop - Russian", target_id)
                    win.cb_tts_voice.setCurrentIndex(items_count)

                self.assertEqual(win.settings["tts_voice"], target_id)
                with open(temp_config, "r", encoding="utf-8") as f:
                    saved_cfg = json.load(f)
                self.assertEqual(saved_cfg["tts_voice"], target_id)
                self.assertGreaterEqual(len(emitted_events), 1)
                print(f"[Test 4] Выбор голоса «{target_id}» успешно сохранил settings.json и эмитил settings_changed.")

                # 3. Проверяем кнопку «Проверить звук»
                print("[Test 4] Тестирование кнопки тестового воспроизведения TTS...")
                tts_test_calls = []
                win.test_tts_requested.connect(lambda v: tts_test_calls.append(v))
                win.btn_test_tts.click()
                self.assertEqual(len(tts_test_calls), 1)
                self.assertEqual(tts_test_calls[0], target_id)
                print(f"[Test 4] Кнопка btn_test_tts эмитила test_tts_requested('{target_id}').")


if __name__ == "__main__":
    unittest.main()
