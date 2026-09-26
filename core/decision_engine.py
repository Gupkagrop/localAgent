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

        # 5. Веб-поиск и сайты
        if text.startswith("найди в гугле") or text.startswith("поищи") or text.startswith("найди"):
            query_part = re.sub(r"^(найди в гугле|поищи|найди)\s+", "", cleaned_raw, flags=re.IGNORECASE).strip()
            return {
                "action": "open_url",
                "target": f"https://www.google.com/search?q={query_part}",
                "parameters": {"query": query_part}
            }
        if "ютуб" in text or "youtube" in text:
            match_yt = re.search(r"(ютуб|youtube)\s+(.+)", cleaned_raw, flags=re.IGNORECASE)
            if match_yt:
                return {
                    "action": "open_url",
                    "target": f"https://www.youtube.com/results?search_query={match_yt.group(2).strip()}",
                    "parameters": {}
                }
            return {
                "action": "open_url",
                "target": "https://www.youtube.com",
                "parameters": {}
            }
        # Динамические URL из commands.json
        for site_key, site_url in self.url_map.items():
            stem = site_key.rstrip("аеиоуыэюя") if len(site_key) > 3 else site_key
            if site_key in text or (stem and stem in text):
                return {
                    "action": "open_url",
                    "target": site_url,
                    "parameters": {"site": site_key}
                }

        # 6. Запуск программ (динамически из commands.json + встроенные)
        for name, cmd in self.app_map.items():
            stem = name.rstrip("аеиоуыэюя") if len(name) > 3 else name
            if name in text or (stem and stem in text):
                return {
                    "action": "launch_app",
                    "target": cmd,
                    "parameters": {"app_name": name}
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

        system_prompt = (
            "Ты — интеллектуальный диспетчер команд голосового ассистента Windows. "
            "Пользователь говорит по-русски. Твоя задача — вернуть строго JSON объект без лишнего текста и markdown. "
            "Формат JSON: {\"action\": string, \"target\": string, \"parameters\": object}. "
            "Поддерживаемые действия:\n"
            "- \"antigravity_gui\": target in [\"open\", \"new_chat\", \"prompt\"], parameters: {\"prompt\": \"...\"}\n"
            "- \"antigravity_cli\": target \"launch\", parameters: {\"prompt\": \"...\"}\n"
            "- \"set_volume\": target in [\"step_up\", \"step_down\", \"mute\", \"absolute\"], parameters: {\"percent\": 0-100}\n"
            "- \"media_control\": target in [\"play_pause\", \"next_track\", \"prev_track\"]\n"
            "- \"open_url\": target URL (например https://www.google.com/search?q=...)\n"
            "- \"launch_app\": target executable name (например calc.exe, notepad.exe, telegram.exe, code.exe)\n"
            "- \"system_action\": target in [\"shutdown\", \"restart\"], parameters: {\"dangerous\": True}\n"
            "- \"general_answer\": target \"answer\", parameters: {\"text\": \"Краткий и точный ответ на русском языке (1-2 предложения)\"}\n"
            "Если запрос — это вопрос, справка или беседа, всегда возвращай action \"general_answer\"."
        )

        try:
            resp = self._llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                max_tokens=150,
                temperature=0.1
            )
            content = resp["choices"][0]["message"]["content"].strip()
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                if isinstance(data, dict) and "action" in data:
                    return data

            return {
                "action": "general_answer",
                "target": "answer",
                "parameters": {"text": content}
            }
        except Exception:
            return {
                "action": "unknown",
                "target": query,
                "parameters": {}
            }
