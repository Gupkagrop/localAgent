"""
Генератор звуковых сигналов обратной связи (soft audio chimes) в формате WAV.
Создает мягкие синусоидальные тона с плавным затуханием (fade-in/fade-out).
"""
import os
import numpy as np
from scipy.io import wavfile

SAMPLE_RATE = 44100

def create_tone(freqs: list[float], duration: float = 0.25, volume: float = 0.25) -> np.ndarray:
    """Создает составной тон с плавным огибающим колоколом (Hanning window)."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    signal = np.zeros_like(t)
    for i, f in enumerate(freqs):
        # Добавляем небольшую задержку для арпеджио если частот несколько
        shift = int(i * 0.04 * SAMPLE_RATE)
        sub_t = t[shift:]
        tone = np.sin(2 * np.pi * f * sub_t)
        # Экспоненциальное затухание
        envelope = np.exp(-sub_t * 6.0)
        signal[shift:] += tone * envelope * (1.0 / len(freqs))
    
    # Нормализация и перевод в int16
    signal = signal / (np.max(np.abs(signal)) + 1e-6) * volume
    return (signal * 32767).astype(np.int16)

def main():
    sounds_dir = os.path.join(os.path.dirname(__file__), "sounds")
    os.makedirs(sounds_dir, exist_ok=True)
    
    # 1. Активация: мягкое восходящее мажорное созвучие (C5 -> G5)
    activate_tone = create_tone([523.25, 783.99], duration=0.22, volume=0.20)
    wavfile.write(os.path.join(sounds_dir, "activate.wav"), SAMPLE_RATE, activate_tone)
    
    # 2. Успех: подтверждающий светлый перелив (D5 -> F#5 -> A5)
    success_tone = create_tone([587.33, 739.99, 880.00], duration=0.30, volume=0.20)
    wavfile.write(os.path.join(sounds_dir, "success.wav"), SAMPLE_RATE, success_tone)
    
    # 3. Ошибка: мягкий нисходящий глухой сигнал (G4 -> E4)
    error_tone = create_tone([392.00, 329.63], duration=0.28, volume=0.22)
    wavfile.write(os.path.join(sounds_dir, "error.wav"), SAMPLE_RATE, error_tone)
    
    print("Звуковые файлы успешно сгенерированы в", sounds_dir)

if __name__ == "__main__":
    main()
