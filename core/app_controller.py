"""
Модуль расширенного управления десктопными приложениями Windows.
Отвечает за интеллектуальный запуск, переключение фокуса без дублирования окон,
управление состоянием окон (свернуть/развернуть/закрыть) и ввод данных внутри приложений.
"""
import os
import re
import time
import ctypes
import subprocess
from typing import Optional, Callable, Any
import win32gui
import win32con
import win32process
import win32api
import win32clipboard

# Виртуальные коды клавиш Windows
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12  # Alt
VK_LWIN = 0x5B
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_V = 0x56
VK_C = 0x43
VK_N = 0x4E
VK_T = 0x54
VK_W = 0x57
VK_F = 0x46
VK_D = 0x44
KEYEVENTF_KEYUP = 0x0002

APP_TITLE_ALIASES: dict[str, list[str]] = {
    "блокнот": ["блокнот", "notepad"],
    "notepad": ["notepad", "блокнот"],
    "калькулятор": ["калькулятор", "calculator"],
    "calculator": ["calculator", "калькулятор"],
    "хром": ["chrome", "google chrome"],
    "chrome": ["chrome", "google chrome"],
    "браузер": ["chrome", "google chrome", "edge", "yandex", "firefox"],
    "телеграм": ["telegram"],
    "telegram": ["telegram"],
    "проводник": ["проводник", "explorer", "этот компьютер"],
    "explorer": ["explorer", "проводник", "этот компьютер"],
    "диспетчер задач": ["диспетчер задач", "task manager"],
    "taskmgr": ["taskmgr", "диспетчер задач", "task manager"],
    "терминал": ["windows terminal", "wt", "консоль", "powershell", "cmd"],
    "antigravity": ["antigravity"],
    "ворд": ["word"],
    "word": ["word"],
    "эксель": ["excel"],
    "excel": ["excel"],
    "пейнт": ["paint"],
    "paint": ["paint"],
    "спотифай": ["spotify"],
    "spotify": ["spotify"],
    "дискорд": ["discord"],
    "discord": ["discord"],
    "стим": ["steam"],
    "steam": ["steam"]
}

DEFAULT_EXECUTABLES: dict[str, str] = {
    "блокнот": "notepad.exe",
    "notepad": "notepad.exe",
    "калькулятор": "calc.exe",
    "calculator": "calc.exe",
    "хром": "chrome.exe",
    "chrome": "chrome.exe",
    "браузер": "chrome.exe",
    "телеграм": "telegram.exe",
    "telegram": "telegram.exe",
    "проводник": "explorer.exe",
    "explorer": "explorer.exe",
    "диспетчер задач": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "терминал": "wt.exe",
    "paint": "mspaint.exe",
    "пейнт": "mspaint.exe",
    "word": "winword.exe",
    "ворд": "winword.exe",
    "excel": "excel.exe",
    "эксель": "excel.exe",
    "antigravity": "antigravity"
}


class DesktopAppController:
    """Управляет жизненным циклом и окнами приложений Windows."""

    def __init__(self, on_log: Optional[Callable[[str], None]] = None):
        self.on_log = on_log
        self.attach_interactive_desktop()

    def log(self, message: str) -> None:
        """Логирует действия контроллера приложений."""
        if self.on_log:
            self.on_log(message)
        print(f"[DesktopAppController] {message}")

    @staticmethod
    def attach_interactive_desktop() -> None:
        """Подключает текущий поток к интерактивной оконной станции WinSta0 для гарантированного поиска окон."""
        try:
            user32 = ctypes.windll.user32
            h_winsta = user32.OpenWindowStationW("WinSta0", False, 0x00020000 | 0x037F)
            if h_winsta:
                user32.SetProcessWindowStation(h_winsta)
                h_desk = user32.OpenDesktopW("Default", 0, False, 0x00020000 | 0x01FF)
                if h_desk:
                    user32.SetThreadDesktop(h_desk)
        except Exception:
            pass

    def find_window(self, app_name: str) -> Optional[int]:
        """
        Ищет видимое главное окно приложения по его названию или псевдонимам.
        Возвращает HWND окна или None.
        """
        self.attach_interactive_desktop()
        clean_name = app_name.lower().strip()
        search_terms = APP_TITLE_ALIASES.get(clean_name, [clean_name])

        target_hwnd: Optional[int] = None

        def enum_callback(hwnd: int, _: Any) -> bool:
            nonlocal target_hwnd
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd).strip().lower()
            if not title:
                return True
            for term in search_terms:
                if term in title:
                    target_hwnd = hwnd
                    return False
            return True

        try:
            win32gui.EnumWindows(enum_callback, None)
        except Exception:
            pass

        return target_hwnd

    def focus_window(self, hwnd: int) -> bool:
        """
        Надежно выводит окно на передний план с обходом ограничений Windows 11.
        """
        if not win32gui.IsWindow(hwnd):
            return False

        try:
            # Если окно свернуто - восстанавливаем его
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            else:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

            foreground_hwnd = win32gui.GetForegroundWindow()
            if foreground_hwnd == hwnd:
                return True

            curr_thread = win32api.GetCurrentThreadId()
            fore_thread, _ = win32process.GetWindowThreadProcessId(foreground_hwnd)

            attached = False
            if curr_thread != fore_thread and fore_thread != 0:
                try:
                    win32process.AttachThreadInput(curr_thread, fore_thread, True)
                    attached = True
                except Exception:
                    pass

            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)

            if attached:
                try:
                    win32process.AttachThreadInput(curr_thread, fore_thread, False)
                except Exception:
                    pass

            time.sleep(0.08)
            return True
        except Exception:
            # Резервный трюк через имитацию клавиши Alt для обхода ограничений
            try:
                win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
                win32gui.SetForegroundWindow(hwnd)
                win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
                return True
            except Exception:
                return False

    def launch_or_focus(self, app_name: str, executable: Optional[str] = None) -> tuple[bool, str]:
        """
        Интеллектуальный запуск приложения:
        - Если окно уже открыто -> выводит его на передний план (без дублирования процессов).
        - Если не открыто -> запускает исполняемый файл, ожидает окно и передает фокус.
        """
        clean_name = app_name.lower().strip()
        existing_hwnd = self.find_window(clean_name)
        if existing_hwnd:
            self.focus_window(existing_hwnd)
            self.log(f"Окно {app_name} уже открыто, переключен фокус.")
            return True, f"Переключено на {app_name}"

        # Запуск приложения
        target_exe = executable or DEFAULT_EXECUTABLES.get(clean_name, f"{clean_name}.exe")
        try:
            if target_exe.lower() == "antigravity":
                subprocess.Popen(["cmd", "/c", "start", "", "antigravity"], shell=True)
            else:
                os.startfile(target_exe)
            self.log(f"Запущено приложение: {target_exe}")

            # Ожидаем появления окна до 1.5 секунд
            for _ in range(10):
                time.sleep(0.15)
                new_hwnd = self.find_window(clean_name)
                if new_hwnd:
                    self.focus_window(new_hwnd)
                    break

            return True, f"Запущено: {app_name}"
        except Exception as e:
            self.log(f"Ошибка запуска {app_name}: {e}")
            return False, f"Не удалось запустить {app_name}"

    def close_app(self, app_name: str) -> tuple[bool, str]:
        """Мягко закрывает приложение через системное сообщение WM_CLOSE."""
        clean_name = app_name.lower().strip()
        hwnd = self.find_window(clean_name)
        if not hwnd:
            # Если передано "окно" или "текущее" - закрываем активное
            if clean_name in ["окно", "текущее", "программу"]:
                hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return False, f"Окно {app_name} не найдено"

        try:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            self.log(f"Отправлено сообщение закрытия окну: {app_name}")
            return True, f"Закрыто: {app_name}"
        except Exception as e:
            return False, f"Ошибка закрытия окна: {e}"

    def minimize_app(self, app_name: str) -> tuple[bool, str]:
        """Сворачивает указанное приложение или текущее активное окно."""
        clean_name = app_name.lower().strip()
        hwnd = self.find_window(clean_name) if clean_name not in ["окно", "текущее", "всё", "все"] else win32gui.GetForegroundWindow()
        if not hwnd:
            return False, f"Окно {app_name} не найдено"

        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        self.log(f"Окно свернуто: {app_name}")
        return True, f"Свернуто: {app_name}"

    def maximize_app(self, app_name: str) -> tuple[bool, str]:
        """Разворачивает окно приложения на весь экран."""
        clean_name = app_name.lower().strip()
        hwnd = self.find_window(clean_name) if clean_name not in ["окно", "текущее"] else win32gui.GetForegroundWindow()
        if not hwnd:
            return False, f"Окно {app_name} не найдено"

        self.focus_window(hwnd)
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        self.log(f"Окно развернуто на весь экран: {app_name}")
        return True, f"Развернуто: {app_name}"

    def minimize_all(self) -> tuple[bool, str]:
        """Сворачивает все окна (эмуляция Win+D) и показывает рабочий стол."""
        self._send_key_combo(VK_LWIN, VK_D)
        self.log("Свернуты все окна (показан рабочий стол)")
        return True, "Рабочий стол"

    def type_into_app(
        self,
        app_name: str,
        text: str,
        submit: bool = False,
        search_mode: bool = False
    ) -> tuple[bool, str]:
        """
        Фокусирует приложение и вводит в него текст (через буфер обмена).
        Если search_mode=True, сначала нажимает Ctrl+F для вызова строки поиска.
        Если submit=True, после ввода нажимает клавишу Enter.
        """
        clean_name = app_name.lower().strip()
        hwnd = self.find_window(clean_name)
        if not hwnd:
            # Запускаем приложение если не было открыто
            ok, _ = self.launch_or_focus(clean_name)
            if not ok:
                return False, f"Не удалось открыть {app_name}"
            time.sleep(0.5)
            hwnd = self.find_window(clean_name)

        if hwnd:
            self.focus_window(hwnd)
            time.sleep(0.15)

        # Вызов строки поиска при необходимости
        if search_mode:
            self._send_key_combo(VK_CONTROL, VK_F)
            time.sleep(0.15)

        # Копируем текст в буфер обмена Windows
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()

        # Вставляем текст через Ctrl+V
        self._send_key_combo(VK_CONTROL, VK_V)

        if submit:
            time.sleep(0.08)
            self._send_key(VK_RETURN)

        self.log(f"Введен текст в {app_name}: {text}")
        return True, f"Введено в {app_name}"

    def send_app_hotkey(self, app_name: str, hotkey: str) -> tuple[bool, str]:
        """Отправляет клавиатурное сочетание в приложение (new_tab, close_tab, search)."""
        clean_name = app_name.lower().strip()
        hwnd = self.find_window(clean_name) if clean_name not in ["окно", "текущее"] else win32gui.GetForegroundWindow()
        if hwnd:
            self.focus_window(hwnd)
            time.sleep(0.1)

        action_name = hotkey.lower()
        if action_name in ["new_tab", "новая вкладка"]:
            self._send_key_combo(VK_CONTROL, VK_T)
            return True, "Новая вкладка"
        if action_name in ["close_tab", "закрой вкладку"]:
            self._send_key_combo(VK_CONTROL, VK_W)
            return True, "Вкладка закрыта"
        if action_name in ["search", "поиск"]:
            self._send_key_combo(VK_CONTROL, VK_F)
            return True, "Поиск"

        return False, "Неизвестное сочетание клавиш"

    @staticmethod
    def _send_key(vk_code: int) -> None:
        """Отправляет одиночное нажатие и отпускание клавиши."""
        win32api.keybd_event(vk_code, 0, 0, 0)
        time.sleep(0.03)
        win32api.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

    @staticmethod
    def _send_key_combo(modifier_vk: int, key_vk: int) -> None:
        """Отправляет сочетание клавиш (модификатор + клавиша)."""
        win32api.keybd_event(modifier_vk, 0, 0, 0)
        time.sleep(0.02)
        win32api.keybd_event(key_vk, 0, 0, 0)
        time.sleep(0.03)
        win32api.keybd_event(key_vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.02)
        win32api.keybd_event(modifier_vk, 0, KEYEVENTF_KEYUP, 0)
