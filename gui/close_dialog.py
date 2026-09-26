"""
Модальный диалог подтверждения при закрытии окна («Свернуть в трей» vs «Закрыть совсем»).
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QCheckBox, QButtonGroup
)
from PyQt6.QtGui import QFont

class CloseConfirmDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Закрытие Antigravity Voice")
        self.setFixedSize(400, 220)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.setStyleSheet("""
            QDialog {
                background-color: #18191E;
                color: #EDEDED;
            }
            QLabel {
                color: #EDEDED;
            }
            QRadioButton {
                color: #D1D5DB;
                font-size: 13px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("Куда направить приложение?", self)
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        self.radio_group = QButtonGroup(self)
        
        self.rb_tray = QRadioButton("Свернуть в трей (продолжать работу в фоне)", self)
        self.rb_tray.setChecked(True)
        self.radio_group.addButton(self.rb_tray)
        layout.addWidget(self.rb_tray)

        self.rb_exit = QRadioButton("Выйти из приложения полностью", self)
        self.radio_group.addButton(self.rb_exit)
        layout.addWidget(self.rb_exit)

        self.cb_remember = QCheckBox("Запомнить мой выбор (можно сбросить в настройках)", self)
        self.cb_remember.setFont(QFont("Segoe UI", 11))
        self.cb_remember.setStyleSheet("color: #9CA3AF; margin-top: 4px;")
        layout.addWidget(self.cb_remember)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Отмена", self)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_ok = QPushButton("Подтвердить", self)
        self.btn_ok.setObjectName("PrimaryButton")
        self.btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_ok)

        layout.addLayout(btn_row)

    def get_result(self) -> tuple[str, bool]:
        """Возвращает ('tray' или 'exit', remember_choice: bool)."""
        action = "tray" if self.rb_tray.isChecked() else "exit"
        remember = self.cb_remember.isChecked()
        return action, remember
