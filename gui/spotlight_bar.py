"""
Плавающая поисковая строка Spotlight для текстового ввода команд (при удержании клавиши Copilot).
Появляется по центру активного монитора с поддержкой истории и подсказок.
"""
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QPushButton, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QGuiApplication, QCursor

class SpotlightLineEdit(QLineEdit):
    """Поле ввода с перехватом клавиш истории (Вверх / Вниз) и Esc."""
    up_pressed = pyqtSignal()
    down_pressed = pyqtSignal()
    esc_pressed = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Up:
            self.up_pressed.emit()
            return
        if event.key() == Qt.Key.Key_Down:
            self.down_pressed.emit()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.esc_pressed.emit()
            return
        super().keyPressEvent(event)

class SpotlightBar(QWidget):
    command_submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.setFixedWidth(640)
        self.history: list[str] = []
        self.history_index: int = -1

        # Главный макет
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(10)

        # Контейнер стиля
        self.container = QWidget(self)
        self.container.setStyleSheet("""
            QWidget {
                background-color: rgba(18, 19, 23, 245);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 16px;
            }
        """)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(16, 14, 16, 14)
        container_layout.setSpacing(10)

        # Верхняя строка: Иконка + Поле ввода
        input_row = QHBoxLayout()
        input_row.setSpacing(12)

        icon_label = QLabel("✨", self.container)
        icon_label.setFont(QFont("Segoe UI Emoji", 14))
        icon_label.setStyleSheet("border: none; background: transparent;")
        input_row.addWidget(icon_label)

        self.line_edit = SpotlightLineEdit(self.container)
        self.line_edit.setFont(QFont("Segoe UI", 13))
        self.line_edit.setPlaceholderText("Введите команду для Antigravity или системы... (Esc для отмены)")
        self.line_edit.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #FFFFFF;
                padding: 4px;
            }
            QLineEdit::placeholder {
                color: #71717A;
            }
        """)
        self.line_edit.returnPressed.connect(self._on_enter)
        self.line_edit.up_pressed.connect(self._prev_history)
        self.line_edit.down_pressed.connect(self._next_history)
        self.line_edit.esc_pressed.connect(self.hide)
        input_row.addWidget(self.line_edit)

        container_layout.addLayout(input_row)

        # Разделитель
        sep = QWidget(self.container)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255, 255, 255, 15); border: none;")
        container_layout.addWidget(sep)

        # Нижняя строка: Подсказки частых команд
        hints_row = QHBoxLayout()
        hints_row.setSpacing(8)

        hint_title = QLabel("Подсказки:", self.container)
        hint_title.setFont(QFont("Segoe UI", 10))
        hint_title.setStyleSheet("color: #71717A; border: none; background: transparent;")
        hints_row.addWidget(hint_title)

        chips = [
            ("Antigravity GUI", "Открой Antigravity"),
            ("Antigravity CLI", "Запусти Antigravity CLI"),
            ("Громкость 40%", "Громкость 40%"),
            ("YouTube", "Открой ютуб")
        ]

        for title, cmd_text in chips:
            btn = QPushButton(title, self.container)
            btn.setFont(QFont("Segoe UI", 10))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 12);
                    border: 1px solid rgba(255, 255, 255, 18);
                    border-radius: 6px;
                    color: #A1A1AA;
                    padding: 3px 8px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 24);
                    color: #FFFFFF;
                }
            """)
            btn.clicked.connect(lambda _, t=cmd_text: self._set_and_submit(t))
            hints_row.addWidget(btn)

        hints_row.addStretch()
        container_layout.addLayout(hints_row)

        layout.addWidget(self.container)

        # Тень
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setColor(QColor(0, 0, 0, 220))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)

    def show_spotlight(self):
        """Отображает Spotlight по центру экрана, где сейчас находится курсор мыши."""
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            x = geom.x() + (geom.width() - self.width()) // 2
            y = geom.y() + (geom.height() - self.height()) // 2 - 80
            self.move(x, y)

        self.line_edit.clear()
        self.history_index = len(self.history)
        self.show()
        self.activateWindow()
        self.line_edit.setFocus()

    def _set_and_submit(self, text: str):
        self.line_edit.setText(text)
        self._on_enter()

    def _on_enter(self):
        text = self.line_edit.text().strip()
        if text:
            if not self.history or self.history[-1] != text:
                self.history.append(text)
            self.command_submitted.emit(text)
        self.hide()

    def _prev_history(self):
        if not self.history:
            return
        if self.history_index > 0:
            self.history_index -= 1
            self.line_edit.setText(self.history[self.history_index])

    def _next_history(self):
        if not self.history:
            return
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.line_edit.setText(self.history[self.history_index])
        else:
            self.history_index = len(self.history)
            self.line_edit.clear()
