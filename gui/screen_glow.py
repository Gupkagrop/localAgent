"""
Контурная неоновая подсветка экрана (Screen Contour Glow Overlay).
Отображает стильную рамку по периметру экрана в стиле HUD Jarvis
во время работы автономного Vision-агента или выполнения сложных задач.
Полностью прозрачна для кликов мыши (WS_EX_TRANSPARENT) и работает в статическом
энергоэффективном режиме с нулевой нагрузкой на Windows DWM (0% CPU / GPU).
"""
from typing import Optional
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QLinearGradient,
    QFont, QGuiApplication, QCursor
)

try:
    import win32gui
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class ScreenGlowOverlay(QWidget):
    """
    Полноэкранный полупрозрачный оверлей со статичным неоновым контуром.
    Не перехватывает клики мыши, не забирает фокус и не производит лишних перерисовок.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # Безрамочное окно поверх всех окон, скрытое из панели задач
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._glow_color = QColor(0, 240, 255)  # Неоновый циан Jarvis
        self._status_text = "JARVIS • VISION AGENT ACTIVE"
        self._is_active = False

        self._setup_win32_passthrough()

    def _setup_win32_passthrough(self) -> None:
        """Настраивает расширенные стили Win32 для гарантированного сквозного клика."""
        if not HAS_WIN32:
            return
        try:
            hwnd = int(self.winId())
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                hwnd,
                win32con.GWL_EXSTYLE,
                ex_style | win32con.WS_EX_TRANSPARENT |
                win32con.WS_EX_LAYERED |
                win32con.WS_EX_NOACTIVATE |
                win32con.WS_EX_TOOLWINDOW
            )
        except Exception:
            pass

    def _reposition_to_active_screen(self) -> None:
        """Растягивает оверлей на весь активный монитор."""
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            self.setGeometry(geom)

    def is_active(self) -> bool:
        """Возвращает статус активности оверлея."""
        return self._is_active

    def start_glow(self, text: str = "JARVIS • VISION AGENT ACTIVE", color: Optional[QColor] = None) -> None:
        """Запускает отображение статического неонового контура (0% CPU оверхеда)."""
        if color:
            self._glow_color = color
        self._status_text = text
        self._is_active = True
        self._reposition_to_active_screen()
        self._setup_win32_passthrough()
        self.update()
        self.show()
        self.raise_()

    def stop_glow(self) -> None:
        """Скрывает оверлей."""
        self._is_active = False
        self.hide()

    def paintEvent(self, event) -> None:
        """Отрисовка четкого неонового контура, угловых скобок HUD и статус-бейджа."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())

        base_alpha = 230
        halo_alpha = 75

        glow_rgb = (self._glow_color.red(), self._glow_color.green(), self._glow_color.blue())
        halo_depth = 28.0

        # 1. Внутренний мягкий ореол (Glow Halo) по 4 сторонам
        top_grad = QLinearGradient(0, 0, 0, halo_depth)
        top_grad.setColorAt(0.0, QColor(*glow_rgb, halo_alpha))
        top_grad.setColorAt(1.0, QColor(*glow_rgb, 0))
        painter.fillRect(QRectF(0, 0, w, halo_depth), top_grad)

        bottom_grad = QLinearGradient(0, h, 0, h - halo_depth)
        bottom_grad.setColorAt(0.0, QColor(*glow_rgb, halo_alpha))
        bottom_grad.setColorAt(1.0, QColor(*glow_rgb, 0))
        painter.fillRect(QRectF(0, h - halo_depth, w, halo_depth), bottom_grad)

        left_grad = QLinearGradient(0, 0, halo_depth, 0)
        left_grad.setColorAt(0.0, QColor(*glow_rgb, halo_alpha))
        left_grad.setColorAt(1.0, QColor(*glow_rgb, 0))
        painter.fillRect(QRectF(0, 0, halo_depth, h), left_grad)

        right_grad = QLinearGradient(w, 0, w - halo_depth, 0)
        right_grad.setColorAt(0.0, QColor(*glow_rgb, halo_alpha))
        right_grad.setColorAt(1.0, QColor(*glow_rgb, 0))
        painter.fillRect(QRectF(w - halo_depth, 0, halo_depth, h), right_grad)

        # 2. Четкая внешняя граница периметра
        border_pen = QPen(QColor(*glow_rgb, base_alpha))
        border_pen.setWidthF(3.5)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(1.75, 1.75, w - 3.5, h - 3.5))

        # 3. Футуристичные угловые скобки HUD (Cyber Brackets)
        bracket_len = 36.0
        bracket_pen = QPen(QColor(255, 255, 255, 240))
        bracket_pen.setWidthF(4.0)
        painter.setPen(bracket_pen)

        # Верхний левый угол
        painter.drawLine(QPointF(4, 4), QPointF(4 + bracket_len, 4))
        painter.drawLine(QPointF(4, 4), QPointF(4, 4 + bracket_len))

        # Верхний правый угол
        painter.drawLine(QPointF(w - 4, 4), QPointF(w - 4 - bracket_len, 4))
        painter.drawLine(QPointF(w - 4, 4), QPointF(w - 4, 4 + bracket_len))

        # Нижний левый угол
        painter.drawLine(QPointF(4, h - 4), QPointF(4 + bracket_len, h - 4))
        painter.drawLine(QPointF(4, h - 4), QPointF(4, h - 4 - bracket_len))

        # Нижний правый угол
        painter.drawLine(QPointF(w - 4, h - 4), QPointF(w - 4 - bracket_len, h - 4))
        painter.drawLine(QPointF(w - 4, h - 4), QPointF(w - 4, h - 4 - bracket_len))

        # 4. Стильный верхний HUD-бейдж по центру
        badge_w = 280.0
        badge_h = 24.0
        badge_x = (w - badge_w) / 2.0
        badge_y = 6.0

        painter.setPen(QPen(QColor(*glow_rgb, 180), 1.5))
        painter.setBrush(QBrush(QColor(15, 23, 42, 220)))
        painter.drawRoundedRect(QRectF(badge_x, badge_y, badge_w, badge_h), 6.0, 6.0)

        # Текст внутри бейджа
        painter.setPen(QColor(255, 255, 255, 240))
        font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        painter.setFont(font)
        painter.drawText(
            QRectF(badge_x, badge_y, badge_w, badge_h),
            Qt.AlignmentFlag.AlignCenter,
            self._status_text
        )
