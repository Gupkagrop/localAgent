import sys
import ctranslate2
import faster_whisper
import sounddevice as sd

print("=== ДИАГНОСТИКА ОКРУЖЕНИЯ ===")
print("Python:", sys.version)
print("CTranslate2 version:", ctranslate2.__version__)

try:
    cuda_types = ctranslate2.get_supported_compute_types("cuda")
    print("CUDA compute types:", cuda_types)
except Exception as e:
    print("CUDA недоступен в ctranslate2:", e)

try:
    cpu_types = ctranslate2.get_supported_compute_types("cpu")
    print("CPU compute types:", cpu_types)
except Exception as e:
    print("CPU compute types error:", e)

# Проверяем микрофоны
try:
    devices = sd.query_devices()
    input_devs = [d for d in devices if d.get("max_input_channels", 0) > 0]
    print(f"Обнаружено микрофонов: {len(input_devs)}")
    for d in input_devs:
        print(f" - {d['name']} (входных каналов: {d['max_input_channels']})")
except Exception as e:
    print("Ошибка опроса микрофонов:", e)

print("=== КОНЕЦ ДИАГНОСТИКИ ===")
