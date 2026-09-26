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

        # Таймер скрытия
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def _reposition(self):
        """Размещает пилюлю по центру внизу экрана, где находится курсор мыши."""
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            x = geom.x() + (geom.width() - self.width()) // 2
            y = geom.y() + geom.height() - 95  # 95px выше панели задач
            self.move(x, y)

    def show_listening(self):
        """Переводит индикатор в режим прослушивания."""
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

    def show_executing(self, action_name: str = "Выполняю..."):
        """Показывает статус выполнения действия."""
        self.dot.setStyleSheet("color: #10B981;")  # Зеленый свет
        self.label.setText(action_name)
        self.adjustSize()
        self._reposition()
        self._hide_timer.start(1600)  # Скрываем через 1.6 сек после завершения

    def show_error(self, message: str = "Не удалось распознать"):
        """Показывает статус ошибки."""
        self.dot.setStyleSheet("color: #EF4444;")  # Красный свет
        self.label.setText(message)
        self.adjustSize()
        self._reposition()
        self._hide_timer.start(2000)
