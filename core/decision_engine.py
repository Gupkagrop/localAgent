"""
Модуль семантического роутинга и принятия решений (Decision Engine).
Преобразует произвольный текст голосовой команды в строго типизированный JSON.
Объединяет сверхбыстрый Fast-Path (0 мс) и поддержку локальной LLM с полной выгрузкой VRAM.
"""
import re
import json
import os
import gc
from typing import Optional, Any

class DecisionEngine:
    def __init__(self, models_dir: Optional[str] = None, config_path: Optional[str] = None):
        self.project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.models_dir = models_dir or os.path.join(self.project_dir, "models")
        self.commands_path = config_path or os.path.join(self.project_dir, "config", "commands.json")
        self._llm = None
        self._is_loaded = False
        self._load_commands_config()

    def _load_commands_config(self):
        """Загружает динамическую конфигурацию приложений и ссылок из commands.json."""
        self.app_map = {
            "калькулятор": "calc.exe",
            "блокнот": "notepad.exe",
            "проводник": "explorer.exe",
            "диспетчер задач": "taskmgr.exe",
            "хром": "chrome.exe",
            "браузер": "chrome.exe",
            "телеграм": "telegram.exe",
            "настройки": "ms-settings:"
        }
        self.url_map = {
            "ютуб": "https://youtube.com",
            "youtube": "https://youtube.com",
            "гитхаб": "https://github.com",
            "github": "https://github.com",
            "вк": "https://vk.com",
            "vk": "https://vk.com",
            "вконтакте": "https://vk.com",
            "почта": "https://mail.google.com"
        }
        if os.path.exists(self.commands_path):
            try:
                with open(self.commands_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "apps" in data and isinstance(data["apps"], dict):
                        self.app_map.update(data["apps"])
                    if "urls" in data and isinstance(data["urls"], dict):
                        self.url_map.update(data["urls"])
            except Exception as e:
                print(f"[DecisionEngine Error loading commands.json] {e}")

    def is_llm_available(self) -> bool:
        """Проверяет наличие локального файла весов GGUF."""
        model_path = os.path.join(self.models_dir, "qwen2.5-1.5b-instruct-q4_k_m.gguf")
        return os.path.exists(model_path) and os.path.getsize(model_path) > 100_000_000

    def get_model_status(self) -> str:
        """Возвращает наглядный статус работы модуля ИИ."""
        if self.is_llm_available():
            return "Локальная LLM (Qwen2.5 1.5B Q4)"
        return "Fast-Path (0 мс, 0 МБ VRAM)"

    def download_llm_model(self, progress_callback: Optional[Any] = None) -> bool:
        """Скачивает модель Qwen2.5-1.5B GGUF с Hugging Face."""
        url = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
        os.makedirs(self.models_dir, exist_ok=True)
        dest_path = os.path.join(self.models_dir, "qwen2.5-1.5b-instruct-q4_k_m.gguf")
        temp_path = dest_path + ".download"

        try:
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                block_size = 1024 * 1024  # 1 MB

                with open(temp_path, "wb") as out_file:
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        downloaded += len(buffer)
                        out_file.write(buffer)
                        if progress_callback and total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            progress_callback(percent, downloaded, total_size)

            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(temp_path, dest_path)
            return True
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            return False

    def load_model(self) -> bool:
        """Загружает модель GGUF в видеопамять если файл существует."""
        model_path = os.path.join(self.models_dir, "qwen2.5-1.5b-instruct-q4_k_m.gguf")
        if not os.path.exists(model_path):
            return False

        try:
            from llama_cpp import Llama
            self._llm = Llama(
                model_path=model_path,
                n_gpu_layers=-1,
                n_ctx=1024,
                verbose=False
            )
            self._is_loaded = True
            return True
        except Exception as e:
            print(f"[LLM Load Error] {e}")
            self._llm = None
            self._is_loaded = False
            return False

    def unload_model(self) -> None:
        """Полная выгрузка нейросети из VRAM в 0 МБ."""
        if self._llm is not None:
            del self._llm
            self._llm = None
            self._is_loaded = False
            gc.collect()

    def parse_command(self, query: str) -> dict[str, Any]:
        """
        Преобразует пользовательский запрос в структурированное действие.
        Возвращает: {"action": "...", "target": "...", "parameters": {...}}
        """
        raw_query = query.strip()
        if not raw_query:
            return {"action": "unknown", "target": "", "parameters": {}}

        # Очищаем обращение («джарвис», «компьютер»)
        cleaned_raw = re.sub(r"^(джарвис|компьютер|ассистент)[\s,]+", "", raw_query, flags=re.IGNORECASE).strip()
        text = cleaned_raw.lower()

        # 1. Antigravity 2.0 (GUI)
        if any(kw in text for kw in ["антигравити", "antigravity"]):
            # Приоритет: сначала проверяем создание нового диалога
            if "новый чат" in text or "новый диалог" in text:
                return {
                    "action": "antigravity_gui",
                    "target": "new_chat",
                    "parameters": {}
                }

            # Проверяем, есть ли запрос на ввод промпта
            match_prompt = re.search(r"(напиши|создай|сделай|запрос|спроси)\s+(.+)", cleaned_raw, flags=re.IGNORECASE)
            if match_prompt and "cli" not in text and "терминал" not in text:
                return {
                    "action": "antigravity_gui",
                    "target": "prompt",
                    "parameters": {"prompt": match_prompt.group(2).strip(), "new_chat": True}
                }

            if "cli" not in text and "терминал" not in text and "консоль" not in text:
                return {
                    "action": "antigravity_gui",
                    "target": "open",
                    "parameters": {}
                }

        # 2. Antigravity CLI
        if any(kw in text for kw in ["cli", "agy", "терминал", "консоль"]) and ("antigravity" in text or "антигравити" in text or "agy" in text):
            match_task = re.search(r"(cli|agy|терминал|консоль)\s+(.+)", cleaned_raw, flags=re.IGNORECASE)
            prompt = match_task.group(2).strip() if match_task else ""
            return {
                "action": "antigravity_cli",
                "target": "launch",
                "parameters": {"prompt": prompt}
            }

        # 3. Громкость звука
        volume_keywords = ["громк", "звук", "тише", "потише", "громче", "погромче", "без звука", "мут", "заглуши"]
        if any(kw in text for kw in volume_keywords):
            # Точный процент
            match_num = re.search(r"(\d+)\s*(%|процент)?", text)
            if match_num:
                val = int(match_num.group(1))
                return {
                    "action": "set_volume",
                    "target": "absolute",
                    "parameters": {"percent": max(0, min(100, val))}
                }
            if any(kw in text for kw in ["тише", "убавь", "потише", "снизь"]):
                return {
                    "action": "set_volume",
                    "target": "step_down",
                    "parameters": {"step": 10}
                }
            if any(kw in text for kw in ["громче", "прибавь", "погромче", "увеличь"]):
                return {
                    "action": "set_volume",
                    "target": "step_up",
                    "parameters": {"step": 10}
                }
            if any(kw in text for kw in ["выключи звук", "без звука", "мут", "заглуши"]):
                return {
                    "action": "set_volume",
                    "target": "mute",
                    "parameters": {}
                }

        # 4. Управление медиаплеером
        if any(kw in text for kw in ["пауза", "останови музыку", "стоп музыка", "плей", "продолжи воспроизведение"]):
            return {
                "action": "media_control",
                "target": "play_pause",
                "parameters": {}
            }
        if any(kw in text for kw in ["следующий трек", "след трек", "переключи трек", "вперед"]):
            return {
                "action": "media_control",
                "target": "next_track",
                "parameters": {}
            }
        if any(kw in text for kw in ["предыдущий трек", "пред трек", "назад"]):
            return {
                "action": "media_control",
                "target": "prev_track",
                "parameters": {}
            }

        # Извлекаем слова без пунктуации для быстрого поиска
        words = [re.sub(r"[^\w-]", "", w) for w in text.split()]

        # 5. Специфические страницы сайтов (многословные URL из commands.json)
        # Сортируем по убыванию длины, чтобы составные («сообщения вк») проверялись до («вк»)
        multi_word_urls = [(k, v) for k, v in self.url_map.items() if " " in k]
        multi_word_urls.sort(key=lambda x: len(x[0]), reverse=True)
        norm_text = re.sub(r"\b(в|во|на|к)\b", " ", text)
        norm_text = re.sub(r"\s+", " ", norm_text).strip()

        for site_key, site_url in multi_word_urls:
            if site_key in text or site_key in norm_text:
                return {
                    "action": "open_url",
                    "target": site_url,
                    "parameters": {"site": site_key}
                }
            key_words = site_key.split()
            all_present = True
            for kw in key_words:
                kw_stem = kw[:-1] if len(kw) >= 5 else kw
                if not any(w.startswith(kw_stem) for w in words):
                    all_present = False
                    break
            if all_present:
                return {
                    "action": "open_url",
                    "target": site_url,
                    "parameters": {"site": site_key}
                }

        # 6. Прямые доменные имена и ссылки (например: «открой vk.com в браузере»)
        # Проверяются ДО списка приложений, чтобы слова вроде «браузер» не перехватывали URL
        domain_match = re.search(
            r'([a-zA-Z0-9-]+\.(?:com|ru|org|net|io|dev|ai|me|info|biz|рф)(?:/[^\s]*)?)',
            text,
            flags=re.IGNORECASE
        )
        if domain_match:
            dom = domain_match.group(1).strip()
            target_url = f"https://{dom}" if not dom.startswith("http") else dom
            return {
                "action": "open_url",
                "target": target_url,
                "parameters": {"domain": dom}
            }

        # 7. Запуск программ (из commands.json)
        # Проверяется ДО общего поиска/медиа, чтобы «включи калькулятор» открывало calc.exe
        for name, cmd in self.app_map.items():
            matches = any(
                w == name or (len(name) >= 4 and w.startswith(name[:-1]))
                for w in words
            )
            if name in text or matches:
                return {
                    "action": "launch_app",
                    "target": cmd,
                    "parameters": {"app_name": name}
                }

        # 8. Поиск в Google (если явно упомянут Google / в гугле)
        if "в гугле" in text or "гугл" in text or "google" in text:
            query_part = re.sub(r"^(найди в гугле|поищи в гугле|найди|поищи|гугл)\s+", "", cleaned_raw, flags=re.IGNORECASE)
            query_part = re.sub(r"\b(?:в гугле|в google|гугл|google)\b", "", query_part, flags=re.IGNORECASE).strip()
            return {
                "action": "open_url",
                "target": f"https://www.google.com/search?q={query_part}",
                "parameters": {"query": query_part}
            }

        # 9. YouTube (поиск, каналы, прямое воспроизведение треков/видео)
        has_yt_keyword = bool(re.search(r"(?:ютуб\w*|youtube)", text))
        has_play_intent = bool(re.search(
            r"\b(?:включи\w*|поставь|воспроизведи|вруби|запусти|послушать|слушать|глянуть|посмотреть)\b",
            text
        ))
        has_media_noun = bool(re.search(
            r"\b(?:видео|ролик|клип|песн\w*|трек|фильм)\b",
            text
        ))

        if has_yt_keyword or has_play_intent or (has_media_noun and not any(w in text for w in ["пауза", "стоп", "громк"])):
            is_latest = bool(re.search(r"\b(?:последн\w*|свеж\w*|нов\w*|крайн\w*)\b", text))
            is_search_only = bool(re.search(r"\b(?:найди|поищи|список)\b", text)) and not has_play_intent
            is_direct_play = not is_search_only and (has_play_intent or has_media_noun or is_latest)

            # Извлекаем тему / поисковый запрос
            search_query = cleaned_raw
            # Очищаем упоминание сервиса
            search_query = re.sub(r"(?:на\s+|в\s+)?(?:ютуб\w*|youtube)", "", search_query, flags=re.IGNORECASE)
            # Очищаем глаголы
            search_query = re.sub(
                r"\b(?:открой|запусти|включи\w*|поставь|воспроизведи|вруби|найди|поищи|покажи|послушать|слушать|глянуть|посмотреть)\b",
                "",
                search_query,
                flags=re.IGNORECASE
            )
            # Очищаем медиа-существительные
            search_query = re.sub(r"\b(?:видео|ролик|клип|песн\w*|трек|фильм)\b", "", search_query, flags=re.IGNORECASE)
            # Очищаем слова свежести
            if is_latest:
                search_query = re.sub(r"\b(?:последн\w*|свеж\w*|нов\w*|крайн\w*)\b", "", search_query, flags=re.IGNORECASE)
            # Очищаем вводные слова
            search_query = re.sub(r"\b(?:пожалуйста|плиз|там|в браузере|и)\b", "", search_query, flags=re.IGNORECASE)
            search_query = re.sub(r"\s+", " ", search_query).strip()

            if search_query:
                target_url = f"https://www.youtube.com/results?search_query={search_query}"
                if is_latest:
                    target_url += "&sp=CAI%253D"
                return {
                    "action": "open_url",
                    "target": target_url,
                    "parameters": {
                        "query": search_query,
                        "direct_play": is_direct_play,
                        "sort_by_date": is_latest
                    }
                }
            if has_yt_keyword:
                return {
                    "action": "open_url",
                    "target": "https://www.youtube.com",
                    "parameters": {}
                }

        # 10. Общий поиск в Google («найди ...», «поищи ...»)
        if text.startswith("найди") or text.startswith("поищи"):
            query_part = re.sub(r"^(найди|поищи)\s+", "", cleaned_raw, flags=re.IGNORECASE).strip()
            return {
                "action": "open_url",
                "target": f"https://www.google.com/search?q={query_part}",
                "parameters": {"query": query_part}
            }

        # 11. Однословные URL из commands.json («ютуб», «вк», «гитхаб», «почта»)
        single_word_urls = [(k, v) for k, v in self.url_map.items() if " " not in k]
        for site_key, site_url in single_word_urls:
            matches = any(
                w == site_key or (len(site_key) >= 4 and w.startswith(site_key[:-1]))
                for w in words
            )
            if site_key in text or matches:
                return {
                    "action": "open_url",
                    "target": site_url,
                    "parameters": {"site": site_key}
                }



        # 7. Потенциально опасные команды (требующие подтверждения)
        if any(kw in text for kw in ["выключи ноутбук", "выключи компьютер", "заверши работу"]):
            return {
                "action": "system_action",
                "target": "shutdown",
                "parameters": {"dangerous": True}
            }
        if any(kw in text for kw in ["перезагрузи", "перезагрузка"]):
            return {
                "action": "system_action",
                "target": "restart",
                "parameters": {"dangerous": True}
            }

        # 8. Локальная LLM (Qwen2.5 1.5B) при наличии файла весов
        if self.is_llm_available():
            llm_result = self._parse_with_llm(cleaned_raw)
            if llm_result.get("action") != "unknown":
                return llm_result

        # 9. Неизвестная команда
        return {
            "action": "unknown",
            "target": text,
            "parameters": {}
        }

    def _parse_with_llm(self, query: str) -> dict[str, Any]:
        """Инференс локальной нейросети Qwen2.5 GGUF для семантического роутинга и ответов."""
        if not self._is_loaded or self._llm is None:
            ok = self.load_model()
            if not ok or self._llm is None:
                return {"action": "unknown", "target": query, "parameters": {}}

        schema = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "launch_app",
                        "open_url",
                        "antigravity_gui",
                        "antigravity_cli",
                        "set_volume",
                        "media_control",
                        "system_action",
                        "general_answer",
                        "unknown"
                    ]
                },
                "target": {"type": "string"},
                "parameters": {"type": "object"}
            },
            "required": ["action", "target", "parameters"]
        }

        system_prompt = (
            "Ты — интеллектуальный диспетчер команд голосового ассистента Windows. "
            "Пользователь говорит по-русски. Твоя задача — вернуть строго JSON объект действия.\n"
            "Примеры:\n"
            "- 'открой калькулятор' -> {\"action\": \"launch_app\", \"target\": \"calc.exe\", \"parameters\": {\"app_name\": \"калькулятор\"}}\n"
            "- 'открой блокнот' -> {\"action\": \"launch_app\", \"target\": \"notepad.exe\", \"parameters\": {\"app_name\": \"блокнот\"}}\n"
            "- 'включи музыку' -> {\"action\": \"media_control\", \"target\": \"play_pause\", \"parameters\": {}}\n"
            "- 'громкость 50' -> {\"action\": \"set_volume\", \"target\": \"absolute\", \"parameters\": {\"percent\": 50}}\n"
            "- 'сделай тише' -> {\"action\": \"set_volume\", \"target\": \"step_down\", \"parameters\": {\"step\": 10}}\n"
            "- 'найди в гугле питон' -> {\"action\": \"open_url\", \"target\": \"https://www.google.com/search?q=питон\", \"parameters\": {\"query\": \"питон\"}}\n"
            "- 'открой ютуб' -> {\"action\": \"open_url\", \"target\": \"https://youtube.com\", \"parameters\": {}}\n"
            "- 'открой вк' -> {\"action\": \"open_url\", \"target\": \"https://vk.com\", \"parameters\": {\"site\": \"вк\"}}\n"
            "- 'открой vk.com в браузере' -> {\"action\": \"open_url\", \"target\": \"https://vk.com\", \"parameters\": {\"domain\": \"vk.com\"}}\n"
            "- 'открой антигравити' -> {\"action\": \"antigravity_gui\", \"target\": \"open\", \"parameters\": {}}\n"
            "- 'создай новый чат в антигравити' -> {\"action\": \"antigravity_gui\", \"target\": \"new_chat\", \"parameters\": {}}\n"
            "- 'напиши в антигравити напиши скрипт' -> {\"action\": \"antigravity_gui\", \"target\": \"prompt\", \"parameters\": {\"prompt\": \"напиши скрипт\", \"new_chat\": true}}\n"
            "- 'запусти в agy тесты' -> {\"action\": \"antigravity_cli\", \"target\": \"launch\", \"parameters\": {\"prompt\": \"agy тесты\"}}\n"
            "- 'сколько будет два плюс два' -> {\"action\": \"general_answer\", \"target\": \"answer\", \"parameters\": {\"text\": \"Четыре.\"}}\n"
            "ПРАВИЛА:\n"
            "1. Для любых команд управления (открыть, запустить, найти, громкость, звук, трек, антигравити) ВСЕГДА выбирай системное действие!\n"
            "2. Для любых сайтов, доменов (.com, .ru) и соцсетей (вк, ютуб, github) ВСЕГДА используй open_url со ссылкой https://, а не launch_app!\n"
            "3. Никогда не используй 'general_answer' для команд запуска или управления!\n"
            "4. Для вопросов отвечай 'general_answer' СТРОГО одним кратким предложением (до 10-12 слов), без вступительных слов и без монологов."
        )

        try:
            resp = self._llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                response_format={"type": "json_object", "schema": schema},
                max_tokens=64,
                temperature=0.0
            )
            content = resp["choices"][0]["message"]["content"].strip()
            data = json.loads(content)
            action = data.get("action", "unknown")

            # Защита от длинных ответов при general_answer
            if action == "general_answer":
                params = data.get("parameters", {})
                raw_text = params.get("text", "") or data.get("target", "")

                # Если запрос содержал глаголы действия, перенаправляем в поиск вместо чтения лекции
                cmd_verbs = ["открой", "запусти", "включи", "найди", "поищи", "поставь"]
                if any(v in query.lower() for v in cmd_verbs):
                    return {
                        "action": "open_url",
                        "target": f"https://www.google.com/search?q={query}",
                        "parameters": {"query": query}
                    }

                # Оставляем ровно 1 первое предложение (до 100 символов)
                sentences = re.split(r"(?<=[.!?])\s+", str(raw_text).strip())
                short_text = sentences[0] if sentences else str(raw_text).strip()
                if len(short_text) > 100:
                    short_text = short_text[:97] + "..."
                params["text"] = short_text
                data["parameters"] = params

            return data
        except Exception:
            try:
                # Запасной вариант если response_format со схемой не поддерживается
                resp = self._llm.create_chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query}
                    ],
                    max_tokens=64,
                    temperature=0.0
                )
                content = resp["choices"][0]["message"]["content"].strip()
                match = re.search(r"\{.*\}", content, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    if isinstance(data, dict) and "action" in data:
                        return data
            except Exception:
                pass

            # Если была команда, перенаправляем в веб-поиск
            cmd_verbs = ["открой", "запусти", "включи", "найди", "поищи"]
            if any(v in query.lower() for v in cmd_verbs):
                return {
                    "action": "open_url",
                    "target": f"https://www.google.com/search?q={query}",
                    "parameters": {"query": query}
                }

            return {
                "action": "unknown",
                "target": query,
                "parameters": {}
            }
