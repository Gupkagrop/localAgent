"""
Модуль захвата звука и фильтрации речевой активности (VAD).
Реализует архитектуру единого непрерывного аудиопотока (Single Persistent Stream):
- Живой VU-метр без прерываний
- Исключение конфликтов устройств ввода и ошибок WASAPI (-9999)
- Потокобезопасная запись команд (Tap-to-Talk)
- Фоновое распознавание ключевого слова («Джарвис») без блокировки аудиопотока
"""
import time
import threading
from typing import Callable, Optional
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHUNK_SIZE = 512  # 32 мс при 16 кГц

class AudioListener:
    def __init__(
        self,
        device_index: Optional[int] = None,
        on_vu_meter: Optional[Callable[[float], None]] = None
    ):
        self.device_index = device_index
        self.on_vu_meter = on_vu_meter

        self._is_running = False
        self._stream_thread: Optional[threading.Thread] = None
        self._state_lock = threading.Lock()

        # Режимы работы: "idle", "wake_listen", "recording"
        self._mode = "idle"
        self._wake_words = ("джарвис", "jarvis")
        self._on_wake_detected: Optional[Callable[[], None]] = None
        self._stt_engine = None

        # Параметры записи команды
        self._record_buffer: list[np.ndarray] = []
        self._record_done_event = threading.Event()
        self._has_spoken = False
        self._silence_start: Optional[float] = None
        self._record_start_time = 0.0
        self._max_duration_sec = 8.0

        # Пороги энергии речи и тишины (0.004 обеспечивает естественный захват с ноутбука)
        self.speech_energy_threshold = 0.004
        self.silence_threshold_ms = 450

        # Буфер для фонового Wake Word
        self._wake_buffer: list[np.ndarray] = []
        self._wake_speech_active = False
        self._wake_silence_start: Optional[float] = None
        self._is_checking_wake = False

    @staticmethod
    def get_input_devices() -> list[dict]:
        """Возвращает список доступных микрофонов в системе."""
        devices = []
        try:
            device_list = sd.query_devices()
            for idx, dev in enumerate(device_list):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append({
                        "index": idx,
                        "name": dev.get("name", f"Microphone {idx}"),
                        "channels": dev.get("max_input_channels"),
                        "default": idx == sd.default.device[0]
                    })
        except Exception:
            pass
        return devices

    def start_stream(self):
        """Запускает постоянный фоновый поток считывания микрофона."""
        if self._is_running:
            return
        self._is_running = True
        self._stream_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._stream_thread.start()

    def stop_stream(self):
        """Останавливает аудиопоток."""
        self._is_running = False
        if self._stream_thread:
            self._stream_thread.join(timeout=1.0)
            self._stream_thread = None

    def _run_loop(self):
        """Единый цикл чтения из звуковой карты с непрерывным VU-метром."""
        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=CHUNK_SIZE,
                device=self.device_index
            ) as stream:
                while self._is_running:
                    data, overflowed = stream.read(CHUNK_SIZE)
                    chunk = data.flatten()

                    # 1. Расчет RMS и непрерывное обновление VU-метра в UI
                    rms = float(np.sqrt(np.mean(chunk**2)))
                    if self.on_vu_meter:
                        # Масштабируем сигнал для наглядности (0.0 .. 1.0)
                        self.on_vu_meter(min(1.0, rms * 12.0))

                    # 2. Обработка в зависимости от текущего режима
                    with self._state_lock:
                        curr_mode = self._mode

                    if curr_mode == "recording":
                        self._process_recording(chunk, rms)
                    elif curr_mode == "wake_listen":
                        self._process_wake_word(chunk, rms)
        except Exception as e:
            print(f"[AudioListener Error] {e}")
        finally:
            if self.on_vu_meter:
                self.on_vu_meter(0.0)

    def _process_recording(self, chunk: np.ndarray, rms: float):
        """Накапливает сэмплы при записи голосовой команды до наступления паузы."""
        self._record_buffer.append(chunk)

        is_speech = rms > self.speech_energy_threshold
        now = time.time()

        if is_speech:
            self._has_spoken = True
            self._silence_start = None
        else:
            if self._has_spoken:
                if self._silence_start is None:
                    self._silence_start = now
                elif (now - self._silence_start) * 1000 > self.silence_threshold_ms:
                    # Пользователь закончил говорить
                    self._record_done_event.set()
                    return

        # Защита от бесконечной записи
        if now - self._record_start_time > self._max_duration_sec:
            self._record_done_event.set()

    def _process_wake_word(self, chunk: np.ndarray, rms: float):
        """Отслеживает ключевое слово «Джарвис» без блокировки аудиопотока."""
        if self._is_checking_wake:
            return

        is_speech = rms > self.speech_energy_threshold
        now = time.time()

        if is_speech:
            self._wake_speech_active = True
            self._wake_silence_start = None
            self._wake_buffer.append(chunk)
            # Ограничиваем буфер фразы до 2.5 секунд
            if len(self._wake_buffer) > int(SAMPLE_RATE * 2.5 / CHUNK_SIZE):
                self._wake_buffer.pop(0)
        else:
            if self._wake_speech_active:
                self._wake_buffer.append(chunk)
                if self._wake_silence_start is None:
                    self._wake_silence_start = now
                elif (now - self._wake_silence_start) * 1000 > 300:
                    # Фраза завершилась - запускаем проверку в отдельном потоке
                    if len(self._wake_buffer) >= int(SAMPLE_RATE * 0.35 / CHUNK_SIZE):
                        audio_candidate = np.concatenate(self._wake_buffer)
                        self._wake_buffer = []
                        self._wake_speech_active = False
                        self._wake_silence_start = None
                        self._async_check_wake_word(audio_candidate)
                    else:
                        self._wake_buffer = []
                        self._wake_speech_active = False

    def _async_check_wake_word(self, audio: np.ndarray):
        """Асинхронный инференс STT для проверки слова-триггера."""
        def worker():
            self._is_checking_wake = True
            try:
                if self._stt_engine and self._mode == "wake_listen":
                    text = self._stt_engine.transcribe(audio).lower().strip()
                    if any(w in text for w in self._wake_words):
                        if self._on_wake_detected:
                            self._on_wake_detected()
            except Exception:
                pass
            finally:
                self._is_checking_wake = False

        threading.Thread(target=worker, daemon=True).start()

    def record_command(self, max_duration_sec: float = 8.0) -> np.ndarray:
        """
        Переводит существующий поток в режим записи команды и ждет паузы в речи.
        Никаких повторных открытий устройств sounddevice.
        """
        if not self._is_running:
            self.start_stream()

        with self._state_lock:
            prev_mode = self._mode
            self._mode = "recording"
            self._record_buffer = []
            self._has_spoken = False
            self._silence_start = None
            self._record_start_time = time.time()
            self._max_duration_sec = max_duration_sec
            self._record_done_event.clear()

        # Ждем пока пользователь выскажется или истечет таймаут
        self._record_done_event.wait(timeout=max_duration_sec + 0.5)

        # Возвращаем режим обратно
        with self._state_lock:
            if self._mode == "recording":
                self._mode = prev_mode

            if not self._record_buffer:
                return np.array([], dtype=np.float32)

            return np.concatenate(self._record_buffer)

    def start_wake_word_loop(
        self,
        on_wake_detected: Callable[[], None],
        stt_engine,
        wake_words: tuple[str, ...] = ("джарвис", "jarvis")
    ):
        """Включает фоновый анализ аудиопотока на слово «Джарвис»."""
        with self._state_lock:
            self._on_wake_detected = on_wake_detected
            self._stt_engine = stt_engine
            self._wake_words = wake_words
            self._mode = "wake_listen"
        if not self._is_running:
            self.start_stream()

    def stop_wake_word_loop(self):
        """Выключает фоновый поиск ключевого слова и останавливает запись при остановке агента."""
        with self._state_lock:
            self._mode = "idle"
            self._record_done_event.set()
            self._wake_buffer.clear()
            self._wake_speech_active = False
