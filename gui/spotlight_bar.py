"""
Плавающая поисковая строка Spotlight для текстового ввода команд (при удержании клавиши Copilot или Alt+Space).
Появляется по центру активного монитора с поддержкой автодополнения (live auto-suggestions), истории и подсказок.
"""
import os
import json
import sys
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QPushButton, QGraphicsDropShadowEffect,
    QListWidget, QListWidgetItem
)
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QGuiApplication, QCursor


class SpotlightLineEdit(QLineEdit):
    """Поле ввода с перехватом клавиш навигации (Вверх / Вниз) и Esc."""
    up_pressed = pyqtSignal()
    down_pressed = pyqtSignal()
    esc_pressed = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
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
    """Плавающая панель поиска команд Spotlight с живыми автоподсказками."""
    command_submitted = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
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

        # Загрузка словаря команд для автодополнения
        self._known_commands: list[str] = self._load_command_dictionary()

        # Главный макет окна
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(10)

        # Контейнер визуального стиля
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
        self.line_edit.up_pressed.connect(self._on_up_pressed)
        self.line_edit.down_pressed.connect(self._on_down_pressed)
        self.line_edit.esc_pressed.connect(self.hide)
        self.line_edit.textChanged.connect(self._on_text_changed)
        input_row.addWidget(self.line_edit)

        container_layout.addLayout(input_row)

        # Разделитель
        self.sep = QWidget(self.container)
        self.sep.setFixedHeight(1)
        self.sep.setStyleSheet("background-color: rgba(255, 255, 255, 15); border: none;")
        container_layout.addWidget(self.sep)

        # Выпадающий список живых автоподсказок
        self.list_suggestions = QListWidget(self.container)
        self.list_suggestions.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_suggestions.setCursor(Qt.CursorShape.PointingHandCursor)
        self.list_suggestions.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_suggestions.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_suggestions.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
                color: #EDEDED;
            }
            QListWidget::item {
                background-color: rgba(255, 255, 255, 6);
                border: 1px solid rgba(255, 255, 255, 12);
                border-radius: 8px;
                padding: 6px 12px;
                margin-bottom: 3px;
                color: #D4D4D8;
                font-size: 13px;
                font-family: 'Segoe UI', sans-serif;
            }
            QListWidget::item:selected {
                background-color: #2563EB;
                border: 1px solid #3B82F6;
                color: #FFFFFF;
            }
            QListWidget::item:hover:!selected {
                background-color: rgba(255, 255, 255, 18);
                color: #FFFFFF;
            }
        """)
        self.list_suggestions.itemClicked.connect(self._on_suggestion_clicked)
        self.list_suggestions.hide()
        container_layout.addWidget(self.list_suggestions)

        # Контейнер нижней строки: Подсказки частых команд (чипы)
        self.hints_container = QWidget(self.container)
        self.hints_container.setStyleSheet("background: transparent; border: none;")
        hints_row = QHBoxLayout(self.hints_container)
        hints_row.setContentsMargins(0, 0, 0, 0)
        hints_row.setSpacing(8)

        hint_title = QLabel("Подсказки:", self.hints_container)
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
            btn = QPushButton(title, self.hints_container)
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
        container_layout.addWidget(self.hints_container)

        layout.addWidget(self.container)

        # Эффект тени
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setColor(QColor(0, 0, 0, 220))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)

    def _load_command_dictionary(self) -> list[str]:
        """Загружает базу известных команд из config/commands.json и системных фраз."""
        commands: list[str] = [
            "Сделай громкость 50%",
            "Сверни все окна",
            "Включи видео ...",
            "Открой Antigravity",
            "Новый чат в Antigravity",
            "Запусти Antigravity CLI",
            "Сделай потише",
            "Сделай громче",
            "Выключи звук",
            "Пауза",
        ]

        cfg_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config",
            "commands.json"
        )
        if not os.path.exists(cfg_path):
            return commands

        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for app in data.get("apps", {}).keys():
                phrase = f"Открой {app}"
                if phrase.lower() not in [c.lower() for c in commands]:
                    commands.append(phrase)

            for url_name in data.get("urls", {}).keys():
                phrase = f"Открой {url_name}"
                if phrase.lower() not in [c.lower() for c in commands]:
                    commands.append(phrase)
        except Exception as e:
            print(f"[SpotlightBar] Ошибка загрузки словаря команд из {cfg_path}: {e}", file=sys.stderr)

        return commands

    def show_spotlight(self) -> None:
        """Отображает Spotlight по центру экрана, где сейчас находится курсор мыши."""
        self.line_edit.clear()
        self.history_index = len(self.history)
        self.list_suggestions.clear()
        self.list_suggestions.hide()
        self.hints_container.show()
        self.sep.show()
        self.adjustSize()

        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            x = geom.x() + (geom.width() - self.width()) // 2
            y = geom.y() + (geom.height() - self.height()) // 2 - 80
            self.move(x, y)

        self.show()
        self.activateWindow()
        self.line_edit.setFocus()

    def _on_text_changed(self, text: str) -> None:
        """Динамическая фильтрация подсказок при вводе текста."""
        query = text.strip().lower()
        if not query:
            self.list_suggestions.clear()
            self.list_suggestions.hide()
            self.hints_container.show()
            self.sep.show()
            self.adjustSize()
            return

        # Фильтруем до 5 совпадений (сначала начинающиеся с запроса, затем содержащие)
        starts = [c for c in self._known_commands if c.lower().startswith(query)]
        contains = [c for c in self._known_commands if query in c.lower() and not c.lower().startswith(query)]
        matches = (starts + contains)[:5]

        self.list_suggestions.clear()
        if matches:
            for cmd in matches:
                self.list_suggestions.addItem(QListWidgetItem(cmd))
            item_height = 36
            total_height = min(len(matches) * item_height + 6, 190)
            self.list_suggestions.setFixedHeight(total_height)
            self.list_suggestions.setCurrentRow(-1)
            self.hints_container.hide()
            self.list_suggestions.show()
            self.sep.show()
        else:
            self.list_suggestions.hide()
            self.hints_container.hide()
            self.sep.hide()

        self.adjustSize()

    def _on_up_pressed(self) -> None:
        """Обработка стрелки Вверх: навигация по подсказкам или истории."""
        if self.list_suggestions.isVisible() and self.list_suggestions.count() > 0:
            count = self.list_suggestions.count()
            row = self.list_suggestions.currentRow()
            if row > 0:
                self.list_suggestions.setCurrentRow(row - 1)
            elif row == 0:
                self.list_suggestions.setCurrentRow(-1)
            else:
                self.list_suggestions.setCurrentRow(count - 1)
            return

        self._prev_history()

    def _on_down_pressed(self) -> None:
        """Обработка стрелки Вниз: навигация по подсказкам или истории."""
        if self.list_suggestions.isVisible() and self.list_suggestions.count() > 0:
            count = self.list_suggestions.count()
            row = self.list_suggestions.currentRow()
            if row < count - 1:
                self.list_suggestions.setCurrentRow(row + 1)
            else:
                self.list_suggestions.setCurrentRow(0)
            return

        self._next_history()

    def _on_suggestion_clicked(self, item: QListWidgetItem) -> None:
        """Обработка клика мыши по подсказке."""
        if not item:
            return
        text = item.text().strip()
        if text.endswith("..."):
            prefix = text.replace("...", "").strip() + " "
            self.line_edit.setText(prefix)
            self.line_edit.setFocus()
            self.line_edit.setCursorPosition(len(prefix))
            return
        self._set_and_submit(text)

    def _set_and_submit(self, text: str) -> None:
        """Устанавливает текст и выполняет отправку команды."""
        self.line_edit.setText(text)
        self._on_enter()

    def _on_enter(self) -> None:
        """Выполнение выбранной или введенной команды при нажатии Enter."""
        text = ""
        if self.list_suggestions.isVisible() and self.list_suggestions.currentRow() >= 0:
            item = self.list_suggestions.currentItem()
            if item:
                text = item.text().strip()

        if not text:
            text = self.line_edit.text().strip()

        if not text:
            return

        if text.endswith("..."):
            prefix = text.replace("...", "").strip() + " "
            self.line_edit.setText(prefix)
            self.line_edit.setFocus()
            self.line_edit.setCursorPosition(len(prefix))
            return

        if not self.history or self.history[-1] != text:
            self.history.append(text)
        self.command_submitted.emit(text)
        self.hide()

    def _prev_history(self) -> None:
        """Переход к предыдущей команде в истории."""
        if not self.history:
            return
        if self.history_index > 0:
            self.history_index -= 1
            self.line_edit.setText(self.history[self.history_index])

    def _next_history(self) -> None:
        """Переход к следующей команде в истории."""
        if not self.history:
            return
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.line_edit.setText(self.history[self.history_index])
        else:
            self.history_index = len(self.history)
            self.line_edit.clear()
