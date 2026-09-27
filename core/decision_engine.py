"""
Модуль семантического роутинга и принятия решений (Decision Engine).
Обеспечивает двухуровневую гибридную маршрутизацию:
1. Fast-Path (0 мс, 0 МБ VRAM): мгновенные системные команды (громкость, окна, медиа, запуск по алиасам).
2. Vision-Path: автономное выполнение задач в интерфейсе Windows/Web через Vision-агента (Jedi-3B / Qwen2.5-VL).
"""

import json
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional


class DecisionEngine:
    """Двухуровневый маршрутизатор команд ассистента."""

    def __init__(self, config_path: Optional[str] = None, models_dir: Optional[str] = None) -> None:
        self.project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.commands_path = config_path or os.path.join(self.project_dir, "config", "commands.json")
        self._load_commands_config()

    def _load_commands_config(self) -> None:
        """Загружает словарь известных приложений и URL."""
        self.app_map: Dict[str, str] = {
            "калькулятор": "calc.exe",
            "блокнот": "notepad.exe",
            "проводник": "explorer.exe",
            "диспетчер задач": "taskmgr.exe",
            "хром": "chrome.exe",
            "браузер": "chrome.exe",
            "телеграм": "telegram.exe",
            "настройки": "ms-settings:",
        }
        self.url_map: Dict[str, str] = {
            "ютуб": "https://www.youtube.com",
            "youtube": "https://www.youtube.com",
            "гитхаб": "https://github.com",
            "github": "https://github.com",
            "вк": "https://vk.com",
            "vk": "https://vk.com",
            "вконтакте": "https://vk.com",
            "почта": "https://mail.google.com",
            "яндекс": "https://ya.ru",
            "сообщения вк": "https://vk.com/im",
            "сообщения в вк": "https://vk.com/im",
            "подписки на ютубе": "https://www.youtube.com/feed/subscriptions",
            "подписки на youtube": "https://www.youtube.com/feed/subscriptions",
            "тренды гитхаб": "https://github.com/trending",
            "тренды github": "https://github.com/trending",
            "входящие в почте": "https://mail.google.com/mail/u/0/#inbox",
            "входящие на почте": "https://mail.google.com/mail/u/0/#inbox",
        }
        if not os.path.exists(self.commands_path):
            return

        try:
            with open(self.commands_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "apps" in data and isinstance(data["apps"], dict):
                    self.app_map.update(data["apps"])
                if "urls" in data and isinstance(data["urls"], dict):
                    self.url_map.update(data["urls"])
        except Exception as e:
            print(f"[DecisionEngine Error loading commands.json] {e}")

    def get_model_status(self) -> str:
        """Возвращает наглядный статус работы роутера."""
        return "Fast-Path (0 мс) + Vision Computer-Use (Jedi-3B)"

    def is_llm_available(self) -> bool:
        """Проверяет наличие локальных весов модели Vision-агента в кэше HuggingFace."""
        cache_hub = os.path.expanduser("~/.cache/huggingface/hub")
        jedi_dir = os.path.join(cache_hub, "models--xlangai--Jedi-3B-1080p")
        qwen_dir = os.path.join(cache_hub, "models--Qwen--Qwen2.5-VL-3B-Instruct")
        for mdir in (jedi_dir, qwen_dir):
            if not os.path.exists(mdir):
                continue
            snap_dir = os.path.join(mdir, "snapshots")
            if not os.path.exists(snap_dir):
                continue
            for _, _, files in os.walk(snap_dir):
                if any(f.endswith(".safetensors") or f.endswith(".bin") or f == "config.json" for f in files):
                    return True
        return False

    def load_model(self) -> bool:
        """Проверяет доступность модели Vision-агента (совместимость)."""
        return self.is_llm_available()

    def unload_model(self) -> None:
        """Освобождает ресурсы модели (совместимость интерфейса)."""
        pass

    def download_llm_model(self, progress_callback: Optional[Any] = None) -> bool:
        """Загрузка / проверка наличия весов xlangai/Jedi-3B-1080p в кэше."""
        try:
            from huggingface_hub import snapshot_download
            if progress_callback:
                progress_callback(50, 50, 100)
            snapshot_download(repo_id="xlangai/Jedi-3B-1080p")
            if progress_callback:
                progress_callback(100, 100, 100)
            return True
        except Exception as e:
            print(f"[DecisionEngine Error loading model] {e}")
            return False

    def parse_command(self, text: str) -> Dict[str, Any]:
        """
        Основной метод анализа голосовой команды.
        Сначала проверяет мгновенный Fast Path. Если совпадений нет — направляет в VisionAgent.
        """
        cleaned = text.strip()
        if not cleaned:
            return {"action": "unknown", "target": "", "parameters": {}}

        # 1. Попытка мгновенного разбора через Fast Path
        fast_result = self._parse_fast_path(cleaned)
        if fast_result is not None:
            return fast_result

        # 2. Если это интерфейсное действие, поиск или сложное взаимодействие — передаем в VisionAgent
        return {
            "action": "vision_agent",
            "target": "computer_use",
            "parameters": {
                "prompt": cleaned
            }
        }

    def _parse_fast_path(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Мгновенный разбор регулярными выражениями системных команд (0 мс задержки).
        """
        raw_query = query.strip()
        q_lower = raw_query.lower()

        # 1. Интеграция с Antigravity 2.0 GUI и CLI (с сохранением оригинального регистра текста/кода)
        if "антигравити" in q_lower or "antigravity" in q_lower:
            if any(w in q_lower for w in ["новый чат", "создай чат"]):
                return {"action": "antigravity_gui", "target": "new_chat", "parameters": {}}

            # Контекстный сценарий работы с кодом/ошибкой из буфера обмена (Ctrl+C)
            clipboard_patterns = [
                r"спроси\s+(?:в\s+)?(?:антигравити|antigravity)\s+(?:про\s+)?(?:эту\s+|этот\s+)?(?:ошибк[уае]|код|текст)",
                r"исправь\s+(?:этот\s+)?код\s+(?:в\s+)?(?:антигравити|antigravity)",
                r"объясни\s+(?:эту\s+)?ошибк[уае]\s+(?:в\s+)?(?:антигравити|antigravity)",
                r"(?:в\s+)?(?:антигравити|antigravity)\s+(?:исправь|объясни)\s+(?:этот\s+)?(?:код|ошибк[уае])",
                r"(?:в\s+)?(?:антигравити|antigravity)\s+спроси\s+(?:про\s+)?(?:эту\s+|этот\s+)?(?:ошибк[уае]|код|текст)",
            ]
            if any(re.search(p, q_lower) for p in clipboard_patterns):
                return {
                    "action": "antigravity_cli",
                    "target": "launch",
                    "parameters": {
                        "prompt": "Объясни и исправь следующую ошибку/код:",
                        "use_clipboard": True
                    }
                }

            prompt_match = re.search(r"(?:напиши|спроси|отправь|скажи)\s+(?:в\s+)?(?:антигравити|antigravity)\s+(.+)", raw_query, re.IGNORECASE)
            if prompt_match:
                return {
                    "action": "antigravity_gui",
                    "target": "prompt",
                    "parameters": {"prompt": prompt_match.group(1).strip(), "new_chat": False}
                }

            if any(w in q_lower for w in ["cli", "терминал", "консоль", "запусти в терминале", "agy"]):
                return {"action": "antigravity_cli", "target": "launch", "parameters": {"prompt": raw_query}}

            if any(w in q_lower for w in ["открой", "запусти", "покажи"]):
                return {"action": "antigravity_gui", "target": "open", "parameters": {}}

        # Нормализация для системных команд
        q = q_lower
        # Удаляем слово-триггер если оно присутствует в тексте
        q = re.sub(r"^(?:джарвис|ассистент|компьютер|jarvis)[,\s]+", "", q).strip()
        # Удаляем знаки препинания и вежливые слова в конце фразы
        q = q.rstrip(".,!? ").strip()
        q = re.sub(r"[, ]+(?:пожалуйста|плиз|плииз)$", "", q).strip()
        q = q.rstrip(".,!? ").strip()

        # 2. Управление громкостью звука
        vol_match = re.search(r"(?:громкость|звук)\s*(?:на|в)?\s*(\d{1,3})%?", q)
        if vol_match:
            val = min(100, max(0, int(vol_match.group(1))))
            return {
                "action": "set_volume",
                "target": "absolute",
                "parameters": {"percent": val}
            }

        if any(w in q for w in ["сделай громче", "прибавь звук", "погромче", "увеличь громкость"]):
            return {"action": "set_volume", "target": "step_up", "parameters": {"step": 10}}

        if any(w in q for w in ["сделай тише", "убавь звук", "потише", "уменьши громкость"]):
            return {"action": "set_volume", "target": "step_down", "parameters": {"step": 10}}

        if any(w in q for w in ["выключи звук", "заглуши", "без звука", "мут"]):
            return {"action": "set_volume", "target": "mute", "parameters": {}}

        if any(w in q for w in ["включи звук", "верни звук", "размут"]):
            return {"action": "set_volume", "target": "unmute", "parameters": {}}

        # 3. Управление медиаплеером
        if any(w in q for w in ["пауза", "стоп музыка", "останови музыку", "продолжи воспроизведение"]):
            return {"action": "media_control", "target": "play_pause", "parameters": {}}

        if any(w in q for w in ["следующий трек", "переключи трек", "следующая песня"]):
            return {"action": "media_control", "target": "next_track", "parameters": {}}

        if any(w in q for w in ["предыдущий трек", "прошлый трек", "назад трек"]):
            return {"action": "media_control", "target": "prev_track", "parameters": {}}

        # 4. Горячие клавиши вкладок (перед управлением окнами!)
        if "новая вкладка" in q:
            return {"action": "app_hotkey", "target": "new_tab", "parameters": {"hotkey": "new_tab"}}
        if "закрой вкладку" in q:
            return {"action": "app_hotkey", "target": "close_tab", "parameters": {"hotkey": "close_tab"}}

        # 5. Управление окнами и рабочим столом Windows
        if any(w in q for w in ["сверни все", "сверни всё", "рабочий стол", "покажи рабочий стол"]):
            return {"action": "window_control", "target": "minimize_all", "parameters": {}}

        close_match = re.search(r"^(?:закрой|закрой окно|закрой программу|закрой приложение)\s*(.*)", q)
        if close_match:
            target_app = close_match.group(1).strip()
            return {
                "action": "window_control",
                "target": "close",
                "parameters": {"app_name": target_app}
            }

        min_match = re.search(r"^(?:сверни|сверни окно)\s*(.*)", q)
        if min_match and not any(w in q for w in ["все", "всё"]):
            target_app = min_match.group(1).strip()
            return {
                "action": "window_control",
                "target": "minimize",
                "parameters": {"app_name": target_app}
            }

        max_match = re.search(r"^(?:разверни|разверни окно|на весь экран)\s*(.*)", q)
        if max_match:
            target_app = max_match.group(1).strip()
            return {
                "action": "window_control",
                "target": "maximize",
                "parameters": {"app_name": target_app}
            }

        # 6. Безопасность и управление питанием ПК
        if any(w in q for w in ["заблокируй компьютер", "заблокируй пк", "заблокируй экран"]):
            return {"action": "system_action", "target": "lock_workstation", "parameters": {}}

        if any(w in q for w in ["выключи компьютер", "выключи пк", "выключи ноутбук", "заверши работу"]):
            return {"action": "system_action", "target": "shutdown", "parameters": {"dangerous": True}}

        if any(w in q for w in ["перезагрузи компьютер", "перезагрузи пк", "перезагрузи ноутбук", "перезагрузка"]):
            return {"action": "system_action", "target": "restart", "parameters": {"dangerous": True}}

        # 7. Ввод текста в активное приложение
        type_match = re.search(r"^(?:в|внутри)\s+([a-zA-Zа-яА-Я0-9_.-]+)\s+(?:напиши|введи|напечатай)\s+(.+)", q)
        if type_match:
            app_raw = type_match.group(1).strip()
            if app_raw.endswith("е") and len(app_raw) > 3:
                app_name = app_raw[:-1]
            else:
                app_name = app_raw
            text_to_type = type_match.group(2).strip()
            return {
                "action": "app_type",
                "target": "type",
                "parameters": {"app_name": app_name, "text": text_to_type, "submit": False, "search_mode": False}
            }

        # 8. Быстрый веб-поиск в Google
        google_match = re.search(r"^(?:найди|поищи)\s+(?:в\s+гугле|в\s+google)\s+(.+)", q)
        if google_match:
            search_query = google_match.group(1).strip()
            return {
                "action": "open_url",
                "target": f"https://www.google.com/search?q={urllib.parse.quote(search_query)}",
                "parameters": {"query": search_query}
            }

        # 8b. Прямое воспроизведение видео / музыки на YouTube
        play_video_match = re.search(
            r"^(?:включи|поставь|запусти)\s+(?:видео|ролик|клип|песню|трек|музыку|на ютубе|в ютубе)\s+(.+)",
            q
        )
        if play_video_match:
            video_query = play_video_match.group(1).strip()
            video_query = re.sub(r"^(?:на\s+ютубе|в\s+ютубе|на\s+youtube|в\s+youtube)\s+", "", video_query).strip()
            return {
                "action": "open_url",
                "target": "https://www.youtube.com",
                "parameters": {
                    "query": video_query,
                    "direct_play": True,
                    "sort_by_date": False
                }
            }

        # 8c. Поиск на YouTube
        yt_search_match = re.search(r"^(?:найди|поищи)\s+(?:на\s+ютубе|в\s+ютубе|на\s+youtube|в\s+youtube)\s+(.+)", q)
        if yt_search_match:
            yt_query = yt_search_match.group(1).strip()
            return {
                "action": "open_url",
                "target": f"https://www.youtube.com/results?search_query={urllib.parse.quote(yt_query)}",
                "parameters": {"query": yt_query}
            }

        # 9. Быстрые ссылки на популярные разделы сайтов и составные URL
        # Проверяем многословные ключи из конфигурации (от самых длинных к коротким)
        multi_word_urls = sorted(
            [(k, v) for k, v in self.url_map.items() if " " in k],
            key=lambda item: len(item[0]),
            reverse=True
        )
        for sub_key, sub_url in multi_word_urls:
            if sub_key in q:
                return {
                    "action": "open_url",
                    "target": sub_url,
                    "parameters": {"section": sub_key}
                }

        # 10. Открытие простых известных сайтов (без внутреннего поиска)
        open_url_match = re.search(r"^(?:открой|перейди на|зайди на)\s+([a-zA-Zа-яА-Я0-9_.-]+)(?:\s+(?:в|через)\s+(?:браузере|браузер|хроме|хром))?$", q)
        if open_url_match:
            site_key = open_url_match.group(1).lower()
            if site_key in self.url_map:
                return {
                    "action": "open_url",
                    "target": self.url_map[site_key],
                    "parameters": {"site": site_key}
                }
            if "." in site_key and not site_key.endswith(".exe"):
                url = site_key if site_key.startswith("http") else f"https://{site_key}"
                return {
                    "action": "open_url",
                    "target": url,
                    "parameters": {"domain": site_key}
                }

        # 11. Запуск приложений по точным системным алиасам (без параметров)
        launch_match = re.search(r"^(?:открой|запусти|включи)\s+([a-zA-Zа-яА-Я0-9_.-]+)$", q)
        if launch_match:
            app_key = launch_match.group(1).lower()
            if app_key in self.app_map:
                return {
                    "action": "launch_app",
                    "target": self.app_map[app_key],
                    "parameters": {"app_name": app_key}
                }

        return None
