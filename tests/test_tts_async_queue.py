"""
Модульные тесты асинхронного синтеза речи и очередей TextToSpeech (core/text_to_speech.py).
Проверяют неблокирующий вызов speak(async_mode=True), потокобезопасность блокировки _lock,
логику выбора голоса и фоллбэк на SAPI5 при сбое Piper TTS.
"""
import time
import unittest
from unittest.mock import patch, MagicMock

from core.text_to_speech import TextToSpeech


class TestTextToSpeechAsync(unittest.TestCase):
    """Тестирование асинхронной работы и отказоустойчивости TextToSpeech."""

    def test_speak_async_non_blocking(self):
        """Асинхронный вызов speak(async_mode=True) возвращает управление немедленно."""
        tts = TextToSpeech()
        call_started = False
        call_finished = False

        def slow_speak(text):
            nonlocal call_started, call_finished
            call_started = True
            time.sleep(0.3)
            call_finished = True
            return True

        with patch.object(tts, "_speak_piper", side_effect=slow_speak):
            start_time = time.time()
            tts.speak("Быстрая команда без блокировки GUI", async_mode=True)
            elapsed = time.time() - start_time

            # Метод должен вернуться практически мгновенно (< 50 мс)
            self.assertLess(elapsed, 0.08, "Асинхронный вызов tts.speak заблокировал вызывающий поток!")

            # Ожидаем завершения фонового потока
            time.sleep(0.4)
            self.assertTrue(call_started)
            self.assertTrue(call_finished)

    def test_speak_fallback_to_sapi5_on_piper_failure(self):
        """При сбое Piper TTS происходит автоматический переход на Windows SAPI5."""
        tts = TextToSpeech(voice_name="piper:ru_RU-dmitri-medium")

        with patch.object(tts, "_speak_piper", return_value=False) as mock_piper, \
             patch.object(tts, "_speak_sapi5") as mock_sapi:
            tts.speak("Тестовое сообщение", async_mode=False)

            mock_piper.assert_called_once_with("Тестовое сообщение")
            mock_sapi.assert_called_once_with("Тестовое сообщение")

    def test_speak_fallback_to_sapi5_on_piper_exception(self):
        """При возникновении исключения в Piper TTS происходит безопасный переход на SAPI5."""
        tts = TextToSpeech(voice_name="dmitri")

        with patch.object(tts, "_speak_piper", side_effect=RuntimeError("ONNX Runtime failure")) as mock_piper, \
             patch.object(tts, "_speak_sapi5") as mock_sapi:
            tts.speak("Тест сбоя", async_mode=False)

            mock_piper.assert_called_once()
            mock_sapi.assert_called_once_with("Тест сбоя")

    def test_concurrent_speaks_thread_safety(self):
        """Проверка потокобезопасности при конкурентных вызовах из нескольких потоков."""
        import threading
        tts = TextToSpeech()
        processed_texts: list[str] = []

        def fake_speak(text):
            time.sleep(0.02)
            processed_texts.append(text)
            return True

        with patch.object(tts, "_speak_piper", side_effect=fake_speak):
            threads = []
            for i in range(5):
                t = threading.Thread(target=tts.speak, args=(f"Фраза {i}", False))
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=2.0)

            self.assertEqual(len(processed_texts), 5)


if __name__ == "__main__":
    unittest.main()
