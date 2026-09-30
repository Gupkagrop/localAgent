"""
Плавающий полупрозрачный индикатор статуса («пилюля») у нижнего края экрана.
Отображает статус записи («Слушаю...»), уровень голоса в виде неонового эквалайзера и распознаваемый текст.
"""
import math
from PyQt6.QtCore import Qt, QTimer, QPoint, QRectF, QPointF
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QGraphicsDropShadowEffect
from PyQt6.QtGui import (
    QColor, QFont, QGuiApplication, QCursor, QPainter,
    QBrush, QLinearGradient, QPen
)


class AudioWaveVisualizer(QWidget):
    """
    Анимированный спектральный эквалайзер в стиле Jarvis HUD (5 полос спектра).
    Отображает плавный динамический танец волн при звуках речи
    и мягкое гармоническое дыхание в тишине.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(38, 24)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._vu_level = 0.0
        self._phase = 0.0
        self._mode = "listening"  # "listening", "step", "executing", "error"

        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 FPS
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    def set_vu_level(self, level: float) -> None:
        """Передает текущий RMS уровень микрофона от 0.0 до 1.0."""
        self._vu_level = max(0.0, min(1.0, float(level)))

    def set_mode(self, mode: str) -> None:
        """Переключает цветовую схему спектра."""
        self._mode = mode
        self.update()

    def _on_tick(self) -> None:
        self._phase += 0.22
        if self._phase > 2 * math.pi:
            self._phase -= 2 * math.pi
        if self.isVisible():
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bar_count = 5
        bar_width = 3.5
        gap = 3.5
        total_width = bar_count * bar_width + (bar_count - 1) * gap
        start_x = (self.width() - total_width) / 2.0
        max_h = float(self.height() - 4)
        center_y = self.height() / 2.0

        # Цветовые темы
        if self._mode == "executing":
            color_top = QColor(52, 211, 153)    # Изумрудный светлый
            color_bot = QColor(16, 185, 129)    # Изумрудный темный
        elif self._mode == "error":
            color_top = QColor(248, 113, 113)   # Красный светлый
            color_bot = QColor(239, 68, 68)     # Красный темный
        elif self._mode == "step":
            color_top = QColor(56, 189, 248)    # Неоновый голубой
            color_bot = QColor(14, 165, 233)    # Лазурный
        else:
            # Режим listening: Неоновый циан Jarvis -> Фиолетовый градиент
            color_top = QColor(0, 240, 255)     # Neon Cyan
            color_bot = QColor(139, 92, 246)    # Violet

        # Симметричные коэффициенты высот для красивой дуговой формы
        multipliers = [0.45, 0.75, 1.0, 0.75, 0.45]

        for i in range(bar_count):
            wave_mod = 0.5 + 0.5 * math.sin(self._phase + i * 0.9)
            audio_factor = self._vu_level * 1.8
            h = 4.0 + (max_h - 4.0) * (0.25 * wave_mod + 0.75 * min(1.0, audio_factor)) * multipliers[i]
            h = max(3.5, min(max_h, h))

            x = start_x + i * (bar_width + gap)
            y = center_y - h / 2.0

            grad = QLinearGradient(x, y, x, y + h)
            grad.setColorAt(0.0, color_top)
            grad.setColorAt(1.0, color_bot)

            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, y, bar_width, h), 1.75, 1.75)


class FloatingPill(QWidget):
    """
    Плавающий HUD-индикатор у нижнего края экрана.
    Отображает спектральный анализатор голоса, статус и распознаваемый текст.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Окно без рамок, поверх всех окон, скрыто из панели задач
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.setFixedHeight(50)
        self.setMinimumWidth(280)

        # Стили границ и фона для различных состояний (Frosted Dark Glass)
        self._style_default = """
            QWidget {
                background-color: rgba(15, 23, 42, 235);
                border: 1.5px solid rgba(0, 240, 255, 60);
                border-radius: 25px;
            }
        """
        self._style_listening = """
            QWidget {
                background-color: rgba(15, 23, 42, 245);
                border: 1.5px solid rgba(0, 240, 255, 210);
                border-radius: 25px;
            }
        """
        self._style_executing = """
            QWidget {
                background-color: rgba(15, 23, 42, 245);
                border: 1.5px solid rgba(16, 185, 129, 210);
                border-radius: 25px;
            }
        """
        self._style_error = """
            QWidget {
                background-color: rgba(15, 23, 42, 245);
                border: 1.5px solid rgba(239, 68, 68, 210);
                border-radius: 25px;
            }
        """

        # Компоновка
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 6, 18, 6)
        layout.setSpacing(12)

        # Спектральный анализатор волны Jarvis
        self.wave = AudioWaveVisualizer(self)
        layout.addWidget(self.wave)

        # Скрытая точка активности для сохранения обратной совместимости
        self.dot = QLabel("●", self)
        self.dot.hide()

        # Текст распознанной фразы / статус
        self.label = QLabel("Слушаю...", self)
        self.label.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        self.label.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(self.label)

        # Мягкая неоновая тень для отделения от любого светлого или темного фона
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 240, 255, 70))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        self.setStyleSheet(self._style_default)
        self._mode = "idle"

        # Таймер скрытия
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._on_hide_timeout)

    def _on_hide_timeout(self) -> None:
        self._mode = "idle"
        self.hide()

    def _reposition(self) -> None:
        """Размещает пилюлю по центру внизу экрана, где находится курсор мыши."""
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            x = geom.x() + (geom.width() - self.width()) // 2
            y = geom.y() + geom.height() - 95  # 95px выше панели задач
            self.move(x, y)

    def update_vu(self, level: float) -> None:
        """Передает уровень громкости голоса в спектральный анализатор."""
        if not self.isVisible() or self._mode != "listening":
            return
        self.wave.set_vu_level(level)

    def show_listening(self) -> None:
        """Переводит индикатор в эстетичный режим прослушивания Jarvis."""
        self._mode = "listening"
        self._hide_timer.stop()
        self.setStyleSheet(self._style_listening)
        self.wave.set_mode("listening")
        self.label.setText("Слушаю...")
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()

    def update_text(self, text: str) -> None:
        """Обновляет распознанный текст прямо во время речи."""
        self._hide_timer.stop()
        display = text.strip() or "Слушаю..."
        if len(display) > 55:
            display = display[:52] + "..."
        self.label.setText(display)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()

    def show_step(self, step: int, max_steps: int, action_text: str) -> None:
        """Показывает текущий промежуточный шаг выполнения Vision-агента."""
        self._mode = "step"
        self._hide_timer.stop()
        self.setStyleSheet(self._style_listening)
        self.wave.set_mode("step")
        display = f"[{step}/{max_steps}] {action_text.strip()}"
        if len(display) > 58:
            display = display[:55] + "..."
        self.label.setText(display)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()

    def show_executing(self, action_name: str = "Выполняю...") -> None:
        """Показывает статус выполнения действия с изумрудным подтверждением."""
        self._mode = "executing"
        self.setStyleSheet(self._style_executing)
        self.wave.set_mode("executing")
        self.label.setText(action_name)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        self._hide_timer.start(2000)

    def show_error(self, message: str = "Не удалось распознать") -> None:
        """Показывает статус ошибки с рубиновой индикацией."""
        self._mode = "error"
        self.setStyleSheet(self._style_error)
        self.wave.set_mode("error")
        self.label.setText(message)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        self._hide_timer.start(2500)


class ClickIndicatorOverlay(QWidget):
    """
    Полупрозрачный оверлей маркера клика (пульсирующий круг).
    Показывает точное место действия Vision-агента на экране Windows.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.size_px = 64
        self.setFixedSize(self.size_px, self.size_px)

        self._current_step = 0
        self._max_steps = 10
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._animate_step)

    def show_click(self, screen_x: int, screen_y: int) -> None:
        """Показывает анимацию клика в экранных координатах с центрированием маркера."""
        half = self.size_px // 2
        self.move(int(screen_x - half), int(screen_y - half))
        self._current_step = 0
        self.show()
        self.raise_()
        self._timer.start()

    def _animate_step(self) -> None:
        self._current_step += 1
        if self._current_step >= self._max_steps:
            self._timer.stop()
            self.hide()
            return
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            progress = self._current_step / float(self._max_steps)
            radius = 8.0 + progress * 20.0
            alpha = int(240 * (1.0 - progress))

            center_x = self.width() / 2.0
            center_y = self.height() / 2.0

            # Внешнее пульсирующее кольцо
            pen = QPen(QColor(0, 240, 255, alpha))
            pen.setWidthF(2.5)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(0, 240, 255, int(alpha * 0.25))))
            painter.drawEllipse(QPointF(center_x, center_y), radius, radius)

            # Центральная точка клика
            center_pen = QPen(QColor(255, 255, 255, alpha))
            center_pen.setWidthF(1.5)
            painter.setPen(center_pen)
            painter.setBrush(QBrush(QColor(0, 240, 255, alpha)))
            painter.drawEllipse(QPointF(center_x, center_y), 4.0, 4.0)
        finally:
            painter.end()
