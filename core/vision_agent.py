"""
Мультимодальный автономный агент компьютерного управления (Vision Computer-Use Agent).
Обеспечивает зрение (GDI BitBlt), рассуждение (Jedi-3B / Qwen2.5-VL 4-bit) и манипуляцию интерфейсом.
Работает в изолированном фоновом процессе (Worker Process) для предотвращения конфликтов CUDA DLL и утечек VRAM.
"""

import ctypes
import json
import multiprocessing as mp
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from PIL import Image

# Системный промпт для Computer-Use в Windows 11
COMPUTER_USE_SYSTEM_PROMPT = """You are Jarvis, an autonomous Computer-Use AI agent running locally on Windows 11.
Your task is to accomplish the user's goal by looking at the desktop screenshot and deciding the next action.

Output your next action in strict JSON format inside a ```json ``` block with these keys:
- "thought": A brief explanation in Russian of what you see and what you will do.
- "action": One of ["click", "double_click", "right_click", "type", "press", "hotkey", "scroll", "wait", "ask_confirmation", "finish"]
- "coordinate": [y, x] in range 0..1000 (relative to the full screen) for click/double_click/right_click actions.
- "text": string to type (for "type" action).
- "press_enter": boolean, whether to press Enter after typing.
- "key": string key name for "press" (e.g. "enter", "esc", "tab", "backspace").
- "keys": array of keys for "hotkey" (e.g. ["ctrl", "t"], ["win", "d"], ["ctrl", "w"]).
- "direction": "down" or "up" for "scroll" action.
- "message": final summary in Russian for "finish" or question for "ask_confirmation".

Rules:
1. Always look for search bars, icons, buttons, or input fields matching the user request.
2. If the desired application or browser is visible on the screen or taskbar, click on it.
3. If you need to search, first click the search field, then type the query.
4. If the task is completed (e.g. the video started playing, or the window is open), return action "finish".
5. For dangerous actions (deleting files, sending personal chat messages), return action "ask_confirmation".
"""


@dataclass
class VisionAction:
    """Структурированное действие модели."""
    thought: str = ""
    action_type: str = "wait"
    coordinate: Optional[Tuple[int, int]] = None  # [y, x] в диапазоне 0..1000
    text: str = ""
    press_enter: bool = False
    key: str = ""
    keys: List[str] = field(default_factory=list)
    direction: str = "down"
    message: str = ""
    raw_response: str = ""


class ActionParser:
    """Парсер ответов модели в структурированные команды управления."""

    @staticmethod
    def parse(response_text: str) -> VisionAction:
        """Извлекает и валидирует JSON-действие из ответа модели."""
        if not response_text:
            return VisionAction(thought="Пустой ответ", action_type="finish", message="Ответ от модели не получен")

        # Извлечение JSON из markdown-блока ```json ... ``` или сырого текста
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        raw_json = json_match.group(1) if json_match else None

        if not raw_json:
            # Поиск первого сбалансированного JSON-объекта
            bracket_match = re.search(r"(\{.*\})", response_text, re.DOTALL)
            raw_json = bracket_match.group(1) if bracket_match else None

        if not raw_json:
            return VisionAction(
                thought="Не удалось распознать JSON",
                action_type="finish",
                message=response_text[:150],
                raw_response=response_text
            )

        try:
            data = json.loads(raw_json)
        except Exception:
            return VisionAction(
                thought="Синтаксическая ошибка в JSON",
                action_type="finish",
                message="Ошибка декодирования команды",
                raw_response=response_text
            )

        thought = str(data.get("thought", ""))
        action_type = str(data.get("action", "wait")).lower().strip()
        message = str(data.get("message", ""))
        text = str(data.get("text", ""))
        press_enter = bool(data.get("press_enter", False))
        key = str(data.get("key", "")).lower().strip()
        keys_val = data.get("keys", [])
        keys = [str(k).lower().strip() for k in keys_val] if isinstance(keys_val, list) else []
        direction = str(data.get("direction", "down")).lower().strip()

        coord: Optional[Tuple[int, int]] = None
        raw_coord = data.get("coordinate")
        if isinstance(raw_coord, (list, tuple)) and len(raw_coord) >= 2:
            try:
                y = int(raw_coord[0])
                x = int(raw_coord[1])
                coord = (y, x)
            except (ValueError, TypeError):
                coord = None

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


class FailSafeMonitor:
    """Контроллер экстренной остановки агента при вмешательстве пользователя."""

    def __init__(self) -> None:
        self.user32 = ctypes.windll.user32
        self._last_cursor_pos: Optional[Tuple[int, int]] = None

    def get_cursor_position(self) -> Tuple[int, int]:
        """Возвращает текущие экранные координаты курсора мыши."""
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pt = POINT()
        self.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def update_known_position(self, x: int, y: int) -> None:
        """Запоминает координаты, куда агент сам переместил курсор."""
        self._last_cursor_pos = (x, y)

    def is_interrupted(self) -> Tuple[bool, str]:
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
    stop_event: Any,
    fallback_model: str = "Qwen/Qwen2.5-VL-3B-Instruct"
) -> None:
    """
    Основной цикл изолированного рабочего процесса Vision-агента.
    Выполняется в отдельном адресном пространстве процесса Windows.
    """
    import torch
    from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration
    from core.screen_tools import ScreenController

    screen = ScreenController()
    failsafe = FailSafeMonitor()

    # 4-битная квантизация BitsAndBytes NF4
    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True
    )

    model = None
    processor = None
    candidates = [model_name]
    if fallback_model and fallback_model != model_name:
        candidates.append(fallback_model)

    for candidate in candidates:
        status_queue.put({"type": "log", "message": f"Загрузка модели {candidate} в 4-битном режиме (NF4)..."})
        try:
            model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                candidate,
                quantization_config=quant_config,
                device_map="auto",
                torch_dtype=torch.float16,
                low_cpu_mem_usage=True
            )
            processor = AutoProcessor.from_pretrained(candidate)
            status_queue.put({"type": "ready", "message": f"Vision-модель {candidate} готова к работе"})
            break
        except Exception as e:
            status_queue.put({"type": "log", "message": f"Не удалось загрузить {candidate}: {e}"})

    if model is None or processor is None:
        status_queue.put({"type": "error", "message": "Ошибка: не удалось загрузить ни основную, ни резервную модель"})
        return

    while not stop_event.is_set():
        try:
            task = task_queue.get(timeout=0.5)
        except Exception:
            continue

        if task.get("type") == "stop":
            break

        if task.get("type") != "execute":
            continue

        prompt = task.get("prompt", "")
        max_steps = task.get("max_steps", 8)
        history: List[str] = []

        status_queue.put({"type": "task_started", "prompt": prompt})

        task_success = False
        final_message = ""

        for step in range(1, max_steps + 1):
            if stop_event.is_set():
                final_message = "Задача остановлена"
                break

            # 1. Проверка прерывания
            interrupted, reason = failsafe.is_interrupted()
            if interrupted:
                status_queue.put({"type": "interrupted", "reason": reason})
                final_message = reason
                break

            # 2. Захват экрана
            status_queue.put({"type": "step_status", "step": step, "status": "Захват экрана..."})
            image = screen.capture_screen()

            # Ресайз под динамическую сетку (кратно 28x28)
            img_w, img_h = image.size
            target_w = (img_w // 28) * 28
            target_h = (img_h // 28) * 28
            if target_w != img_w or target_h != img_h:
                image = image.resize((target_w, target_h), Image.Resampling.LANCZOS)

            # 3. Формирование контекста и вывод модели
            status_queue.put({"type": "step_status", "step": step, "status": "Анализ интерфейса нейросетью..."})

            history_str = "\n".join(f"Шаг {i+1}: {h}" for i, h in enumerate(history[-3:]))
            user_content = f"Цель пользователя: {prompt}\n"
            if history_str:
                user_content += f"Предыдущие выполненные действия:\n{history_str}\n"
            user_content += "Определи следующее действие в формате JSON."

            messages = [
                {"role": "system", "content": COMPUTER_USE_SYSTEM_PROMPT},
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
                ).to("cuda")

                with torch.inference_mode():
                    generated_ids = model.generate(
                        **inputs,
                        max_new_tokens=256,
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

            # 4. Обработка завершения или подтверждения
            if action.action_type == "finish":
                task_success = True
                final_message = action.message or "Задача успешно выполнена"
                break

            if action.action_type == "ask_confirmation":
                status_queue.put({"type": "confirmation_requested", "message": action.message})
                final_message = f"Требуется подтверждение: {action.message}"
                break

            # 5. Выполнение физического действия через Win32 API
            if action.action_type in ("click", "double_click", "right_click") and action.coordinate:
                norm_y, norm_x = action.coordinate
                screen_x, screen_y = screen.denormalize_coordinate(norm_y=norm_y, norm_x=norm_x)
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
                screen.type_text(action.text, press_enter=action.press_enter)

            elif action.action_type == "press" and action.key:
                screen.send_key(action.key)

            elif action.action_type == "hotkey" and action.keys:
                screen.hotkey(action.keys)

            elif action.action_type == "scroll":
                screen.scroll(direction=action.direction, amount=3)

            # Короткая пауза для отрисовки интерфейса Windows
            time.sleep(0.3)

        status_queue.put({
            "type": "task_completed",
            "success": task_success,
            "message": final_message or "Достигнут лимит шагов"
        })

    # Выгрузка при остановке
    del model
    del processor
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


class VisionAgentProcessManager:
    """Менеджер жизненного цикла изолированного рабочего процесса Vision-агента."""

    def __init__(
        self,
        model_name: str = "xlangai/Jedi-3B-1080p",
        fallback_model: str = "Qwen/Qwen2.5-VL-3B-Instruct"
    ) -> None:
        self.model_name = model_name
        self.fallback_model = fallback_model
        self._process: Optional[mp.Process] = None
        self._task_queue: Optional[mp.Queue] = None
        self._status_queue: Optional[mp.Queue] = None
        self._stop_event: Optional[Any] = None
        self._is_ready: bool = False
        self._is_busy: bool = False

    def is_running(self) -> bool:
        """Проверяет, запущен ли рабочий процесс."""
        return self._process is not None and self._process.is_alive()

    def is_ready(self) -> bool:
        """Готова ли модель к инференсу."""
        return self.is_running() and self._is_ready

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
        self._is_ready = False
        self._is_busy = False

        self._process = mp.Process(
            target=_worker_process_loop,
            args=(self._task_queue, self._status_queue, self.model_name, self._stop_event, self.fallback_model),
            daemon=True
        )
        self._process.start()
        return True

    def stop(self) -> None:
        """Полная остановка процесса и гарантированное освобождение VRAM."""
        if self._stop_event is not None:
            self._stop_event.set()

        if self._task_queue is not None:
            try:
                self._task_queue.put({"type": "stop"})
            except Exception:
                pass

        if self._process is not None and self._process.is_alive():
            self._process.join(timeout=2.0)
            if self._process.is_alive():
                self._process.terminate()

        self._process = None
        self._task_queue = None
        self._status_queue = None
        self._stop_event = None
        self._is_ready = False
        self._is_busy = False

    def abort_task(self) -> None:
        """Экстренно прерывает выполнение текущей задачи агента."""
        self._is_busy = False
        if self._stop_event is not None:
            self._stop_event.set()

    def poll_status(self) -> List[Dict[str, Any]]:
        """Опрашивает очередь обновлений статуса от рабочего процесса."""
        events: List[Dict[str, Any]] = []
        if self._status_queue is None:
            return events

        while True:
            try:
                ev = self._status_queue.get_nowait()
                ev_type = ev.get("type")
                if ev_type == "ready":
                    self._is_ready = True
                elif ev_type in ("task_completed", "interrupted", "error"):
                    self._is_busy = False
                events.append(ev)
            except Exception:
                break
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
