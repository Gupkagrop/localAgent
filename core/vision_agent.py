"""
Мультимодальный автономный агент компьютерного управления (Vision Computer-Use Agent).
Обеспечивает зрение (GDI BitBlt), рассуждение (Jedi-3B / Qwen2.5-VL 4-bit) и манипуляцию интерфейсом.
Работает в изолированном фоновом процессе (Worker Process) для предотвращения конфликтов CUDA DLL и утечек VRAM.
"""

import ctypes
import json
import multiprocessing as mp
import os
import queue
import re
import sys
import time
import traceback
from dataclasses import dataclass, field
from multiprocessing.synchronize import Event as EventType
from PIL import Image
from core.screen_tools import POINT

# Системный промпт для Computer-Use в Windows 11
def build_computer_use_prompt(width: int = 1920, height: int = 1080) -> str:
    """Генерирует системный промпт для Computer-Use с точным разрешением входного изображения."""
    return f"""You are Jarvis, an autonomous Computer-Use AI agent running locally on Windows 11.
Your task is to accomplish the user's goal by looking at the desktop screenshot and deciding the next action.
The screen screenshot resolution is {width}x{height}.

Output your next action in strict JSON format inside a ```json ``` block with these keys:
- "thought": A brief explanation in Russian of what you see and what you will do.
- "action": One of ["click", "double_click", "right_click", "type", "press", "hotkey", "scroll", "wait", "ask_confirmation", "finish"]
- "coordinate": [x, y] pixel coordinates on the {width}x{height} image (x: 0..{width}, y: 0..{height}) to click directly on the center of the target element.
- "text": string to type (for "type" action).
- "press_enter": boolean, whether to press Enter after typing.
- "key": string key name for "press" (e.g. "enter", "esc", "tab", "backspace").
- "keys": array of keys for "hotkey" (e.g. ["ctrl", "t"], ["win", "d"], ["ctrl", "w"]).
- "direction": "down" or "up" for "scroll" action.
- "message": final summary in Russian for "finish" or question for "ask_confirmation".

Rules:
1. Always look for icons, buttons, search bars, or input fields matching the user request.
2. If the desired application or file is on the desktop, use "double_click" on its icon to launch it.
3. If an application is on the taskbar, start menu, or browser, a single "click" is sufficient.
4. When clicking an icon or button, provide the coordinate [x, y] at the visual center of the element.
5. If you need to search, first click the search field, then type the query.
6. If the task is completed (e.g. the window is open and active), return action "finish".
7. For dangerous actions (deleting files, modifying system registry), return action "ask_confirmation".
"""

COMPUTER_USE_SYSTEM_PROMPT = build_computer_use_prompt(1920, 1080)


@dataclass
class VisionAction:
    """Структурированное действие модели."""
    thought: str = ""
    action_type: str = "wait"
    coordinate: tuple[int, int] | None = None  # [x, y] в диапазоне 0..1000
    text: str = ""
    press_enter: bool = False
    key: str = ""
    keys: list[str] = field(default_factory=list)
    direction: str = "down"
    message: str = ""
    raw_response: str = ""


class ActionParser:
    """Парсер ответов модели в структурированные команды управления."""

    @classmethod
    def _repair_and_parse_json(cls, text: str) -> dict | None:
        """Многоуровневый алгоритм восстановления и парсинга поврежденного JSON от LLM."""
        if not text or not isinstance(text, str):
            return None

        # 1. Попытка прямого разбора сырого текста
        try:
            res = json.loads(text.strip())
            if isinstance(res, dict):
                return res
        except Exception:
            pass

        # 2. Извлечение содержимого блока markdown ```json ... ```
        md_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if md_match:
            try:
                res = json.loads(md_match.group(1).strip())
                if isinstance(res, dict):
                    return res
            except Exception:
                text = md_match.group(1)

        # 3. Выделение самого внешнего блока { ... }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace == -1:
            return None

        if last_brace > first_brace:
            candidate = text[first_brace : last_brace + 1].strip()
        else:
            # Отрезанный конец (missing closing brace)
            candidate = text[first_brace:].strip() + "}"

        # 4. Попытка разобрать кандидат как есть
        try:
            res = json.loads(candidate)
            if isinstance(res, dict):
                return res
        except Exception:
            pass

        # 5. Очистка завершающих запятых перед } или ] (trailing commas)
        cleaned = re.sub(r",\s*([\}\]])", r"\1", candidate)
        try:
            res = json.loads(cleaned)
            if isinstance(res, dict):
                return res
        except Exception:
            pass

        # 6. Попытка через ast.literal_eval (если модель выдала одинарные кавычки Python dict)
        try:
            import ast
            res = ast.literal_eval(cleaned)
            if isinstance(res, dict):
                return res
        except Exception:
            pass

        # 7. Замена одинарных кавычек вокруг ключей и строковых значений на двойные
        try:
            fixed_quotes = re.sub(r"(?<=[\{\s,])'([a-zA-Z0-9_]+)':", r'"\1":', cleaned)
            res = json.loads(fixed_quotes)
            if isinstance(res, dict):
                return res
        except Exception:
            pass

        # 8. Точечное извлечение полей по регулярным выражениям (regex fallback)
        data: dict = {}
        for key in ("thought", "action", "text", "key", "direction", "message"):
            m = re.search(rf'"{key}"\s*:\s*"((?:\\.|[^"\\])*?)"(?=\s*[,}}])', candidate)
            if not m:
                m = re.search(rf'"{key}"\s*:\s*"(.*?)"(?=\s*,\s*"[a-zA-Z0-9_]+"\s*:|\s*\}})', candidate, re.DOTALL)
            if not m:
                m = re.search(rf"'{key}'\s*:\s*'((?:\\.|[^'\\])*?)'(?=\s*[,}}])", candidate)
            if m:
                data[key] = m.group(1).replace('\\"', '"').replace("\\'", "'")

        coord_m = re.search(r'["\']coordinate["\']\s*:\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]', candidate)
        if coord_m:
            data["coordinate"] = [int(coord_m.group(1)), int(coord_m.group(2))]

        pe_m = re.search(r'["\']press_enter["\']\s*:\s*(true|false)', candidate, re.IGNORECASE)
        if pe_m:
            data["press_enter"] = pe_m.group(1).lower() == "true"

        keys_m = re.search(r'["\']keys["\']\s*:\s*\[(.*?)\]', candidate, re.DOTALL)
        if keys_m:
            data["keys"] = [k.strip(' "\'') for k in keys_m.group(1).split(",") if k.strip(' "\'')]

        if data.get("action") or data.get("thought") or data.get("coordinate"):
            return data

        return None

    @classmethod
    def parse(cls, response_text: str) -> VisionAction:
        """Извлекает и валидирует JSON-действие из ответа модели."""
        if not response_text or not response_text.strip():
            return VisionAction(
                thought="Пустой ответ",
                action_type="error",
                message="Ответ от модели не получен"
            )

        data = cls._repair_and_parse_json(response_text)
        if not data:
            return VisionAction(
                thought="Синтаксическая ошибка в JSON",
                action_type="error",
                message="Ошибка декодирования команды",
                raw_response=response_text
            )

        thought = str(data.get("thought", ""))
        action_type = str(data.get("action", "")).lower().strip()
        alias_map = {
            "left_click": "click",
            "leftclick": "click",
            "left-click": "click",
            "single_click": "click",
            "rightclick": "right_click",
            "right-click": "right_click",
            "doubleclick": "double_click",
            "double-click": "double_click",
            "write": "type",
            "input": "type",
            "input_text": "type",
            "done": "finish",
            "complete": "finish",
            "completed": "finish",
            "terminate": "finish",
            "exit": "finish",
        }
        action_type = alias_map.get(action_type, action_type)
        message = str(data.get("message", ""))
        text = str(data.get("text", ""))
        press_enter = bool(data.get("press_enter", False))
        key = str(data.get("key", "")).lower().strip()
        keys_val = data.get("keys", [])
        keys = [str(k).lower().strip() for k in keys_val] if isinstance(keys_val, list) else []
        direction = str(data.get("direction", "down")).lower().strip()

        coord: tuple[int, int] | None = None
        raw_coord = data.get("coordinate")
        if isinstance(raw_coord, (list, tuple)) and len(raw_coord) >= 2:
            try:
                x = int(raw_coord[0])
                y = int(raw_coord[1])
                coord = (x, y)
            except (ValueError, TypeError):
                coord = None

        # Эвристика восстановления действия при отсутствии поля 'action'
        if not action_type or action_type == "wait":
            if coord is not None:
                action_type = "click"
            elif text:
                action_type = "type"
            elif key:
                action_type = "press"
            elif keys:
                action_type = "hotkey"
            elif not action_type:
                action_type = "wait"

        return VisionAction(
            thought=thought,
            action_type=action_type,
            coordinate=coord,
            text=text,
            press_enter=press_enter,
            key=key,
            keys=keys,
            direction=direction,
            message=message,
            raw_response=response_text
        )

    @staticmethod
    def is_dangerous_hotkey(keys: list[str]) -> bool:
        """Проверяет сочетание клавиш на наличие в черном списке деструктивных команд Windows."""
        if not keys:
            return False
        dangerous_combos = {("shift", "delete"), ("win", "r"), ("ctrl", "alt", "delete")}
        alias_map = {"windows": "win", "control": "ctrl", "del": "delete"}
        keys_normalized = set(alias_map.get(k.lower().strip(), k.lower().strip()) for k in keys)
        return any(all(k in keys_normalized for k in combo) for combo in dangerous_combos)

    @staticmethod
    def is_dangerous_command_text(text: str) -> bool:
        """Проверяет вводимый текст на наличие деструктивных команд ОС."""
        if not text:
            return False
        clean = text.strip()
        patterns = [
            r'(?i)\b(?:format|diskpart|bcdedit)\b',
            r'(?i)\b(?:del|rmdir|rd)\s+.*\/s\b',
            r'(?i)\b(?:Remove-Item|ri|rm|del)\s+.*-(?:Recurse|r)\b',
            r'(?i)\b(?:reg\s+(?:delete|add)|regedit)\b',
            r'(?i)\b(?:shutdown|restart-computer|stop-computer)\b',
            r'(?i)\b(?:vssadmin\s+delete\s+shadows)\b',
            r'(?i)\b(?:powershell|cmd)\.exe\s+.*-(?:enc|encodedcommand|c|command)\b',
        ]
        return any(bool(re.search(pat, clean)) for pat in patterns)


class FailSafeMonitor:
    """Контроллер экстренной остановки агента при вмешательстве пользователя."""

    def __init__(self) -> None:
        self.user32 = ctypes.windll.user32
        self._last_cursor_pos: tuple[int, int] | None = None

    def get_cursor_position(self) -> tuple[int, int]:
        """Возвращает текущие экранные координаты курсора мыши."""
        pt = POINT()
        self.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def update_known_position(self, x: int, y: int) -> None:
        """Запоминает координаты, куда агент сам переместил курсор."""
        self._last_cursor_pos = (x, y)

    def is_interrupted(self) -> tuple[bool, str]:
        """
        Проверяет, нажал ли пользователь клавишу ESC или физически дернул мышь.
        """
        # 1. Проверка нажатия ESC (VK_ESCAPE = 0x1B)
        if self.user32.GetAsyncKeyState(0x1B) & 0x8000:
            return True, "Прервано пользователем (клавиша ESC)"

        # 2. Проверка физического движения мыши
        if self._last_cursor_pos is not None:
            curr_x, curr_y = self.get_cursor_position()
            prev_x, prev_y = self._last_cursor_pos
            distance = ((curr_x - prev_x) ** 2 + (curr_y - prev_y) ** 2) ** 0.5
            if distance > 40:  # Порог движения 40 пикселей
                return True, "Прервано пользователем (движение мыши)"

        return False, ""


def _worker_process_loop(
    task_queue: mp.Queue,
    status_queue: mp.Queue,
    model_name: str,
    stop_event: EventType,
    cancel_event: EventType | None = None,
    fallback_model: str = "Qwen/Qwen2.5-VL-3B-Instruct"
) -> None:
    """
    Основной цикл изолированного рабочего процесса Vision-агента.
    Выполняется в отдельном адресном пространстве процесса Windows.
    """
    try:
        # На Windows гарантируем изоляцию и согласованную загрузку CUDA/cuDNN для PyTorch
        if sys.platform == "win32":
            torch_lib = os.path.join(sys.prefix, "Lib", "site-packages", "torch", "lib")
            if os.path.exists(torch_lib):
                try:
                    os.add_dll_directory(torch_lib)
                except Exception as dll_dir_err:
                    print(f"[VisionWorker] Предупреждение add_dll_directory: {dll_dir_err}", file=sys.stderr)

                # Исключаем сторонние версии cublas/cudnn/ctranslate2 из PATH воркера и ставим torch/lib в приоритет
                current_paths = os.environ.get("PATH", "").split(os.pathsep)
                filtered_paths = [
                    p for p in current_paths
                    if not any(k in p.lower() for k in ("nvidia\\cudnn", "nvidia/cudnn", "nvidia\\cublas", "nvidia/cublas", "ctranslate2"))
                ]
                os.environ["PATH"] = os.pathsep.join([torch_lib] + filtered_paths)

                # Предварительно загружаем зависимости в топологическом порядке
                import ctypes
                kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
                kernel32.LoadLibraryExW.restype = ctypes.c_void_p

                # 1. cuBLAS и CUDA Runtime
                for dll_name in ("cublasLt64_12.dll", "cublas64_12.dll", "cudart64_12.dll"):
                    dll_file = os.path.join(torch_lib, dll_name)
                    if os.path.exists(dll_file):
                        kernel32.LoadLibraryExW(dll_file, None, 0x00001100)

                # 2. cuDNN библиотеки
                for dll_name in (
                    "cudnn_ops64_9.dll", "cudnn_graph64_9.dll", "cudnn_adv64_9.dll",
                    "cudnn64_9.dll", "cudnn_cnn64_9.dll"
                ):
                    dll_file = os.path.join(torch_lib, dll_name)
                    if os.path.exists(dll_file):
                        kernel32.LoadLibraryExW(dll_file, None, 0x00001100)

        import torch
        from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration
        from core.screen_tools import ScreenController

        screen = ScreenController()
        failsafe = FailSafeMonitor()

        device = "cuda" if torch.cuda.is_available() else "cpu"
        # 4-битная квантизация BitsAndBytes NF4 (доступна только при наличии CUDA)
        quant_config = (
            BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True
            )
            if torch.cuda.is_available()
            else None
        )

        import transformers.utils.logging as hf_logging

        def _make_progress_hook(queue_target):
            last_reported_pct = -1
            def hook(factory, args, kwargs):
                bar = factory(*args, **kwargs)
                orig_update = getattr(bar, "update", None)
                if not callable(orig_update):
                    return bar
                desc = kwargs.get("desc", "Загрузка весов...")

                def update(n=1):
                    nonlocal last_reported_pct
                    res = orig_update(n)
                    try:
                        tot = getattr(bar, "total", 0)
                        cur = getattr(bar, "n", 0)
                        if tot and tot > 0:
                            pct = min(100, max(0, int((cur / tot) * 100)))
                            if pct != last_reported_pct:
                                last_reported_pct = pct
                                queue_target.put({
                                    "type": "loading_progress",
                                    "progress": pct,
                                    "desc": desc,
                                    "current": cur,
                                    "total": tot
                                })
                    except Exception:
                        pass
                    return res

                bar.update = update
                return bar
            return hook

        model = None
        processor = None
        candidates = [model_name]
        if fallback_model and fallback_model != model_name:
            candidates.append(fallback_model)

        for candidate in candidates:
            status_queue.put({"type": "log", "message": f"Загрузка модели {candidate} в 4-битном режиме (NF4)..."})
            status_queue.put({"type": "loading_progress", "progress": 0, "desc": "Подготовка модели..."})
            hook_fn = _make_progress_hook(status_queue)
            prev_hook = hf_logging.set_tqdm_hook(hook_fn)
            try:
                try:
                    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                        candidate,
                        quantization_config=quant_config,
                        device_map="auto",
                        torch_dtype=torch.float16,
                        low_cpu_mem_usage=True,
                        local_files_only=True
                    )
                    processor = AutoProcessor.from_pretrained(candidate, local_files_only=True)
                except Exception:
                    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                        candidate,
                        quantization_config=quant_config,
                        device_map="auto",
                        torch_dtype=torch.float16,
                        low_cpu_mem_usage=True
                    )
                    processor = AutoProcessor.from_pretrained(candidate)

                status_queue.put({"type": "loading_progress", "progress": 100, "desc": "Загрузка завершена"})
                status_queue.put({"type": "ready", "message": f"Vision-модель {candidate} готова к работе"})
                break
            except Exception as e:
                status_queue.put({"type": "log", "message": f"Не удалось загрузить {candidate}: {e}"})
            finally:
                hf_logging.set_tqdm_hook(prev_hook)

        if model is None or processor is None:
            status_queue.put({"type": "error", "message": "Ошибка: не удалось загрузить ни основную, ни резервную модель"})
            return

        try:
            while not stop_event.is_set():
                try:
                    task = task_queue.get(timeout=0.5)
                except Exception:
                    continue

                if task.get("type") == "stop":
                    break

                if task.get("type") != "execute":
                    continue

                if cancel_event is not None:
                    cancel_event.clear()

                prompt = task.get("prompt", "")
                max_steps = task.get("max_steps", 8)
                history: list[str] = []
                prev_image: Image.Image | None = None

                status_queue.put({"type": "task_started", "prompt": prompt})

                task_success = False
                final_message = ""
                was_interrupted = False
                consecutive_parse_errors = 0

                for step in range(1, max_steps + 1):
                    if stop_event.is_set():
                        final_message = "Задача остановлена"
                        was_interrupted = True
                        break

                    if cancel_event is not None and cancel_event.is_set():
                        status_queue.put({"type": "interrupted", "reason": "Задача отменена пользователем"})
                        final_message = "Задача отменена пользователем"
                        was_interrupted = True
                        break

                    # 1. Проверка прерывания
                    interrupted, reason = failsafe.is_interrupted()
                    if interrupted:
                        status_queue.put({"type": "interrupted", "reason": reason})
                        final_message = reason
                        was_interrupted = True
                        break

                    # 2. Захват экрана
                    status_queue.put({"type": "step_status", "step": step, "status": "Захват экрана..."})
                    image = screen.capture_screen()

                    # Детекция изменений экрана после предыдущего действия
                    screen_changed = True
                    if prev_image is not None and prev_image.size == image.size:
                        try:
                            p1 = prev_image.resize((64, 64), Image.Resampling.NEAREST).convert("L")
                            p2 = image.resize((64, 64), Image.Resampling.NEAREST).convert("L")
                            diff = sum(abs(a - b) for a, b in zip(p1.getdata(), p2.getdata()))
                            avg_diff = diff / (64 * 64)
                            if avg_diff < 1.5:  # Среднее изменение яркости пикселей менее 1.5 из 255 (~0.6% от максимума)
                                screen_changed = False
                        except Exception as diff_err:
                            print(f"[VisionWorker] Предупреждение вычисления разницы скриншотов: {diff_err}", file=sys.stderr)

                    prev_image = image

                    # Оптимизация разрешения: ограничение ширины до 1280px с кратностью 28x28 для патчей ViT.
                    # Это уменьшает число визуальных токенов с ~2600 до ~1100, ускоряя инференс модели в 2.5-3 раза.
                    orig_w, orig_h = image.size
                    max_w = 1280
                    if orig_w > max_w:
                        scale = max_w / orig_w
                        target_w = max(28, (int(orig_w * scale) // 28) * 28)
                        target_h = max(28, (int(orig_h * scale) // 28) * 28)
                    else:
                        target_w = max(28, (orig_w // 28) * 28)
                        target_h = max(28, (orig_h // 28) * 28)

                    if target_w != orig_w or target_h != orig_h:
                        image = image.resize((target_w, target_h), Image.Resampling.BILINEAR)

                    # 3. Формирование контекста и вывод модели
                    status_queue.put({"type": "step_status", "step": step, "status": "Анализ интерфейса нейросетью..."})

                    history_str = "\n".join(f"Шаг {i+1}: {h}" for i, h in enumerate(history[-3:]))
                    user_content = f"Цель пользователя: {prompt}\n"
                    if history_str:
                        user_content += f"Предыдущие выполненные действия:\n{history_str}\n"
                    if not screen_changed and step > 1:
                        user_content += "Внимание: после предыдущего шага экран не изменился. Элемент мог не сработать или быть перекрыт всплывающим окном/баннером. Закрой помеху или повтори действие точнее.\n"
                    user_content += "Определи следующее действие в формате JSON."

                    messages = [
                        {"role": "system", "content": build_computer_use_prompt(target_w, target_h)},
                        {
                            "role": "user",
                            "content": [
                                {"type": "image", "image": image},
                                {"type": "text", "text": user_content}
                            ]
                        }
                    ]

                    try:
                        text_input = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                        inputs = processor(
                            text=[text_input],
                            images=[image],
                            padding=True,
                            return_tensors="pt"
                        ).to(device)

                        with torch.inference_mode():
                            generated_ids = model.generate(
                                **inputs,
                                max_new_tokens=128,
                                do_sample=False
                            )

                        generated_ids_trimmed = [
                            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
                        ]
                        output_text = processor.batch_decode(
                            generated_ids_trimmed,
                            skip_special_tokens=True,
                            clean_up_tokenization_spaces=False
                        )[0]
                    except Exception as e:
                        status_queue.put({"type": "error", "message": f"Ошибка генерации модели: {e}"})
                        final_message = f"Ошибка инференса: {e}"
                        break

                    action = ActionParser.parse(output_text)
                    history.append(f"{action.action_type}: {action.thought}")

                    status_queue.put({
                        "type": "action_decided",
                        "step": step,
                        "thought": action.thought,
                        "action": action.action_type,
                        "coordinate": action.coordinate,
                        "message": action.message
                    })

                    # 4. Обработка завершения, ошибок или подтверждения
                    if action.action_type == "finish":
                        task_success = True
                        final_message = action.message or "Задача успешно выполнена"
                        break

                    if action.action_type == "error":
                        consecutive_parse_errors += 1
                        if consecutive_parse_errors < 2 and step < max_steps:
                            status_queue.put({
                                "type": "step_status",
                                "step": step,
                                "status": "Повтор запроса (ошибка формата JSON)..."
                            })
                            history.append(
                                "Системное предупреждение: предыдущий ответ содержал ошибку формата JSON. "
                                "Сформируй ответ СТРОГО в виде валидного JSON-объекта: "
                                '{"thought": "...", "action": "click", "coordinate": [x, y]}'
                            )
                            continue
                        else:
                            task_success = False
                            final_message = f"Ошибка формата команды модели: {action.message or action.thought}"
                            break

                    consecutive_parse_errors = 0

                    if action.action_type == "ask_confirmation":
                        status_queue.put({"type": "confirmation_requested", "message": action.message})
                        final_message = f"Требуется подтверждение: {action.message}"
                        break

                    # 5. Выполнение физического действия через Win32 API
                    if action.action_type in ("click", "double_click", "right_click") and action.coordinate:
                        norm_x, norm_y = action.coordinate
                        screen_x, screen_y = screen.denormalize_coordinate(
                            norm_x=norm_x, norm_y=norm_y, image_size=(target_w, target_h)
                        )
                        failsafe.update_known_position(screen_x, screen_y)

                        status_queue.put({
                            "type": "click_performed",
                            "x": screen_x,
                            "y": screen_y,
                            "button": action.action_type
                        })

                        if action.action_type == "click":
                            screen.click(screen_x, screen_y)
                        elif action.action_type == "double_click":
                            screen.double_click(screen_x, screen_y)
                        elif action.action_type == "right_click":
                            screen.click(screen_x, screen_y, button="right")

                    elif action.action_type == "type":
                        # Программные guardrails: блокировка деструктивных системных команд
                        if action.press_enter and ActionParser.is_dangerous_command_text(action.text):
                            blocked_str = action.text.strip()
                            status_queue.put({
                                "type": "confirmation_requested",
                                "message": f"Блокировка ввода потенциально опасной команды: «{blocked_str}»"
                            })
                            final_message = f"Опасный ввод команды отклонен: {blocked_str}"
                            break
                        screen.type_text(action.text, press_enter=action.press_enter)

                    elif action.action_type == "press" and action.key:
                        screen.send_key(action.key)

                    elif action.action_type == "hotkey" and action.keys:
                        # Программные guardrails: предотвращение деструктивных шорткатов
                        if ActionParser.is_dangerous_hotkey(action.keys):
                            blocked_str = " + ".join(action.keys)
                            status_queue.put({
                                "type": "confirmation_requested",
                                "message": f"Блокировка потенциально опасного сочетания клавиш: {blocked_str}"
                            })
                            final_message = f"Опасное действие отклонено: {blocked_str}"
                            break
                        screen.hotkey(action.keys)

                    elif action.action_type == "scroll":
                        screen.scroll(direction=action.direction, amount=3)

                    # Короткая пауза для отрисовки интерфейса Windows
                    time.sleep(0.3)

                if not was_interrupted:
                    status_queue.put({
                        "type": "task_completed",
                        "success": task_success,
                        "message": final_message or "Достигнут лимит шагов"
                    })

        finally:
            # Гарантированная выгрузка модели и освобождение VRAM при остановке или сбое
            if model is not None:
                del model
            if processor is not None:
                del processor
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            try:
                status_queue.close()
            except Exception:
                pass
            try:
                task_queue.close()
            except Exception:
                pass

    except Exception as e:
        tb = traceback.format_exc()
        try:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, "vision_worker.log"), "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Сбой воркера Vision-агента: {e}\n{tb}\n")
        except Exception as log_err:
            print(f"[VisionWorker] Не удалось записать лог сбоя: {log_err}", file=sys.stderr)
        try:
            status_queue.put_nowait({"type": "error", "message": f"Сбой воркера Vision-агента: {e}"})
        except Exception as queue_err:
            print(f"[VisionWorker] Не удалось отправить статус ошибки: {queue_err}", file=sys.stderr)


class VisionAgentProcessManager:
    """Менеджер жизненного цикла изолированного рабочего процесса Vision-агента."""

    def __init__(
        self,
        model_name: str = "xlangai/Jedi-3B-1080p",
        fallback_model: str = "Qwen/Qwen2.5-VL-3B-Instruct"
    ) -> None:
        self.model_name = model_name
        self.fallback_model = fallback_model
        self._process: mp.Process | None = None
        self._task_queue: mp.Queue | None = None
        self._status_queue: mp.Queue | None = None
        self._stop_event: EventType | None = None
        self._cancel_event: EventType | None = None
        self._is_ready: bool = False
        self._is_busy: bool = False
        self._start_time: float | None = None
        self._startup_timeout: float = 120.0

    def is_running(self) -> bool:
        """Проверяет, запущен ли рабочий процесс."""
        return self._process is not None and self._process.is_alive()

    def is_ready(self) -> bool:
        """Готова ли модель к инференсу."""
        return self.is_running() and self._is_ready

    def is_loading(self) -> bool:
        """Загружается ли модель в память GPU в данный момент."""
        return self.is_running() and not self._is_ready

    def is_busy(self) -> bool:
        """Выполняет ли агент задачу в интерфейсе в данный момент."""
        return self._is_busy

    def start(self) -> bool:
        """Запускает изолированный фоновый процесс с моделью."""
        if self.is_running():
            return True

        self._task_queue = mp.Queue()
        self._status_queue = mp.Queue()
        self._stop_event = mp.Event()
        self._cancel_event = mp.Event()
        self._is_ready = False
        self._is_busy = False
        self._start_time = time.time()

        self._process = mp.Process(
            target=_worker_process_loop,
            args=(self._task_queue, self._status_queue, self.model_name, self._stop_event, self._cancel_event, self.fallback_model),
            daemon=True
        )
        self._process.start()
        return True

    def stop(self) -> None:
        """Полная остановка процесса и гарантированное освобождение VRAM."""
        if self._cancel_event is not None:
            self._cancel_event.set()

        if self._stop_event is not None:
            self._stop_event.set()

        if self._task_queue is not None:
            try:
                self._task_queue.put({"type": "stop"}, timeout=0.5)
            except Exception as e:
                print(f"[VisionAgentManager Stop Error] {e}", file=sys.stderr)

        if self._process is not None and self._process.is_alive():
            self._process.join(timeout=4.0)
            if self._process.is_alive():
                self._process.terminate()

        if self._task_queue is not None:
            try:
                self._task_queue.cancel_join_thread()
                self._task_queue.close()
            except Exception:
                pass

        if self._status_queue is not None:
            try:
                self._status_queue.cancel_join_thread()
                self._status_queue.close()
            except Exception:
                pass

        self._process = None
        self._task_queue = None
        self._status_queue = None
        self._stop_event = None
        self._cancel_event = None
        self._is_ready = False
        self._is_busy = False
        self._start_time = None

    def abort_task(self) -> None:
        """Экстренно прерывает выполнение текущей задачи агента без остановки рабочего процесса."""
        self._is_busy = False
        if self._cancel_event is not None:
            self._cancel_event.set()

    def poll_status(self) -> list[dict[str, str | bool | int | float | None]]:
        """Опрашивает очередь обновлений статуса от рабочего процесса."""
        events: list[dict[str, str | bool | int | float | None]] = []
        if self._status_queue is None:
            return events

        while True:
            try:
                ev = self._status_queue.get_nowait()
                ev_type = ev.get("type")
                if ev_type == "ready":
                    self._is_ready = True
                    self._start_time = None
                elif ev_type in ("task_completed", "interrupted", "error"):
                    self._is_busy = False
                    if ev_type == "error" and not self._is_ready:
                        self._start_time = None
                events.append(ev)
            except queue.Empty:
                break
            except Exception as e:
                print(f"[VisionAgentManager Poll Error] {e}", file=sys.stderr)
                break

        # Защитный таймаут ожидания готовности воркера (ARCH-3)
        if not self._is_ready and self._start_time is not None:
            if time.time() - self._start_time > self._startup_timeout:
                events.append({
                    "type": "error",
                    "message": "Превышен таймаут загрузки Vision-модели (120 сек)"
                })
                self._start_time = None
                self._is_busy = False
                self.stop()

        # Детекция аварийного завершения процесса воркера (CUDA OOM / сбой драйвера)
        if self._is_busy and not self.is_running():
            self._is_busy = False
            events.append({
                "type": "error",
                "message": "Фоновый процесс Vision-агента неожиданно завершился (сбой GPU или памяти)"
            })

        return events

    def execute_task(self, prompt: str, max_steps: int = 8) -> bool:
        """Отправляет задачу на исполнение рабочему процессу."""
        if not self.is_running() or self._task_queue is None:
            return False

        self._is_busy = True
        self._task_queue.put({
            "type": "execute",
            "prompt": prompt,
            "max_steps": max_steps
        })
        return True
