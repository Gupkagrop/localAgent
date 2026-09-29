"""
Скрипт загрузки легковесной нейросетевой модели Piper TTS (ru_RU-dmitri-medium).
Загружает ONNX-веса (~60 МБ) и JSON-конфиг из официального репозитория Hugging Face.
"""
import os
import sys
import urllib.request
import time

MODEL_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/dmitri/medium/ru_RU-dmitri-medium.onnx"
CONFIG_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/dmitri/medium/ru_RU-dmitri-medium.onnx.json"

DEFAULT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "tts"))

def download_file(url: str, dest_path: str, description: str = "") -> bool:
    """Безопасно скачивает файл с отображением прогресса."""
    temp_path = dest_path + ".tmp"
    try:
        dest_dir = os.path.dirname(dest_path)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AntigravityTTS/1.0"}
        req = urllib.request.Request(url, headers=headers)
        
        print(f"Загрузка {description or os.path.basename(dest_path)}...")
        with urllib.request.urlopen(req, timeout=30) as response, open(temp_path, "wb") as out_file:
            total_size = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            block_size = 1024 * 1024  # 1 MB
            start_time = time.time()
            
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                downloaded += len(buffer)
                out_file.write(buffer)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    elapsed = max(0.1, time.time() - start_time)
                    speed_mb = (downloaded / (1024 * 1024)) / elapsed
            print()

        if total_size > 0 and downloaded < total_size:
            raise IOError(f"Загрузка прервана: получено {downloaded} из {total_size} байт.")

        os.replace(temp_path, dest_path)
        print(f"Успешно сохранено: {dest_path}")
        return True
    except Exception as e:
        print(f"\nОшибка загрузки {url}: {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        return False

def ensure_piper_model(target_dir: str = DEFAULT_DIR) -> tuple[str, str]:
    """
    Проверяет наличие файлов модели Piper. Если они отсутствуют — скачивает их.
    Возвращает пути: (model_onnx_path, config_json_path).
    """
    os.makedirs(target_dir, exist_ok=True)
    onnx_file = os.path.join(target_dir, "ru_RU-dmitri-medium.onnx")
    json_file = os.path.join(target_dir, "ru_RU-dmitri-medium.onnx.json")

    # Проверка наличия и целостности (ONNX должен быть не менее 50 МБ)
    need_download_onnx = not os.path.exists(onnx_file) or os.path.getsize(onnx_file) < 50 * 1024 * 1024
    need_download_json = not os.path.exists(json_file) or os.path.getsize(json_file) < 100

    if need_download_json:
        if not download_file(CONFIG_URL, json_file, "JSON-конфигурации модели"):
            raise RuntimeError("Не удалось загрузить конфигурационный файл Piper TTS.")

    if need_download_onnx:
        if not download_file(MODEL_URL, onnx_file, "нейросетевых весов Piper ONNX"):
            raise RuntimeError("Не удалось загрузить файл весов Piper TTS.")

    return onnx_file, json_file

if __name__ == "__main__":
    print("=" * 60)
    print("Утилита загрузки модели Piper TTS (ru_RU-dmitri-medium)")
    print("=" * 60)
    try:
        onnx_p, json_p = ensure_piper_model()
        print(f"\nМодель готова к работе:\nONNX: {onnx_p}\nJSON: {json_p}")
    except Exception as exc:
        print(f"\nКритическая ошибка: {exc}", file=sys.stderr)
        sys.exit(1)
