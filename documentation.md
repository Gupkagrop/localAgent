> [!NOTE]
> Данный документ является официальным исчерпывающим техническим руководством по кодовой базе **Antigravity Voice & Vision Assistant (Jarvis)**. Предназначен для ИИ-агентов и инженеров-разработчиков для быстрого и глубокого погружения в архитектуру, межпроцессное взаимодействие, подсистемы, форматы данных и правила расширения кодовой базы.

# Архитектурная документация: Antigravity Voice & Vision Assistant

---

## 1. Обзор системы и дизайн-концепция

**Antigravity Voice & Vision Assistant** — это локальный ассистент операционной системы Windows 11, объединяющий:
1. **Голосовой контур:** Модель распознавания речи **Faster-Whisper Turbo** на базе аппаратного ускорения **NVIDIA CUDA (float16)** с интеграцией системного приглушения звука (Audio Ducking) через Windows Core Audio API.
2. **Аппаратный триггер:** Глубокая интеграция с физической клавишей **Copilot** на клавиатурах современных ноутбуков (`Shift + Win + F23`) с разделением на Tap-to-Talk (клик) и Spotlight Bar (удержание).
3. **Мгновенный Fast-Path (0 мс, 0 МБ VRAM):** Прямое управление Win32 (звук, окна, медиа, ссылки, приложения, YouTube) через регулярные выражения и системные вызовы Windows API без задействования нейросетей.
4. **Автономный Vision Computer-Use Agent:** Изолированный фоновый процесс с мультимодальной моделью зрения **`xlangai/Jedi-3B-1080p`** (или fallback `Qwen/Qwen2.5-VL-3B-Instruct`) в 4-битном квантовании BitsAndBytes NF4, способный захватывать экран за ~4 мс, анализировать интерфейс на русском языке и совершать клики, ввод текста и прокрутку.
5. **Двухпроцессная изоляция VRAM:** Жесткое разделение памяти между главным GUI-процессом и фоновым воркером зрения исключает взаимную блокировку и решает конфликт DLL-библиотек CTranslate2 и PyTorch (`cudnn_cnn64_9.dll`).

---

## 2. Структура проекта и распределение ответственности

```text
localAgent/
├── main.py                        # Точка входа: сборка GUI, инициализация потоков и сигналов
├── config/
│   ├── settings.json              # Пользовательские настройки (микрофон, триггеры, пороги)
│   └── commands.json              # Реестр алиасов приложений, сайтов и внутренних команд
├── core/
│   ├── audio_listener.py          # Потоковый захват звука, VAD, RMS VU-метр, верификация Wake Word
│   ├── audio_ducking.py           # Audio Ducking через PyCAW с потокобезопасным CoInitialize()
│   ├── speech_to_text.py          # Faster-Whisper Turbo на CUDA (CTranslate2, кэш HF, без torch)
│   ├── text_to_speech.py          # Синтез речи через Win32 SAPI5 (0 МБ VRAM, русские голоса)
│   ├── keyboard_hook.py           # Низкоуровневый хук WH_KEYBOARD_LL (Copilot, Alt+Space, Ctrl+Space)
│   ├── decision_engine.py         # Двухуровневый маршрутизатор (Fast-Path vs Vision-Path)
│   ├── executor.py                # Исполнитель Win32, пре-навигация, защита clipboard, безопасный CLI
│   ├── app_controller.py          # Низкоуровневое управление окнами (SetForeground, SendInput)
│   ├── screen_tools.py            # Win32 GDI BitBlt захват, мультимониторность, DPI, координаты [x, y]
│   └── vision_agent.py            # Computer-Use воркер, VLM Jedi-3B NF4, ActionParser, Fail-Safe
├── gui/
│   ├── main_window.py             # Fluent 2 Dark окно панели, SAPI5 селектор, симулятор команд, диагностика
│   ├── floating_pill.py           # Плавающий оверлей FloatingPill (VU-метр), маркер клика ClickIndicator (High DPI)
│   ├── spotlight_bar.py           # Строка поиска Spotlight (Alt+Space / Hold Copilot, Live Auto-Suggestions)
│   ├── tray_manager.py            # Динамический системный трей (4 состояния, tray_state_signal, сброс VRAM)
│   ├── close_dialog.py            # Модальное окно подтверждения сворачивания/выхода
│   └── styles.py                  # Fluent 2 Dark QSS стили и цветовая палитра
├── sounds/                        # Системные WAV-сигналы (активация, успех, ошибка)
├── tests/
│   ├── test_components.py         # Модульные тесты роутера, громкости, экзекутора, трея (63 теста)
│   ├── test_screen_tools.py       # Тесты координатной сетки, мультимониторности и захвата GDI (7 тестов)
│   ├── test_vision_agent.py       # Тесты ActionParser, Fail-Safe, менеджера процессов и изоляции (12 тестов)
│   ├── test_problems_fixes.py     # Модульные тесты исправлений дефектов BUG-001..BUG-009 (6 тестов)
│   ├── test_cuda_stt.py           # Проверка Faster-Whisper Turbo на CUDA
│   └── full_verification.py       # Комплексный аудит всех 10 подсистем ассистента
├── create_shortcut.py             # Скрипт генерации тихого ярлыка на рабочем столе (pythonw.exe)
├── download_vision_model.py       # Фоновая загрузка весов Jedi-3B в кэш Hugging Face Hub
├── pyproject.toml                 # Конфигурация зависимостей pip / uv
├── docs/
│   └── architecture/              # Модульная архитектура (Tier 3: database, api, frontend, vision)
├── .env.example                   # Шаблон переменных окружения (Hugging Face, CUDA)
├── repomix-output.xml             # AST-карта кодовой базы (Tier 2 архитектуры контекста)
├── AGENTS.md                      # Базовый паспорт проекта и регламент ИИ-агентов (Tier 1)
└── documentation.md               # Данный файл полной технической документации
```

---

## 3. Процессная модель и IPC-протокол

### Архитектура двух процессов
```
+-----------------------------------------------------------------------------------+
| ГЛАВНЫЙ ПРОЦЕСС (main.py — PyQt6 GUI)                                             |
|                                                                                   |
|  [Copilot Key Hook] -----> [AudioListener] -----> [SpeechToText (CTranslate2)]    |
|                                                          |                        |
|                                                          v                        |
|  [FloatingPill] <--------- [CommandExecutor] <--- [DecisionEngine]                |
|  [SpotlightBar]                   | (если Vision-Path)                            |
|  [TrayManager]                    v                                               |
|                             +------------+                                        |
|                             | task_queue |                                        |
+-----------------------------+-----+------+----------------------------------------+
                                    | (IPC Multiprocessing)
                                    v
+-----------------------------+-----+------+----------------------------------------+
| ИЗОЛИРОВАННЫЙ РАБОЧИЙ ПРОЦЕСС (core/vision_agent.py — PyTorch / BitsAndBytes)     |
|                                                                                   |
|                      +------------------------+                                   |
|                      |  _vision_worker_loop   |                                   |
|                      +-----------+------------+                                   |
|                                  |                                                |
|       +--------------------------+--------------------------+                     |
|       |                          |                          |                     |
|       v                          v                          v                     |
| [ScreenController]      [Jedi-3B-1080p NF4]          [FailSafeMonitor]            |
| (GDI BitBlt ~4 ms)    (HuggingFace Transformers)   (ESC / Мышь > 40px)            |
|                                  |                          |                     |
|                                  +------------+-------------+                     |
|                                               |                                   |
|                                               v                                   |
|                                   [Win32 API SendInput]                           |
|                                   (Клики, Ввод, Скролл)                           |
|                                               |                                   |
|                             +-----------------+                                   |
|                             v                                                     |
|                      +--------------+                                             |
|                      | status_queue |                                             |
+----------------------+------+-------+---------------------------------------------+
                              |
                              +---> Возврат статуса шагов в FloatingPill / MainWindow
```

### Формат сообщений IPC

#### Входные задачи (`task_queue`):
```json
{
  "type": "execute",
  "prompt": "На ютубе найди Мармука",
  "max_steps": 8
}
```
Команда завершения воркера:
```json
{
  "type": "stop"
}
```

#### Исходящие статусы (`status_queue`):
* `{"type": "ready", "message": "Vision-модель xlangai/Jedi-3B-1080p готова к работе"}`
* `{"type": "task_started", "prompt": "..."}`
* `{"type": "step_status", "step": 1, "status": "Захват экрана..."}`
* `{"type": "action_decided", "step": 1, "thought": "...", "action": "click", "coordinate": [x, y], "message": ""}`
* `{"type": "click_performed", "x": 960, "y": 540, "button": "click"}`
* `{"type": "confirmation_requested", "message": "Подтвердите опасное действие"}`
* `{"type": "interrupted", "reason": "Прервано пользователем (клавиша ESC)"}`
* `{"type": "task_completed", "success": true, "message": "Задача успешно выполнена"}`

---

## 4. Детальное описание модулей ядра (`core/`)

### 4.1. `core/audio_listener.py`
* **Класс `AudioListener`**:
  * Непрерывный фоновый захват 16-битного моно-аудио с частотой 16 000 Гц через `sounddevice.InputStream` в архитектуре единого постоянного потока (Single Persistent Stream) без постоянных переоткрытий звуковой карты.
  * **Кольцевой буфер:** Хранит последние ~1.5–2.0 секунды аудио для предотвращения обрезания начала фразы.
  * **RMS-фильтр тишины (VAD):** Вычисляет среднеквадратичную амплитуду `rms = np.sqrt(np.mean(chunk**2))`. Если `rms > speech_energy_threshold`, фиксируется начало речевой активности.
  * **Детекция Wake Word:** Выполняется в фоновом потоке с защитой через `self._state_lock`, исключая data race при частых вызовах. Аудиобуфер транскрибируется моделью Whisper Turbo: при обнаружении ключевого слова (по умолчанию «джарвис») вызывается колбэк `on_wake_detected()`.
  * **Живой VU-метр:** Колбэк `on_vu_meter(level)` передает нормализованный уровень звука (0.0–1.0) с дросселированием до 12.5 Гц для плавной анимации карточки микрофона в GUI и пульсации FloatingPill.

### 4.2. `core/audio_ducking.py`
* **Класс `AudioDucker`**:
  * Управляет общей громкостью Windows через Windows Core Audio API (`pycaw`, `IAudioEndpointVolume`).
  * **Потокобезопасность и инициализация COM:** Перед вызовом интерфейсов вызывается `comtypes.CoInitialize()`, что гарантирует стабильную работу при вызовах из любых фоновых потоков и предотвращает исключения `COMError`.
  * Метод `duck(duck_factor=0.20)`: Запоминает исходный уровень громкости в `self._previous_volume` и снижает мастер-громкость до `target = max(0.05, current * duck_factor)`.
  * Метод `unduck()`: Восстанавливает прежний уровень громкости без щелчков.
  * Синхронизация: Все критические секции защищены объектом `self._lock = threading.Lock()`.

### 4.3. `core/speech_to_text.py`
* **Класс `SpeechToText`**:
  * Обертка над библиотекой `faster_whisper.WhisperModel` с инференсом через оптимизированный C++ движок CTranslate2.
  * **Строгая изоляция PyTorch:** В модуле полностью отсутствует импорт `torch` — это исключает конфликт CUDA DLL в основном процессе GUI и снижает оверхед памяти.
  * Модель по умолчанию: `turbo` с аппаратным ускорением `device="cuda"`, `compute_type="float16"` (с автоматическим фолбеком на CPU int8).
  * Метод `transcribe(audio_data, language="ru")`: Принимает массив `np.float32`, выполняет инференс, фильтрует галлюцинации тишины и возвращает распознанный текст.
  * Кэширование весов: Параметр `download_root=~/.cache/huggingface/hub` сохраняет веса модели в глобальном кэше Hugging Face Hub.
  * Метод `unload_model()`: Выгружает модель из VRAM (`del self._model`) и инициирует сборку мусора для мгновенного освобождения ~1.5 ГБ VRAM перед запуском 3D-игр.

### 4.4. `core/keyboard_hook.py`
* **Класс `CopilotKeyHook`**:
  * Перехватывает аппаратную клавишу Copilot через низкоуровневый хук Windows `WH_KEYBOARD_LL` (библиотека `pynput`).
  * **Коды клавиш и шорткаты:**
    * `VK_F23 = 0x86` (134 dec) — стандартный сканкод Windows SDK.
    * `VK_F23_ALT = 0x8E` (142 dec) — альтернативный OEM-код контроллеров клавиатур ноутбуков.
    * `Alt + Space` — глобальный вызов строки поиска Spotlight Bar.
    * `Ctrl + Space` — быстрый вызов микрофона Tap-to-Talk для клавиатур без физической кнопки Copilot.
    * Резервные шорткаты: `Ctrl + Shift + J` и `Win + Shift + C`.
  * **Маскирование меню Пуск (`#MenuMaskKey`):**
    Клавиша Copilot на аппаратном уровне генерирует аккорд `Shift + Win + F23`. Метод `_mask_win_key()` отправляет виртуальный сканкод `0xFF` (`VK_MASK`), сигнализируя Windows о системном модификаторе и полностью подавляя всплывание меню «Пуск» и поиска.
  * **Разделение клика и удержания:**
    * Нажатие длительностью `< 0.4 сек` -> вызов `on_click()` (Tap-to-Talk).
    * Нажатие длительностью `>= 0.4 сек` -> вызов `on_hold()` (Spotlight Bar).

### 4.5. `core/decision_engine.py`
* **Класс `DecisionEngine`**:
  * **Fast-Path (0 мс):** Анализирует нормализованный текст регулярными выражениями:
    * Системная громкость: `громкость на 40%`, `потише`, `без звука`.
    * Медиа: `пауза`, `следующий трек`, `продолжи`.
    * Окна: `сверни все`, `закрой окно {приложение}`, `разверни на весь экран`.
    * Браузерные вкладки: `новая вкладка`, `закрой вкладку`.
    * Прямой YouTube: `включи видео {запрос}`, `поставь трек {запрос}` -> маршрутизация в `open_url` с `direct_play=True`.
    * Быстрые разделы: `сообщения вк`, `подписки на ютубе`, `почта`.
    * Питание: `заблокируй экран`, `выключи пк` (требует подтверждения).
  * **Vision-Path:** Если совпадений в Fast-Path нет, команда помечается действием `vision_agent` и передается для зрительного анализа рабочего стола.

### 4.6. `core/screen_tools.py`
* **Класс `ScreenController`**:
  * **DPI-Awareness:** При инициализации вызывает `SetProcessDpiAwareness(2)` (Per-Monitor DPI Aware v2) для получения точных физических пикселей в Windows 11.
  * **Мультимониторность (`MonitorFromWindow` / `MonitorFromPoint`):**
    Автоматически определяет активный экран под курсором или окном приложения. Возвращает физический прямоугольник `(left, top, width, height)`.
  * **Сверхбыстрый захват (GDI BitBlt ~4 мс):**
    Создает совместимый контекст устройства (`CreateCompatibleDC`), выделяет растровый дескриптор `CreateCompatibleBitmap`, копирует пиксели через `BitBlt` с флагом `SRCCOPY` и извлекает байты через `GetDIBits` напрямую в память PIL Image. В случае сбоя переключается на fallback (`mss` -> `PIL.ImageGrab`) с информативным логированием.
  * **Система координат:**
    Использует претрейн-стандарт Qwen-VL `[x, y]`, где `0` — левый/верхний край, `1000` — правый/нижний край.
    Денормализация:
    $$\text{ScreenX} = \text{Left} + \left(\frac{\text{NormX}}{1000}\right) \times \text{Width}$$
    $$\text{ScreenY} = \text{Top} + \left(\frac{\text{NormY}}{1000}\right) \times \text{Height}$$
  * **Ввод текста:** Для фраз `<= 20 символов` используется `SendInput` с флагом `KEYEVENTF_UNICODE`. Для длинных текстов — моментальная вставка `Ctrl+V` через буфер обмена Windows (`win32clipboard` и `win32con.CF_UNICODETEXT`) с предварительным сохранением и последующим восстановлением данных пользователя.

### 4.7. `core/vision_agent.py`
* **Классы:**
  * **`ActionParser`**: Извлекает структурированный JSON из ответа нейросети (поддерживает Markdown code blocks и сырой текст). Парсит типы действий: `click`, `double_click`, `right_click`, `type`, `press`, `hotkey`, `scroll`, `finish`, `ask_confirmation`.
  * **`FailSafeMonitor`**: Проверяет нажатие клавиши `ESC` (0x1B) через `GetAsyncKeyState` и смещение мыши более чем на 40 пикселей от последней известной точки, мгновенно прерывая выполнение.
  * **`VisionAgentProcessManager`**: Отвечает за запуск, остановку, передачу очередей и мониторинг жизненного цикла процесса `multiprocessing.Process`.
  * **`_vision_worker_loop`**: Рабочий цикл фонового процесса. Держит модель в памяти в режиме Always-Warm, циклически захватывает экран, сравнивает кадры для детекции помех (`avg_diff < 1.5`), генерирует токены и исполняет действия. Блок `try...finally` гарантирует удаление модели и очистку VRAM при остановке.

### 4.8. `core/executor.py`
* **Класс `CommandExecutor`**:
  * Диспетчер команд ассистента. Получает распарсенный словарь от `DecisionEngine` и вызывает соответствующие подсистемы:
    * `0. general_answer` — текстовый ответ ассистента.
    * `1. antigravity_gui` — интеграция с окном Antigravity IDE (создание нового чата, безопасная вставка промпта в буфер обмена с сохранением и асинхронным восстановлением данных пользователя).
    * `2. antigravity_cli` — запуск задачи в Windows Terminal / PowerShell через Base64 `-EncodedCommand` с параметром `shell=False`, исключающий атаки типа Command Injection.
    * `3. set_volume` — вызов `AudioDucker`.
    * `4. media_control` — отправка виртуальных клавиш `VK_MEDIA_*`.
    * `5. launch_app` — запуск exe или перевод фокуса на существующее окно с валидацией веб-целей.
    * `6. open_url / direct_play` — открытие веб-ссылок с валидацией схемы (HTTP/HTTPS); при наличии `direct_play` метод `_resolve_youtube_video` извлекает ID ролика с лимитом чтения 256 КБ для защиты от DoS.
    * `7. window_control` — закрытие, сворачивание, разворачивание окон.
    * `8. app_type` — печать текста в активное окно.
    * `9. app_hotkey` — горячие клавиши вкладок (`Ctrl+T`, `Ctrl+W`).
    * `10. system_action` — блокировка, выключение или перезагрузка с обязательным модальным подтверждением пользователя (`CONFIRM_REQUIRED`).
    * `11. vision_agent` — запуск Vision-агента с предварительной навигацией на маркетплейсы (`avito.ru`, `ozon.ru`, `wildberries.ru`, `market.yandex.ru`) и автоматической фокусировкой браузера Google Chrome.

---

## 5. Графический интерфейс (`gui/`)

1. **`gui/main_window.py` (`MainWindow`):**
   * Панель управления в тёмном стиле Fluent Design.
   * Интерактивные карточки со статусом устройств (Микрофон, Клавиша Copilot, Модель Vision, STT, VRAM, Antigravity).
   * Поле динамической настройки слова-триггера («Джарвис») с мгновенным сохранением в `settings.json`.
   * Кнопка комплексной диагностики («Проверить все системы»), запускающая сквозной аудит всех компонентов без закрытия приложения.
   * Выпадающий селектор голосов Windows SAPI5 с кнопкой «🔊 Тест» для проверки синтеза речи.
   * Встроенный симулятор команд прямо в GUI для быстрого тестирования без использования микрофона.
   * Консольный лог действий в реальном времени.

2. **`gui/floating_pill.py` (`FloatingPill` и `ClickIndicatorOverlay`):**
   * **`FloatingPill`**: Полупрозрачный плавающий виджет без рамок и заголовка (`Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool`), отображающий статус микрофона («Слушаю...», «Выполняю...») и промежуточные шаги агента зрения `[1/8] Анализирую экран...`. Включает динамическую аудио-пульсацию синей точки в такт громкости голоса (RMS VU-метр через `update_vu(level)`).
   * **`ClickIndicatorOverlay`**: Анимированный пульсирующий неоновый круг в точке действия ассистента с делением координат на `devicePixelRatio()` для корректного отображения на экранах с High DPI масштабированием. Сконфигурирован с атрибутом `WA_TransparentForMouseEvents`, что гарантирует прохождение кликов сквозь оверлей.

3. **`gui/spotlight_bar.py` (`SpotlightBar`):**
   * Строка ручного ввода команд по центру экрана (вызывается удержанием Copilot на 0.4 сек или хоткеем `Alt+Space`).
   * Включает Live Auto-Suggestions (динамические автоподсказки на лету из `commands.json`), навигацию стрелками вверх/вниз и мгновенный выбор по `Enter`.

4. **`gui/tray_manager.py` (`TrayManager`):**
   * Иконка в системном трее Windows с поддержкой сигнала `tray_state_signal`.
   * **Динамическая индикация статусов (4 состояния):**
     1. `idle`: статический зелёный маркер (готов к работе);
     2. `listening`: пульсирующий красный/розовый огонёк записи речи;
     3. `working`: пульсирующий фиолетовый/голубой статус анализа экрана Vision-агентом;
     4. `stopped`: серый маркер остановки и выгрузки VRAM в 0 МБ.
   * Контекстное меню с опцией **«Остановить ассистента (Освободить VRAM)»** для моментального освобождения 100% GPU памяти для 3D-игр.

---

## 6. Конфигурация и расширение

### Настройки `config/settings.json`
```json
{
  "wake_word": "джарвис",
  "wake_word_enabled": true,
  "audio_ducking_enabled": true,
  "audio_ducking_factor": 0.20,
  "close_behavior": "minimize_to_tray",
  "vision_auto_focus_browser": true,
  "vision_max_steps": 8,
  "tts_voice": "irina",
  "tts_speed": 1.0,
  "start_minimized": false
}
```

### Добавление новых голосовых команд
1. **Для мгновенных команд Fast-Path:**
   * Откройте [`core/decision_engine.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/decision_engine.py).
   * В метод `_parse_fast_path(query)` добавьте проверку регулярным выражением:
     ```python
     if "мой_паттерн" in q:
         return {"action": "моё_действие", "target": "параметр", "parameters": {}}
     ```
   * В [`core/executor.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/executor.py) добавьте обработчик соответствующего `action`.
2. **Для веб-ссылок и программ:**
   * Добавьте запись в [`config/commands.json`](file:///C:/Users/denis/Documents/antigravity/localAgent/config/commands.json) в секцию `"apps"` или `"urls"`.

---

## 7. Стандарты разработки для ИИ-агентов

1. **Изоляция тяжелых библиотек:** Ни при каких обстоятельствах не импортируйте `torch`, `torchvision`, `transformers` или `bitsandbytes` в главном процессе GUI (`main.py`, `core/executor.py` и т.д.). Все VLM-инференсы должны выполняться исключительно внутри `core/vision_agent.py` в изолированном воркере.
2. **Контроль вложенности и типизация:**
   * Используйте Early Returns (максимальная глубина вложенности блоков — не более 3 уровней).
   * Обязательно указывайте явные type-hints для аргументов и возвращаемых значений функций (`def func(param: str) -> bool:`).
   * Никаких фиктивных заглушек (`TODO`, `pass` в критических путях) — все методы должны содержать законченную продакшн-логику.
3. **Комментарии и ссылки:**
   * Все комментарии к коду, докстринги и технические пометки внутри файлов пишутся на **русском языке**.
   * Имена переменных, классов, методов и констант — строго на **английском языке**.
   * При формировании ответов пользователю оформляйте пути к файлам кликабельными Markdown-ссылками со схемой `file:///` и прямыми слэшами.
4. **Валидация перед коммитом:**
   * Обязателен запуск:
     ```powershell
     .\.venv\Scripts\python.exe -m unittest discover tests
     .\.venv\Scripts\python.exe tests/full_verification.py
     ```
   * Все 88 unit-тестов и 10 этапов сквозного аудита должны возвращать статус **100% OK**.
