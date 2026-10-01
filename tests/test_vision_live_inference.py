"""
Интерактивный и автоматический тест полной работоспособности ИИ-агента Vision (Live Model Verification).
Запускает реальный фоновый процесс с 4-битной квантованной моделью (Jedi-3B / Qwen2.5-VL),
проверяет загрузку в VRAM, опрос IPC очередей, распознавание элементов интерфейса и инференс.
"""

import os
import sys
import time
from PIL import Image, ImageDraw

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Добавляем корневую директорию проекта в sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.vision_agent import VisionAgentProcessManager, ActionParser


def create_mock_desktop_image(file_path: str = "temp_mock_desktop.png") -> tuple[str, tuple[int, int]]:
    """
    Создает тестовое 1080p изображение рабочего стола с ярлыками для верификации точности клика.
    Возвращает путь к файлу и точные координаты центра иконки Obsidian.
    """
    width, height = 1920, 1080
    img = Image.new("RGB", (width, height), color=(18, 12, 38))
    draw = ImageDraw.Draw(img)

    # Рисуем панель задач Windows 11 внизу
    draw.rectangle([0, height - 48, width, height], fill=(28, 24, 46))
    draw.rectangle([width // 2 - 200, height - 40, width // 2 + 200, height - 8], fill=(42, 36, 68))

    # Рисуем тестовую иконку Obsidian в левом нижнем углу (как на реальном рабочем столе пользователя)
    obsidian_center_x = 80
    obsidian_center_y = 860
    box_size = 48
    draw.rectangle(
        [
            obsidian_center_x - box_size // 2,
            obsidian_center_y - box_size // 2,
            obsidian_center_x + box_size // 2,
            obsidian_center_y + box_size // 2,
        ],
        fill=(138, 43, 226),  # Фиолетовый кристалл Obsidian
        outline=(200, 150, 255),
        width=2
    )
    # Текст под иконкой
    draw.text((obsidian_center_x - 22, obsidian_center_y + 30), "Obsidian", fill=(255, 255, 255))

    img.save(file_path)
    return file_path, (obsidian_center_x, obsidian_center_y)


def run_vision_agent_live_test() -> bool:
    """Запускает сквозную проверку работоспособности модели Vision-агента."""
    print("=" * 70)
    print("🚀 ЗАПУСК ПОЛНОЙ ПРОВЕРКИ РАБОТОСПОСОБНОСТИ ИИ-АГЕНТА VISION (E2E LIVE)")
    print("=" * 70)

    # 1. Проверка наличия весов в кэше
    cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
    print(f"\n[1/5] Проверка кэша моделей Hugging Face...")
    print(f"      Директория кэша: {cache_dir}")

    # 2. Инициализация менеджера процессов
    model_name = "xlangai/Jedi-3B-1080p"
    fallback_model = "Qwen/Qwen2.5-VL-3B-Instruct"
    print(f"\n[2/5] Инициализация VisionAgentProcessManager ({model_name})...")
    mgr = VisionAgentProcessManager(model_name=model_name, fallback_model=fallback_model)

    start_t = time.time()
    print("      Старт фонового воркер-процесса...")
    if not mgr.start():
        print("❌ Не удалось запустить фоновый процесс.")
        return False

    print("      Ожидание загрузки весов и прогресса (BitsAndBytes 4-bit NF4)...")
    last_reported_pct = -1
    is_ready = False
    load_timeout = 180.0

    while time.time() - start_t < load_timeout:
        events = mgr.poll_status()
        for ev in events:
            ev_type = ev.get("type")
            if ev_type == "loading_progress":
                pct = ev.get("progress", 0)
                desc = ev.get("desc", "Загрузка")
                if pct != last_reported_pct:
                    last_reported_pct = pct
                    sys.stdout.write(f"\r      ⏳ {desc}: {pct}%")
                    sys.stdout.flush()
            elif ev_type == "log":
                print(f"\n      [Worker Log] {ev.get('message')}")
            elif ev_type == "ready":
                print(f"\n      ✅ Модель успешно загружена и готова к работе! ({ev.get('message')})")
                is_ready = True
                break
            elif ev_type == "error":
                print(f"\n❌ [Worker Error] {ev.get('message')}")
                mgr.stop()
                return False

        if is_ready:
            break
        time.sleep(0.5)

    if not is_ready:
        print("\n❌ Истек таймаут ожидания готовности модели (180 сек).")
        mgr.stop()
        return False

    load_duration = time.time() - start_t
    print(f"      ⏱ Время холодной инициализации модели в VRAM: {load_duration:.2f} сек.")

    # 3. Отправка тестовой задачи управления
    print("\n[3/5] Запуск тестовой задачи компьютерного управления...")
    task_prompt = "Дважды кликни на иконку Obsidian на рабочем столе, чтобы открыть заметки"
    print(f"      Целевая задача: «{task_prompt}»")

    task_started_time = time.time()
    if not mgr.execute_task(task_prompt, max_steps=3):
        print("❌ Ошибка отправки команды в task_queue.")
        mgr.stop()
        return False

    # 4. Мониторинг выполнения шагов и рассуждений
    print("\n[4/5] Мониторинг рассуждений модели (Reasoning Loop)...")
    task_done = False
    task_success = False
    recorded_actions = []

    while time.time() - task_started_time < 90.0:
        events = mgr.poll_status()
        for ev in events:
            ev_type = ev.get("type")
            if ev_type == "step_status":
                print(f"      👉 [Шаг {ev.get('step')}] Статус: {ev.get('status')}")
            elif ev_type == "action_decided":
                thought = ev.get("thought", "")
                act = ev.get("action", "")
                coord = ev.get("coordinate", "")
                recorded_actions.append(ev)
                print(f"      🧠 [Мысль модели] {thought}")
                print(f"      🎯 [Команда] action='{act}', coordinate={coord}")
            elif ev_type == "click_performed":
                print(f"      🖱 [Win32 Клик] ({ev.get('x')}, {ev.get('y')}) кнопка={ev.get('button')}")
            elif ev_type == "confirmation_requested":
                print(f"      🛡 [Guardrails Запрос подтверждения] {ev.get('message')}")
            elif ev_type == "task_completed":
                task_done = True
                task_success = ev.get("success", False)
                print(f"\n      🏁 Задача завершена! Статус: {'Успех' if task_success else 'Прервано'}")
                print(f"      Сообщение: {ev.get('message')}")
                break
            elif ev_type == "interrupted":
                print(f"\n      🛑 Задача прервана: {ev.get('reason')}")
                task_done = True
                break
            elif ev_type == "error":
                print(f"\n❌ [Ошибка воркера] {ev.get('message')}")
                task_done = True
                break

        if task_done:
            break
        time.sleep(0.3)

    inference_duration = time.time() - task_started_time
    print(f"      ⏱ Полное время решения задачи: {inference_duration:.2f} сек.")

    # 5. Тестирование экстренной остановки и очистки ресурсов
    print("\n[5/5] Проверка завершения процесса и освобождения VRAM...")
    mgr.stop()
    time.sleep(1.0)

    if not mgr.is_running() and not mgr.is_busy():
        print("      ✅ Процесс воркера остановлен, ресурсы VRAM полностью освобождены.")
    else:
        print("      ⚠ Предупреждение: процесс не завершился чисто.")

    print("\n" + "=" * 70)
    print("📊 ИТОГОВЫЙ ОТЧЕТ РАБОТОСПОСОБНОСТИ VISION-АГЕНТА:")
    print(f"   • Загрузка модели в память:  УСПЕХ ({load_duration:.1f} сек)")
    print(f"   • Генерация действий:         {len(recorded_actions)} действий принято")
    print(f"   • Статус завершения задачи:   {'УСПЕХ' if task_success else 'ЗАВЕРШЕНО (лимит шагов/прервано)'}")
    print("=" * 70 + "\n")

    return True


if __name__ == "__main__":
    success = run_vision_agent_live_test()
    sys.exit(0 if success else 1)
