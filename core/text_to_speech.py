"""
Модуль синтеза речи (Text-to-Speech).
Поддерживает гибридный режим:
1. Нейросетевой Piper TTS (ONNX Runtime CPU, голос ru_RU-dmitri-medium) — высокое качество, 0 МБ VRAM.
2. Нативный Windows SAPI5 (Microsoft Irina Desktop) — надежный мгновенный фоллбэк.

Архитектура потоков:
- Очередь воспроизведения (queue.Queue) и выделенный фоновый поток-демон.
- Устранена блокировка GUI и зависание потоков (lock starvation).
- Поддержка мгновенной очистки очереди и прерывания речи (stop()).
- COM инициализируется один раз при старте потока-демона.
"""
import io
import os
import sys
import wave
import queue
import threading
# Кэш загруженной модели Piper, чтобы не перезагружать веса при каждом вызове
_CACHED_PIPER_VOICE = None
_PIPER_LOCK = threading.Lock()

def get_piper_model_paths() -> tuple[str | None, str | None]:
    """Возвращает пути к файлам ONNX и JSON модели Piper, если они существуют."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "tts"))
    onnx_path = os.path.join(base_dir, "ru_RU-dmitri-medium.onnx")
    json_path = os.path.join(base_dir, "ru_RU-dmitri-medium.onnx.json")
    if os.path.exists(onnx_path) and os.path.exists(json_path) and os.path.getsize(onnx_path) > 1024 * 1024:
        return onnx_path, json_path
    return None, None

class TextToSpeech:
    """Универсальный класс синтеза речи с поддержкой Piper TTS и SAPI5."""

    def __init__(self, voice_name: str | None = None, speed: float | int = 1.0) -> None:
        self.voice_name: str | None = voice_name
        self.speed: float | int = speed
        self._lock = threading.Lock()
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._is_running: bool = True
        self._worker_thread = threading.Thread(target=self._queue_worker, daemon=True)
        self._worker_thread.start()

    def _queue_worker(self) -> None:
        """Долгоживущий рабочий поток для последовательного синтеза без спавна лишних потоков."""
        has_com = False
        try:
            import pythoncom
            pythoncom.CoInitialize()
            has_com = True
        except Exception as e:
            print(f"[TTS] Предупреждение CoInitialize: {e}", file=sys.stderr)

        try:
            while self._is_running:
                try:
                    text = self._queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                if text is None:
                    break

                try:
                    with self._lock:
                        if self._is_piper_requested():
                            try:
                                success = self._speak_piper(text)
                            except Exception as pe:
                                print(f"[TTS Piper Error] {pe}")
                                success = False
                            if not success:
                                print("[TTS] Фоллбэк на Windows SAPI5...")
                                self._speak_sapi5(text)
                        else:
                            self._speak_sapi5(text)
                except Exception as e:
                    print(f"[TTS Worker Error] {e}")
                finally:
                    self._queue.task_done()
        finally:
            if has_com:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception as e:
                    print(f"[TTS] Предупреждение CoUninitialize: {e}", file=sys.stderr)

    def stop(self) -> None:
        """Очищает очередь воспроизведения и прерывает текущую речь."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception as e:
            print(f"[TTS] Предупреждение при сбросе воспроизведения: {e}", file=sys.stderr)

    @staticmethod
    def get_available_voices() -> list[dict]:
        """Возвращает список доступных голосов (нейросетевых Piper и системных SAPI5)."""
        voices: list[dict] = []

        # 1. Проверяем наличие модели Piper TTS
        onnx_p, _ = get_piper_model_paths()
        if onnx_p is not None:
            voices.append({
                "id": "piper:ru_RU-dmitri-medium",
                "name": "Piper Neural TTS (Дмитрий, ONNX CPU)"
            })

        # 2. Опрашиваем системные голоса Windows SAPI5
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            try:
                speaker = win32com.client.Dispatch("SAPI.SpVoice")
                for v in speaker.GetVoices():
                    desc = v.GetDescription()
                    voices.append({"id": desc, "name": f"SAPI5: {desc}"})
            finally:
                pythoncom.CoUninitialize()
        except Exception as e:
            print(f"[TTS Voices Error] {e}")

        return voices

    def _is_piper_requested(self) -> bool:
        """Определяет, выбран ли движок Piper TTS."""
        if not self.voice_name:
            # По умолчанию: если веса Piper присутствуют на диске, используем его
            onnx_p, _ = get_piper_model_paths()
            return onnx_p is not None

        vn = self.voice_name.lower()
        if vn.startswith("piper") or "dmitri" in vn or "ru_ru-dmitri" in vn:
            return True
        return False

    def _get_piper_voice(self):
        """Загружает или возвращает кэшированный экземпляр PiperVoice."""
        global _CACHED_PIPER_VOICE
        with _PIPER_LOCK:
            if _CACHED_PIPER_VOICE is not None:
                return _CACHED_PIPER_VOICE

            onnx_path, json_path = get_piper_model_paths()
            if not onnx_path or not json_path:
                return None

            try:
                from piper import PiperVoice
                voice = PiperVoice.load(onnx_path, json_path, use_cuda=False)
                _CACHED_PIPER_VOICE = voice
                return voice
            except Exception as e:
                print(f"[TTS Piper Load Error] Ошибка загрузки модели Piper: {e}")
                return None

    def _speak_piper(self, text: str) -> bool:
        """Синтезирует и воспроизводит речь через Piper TTS на CPU."""
        voice = self._get_piper_voice()
        if voice is None:
            return False

        try:
            import winsound
            from piper.config import SynthesisConfig

            # Конвертируем параметр скорости в length_scale Piper
            # Для Piper: length_scale < 1.0 быстрее, > 1.0 медленнее
            if isinstance(self.speed, (int, float)):
                if -10 <= self.speed <= 10 and isinstance(self.speed, int):
                    speed_factor = 1.0 + (self.speed / 10.0)
                else:
                    speed_factor = float(self.speed)
            else:
                speed_factor = 1.0

            speed_factor = max(0.5, min(2.5, speed_factor))
            length_scale = 1.0 / speed_factor
            syn_config = SynthesisConfig(length_scale=length_scale)

            wav_io = io.BytesIO()
            with wave.open(wav_io, "wb") as wav_file:
                voice.synthesize_wav(text, wav_file, syn_config=syn_config)

            wav_bytes = wav_io.getvalue()
            if not wav_bytes:
                return False

            winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
            return True
        except Exception as e:
            print(f"[TTS Piper Synthesis Error] {e}")
            return False

    def _speak_sapi5(self, text: str) -> None:
        """Синтезирует речь через Windows SAPI5 (Microsoft Irina Desktop)."""
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            try:
                speaker = win32com.client.Dispatch("SAPI.SpVoice")
                
                # Масштабируем скорость в диапазон [-10, 10]
                if isinstance(self.speed, float) and 0.1 <= self.speed <= 3.0:
                    sapi_rate = int((self.speed - 1.0) * 10)
                else:
                    sapi_rate = int(self.speed) if isinstance(self.speed, int) else 0
                speaker.Rate = max(-10, min(10, sapi_rate))

                # Подбор русского голоса
                selected_voice = None
                target_voice = self.voice_name.lower() if self.voice_name else ""
                target_needle = "irina" if "irina" in target_voice else target_voice

                for v in speaker.GetVoices():
                    desc = v.GetDescription().lower()
                    if target_needle and target_needle in desc:
                        selected_voice = v
                        break
                    if not selected_voice and any(kw in desc for kw in ["russian", "русск", "irina", "pavel"]):
                        selected_voice = v

                if selected_voice:
                    speaker.Voice = selected_voice

                speaker.Speak(text)
            finally:
                pythoncom.CoUninitialize()
        except Exception as e:
            print(f"[TTS SAPI5 Error] {e}")

    def speak(self, text: str, async_mode: bool = True) -> None:
        """
        Озвучивает текст без блокировки основного GUI-потока.
        Если async_mode=True, фраза помещается в очередь фонового потока-демона.
        Если async_mode=False, выполняется синхронно в вызывающем потоке.
        """
        if not text or not text.strip():
            return

        if async_mode:
            self._queue.put(text)
        else:
            with self._lock:
                if self._is_piper_requested():
                    try:
                        success = self._speak_piper(text)
                    except Exception as pe:
                        print(f"[TTS Piper Error] {pe}")
                        success = False
                    if not success:
                        self._speak_sapi5(text)
                else:
                    self._speak_sapi5(text)
