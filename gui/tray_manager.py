"""
Управление системным треем Windows (QSystemTrayIcon).
"""
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont

class TrayManager(QObject):
    show_window_requested = pyqtSignal()
    toggle_agent_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tray_icon = QSystemTrayIcon(parent)
        self._create_icon()
        self._create_menu()
        self.tray_icon.activated.connect(self._on_activated)

    def _create_icon(self):
        """Создает высококонтрастную иконку с логотипом Antigravity для системного трея."""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Синий круг с градиентом
        painter.setBrush(QColor("#2563EB"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(2, 2, 28, 28, 7, 7)

        # Буква 'A' по центру
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "A")
        painter.end()

        self.tray_icon.setIcon(QIcon(pixmap))
        self.tray_icon.setToolTip("Antigravity Voice")

    def _create_menu(self):
        self.menu = QMenu()
        self.menu.setStyleSheet("""
            QMenu {
                background-color: #1E1F24;
                color: #EDEDED;
                border: 1px solid #2F3138;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #27282D;
            }
            QMenu::separator {
                height: 1px;
                background-color: #2F3138;
                margin: 4px 8px;
            }
        """)

        self.action_show = self.menu.addAction("Открыть панель управления")
        self.action_show.triggered.connect(self.show_window_requested.emit)

        self.menu.addSeparator()

        self.status_action = self.menu.addAction("Статус: Работает")
        self.status_action.setEnabled(False)

        self.action_toggle = self.menu.addAction("Остановить ассистента")
        self.action_toggle.triggered.connect(self.toggle_agent_requested.emit)

        self.menu.addSeparator()

        self.action_exit = self.menu.addAction("Выход из приложения")
        self.action_exit.triggered.connect(self.exit_requested.emit)

        self.tray_icon.setContextMenu(self.menu)

    def _on_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick
        ):
            self.show_window_requested.emit()

    def update_status(self, is_running: bool):
        if is_running:
            self.status_action.setText("Статус: Активен")
            self.action_toggle.setText("Остановить ассистента (освободить VRAM)")
        else:
            self.status_action.setText("Статус: Остановлен (0 МБ VRAM)")
            self.action_toggle.setText("Запустить ассистента")

    def show(self):
        self.tray_icon.show()

    def show_message(self, title: str, text: str):
        self.tray_icon.showMessage(title, text, QSystemTrayIcon.MessageIcon.Information, 2500)
