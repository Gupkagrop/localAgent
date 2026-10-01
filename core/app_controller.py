"""
Модуль расширенного управления десктопными приложениями Windows.
Отвечает за интеллектуальный запуск, переключение фокуса без дублирования окон,
управление состоянием окон (свернуть/развернуть/закрыть) и ввод данных внутри приложений.
"""
import os
import re
import time
import threading
import ctypes
import subprocess
import sys
from collections.abc import Callable
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
    "steam": ["steam"],
    "обсидиан": ["obsidian"],
    "obsidian": ["obsidian"]
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
    "обсидиан": "obsidian.exe",
    "obsidian": "obsidian.exe",
    "antigravity": "antigravity"
}

BLOCKED_EXECUTABLE_EXTENSIONS: set[str] = {
    ".bat", ".cmd", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
    ".ps1", ".ps1xml", ".ps2", ".ps2xml", ".psc1", ".psc2",
    ".reg", ".scr", ".com", ".pif", ".hta", ".cpl", ".msc", ".jar"
}


class DesktopAppController:
    """Управляет жизненным циклом и окнами приложений Windows."""

    @staticmethod
    def launch_antigravity_gui() -> bool:
        """Безопасный запуск Antigravity IDE (GUI) без shell=True."""
        try:
            subprocess.Popen(["cmd.exe", "/c", "start", "", "antigravity"], shell=False)
            return True
        except Exception as e:
            print(f"[DesktopAppController] Ошибка запуска Antigravity IDE: {e}", file=sys.stderr)
            return False

    def __init__(self, on_log: Callable[[str], None] | None = None) -> None:
        self.on_log = on_log
        self.attach_interactive_desktop()

    def log(self, message: str) -> None:
        """Логирует действия контроллера приложений."""
        if self.on_log:
            self.on_log(message)
        print(f"[DesktopAppController] {message}")

    @staticmethod
    def attach_interactive_desktop() -> None:
        """Подключает текущий поток к интерактивной оконной станции WinSta0 при необходимости."""
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        try:
            user32 = ctypes.windll.user32
            h_winsta = user32.OpenWindowStationW("WinSta0", False, 0x00020000 | 0x037F)
            if h_winsta:
                user32.SetProcessWindowStation(h_winsta)
                h_desk = user32.OpenDesktopW("Default", 0, False, 0x00020000 | 0x01FF)
                if h_desk:
                    user32.SetThreadDesktop(h_desk)
        except Exception as e:
            print(f"[DesktopAppController] Не удалось подключиться к WinSta0: {e}", file=sys.stderr)

    def find_window(self, app_name: str) -> int | None:
        """
        Ищет видимое главное окно приложения по его названию или псевдонимам.
        Возвращает HWND окна или None.
        """
        self.attach_interactive_desktop()
        clean_name = app_name.lower().strip()
        search_terms = APP_TITLE_ALIASES.get(clean_name, [clean_name])

        target_hwnd: int | None = None

        def enum_callback(hwnd: int, _: int) -> bool:
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
            # Прерывание EnumWindows при возврате False из callback в pywin32 вызывает исключение
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
                except Exception as attach_err:
                    print(f"[AppController] Предупреждение AttachThreadInput (attach): {attach_err}", file=sys.stderr)

            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)

            if attached:
                try:
                    win32process.AttachThreadInput(curr_thread, fore_thread, False)
                except Exception as detach_err:
                    print(f"[AppController] Предупреждение AttachThreadInput (detach): {detach_err}", file=sys.stderr)

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

    @staticmethod
    def resolve_executable_or_shortcut(target_exe: str, app_name: str = "") -> str:
        """
        Интеллектуальный поиск пути к исполняемому файлу или ярлыку Windows (.lnk).
        Если файл существует или находится в PATH — возвращает его.
        Иначе ищет в Program Files, AppData, на рабочем столе и в меню Пуск.
        """
        import shutil
        if not target_exe:
            return target_exe

        # 1. Если это существующий путь
        if os.path.exists(target_exe):
            return target_exe

        # 2. Если файл находится в системном PATH
        which_path = shutil.which(target_exe)
        if which_path:
            return which_path

        base_stem = os.path.splitext(os.path.basename(target_exe))[0].lower()
        search_names = {base_stem}
        if app_name:
            search_names.add(app_name.lower().strip())

        # 3. Поиск в Program Files и LocalAppData
        search_dirs = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs"),
        ]
        for sdir in search_dirs:
            if not os.path.isdir(sdir):
                continue
            for name in search_names:
                candidate = os.path.join(sdir, name, f"{name}.exe")
                if os.path.exists(candidate):
                    return candidate
                try:
                    for folder in os.listdir(sdir):
                        if folder.lower() == name:
                            folder_path = os.path.join(sdir, folder)
                            if os.path.isdir(folder_path):
                                for fname in os.listdir(folder_path):
                                    if fname.lower() in (f"{name}.exe", f"{base_stem}.exe"):
                                        return os.path.join(folder_path, fname)
                except Exception:
                    pass

        # 4. Поиск в ярлыках Рабочего стола и Меню «Пуск»
        onedrive_desktop = os.path.expanduser(r"~\OneDrive\Desktop")
        shortcut_dirs = [
            os.environ.get("PUBLIC", r"C:\Users\Public") + r"\Desktop",
            os.path.expanduser(r"~\Desktop"),
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        ]
        if os.path.isdir(onedrive_desktop):
            shortcut_dirs.insert(2, onedrive_desktop)

        for sdir in shortcut_dirs:
            if not os.path.isdir(sdir):
                continue
            for name in search_names:
                direct_lnk = os.path.join(sdir, f"{name}.lnk")
                if os.path.exists(direct_lnk):
                    return direct_lnk
                try:
                    for root, _, files in os.walk(sdir):
                        for f in files:
                            if f.lower().endswith(".lnk") and any(n in f.lower() for n in search_names):
                                return os.path.join(root, f)
                except Exception:
                    pass

        return target_exe

    def launch_or_focus(self, app_name: str, executable: str | None = None) -> tuple[bool, str]:
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

        orig_ext = os.path.splitext(target_exe)[1].lower()
        if orig_ext in BLOCKED_EXECUTABLE_EXTENSIONS:
            self.log(f"Запуск файла с расширением '{orig_ext}' заблокирован политикой безопасности: {target_exe}")
            return False, f"Запуск файлов {orig_ext} заблокирован"

        resolved_exe = self.resolve_executable_or_shortcut(target_exe, clean_name)

        ext = os.path.splitext(resolved_exe)[1].lower()
        if ext in BLOCKED_EXECUTABLE_EXTENSIONS:
            self.log(f"Запуск файла с расширением '{ext}' заблокирован политикой безопасности: {resolved_exe}")
            return False, f"Запуск файлов {ext} заблокирован"

        try:
            if resolved_exe.lower() == "antigravity":
                if not self.launch_antigravity_gui():
                    return False, f"Не удалось запустить {app_name}"
            else:
                os.startfile(resolved_exe)
            self.log(f"Запущено приложение: {resolved_exe}")

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

        # Копируем текст в буфер обмена Windows с повторными попытками
        clipboard_opened = False
        for _ in range(5):
            try:
                win32clipboard.OpenClipboard()
                clipboard_opened = True
                break
            except Exception:
                time.sleep(0.05)

        if not clipboard_opened:
            return False, "Буфер обмена Windows временно заблокирован другим приложением"

        prev_clipboard = None
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                prev_clipboard = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()

        # Вставляем текст через Ctrl+V
        self._send_key_combo(VK_CONTROL, VK_V)

        if submit:
            time.sleep(0.08)
            self._send_key(VK_RETURN)

        # Восстанавливаем буфер обмена пользователя
        if prev_clipboard is not None:
            def restore_clipboard():
                time.sleep(0.08)
                for _ in range(5):
                    try:
                        win32clipboard.OpenClipboard()
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardText(prev_clipboard, win32con.CF_UNICODETEXT)
                        win32clipboard.CloseClipboard()
                        break
                    except Exception:
                        time.sleep(0.04)

            threading.Thread(target=restore_clipboard, daemon=True).start()

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


# Алиас класса для унифицированного доступа и обратной совместимости
AppController = DesktopAppController
