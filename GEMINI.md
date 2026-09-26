> [!NOTE]
> Данный файл содержит архитектурное описание, инструкции по запуску, стек технологий и стандарты разработки локального голосового ассистента **Antigravity Voice**. Предназначен для разработчиков и ИИ-агентов, работающих с проектом.

# Antigravity Voice Assistant

Автономный локальный голосовой ассистент для Windows 11 с нативной поддержкой аппаратной клавиши **Copilot**, минимальным расходом видеопамяти и глубокой интеграцией с IDE **Antigravity 2.0** и **Antigravity CLI** (`agy`).

Разработан и оптимизирован для ноутбуков с дискретной видеокартой **NVIDIA GeForce RTX 5050 Laptop GPU (8 ГБ GDDR7)**.

---

## 1. Стек технологий

* **Язык и среда:** Python 3.12 (изолированное виртуальное окружение `.venv` под управлением `uv`).
* **Графический интерфейс:** `PyQt6` с темной темой Windows 11 Fluent 2 Dark и прокручиваемыми областями `QScrollArea`.
* **Распознавание речи (STT):** `faster-whisper` (модель Small, ~460 МБ) с аппаратным ускорением **CUDA float16** на базе движка `ctranslate2 4.8.2`. Включает бандл библиотек `nvidia-cublas-cu12` и `nvidia-cudnn-cu12` (`cublas64_12.dll`, `cudnn64_9.dll`).
* **Модуль принятия решений (Decision Engine):**
  - **Fast-Path:** моментальный семантический роутер команд (0 мс задержки, 0 МБ VRAM).
  - **Локальная LLM:** поддержка `Qwen2.5-1.5B-Instruct-Q4_K_M.gguf` (~1.1 ГБ) с встроенным загрузчиком прямо из GUI.
* **Аудиоконтур:** `sounddevice` с архитектурой *Single Persistent Stream* (единый непрерывный поток, постоянный живой VU-метр, отсутствие ошибок WASAPI `PaErrorCode -9999`).
* **Audio Ducking:** `pycaw` (Windows Core Audio API) — автоматическое приглушение системного звука до 20% во время записи голоса.
* **Синтез речи (TTS):** Windows SAPI5 (русские системные голоса, 0 МБ VRAM).
* **Аппаратный перехватчик:** `pynput` с низкоуровневым системным фильтром `win32_event_filter` (перехват официального кода Windows SDK `VK_F23 = 0x86` и `0x8E`, `VK_APPS = 0x5D`, `Win + Shift + C`, резервного `Ctrl + Shift + J` и маскирование `VK_CONTROL` для блокировки поиска Windows).

---

## 2. Структура проекта

```text
localAgent/
├── config/
│   ├── settings.json           # Конфигурация приложения (режим старта, трей, звук)
│   └── commands.json           # Сопоставление команд, приложений и URL
├── core/
│   ├── audio_listener.py       # Единый аудиопоток, VAD, VU-метр, Wake Word «Джарвис»
│   ├── audio_ducking.py        # Управление мастер-громкостью Windows (Audio Ducking)
│   ├── speech_to_text.py       # Faster-Whisper Small (CUDA float16) с lock и 0 МБ VRAM
│   ├── decision_engine.py      # Роутер команд Fast-Path + GGUF API загрузки
│   ├── text_to_speech.py       # Windows SAPI5 синтезатор
│   ├── keyboard_hook.py        # Перехватчик Copilot (pynput + VK_CONTROL маскирование)
│   └── executor.py             # Исполнитель: Antigravity CLI/GUI, громкость, софт
├── gui/
│   ├── main_window.py          # Панель управления с 6 карточками статуса и QScrollArea
│   ├── floating_pill.py        # Полупрозрачный оверлей-пилюля со статусом распознавания
│   ├── spotlight_bar.py        # Плавающая поисковая строка Spotlight (центр экрана)
│   ├── close_dialog.py         # Диалог подтверждения закрытия («Запомнить выбор»)
│   ├── tray_manager.py         # Иконка системного трея Windows и контекстное меню
│   └── styles.py               # Fluent 2 Dark тема с адаптивной прокруткой
├── models/                     # Каталог весов локальной LLM (Qwen2.5 GGUF)
├── sounds/                     # WAV-сигналы: activate, success, error
├── tests/
│   ├── check_env.py            # Диагностика установленных пакетов и CUDA
│   ├── test_cuda_stt.py        # Тест Faster-Whisper на GPU
│   ├── test_components.py      # 18 модульных тестов компонентов
│   ├── smoke_test.py           # Тест инициализации координатора и GUI
│   └── full_verification.py    # Сквозной валидационный тест всех 8 систем
├── create_shortcut.py          # Скрипт создания ярлыка Antigravity Voice.lnk
├── main.py                     # Точка входа координатора приложения
├── DETAILED_PLAN.md            # Чек-лист реализации и статус компонентов
└── GEMINI.md                   # Архитектурное руководство и инструкции
```

---

## 3. Инструкции по запуску и управлению

### Обычный запуск (для пользователя):
* Двойной клик по ярлыку на рабочем столе: `Antigravity Voice.lnk`.
* Или через командную строку:
  ```powershell
  Set-Location "C:\Users\denis\Documents\antigravity\localAgent"
  .\.venv\Scripts\python.exe main.py
  ```

### Тихий запуск (в трей):
```powershell
.\.venv\Scripts\pythonw.exe main.py --minimized
```

### Запуск тестов:
```powershell
# Модульные тесты компонентов (20 тестов)
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m unittest tests/test_components.py

# Сквозной тест всех 8 систем
$env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\python.exe tests/full_verification.py
```

---

## 4. Поведение аппаратной клавиши Copilot

1. **Короткий клик (< 0.4 сек):**
   * Если ассистент активен: воспроизводится мягкий звук `activate.wav`, приглушается фоновый звук системы (Audio Ducking), всплывает полупрозрачная пилюля и включается запись команды (Tap-to-Talk).
   * Если ассистент остановлен: всплывает диалог с предложением запустить систему.
2. **Удержание (>= 0.4 сек):**
   * По центру экрана всплывает командная строка **Spotlight** с историей команд (`Вверх`/`Вниз`) и подсказками быстрых действий.
3. **Блокировка поиска Windows:**
   * При каждом обнаружении `VK_F23` hook посылает кратковременный синтетический сигнал `VK_CONTROL` (`0x11`), что исключает открытие меню Пуск и Windows Search.
