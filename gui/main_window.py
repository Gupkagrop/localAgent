"""
Главное окно управления Antigravity Voice (PyQt6 Fluent 2 Dark).
Оснащено удобной QScrollArea (без обрезания контента на экранах с любым масштабированием),
интерактивными карточками проверки компонентов системы, тестером клавиши Copilot
и панелью контроля видеопамяти (VRAM).
"""
import os
import json
import winreg
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QCheckBox, QComboBox, QProgressBar,
    QPlainTextEdit, QGroupBox, QRadioButton, QButtonGroup, QMessageBox,
    QFrame, QScrollArea, QGridLayout, QLineEdit, QSpinBox
)
from PyQt6.QtGui import QFont, QCloseEvent

from gui.styles import DARK_THEME_QSS
from gui.close_dialog import CloseConfirmDialog

class MainWindow(QMainWindow):
    agent_toggle_requested = pyqtSignal(bool)
    mic_changed = pyqtSignal(int)
    settings_changed = pyqtSignal(dict)
    app_exit_requested = pyqtSignal()
    test_mic_requested = pyqtSignal()
    test_sound_requested = pyqtSignal()
    test_stt_requested = pyqtSignal()
    download_llm_requested = pyqtSignal()
    check_all_systems_requested = pyqtSignal()

    def __init__(self, config_path: str, parent=None):
        super().__init__(parent)
        self.config_path = config_path
        self.settings = self._load_settings()

        self.setWindowTitle("Antigravity Voice & Vision • Панель управления")
        self.resize(840, 700)
        self.setMinimumSize(720, 520)

        self._setup_ui()
        self.setStyleSheet(DARK_THEME_QSS)

    def _load_settings(self) -> dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "autostart_with_windows": False,
            "start_minimized": False,
            "close_behavior": "ask",
            "default_activation_mode": "copilot_only",
            "wake_word_enabled": False,
            "wake_word": "джарвис",
            "audio_ducking_enabled": True,
            "sound_cues_enabled": True,
            "tts_enabled": False
        }

    def save_settings(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            self.settings_changed.emit(self.settings)
        except Exception as e:
            self.log(f"Ошибка сохранения настроек: {e}")

    def _setup_ui(self):
        central_widget = QWidget(self)
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # 1. Шапка (Header)
        header_row = QHBoxLayout()
        
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_label = QLabel("Antigravity Voice", self)
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #FFFFFF;")
        
        subtitle = QLabel("Локальный голосовой ассистент • NVIDIA GeForce RTX 5050", self)
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet("color: #9CA3AF;")
        
        title_box.addWidget(title_label)
        title_box.addWidget(subtitle)
        header_row.addLayout(title_box)
        header_row.addStretch()

        # Индикатор статуса (Badge)
        self.status_badge = QLabel("🟢 АКТИВЕН", self)
        self.status_badge.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.status_badge.setStyleSheet("""
            background-color: #064E3B;
            color: #34D399;
            border: 1px solid #059669;
            border-radius: 12px;
            padding: 5px 14px;
        """)
        header_row.addWidget(self.status_badge)

        # Кнопка Запуск / Остановка
        self.btn_toggle_agent = QPushButton("Остановить ассистента", self)
        self.btn_toggle_agent.setObjectName("DangerButton")
        self.btn_toggle_agent.clicked.connect(self._on_toggle_agent_clicked)
        header_row.addWidget(self.btn_toggle_agent)

        main_layout.addLayout(header_row)

        # 2. Вкладки (Tabs)
        self.tabs = QTabWidget(self)

        # --- Вкладка 1: Панель управления ---
        tab_control_scroll = QScrollArea(self)
        tab_control_scroll.setWidgetResizable(True)
        tab_control_content = QWidget()
        ctrl_layout = QVBoxLayout(tab_control_content)
        ctrl_layout.setContentsMargins(10, 10, 10, 10)
        ctrl_layout.setSpacing(14)

        # Блок наглядного статуса компонентов (System Health Panel)
        health_box = QGroupBox("Состояние и диагностика компонентов системы", tab_control_content)
        health_layout = QVBoxLayout(health_box)
        health_layout.setSpacing(10)

        # Сетка карточек статуса (2 ряда)
        grid_cards = QGridLayout()
        grid_cards.setSpacing(10)

        # Карточка 1: Микрофон
        self.card_mic = self._create_status_card("🎙 Микрофон", "Подключен", "#34D399")
        grid_cards.addWidget(self.card_mic, 0, 0)

        # Карточка 2: Клавиша Copilot
        self.card_key = self._create_status_card("⌨ Кнопка Copilot", "Хук активен (F23)", "#34D399")
        grid_cards.addWidget(self.card_key, 0, 1)

        # Карточка 3: Распознавание речи STT
        self.card_stt = self._create_status_card("🧠 Faster-Whisper", "Turbo (RTX 5050)", "#34D399")
        grid_cards.addWidget(self.card_stt, 0, 2)

        # Карточка 4: Модуль ИИ
        self.card_ai = self._create_status_card("🤖 Vision-агент", "Jedi-3B (Always-Warm)", "#34D399")
        grid_cards.addWidget(self.card_ai, 1, 0)

        # Карточка 5: Видеопамять VRAM
        self.card_vram = self._create_status_card("⚡ Расход VRAM", "~4.7 ГБ (RTX 5050)", "#60A5FA")
        grid_cards.addWidget(self.card_vram, 1, 1)

        # Карточка 6: Antigravity IDE
        self.card_ide = self._create_status_card("🚀 Antigravity", "GUI + CLI готовы", "#34D399")
        grid_cards.addWidget(self.card_ide, 1, 2)

        health_layout.addLayout(grid_cards)

        # Главная кнопка комплексной проверки всех систем
        self.btn_check_all_systems = QPushButton("⚡ Проверить все системы (Комплексная диагностика)", health_box)
        self.btn_check_all_systems.setObjectName("CheckAllButton")
        self.btn_check_all_systems.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_all_systems.clicked.connect(self._on_check_all_systems_clicked)
        health_layout.addWidget(self.btn_check_all_systems)

        # Ряд кнопок интерактивной диагностики
        test_buttons_row = QHBoxLayout()
        test_buttons_row.setSpacing(8)

        btn_test_sound = QPushButton("🔊 Проверить звук («бип»)", health_box)
        btn_test_sound.clicked.connect(self.test_sound_requested.emit)
        test_buttons_row.addWidget(btn_test_sound)

        btn_test_mic = QPushButton("🎙 Проверить микрофон (Запись 3с)", health_box)
        btn_test_mic.clicked.connect(self.test_mic_requested.emit)
        test_buttons_row.addWidget(btn_test_mic)

        btn_test_stt = QPushButton("🧠 Проверить STT (Тест CUDA)", health_box)
        btn_test_stt.clicked.connect(self.test_stt_requested.emit)
        test_buttons_row.addWidget(btn_test_stt)

        self.btn_download_llm = QPushButton("✓ Vision Jedi-3B (Готова)", health_box)
        self.btn_download_llm.clicked.connect(self.download_llm_requested.emit)
        test_buttons_row.addWidget(self.btn_download_llm)

        health_layout.addLayout(test_buttons_row)

        # Живая плашка тестирования клавиши Copilot
        key_test_box = QHBoxLayout()
        self.lbl_key_test = QLabel("⌨ Тест клавиши: нажмите Copilot на клавиатуре ноутбука для мгновенной проверки перехвата...", health_box)
        self.lbl_key_test.setStyleSheet("""
            background-color: #121316;
            border: 1px dashed #3B82F6;
            border-radius: 6px;
            padding: 6px 12px;
            color: #93C5FD;
            font-size: 11px;
        """)
        key_test_box.addWidget(self.lbl_key_test)
        health_layout.addLayout(key_test_box)

        ctrl_layout.addWidget(health_box)

        # Индикатор громкости микрофона (VU-метр)
        vu_box = QGroupBox("Уровень сигнала микрофона в реальном времени (VU)", tab_control_content)
        vu_layout = QVBoxLayout(vu_box)
        vu_layout.setSpacing(4)
        self.vu_bar = QProgressBar(vu_box)
        self.vu_bar.setRange(0, 100)
        self.vu_bar.setValue(0)
        vu_layout.addWidget(self.vu_bar)
        ctrl_layout.addWidget(vu_box)

        # Терминал логов
        log_box = QGroupBox("Журнал событий и распознанных команд", tab_control_content)
        log_layout = QVBoxLayout(log_box)
        log_layout.setSpacing(6)
        
        self.log_view = QPlainTextEdit(log_box)
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(140)
        log_layout.addWidget(self.log_view)

        btn_clear_log = QPushButton("Очистить журнал", log_box)
        btn_clear_log.setMaximumWidth(140)
        btn_clear_log.clicked.connect(self.log_view.clear)
        log_layout.addWidget(btn_clear_log, alignment=Qt.AlignmentFlag.AlignRight)

        ctrl_layout.addWidget(log_box)
        ctrl_layout.addStretch()

        tab_control_scroll.setWidget(tab_control_content)
        self.tabs.addTab(tab_control_scroll, "Панель управления")

        # --- Вкладка 2: Настройки ---
        tab_settings_scroll = QScrollArea(self)
        tab_settings_scroll.setWidgetResizable(True)
        tab_settings_content = QWidget()
        sett_layout = QVBoxLayout(tab_settings_content)
        sett_layout.setContentsMargins(10, 10, 10, 10)
        sett_layout.setSpacing(14)

        # 1. Режим по умолчанию при запуске
        mode_box = QGroupBox("Режим активации по умолчанию при старте приложения", tab_settings_content)
        mode_layout = QVBoxLayout(mode_box)
        mode_layout.setSpacing(8)
        self.mode_group = QButtonGroup(mode_box)

        ww_disp = (self.settings.get("wake_word", "джарвис") or "джарвис").capitalize()
        self.rb_copilot_only = QRadioButton("Только кнопка Copilot (100% приватность, 0% CPU в фоне)", mode_box)
        self.rb_wake_word = QRadioButton(f"Кнопка Copilot + фоновый вызов словом «{ww_disp}» (Hands-free)", mode_box)

        self.mode_group.addButton(self.rb_copilot_only)
        self.mode_group.addButton(self.rb_wake_word)

        self.rb_copilot_only.blockSignals(True)
        self.rb_wake_word.blockSignals(True)
        if self.settings.get("default_activation_mode") == "wake_word_and_copilot":
            self.rb_wake_word.setChecked(True)
        else:
            self.rb_copilot_only.setChecked(True)
        self.rb_copilot_only.blockSignals(False)
        self.rb_wake_word.blockSignals(False)

        self.rb_copilot_only.toggled.connect(self._on_activation_mode_changed)
        mode_layout.addWidget(self.rb_copilot_only)
        mode_layout.addWidget(self.rb_wake_word)
        sett_layout.addWidget(mode_box)

        # 1.1 Настройка слова-триггера для голосовой активации
        wake_box = QGroupBox("Слово-триггер для голосовой активации (Wake Word)", tab_settings_content)
        wake_layout = QVBoxLayout(wake_box)
        wake_layout.setSpacing(8)

        lbl_wake = QLabel("Слово или имя, активирующее запись в режиме Hands-free (по умолчанию «Джарвис»):", wake_box)
        lbl_wake.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        wake_layout.addWidget(lbl_wake)

        wake_row = QHBoxLayout()
        wake_row.setSpacing(8)

        self.txt_wake_word = QLineEdit(wake_box)
        self.txt_wake_word.setPlaceholderText("Джарвис")
        cur_ww = self.settings.get("wake_word", "джарвис") or "джарвис"
        self.txt_wake_word.setText(cur_ww.capitalize())
        self.txt_wake_word.textChanged.connect(self._on_wake_word_changed)
        wake_row.addWidget(self.txt_wake_word)

        btn_reset_wake = QPushButton("По умолчанию (Джарвис)", wake_box)
        btn_reset_wake.setToolTip("Сбросить слово-триггер на «Джарвис»")
        btn_reset_wake.clicked.connect(self._reset_wake_word)
        wake_row.addWidget(btn_reset_wake)

        wake_layout.addLayout(wake_row)

        lbl_wake_tip = QLabel("Совет: используйте чёткие и короткие слова («Джарвис», «Ассистент», «Компьютер»).", wake_box)
        lbl_wake_tip.setStyleSheet("color: #6B7280; font-size: 11px;")
        wake_layout.addWidget(lbl_wake_tip)

        sett_layout.addWidget(wake_box)

        # 2. Выбор микрофона
        mic_box = QGroupBox("Устройство ввода аудио (Микрофон)", tab_settings_content)
        mic_layout = QVBoxLayout(mic_box)
        self.cb_microphones = QComboBox(mic_box)
        self.cb_microphones.currentIndexChanged.connect(self._on_mic_selected)
        mic_layout.addWidget(self.cb_microphones)
        sett_layout.addWidget(mic_box)

        # 2.1 Модель распознавания речи (Faster-Whisper Large-v3-Turbo)
        stt_box = QGroupBox("Модель распознавания речи (Faster-Whisper)", tab_settings_content)
        stt_layout = QVBoxLayout(stt_box)
        stt_layout.setSpacing(6)

        lbl_stt = QLabel("Используемая модель Whisper для преобразования голоса в текст:", stt_box)
        lbl_stt.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        stt_layout.addWidget(lbl_stt)

        self.cb_stt_model = QComboBox(stt_box)
        self.cb_stt_model.addItem("🚀 Turbo (Large-v3-Turbo: флагманская точность русской речи, 800M)", "turbo")
        self.cb_stt_model.setCurrentIndex(0)
        self.cb_stt_model.setEnabled(False)
        self.cb_stt_model.currentIndexChanged.connect(self._on_stt_model_selected)
        stt_layout.addWidget(self.cb_stt_model)

        lbl_stt_tip = QLabel("Модель Large-v3-Turbo зафиксирована как основная: обеспечивает эталонную точность на GPU RTX 5050.", stt_box)
        lbl_stt_tip.setStyleSheet("color: #6B7280; font-size: 11px;")
        stt_layout.addWidget(lbl_stt_tip)

        sett_layout.addWidget(stt_box)

        # 2.2 Модуль автономного управления Vision Computer-Use (Jedi-3B 1080p)
        vision_box = QGroupBox("Автономный агент интерфейса (Vision Computer-Use)", tab_settings_content)
        vision_layout = QVBoxLayout(vision_box)
        vision_layout.setSpacing(8)

        lbl_vlm = QLabel("Мультимодальная модель компьютерного зрения (VLM):", vision_box)
        lbl_vlm.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        vision_layout.addWidget(lbl_vlm)

        self.cb_vision_model = QComboBox(vision_box)
        self.cb_vision_model.addItem("👁 Jedi-3B (1080p Desktop Agent, 4-bit NF4)", "xlangai/Jedi-3B-1080p")
        self.cb_vision_model.addItem("⚡ Qwen2.5-VL-3B-Instruct (Резервная VLM)", "Qwen/Qwen2.5-VL-3B-Instruct")
        saved_vision_model = self.settings.get("vision_model", "xlangai/Jedi-3B-1080p")
        idx = self.cb_vision_model.findData(saved_vision_model)
        if idx >= 0:
            self.cb_vision_model.setCurrentIndex(idx)
        self.cb_vision_model.currentIndexChanged.connect(self._on_vision_model_selected)
        vision_layout.addWidget(self.cb_vision_model)

        steps_row = QHBoxLayout()
        lbl_steps = QLabel("Лимит автономных шагов (Sense-Act-Verify):", vision_box)
        lbl_steps.setStyleSheet("color: #D1D5DB; font-size: 12px;")
        steps_row.addWidget(lbl_steps)
        self.sp_max_steps = QSpinBox(vision_box)
        self.sp_max_steps.setRange(1, 20)
        self.sp_max_steps.setValue(int(self.settings.get("vision_max_steps", 8)))
        self.sp_max_steps.valueChanged.connect(self._on_max_steps_changed)
        steps_row.addWidget(self.sp_max_steps)
        steps_row.addStretch()
        vision_layout.addLayout(steps_row)

        self.cb_auto_focus_chrome = QCheckBox("Автоматически фокусировать Google Chrome перед веб-задачами", vision_box)
        self.cb_auto_focus_chrome.setChecked(self.settings.get("vision_auto_focus_browser", True))
        self.cb_auto_focus_chrome.toggled.connect(self._on_auto_focus_chrome_toggled)
        vision_layout.addWidget(self.cb_auto_focus_chrome)

        lbl_vision_tip = QLabel("Модель работает в изолированном процессе Always-Warm (~3.2 ГБ VRAM). При остановке ассистента память сбрасывается до 0 МБ.", vision_box)
        lbl_vision_tip.setStyleSheet("color: #6B7280; font-size: 11px;")
        lbl_vision_tip.setWordWrap(True)
        vision_layout.addWidget(lbl_vision_tip)

        sett_layout.addWidget(vision_box)

        # 3. Интеграция с Windows и автозапуск
        sys_box = QGroupBox("Автозапуск и системные параметры", tab_settings_content)
        sys_layout = QVBoxLayout(sys_box)
        sys_layout.setSpacing(8)

        self.cb_autostart = QCheckBox("Запускать приложение вместе с Windows (в автозагрузку)", sys_box)
        self.cb_autostart.setChecked(self.settings.get("autostart_with_windows", False))
        self.cb_autostart.toggled.connect(self._on_autostart_toggled)
        sys_layout.addWidget(self.cb_autostart)

        self.cb_start_minimized = QCheckBox("Запускать в свернутом виде (прямо в системный трей)", sys_box)
        self.cb_start_minimized.setChecked(self.settings.get("start_minimized", False))
        self.cb_start_minimized.toggled.connect(self._on_start_minimized_toggled)
        sys_layout.addWidget(self.cb_start_minimized)

        self.cb_ducking = QCheckBox("Приглушать звук системы (Audio Ducking) при записи речи", sys_box)
        self.cb_ducking.setChecked(self.settings.get("audio_ducking_enabled", True))
        self.cb_ducking.toggled.connect(self._on_ducking_toggled)
        sys_layout.addWidget(self.cb_ducking)

        self.cb_sound_cues = QCheckBox("Воспроизводить звуковые сигналы активации/успеха («бип»)", sys_box)
        self.cb_sound_cues.setChecked(self.settings.get("sound_cues_enabled", True))
        self.cb_sound_cues.toggled.connect(self._on_sound_cues_toggled)
        sys_layout.addWidget(self.cb_sound_cues)

        self.cb_tts = QCheckBox("Озвучивать ответы ассистента голосом (Text-to-Speech SAPI5)", sys_box)
        self.cb_tts.setChecked(self.settings.get("tts_enabled", False))
        self.cb_tts.toggled.connect(self._on_tts_toggled)
        sys_layout.addWidget(self.cb_tts)

        btn_reset_close = QPushButton("Сбросить запомненный выбор при закрытии окна", sys_box)
        btn_reset_close.clicked.connect(self._reset_close_behavior)
        sys_layout.addWidget(btn_reset_close)

        sett_layout.addWidget(sys_box)

        # 4. Подсказка о настройке клавиши Copilot в Windows 11
        hint_box = QGroupBox("Интеграция с клавишей Copilot в Windows 11", tab_settings_content)
        hint_layout = QVBoxLayout(hint_box)
        hint_text = QLabel(
            "В Windows 11 клавишу Copilot также можно настроить через системные Параметры:\n"
            "«Параметры -> Персонализация -> Сенсорная клавиатура и ввод -> Настройка клавиши Copilot».\n"
            "Наш низкоуровневый перехватчик (WH_KEYBOARD_LL) автоматически блокирует Windows Search.",
            hint_box
        )
        hint_text.setWordWrap(True)
        hint_text.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        hint_layout.addWidget(hint_text)
        sett_layout.addWidget(hint_box)

        sett_layout.addStretch()

        tab_settings_scroll.setWidget(tab_settings_content)
        self.tabs.addTab(tab_settings_scroll, "Настройки")

        # Активируем вкладку «Панель управления» по умолчанию
        self.tabs.setCurrentIndex(0)
        main_layout.addWidget(self.tabs)

        self.log("Antigravity Voice инициализирован и готов к работе.")

    def _create_status_card(self, title: str, status_text: str, color: str) -> QFrame:
        card = QFrame(self)
        card.setStyleSheet("""
            QFrame {
                background-color: #1A1B22;
                border: 1px solid #2B2D38;
                border-radius: 8px;
                padding: 8px 10px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        lbl_title = QLabel(title, card)
        lbl_title.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        layout.addWidget(lbl_title)

        lbl_status = QLabel(status_text, card)
        lbl_status.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_status.setStyleSheet(f"color: {color};")
        card.status_label = lbl_status
        layout.addWidget(lbl_status)

        return card

    def update_key_test_indicator(self, key_name: str, vk_code: int):
        """Мгновенно обновляет статусную плашку при нажатии клавиши."""
        if vk_code in (0x86, 0x8E) or "Copilot" in key_name:
            self.lbl_key_test.setText(f"✓ Клавиша Copilot успешно поймана! (Код: {hex(vk_code)} / F23) — Поиск Windows заблокирован!")
            self.lbl_key_test.setStyleSheet("""
                background-color: #064E3B;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 6px 12px;
                color: #34D399;
                font-weight: bold;
                font-size: 11px;
            """)
            self.card_key.status_label.setText("Copilot поймана!")
            self.card_key.status_label.setStyleSheet("color: #34D399;")
        else:
            self.lbl_key_test.setText(f"ℹ Нажата клавиша: {key_name} (Код: {hex(vk_code)})")
            self.lbl_key_test.setStyleSheet("""
                background-color: #1E1F24;
                border: 1px solid #3B82F6;
                border-radius: 6px;
                padding: 6px 12px;
                color: #60A5FA;
                font-size: 11px;
            """)

        QTimer.singleShot(4000, lambda: self.lbl_key_test.setText("⌨ Тест клавиши: нажмите Copilot на клавиатуре ноутбука для мгновенной проверки перехвата..."))
        QTimer.singleShot(4000, lambda: self.lbl_key_test.setStyleSheet("""
            background-color: #121316;
            border: 1px dashed #3B82F6;
            border-radius: 6px;
            padding: 6px 12px;
            color: #93C5FD;
            font-size: 11px;
        """))

    def log(self, message: str):
        self.log_view.appendPlainText(message)

    def set_vu_level(self, level: float):
        self.vu_bar.setValue(int(level * 100))

    def update_agent_state(self, is_running: bool):
        if is_running:
            self.status_badge.setText("🟢 АКТИВЕН")
            self.status_badge.setStyleSheet("""
                background-color: #064E3B;
                color: #34D399;
                border: 1px solid #059669;
                border-radius: 12px;
                padding: 5px 14px;
            """)
            self.btn_toggle_agent.setText("Остановить ассистента")
            self.btn_toggle_agent.setObjectName("DangerButton")
            self.card_vram.status_label.setText("~4.7 ГБ (RTX 5050)")
            self.card_vram.status_label.setStyleSheet("color: #60A5FA;")
            self.card_ai.status_label.setText("Jedi-3B (Always-Warm)")
            self.card_ai.status_label.setStyleSheet("color: #34D399;")
        else:
            self.status_badge.setText("⚪ ОСТАНОВЛЕН (0 МБ VRAM)")
            self.status_badge.setStyleSheet("""
                background-color: #1F2937;
                color: #9CA3AF;
                border: 1px solid #374151;
                border-radius: 12px;
                padding: 5px 14px;
            """)
            self.btn_toggle_agent.setText("Запустить ассистента")
            self.btn_toggle_agent.setObjectName("PrimaryButton")
            self.card_vram.status_label.setText("0 МБ VRAM (Свободна)")
            self.card_vram.status_label.setStyleSheet("color: #9CA3AF;")
            self.card_ai.status_label.setText("Выгружен (0 МБ)")
            self.card_ai.status_label.setStyleSheet("color: #9CA3AF;")

        self.btn_toggle_agent.style().unpolish(self.btn_toggle_agent)
        self.btn_toggle_agent.style().polish(self.btn_toggle_agent)

    def set_microphones(self, mics: list[dict]):
        self.cb_microphones.blockSignals(True)
        self.cb_microphones.clear()
        selected_idx = 0
        saved_idx = self.settings.get("audio_device_index")
        for i, m in enumerate(mics):
            text = m["name"]
            if m.get("default"):
                text += " (По умолчанию)"
            self.cb_microphones.addItem(text, m["index"])
            if saved_idx is not None and m["index"] == saved_idx:
                selected_idx = i
        self.cb_microphones.setCurrentIndex(selected_idx)
        self.cb_microphones.blockSignals(False)
        if mics:
            cur_name = mics[selected_idx]["name"]
            if len(cur_name) > 22:
                cur_name = cur_name[:20] + "..."
            self.card_mic.status_label.setText(cur_name)

    def set_llm_status(self, is_installed: bool):
        if is_installed:
            self.card_ai.status_label.setText("Jedi-3B (Always-Warm)")
            self.card_ai.status_label.setStyleSheet("color: #34D399;")
            self.btn_download_llm.setText("✓ Jedi-3B (1080p) готова")
            self.btn_download_llm.setEnabled(False)
        else:
            self.card_ai.status_label.setText("Fast-Path (0 мс, 0 МБ)")
            self.card_ai.status_label.setStyleSheet("color: #60A5FA;")
            self.btn_download_llm.setText("📥 Скачать Jedi-3B (1080p)")
            self.btn_download_llm.setEnabled(True)

    def _on_vision_model_selected(self, index: int):
        model_val = self.cb_vision_model.itemData(index)
        if model_val:
            self.settings["vision_model"] = model_val
            self.save_settings()
            self.log(f"Настройки: выбрана модель Vision-агента «{model_val}».")

    def _on_max_steps_changed(self, val: int):
        self.settings["vision_max_steps"] = val
        self.save_settings()
        self.log(f"Настройки: лимит шагов Vision-агента установлен на {val}.")

    def _on_auto_focus_chrome_toggled(self, checked: bool):
        self.settings["vision_auto_focus_browser"] = checked
        self.save_settings()
        self.log(f"Настройки: автофокус браузера {'включен' if checked else 'отключен'}.")

    def _on_mic_selected(self, index: int):
        data = self.cb_microphones.currentData()
        if data is not None:
            if self.settings.get("audio_device_index") == data:
                return
            self.settings["audio_device_index"] = data
            self.save_settings()
            self.mic_changed.emit(data)
            cur_text = self.cb_microphones.currentText()
            if len(cur_text) > 22:
                cur_text = cur_text[:20] + "..."
            self.card_mic.status_label.setText(cur_text)

    def _on_check_all_systems_clicked(self):
        self.btn_check_all_systems.setEnabled(False)
        self.btn_check_all_systems.setText("⏳ Проверка всех систем... Подождите")
        self.check_all_systems_requested.emit()

    def reset_check_all_systems_button(self):
        self.btn_check_all_systems.setEnabled(True)
        self.btn_check_all_systems.setText("⚡ Проверить все системы (Комплексная диагностика)")

    def update_status_card(self, card_name: str, text: str, color: str):
        mapping = {
            "mic": self.card_mic,
            "key": self.card_key,
            "stt": self.card_stt,
            "ai": self.card_ai,
            "vram": self.card_vram,
            "ide": self.card_ide,
        }
        card = mapping.get(card_name)
        if card and hasattr(card, "status_label"):
            card.status_label.setText(text)
            card.status_label.setStyleSheet(f"color: {color};")

    def _on_toggle_agent_clicked(self):
        is_currently_active = "АКТИВЕН" in self.status_badge.text()
        self.agent_toggle_requested.emit(not is_currently_active)

    def _on_activation_mode_changed(self):
        mode = "wake_word_and_copilot" if self.rb_wake_word.isChecked() else "copilot_only"
        if self.settings.get("default_activation_mode") == mode:
            return
        self.settings["default_activation_mode"] = mode
        self.settings["wake_word_enabled"] = (mode == "wake_word_and_copilot")
        self.save_settings()
        self.log(f"Режим по умолчанию изменен на: {mode}")

    def _on_wake_word_changed(self, text: str):
        cleaned = text.strip().lower()
        if not cleaned:
            cleaned = "джарвис"
        if self.settings.get("wake_word") == cleaned:
            return
        self.settings["wake_word"] = cleaned
        self.save_settings()
        display_word = cleaned.capitalize()
        self.rb_wake_word.setText(f"Кнопка Copilot + фоновый вызов словом «{display_word}» (Hands-free)")

    def _reset_wake_word(self):
        self.txt_wake_word.blockSignals(True)
        self.txt_wake_word.setText("Джарвис")
        self.txt_wake_word.blockSignals(False)
        self.settings["wake_word"] = "джарвис"
        self.save_settings()
        self.rb_wake_word.setText("Кнопка Copilot + фоновый вызов словом «Джарвис» (Hands-free)")
        self.log("Слово-триггер сброшено на значение по умолчанию: «Джарвис».")

    def _on_stt_model_selected(self, index: int):
        model_val = self.cb_stt_model.itemData(index)
        if model_val:
            self.settings["stt_model"] = model_val
            self.save_settings()
            self.settings_changed.emit(self.settings)
            self.log(f"Настройки: выбрана модель распознавания «{model_val}».")

    def _on_autostart_toggled(self, checked: bool):
        self.settings["autostart_with_windows"] = checked
        self.save_settings()
        self._apply_windows_autostart(checked)

    def _apply_windows_autostart(self, enable: bool):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "AntigravityVoice"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
                if enable:
                    exe_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".venv", "Scripts", "pythonw.exe"))
                    main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
                    cmd = f'"{exe_path}" "{main_py}" --minimized'
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
                    self.log("Автозапуск с Windows включен.")
                else:
                    try:
                        winreg.DeleteValue(key, app_name)
                        self.log("Автозапуск с Windows отключен.")
                    except FileNotFoundError:
                        pass
        except Exception as e:
            self.log(f"Ошибка настройки реестра автозапуска: {e}")

    def _on_start_minimized_toggled(self, checked: bool):
        self.settings["start_minimized"] = checked
        self.save_settings()

    def _on_ducking_toggled(self, checked: bool):
        self.settings["audio_ducking_enabled"] = checked
        self.save_settings()

    def _on_sound_cues_toggled(self, checked: bool):
        self.settings["sound_cues_enabled"] = checked
        self.save_settings()

    def _on_tts_toggled(self, checked: bool):
        self.settings["tts_enabled"] = checked
        self.save_settings()

    def _reset_close_behavior(self):
        self.settings["close_behavior"] = "ask"
        self.save_settings()
        QMessageBox.information(
            self,
            "Сброс настроек",
            "Выбор при закрытии сброшен. При следующем нажатии на крестик снова появится диалоговое окно."
        )

    def closeEvent(self, event: QCloseEvent):
        behavior = self.settings.get("close_behavior", "ask")

        if behavior == "tray":
            event.ignore()
            self.hide()
            return

        if behavior == "exit":
            self.app_exit_requested.emit()
            event.accept()
            return

        dialog = CloseConfirmDialog(self)
        if dialog.exec():
            action, remember = dialog.get_result()
            if remember:
                self.settings["close_behavior"] = action
                self.save_settings()

            if action == "tray":
                event.ignore()
                self.hide()
            else:
                self.app_exit_requested.emit()
                event.accept()
        else:
            event.ignore()
