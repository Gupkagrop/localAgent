"""
Низкоуровневый перехватчик аппаратной клавиши Copilot (pynput + Win32 Event Filter).
Распознает нажатие физической клавиши Copilot (VK_F23 = 0x8E, VK_APPS = 0x5D, Win+Shift+C),
блокирует открытие поиска/меню Пуск Windows (маскирование VK_CONTROL),
различает одиночный клик (Tap-to-Talk) и удержание (Spotlight).
"""
import time
import ctypes
import threading
from typing import Callable, Optional
from pynput import keyboard

VK_F23 = 0x86          # Официальный Windows виртуальный код F23 (134 = 0x86, аппаратный Copilot)
VK_F23_ALT = 0x8E      # Дополнительный OEM/сканкод некоторых клавиатур (142 = 0x8E)
VK_LWIN = 0x5B         # Левая клавиша Windows
VK_RWIN = 0x5C         # Правая клавиша Windows
VK_LSHIFT = 0xA0       # Левый Shift
VK_APPS = 0x5D         # Клавиша Menu/Application
VK_CONTROL = 0x11      # Виртуальная клавиша Ctrl для маскирования Win-клавиши
VK_KEY_J = 0x4A        # Клавиша 'J' для глобального шортката Ctrl+Shift+J
VK_ESCAPE = 0x1B       # Клавиша Escape
VK_MASK = 0xFF         # vkFF (AutoHotkey #MenuMaskKey для нейтрализации меню Пуск)

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

HOLD_THRESHOLD_SEC = 0.40  # Порог удержания для вызова строки Spotlight

class CopilotKeyHook:
    def __init__(
        self,
        on_click: Optional[Callable[[], None]] = None,
        on_hold: Optional[Callable[[], None]] = None,
        on_debug: Optional[Callable[[str], None]] = None,
        on_any_key: Optional[Callable[[int, str], None]] = None
    ):
        self.on_click = on_click
        self.on_hold = on_hold
        self.on_debug = on_debug
        self.on_any_key = on_any_key

        self._listener: Optional[keyboard.Listener] = None
        self._is_running = False

        self._press_start_time: Optional[float] = None
        self._hold_triggered = False
        self._timer: Optional[threading.Timer] = None
        self._copilot_last_seen = 0.0

    def _mask_win_key(self):
        """
        Нейтрализует открытие меню Пуск и поиска Windows.
        Использует vkFF (0xFF, стандарт AutoHotkey #MenuMaskKey),
        чтобы Windows пометила использование модификатора без открытия меню или поиска.
        """
        try:
            # 1. Посылаем dummy mask key vkFF (нажатие и отпускание)
            ctypes.windll.user32.keybd_event(VK_MASK, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_MASK, 0, KEYEVENTF_KEYUP, 0)
            # 2. Принудительно отпускаем Shift и Win, предотвращая вызов SearchHost
            ctypes.windll.user32.keybd_event(VK_LSHIFT, 0, KEYEVENTF_KEYUP, 0)
            ctypes.windll.user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
        except Exception:
            pass

    def dismiss_search_window(self):
        """Закрывает окно поиска Windows SearchHost при попытке всплытия."""
        try:
            ctypes.windll.user32.keybd_event(VK_ESCAPE, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
        except Exception:
            pass

    def _win32_event_filter(self, msg: int, data) -> bool:
        """
        Низкоуровневый фильтр событий клавиатуры Windows.
        Возврат False подавляет клавишу от передачи в Windows Shell.
        Возврат True пропускает клавишу в систему.
        """
        try:
            vk = data.vkCode

            # Логируем нажатие для диалогового тестера в UI
            if msg in (WM_KEYDOWN, WM_SYSKEYDOWN) and self.on_any_key:
                self.on_any_key(vk, hex(vk))

            now = time.time()

            # 1. Подавление физического отпускания LWin/LShift СТРОГО в течение 250 мс
            # после срабатывания комбинации Copilot, чтобы Windows не открывала поиск.
            # Обычное нажатие и отпускание физической клавиши Windows НИКОГДА не блокируется!
            if (now - self._copilot_last_seen) < 0.25:
                if vk in (VK_LWIN, VK_RWIN, VK_LSHIFT, 0x10):
                    if msg in (WM_KEYUP, WM_SYSKEYUP):
                        return False

            # 2. Аппаратный код клавиши Copilot (VK_F23 = 0x86 или 0x8E)
            if vk in (VK_F23, VK_F23_ALT):
                self._copilot_last_seen = now
                self._mask_win_key()

                if msg in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    if self.on_debug:
                        self.on_debug(f"Клавиша Copilot ({hex(vk)}) нажата")
                    if self._press_start_time is None:
                        self._press_start_time = time.time()
                        self._hold_triggered = False

                        def trigger_hold():
                            if self._press_start_time is not None:
                                self._hold_triggered = True
                                if self.on_hold:
                                    self.on_hold()

                        self._timer = threading.Timer(HOLD_THRESHOLD_SEC, trigger_hold)
                        self._timer.daemon = True
                        self._timer.start()

                    return False  # Блокируем клавишу от передачи в Windows

                elif msg in (WM_KEYUP, WM_SYSKEYUP):
                    self._mask_win_key()
                    if self.on_debug:
                        self.on_debug(f"Клавиша Copilot ({hex(vk)}) отпущена")
                    if self._timer:
                        self._timer.cancel()
                        self._timer = None

                    if self._press_start_time is not None:
                        dur = time.time() - self._press_start_time
                        self._press_start_time = None
                        if not self._hold_triggered and dur < HOLD_THRESHOLD_SEC:
                            if self.on_click:
                                self.on_click()

                    return False

            # 3. Обработка клавиши VK_APPS (Menu), если она зажата вместе с Win
            if vk == VK_APPS:
                win_down = (ctypes.windll.user32.GetKeyState(VK_LWIN) & 0x8000) or (ctypes.windll.user32.GetKeyState(VK_RWIN) & 0x8000)
                if win_down:
                    self._copilot_last_seen = now
                    self._mask_win_key()
                    if msg in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        if self.on_click:
                            self.on_click()
                    return False

            # 4. Обработка связки Win + Shift + C
            if vk == 0x43:  # 'C'
                win_down = (ctypes.windll.user32.GetKeyState(VK_LWIN) & 0x8000) or (ctypes.windll.user32.GetKeyState(VK_RWIN) & 0x8000)
                shift_down = (ctypes.windll.user32.GetKeyState(VK_LSHIFT) & 0x8000) or (ctypes.windll.user32.GetKeyState(0x10) & 0x8000)
                if win_down and shift_down:
                    self._copilot_last_seen = now
                    self._mask_win_key()
                    if msg in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        if self.on_click:
                            self.on_click()
                    return False

            # 4. Альтернативный горячий шорткат: Ctrl + Shift + J
            if vk == VK_KEY_J:
                ctrl_down = (ctypes.windll.user32.GetKeyState(VK_CONTROL) & 0x8000) or (ctypes.windll.user32.GetKeyState(0x11) & 0x8000)
                shift_down = (ctypes.windll.user32.GetKeyState(VK_LSHIFT) & 0x8000) or (ctypes.windll.user32.GetKeyState(0x10) & 0x8000)
                if ctrl_down and shift_down:
                    if msg in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        if self.on_click:
                            self.on_click()
                    return False

            return True
        except Exception:
            return True

    def start(self):
        """Запускает перехватчик событий клавиатуры."""
        if self._is_running:
            return
        self._is_running = True
        self._listener = keyboard.Listener(win32_event_filter=self._win32_event_filter)
        self._listener.start()

    def stop(self):
        """Останавливает перехватчик."""
        self._is_running = False
        if self._listener:
            self._listener.stop()
            self._listener = None
