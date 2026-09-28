> [!NOTE]
> **Паспорт проекта для ИИ-агентов:** Данный файл является единым базовым контрактом (Уровень 1) архитектуры контекста Antigravity Voice & Vision Assistant. Регламентирует стек, команды валидации, правила написания кода, архитектурные ограничения и запрещенные паттерны.

# Antigravity Voice & Vision Assistant (Jarvis) — Контракт ИИ-агентов

Автономный локальный голосовой ассистент и мультимодальный агент компьютерного управления (Computer-Use) для Windows 11 с нативной поддержкой физической клавиши Copilot (`Shift + Win + F23`), распознаванием речи Faster-Whisper Turbo на CUDA и моделью зрения Jedi-3B (4-bit NF4) на GPU NVIDIA GeForce RTX 5050 (8 ГБ GDDR7).

---

## 1. Стек технологий (Tech Stack)

- **Платформа и ОС:** Windows 11 x64, сессия `WinSta0\Default`.
- **Среда выполнения и пакетный менеджер:** Python 3.12, изолированное окружение `.venv` под управлением `uv`.
- **Графический интерфейс:** PyQt6 (Fluent 2 Dark стилизация, немодальные High DPI оверлеи).
- **Распознавание речи (STT):** `faster-whisper` (модель `turbo`) через C++ акселератор `ctranslate2` (CUDA 12.8, float16) — без оверхеда PyTorch в GUI-процессе (~1.4–1.6 ГБ VRAM).
- **Компьютерное зрение (Computer-Use):** `xlangai/Jedi-3B-1080p` (fallback: `Qwen/Qwen2.5-VL-3B-Instruct`) в квантовании `bitsandbytes` 4-bit NF4 в отдельном воркер-процессе (~3.0–3.2 ГБ VRAM).
- **Интеграция с Windows 11:**
  - Захват экрана: прямой Win32 GDI `BitBlt` (~4 мс) с автоопределением активного монитора.
  - Ввод: Unicode `SendInput` ($\le 20$ символов) + Clipboard `Ctrl+V` ($> 20$ символов).
  - Звук: `pycaw` (Audio Ducking с приглушением до 25%).
  - Клавиатура: `pynput` с хуком `WH_KEYBOARD_LL` (Copilot `VK_F23 = 0x86` / `0x8E`).

---

## 2. Команды разработки и верификации (Commands)

```powershell
# Установка и синхронизация зависимостей
uv sync

# Запуск основного приложения (PyQt6 GUI)
.\.venv\Scripts\python.exe main.py

# Запуск полного сьюта unit-тестов (92 теста, 100% PASS)
.\.venv\Scripts\python.exe -m unittest discover tests

# Комплексная системная проверка всех 10 подсистем (10/10 OK)
.\.venv\Scripts\python.exe tests/full_verification.py

# Фоновая предзагрузка весов VLM Jedi-3B в кэш Hugging Face
.\.venv\Scripts\python.exe download_vision_model.py

# Генерация тихого ярлыка на рабочем столе Windows
.\.venv\Scripts\python.exe create_shortcut.py
```

---

## 3. Стандарты кода (Code Standards)

1. **Языковой стандарт:**
   - Код, названия переменных, функций, классов и файлов — строго на **английском языке**.
   - Комментарии в коде, docstrings, аннотации и коммиты Git — строго на **русском языке** по стандарту Conventional Commits (`исправление: ...`, `функция: ...`, `рефакторинг: ...`).
2. **Структурная чистота (Early Returns):**
   - Запрещена вложенность глубже 3 уровней. Использовать guard clauses и ранние возвраты.
   - Длина функций: до 30–40 строк. Большие функции декомпозировать на вспомогательные.
3. **Строгая типизация (Zero-Any):**
   - Полный запрет на `Any` или неявные типы аргументов и возвращаемых значений.
   - Обязательное использование тайп-хинтинга Python (`typing`, `Union`, `Optional`, `Tuple`).
4. **Запрет заглушек (Zero-Placeholders):**
   - Категорически запрещены комментарии `// TODO`, `pass` вместо логики или нереализованные заглушки.

---

## 4. Архитектурные правила (Architecture Rules)

1. **Двухпроцессная изоляция VRAM:**
   - Библиотеки `torch`, `torchvision`, `transformers`, `bitsandbytes` **категорически запрещены** к импорту в основном GUI-процессе (`main.py`, `core/executor.py`, `core/speech_to_text.py` и др.).
   - Все операции VLM выполняются строго внутри процесса `core/vision_agent.py`.
2. **Безопасность вызовов PowerShell:**
   - Системные команды исполняются только через Base64 `-EncodedCommand` (UTF-16LE) с обязательным `shell=False`.
3. **Двухуровневая маршрутизация:**
   - `DecisionEngine`: Fast-Path (0 мс, системные команды, окна, ссылки) выполняется мгновенно; Vision-Path передается в очередь воркера только для сложных интерфейсных сценариев.
4. **Fail-Safe защита:**
   - Перехват `ESC` или смещение мыши $>40$ px немедленно прерывает выполнение компьютерного управления.
5. **Модульная архитектура (Уровень 3):**
   - Детализация подсистем описана в [`docs/architecture/`](file:///c:/Users/denis/Documents/antigravity/localAgent/docs/architecture/):
     * [Схемы данных и хранилище](file:///c:/Users/denis/Documents/antigravity/localAgent/docs/architecture/database.md)
     * [API, IPC и маршрутизация](file:///c:/Users/denis/Documents/antigravity/localAgent/docs/architecture/api.md)
     * [Графический интерфейс PyQt6](file:///c:/Users/denis/Documents/antigravity/localAgent/docs/architecture/frontend.md)
     * [Компьютерное зрение и Screen Tools](file:///c:/Users/denis/Documents/antigravity/localAgent/docs/architecture/vision_agent.md)

---

## 5. Запрещенные паттерны (Prohibited Patterns)

- ❌ Запрещен импорт `torch` в главном процессе (приводит к конфликтам DLL и утечкам VRAM).
- ❌ Запрещены вызовы shell с объединением строк (`f"powershell {cmd}"`) из-за уязвимостей инъекций.
- ❌ Запрещены деструктивные операции ОС без интерактивного подтверждения через `ask_question`.
- ❌ Запрещено хранение секретов и токенов в кодовой базе (использовать `.env`).
