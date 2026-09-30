"""
Управление системным треем Windows (QSystemTrayIcon) с динамической индикацией статусов.
"""
from typing import Literal
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont

TrayState = Literal["idle", "listening", "working", "stopped"]


class TrayManager(QObject):
    show_window_requested = pyqtSignal()
    spotlight_requested = pyqtSignal()
    toggle_agent_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.tray_icon = QSystemTrayIcon(parent)

        self._current_state: TrayState = "idle"
        self._pulse_phase: int = 0

        # Таймер пульсации для анимированных состояний (listening / working)
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(250)
        self._anim_timer.timeout.connect(self._on_anim_tick)

        self._create_menu()
        self._render_icon()
        self.set_state("idle")
        self.tray_icon.activated.connect(self._on_activated)

    def _create_menu(self) -> None:
        """Создает контекстное меню системного трея."""
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

        self.action_spotlight = self.menu.addAction("🔍 Открыть строку Spotlight (Alt+Space)")
        self.action_spotlight.triggered.connect(self.spotlight_requested.emit)

        self.menu.addSeparator()

        self.status_action = self.menu.addAction("Статус: Активен (Готов)")
        self.status_action.setEnabled(False)

        self.action_toggle = self.menu.addAction("Остановить ассистента (освободить VRAM)")
        self.action_toggle.triggered.connect(self.toggle_agent_requested.emit)

        self.menu.addSeparator()

        self.action_exit = self.menu.addAction("Выход из приложения")
        self.action_exit.triggered.connect(self._on_exit_requested)

        self.tray_icon.setContextMenu(self.menu)

    def _render_icon(self) -> None:
        """Отрисовывает динамическую иконку 32x32 в зависимости от текущего состояния."""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Выбор цветовой палитры основы и текста
        if self._current_state == "stopped":
            base_color = QColor("#374151")
            text_color = QColor("#9CA3AF")
        else:
            base_color = QColor("#2563EB")
            text_color = QColor("#FFFFFF")

        # Фоновый закругленный квадрат
        painter.setBrush(base_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(2, 2, 28, 28, 7, 7)

        # Буква 'A' по центру
        painter.setPen(text_color)
        painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "A")

        # Определение параметров индикатора статуса в правом нижнем углу
        dot_color = QColor("#22C55E")
        radius = 3.5

        if self._current_state == "idle":
            dot_color = QColor("#22C55E")
            radius = 3.5
        elif self._current_state == "listening":
            dot_color = QColor("#EF4444") if self._pulse_phase == 0 else QColor("#F87171")
            radius = 3.5 if self._pulse_phase == 0 else 4.5
        elif self._current_state == "working":
            dot_color = QColor("#A855F7") if self._pulse_phase == 0 else QColor("#38BDF8")
            radius = 3.5 if self._pulse_phase == 0 else 4.5
        elif self._current_state == "stopped":
            dot_color = QColor("#6B7280")
            radius = 3.0

        center_x = 24.0
        center_y = 24.0

        # Контур индикатора (темный для контраста)
        painter.setBrush(QColor("#1E1F24"))
        painter.drawEllipse(
            int(center_x - radius - 1.2),
            int(center_y - radius - 1.2),
            int((radius + 1.2) * 2),
            int((radius + 1.2) * 2)
        )

        # Сам цветной индикатор
        painter.setBrush(dot_color)
        painter.drawEllipse(
            int(center_x - radius),
            int(center_y - radius),
            int(radius * 2),
            int(radius * 2)
        )

        painter.end()
        self.tray_icon.setIcon(QIcon(pixmap))

    def _on_anim_tick(self) -> None:
        """Шаг таймера анимации пульсирующего индикатора."""
        self._pulse_phase = 1 if self._pulse_phase == 0 else 0
        self._render_icon()

    def set_state(self, state: TrayState | str) -> None:
        """Устанавливает динамическое состояние трея: idle, listening, working, stopped."""
        normalized: TrayState = "idle"
        raw_state = state.lower().strip()
        if raw_state in ("idle", "listening", "working", "stopped"):
            normalized = raw_state  # type: ignore[assignment]

        self._current_state = normalized

        if normalized == "idle":
            if self._anim_timer.isActive():
                self._anim_timer.stop()
            self._pulse_phase = 0
            self.tray_icon.setToolTip("Antigravity Voice: Готов к работе")
            self.status_action.setText("Статус: Активен (Готов)")
            self.action_toggle.setText("Остановить ассистента (освободить VRAM)")
        elif normalized == "listening":
            self.tray_icon.setToolTip("Antigravity Voice: Запись речи...")
            self.status_action.setText("Статус: Запись речи...")
            self.action_toggle.setText("Остановить ассистента (освободить VRAM)")
            if not self._anim_timer.isActive():
                self._anim_timer.start()
        elif normalized == "working":
            self.tray_icon.setToolTip("Antigravity Voice: Vision-агент анализирует экран...")
            self.status_action.setText("Статус: Анализ экрана...")
            self.action_toggle.setText("Остановить ассистента (освободить VRAM)")
            if not self._anim_timer.isActive():
                self._anim_timer.start()
        elif normalized == "stopped":
            if self._anim_timer.isActive():
                self._anim_timer.stop()
            self._pulse_phase = 0
            self.tray_icon.setToolTip("Antigravity Voice: Остановлен (0 МБ VRAM)")
            self.status_action.setText("Статус: Остановлен (0 МБ VRAM)")
            self.action_toggle.setText("Запустить ассистента")

        self._render_icon()

    def update_status(self, is_running: bool) -> None:
        """Обновляет статус ассистента (активен/остановлен)."""
        self.set_state("idle" if is_running else "stopped")

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick
        ):
            self.show_window_requested.emit()

    def _on_exit_requested(self) -> None:
        self.stop()
        self.exit_requested.emit()

    def stop(self) -> None:
        """Останавливает таймеры анимации."""
        if self._anim_timer.isActive():
            self._anim_timer.stop()

    def show(self) -> None:
        self.tray_icon.show()

    def show_message(self, title: str, text: str) -> None:
        self.tray_icon.showMessage(title, text, QSystemTrayIcon.MessageIcon.Information, 2500)
