"""
QSS стили интерфейса Antigravity Voice (Fluent 2 Dark Theme).
Современная темная палитра Windows 11 с аккуратными скруглениями,
карточками компонентов и поддержкой масштабирования экранов.
"""

DARK_THEME_QSS = """
QMainWindow, QWidget#CentralWidget {
    background-color: #0F1012;
    color: #F3F4F6;
    font-family: 'Segoe UI Variable Display', 'Segoe UI', -apple-system, sans-serif;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QTabWidget::pane {
    border: 1px solid #23252B;
    background-color: #141519;
    border-radius: 12px;
    padding: 6px;
}

QTabBar::tab {
    background-color: transparent;
    color: #9CA3AF;
    padding: 8px 20px;
    margin-right: 6px;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
    border: 1px solid transparent;
}

QTabBar::tab:selected {
    background-color: #21232A;
    color: #FFFFFF;
    border: 1px solid #32353E;
}

QTabBar::tab:hover:!selected {
    background-color: #1A1B20;
    color: #E5E7EB;
}

QGroupBox {
    border: 1px solid #262830;
    border-radius: 10px;
    background-color: #16171C;
    margin-top: 14px;
    padding: 16px 14px 14px 14px;
    font-size: 13px;
    font-weight: 600;
    color: #E5E7EB;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    background-color: #141519;
    color: #9CA3AF;
    font-size: 12px;
}

QPushButton {
    background-color: #22242B;
    border: 1px solid #32353E;
    border-radius: 8px;
    color: #F3F4F6;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #2C2F38;
    border-color: #454955;
    color: #FFFFFF;
}

QPushButton:pressed {
    background-color: #1A1B20;
}

QPushButton#PrimaryButton {
    background-color: #2563EB;
    border: 1px solid #3B82F6;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background-color: #1D4ED8;
    border-color: #60A5FA;
}

QPushButton#PrimaryButton:pressed {
    background-color: #1E40AF;
}

QPushButton#CheckAllButton {
    background-color: #1D4ED8;
    border: 1px solid #3B82F6;
    color: #FFFFFF;
    font-weight: 600;
    font-size: 13px;
    padding: 9px 18px;
    border-radius: 8px;
}

QPushButton#CheckAllButton:hover {
    background-color: #2563EB;
    border-color: #60A5FA;
}

QPushButton#CheckAllButton:pressed {
    background-color: #1E40AF;
}

QPushButton#CheckAllButton:disabled {
    background-color: #1F2937;
    color: #6B7280;
    border-color: #374151;
}

QLineEdit {
    background-color: #1A1B20;
    border: 1px solid #32353E;
    border-radius: 8px;
    padding: 6px 12px;
    color: #F3F4F6;
    font-size: 13px;
}

QLineEdit:focus {
    border: 1px solid #3B82F6;
    background-color: #21232A;
}

QPushButton#SuccessButton {
    background-color: #059669;
    border: 1px solid #10B981;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton#SuccessButton:hover {
    background-color: #047857;
    border-color: #34D399;
}

QPushButton#DangerButton {
    background-color: #991B1B;
    border: 1px solid #DC2626;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton#DangerButton:hover {
    background-color: #B91C1C;
    border-color: #EF4444;
}

QRadioButton {
    color: #E5E7EB;
    font-size: 13px;
    spacing: 8px;
    padding: 4px 0;
}

QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border-radius: 9px;
    border: 1px solid #4B5563;
    background-color: #1A1B20;
}

QRadioButton::indicator:hover {
    border-color: #60A5FA;
}

QRadioButton::indicator:checked {
    border: 5px solid #3B82F6;
    background-color: #FFFFFF;
}

QCheckBox {
    color: #E5E7EB;
    font-size: 13px;
    spacing: 8px;
    padding: 3px 0;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #4B5563;
    border-radius: 4px;
    background-color: #1A1B20;
}

QCheckBox::indicator:hover {
    border-color: #60A5FA;
}

QCheckBox::indicator:checked {
    background-color: #2563EB;
    border: 1px solid #3B82F6;
}

QCheckBox::indicator:checked:hover {
    background-color: #1D4ED8;
    border-color: #60A5FA;
}

QComboBox {
    background-color: #1A1B20;
    border: 1px solid #32353E;
    border-radius: 8px;
    padding: 6px 12px;
    color: #F3F4F6;
    font-size: 13px;
}

QComboBox:hover {
    border-color: #454955;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #1A1B20;
    border: 1px solid #32353E;
    color: #F3F4F6;
    selection-background-color: #2563EB;
    padding: 4px;
    border-radius: 6px;
}

QProgressBar {
    background-color: #1A1B20;
    border: 1px solid #2B2D36;
    border-radius: 5px;
    text-align: center;
    color: transparent;
    height: 8px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #3B82F6);
    border-radius: 4px;
}

QTextEdit, QPlainTextEdit {
    background-color: #0A0B0E;
    border: 1px solid #202228;
    border-radius: 8px;
    color: #9CA3AF;
    font-family: 'Consolas', 'Cascadia Code', monospace;
    font-size: 12px;
    padding: 8px;
}

QScrollBar:vertical {
    border: none;
    background-color: transparent;
    width: 6px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #2C2F38;
    border-radius: 3px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background-color: #4B5563;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    border: none;
    background-color: transparent;
    height: 6px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #2C2F38;
    border-radius: 3px;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #4B5563;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
"""
