"""
Модуль распознавания речи (STT) на базе Faster-Whisper.
Задействует CUDA на GPU NVIDIA RTX 5050 с поддержкой полной выгрузки из VRAM
и потокобезопасной блокировкой (thread-safe lock) для исключения взаимных блокировок.
"""
import os
import sys
import gc
import threading
from typing import Optional
import numpy as np

# Регистрация путей к CUDA DLL (cublas64_12.dll, cudnn) для CTranslate2
for dll_sub in [
    os.path.join(sys.prefix, 'Lib', 'site-packages', 'ctranslate2'),
    os.path.join(sys.prefix, 'Lib', 'site-packages', 'nvidia', 'cublas', 'bin'),
    os.path.join(sys.prefix, 'Lib', 'site-packages', 'nvidia', 'cudnn', 'bin'),
]:
    if os.path.exists(dll_sub):
        try:
            os.add_dll_directory(dll_sub)
            os.environ["PATH"] = dll_sub + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass

from faster_whisper import WhisperModel

class SpeechToText:
    def __init__(self, model_size: str = "turbo", device: str = "cuda"):
        self.model_size = model_size
        self.device = device
        self._model: Optional[WhisperModel] = None
        self._lock = threading.Lock()
        self._initial_prompt: str = (
            "Джарвис, открой, запусти, сделай, Antigravity, agy, терминал, git, commit, push, "
            "powershell, chrome, браузер, ютуб, калькулятор, блокнот, telegram, "
            "visual studio code, громкость, тише, громче, пауза, трек, поиск."
        )

    def load_model(self) -> bool:
        """Загружает модель в память GPU (CUDA) или CPU (потокобезопасно)."""
        with self._lock:
            return self._load_model_unlocked()

    def unload_model(self) -> None:
        """Полностью выгружает модель из VRAM для освобождения ресурсов под игры."""
        with self._lock:
            if self._model is not None:
                del self._model
                self._model = None
                gc.collect()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except ImportError:
                    pass

    def is_loaded(self) -> bool:
        return self._model is not None

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        """Транскрибирует нормализованный массив сэмплов float32 в строку текста."""
        with self._lock:
            if not self.is_loaded():
                if not self._load_model_unlocked():
                    return ""

            if len(audio_data) == 0:
                return ""

            # Убеждаемся что формат данных float32
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)

            # Нормализация амплитуды и удаление постоянной составляющей (DC offset)
            audio_data = audio_data - np.mean(audio_data)
            peak = float(np.max(np.abs(audio_data))) if len(audio_data) > 0 else 0.0
            if peak > 0.003:
                # Масштабируем тихий сигнал микрофона ноутбука до целевого уровня 0.85
                scale = min(15.0, 0.85 / peak)
                audio_data = audio_data * scale

            try:
                segments, info = self._model.transcribe(
                    audio_data,
                    beam_size=5,
                    best_of=5,
                    temperature=0.0,
                    language="ru",
                    initial_prompt=self._initial_prompt,
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=250,
                        speech_pad_ms=200
                    ),
                    condition_on_previous_text=False
                )
                text = " ".join([seg.text.strip() for seg in segments]).strip()
                return text
            except Exception as e:
                print(f"[STT Error] {e}")
                return ""

    def _load_model_unlocked(self) -> bool:
        """Вспомогательный метод загрузки, вызываемый изнутри уже захваченного лока."""
        if self._model is not None:
            return True
        try:
            compute_type = "float16" if self.device == "cuda" else "int8"
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=compute_type,
                cpu_threads=4,
                download_root=os.path.expanduser("~/.cache/huggingface/hub")
            )
            return True
        except Exception:
            try:
                self._model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=4,
                    download_root=os.path.expanduser("~/.cache/huggingface/hub")
                )
                self.device = "cpu"
                return True
            except Exception:
                return False
