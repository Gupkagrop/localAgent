"""
Модуль захвата звука и фильтрации речевой активности (VAD).
Реализует архитектуру единого непрерывного аудиопотока (Single Persistent Stream):
- Живой VU-метр без прерываний
- Исключение конфликтов устройств ввода и ошибок WASAPI (-9999)
- Потокобезопасная запись команд (Tap-to-Talk)
- Фоновое распознавание ключевого слова («Джарвис») без блокировки аудиопотока
"""
from __future__ import annotations

import time
import re
import queue
import threading
import sys
from typing import TYPE_CHECKING, Callable
import numpy as np
import sounddevice as sd

if TYPE_CHECKING:
    from core.speech_to_text import SpeechToText

SAMPLE_RATE = 16000
CHUNK_SIZE = 512  # 32 мс при 16 кГц

class AudioListener:
    @staticmethod
    def calculate_rms(chunk: np.ndarray) -> float:
        """Вычисляет среднеквадратическую энергию (RMS) аудиофрагмента."""
        if chunk is None or len(chunk) == 0:
            return 0.0
        return float(np.sqrt(np.mean(chunk**2)))

    def __init__(
        self,
        device_index: int | None = None,
        on_vu_meter: Callable[[float], None] | None = None
    ) -> None:
        self.device_index = device_index
        self.on_vu_meter = on_vu_meter

        self._is_running = False
        self._stream_thread: threading.Thread | None = None
        self._state_lock = threading.Lock()

        # Режимы работы: "idle", "wake_listen", "recording"
        self._mode = "idle"
        self._wake_words = ("джарвис", "jarvis")
        self._on_wake_detected: Callable[..., None] | None = None
        self._stt_engine: SpeechToText | None = None

        # Параметры записи команды
        self._record_buffer: list[np.ndarray] = []
        self._record_done_event = threading.Event()
        self._has_spoken = False
        self._silence_start: float | None = None
        self._record_start_time = 0.0
        self._max_duration_sec = 8.0

        # Пороги энергии речи и тишины (0.002 обеспечивает надежный захват с микрофона ноутбука)
        self.speech_energy_threshold = 0.002
        self.silence_threshold_ms = 400

        # Буфер для фонового Wake Word и выделенный рабочий поток
        self.wake_word_enabled = True
        self._wake_buffer: list[np.ndarray] = []
        self._wake_pre_buffer: list[np.ndarray] = []
        self._wake_speech_active = False
        self._wake_silence_start: float | None = None
        self._is_checking_wake = False
        self._wake_queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=2)
        self._wake_worker_thread: threading.Thread | None = None

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
        except Exception as e:
            print(f"[AudioListener] Предупреждение: ошибка опроса аудиоустройств: {e}", file=sys.stderr)
        return devices

    def start_stream(self):
        """Запускает постоянный фоновый поток считывания микрофона."""
        if self._is_running:
            return
        self._is_running = True
        self._stream_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._stream_thread.start()

    def stop_stream(self):
        """Останавливает аудиопоток и фоновый воркер Wake Word."""
        self._is_running = False
        if self._stream_thread:
            self._stream_thread.join(timeout=1.0)
            self._stream_thread = None
        if self._wake_worker_thread:
            try:
                self._wake_queue.put_nowait(None)
            except Exception:
                pass
            self._wake_worker_thread.join(timeout=1.0)
            self._wake_worker_thread = None

    def _run_loop(self):
        """Единый цикл чтения из звуковой карты с непрерывным VU-метром."""
        last_vu_time = 0.0
        last_vu_level = 0.0
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

                    # 1. Расчет RMS и дросселированное обновление VU-метра в UI (макс 12.5 Гц)
                    rms = self.calculate_rms(chunk)
                    if self.on_vu_meter:
                        now = time.time()
                        level = min(1.0, rms * 12.0)
                        if now - last_vu_time >= 0.08:
                            if abs(level - last_vu_level) >= 0.015 or level == 0.0:
                                last_vu_time = now
                                last_vu_level = level
                                self.on_vu_meter(level)

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
            self._is_running = False
            self._record_done_event.set()
            if self.on_vu_meter:
                self.on_vu_meter(0.0)

    def _process_recording(self, chunk: np.ndarray, rms: float):
        with self._state_lock:
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
        """Отслеживает ключевое слово («Джарвис») без блокировки аудиопотока."""
        if not self.wake_word_enabled:
            return

        with self._state_lock:
            now = time.time()
            is_speech = rms > self.speech_energy_threshold

            # Сохраняем короткий кольцевой буфер до начала речи (чтобы не срезать первый согласный звук)
            if not self._wake_speech_active:
                self._wake_pre_buffer.append(chunk)
                if len(self._wake_pre_buffer) > int(SAMPLE_RATE * 0.15 / CHUNK_SIZE):
                    self._wake_pre_buffer.pop(0)

            if is_speech:
                if not self._wake_speech_active:
                    self._wake_speech_active = True
                    self._wake_buffer.extend(self._wake_pre_buffer)
                    self._wake_pre_buffer.clear()
                self._wake_silence_start = None
                self._wake_buffer.append(chunk)
                # Ограничиваем буфер фразы до 3.5 секунд (чтобы вместить фразу целиком)
                if len(self._wake_buffer) > int(SAMPLE_RATE * 3.5 / CHUNK_SIZE):
                    self._wake_buffer.pop(0)
            else:
                if self._wake_speech_active:
                    self._wake_buffer.append(chunk)
                    if self._wake_silence_start is None:
                        self._wake_silence_start = now
                    elif (now - self._wake_silence_start) * 1000 > 320:
                        # Фраза завершилась - запускаем проверку слова-триггера (минимум 0.50 с речи)
                        if len(self._wake_buffer) >= int(SAMPLE_RATE * 0.50 / CHUNK_SIZE):
                            audio_candidate = np.concatenate(self._wake_buffer)
                            self._wake_buffer = []
                            self._wake_speech_active = False
                            self._wake_silence_start = None
                            self._async_check_wake_word(audio_candidate)
                        else:
                            self._wake_buffer = []
                            self._wake_speech_active = False
                            self._wake_silence_start = None

    def _ensure_wake_worker(self) -> None:
        """Гарантирует работу выделенного потока-воркера Wake Word."""
        if self._wake_worker_thread is None or not self._wake_worker_thread.is_alive():
            self._wake_worker_thread = threading.Thread(target=self._wake_worker_loop, daemon=True)
            self._wake_worker_thread.start()

    def _wake_worker_loop(self) -> None:
        """Долгоживущий рабочий цикл проверки ключевого слова."""
        while self._is_running:
            try:
                audio = self._wake_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if audio is None:
                break

            try:
                self._handle_wake_audio(audio)
            except Exception as e:
                print(f"[AudioListener] Ошибка фоновой проверки Wake Word: {e}", file=sys.stderr)
            finally:
                self._wake_queue.task_done()
                with self._state_lock:
                    self._is_checking_wake = False

    def _async_check_wake_word(self, audio: np.ndarray) -> None:
        """Передает сэмпл в очередь фонового воркера без создания лишних потоков."""
        if self._is_checking_wake:
            return
        self._is_checking_wake = True
        self._ensure_wake_worker()
        try:
            self._wake_queue.put_nowait(audio)
        except queue.Full:
            self._is_checking_wake = False

    def _handle_wake_audio(self, audio: np.ndarray) -> None:
        """Инференс STT для проверки слова-триггера."""
        with self._state_lock:
            stt = self._stt_engine
            mode = self._mode
            words_list = list(self._wake_words)
            cb = self._on_wake_detected

        if not stt or mode != "wake_listen":
            return

        text = stt.transcribe(audio).lower().strip()
        if not text:
            return

        # Очищаем от знаков препинания для пословного анализа
        clean_text = re.sub(r"[^\w\s]", " ", text)
        words = clean_text.split()

        # Проверяем совпадение со словом-триггером
        matched = False
        for w in words_list:
            w_lower = w.lower()
            if w_lower in text or w_lower in words:
                matched = True
                break
            if len(w_lower) >= 4 and any(
                word.startswith(w_lower[:4]) or w_lower.startswith(word[:4])
                for word in words if len(word) >= 4
            ):
                matched = True
                break

        if matched and cb:
            tail_cmd = ""
            pattern = rf"(?:^|\s)(?:{'|'.join(re.escape(w) for w in words_list)})\w*[\s,]+(.+)"
            match_tail = re.search(pattern, text, flags=re.IGNORECASE)
            if match_tail:
                candidate = match_tail.group(1).strip()
                if len(candidate.split()) >= 1:
                    tail_cmd = candidate

            try:
                cb(tail_cmd)
            except TypeError:
                cb()

    def record_command(self, max_duration_sec: float = 8.0) -> np.ndarray:
        """
        Переводит существующий поток в режим записи команды и ждет паузы в речи.
        Никаких повторных открытий устройств sounddevice.
        """
        self._record_done_event.clear()

        if not self._is_running:
            self.start_stream()

        # Предотвращение состояния гонки с фоновой проверкой Wake Word (ARCH-4)
        wait_deadline = time.time() + 0.3
        while self._is_checking_wake and time.time() < wait_deadline:
            time.sleep(0.01)

        with self._state_lock:
            prev_mode = self._mode
            self._mode = "recording"
            self._record_buffer = []
            self._has_spoken = False
            self._silence_start = None
            self._record_start_time = time.time()
            self._max_duration_sec = max_duration_sec

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
        on_wake_detected: Callable[..., None],
        stt_engine: SpeechToText | None,
        wake_words: tuple[str, ...] = ("джарвис", "jarvis")
    ) -> None:
        """Включает фоновый анализ аудиопотока на слово «Джарвис»."""
        with self._state_lock:
            self._on_wake_detected = on_wake_detected
            self._stt_engine = stt_engine
            self._wake_words = wake_words
            self._mode = "wake_listen"
        if not self._is_running:
            self.start_stream()

    def stop_wake_word_loop(self) -> None:
        """Выключает фоновый поиск ключевого слова и останавливает запись при остановке агента."""
        with self._state_lock:
            self._mode = "idle"
            self._record_done_event.set()
            self._wake_buffer.clear()
            self._wake_speech_active = False
