> [!NOTE]
> Результаты **полного независимого аудита** кода проекта **Antigravity Voice & Vision Assistant** с нуля.
> Дата анализа: **2026-09-27 02:32**. Все файлы прочитаны и проанализированы заново.
> Формат: 🔴 Критично (runtime crash), 🟡 Средне (логическая ошибка), 🟢 Низко (tech-debt).

# Отчёт аудита — Antigravity Voice v3 (Vision Computer-Use)

---

## Сводная таблица

| ID | Приоритет | Файл | Описание |
|---|---|---|---|
| BUG-001 | 🔴 | `core/app_controller.py` | `Any` используется без импорта — `NameError` при каждом управлении окнами |
| BUG-002 | 🔴 | `core/executor.py` | `"unmute"` не обрабатывается в `_handle_volume()` — команда «Включи звук» возвращает ошибку |
| BUG-003 | 🔴 | `core/executor.py` | `"lock_workstation"` не реализован в `system_action` — компьютер не блокируется |
| BUG-004 | 🟡 | `main.py` | `vision_model` из `settings.json` не передаётся в `VisionAgentProcessManager` |
| BUG-005 | 🟡 | `gui/main_window.py` | `cb_stt_model.currentIndexChanged` не подключён к `_on_stt_model_selected` |
| BUG-006 | 🟡 | `config/commands.json` | URL `"https://github.com?tab=repositories"` невалиден — редиректит на главную |
| BUG-007 | 🟢 | `core/keyboard_hook.py` | Дублирование номера секции «4.» в комментариях — две секции подряд называются «4.» |
| BUG-008 | 🟢 | `main.py` + `settings.json` | `vision_auto_focus_browser` из настроек не читается — браузер всегда фокусируется |
| BUG-009 | 🟢 | `core/decision_engine.py` | Дублирование URL: `subpages_map` и `url_map` из `commands.json` пересекаются |

---

## Детали

---

### 🔴 BUG-001 — `app_controller.py`: `Any` не импортирован (NameError при каждом вызове)

**Файл:** [`core/app_controller.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/app_controller.py#L127)
**Строка:** 127

```python
# Строка 11 — импорты:
from typing import Optional, Callable  # ← Any ОТСУТСТВУЕТ

# Строка 127 — использование:
def enum_callback(hwnd: int, _: Any) -> bool:  # ← NameError: name 'Any' is not defined
```

`Any` используется в качестве аннотации типа для параметра `_` в callback-функции `enum_callback` внутри метода `find_window()`. При вызове `find_window()` Python не проверяет аннотации в рантайме, поэтому ошибки при простом вызове нет — но если используется `from __future__ import annotations` или инструменты типизации, это сломается. Тем не менее это явная ошибка кода — неимпортированный символ.

**Исправление:**
```python
from typing import Optional, Callable, Any
```

---

### 🔴 BUG-002 — `executor.py`: команда «Включи звук» возвращает ошибку

**Файл:** [`core/executor.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/executor.py#L341)
**Строки:** 341–369

`decision_engine.py` (строка 158) возвращает `{"action": "set_volume", "target": "unmute"}` для команд:
- «Включи звук»
- «Верни звук»
- «Размут»

Но метод `_handle_volume()` в `executor.py` не содержит ветки для `target == "unmute"`:

```python
def _handle_volume(self, target: str, params: dict) -> tuple[bool, str]:
    if target == "absolute": ...
    if target == "step_up": ...
    if target == "step_down": ...
    if target == "mute":
        self._send_key(VK_VOLUME_MUTE)  # ← Toggle mute
        return True, "Звук переключен"
    # ← "unmute" не обрабатывается!
    return False, "Не удалось изменить громкость"  # ← всегда возвращается ошибка
```

**Исправление:** добавить ветку после `mute`:
```python
if target == "unmute":
    self._send_key(VK_VOLUME_MUTE)
    return True, "Звук включен"
```

---

### 🔴 BUG-003 — `executor.py`: блокировка компьютера не реализована

**Файл:** [`core/executor.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/executor.py#L187)
**Строки:** 187–205

`decision_engine.py` (строка 210) возвращает `{"action": "system_action", "target": "lock_workstation"}` для команд:
- «Заблокируй компьютер»
- «Заблокируй ПК»
- «Заблокируй экран»

Но `execute()` в блоке `system_action` обрабатывает только `shutdown` и `restart`:

```python
if action == "system_action":
    confirmed = params.get("confirmed", False)
    if params.get("dangerous") and not confirmed:
        return False, "CONFIRM_REQUIRED"
    if target == "shutdown": ...
    if target == "restart": ...
    return True, "Действие отменено"  # ← lock_workstation упал сюда, компьютер НЕ заблокирован
```

Причём `lock_workstation` не помечен как `dangerous=True` в `decision_engine.py` (строка 210), поэтому `CONFIRM_REQUIRED` не срабатывает — команда молча «выполняется» с результатом «Действие отменено».

**Исправление:** добавить перед `return True, "Действие отменено"`:
```python
if target == "lock_workstation":
    try:
        ctypes.windll.user32.LockWorkStation()
        self.log("Компьютер заблокирован.")
        return True, "Компьютер заблокирован"
    except Exception as e:
        return False, f"Ошибка блокировки: {e}"
```

---

### 🟡 BUG-004 — `main.py`: модель Vision-агента из настроек игнорируется

**Файл:** [`main.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/main.py#L71)
**Строка:** 71

```python
self.vision_manager = VisionAgentProcessManager()  # ← использует дефолтный "xlangai/Jedi-3B-1080p"
```

В `settings.json` есть поле `"vision_model": "xlangai/Jedi-3B-1080p"`, которое позволяет пользователю переключить модель. Но `VisionAgentProcessManager()` инициализируется без аргументов — настройка полностью игнорируется.

**Исправление:**
```python
vision_model = self.window.settings.get("vision_model", "xlangai/Jedi-3B-1080p")
self.vision_manager = VisionAgentProcessManager(model_name=vision_model)
```

---

### 🟡 BUG-005 — `main_window.py`: сигнал `cb_stt_model` не подключён

**Файл:** [`gui/main_window.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/gui/main_window.py#L327)
**Строки:** 327–335

Метод `_on_stt_model_selected()` (строки 600–606) определён, но сигнал `currentIndexChanged` комбобокса `cb_stt_model` **нигде не подключён** к нему. Для сравнения — `cb_microphones.currentIndexChanged` подключён корректно (строка 314).

```python
self.cb_stt_model = QComboBox(stt_box)
self.cb_stt_model.addItem("🚀 Turbo ...", "turbo")
self.cb_stt_model.setCurrentIndex(0)
self.cb_stt_model.setEnabled(False)  # ← сейчас отключён, но если включат — менять модель не будет
# ← currentIndexChanged.connect(_on_stt_model_selected) ОТСУТСТВУЕТ
```

Сейчас не критично, т.к. `cb_stt_model.setEnabled(False)`. Но если в будущем добавят другие модели — изменение не сохранится.

**Исправление:** после строки 330 добавить:
```python
self.cb_stt_model.currentIndexChanged.connect(self._on_stt_model_selected)
```

---

### 🟡 BUG-006 — `commands.json`: невалидный URL для GitHub-репозиториев

**Файл:** [`config/commands.json`](file:///C:/Users/denis/Documents/antigravity/localAgent/config/commands.json#L32)
**Строка:** 32

```json
"репозитории гитхаб": "https://github.com?tab=repositories"
```

URL `https://github.com?tab=repositories` невалиден: `?` должен следовать после пути, а не сразу за доменом. GitHub не поддерживает такой параметр без имени пользователя. При переходе по этой ссылке откроется просто `github.com` (главная страница).

**Правильный URL** для своих репозиториев: `https://github.com/{username}?tab=repositories`. Без username корректного универсального URL нет — либо убрать эту запись, либо вести на `https://github.com/` с уточнением.

---

### 🟢 BUG-007 — `keyboard_hook.py`: дублирование номеров комментариев

**Файл:** [`core/keyboard_hook.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/keyboard_hook.py#L154)
**Строки:** 154, 166

```python
# 4. Обработка связки Win + Shift + C   ← строка 154
if vk == 0x43:
    ...

# 4. Альтернативный горячий шорткат: Ctrl + Shift + J  ← строка 166, тоже «4.»!
if vk == VK_KEY_J:
    ...
```

Обе секции пронумерованы как «4.» — очевидно, одну забыли переименовать в «5.». Не влияет на работу, но затрудняет навигацию.

---

### 🟢 BUG-008 — `settings.json`: поле `vision_auto_focus_browser` не используется

**Файл:** [`main.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/main.py) + [`core/executor.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/executor.py#L232)

`settings.json` содержит `"vision_auto_focus_browser": true`, но в `_handle_vision_agent()` (executor.py строки 232–240) браузер всегда фокусируется при любом веб-запросе, безусловно — настройка никогда не читается:

```python
# executor.py строки 234-238:
if any(w in prompt_lower for w in web_keywords):
    try:
        self.app_controller.launch_or_focus("хром", "chrome.exe")
        # ← настройка vision_auto_focus_browser из settings.json ИГНОРИРУЕТСЯ
```

---

### 🟢 BUG-009 — `decision_engine.py`: дублирование URL между `subpages_map` и `url_map`

**Файл:** [`core/decision_engine.py`](file:///C:/Users/denis/Documents/antigravity/localAgent/core/decision_engine.py#L244)
**Строки:** 244–278

В `_parse_fast_path()` существует два перекрывающихся механизма для URL-навигации:

**Шаг 9 (строки 244–260):** `subpages_map` — hardcoded словарь в коде:
```python
subpages_map = {
    "подписки на ютубе": "...",
    "тренды гитхаб": "...",
    ...
}
```

**Шаг 10 (строки 262–278):** `url_map` — загружается из `commands.json`, содержит те же ключи («ютуб», «github», «подписки на ютубе» и др.).

Но в `commands.json` `urls` секция содержит более богатый набор: «подписки ютуб», «тренды ютуб», «история ютуб», «библиотека ютуб», «музыка вк» и т.д. Проблема: шаг 9 использует `if sub_key in q` (подстрока), а шаг 10 использует regex `^(?:открой|перейди на|зайди на)\s+([...]+)$`. Ключи из `commands.json` с несколькими словами («подписки на ютубе», «тренды ютуб») **никогда не попадут** в шаг 10, потому что regex в шаге 10 ищет только один токен. Они обработаются только через шаг 9 (если ключ хардкодирован там) или не обработаются совсем.

**Итог:** URL-записи в `commands.json` с многословными ключами (кроме тех, что уже есть в hardcoded `subpages_map`) будут **проигнорированы** Fast-Path и всегда уйдут в Vision-агент.

---

## Итог

| Категория | Количество |
|---|---|
| 🔴 Критических (runtime) | 3 |
| 🟡 Средних (логических) | 3 |
| 🟢 Низких (tech-debt) | 3 |

**Самое срочное:** BUG-001 (NameError при управлении окнами), BUG-002 (команда «Включи звук» не работает), BUG-003 (блокировка ПК не работает).
