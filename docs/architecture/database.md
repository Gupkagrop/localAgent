> [!NOTE]
> **Назначение документа:** Описание архитектуры хранения данных, конфигурационных схем и кэша моделей ассистента Antigravity Voice & Vision Assistant. Документ регламентирует форматы JSON-хранилищ, валидацию настроек и структуру кэширования нейросетей на диске.

# Схемы данных и хранилище конфигураций

В архитектуре ассистента функции персистентного слоя выполняют локальные JSON-хранилища в каталоге `config/`, системный реестр Windows 11 и кэш моделей Hugging Face Hub / Piper TTS.

---

## 1. Конфигурация приложения (`config/settings.json`)

Файл хранит пользовательские параметры работы аудиоконтура, автозагрузки, синтезатора речи (TTS), распознавания речи (STT) и ограничений автономного Vision-агента.

### Актуальная структура схемы:
```json
{
  "autostart_with_windows": false,                 // bool: Автозагрузка с Windows 11 через реестр HKCU Run
  "start_minimized": false,                        // bool: Запуск в свернутом виде (в системный трей)
  "close_behavior": "ask",                         // string: Поведение при закрытии окна ("ask" | "tray" | "exit")
  "default_activation_mode": "wake_word_and_copilot", // string: Режим активации ("wake_word_and_copilot" | "copilot_only")
  "wake_word_enabled": true,                       // bool: Включено ли фоновое слово-триггер
  "wake_word": "джарвис",                          // string: Локальное слово-триггер для Wake Word
  "audio_ducking_enabled": true,                   // bool: Автоматическое приглушение системного звука Windows
  "audio_ducking_level": 0.2,                      // float: Уровень приглушения фонового звука (0.0 .. 1.0)
  "sound_cues_enabled": true,                      // bool: Звуковые сигналы активации/успеха/ошибки
  "tts_enabled": true,                             // bool: Озвучивание ответов и шагов агента
  "tts_voice": "piper:ru_RU-dmitri-medium",        // string: Идентификатор активного голоса (Piper ONNX или SAPI5)
  "tts_speed": 1.0,                                // float: Скорость речи (0.5 .. 2.0)
  "audio_device_index": 1,                         // int | null: Индекс микрофона (null = системный по умолчанию)
  "stt_model": "turbo",                            // string: Модель Faster-Whisper ("turbo" | "small" | "base")
  "confirm_dangerous_actions": true,               // bool: Запрос подтверждения опасных системных действий
  "vision_max_steps": 8,                           // int: Максимальное количество шагов Vision-агента (1..15)
  "vision_model": "xlangai/Jedi-3B-1080p",         // string: Модель компьютерного зрения VLM
  "vision_auto_focus_browser": true                // bool: Автоматический перевод фокуса в окно браузера
}
```

---

## 2. Реестр команд и алиасов (`config/commands.json`)

Файл служит базой знаний для мгновенного Fast-Path роутера (`DecisionEngine`) и строки быстрого ввода `SpotlightBar`.

### Актуальная структура схемы:
```json
{
  "apps": {
    "браузер": "chrome.exe",
    "хром": "chrome.exe",
    "калькулятор": "calc.exe",
    "блокнот": "notepad.exe",
    "проводник": "explorer.exe",
    "диспетчер задач": "taskmgr.exe",
    "телеграм": "telegram.exe",
    "терминал": "wt.exe",
    "antigravity": "antigravity"
  },
  "urls": {
    "подписки ютуб": "https://www.youtube.com/feed/subscriptions",
    "тренды ютуб": "https://www.youtube.com/feed/trending",
    "сообщения вк": "https://vk.com/im",
    "новости вк": "https://vk.com/feed",
    "тренды гитхаб": "https://github.com/trending",
    "ютуб": "https://www.youtube.com",
    "гитхаб": "https://github.com",
    "вк": "https://vk.com",
    "почта": "https://mail.google.com"
  },
  "antigravity": {
    "gui_window_names": ["Antigravity", "antigravity"],
    "cli_executable": "agy"
  }
}
```

---

## 3. Кэширование весов нейросетей на диске

- **Whisper Turbo:** Загружается через движок `faster-whisper` и CTranslate2 в локальный кэш `~/.cache/huggingface/hub/models--Systran--faster-whisper-turbo` (или переменную окружения `HF_HOME`).
- **Jedi-3B-1080p (4-bit NF4):** Веса кэшируются стандартным механизмом Hugging Face Hub (`snapshot_download(repo_id="xlangai/Jedi-3B-1080p")`).
- **Piper Neural TTS (`ru_RU-dmitri-medium`):** Веса ONNX (~60.3 МБ) и JSON-конфигурация хранятся локально в `models/tts/`. Инференс выполняется исключительно на CPU через `onnxruntime` (0 МБ оверхеда VRAM).

---

## 4. Логирование и временные дампы (`logs/`)

- `logs/assistant.log`: Общий журнал работы главного GUI-процесса.
- `logs/vision_worker.log`: Логи изолированного процесса зрения, отладочная информация инференса и парсинга действий.
