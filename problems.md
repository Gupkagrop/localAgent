> [!NOTE]
> Данный файл содержит результаты **повторного независимого аудита** кода проекта **Antigravity Voice**.
> Анализ выполнен с нуля после исправлений агента. Дата: **2026-09-26 21:03**.
> Формат: 🔴 Критично, 🟡 Средне, 🟢 Низко / tech-debt, ✅ Исправлено.

# Отчёт аудита — Antigravity Voice (v2, после исправлений)

---

## Итоговая таблица

| ID | Приоритет | Файл | Описание | Статус |
|---|---|---|---|---|
| BUG-001 | ✅ | `speech_to_text.py` | Дублирование `load_model` / `_load_model_unlocked` | ✅ Исправлено |
| BUG-002 | ✅ | `audio_listener.py` | Race condition в `record_command()` | ✅ Исправлено |
| BUG-003 | ✅ | `executor.py` | Утечка буфера обмена | ✅ Исправлено |
| BUG-004 | ✅ | `decision_engine.py` | `load_model()` возвращал `True` при ошибке | ✅ Исправлено |
| BUG-005 | ✅ | `main.py` | Qt-виджет из фонового потока | ✅ Исправлено |
| BUG-006 | ✅ | `decision_engine.py` | LLM никогда не вызывалась | ✅ Исправлено |
| BUG-007 | ✅ | `settings.json` / код | 5 полей конфига игнорировались кодом | ✅ Исправлено |
| BUG-008 | ✅ | `executor.py` + `main.py` | Диалог подтверждения shutdown/restart | ✅ Исправлено |
| BUG-009 | ✅ | `audio_ducking.py` | `duck_factor` не читался из настроек | ✅ Исправлено |
| BUG-010 | ✅ | `main_window.py` | `toggled` до `setChecked` → лишний `save_settings()` | ✅ Исправлено |
| BUG-011 | ✅ | `commands.json` | Файл не читался кодом | ✅ Исправлено |
| BUG-012 | ✅ | `audio_listener.py` | `stop_wake_word_loop()` не сбрасывал `"recording"` | ✅ Исправлено |
| BUG-013 | ✅ | `floating_pill.py` | `update_text()` не вызывал `show()` | ✅ Исправлено |
| NEW-001 | 🟡 | `main.py` | `_run_check_all_systems`: вызов несуществующего метода `_get_endpoint_volume()` вместо `_get_volume_endpoint()` | ❌ Новый баг |
| NEW-002 | 🟡 | `audio_listener.py` | `_record_buffer` читается внутри лока, но пишется из аудио-потока без лока | ❌ Новый баг |
| NEW-003 | 🟢 | `decision_engine.py` | Стеммер слов для URL/App map ненадёжен — `rstrip("аеиоуыэюя")` не является полноценной морфологией | ⚠️ Деградация |
| NEW-004 | 🟢 | `commands.json` | Секция `"antigravity"` (строки 21–24) загружается, но нигде не используется | ⚠️ Мёртвый конфиг |
| NEW-005 | 🟢 | `main.py` | `pill.show_listening()` вызывается напрямую из `worker()` (не GUI поток) | ⚠️ Потенциальный UB |
| NEW-006 | 🟢 | `audio_ducking.py` | `unduck()`: если `endpoint is None`, `_is_ducked` и `_previous_volume` не сбрасываются — следующий `unduck()` опять войдёт в блок и снова не восстановит громкость | ❌ Остаточный баг |
| ISSUE-002 | 🟢 | `full_verification.py` | `scipy` импортируется в тестах, не используется в продакшн-коде | ⚠️ Tech debt |
| ISSUE-004 | 🟢 | `create_shortcut.py` | Ярлык не передаёт `--minimized` при создании | ⚠️ Tech debt |
| ISSUE-006 | 🟢 | `styles.py` | Горизонтальный скроллбар не стилизован | ⚠️ Косметика |

---

## Что исправлено с нуля (все 13 старых багов)

### ✅ BUG-001 — `speech_to_text.py`
`load_model()` теперь просто делегирует в `_load_model_unlocked()` (строки 39–42). Дублирование устранено.

### ✅ BUG-002 — `audio_listener.py`
Добавлен `self._state_lock = threading.Lock()` (строка 29). Все операции над `_mode` в `record_command()` (строки 202–210), `start_wake_word_loop()` (строки 232–236) и `stop_wake_word_loop()` (строки 242–246) защищены. В `_run_loop` режим читается атомарно (строки 109–110). Возврат `_record_buffer` тоже под локом (строки 216–223).

### ✅ BUG-003 — `executor.py`
`CloseClipboard()` перенесён в `finally` блок (строки 168–173).

### ✅ BUG-004 — `decision_engine.py`
`load_model()` теперь возвращает `False` если файл отсутствует (строка 104), и `False` при исключении (строки 116–120). `_llm = None` явно выставляется при ошибке.

### ✅ BUG-005 — `main.py`
`btn_download_llm.setEnabled(False)` перенесён в GUI-поток — вызывается **до** запуска `worker()`, на строке 323 в методе `_run_download_llm()`, который сам вызывается из GUI.

### ✅ BUG-006 — `decision_engine.py`
Добавлен `_parse_with_llm()` (строки 298–347) с полноценным system-prompt. Вызывается на шаге 8 `parse_command()` (строки 285–289).

### ✅ BUG-007 — Поля `settings.json` теперь используются кодом
- `tts_voice`, `tts_speed` → передаются в `TextToSpeech(voice_name=..., speed=...)` (main.py строки 61–69)
- `tts_voice`, `tts_speed` → применяются при изменении настроек (`_on_settings_updated`, строки 218–222)
- `wake_word` → читается в `_apply_activation_mode()` (строки 206–207), передаётся в `start_wake_word_loop()`
- `audio_ducking_level` → читается в `_handle_voice_input()` (строка 570) и `_run_test_sound()` (строка 269), передаётся в `duck(duck_factor=...)`
- `confirm_dangerous_actions` → проверяется в `_handle_voice_input()` (строка 604) и `_handle_text_command()` (строка 641)

### ✅ BUG-008 — Подтверждение опасных действий
`confirm_action_signal` / `_show_confirmation_dialog()` реализован полностью. При `confirm_dangerous_actions: false` в настройках действие выполняется без диалога (строки 607–614).

### ✅ BUG-009 — `audio_ducking.py`
`duck_factor` по умолчанию изменён с `0.25` на `0.20` (строка 25), и вызывается с явным `duck_factor` из настроек.

### ✅ BUG-010 — `main_window.py`
Перед `setChecked()` вызывается `blockSignals(True)` на обеих радиокнопках (строки 264–271), после — `blockSignals(False)`. Лишний `save_settings()` при старте устранён.

### ✅ BUG-011 — `commands.json` теперь читается
`DecisionEngine.__init__` принимает `config_path` (строка 13), вызывает `_load_commands_config()` (строка 19). Метод мержит `data["apps"]` в `self.app_map` и `data["urls"]` в `self.url_map` (строки 40–48). В `parse_command()` используются эти динамические карты (строки 252–269).

### ✅ BUG-012 — `audio_listener.py`
`stop_wake_word_loop()` теперь всегда (без проверки текущего режима) устанавливает `_mode = "idle"` и вызывает `_record_done_event.set()` (строки 242–246) — разблокирует зависшую запись.

### ✅ BUG-013 — `floating_pill.py`
`update_text()` теперь вызывает `self.show()` и `self.raise_()` (строки 82–90), плюс останавливает таймер скрытия в начале.

---

## Новые баги, обнаруженные после исправлений

---

### 🟡 NEW-001 — `main.py` строка 466: несуществующий метод `_get_endpoint_volume()`

**Критичность:** средняя — упадёт при первом запуске «Комплексной диагностики».

```python
# main.py, строка 466 в _run_check_all_systems():
has_endpoint = self.audio_ducker._get_endpoint_volume() is not None
```

Метод в `AudioDucker` называется `_get_volume_endpoint()`, а не `_get_endpoint_volume()`. При запуске "⚡ Проверить все системы" блок 5/7 упадёт с `AttributeError`.

**Исправление:**
```python
has_endpoint = self.audio_ducker._get_volume_endpoint() is not None
```

---

### 🟡 NEW-002 — `audio_listener.py`: `_record_buffer` читается под локом, пишется без

В `_process_recording()` (строка 124):
```python
self._record_buffer.append(chunk)  # ← вызывается из аудио-потока, БЕЗ _state_lock
```

В `record_command()` (строки 216–223):
```python
with self._state_lock:
    ...
    return np.concatenate(self._record_buffer)  # ← читается ПОД локом
```

Т.е. буфер **пишется без лока** и **читается с локом** — это не обеспечивает потокобезопасность. В Python GIL защищает от одновременного append + read на уровне байткода, но `np.concatenate` во время одновременного append может получить неконсистентный список (особенно на подмене `_record_buffer = []` в строке 205 vs append в строке 124). Это race на составных операциях.

---

### 🟢 NEW-003 — `decision_engine.py`: ненадёжный стеммер для app/url map

```python
# Строки 253 и 263:
stem = site_key.rstrip("аеиоуыэюя") if len(site_key) > 3 else site_key
if site_key in text or (stem and stem in text):
```

Например, `"браузер"` → stem `"браз"` (не `"браузер"` без окончания). Или `"телеграм"` → `"телегр"` — может дать ложное срабатывание на слове `"телеграф"`. Использование `rstrip` вместо морфологического стеммера — заведомо ненадёжное решение.

**Рекомендация:** убрать стем-матчинг или заменить простой проверкой `startswith`.

---

### 🟢 NEW-004 — `commands.json`: секция `"antigravity"` не используется

```json
"antigravity": {
    "gui_window_names": ["Antigravity", "antigravity"],
    "cli_executable": "agy"
}
```

`_load_commands_config()` читает только `data["apps"]` и `data["urls"]`. Секция `"antigravity"` загружается, но не используется — `executor.py` всё равно хардкодит `"antigravity"` в строке поиска окна (строка 139: `if "antigravity" in title.lower()`).

---

### 🟢 NEW-005 — `main.py`: `pill.show_listening()` из фонового потока

```python
# Строки 564-566 в worker() внутри _handle_voice_input():
def worker():
    ...
    self._play_sound("activate")
    self.pill.show_listening()   # ← прямой вызов Qt-виджета из threading.Thread
```

`FloatingPill` — это `QWidget`. Вызов его методов из не-GUI потока технически UB в PyQt6, хотя на практике часто работает. Правильный вариант — через сигнал.

---

### 🟢 NEW-006 — `audio_ducking.py`: `_is_ducked` не сбрасывается если `endpoint is None`

```python
def unduck(self) -> None:
    with self._lock:
        if not self._is_ducked or self._previous_volume is None:
            return

        endpoint = self._get_volume_endpoint()
        if endpoint is not None:
            try:
                endpoint.SetMasterVolumeLevelScalar(self._previous_volume, None)
                self._is_ducked = False        # ← только внутри if endpoint
                self._previous_volume = None   # ← только внутри if endpoint
            except Exception:
                pass
        # ← если endpoint is None: _is_ducked и _previous_volume НЕ сбрасываются
        # следующий вызов unduck() снова зайдёт в метод, снова получит None и ничего не сделает
        # duck() не даст приглушить снова (is_ducked = True)
```

Результат: если `GetSpeakers()` недоступен временно — ассистент навсегда останется в состоянии «приглушён» (duck), даже если устройство восстановилось. Нужно сбрасывать флаги в любом случае.

**Исправление:**
```python
endpoint = self._get_volume_endpoint()
if endpoint is not None:
    try:
        endpoint.SetMasterVolumeLevelScalar(self._previous_volume, None)
    except Exception:
        pass
# Сбрасываем всегда, независимо от наличия endpoint
self._is_ducked = False
self._previous_volume = None
```

---

## Общий прогресс

| Категория | Было | Стало |
|---|---|---|
| 🔴 Критических | 5 | 0 |
| 🟡 Средних | 8 | 2 (NEW-001, NEW-002) |
| 🟢 Низких/tech-debt | 6 | 6 (3 новых, 3 старых) |
| ✅ Исправлено | 0 | 13 из 13 |

**Качество кода значительно улучшилось.** Самое срочное к исправлению: **NEW-001** (упадёт при диагностике) и **NEW-006** (логическая ошибка состояния ducking).
