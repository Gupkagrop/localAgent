"""
Скрипт фоновой загрузки весов и токенизатора модели xlangai/Jedi-3B-1080p из Hugging Face Hub.
Использует snapshot_download с поддержкой докачки (resume).
"""
import sys
import time
from huggingface_hub import snapshot_download

MODEL_ID = "xlangai/Jedi-3B-1080p"

def main() -> None:
    print(f"[{time.strftime('%H:%M:%S')}] Инициализация скачивания модели '{MODEL_ID}'...")
    print(f"[{time.strftime('%H:%M:%S')}] Файлы кэшируются в стандартную директорию Hugging Face Hub.")
    
    try:
        local_dir = snapshot_download(
            repo_id=MODEL_ID,
            max_workers=4
        )
        print(f"\n[{time.strftime('%H:%M:%S')}] [SUCCESS] Модель '{MODEL_ID}' успешно загружена!")
        print(f"Локальный путь кэша: {local_dir}")
    except Exception as e:
        print(f"\n[{time.strftime('%H:%M:%S')}] [ERROR] Ошибка при скачивании модели: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
