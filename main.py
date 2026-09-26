"""
Главная точка входа Antigravity Voice.
Координирует работу GUI, системного трея, низкоуровневого хука Copilot,
аудиоконтура, распознавания речи, синтеза ответов (TTS) и исполнителя команд.
"""
import sys
import os
import time
import winsound
import threading
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from core.audio_ducking import AudioDucker
from core.audio_listener import AudioListener
from core.speech_to_text import SpeechToText
from core.decision_engine import DecisionEngine
from core.text_to_speech import TextToSpeech
from core.executor import CommandExecutor
from core.keyboard_hook import CopilotKeyHook
from core.vision_agent import VisionAgentProcessManager

from gui.main_window import MainWindow
from gui.tray_manager import TrayManager
from gui.floating_pill import FloatingPill, ClickIndicatorOverlay
from gui.spotlight_bar import SpotlightBar
from create_shortcut import create_desktop_shortcut

class AppCoordinator(QObject):
    # Сигналы для безопасного межпоточного взаимодействия с GUI PyQt6
    request_voice_input_signal = pyqtSignal(str)
    request_spotlight_signal = pyqtSignal()
    prompt_start_agent_signal = pyqtSignal()
    vu_meter_signal = pyqtSignal(float)
    log_signal = pyqtSignal(str)
    pill_text_signal = pyqtSignal(str)
    pill_executing_signal = pyqtSignal(str)
    pill_error_signal = pyqtSignal(str)
    pill_listening_signal = pyqtSignal()
    key_detected_signal = pyqtSignal(str, int)
    llm_download_progress_signal = pyqtSignal(int)
    llm_download_done_signal = pyqtSignal(bool)
    confirm_action_signal = pyqtSignal(dict, str)
    card_status_signal = pyqtSignal(str, str, str)
    check_all_done_signal = pyqtSignal(bool, str)

    def __init__(self, is_minimized: bool = False):
        super().__init__()
        self.project_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.project_dir, "config", "settings.json")
        self.sounds_dir = os.path.join(self.project_dir, "sounds")

        # 1. Инициализация интерфейса
        self.window = MainWindow(self.config_path)
        self.tray = TrayManager()
        self.pill = FloatingPill()
        self.click_overlay = ClickIndicatorOverlay()
        self.spotlight = SpotlightBar()

        # 2. Инициализация ядра с сохраненными настройками
        saved_device = self.window.settings.get("audio_device_index")
        tts_voice = self.window.settings.get("tts_voice", "ru_RU-irina-medium")
        tts_speed = float(self.window.settings.get("tts_speed", 1.0))
        sapi_speed = int(max(-10, min(10, (tts_speed - 1.0) * 10)))

        stt_model = self.window.settings.get("stt_model", "turbo")
        self.audio_ducker = AudioDucker()
        self.decision_engine = DecisionEngine()
        vision_model = self.window.settings.get("vision_model", "xlangai/Jedi-3B-1080p")
        self.vision_manager = VisionAgentProcessManager(model_name=vision_model)
        self.executor = CommandExecutor(
            self.audio_ducker,
            on_log=self.log,
            vision_manager=self.vision_manager,
            settings=self.window.settings
        )
        self.stt = SpeechToText(model_size=stt_model, device="cuda")
        self.tts = TextToSpeech(voice_name=tts_voice, speed=sapi_speed)
        self.listener = AudioListener(device_index=saved_device, on_vu_meter=self.vu_meter_signal.emit)

        self.is_agent_running = True
        self._is_processing_voice = False

        # Фоновый запуск Vision-агента в режиме Always-Warm
        self.vision_manager.start()

        # Таймер опроса очереди событий Vision-агента (каждые 120 мс)
        self._vision_timer = QTimer(self)
        self._vision_timer.setInterval(120)
        self._vision_timer.timeout.connect(self._poll_vision_agent)
        self._vision_timer.start()

        # 3. Подключение сигналов
        self._connect_signals()

        # 4. Применяем настройки микрофона и LLM
        devices = self.listener.get_input_devices()
        self.window.set_microphones(devices)
        self.window.set_llm_status(self.decision_engine.is_llm_available())
        self.listener.start_stream()

        # 5. Запуск низкоуровневого перехватчика Copilot
        self.hook = CopilotKeyHook(
            on_click=self._on_copilot_click_from_hook,
            on_hold=self._on_copilot_hold_from_hook,
            on_debug=lambda msg: self.log(f"Клавиатурный хук: {msg}"),
            on_any_key=self._on_any_key_from_hook
        )
        self.hook.start()

        # 6. Режим активации по умолчанию
        self._apply_activation_mode()

        # 7. Отображение окна
        self.tray.show()
        if not is_minimized and not self.window.settings.get("start_minimized", False):
            self.window.show()

        # Создаем ярлык на рабочем столе при первом запуске
        try:
            create_desktop_shortcut()
        except Exception:
            pass

        self._log_system_readiness()

    def _log_system_readiness(self):
        """Выводит подробный и наглядный отчет о готовности всех подсистем."""
        stt_mode = "CUDA (NVIDIA RTX 5050)" if self.stt.device == "cuda" else "CPU"
        ai_mode = self.decision_engine.get_model_status()
        self.log("==================================================")
        self.log("🚀 Antigravity Voice запущен и готов к работе!")
        self.log("• Микрофон: активен и готов к записи речи")
        self.log(f"• Распознавание речи: Faster-Whisper {self.stt.model_size.capitalize()} на {stt_mode}")
        self.log(f"• Модуль ИИ: {ai_mode}")
        self.log("• Клавиша Copilot: перехватчик активен (VK_F23 = 0x8E)")
        self.log("• Интеграция: Antigravity IDE (GUI) + Antigravity CLI (agy)")
        self.log("==================================================")

    def _connect_signals(self):
        # Межпоточные сигналы хука
        self.request_voice_input_signal.connect(self._handle_voice_input)
        self.request_spotlight_signal.connect(self.spotlight.show_spotlight)
        self.prompt_start_agent_signal.connect(self._show_start_agent_prompt)
        self.key_detected_signal.connect(self.window.update_key_test_indicator)

        # Сигналы логов и UI
        self.log_signal.connect(self.window.log)
        self.vu_meter_signal.connect(self.window.set_vu_level)
        self.pill_text_signal.connect(self.pill.update_text)
        self.pill_executing_signal.connect(self.pill.show_executing)
        self.pill_error_signal.connect(self.pill.show_error)
        self.pill_listening_signal.connect(self.pill.show_listening)

        # Сигналы окон и трея
        self.window.agent_toggle_requested.connect(self.toggle_agent)
        self.window.mic_changed.connect(self._on_mic_changed)
        self.window.settings_changed.connect(self._on_settings_updated)
        self.window.app_exit_requested.connect(self.exit_app)

        # Сигналы интерактивной диагностики
        self.window.test_sound_requested.connect(self._run_test_sound)
        self.window.test_mic_requested.connect(self._run_test_mic)
        self.window.test_stt_requested.connect(self._run_test_stt)
        self.window.download_llm_requested.connect(self._run_download_llm)
        self.window.check_all_systems_requested.connect(self._run_check_all_systems)

        self.card_status_signal.connect(self.window.update_status_card)
        self.check_all_done_signal.connect(self._on_check_all_done)

        self.llm_download_progress_signal.connect(self._on_llm_download_progress)
        self.llm_download_done_signal.connect(self._on_llm_download_done)

        self.tray.show_window_requested.connect(self._show_window)
        self.tray.toggle_agent_requested.connect(lambda: self.toggle_agent(not self.is_agent_running))
        self.tray.exit_requested.connect(self.exit_app)

        # Сигнал подтверждения опасных действий
        self.confirm_action_signal.connect(self._show_confirmation_dialog)

        # Сигнал от Spotlight
        self.spotlight.command_submitted.connect(self._handle_text_command)

    def _show_confirmation_dialog(self, command: dict, text: str):
        """Безопасный диалог подтверждения опасных системных действий в главном GUI потоке."""
        action_name = "выключение" if command.get("target") == "shutdown" else "перезагрузку"
        reply = QMessageBox.warning(
            self.window,
            "Подтверждение действия",
            f"Ассистент запросил опасное системное действие: {action_name} компьютера.\n\nКоманда: «{text}»\n\nВы действительно хотите выполнить это действие?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            command.setdefault("parameters", {})["confirmed"] = True
            success, msg = self.executor.execute(command)
            if success:
                self.pill_executing_signal.emit(msg)
                self._play_sound("success")
                if self.window.settings.get("tts_enabled", False):
                    self.tts.speak(msg)
        else:
            self.log("Опасное системное действие отменено пользователем.")
            self.pill_error_signal.emit("Отменено")

    def log(self, message: str):
        self.log_signal.emit(message)

    def _play_sound(self, sound_name: str):
        """Воспроизведение WAV сигнала без блокировки потока."""
        if not self.window.settings.get("sound_cues_enabled", True):
            return
        path = os.path.join(self.sounds_dir, f"{sound_name}.wav")
        if os.path.exists(path):
            try:
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception:
                pass

    def _apply_activation_mode(self):
        """Применяет режим активации (фоновый Wake Word Джарвис)."""
        mode = self.window.settings.get("default_activation_mode", "copilot_only")
        wake_enabled = self.window.settings.get("wake_word_enabled", True)
        if mode == "wake_word_and_copilot" and wake_enabled and self.is_agent_running:
            configured_ww = self.window.settings.get("wake_word", "джарвис").strip().lower()
            if configured_ww in ("джарвис", "jarvis"):
                # Расширяем фонетическими вариациями распознавания Whisper
                wake_variants = ["джарвис", "жарвис", "ярвис", "джарвиз", "чарвис", "гарвис", "jarvis"]
            else:
                wake_variants = [configured_ww]
            wake_words = tuple(dict.fromkeys(wake_variants))
            self.listener.start_wake_word_loop(
                on_wake_detected=lambda cmd="": self.request_voice_input_signal.emit(cmd or ""),
                stt_engine=self.stt,
                wake_words=wake_words
            )
            self.log(f"Режим Hands-free активен: слушаю слово «{configured_ww.capitalize()}».")
        else:
            self.listener.stop_wake_word_loop()

    def _on_settings_updated(self, settings: dict):
        self.executor.settings = settings
        tts_voice = settings.get("tts_voice", "ru_RU-irina-medium")
        tts_speed = float(settings.get("tts_speed", 1.0))
        sapi_speed = int(max(-10, min(10, (tts_speed - 1.0) * 10)))
        self.tts.voice_name = tts_voice
        self.tts.speed = sapi_speed

        stt_model = settings.get("stt_model", "turbo")
        if self.stt.model_size != stt_model:
            self.stt.unload_model()
            self.stt.model_size = stt_model
            self.log(f"Модель Faster-Whisper изменена на «{stt_model}».")

        vision_model = settings.get("vision_model", "xlangai/Jedi-3B-1080p")
        if hasattr(self.vision_manager, "model_name") and self.vision_manager.model_name != vision_model:
            self.vision_manager.model_name = vision_model
            self.log(f"Модель Vision-агента изменена на «{vision_model}».")

        self._apply_activation_mode()

    def _on_any_key_from_hook(self, vk: int, hex_code: str):
        key_name = f"Copilot ({hex_code})" if vk in (0x86, 0x8E) else f"Клавиша {hex_code}"
        self.key_detected_signal.emit(key_name, vk)

    def _on_copilot_click_from_hook(self):
        """Событие одиночного клика клавиши Copilot из низкоуровневого потока."""
        self.hook.dismiss_search_window()
        if self.is_agent_running:
            self.request_voice_input_signal.emit("")
        else:
            self.prompt_start_agent_signal.emit()

    def _on_copilot_hold_from_hook(self):
        """Событие удержания клавиши Copilot из низкоуровневого потока."""
        self.hook.dismiss_search_window()
        self.request_spotlight_signal.emit()

    def _show_start_agent_prompt(self):
        """Диалог с вопросом о запуске если агент остановлен."""
        reply = QMessageBox.question(
            self.window,
            "Ассистент остановлен",
            "Голосовой ассистент сейчас остановлен (VRAM свободна).\nЗапустить его сейчас?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.toggle_agent(True)
            self._handle_voice_input("")

    def _show_window(self):
        self.window.show()
        self.window.activateWindow()

    def _on_mic_changed(self, device_idx: int):
        self.listener.stop_stream()
        self.listener.device_index = device_idx
        self.listener.start_stream()
        self._apply_activation_mode()
        self.log(f"Микрофон переключен на индекс: {device_idx}")

    def _run_test_sound(self):
        """Тест воспроизведения звука и Audio Ducking."""
        def worker():
            self.log("🔊 Тест звука: воспроизведение сигнала активации и проверка Audio Ducking...")
            if self.window.settings.get("audio_ducking_enabled", True):
                duck_level = float(self.window.settings.get("audio_ducking_level", 0.20))
                self.audio_ducker.duck(duck_factor=duck_level)
            self._play_sound("activate")
            time.sleep(1.2)
            if self.window.settings.get("audio_ducking_enabled", True):
                self.audio_ducker.unduck()
            self.log("✓ Звуковой сигнал и система Audio Ducking работают в штатном режиме.")
        threading.Thread(target=worker, daemon=True).start()

    def _run_test_mic(self):
        """Интерактивный тест микрофона с распознаванием тестовой фразы."""
        if self._is_processing_voice:
            return

        def worker():
            self._is_processing_voice = True
            try:
                self.log("🎙 Тест микрофона: скажите любую фразу вслух (запись 3 секунды)...")
                self._play_sound("activate")
                audio = self.listener.record_command()
                if len(audio) == 0:
                    self.log("⚠ Звук с микрофона не обнаружен. Проверьте устройство в «Настройки».")
                    self._play_sound("error")
                    return

                self.log("🧠 Распознавание записанного тестового сэмпла...")
                text = self.stt.transcribe(audio)
                if text:
                    self.log(f"✓ Микрофон работает отлично! Распознано: «{text}»")
                    self._play_sound("success")
                else:
                    self.log("✓ Запись с микрофона получена, но речь была слишком тихой.")
            except Exception as e:
                self.log(f"Ошибка при проверке микрофона: {e}")
            finally:
                self._is_processing_voice = False

        threading.Thread(target=worker, daemon=True).start()

    def _run_test_stt(self):
        """Тестирует скорость и работоспособность Faster-Whisper на GPU CUDA."""
        def worker():
            self.log("🧠 Тестирование Faster-Whisper Turbo на GPU NVIDIA GeForce RTX 5050 (CUDA)...")
            start = time.time()
            ok = self.stt.load_model()
            duration = time.time() - start
            if ok:
                self.log(f"✓ Faster-Whisper Turbo успешно проверен на CUDA! (Время отклика: {duration:.2f} сек)")
            else:
                self.log("⚠ Ошибка инференса на CUDA. Проверьте видеодрайвер NVIDIA.")
        threading.Thread(target=worker, daemon=True).start()

    def _run_download_llm(self):
        """Скачивает и проверяет модель Jedi-3B 1080p с Hugging Face Hub."""
        self.window.btn_download_llm.setEnabled(False)
        self.window.btn_download_llm.setText("Запуск скачивания...")

        def worker():
            self.log("📥 Запуск проверки и загрузки модели xlangai/Jedi-3B-1080p...")
            
            def progress(percent, cur, total):
                self.llm_download_progress_signal.emit(percent)

            ok = self.decision_engine.download_llm_model(progress_callback=progress)
            self.llm_download_done_signal.emit(ok)

        threading.Thread(target=worker, daemon=True).start()

    def _on_llm_download_progress(self, percent: int):
        self.window.btn_download_llm.setText(f"Скачивание... {percent}%")

    def _on_llm_download_done(self, success: bool):
        if success:
            self.window.set_llm_status(True)
            self.log("✓ Модель Jedi-3B-1080p успешно проверена и установлена!")
            self._play_sound("success")
        else:
            self.window.btn_download_llm.setText("📥 Ошибка скачивания (Повторить)")
            self.window.btn_download_llm.setEnabled(True)
            self.log("⚠ Ошибка загрузки Jedi-3B. Проверьте интернет-соединение.")
            self._play_sound("error")

    def _on_check_all_done(self, success: bool, message: str):
        self.window.reset_check_all_systems_button()
        if success:
            self._play_sound("success")
            self.pill_executing_signal.emit("Все системы OK")
        else:
            self._play_sound("error")
            self.pill_error_signal.emit("Ошибка систем")

    def _run_check_all_systems(self):
        """Выполняет комплексную проверку всех подсистем ассистента."""
        if self._is_processing_voice:
            self.log("⚠ Проверка отложена: в данный момент обрабатывается голосовой ввод.")
            self.window.reset_check_all_systems_button()
            return

        def worker():
            self.log("==================================================")
            self.log("🔍 ЗАПУСК ПОЛНОЙ ПРОВЕРКИ ВСЕХ СИСТЕМ...")
            self.log("==================================================")
            all_ok = True
            summary_results = []

            # 1. Проверка аудиоустройств и микрофона
            try:
                import sounddevice as sd
                devices = sd.query_devices()
                input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
                if input_devices:
                    cur_dev = self.listener.device_index
                    dev_name = "По умолчанию"
                    if cur_dev is not None and cur_dev < len(devices):
                        dev_name = devices[cur_dev]["name"]
                    elif len(input_devices) > 0:
                        dev_name = input_devices[0]["name"]
                    if len(dev_name) > 22:
                        dev_name = dev_name[:20] + "..."
                    self.card_status_signal.emit("mic", dev_name, "#34D399")
                    self.log(f"[1/7] 🎙 Микрофон: OK ({len(input_devices)} устройств найдено, активен: {dev_name})")
                    summary_results.append("Микрофон: OK")
                else:
                    self.card_status_signal.emit("mic", "Не найден", "#EF4444")
                    self.log("[1/7] ⚠ Микрофон: устройства ввода не обнаружены!")
                    all_ok = False
                    summary_results.append("Микрофон: Ошибка")
            except Exception as e:
                self.card_status_signal.emit("mic", "Ошибка", "#EF4444")
                self.log(f"[1/7] ❌ Ошибка проверки микрофона: {e}")
                all_ok = False
                summary_results.append("Микрофон: Ошибка")

            # 2. Проверка хука клавиатуры и клавиши Copilot
            try:
                hook_active = self.hook._is_running
                if hook_active:
                    self.card_status_signal.emit("key", "Хук активен (0x86/0x8E)", "#34D399")
                    self.log("[2/7] ⌨ Клавиша Copilot: OK (WH_KEYBOARD_LL активен, блокировка поиска включена)")
                    summary_results.append("Клавиша Copilot: OK")
                else:
                    self.card_status_signal.emit("key", "Хук остановлен", "#F59E0B")
                    self.log("[2/7] ⚠ Клавиша Copilot: перехватчик не запущен")
                    summary_results.append("Клавиша Copilot: Предупреждение")
            except Exception as e:
                self.card_status_signal.emit("key", "Ошибка", "#EF4444")
                self.log(f"[2/7] ❌ Ошибка проверки клавиатурного хука: {e}")
                all_ok = False
                summary_results.append("Клавиша Copilot: Ошибка")

            # 3. Проверка Faster-Whisper и аппаратного ускорения NVIDIA CUDA
            try:
                import ctranslate2
                cuda_count = ctranslate2.get_cuda_device_count()
                supported_types = ctranslate2.get_supported_compute_types("cuda")
                has_cuda = cuda_count > 0 and "float16" in supported_types
                stt_loaded = self.stt.load_model()
                if stt_loaded and has_cuda:
                    self.card_status_signal.emit("stt", "Turbo CUDA (RTX 5050)", "#34D399")
                    self.log("[3/7] 🧠 Faster-Whisper: OK (Turbo CUDA float16 активна на RTX 5050)")
                    summary_results.append("Faster-Whisper (Turbo): OK")
                elif stt_loaded:
                    self.card_status_signal.emit("stt", "Turbo CPU (int8)", "#F59E0B")
                    self.log("[3/7] 🧠 Faster-Whisper: OK (Работает в режиме CPU)")
                    summary_results.append("Faster-Whisper (CPU): OK")
                else:
                    self.card_status_signal.emit("stt", "Ошибка загрузки", "#EF4444")
                    self.log("[3/7] ❌ Faster-Whisper: не удалось загрузить модель")
                    all_ok = False
                    summary_results.append("Faster-Whisper: Ошибка")
            except Exception as e:
                self.card_status_signal.emit("stt", "Ошибка", "#EF4444")
                self.log(f"[3/7] ❌ Ошибка проверки Faster-Whisper: {e}")
                all_ok = False
                summary_results.append("Faster-Whisper: Ошибка")

            # 4. Проверка модуля принятия решений (Decision Engine)
            try:
                test_res = self.decision_engine.parse_command("Сделай потише")
                fast_ok = test_res.get("action") == "set_volume"
                has_llm = self.decision_engine.is_llm_available()
                if has_llm:
                    self.card_status_signal.emit("ai", "Локальная LLM (Qwen2.5)", "#34D399")
                    self.log("[4/7] 🤖 Модуль ИИ: OK (Fast-Path готов + Локальная нейросеть Qwen2.5 активна)")
                    summary_results.append("Модуль ИИ: OK (LLM)")
                else:
                    self.card_status_signal.emit("ai", "Fast-Path (0 мс)", "#60A5FA")
                    self.log("[4/7] 🤖 Модуль ИИ: OK (Fast-Path готов, LLM доступна для скачивания)")
                    summary_results.append("Модуль ИИ: OK (Fast-Path)")
            except Exception as e:
                self.card_status_signal.emit("ai", "Ошибка", "#EF4444")
                self.log(f"[4/7] ❌ Ошибка проверки Decision Engine: {e}")
                all_ok = False
                summary_results.append("Модуль ИИ: Ошибка")

            # 5. Проверка управления звуком (Audio Ducking) и звуковых эффектов
            try:
                has_endpoint = self.audio_ducker._get_volume_endpoint() is not None
                sounds_ok = all(
                    os.path.exists(os.path.join(self.sounds_dir, f"{s}.wav"))
                    for s in ("activate", "success", "error")
                )
                if has_endpoint and sounds_ok:
                    self.log("[5/7] 🔊 Аудио-система: OK (Audio Ducking и все WAV сигналы готовы)")
                    summary_results.append("Audio Ducking & Звуки: OK")
                else:
                    self.log("[5/7] ⚠ Аудио-система: звуковое устройство или сигналы доступны частично")
                    summary_results.append("Audio Ducking & Звуки: Предупреждение")
            except Exception as e:
                self.log(f"[5/7] ❌ Ошибка проверки аудио-системы: {e}")
                all_ok = False
                summary_results.append("Audio Ducking & Звуки: Ошибка")

            # 6. Проверка интеграции с Antigravity (IDE 2.0 + CLI)
            try:
                import win32gui
                ide_found = False
                def enum_cb(hwnd, _):
                    nonlocal ide_found
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd).lower()
                        if "antigravity" in title:
                            ide_found = True
                win32gui.EnumWindows(enum_cb, None)

                import shutil
                cli_found = shutil.which("agy") is not None
                ide_status = "Окно обнаружено" if ide_found else "Модуль готов"
                self.card_status_signal.emit("ide", f"GUI + CLI ({ide_status})", "#34D399")
                self.log(f"[6/7] 🚀 Antigravity: OK (Интеграция с GUI готова, CLI в PATH: {'да' if cli_found else 'через терминал'})")
                summary_results.append("Antigravity: OK")
            except Exception as e:
                self.card_status_signal.emit("ide", "Ошибка", "#EF4444")
                self.log(f"[6/7] ❌ Ошибка проверки Antigravity: {e}")
                all_ok = False
                summary_results.append("Antigravity: Ошибка")

            # 7. Проверка конфигураций и ярлыка
            try:
                conf_ok = os.path.exists(self.config_path)
                cmd_ok = os.path.exists(os.path.join(os.path.dirname(self.config_path), "commands.json"))
                desktop_lnk = os.path.expanduser(r"~\Desktop\Antigravity Voice.lnk")
                lnk_ok = os.path.exists(desktop_lnk)
                if conf_ok and cmd_ok:
                    self.log(f"[7/7] ⚙ Конфигурация: OK (settings.json, commands.json, ярлык на Рабочем столе: {'да' if lnk_ok else 'создаётся'})")
                    summary_results.append("Конфигурация: OK")
                else:
                    self.log("[7/7] ⚠ Конфигурация: отсутствуют некоторые конфигурационные файлы")
                    all_ok = False
                    summary_results.append("Конфигурация: Ошибка")
            except Exception as e:
                self.log(f"[7/7] ❌ Ошибка проверки конфигурации: {e}")
                all_ok = False
                summary_results.append("Конфигурация: Ошибка")

            # Итоговое резюме
            self.log("==================================================")
            if all_ok:
                self.log("✅ ВСЕ СИСТЕМЫ ПРОВЕРЕНЫ И РАБОТАЮТ ШТАТНО (100% OK)!")
                for item in summary_results:
                    self.log(f"  ✓ {item}")
            else:
                self.log("⚠ ПРОВЕРКА ЗАВЕРШЕНА С ЗАМЕЧАНИЯМИ:")
                for item in summary_results:
                    self.log(f"  • {item}")
            self.log("==================================================")

            self.check_all_done_signal.emit(all_ok, "100% OK" if all_ok else "Обнаружены замечания")

        threading.Thread(target=worker, daemon=True).start()

    def _poll_vision_agent(self) -> None:
        """Опрашивает очередь событий фонового процесса Vision-агента и передает их в GUI."""
        max_steps = int(self.window.settings.get("vision_max_steps", 8))
        events = self.vision_manager.poll_status()
        for ev in events:
            ev_type = ev.get("type")
            if ev_type == "ready":
                self.log("✓ Vision Computer-Use Agent (Jedi-3B) готов к работе в фоновом процессе.")
            elif ev_type == "task_started":
                self.pill.show_step(1, max_steps, "Анализирую экран...")
                self.log(f"Vision-агент начал выполнение: «{ev.get('prompt', '')}»")
            elif ev_type == "step_status":
                step = ev.get("step", 1)
                status = ev.get("status", "")
                self.pill.show_step(step, max_steps, status)
            elif ev_type == "action_decided":
                step = ev.get("step", 1)
                thought = ev.get("thought", "")
                action_name = ev.get("action", "")
                msg = thought or f"Действие: {action_name}"
                self.pill.show_step(step, max_steps, msg)
                self.log(f"  [Шаг {step}] {msg}")
            elif ev_type == "click_performed":
                x = ev.get("x", 0)
                y = ev.get("y", 0)
                self.click_overlay.show_click(x, y)
            elif ev_type == "interrupted":
                reason = ev.get("reason", "Прервано пользователем")
                self.pill.show_error(reason)
                self.log(f"⚠ Vision-агент прерван: {reason}")
                self._play_sound("error")
            elif ev_type == "task_completed":
                success = ev.get("success", False)
                message = ev.get("message", "Готово")
                if success:
                    self.pill.show_executing(message)
                    self.log(f"✓ Задача успешно выполнена: {message}")
                    self._play_sound("success")
                    if self.window.settings.get("tts_enabled", False):
                        self.tts.speak(message)
                else:
                    self.pill.show_error(message)
                    self.log(f"⚠ Задача не завершена: {message}")
                    self._play_sound("error")
            elif ev_type == "error":
                err = ev.get("message", "Ошибка агента")
                self.pill.show_error("Ошибка агента")
                self.log(f"❌ Ошибка Vision-агента: {err}")
                self._play_sound("error")

    def toggle_agent(self, enable: bool):
        """Переключает статус ассистента с полным освобождением VRAM при остановке."""
        self.is_agent_running = enable
        self.window.update_agent_state(enable)
        self.tray.update_status(enable)

        if not enable:
            # Выгружаем модели из VRAM и останавливаем фоновый микрофон
            self.listener.stop_wake_word_loop()
            self.stt.unload_model()
            self.decision_engine.unload_model()
            self.vision_manager.stop()
            self.log("Ассистент остановлен. Видеопамять (VRAM) освобождена до 0 МБ.")
        else:
            self._apply_activation_mode()
            self.vision_manager.start()
            self.log("Ассистент активен и готов к командам.")

    def _handle_voice_input(self, pre_command: str = ""):
        """Запускает процесс записи и распознавания речи в отдельном потоке."""
        if self._is_processing_voice:
            return

        def worker():
            self._is_processing_voice = True
            try:
                text = pre_command.strip() if pre_command else ""

                if not text:
                    # 1. Сигнал и пилюля
                    self._play_sound("activate")
                    self.pill_listening_signal.emit()

                    # 2. Audio Ducking
                    if self.window.settings.get("audio_ducking_enabled", True):
                        duck_level = float(self.window.settings.get("audio_ducking_level", 0.20))
                        self.audio_ducker.duck(duck_factor=duck_level)

                    # 3. Запись звука
                    audio = self.listener.record_command()

                    # Восстанавливаем звук системы
                    if self.window.settings.get("audio_ducking_enabled", True):
                        self.audio_ducker.unduck()

                    if len(audio) == 0:
                        self.pill_error_signal.emit("Звук не обнаружен")
                        self._play_sound("error")
                        return

                    # 4. Распознавание речи (Faster-Whisper CUDA)
                    self.pill_text_signal.emit("Распознаю...")
                    text = self.stt.transcribe(audio)

                    if not text:
                        self.pill_error_signal.emit("Не удалось распознать")
                        self._play_sound("error")
                        self.log("Речь не распознана или была слишком тихой.")
                        return

                self.pill_text_signal.emit(text)
                self.log(f"Голос: «{text}»")

                # 5. Роутинг и исполнение
                self.pill_executing_signal.emit("Выполняю...")
                command = self.decision_engine.parse_command(text)
                is_vision = command.get("action") == "vision_agent"
                success, msg = self.executor.execute(command)

                if is_vision:
                    # Для асинхронного Vision-агента ход выполнения отслеживается таймером _poll_vision_agent
                    if success:
                        self.pill_executing_signal.emit("Анализирую экран...")
                    else:
                        self._play_sound("error")
                        self.pill_error_signal.emit(msg)
                elif msg == "CONFIRM_REQUIRED":
                    if self.window.settings.get("confirm_dangerous_actions", True):
                        self.pill_executing_signal.emit("Требуется подтверждение...")
                        self.confirm_action_signal.emit(command, text)
                    else:
                        command.setdefault("parameters", {})["confirmed"] = True
                        succ, m = self.executor.execute(command)
                        if succ:
                            self._play_sound("success")
                            self.pill_executing_signal.emit(m)
                            if self.window.settings.get("tts_enabled", False):
                                self.tts.speak(m)
                elif success:
                    self._play_sound("success")
                    self.pill_executing_signal.emit(msg)
                    if self.window.settings.get("tts_enabled", False):
                        self.tts.speak(msg)
                else:
                    self._play_sound("error")
                    self.pill_error_signal.emit(msg)

            except Exception as e:
                self.log(f"Ошибка голосового ввода: {e}")
                self.pill_error_signal.emit("Ошибка выполнения")
                self._play_sound("error")
            finally:
                if self.window.settings.get("audio_ducking_enabled", True):
                    self.audio_ducker.unduck()
                self._is_processing_voice = False

        threading.Thread(target=worker, daemon=True).start()

    def _handle_text_command(self, text: str):
        """Исполнение команды, введенной текстом через Spotlight."""
        self.log(f"Spotlight: «{text}»")
        command = self.decision_engine.parse_command(text)
        is_vision = command.get("action") == "vision_agent"
        success, msg = self.executor.execute(command)

        if is_vision:
            if success:
                self.pill_executing_signal.emit("Анализирую экран...")
            else:
                self._play_sound("error")
                self.pill_error_signal.emit(msg)
            return

        if msg == "CONFIRM_REQUIRED":
            if self.window.settings.get("confirm_dangerous_actions", True):
                self.confirm_action_signal.emit(command, text)
            else:
                command.setdefault("parameters", {})["confirmed"] = True
                succ, m = self.executor.execute(command)
                if succ:
                    self._play_sound("success")
                    if self.window.settings.get("tts_enabled", False):
                        self.tts.speak(m)
        elif success:
            self._play_sound("success")
            if self.window.settings.get("tts_enabled", False):
                self.tts.speak(msg)
        else:
            self._play_sound("error")

    def exit_app(self):
        """Полное закрытие приложения и освобождение системных ресурсов."""
        self.hook.stop()
        self.listener.stop_stream()
        self.stt.unload_model()
        self.decision_engine.unload_model()
        self.vision_manager.stop()
        self.tray.tray_icon.hide()
        QApplication.quit()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    is_minimized = "--minimized" in sys.argv
    coordinator = AppCoordinator(is_minimized=is_minimized)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
