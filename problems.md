# Отчёт о проблемах кодовой базы — Antigravity Voice & Vision Assistant

> **Дата аудита:** 2026-09-27  
> **Аудитор:** Независимый анализ (главный агент, без делегирования)  
> **Статус тестов:** 68/68 PASS (тесты проходят, но покрывают только Fast-Path)

---

## 🔴 КРИТИЧЕСКИЕ ОШИБКИ (Runtime crash / Silent wrong behavior)

---

### BUG-01 — Инверсия координат клика (X/Y swap) — `core/vision_agent.py`

**Файл:** [`core/vision_agent.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/vision_agent.py#L25)  
**Строки:** 25, 107–109, 364–365

**Описание:**  
Системный промпт диктует модели возвращать координаты в формате `[y, x]` (строка 25: `"coordinate": [y, x]`).  
Модель Qwen2.5-VL (и её дериватив Jedi-3B) **по умолчанию выдаёт координаты в формате `[x, y]`** (горизонталь первая) согласно официальной документации и тренировочным данным xlangai.  
В итоге все клики систематически попадают в зеркально неверную точку — по диагонали от нужной.

**Код:**
```python
# vision_agent.py, строка 25 (системный промпт)
'"coordinate": [y, x]'  # ← диктуем [y, x]

# строка 364 (воркер)
norm_y, norm_x = action.coordinate  # ← распаковываем как [y, x]
# но реальная модель вернёт [x, y], и тогда x/y будут перепутаны
```

**Исправление:**  
Изменить системный промпт на `"coordinate": [x, y]` и распаковку на `norm_x, norm_y = action.coordinate`.

---

### BUG-02 — Неверная константа `MOUSEEVENTF_RIGHTUP` — `core/screen_tools.py`

**Файл:** [`core/screen_tools.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/screen_tools.py#L27)  
**Строка:** 27

**Описание:**  
```python
MOUSEEVENTF_RIGHTUP = 0x000c  # ← НЕВЕРНО
```
Правильные значения Win32:
- `MOUSEEVENTF_RIGHTDOWN = 0x0008`
- `MOUSEEVENTF_RIGHTUP   = 0x0010`

`0x000c` — это побитовое ИЛИ `DOWN|некий_флаг`, а не `RIGHTUP`. При правом клике мышь не отпускается — кнопка остаётся зажатой до следующего действия.

**Исправление:**
```python
MOUSEEVENTF_RIGHTUP = 0x0010
```

---

### BUG-03 — `win32clipboard.CF_UNICODETEXT` не существует — `core/app_controller.py`

**Файл:** [`core/app_controller.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/app_controller.py#L325)  
**Строка:** 325

**Описание:**  
```python
win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)  # ← AttributeError
```
Модуль `win32clipboard` не имеет атрибута `CF_UNICODETEXT`. Правильный источник — `win32con.CF_UNICODETEXT`. Метод `type_into_app` упадёт с `AttributeError` при каждом вызове.

Для сравнения: в `core/screen_tools.py` строка 425 используется `win32con.CF_UNICODETEXT` — правильно.

**Исправление:**
```python
import win32con
# ...
win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
```

---

### BUG-04 — VRAM не освобождается при краше воркера — `core/vision_agent.py`

**Файл:** [`core/vision_agent.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/vision_agent.py#L401)  
**Строки:** 401–407

**Описание:**  
```python
# После основного цикла while:
del model
del processor
torch.cuda.empty_cache()
```
Код очистки расположен ПОСЛЕ блока `while True`, но вне блока `try/finally`. При исключении внутри основного цикла (OOM, CUDA error, KeyboardInterrupt), переменные `model` и `processor` не будут удалены — VRAM утечёт.

**Исправление:** обернуть весь блок загрузки и цикла в `try/finally`:
```python
try:
    model = ...
    while True:
        ...
finally:
    del model
    del processor
    torch.cuda.empty_cache()
```

---

### BUG-05 — Хардкод `.to("cuda")` без проверки доступности GPU — `core/vision_agent.py`

**Файл:** [`core/vision_agent.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/vision_agent.py#L317)  
**Строка:** ~317

**Описание:**  
```python
inputs = processor(...).to("cuda")  # ← RuntimeError если CUDA недоступна
```
Перемещение тензоров на CUDA происходит без проверки `torch.cuda.is_available()`. Если на другом ПК CUDA недоступна — `RuntimeError` при каждом запросе к Vision-агенту.

---

## 🟡 СРЕДНИЕ ОШИБКИ (Некорректное поведение, несоответствие документации)

---

### BUG-06 — Порог детекции изменений экрана неверно документирован — `core/vision_agent.py`

**Файл:** [`core/vision_agent.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/vision_agent.py#L274)  
**Строка:** ~274

**Описание:**  
```python
avg_diff = np.mean(np.abs(prev_thumb.astype(float) - curr_thumb.astype(float)))
if avg_diff < 1.5:
    # Экран изменился менее чем на 1.5%
```
`avg_diff` — это средняя абсолютная разница пикселей в диапазоне **0–255**, а не процент. Порог `1.5` соответствует примерно **0.6% от максимально возможного** изменения пикселей, а не 1.5%.  
Комментарий в коде и в GEMINI.md («< 1.5% порог изменения») вводят в заблуждение.

---

### BUG-07 — `is_llm_available()` всегда возвращает `True` — `core/decision_engine.py`

**Файл:** [`core/decision_engine.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/decision_engine.py#L73)  
**Строка:** 73

**Описание:**  
```python
def is_llm_available(self) -> bool:
    return True  # ← всегда True
```
Проверка не проверяет ни наличие файлов модели на диске, ни реальный статус Worker-процесса. При первом запуске без загруженной модели Jedi-3B GUI покажет «Vision-агент: готов», хотя Worker упадёт при попытке загрузить модель.

---

### BUG-08 — Непоследовательная нумерация VK_F23 и несоответствие GEMINI.md — `core/keyboard_hook.py`

**Файл:** [`core/keyboard_hook.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/keyboard_hook.py#L13)  
**Строки:** 13–14

**Описание:**  
```python
VK_F23     = 0x86  # 134 decimal — основной
VK_F23_ALT = 0x8E  # 142 decimal — альтернативный
```
В `GEMINI.md` написано: «аппаратная клавиша Copilot (`Shift + Win + F23`)» и `VK_F23 = 0x8E`.  
Однако в коде основной — `0x86` (VK_F22 по официальной таблице Windows!), а `0x8E` помечен как «ALT». Это означает, что описание в документации не совпадает с реализацией. При работе на ноутбуке с другим кодом клавиши Copilot перехват не сработает.

---

### BUG-09 — `_is_checking_wake` изменяется из разных потоков без блокировки — `core/audio_listener.py`

**Файл:** [`core/audio_listener.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/audio_listener.py#L197)  
**Строки:** 197, 201, 245

**Описание:**  
```python
if self._is_checking_wake:   # ← читается из аудио-потока
    return

def worker():
    self._is_checking_wake = True  # ← пишется из daemon thread
    ...
    finally:
        self._is_checking_wake = False
```
Флаг `_is_checking_wake` читается в аудио-потоке и пишется в daemon-потоке `worker()` без lock. CPython GIL делает это фактически безопасным, но технически это data race. В edge-case может запуститься два параллельных `_async_check_wake_word`.

---

### BUG-10 — TOCTOU на `_is_processing_voice` — `main.py`

**Файл:** [`main.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/main.py)  
**Строки:** ~651, ~655, ~735

**Описание:**  
```python
if self._is_processing_voice:  # ← читается
    return
self._is_processing_voice = True  # ← пишется (не атомарно)
```
Простой `bool` без `threading.Lock`. Два быстрых нажатия Copilot могут оба пройти проверку до того, как первый поток выставит флаг. Следствие: два параллельных потока STT и возможный конфликт.

---

### BUG-11 — Мёртвый код `direct_play` — `core/executor.py`

**Файл:** [`core/executor.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/executor.py#L145)  
**Строки:** ~145–150

**Описание:**  
В `execute()` для `action == "open_url"` есть ветка:
```python
if params.get("direct_play"):
    video_url = self._resolve_youtube_video(...)
```
Однако `DecisionEngine._parse_fast_path()` **никогда** не выставляет `direct_play=True` в возвращаемом словаре — сложные YouTube-запросы направляются в `vision_agent`. Код `_resolve_youtube_video()` (150+ строк) реально никогда не вызывается из основного потока команд. Тесты, проверяющие этот путь (`test_executor_open_url_direct_play`), используют мок и не тестируют реальный маршрутизатор.

---

### BUG-12 — Пропущен обработчик `action == 7` с пробелом в нумерации — `core/executor.py`

**Файл:** [`core/executor.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/executor.py)  
**Строки:** комментарии 0–6, затем сразу 8

**Описание:**  
В `execute()` логика ветвления пронумерована комментариями: `# 0.`, `# 1.`, ..., `# 6.`, затем прыжок на `# 8.`. Номер 7 пропущен. Свидетельствует об удалённом блоке, что создаёт путаницу при поддержке кода.

---

## 🟢 НЕЗНАЧИТЕЛЬНЫЕ / ПРЕДУПРЕЖДЕНИЯ

---

### BUG-13 — Отсутствуют зависимости в `pyproject.toml`

**Файл:** [`pyproject.toml`](file:///C:/Users/denis/Documents/antigravity/localAgent/pyproject.toml)

**Описание:**  
Следующие пакеты **используются в коде, но отсутствуют в `pyproject.toml`**:

| Пакет | Где используется |
|---|---|
| `Pillow` / `PIL` | `vision_agent.py`, `screen_tools.py` |
| `mss` | `screen_tools.py` — fallback-захват экрана |
| `torch` / `torchvision` | `vision_agent.py` — основная VLM |
| `transformers` | `vision_agent.py` — загрузка Jedi-3B / Qwen |
| `bitsandbytes` | `vision_agent.py` — 4-bit NF4 квантование |
| `huggingface_hub` | `decision_engine.py` — `download_llm_model()` |
| `scipy` | `full_verification.py` — раздел 1 проверки |

При чистой установке через `uv sync` зависимости не установятся, приложение упадёт при импорте.

---

### BUG-14 — `mss` не установлен по умолчанию, fallback-цепочка нарушена — `core/screen_tools.py`

**Файл:** [`core/screen_tools.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/screen_tools.py#L279)  
**Строка:** ~279

**Описание:**  
Метод `_fallback_capture()` содержит `import mss` внутри функции. Если `mss` не установлен, `ImportError` перехватывается тихо, и происходит переход к следующему fallback (PIL ImageGrab). Это работает, но:
1. Второй fallback `mss` в документации описан как «надёжный» — он не гарантированно доступен.
2. Ошибка нигде не логируется — диагностика невозможна.

---

### BUG-15 — `settings.json`: `tts_speed: 1.0` игнорируется, `tts_voice` не применяется — `core/text_to_speech.py`

**Файл:** [`core/text_to_speech.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/text_to_speech.py)  
**Файл:** [`config/settings.json`](file:///C:/Users/denis/Documents/antigravity/localAgent/config/settings.json)

**Описание:**  
В `settings.json` есть `"tts_speed": 1.0` и `"tts_voice": "ru_RU-irina-medium"`.  
В `TextToSpeech.__init__` параметр `speed` — это целое число `SAPI Rate` от -10 до 10, а не множитель скорости `1.0`. Значение `1.0` будет усечено до `int(1)`, что даёт скорость `1` (немного быстрее нормы) вместо нормальной скорости `0`.  
Голос `"ru_RU-irina-medium"` — это идентификатор piper/espeak, а не SAPI. В `TextToSpeech.speak()` поиск осуществляется по `"irina"` в описании SAPI-голоса, что может совпасть, но не гарантировано.

---

### BUG-16 — `create_shortcut.py`: ярлык не указывает на `pythonw.exe` — `create_shortcut.py`

**Файл:** [`create_shortcut.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/create_shortcut.py)  
**Строки:** 15, 32

**Описание:**  
```python
pythonw_path = os.path.join(project_dir, ".venv", "Scripts", "pythonw.exe")
# ...
shortcut.Arguments = args  # ← только аргументы
# shortcut.TargetPath НЕ ЗАДАН
```
`shortcut.TargetPath` нигде не назначается! Ярлык создаётся без `TargetPath`, что означает что он откроет файл `main.py` системным обработчиком (обычно Python IDE или просто откроет .py в редакторе), а не запустит через `pythonw.exe`. Ярлык нефункционален.

**Исправление:**
```python
shortcut.TargetPath = pythonw_path
shortcut.Arguments = args
```

---

### BUG-17 — `full_verification.py`: проверяет `scipy`, но код не использует `scipy`

**Файл:** [`tests/full_verification.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/tests/full_verification.py#L43)  
**Строка:** 43

**Описание:**  
```python
("scipy", "Аудио DSP")  # ← в коде не используется
```
`scipy` упоминается в верификации как зависимость для «Аудио DSP», но ни в одном файле проекта `scipy` не импортируется. Это либо остаток от ранней версии, либо планируемая зависимость.

---

### BUG-18 — Тест `test_audio_ducker_init` не проверяет реальную работу дакера

**Файл:** [`tests/test_components.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/tests/test_components.py#L238)  
**Строка:** 238

**Описание:**  
```python
def test_audio_ducker_init(self):
    ducker = AudioDucker()
    self.assertFalse(ducker._is_ducked)
```
Тест только проверяет что `_is_ducked == False` после создания объекта. Реальные методы `duck()` / `unduck()` не тестируются — их корректность не верифицируется.

---

### BUG-19 — `FloatingPill.show_executing()` не вызывает `show()` явно

**Файл:** [`gui/floating_pill.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/gui/floating_pill.py#L105)  
**Строки:** 105–111

**Описание:**  
```python
def show_executing(self, action_name: str = "Выполняю..."):
    self.dot.setStyleSheet("color: #10B981;")
    self.label.setText(action_name)
    self.adjustSize()
    self._reposition()
    self._hide_timer.start(2000)  # ← запускает таймер скрытия, но не show()!
```
В отличие от `show_listening()`, `show_step()`, `show_error()` — метод `show_executing()` не вызывает `self.show()`. Если пилюля была скрыта, она так и останется скрытой при вызове `show_executing()`.

---

### BUG-20 — Несоответствие `openwakeword` в документации и коде

**GEMINI.md:** `"Wake Word: openwakeword (активация по слову-триггеру «Джарвис»)"`  
**Реализация:** `audio_listener.py` использует **Faster-Whisper STT** для детектирования wake word (транскрибирует аудиобуфер и ищет «джарвис» в тексте).

`openwakeword` **нигде не используется** и **не установлен** в `pyproject.toml`. Документация описывает несуществующую реализацию.

---

## Сводная таблица исправлений

| ID | Файл | Серьёзность | Тип | Краткое описание | Статус |
|---|---|---|---|---|---|
| BUG-01 | `core/vision_agent.py` | 🔴 Критический | Логическая ошибка | Инверсия X/Y координат клика | ✅ Исправлен ([x, y], denormalize_coordinate) |
| BUG-02 | `core/screen_tools.py` | 🔴 Критический | Неверная константа Win32 | `MOUSEEVENTF_RIGHTUP = 0x000c` вместо `0x0010` | ✅ Исправлен (0x0010) |
| BUG-03 | `core/app_controller.py` | 🔴 Критический | AttributeError в рантайме | `win32clipboard.CF_UNICODETEXT` не существует | ✅ Исправлен (`win32con.CF_UNICODETEXT`) |
| BUG-04 | `core/vision_agent.py` | 🔴 Критический | VRAM утечка | Нет `try/finally` для очистки VRAM при краше | ✅ Исправлен (`try/finally` очистка) |
| BUG-05 | `core/vision_agent.py` | 🔴 Критический | Портируемость | `.to("cuda")` без проверки доступности GPU | ✅ Исправлен (динамический `device`) |
| BUG-06 | `core/vision_agent.py` | 🟡 Средний | Неверная документация | Порог 1.5 — не процент, а абс. пиксели 0–255 | ✅ Исправлен (документировано: 1.5 из 255) |
| BUG-07 | `core/decision_engine.py` | 🟡 Средний | Заглушка | `is_llm_available()` всегда `True` | ✅ Исправлен (проверка кэша HuggingFace) |
| BUG-08 | `core/keyboard_hook.py` | 🟡 Средний | Несоответствие документации | VK_F23 в коде (0x86) ≠ GEMINI.md (0x8E) | ✅ Исправлен (0x86 SDK / 0x8E OEM) |
| BUG-09 | `core/audio_listener.py` | 🟡 Средний | Data race | `_is_checking_wake` без lock | ✅ Исправлен (`self._state_lock`) |
| BUG-10 | `main.py` | 🟡 Средний | TOCTOU | `_is_processing_voice` без lock | ✅ Исправлен (`self._voice_lock`) |
| BUG-11 | `core/executor.py` | 🟡 Средний | Мёртвый код | `direct_play` никогда не активируется | ✅ Исправлен (паттерны прямого воспроизведения) |
| BUG-12 | `core/executor.py` | 🟢 Незначительный | Поддерживаемость | Пробел в нумерации handlers (пропущен #7) | ✅ Исправлен (нумерация выровнена) |
| BUG-13 | `pyproject.toml` | 🟡 Средний | Отсутствующие зависимости | 6+ пакетов не объявлены | ✅ Исправлен (добавлены pillow, mss, vision opt) |
| BUG-14 | `core/screen_tools.py` | 🟢 Незначительный | Silent fallback | `mss` без логирования ошибки | ✅ Исправлен (добавлен `logger.warning`) |
| BUG-15 | `core/text_to_speech.py` | 🟢 Незначительный | Несовместимость типов | `tts_speed: 1.0` ≠ SAPI Rate int; неверный формат voice | ✅ Исправлен (конверсия float -> SAPI Rate [-10, 10]) |
| BUG-16 | `create_shortcut.py` | 🟡 Средний | Функциональная ошибка | `shortcut.TargetPath` не задан — ярлык нерабочий | ✅ Исправлен (`shortcut.TargetPath = pythonw_path`) |
| BUG-17 | `tests/full_verification.py` | 🟢 Незначительный | Ложная зависимость | `scipy` в проверке, но не используется в коде | ✅ Исправлен (`scipy` удален из проверки) |
| BUG-18 | `tests/test_components.py` | 🟢 Незначительный | Слабое покрытие | `AudioDucker.duck/unduck` не тестируется | ✅ Исправлен (добавлен unit-тест) |
| BUG-19 | `gui/floating_pill.py` | 🟡 Средний | UI bug | `show_executing()` не вызывает `show()` | ✅ Исправлен (`self.show()` и `self.raise_()`) |
| BUG-20 | `GEMINI.md` | 🟡 Средний | Документация ≠ код | `openwakeword` заявлен, но не реализован | ✅ Исправлен (документирован RMS+Whisper) |
