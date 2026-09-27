"""
Плавающий полупрозрачный индикатор статуса («пилюля») у нижнего края экрана.
Отображает статус записи («Слушаю...»), уровень голоса и распознаваемый текст.
"""
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QCursor

class FloatingPill(QWidget):
    def __init__(self, parent=None):
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
        self.setMinimumWidth(260)

        # Компоновка
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 6, 18, 6)
        layout.setSpacing(12)

        # Индикатор (точка активности)
        self.dot = QLabel("●", self)
        self.dot.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.dot.setStyleSheet("color: #3B82F6;")
        layout.addWidget(self.dot)

        # Текст распознанной фразы / статус
        self.label = QLabel("Слушаю...", self)
        self.label.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        self.label.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(self.label)

        # Тень для красивого отделения от фона любого приложения
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        self.setStyleSheet("""
            QWidget {
                background-color: rgba(18, 19, 22, 235);
                border: 1px solid rgba(255, 255, 255, 35);
                border-radius: 25px;
            }
        """)

        self._mode = "idle"

        # Таймер скрытия
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._on_hide_timeout)

    def _on_hide_timeout(self) -> None:
        self._mode = "idle"
        self.hide()

    def _reposition(self):
        """Размещает пилюлю по центру внизу экрана, где находится курсор мыши."""
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            x = geom.x() + (geom.width() - self.width()) // 2
            y = geom.y() + geom.height() - 95  # 95px выше панели задач
            self.move(x, y)

    def update_vu(self, level: float) -> None:
        """Обновляет пульсацию точки активности в зависимости от уровня громкости голоса."""
        if not self.isVisible() or self._mode != "listening":
            return
        lvl = max(0.0, min(1.0, float(level)))
        if lvl > 0.6:
            color = "#93C5FD"
            size = 16
        elif lvl > 0.2:
            color = "#60A5FA"
            size = 15
        else:
            color = "#3B82F6"
            size = 14
        self.dot.setFont(QFont("Segoe UI", size, QFont.Weight.Bold))
        self.dot.setStyleSheet(f"color: {color};")

    def show_listening(self):
        """Переводит индикатор в режим прослушивания."""
        self._mode = "listening"
        self._hide_timer.stop()
        self.dot.setStyleSheet("color: #3B82F6;")  # Синий пульс
        self.label.setText("Слушаю...")
        self.adjustSize()
        self._reposition()
        self.show()

    def update_text(self, text: str):
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
        self.dot.setStyleSheet("color: #38BDF8;")  # Неоновый голубой (активное действие агента)
        display = f"[{step}/{max_steps}] {action_text.strip()}"
        if len(display) > 58:
            display = display[:55] + "..."
        self.label.setText(display)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()

    def show_executing(self, action_name: str = "Выполняю..."):
        """Показывает статус выполнения действия."""
        self._mode = "executing"
        self.dot.setStyleSheet("color: #10B981;")  # Зеленый свет
        self.label.setText(action_name)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        self._hide_timer.start(2000)  # Скрываем через 2.0 сек после завершения

    def show_error(self, message: str = "Не удалось распознать"):
        """Показывает статус ошибки."""
        self._mode = "error"
        self.dot.setStyleSheet("color: #EF4444;")  # Красный свет
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

    def __init__(self, parent=None) -> None:
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
        """Показывает анимацию клика в координатах экрана с учетом High DPI масштабирования."""
        screen = QGuiApplication.screenAt(QPoint(int(screen_x), int(screen_y))) or QGuiApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0
        logical_x = screen_x / dpr
        logical_y = screen_y / dpr
        half = self.size_px // 2
        self.move(int(logical_x - half), int(logical_y - half))
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
        from PyQt6.QtGui import QPainter, QPen, QBrush
        from PyQt6.QtCore import QPointF

        painter = QPainter(self)
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

