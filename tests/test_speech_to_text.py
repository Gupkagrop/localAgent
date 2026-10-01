"""
Модульные тесты подсистемы распознавания речи Faster-Whisper (core/speech_to_text.py).
Проверяют инициализацию, загрузку на GPU CUDA/CPU, выгрузку из VRAM и транскрипцию аудио.
"""
import os
import unittest
from unittest.mock import patch, MagicMock
import numpy as np

from core.speech_to_text import SpeechToText


class TestSpeechToText(unittest.TestCase):
    """Тестирование класса SpeechToText."""

    def setUp(self):
        self.stt = SpeechToText(model_size="turbo", device="cuda")

    def test_init(self):
        """Проверка инициализации параметров по умолчанию."""
        self.assertEqual(self.stt.model_size, "turbo")
        self.assertEqual(self.stt.device, "cuda")
        self.assertFalse(self.stt.is_loaded())
        self.assertIn("Джарвис", self.stt._initial_prompt)

    @patch("faster_whisper.WhisperModel")
    def test_load_model_cuda_success(self, mock_whisper_cls):
        """Проверка успешной загрузки модели на GPU с типом float16."""
        mock_instance = MagicMock()
        mock_whisper_cls.return_value = mock_instance

        success = self.stt.load_model()
        self.assertTrue(success)
        self.assertTrue(self.stt.is_loaded())
        mock_whisper_cls.assert_called_once_with(
            "turbo",
            device="cuda",
            compute_type="float16",
            cpu_threads=4,
            download_root=os.path.expanduser("~/.cache/huggingface/hub")
        )

    @patch("faster_whisper.WhisperModel")
    def test_load_model_fallback_cpu_on_cuda_error(self, mock_whisper_cls):
        """Проверка автоматического фоллбэка на CPU при сбое инициализации CUDA."""
        mock_instance_cpu = MagicMock()
        mock_whisper_cls.side_effect = [RuntimeError("CUDA driver out of date"), mock_instance_cpu]

        success = self.stt.load_model()
        self.assertTrue(success)
        self.assertTrue(self.stt.is_loaded())
        self.assertEqual(self.stt.device, "cpu")
        self.assertEqual(mock_whisper_cls.call_count, 2)
        mock_whisper_cls.assert_called_with(
            "turbo",
            device="cpu",
            compute_type="int8",
            cpu_threads=4,
            download_root=os.path.expanduser("~/.cache/huggingface/hub")
        )

    @patch("faster_whisper.WhisperModel")
    def test_load_model_direct_cpu(self, mock_whisper_cls):
        """Проверка прямой загрузки на CPU если указано device='cpu'."""
        stt_cpu = SpeechToText(model_size="turbo", device="cpu")
        mock_instance = MagicMock()
        mock_whisper_cls.return_value = mock_instance

        success = stt_cpu.load_model()
        self.assertTrue(success)
        self.assertTrue(stt_cpu.is_loaded())
        mock_whisper_cls.assert_called_once_with(
            "turbo",
            device="cpu",
            compute_type="int8",
            cpu_threads=4,
            download_root=os.path.expanduser("~/.cache/huggingface/hub")
        )

    @patch("faster_whisper.WhisperModel", side_effect=Exception("Ошибка загрузки весов"))
    def test_load_model_failure(self, mock_whisper_cls):
        """Проверка обработки ошибки при полном сбое загрузки модели."""
        success = self.stt.load_model()
        self.assertFalse(success)
        self.assertFalse(self.stt.is_loaded())

    def test_unload_model(self):
        """Проверка полной выгрузки модели и сброса состояния."""
        self.stt._model = MagicMock()
        self.assertTrue(self.stt.is_loaded())

        self.stt.unload_model()
        self.assertFalse(self.stt.is_loaded())
        self.assertIsNone(self.stt._model)

    def test_transcribe_empty_audio(self):
        """Транскрипция пустого массива сэмплов возвращает пустую строку без вызова модели."""
        self.stt._model = MagicMock()
        result = self.stt.transcribe(np.array([], dtype=np.float32))
        self.assertEqual(result, "")
        self.stt._model.transcribe.assert_not_called()

    def test_transcribe_audio_success(self):
        """Проверка транскрипции нормализованного синусоидального аудиосигнала."""
        mock_model = MagicMock()
        seg1 = MagicMock()
        seg1.text = " Джарвис, открой "
        seg2 = MagicMock()
        seg2.text = " браузер "
        mock_model.transcribe.return_value = ([seg1, seg2], None)
        self.stt._model = mock_model

        # Создаем 1 секунду синусоиды 440 Гц
        sr = 16000
        t = np.linspace(0, 1.0, sr, endpoint=False)
        audio = (np.sin(2 * np.pi * 440 * t) * 0.1).astype(np.float32)

        text = self.stt.transcribe(audio)
        self.assertEqual(text, "Джарвис, открой браузер")
        mock_model.transcribe.assert_called_once()

    def test_transcribe_int16_conversion(self):
        """Проверка автоматической конвертации int16 в float32 при вызове."""
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], None)
        self.stt._model = mock_model

        audio_int16 = np.zeros(1600, dtype=np.int16)
        text = self.stt.transcribe(audio_int16)
        self.assertEqual(text, "")
        mock_model.transcribe.assert_called_once()
        call_audio = mock_model.transcribe.call_args[0][0]
        self.assertEqual(call_audio.dtype, np.float32)

    def test_transcribe_exception_handling(self):
        """Проверка обработки исключений во время транскрипции."""
        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("GPU memory allocation error")
        self.stt._model = mock_model

        audio = np.ones(1600, dtype=np.float32) * 0.05
        text = self.stt.transcribe(audio)
        self.assertEqual(text, "")


if __name__ == "__main__":
    unittest.main()
