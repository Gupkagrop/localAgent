"""
Модуль низкоуровневого взаимодействия с экраном и устройствами ввода Windows.
Обеспечивает захват экрана, преобразование координат с учетом DPI и эмуляцию мыши/клавиатуры.
"""

import ctypes
from ctypes import wintypes
import time
from dataclasses import dataclass
from typing import Optional, Tuple
from PIL import Image

# Установка DPI-awareness для корректного разрешения экрана в Windows 10/11
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Константы Win32 событий мыши
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x000c
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000
WHEEL_DELTA = 120

# Константы Win32 событий клавиатуры
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

# Константа GDI
SRCCOPY = 0x00CC0020

# Коды виртуальных клавиш VK
VK_MAP = {
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "space": 0x20,
    "backspace": 0x08,
    "delete": 0x2E,
    "escape": 0x1B,
    "esc": 0x1B,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "pageup": 0x21,
    "pagedown": 0x22,
    "home": 0x24,
    "end": 0x23,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "win": 0x5B,
    "windows": 0x5B,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
}


@dataclass
class ScreenDimensions:
    """Параметры физического разрешения активного монитора."""
    width: int
    height: int
    left: int = 0
    top: int = 0


class ScreenController:
    """Контроллер экрана и устройств ввода для Vision-агента с поддержкой нескольких мониторов."""

    def __init__(self) -> None:
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32
        self._dimensions = self._get_screen_dimensions()
        self._current_monitor: Tuple[int, int, int, int] = (
            self._dimensions.left,
            self._dimensions.top,
            self._dimensions.width,
            self._dimensions.height
        )

    def _attach_desktop(self) -> None:
        """Подключает поток к интерактивному рабочему столу WinSta0\\Default."""
        try:
            hwinsta = self.user32.OpenWindowStationW("WinSta0", False, 0x10000000)
            if hwinsta:
                self.user32.SetProcessWindowStation(hwinsta)
            hdesk = self.user32.OpenDesktopW("Default", 0, False, 0x10000000)
            if hdesk:
                self.user32.SetThreadDesktop(hdesk)
        except Exception:
            pass

    def get_active_monitor_rect(self) -> Tuple[int, int, int, int]:
        """
        Возвращает (left, top, width, height) монитора, на котором находится
        активное окно приложения или курсор мыши.
        """
        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long)
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD)
            ]

        hwnd = self.user32.GetForegroundWindow()
        hmon = 0
        if hwnd:
            hmon = self.user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST = 2

        if not hmon:
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            pt = POINT()
            self.user32.GetCursorPos(ctypes.byref(pt))
            hmon = self.user32.MonitorFromPoint(pt, 2)

        if hmon:
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if self.user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                rc = mi.rcMonitor
                w = rc.right - rc.left
                h = rc.bottom - rc.top
                if w > 0 and h > 0:
                    return rc.left, rc.top, w, h

        # Резервный возврат основного монитора
        w_main = self.user32.GetSystemMetrics(0)
        h_main = self.user32.GetSystemMetrics(1)
        return 0, 0, w_main, h_main

    def _get_screen_dimensions(self) -> ScreenDimensions:
        """Получает текущее физическое разрешение активного монитора."""
        self._attach_desktop()
        left, top, width, height = self.get_active_monitor_rect()
        return ScreenDimensions(width=width, height=height, left=left, top=top)

    @property
    def dimensions(self) -> ScreenDimensions:
        """Возвращает актуальные размеры экрана."""
        return self._dimensions

    @property
    def screen_width(self) -> int:
        """Ширина экрана в пикселях."""
        return self._dimensions.width

    @property
    def screen_height(self) -> int:
        """Высота экрана в пикселях."""
        return self._dimensions.height

    def capture_screen(self) -> Image.Image:
        """
        Выполняет высокоскоростной снимок активного монитора через Win32 GDI BitBlt.
        При необходимости использует mss или PIL.ImageGrab как резервные каналы.
        """
        self._attach_desktop()
        dims = self._get_screen_dimensions()
        self._dimensions = dims
        left, top, width, height = dims.left, dims.top, dims.width, dims.height
        self._current_monitor = (left, top, width, height)

        hwnd = self.user32.GetDesktopWindow()
        hdc_screen = self.user32.GetDC(hwnd)
        if not hdc_screen:
            return self._fallback_capture()

        hdc_mem = self.gdi32.CreateCompatibleDC(hdc_screen)
        hbm = self.gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
        old_hbm = self.gdi32.SelectObject(hdc_mem, hbm)

        ret = self.gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, left, top, SRCCOPY)
        if not ret:
            # Очистка и переход к фолбеку
            self.gdi32.SelectObject(hdc_mem, old_hbm)
            self.gdi32.DeleteObject(hbm)
            self.gdi32.DeleteDC(hdc_mem)
            self.user32.ReleaseDC(hwnd, hdc_screen)
            return self._fallback_capture()

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = width
        bmi.biHeight = -height  # Отрицательное значение для top-down растра
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buffer_size = width * height * 4
        buf = ctypes.create_string_buffer(buffer_size)

        lines = self.gdi32.GetDIBits(
            hdc_mem,
            hbm,
            0,
            height,
            buf,
            ctypes.byref(bmi),
            0
        )

        # Очистка дескрипторов GDI
        self.gdi32.SelectObject(hdc_mem, old_hbm)
        self.gdi32.DeleteObject(hbm)
        self.gdi32.DeleteDC(hdc_mem)
        self.user32.ReleaseDC(hwnd, hdc_screen)

        if lines > 0:
            return Image.frombuffer("RGBA", (width, height), buf, "raw", "BGRA", 0, 1).convert("RGB")

        return self._fallback_capture()

    def _fallback_capture(self) -> Image.Image:
        """Резервный захват экрана через Qt GUI, mss или ImageGrab."""
        # 1. Если активен контекст Qt — используем нативный grabWindow на экране под курсором
        try:
            from PyQt6.QtGui import QGuiApplication, QCursor
            cursor_pos = QCursor.pos()
            q_screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
            if q_screen is not None:
                pix = q_screen.grabWindow(0)
                if not pix.isNull():
                    from PIL import ImageQt
                    return ImageQt.fromqpixmap(pix).convert("RGB")
        except Exception:
            pass

        # 2. Захват экрана через mss (быстрый в изолированном Worker)
        try:
            import mss
            with mss.MSS() as sct:
                left, top, width, height = self._current_monitor
                target_mon = None
                for mon in sct.monitors[1:]:
                    if abs(mon["left"] - left) < 50 and abs(mon["top"] - top) < 50:
                        target_mon = mon
                        break
                if target_mon is None:
                    target_mon = sct.monitors[1]
                sct_img = sct.grab(target_mon)
                return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        except Exception:
            pass

        # 3. Фолбек на стандартный ImageGrab
        try:
            from PIL import ImageGrab
            return ImageGrab.grab()
        except Exception:
            pass

        return Image.new("RGB", (self.screen_width, self.screen_height), color=(30, 30, 30))

    def denormalize_coordinate(self, norm_y: int, norm_x: int) -> Tuple[int, int]:
        """
        Преобразует нормализованные координаты Qwen (0..1000) в реальные экранные пиксели.
        Учитывает физическое смещение активного монитора (left, top) в мультимониторных конфигурациях.
        """
        safe_x = max(0, min(1000, norm_x))
        safe_y = max(0, min(1000, norm_y))

        left, top, width, height = self._current_monitor
        screen_x = left + int((safe_x / 1000.0) * width)
        screen_y = top + int((safe_y / 1000.0) * height)
        return screen_x, screen_y

    def move_mouse(self, x: int, y: int) -> None:
        """Перемещает курсор мыши в заданные экранные координаты."""
        self._attach_desktop()
        self.user32.SetCursorPos(x, y)

    def click(self, x: int, y: int, button: str = "left") -> None:
        """
        Выполняет клик мыши по заданным физическим координатам экрана.
        """
        self.move_mouse(x, y)
        time.sleep(0.05)

        if button == "right":
            self.user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            self.user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            return

        if button == "middle":
            self.user32.mouse_event(MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            self.user32.mouse_event(MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)
            return

        # По умолчанию - левая кнопка мыши
        self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def double_click(self, x: int, y: int) -> None:
        """Выполняет двойной клик левой кнопкой мыши."""
        self.click(x, y, button="left")
        time.sleep(0.08)
        self.click(x, y, button="left")

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, steps: int = 15) -> None:
        """Выполняет плавное перетаскивание курсором мыши."""
        self.move_mouse(start_x, start_y)
        time.sleep(0.05)
        self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)

        for step in range(1, steps + 1):
            curr_x = int(start_x + (end_x - start_x) * (step / steps))
            curr_y = int(start_y + (end_y - start_y) * (step / steps))
            self.move_mouse(curr_x, curr_y)
            time.sleep(0.01)

        time.sleep(0.05)
        self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def scroll(self, direction: str = "down", amount: int = 3) -> None:
        """
        Выполняет прокрутку колеса мыши.
        direction: 'down' (вниз) или 'up' (вверх).
        amount: количество щелчков прокрутки.
        """
        delta = -WHEEL_DELTA * amount if direction == "down" else WHEEL_DELTA * amount
        self.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)

    def _type_chars_direct(self, text: str) -> None:
        """Посимвольный ввод текста через Unicode SendInput."""
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", ctypes.c_ulong),
                ("ki", KEYBDINPUT),
                ("padding", ctypes.c_ubyte * 8),
            ]

        for char in text:
            inp_down = INPUT()
            inp_down.type = 1
            inp_down.ki.wVk = 0
            inp_down.ki.wScan = ord(char)
            inp_down.ki.dwFlags = KEYEVENTF_UNICODE

            inp_up = INPUT()
            inp_up.type = 1
            inp_up.ki.wVk = 0
            inp_up.ki.wScan = ord(char)
            inp_up.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP

            inputs = (INPUT * 2)(inp_down, inp_up)
            self.user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
            time.sleep(0.01)

    def type_text(self, text: str, press_enter: bool = False) -> None:
        """
        Печатает текст в активный элемент интерфейса.
        Использует гибридный ввод:
        - Короткие фразы (<= 20 символов): посимвольный ввод через Unicode SendInput.
        - Длинные фразы (> 20 символов): быстрая вставка через буфер обмена (Ctrl+V) с восстановлением буфера.
        """
        if not text:
            if press_enter:
                self.send_key("enter")
            return

        if len(text) > 20:
            import win32clipboard
            import win32con
            prev_clipboard: Optional[str] = None
            try:
                win32clipboard.OpenClipboard()
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                        prev_clipboard = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
                finally:
                    win32clipboard.CloseClipboard()

                # Вставка через Ctrl+V
                self.hotkey(["ctrl", "v"])
                time.sleep(0.08)

                # Восстановление буфера пользователя
                if prev_clipboard is not None:
                    win32clipboard.OpenClipboard()
                    try:
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardText(prev_clipboard, win32con.CF_UNICODETEXT)
                    finally:
                        win32clipboard.CloseClipboard()
            except Exception:
                self._type_chars_direct(text)
        else:
            self._type_chars_direct(text)

        if press_enter:
            time.sleep(0.05)
            self.send_key("enter")

    def send_key(self, key_name: str) -> None:
        """Нажимает и отпускает одну виртуальную клавишу по названию."""
        key_lower = key_name.lower().strip()
        vk_code = VK_MAP.get(key_lower)
        if not vk_code:
            if len(key_lower) == 1:
                vk_code = self.user32.VkKeyScanW(ord(key_lower)) & 0xFF
            else:
                return

        self.user32.keybd_event(vk_code, 0, 0, 0)
        time.sleep(0.03)
        self.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

    def hotkey(self, keys: list[str]) -> None:
        """
        Зажимает комбинацию клавиш и затем отпускает в обратном порядке.
        Пример: ['ctrl', 'a'], ['ctrl', 'v'], ['win', 'd'].
        """
        if not keys:
            return

        vk_codes: list[int] = []
        for k in keys:
            k_lower = k.lower().strip()
            vk = VK_MAP.get(k_lower)
            if not vk and len(k_lower) == 1:
                vk = self.user32.VkKeyScanW(ord(k_lower)) & 0xFF
            if vk:
                vk_codes.append(vk)

        for code in vk_codes:
            self.user32.keybd_event(code, 0, 0, 0)
            time.sleep(0.02)

        time.sleep(0.05)

        for code in reversed(vk_codes):
            self.user32.keybd_event(code, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.02)
