"""
Модуль синтеза речи (Text-to-Speech).
Использует нативный голосовой движок Windows SAPI5 (с поддержкой русских голосов, 0 МБ VRAM)
с асинхронным воспроизведением в фоновом потоке и гарантированным освобождением COM-ресурсов.
"""
import threading
from typing import Optional

class TextToSpeech:
    def __init__(self, voice_name: Optional[str] = None, speed: float | int = 0):
        self.voice_name = voice_name
        # SAPI5 ожидает целочисленный Rate в диапазоне [-10, 10].
        # Если передан коэффициент скорости (например 1.0 или 1.2), масштабируем его:
        if isinstance(speed, float) and 0.1 <= speed <= 3.0:
            converted_speed = int((speed - 1.0) * 10)
        else:
            converted_speed = int(speed)
        self.speed: int = max(-10, min(10, converted_speed))
        self._lock = threading.Lock()

    def speak(self, text: str, async_mode: bool = True) -> None:
        """Озвучивает текст без блокировки основного потока приложения."""
        if not text.strip():
            return

        def _worker():
            with self._lock:
                try:
                    import pythoncom
                    import win32com.client
                    pythoncom.CoInitialize()
                    try:
                        speaker = win32com.client.Dispatch("SAPI.SpVoice")
                        speaker.Rate = self.speed
                        
                        # Пытаемся выбрать русский голос по имени или языку
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
                    print(f"[TTS Error] {e}")

        if async_mode:
            threading.Thread(target=_worker, daemon=True).start()
        else:
            _worker()
