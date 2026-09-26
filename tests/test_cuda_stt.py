import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.speech_to_text import SpeechToText

print("--- ТЕСТ ЗАГРУЗКИ FASTER-WHISPER TURBO НА CUDA ---")
stt = SpeechToText(model_size="turbo", device="cuda")
print("Загружаю модель в память GPU (CUDA)...")
success = stt.load_model()
print("Статус загрузки:", success)
print("Используемое устройство:", stt.device)
if success:
    print("Модель успешно загружена на GPU!")
stt.unload_model()
print("Модель успешно выгружена из VRAM!")
