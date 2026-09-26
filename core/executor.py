"""
Модуль исполнения команд (Executor).
Отвечает за вызовы системных API Windows, управление окнами, громкостью,
медиаплеером, а также интеграцию с Antigravity CLI и Antigravity 2.0 GUI.
"""
import os
import time
import ctypes
import subprocess
import webbrowser
from typing import Optional, Callable
import win32gui
import win32con
import win32clipboard

from core.audio_ducking import AudioDucker

# Виртуальные коды мультимедиа-клавиш Windows
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_VOLUME_MUTE = 0xAD

# Коды клавиш модификаторов
VK_CONTROL = 0x11
VK_V = 0x56
VK_N = 0x4E
VK_RETURN = 0x0D
KEYEVENTF_KEYUP = 0x0002

class CommandExecutor:
    def __init__(
        self,
        audio_ducker: Optional[AudioDucker] = None,
        on_log: Optional[Callable[[str], None]] = None
    ):
        self.audio_ducker = audio_ducker or AudioDucker()
        self.on_log = on_log

    def log(self, message: str) -> None:
        if self.on_log:
            self.on_log(message)

    def _send_key_combo(self, key1: int, key2: int) -> None:
        """Эмулирует нажатие двух клавиш (например Ctrl+N или Ctrl+V)."""
        ctypes.windll.user32.keybd_event(key1, 0, 0, 0)
        ctypes.windll.user32.keybd_event(key2, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(key2, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(key1, 0, KEYEVENTF_KEYUP, 0)

    def _send_key(self, key: int) -> None:
        """Эмулирует одиночное нажатие клавиши."""
        ctypes.windll.user32.keybd_event(key, 0, 0, 0)
        time.sleep(0.02)
        ctypes.windll.user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)

    def execute(self, command: dict) -> tuple[bool, str]:
        """
        Исполняет команду, возвращает (success, status_message).
        """
        action = command.get("action", "unknown")
        target = command.get("target", "")
        params = command.get("parameters", {})

        # 0. Прямой диалоговый ответ нейросети (LLM)
        if action == "general_answer":
            ans = params.get("text") or command.get("text") or target
            self.log(f"Ответ ассистента: {ans}")
            return True, str(ans)

        # 1. Antigravity 2.0 (GUI)
        if action == "antigravity_gui":
            return self._handle_antigravity_gui(target, params)

        # 2. Antigravity CLI
        if action == "antigravity_cli":
            return self._handle_antigravity_cli(params.get("prompt", ""))

        # 3. Громкость
        if action == "set_volume":
            return self._handle_volume(target, params)

        # 4. Управление медиа
        if action == "media_control":
            return self._handle_media(target)

        # 5. Запуск сторонних приложений
        if action == "launch_app":
            try:
                os.startfile(target)
                self.log(f"Запущено приложение: {target}")
                return True, f"Запущено: {params.get('app_name', target)}"
            except Exception as e:
                self.log(f"Ошибка запуска приложения {target}: {e}")
                return False, f"Не удалось запустить {target}"

        # 6. Открытие веб-ссылок
        if action == "open_url":
            try:
                webbrowser.open(target)
                self.log(f"Открыта ссылка в браузере: {target}")
                return True, "Открыто в браузере"
            except Exception as e:
                return False, f"Ошибка открытия ссылки: {e}"

        # 7. Системные действия (выключение/перезагрузка)
        if action == "system_action":
            confirmed = params.get("confirmed", False)
            if params.get("dangerous") and not confirmed:
                return False, "CONFIRM_REQUIRED"
            if target == "shutdown":
                try:
                    subprocess.Popen(["shutdown", "/s", "/t", "15"])
                    self.log("Инициировано выключение компьютера через 15 секунд.")
                    return True, "Выключение компьютера через 15 секунд"
                except Exception as e:
                    return False, f"Ошибка выключения: {e}"
            if target == "restart":
                try:
                    subprocess.Popen(["shutdown", "/r", "/t", "15"])
                    self.log("Инициирована перезагрузка компьютера через 15 секунд.")
                    return True, "Перезагрузка компьютера через 15 секунд"
                except Exception as e:
                    return False, f"Ошибка перезагрузки: {e}"
            return True, "Действие отменено"

        self.log(f"Неизвестная команда: {target}")
        return False, "Команда не распознана"

    def _handle_antigravity_gui(self, target: str, params: dict) -> tuple[bool, str]:
        """Управляет окном Antigravity 2.0 (GUI)."""
        hwnd = None

        def enum_windows_callback(handle, extra):
            nonlocal hwnd
            if win32gui.IsWindowVisible(handle):
                title = win32gui.GetWindowText(handle)
                if "antigravity" in title.lower():
                    hwnd = handle
            return True

        win32gui.EnumWindows(enum_windows_callback, None)

        if not hwnd:
            # Окно не найдено - запускаем Antigravity
            try:
                subprocess.Popen(["cmd", "/c", "start", "", "antigravity"], shell=True)
                self.log("Запускаю Antigravity 2.0...")
                return True, "Запускаю Antigravity 2.0"
            except Exception as e:
                return False, f"Не удалось открыть Antigravity: {e}"

        try:
            # Выводим окно на передний план
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.15)

            if target == "prompt":
                prompt_text = params.get("prompt", "")
                if params.get("new_chat"):
                    # Создаем новый чат по Ctrl+N
                    self._send_key_combo(VK_CONTROL, VK_N)
                    time.sleep(0.2)

                # Копируем промпт в буфер обмена
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(prompt_text, win32clipboard.CF_UNICODETEXT)
                finally:
                    win32clipboard.CloseClipboard()

                # Вставляем через Ctrl+V и нажимаем Enter
                self._send_key_combo(VK_CONTROL, VK_V)
                time.sleep(0.08)
                self._send_key(VK_RETURN)
                self.log(f"Промпт отправлен в Antigravity GUI: {prompt_text[:40]}...")
                return True, "Промпт отправлен в Antigravity"

            if target == "new_chat":
                self._send_key_combo(VK_CONTROL, VK_N)
                self.log("Создан новый диалог в Antigravity")
                return True, "Создан новый чат"

            self.log("Окно Antigravity выведено на передний план")
            return True, "Antigravity открыт"
        except Exception as e:
            return False, f"Ошибка управления окном Antigravity: {e}"

    def _handle_antigravity_cli(self, prompt: str) -> tuple[bool, str]:
        """Запускает Antigravity CLI в Windows Terminal."""
        try:
            # Команда запуска Windows Terminal с вкладкой PowerShell и agy
            if prompt:
                # Экранируем кавычки для powershell
                escaped_prompt = prompt.replace('"', '`"')
                cmd = f'wt.exe -w 0 nt powershell -NoExit -Command "agy -p \\"{escaped_prompt}\\""'
            else:
                cmd = 'wt.exe -w 0 nt powershell -NoExit -Command "agy"'

            subprocess.Popen(cmd, shell=True)
            self.log(f"Запущен Antigravity CLI с задачей: {prompt or 'интерактивный режим'}")
            return True, "Antigravity CLI запущен в терминале"
        except Exception:
            # Fallback если wt.exe недоступен
            try:
                if prompt:
                    cmd = f'start powershell -NoExit -Command "agy -p \\"{prompt}\\""'
                else:
                    cmd = 'start powershell -NoExit -Command "agy"'
                subprocess.Popen(cmd, shell=True)
                return True, "Antigravity CLI запущен в PowerShell"
            except Exception as e:
                return False, f"Ошибка запуска CLI: {e}"

    def _handle_volume(self, target: str, params: dict) -> tuple[bool, str]:
        """Управление громкостью через pycaw."""
        if target == "absolute":
            percent = params.get("percent", 50)
            self.audio_ducker.set_volume(percent / 100.0)
            self.log(f"Громкость установлена на {percent}%")
            return True, f"Громкость: {percent}%"

        curr = self.audio_ducker.get_volume()
        step = params.get("step", 10)

        if target == "step_up":
            new_val = min(100.0, curr + step)
            self.audio_ducker.set_volume(new_val / 100.0)
            self.log(f"Громкость увеличена до {int(new_val)}%")
            return True, f"Громкость: {int(new_val)}%"

        if target == "step_down":
            new_val = max(0.0, curr - step)
            self.audio_ducker.set_volume(new_val / 100.0)
            self.log(f"Громкость уменьшена до {int(new_val)}%")
            return True, f"Громкость: {int(new_val)}%"

        if target == "mute":
            self._send_key(VK_VOLUME_MUTE)
            self.log("Звук заглушен / включен")
            return True, "Звук переключен"

        return False, "Не удалось изменить громкость"

    def _handle_media(self, target: str) -> tuple[bool, str]:
        """Эмуляция аппаратных медиаклавиш Windows."""
        if target == "play_pause":
            self._send_key(VK_MEDIA_PLAY_PAUSE)
            self.log("Воспроизведение: Пауза / Плей")
            return True, "Пауза / Плей"

        if target == "next_track":
            self._send_key(VK_MEDIA_NEXT_TRACK)
            self.log("Следующий трек")
            return True, "Следующий трек"

        if target == "prev_track":
            self._send_key(VK_MEDIA_PREV_TRACK)
            self.log("Предыдущий трек")
            return True, "Предыдущий трек"

        return False, "Неизвестное медиа-действие"
