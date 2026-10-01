"""
Модульные тесты для звукового контура AudioListener.
Проверяют расчет RMS, логику VAD, пороги фильтрации шума для Wake Word и изоляцию от физических аудиоустройств.
"""
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from core.audio_listener import AudioListener, SAMPLE_RATE, CHUNK_SIZE


class TestAudioListener(unittest.TestCase):
    def setUp(self):
        self.vu_mock = MagicMock()
        self.listener = AudioListener(on_vu_meter=self.vu_mock)

    def test_initial_state(self):
        """Проверка начальных параметров и флагов слушателя."""
        self.assertEqual(self.listener._mode, "idle")
        self.assertTrue(self.listener.wake_word_enabled)
        self.assertEqual(self.listener.speech_energy_threshold, 0.002)
        self.assertEqual(self.listener.silence_threshold_ms, 400)

    def test_rms_calculation_silence(self):
        """Проверка расчета RMS для абсолютной тишины через статический метод класса."""
        silence = np.zeros(CHUNK_SIZE, dtype=np.float32)
        rms = AudioListener.calculate_rms(silence)
        self.assertEqual(rms, 0.0)

    def test_rms_calculation_sine_wave(self):
        """Проверка расчета RMS для тестового синусоидального сигнала."""
        t = np.linspace(0, 1, CHUNK_SIZE, endpoint=False)
        sine = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
        rms = AudioListener.calculate_rms(sine)
        # Для синусоиды амплитудой A RMS равен A / sqrt(2) ≈ 0.5 / 1.4142 ≈ 0.3535
        self.assertAlmostEqual(rms, 0.3535, places=2)
        self.assertGreater(rms, self.listener.speech_energy_threshold)

    def test_wake_word_disabled_skips_processing(self):
        """Если wake_word_enabled=False, обработка Wake Word не выполняется."""
        self.listener.wake_word_enabled = False
        chunk = np.ones(CHUNK_SIZE, dtype=np.float32) * 0.1
        self.listener._process_wake_word(chunk, rms=0.1)

        self.assertFalse(self.listener._wake_speech_active)
        self.assertEqual(len(self.listener._wake_buffer), 0)
        self.assertEqual(len(self.listener._wake_pre_buffer), 0)

    def test_wake_word_short_noise_filtered_out(self):
        """Короткий шум (< 0.50 с) отбрасывается без запуска STT."""
        with patch.object(self.listener, "_async_check_wake_word") as mock_check:
            # Симулируем 0.20 секунды речи (меньше минимального порога 0.50 с)
            chunks_count = int(SAMPLE_RATE * 0.20 / CHUNK_SIZE)
            chunk = np.ones(CHUNK_SIZE, dtype=np.float32) * 0.05

            for _ in range(chunks_count):
                self.listener._process_wake_word(chunk, rms=0.05)

            # Симулируем окончание фразы и тишину 350 мс
            silence_chunk = np.zeros(CHUNK_SIZE, dtype=np.float32)
            self.listener._wake_silence_start = 100.0
            with patch("time.time", return_value=100.4):  # прошло 400 мс тишины
                self.listener._process_wake_word(silence_chunk, rms=0.0)

            # STT не должен вызываться для короткого щелчка или шума
            mock_check.assert_not_called()
            self.assertFalse(self.listener._wake_speech_active)
            self.assertEqual(len(self.listener._wake_buffer), 0)

    def test_wake_word_sufficient_phrase_triggers_check(self):
        """Речь длительностью >= 0.50 с после тишины отправляется на проверку слова-триггера."""
        with patch.object(self.listener, "_async_check_wake_word") as mock_check:
            # Симулируем 0.60 секунды речи (превышает порог 0.50 с)
            chunks_count = int(SAMPLE_RATE * 0.60 / CHUNK_SIZE)
            chunk = np.ones(CHUNK_SIZE, dtype=np.float32) * 0.05

            for _ in range(chunks_count):
                self.listener._process_wake_word(chunk, rms=0.05)

            self.assertTrue(self.listener._wake_speech_active)

            # Симулируем тишину более 320 мс
            silence_chunk = np.zeros(CHUNK_SIZE, dtype=np.float32)
            self.listener._wake_silence_start = 100.0
            with patch("time.time", return_value=100.4):
                self.listener._process_wake_word(silence_chunk, rms=0.0)

            mock_check.assert_called_once()
            self.assertFalse(self.listener._wake_speech_active)

    def test_stop_wake_word_loop_resets_mode(self):
        """Метод stop_wake_word_loop сбрасывает режим в idle."""
        self.listener._mode = "wake_listen"
        self.listener.stop_wake_word_loop()
        self.assertEqual(self.listener._mode, "idle")

    def test_get_input_devices_mocked(self):
        """Проверка получения списка микрофонов с фильтрацией системных устройств."""
        mock_devices = [
            {"name": "Встроенный микрофон Realtek", "max_input_channels": 2, "hostapi": 0},
            {"name": "Динамики Realtek", "max_input_channels": 0, "hostapi": 0},
            {"name": "USB Наушники Микрофон", "max_input_channels": 1, "hostapi": 0}
        ]
        with patch("sounddevice.query_devices", return_value=mock_devices):
            devices = AudioListener.get_input_devices()
            self.assertEqual(len(devices), 2)
            self.assertEqual(devices[0]["name"], "Встроенный микрофон Realtek")
            self.assertEqual(devices[1]["name"], "USB Наушники Микрофон")

    def test_get_input_devices_exception_handled(self):
        """При исключении в sounddevice возвращается пустой список без падения."""
        with patch("sounddevice.query_devices", side_effect=Exception("PortAudio error")):
            devices = AudioListener.get_input_devices()
            self.assertEqual(devices, [])


if __name__ == "__main__":
    unittest.main()
