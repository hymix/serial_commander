from __future__ import annotations

import sys
import json
import os
import argparse
import fnmatch
import queue
import re
import time
import difflib
import html as html_lib
import serial
import serial.tools.list_ports
from datetime import datetime
from PyQt6.QtWidgets import (QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, 
                             QStackedWidget, QApplication, QListWidget, QTabWidget, QMainWindow, 
                             QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, QPlainTextEdit,
                             QComboBox, QLabel, QMessageBox, QLineEdit, QRadioButton, 
                             QScrollArea, QDialog, QFormLayout, QDialogButtonBox, QCheckBox, 
                             QInputDialog, QSpinBox, QFileDialog, QMenu, QFrame, QSizePolicy)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSize, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QColor, QTextDocument, QTextCursor, QShortcut, QKeySequence, QAction, QFont

from can_support import (CAN_AVAILABLE, CAN_IMPORT_ERROR, CAN_BITRATES, DEFAULT_CAN_BITRATE,
                         TRANSPORT_SERIAL, TRANSPORT_SLCAN, TRANSPORTS, TRANSPORT_LABELS,
                         CanFrameError, CanWorker, parse_can_frame, normalize_can_ack_pattern,
                         normalize_can_id_text, extract_can_id_from_line, can_id_sort_key,
                         format_bitrate_label)

CFG_DIR = "cfg"
APP_SETTINGS_FILE = os.path.join(CFG_DIR, "app_settings.json")
APP_VERSION = "1.7.2"

# ==========================================
# GLOBALNY MOTYW CIEMNY (QSS)
# ==========================================
DARK_STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background-color: #18181b;
    color: #e4e4e7;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #27272a;
    background-color: #18181b;
}
QTabBar::tab {
    background-color: #27272a;
    color: #a1a1aa;
    padding: 6px 14px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #18181b;
    color: #ffffff;
    border-top: 2px solid #228be6;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background-color: #3f3f46;
}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QListWidget, QTableWidget {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 4px;
    padding: 3px 6px;
    color: #f4f4f5;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #228be6;
}
QComboBox QAbstractItemView {
    background-color: #27272a;
    color: #f4f4f5;
    selection-background-color: #228be6;
    selection-color: #ffffff;
    border: 1px solid #3f3f46;
    outline: none;
    padding: 2px;
}
QHeaderView::section {
    background-color: #27272a;
    color: #e4e4e7;
    padding: 4px;
    border: 1px solid #3f3f46;
    font-weight: bold;
}
QPushButton {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 4px;
    padding: 4px 10px;
    color: #e4e4e7;
}
QPushButton:hover {
    background-color: #3f3f46;
}
QPushButton:pressed {
    background-color: #18181b;
}
QPushButton:checked {
    background-color: #1c7ed6;
    border-color: #228be6;
    color: white;
}
QScrollArea {
    border: 1px solid #27272a;
    border-radius: 4px;
}
QMenu {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 3px;
}
QMenu::item:selected {
    background-color: #228be6;
    color: white;
}
QFrame#CollapsiblePanel {
    background-color: #202024;
    border: 1px solid #323238;
    border-radius: 5px;
}
QFrame#LiveWatchFrame {
    background-color: #16161a;
    border: 1px solid #2e3440;
    border-left: 3px solid #fcc419;
    border-radius: 4px;
}
QFrame#SplitCardHeader {
    background-color: #232329;
    border-top: 2px solid #228be6;
    border-bottom: 1px solid #323238;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
"""

# ==========================================
# 1. KONFIGURACJA (ŁADOWANIE / ZAPIS)
# ==========================================
def load_app_settings():
    if os.path.exists(APP_SETTINGS_FILE):
        try:
            with open(APP_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_config": "default.json"}

def save_app_settings(settings):
    try:
        if not os.path.exists(CFG_DIR):
            os.makedirs(CFG_DIR)
        temp_path = APP_SETTINGS_FILE + ".tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f)
        os.replace(temp_path, APP_SETTINGS_FILE)
    except Exception as e:
        print(f"Błąd zapisu ustawień aplikacji: {e}")

def get_default_button(btn_id):
    return {
        "id": btn_id,
        "is_used": False,
        "type": "toggle",          
        "name": f"Przycisk {btn_id}",
        "tx": "FF FF",             
        "tx_on": "AA 01 00 55",    
        "tx_off": "AA 00 00 55",   
        "ack_on": "AA 01 00 55",   
        "ack_off": "AA 00 00 55"   
    }

def get_default_config():
    config = {
        "transport": TRANSPORT_SERIAL,      # "serial" (UART) | "slcan" (CANable)
        "port": "",
        "baudrate": 115200,
        "mode": "ASCII",
        "eol": "CRLF",
        "can_bitrate": DEFAULT_CAN_BITRATE,
        "can_listen_only": False,
        "can_watch_auto": True,
        "filters": [],
        "parsers": [],
        "watch_patterns": [],
        "watch_print_in_console": False,
        "buttons": [get_default_button(i + 1) for i in range(10)]
    }
    return config

def load_config(filepath):
    config = get_default_config()
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                config.update(loaded_config)
                if "filters" not in config:
                    config["filters"] = []
                if "parsers" not in config:
                    config["parsers"] = []
                if "watch_patterns" not in config:
                    config["watch_patterns"] = []
                if "watch_print_in_console" not in config:
                    config["watch_print_in_console"] = False
                if "eol" not in config:
                    config["eol"] = "CRLF"
                if config.get("transport") not in TRANSPORTS:
                    config["transport"] = TRANSPORT_SERIAL
                try:
                    if int(config.get("can_bitrate", DEFAULT_CAN_BITRATE)) not in CAN_BITRATES:
                        config["can_bitrate"] = DEFAULT_CAN_BITRATE
                    else:
                        config["can_bitrate"] = int(config["can_bitrate"])
                except (TypeError, ValueError):
                    config["can_bitrate"] = DEFAULT_CAN_BITRATE
                if "can_listen_only" not in config:
                    config["can_listen_only"] = False
                if "can_watch_auto" not in config:
                    config["can_watch_auto"] = True
        except Exception as e:
            print(f"Błąd ładowania {filepath}: {e}. Używam domyślnych.")
    else:
        save_config(filepath, config)
    return config

def save_config(filepath, config):
    try:
        if not os.path.exists(CFG_DIR):
            os.makedirs(CFG_DIR)
        temp_path = filepath + ".tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        os.replace(temp_path, filepath)
    except Exception as e:
        print(f"Błąd zapisu {filepath}: {e}")

def populate_color_combo(combo):
    colors = [
        ("#FF6B6B", "Koralowy (Czerwony)"),
        ("#4DABF7", "Jasnoniebieski"),
        ("#FCC419", "Żółty"),
        ("#FF922B", "Pomarańczowy"),
        ("#F06595", "Różowy"),
        ("#3BC9DB", "Cyjan"),
        ("#69DB7C", "Jasnozielony"),
        ("#F8F9FA", "Biały"),
        ("#CED4DA", "Jasnoszary"),
        ("#B197FC", "Liliowy (Fioletowy)"),
        ("#20C997", "Turkusowy"),
        ("#FF8787", "Łososiowy"),
        ("#74C0FC", "Błękitny"),
        ("#E599F7", "Fuksja"),
        ("#C0EB75", "Limonkowy"),
        ("#FFD43B", "Złoty")
    ]
    combo.setIconSize(QSize(20, 20))
    for hex_code, name in colors:
        pixmap = QPixmap(20, 20)
        pixmap.fill(QColor(hex_code))
        combo.addItem(QIcon(pixmap), "", hex_code)
        combo.setItemData(combo.count() - 1, name, Qt.ItemDataRole.ToolTipRole)

# ==========================================
# CUSTOMOWE KONTROLKI (PortComboBox, CommandLineEdit, LiveWatchRowWidget)
# ==========================================
class PortComboBox(QComboBox):
    """W spoczynku wyświetla tylko krótki kod portu (np. COM20), a po rozwinięciu pełny opis urządzenia."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(82)
        self.new_ports = set()

    def set_new_ports(self, new_ports: set[str]):
        self.new_ports = set(new_ports)
        self._apply_item_styles()

    def _apply_item_styles(self):
        for i in range(self.count()):
            dev = self.itemData(i, Qt.ItemDataRole.UserRole)
            if dev in self.new_ports:
                self.setItemData(i, QColor("#1b4332"), Qt.ItemDataRole.BackgroundRole)
                self.setItemData(i, QColor("#8ce99a"), Qt.ItemDataRole.ForegroundRole)
            else:
                self.setItemData(i, None, Qt.ItemDataRole.BackgroundRole)
                self.setItemData(i, None, Qt.ItemDataRole.ForegroundRole)

    def showPopup(self):
        for i in range(self.count()):
            dev = self.itemData(i, Qt.ItemDataRole.UserRole)
            full_desc = self.itemData(i, Qt.ItemDataRole.UserRole + 1)
            if full_desc:
                if dev in self.new_ports:
                    self.setItemText(i, f"✨ {full_desc}  [NOWY]")
                else:
                    self.setItemText(i, full_desc)
        self.view().setMinimumWidth(340)
        super().showPopup()

    def hidePopup(self):
        super().hidePopup()
        for i in range(self.count()):
            short_dev = self.itemData(i, Qt.ItemDataRole.UserRole)
            if short_dev:
                self.setItemText(i, short_dev)


class CommandLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = []
        self.history_idx = -1

    def add_to_history(self, cmd):
        if cmd and (not self.history or self.history[-1] != cmd):
            self.history.append(cmd)
        self.history_idx = len(self.history)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Up:
            if self.history and self.history_idx > 0:
                self.history_idx -= 1
                self.setText(self.history[self.history_idx])
        elif event.key() == Qt.Key.Key_Down:
            if self.history and self.history_idx < len(self.history) - 1:
                self.history_idx += 1
                self.setText(self.history[self.history_idx])
            elif self.history_idx == len(self.history) - 1:
                self.history_idx = len(self.history)
                self.clear()
        else:
            super().keyPressEvent(event)


class LiveWatchRowWidget(QFrame):
    """Pojedynczy wiersz przypiętego logu w panelu Live Watch z błyskiem zmienionych tokenów."""
    unpin_requested = pyqtSignal(str)
    FLASH_DURATION = 0.75  # Czas trwania błysku zmiany w sekundach (750 ms)

    def __init__(self, key: str, parent=None, show_period: bool = False, sort_key=None):
        super().__init__(parent)
        self.key = key
        self.sort_key = sort_key
        self.tokens = []
        self.flash_until = []
        self.last_ts = ""
        self.update_count = 0

        self.setStyleSheet("""
            QFrame {
                background-color: #1c1c22;
                border: 1px solid #2d2d35;
                border-radius: 3px;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(6)

        self.lbl_content = QLabel()
        self.lbl_content.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_content.setStyleSheet("font-family: 'Consolas', 'JetBrains Mono', monospace; font-size: 12px; border: none; background: transparent;")
        self.lbl_content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.lbl_content, stretch=1)

        # Czas cyklu ramki (Δt) – używany w trybie CAN
        self.lbl_period = QLabel("")
        self.lbl_period.setStyleSheet("color: #74c0fc; font-size: 11px; font-family: monospace; border: none; background: transparent;")
        self.lbl_period.setToolTip("Czas od poprzedniej ramki o tym ID (cykl nadawania)")
        self.lbl_period.setVisible(show_period)
        layout.addWidget(self.lbl_period)

        self.lbl_counter = QLabel("#0")
        self.lbl_counter.setStyleSheet("color: #71717a; font-size: 11px; font-family: monospace; border: none; background: transparent;")
        self.lbl_counter.setToolTip("Liczba odebranych aktualizacji tego wiersza")
        layout.addWidget(self.lbl_counter)

        self.btn_unpin = QPushButton("✕")
        self.btn_unpin.setFixedSize(18, 18)
        self.btn_unpin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_unpin.setToolTip(f"Odepnij '{key}' z Live Watch")
        self.btn_unpin.setStyleSheet("""
            QPushButton { padding: 0px; background: transparent; border: none; color: #71717a; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #fa5252; color: white; border-radius: 2px; }
        """)
        self.btn_unpin.clicked.connect(lambda: self.unpin_requested.emit(self.key))
        layout.addWidget(self.btn_unpin)

    def update_message(self, msg: str, timestamp: str, period_ms=None):
        now = time.monotonic()
        self.last_ts = timestamp
        self.update_count += 1
        self.lbl_counter.setText(f"#{self.update_count}")
        if period_ms is not None:
            self.lbl_period.setText(f"Δ{period_ms:>6.0f} ms")

        # Podział linii na białe znaki, słowa/liczby oraz pojedyncze symbole (np. '*')
        new_tokens = re.findall(r'\s+|[A-Za-z0-9_.\-+%]+|.', msg)

        if not self.tokens:
            self.tokens = new_tokens
            self.flash_until = [0.0] * len(new_tokens)
        else:
            sm = difflib.SequenceMatcher(None, self.tokens, new_tokens)
            new_flash = [0.0] * len(new_tokens)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == 'equal':
                    for old_i, new_j in zip(range(i1, i2), range(j1, j2)):
                        if old_i < len(self.flash_until):
                            new_flash[new_j] = self.flash_until[old_i]
                elif tag in ('replace', 'insert'):
                    for new_j in range(j1, j2):
                        if not new_tokens[new_j].isspace():
                            new_flash[new_j] = now + self.FLASH_DURATION
            self.tokens = new_tokens
            self.flash_until = new_flash

        self.render_html(now)

    def render_html(self, now: float) -> bool:
        """Renderuje wiersz z podświetleniem zmienionych tokenów. Zwraca True, jeśli któryś token jeszcze błyska."""
        has_active_flash = False
        parts = [f'<span style="color: #69db7c; font-weight: bold;">{html_lib.escape(self.last_ts)}</span> ']
        for tok, exp in zip(self.tokens, self.flash_until):
            esc = html_lib.escape(tok)
            if exp > now and not tok.isspace():
                has_active_flash = True
                # Błysk zmienionej wartości: złoto-pomarańczowe tło i jasny tekst
                parts.append(f'<span style="background-color: #5c3c00; color: #ffd43b; font-weight: bold;">{esc}</span>')
            else:
                parts.append(f'<span style="color: #e4e4e7;">{esc}</span>')
        self.lbl_content.setText("".join(parts))
        return has_active_flash


# ==========================================
# 2. OKNA DIALOGOWE EDYCJI
# ==========================================

CAN_BUTTON_EXAMPLES = {
    "push_tx": "187#01 02 03 04",
    "tog_tx_on": "187#01",
    "tog_tx_off": "187#00",
    "tog_ack_on": "581#01*",
    "tog_ack_off": "581#00*",
    "hld_tx_on": "187#01",
    "hld_tx_off": "187#00",
    "trig_tx": "187#01 02 03 04",
    "mac_tx": "187#01 02;\nsleep(100);\n187#00",
}

CAN_BUTTON_PLACEHOLDERS = {
    "push_tx": "np. 187#01 02 03 04",
    "tog_tx_on": "np. 187#01",
    "tog_tx_off": "np. 187#00",
    "tog_ack_on": "np. 581#01* (lub 581#)",
    "tog_ack_off": "np. 581#00* (lub 581#)",
    "hld_tx_on": "np. 187#01",
    "hld_tx_off": "np. 187#00",
    "trig_tx": "np. 187#01 02 03 04",
    "mac_tx": "np. 187#01 02;\nsleep(100);\n187#00",
}


class ClickToClearLineEdit(QLineEdit):
    """Pole tekstowe z obsługą przykładowego tekstu znikającego natychmiast po kliknięciu myszą."""
    def __init__(self, text: str = "", example_text: str = "", parent=None):
        super().__init__(parent)
        self.is_example = False
        self.example_text = example_text
        if text:
            self.setText(text)
        elif example_text:
            self.set_example(example_text)

    def set_example(self, example: str):
        self.example_text = example
        super().setText(example)
        self.is_example = True
        self.setStyleSheet("color: #868e96; font-style: italic;")

    def clear_example(self):
        if self.is_example:
            super().setText("")
            self.is_example = False
            self.setStyleSheet("")

    def setText(self, text: str):
        self.is_example = False
        self.setStyleSheet("")
        super().setText(text)

    def mousePressEvent(self, event):
        self.clear_example()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if self.is_example:
            key = event.key()
            if key not in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt):
                self.clear_example()
        super().keyPressEvent(event)


class ClickToClearPlainTextEdit(QPlainTextEdit):
    """Wieloliniowe pole edycyjne sekwencji makra znikające natychmiast po kliknięciu myszą."""
    def __init__(self, text: str = "", example_text: str = "", parent=None):
        super().__init__(parent)
        self.is_example = False
        self.example_text = example_text
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        if text:
            self.setPlainText(text)
        elif example_text:
            self.set_example(example_text)

    def set_example(self, example: str):
        self.example_text = example
        super().setPlainText(example)
        self.is_example = True
        self.setStyleSheet("color: #868e96; font-style: italic;")

    def clear_example(self):
        if self.is_example:
            super().setPlainText("")
            self.is_example = False
            self.setStyleSheet("")

    def setPlainText(self, text: str):
        self.is_example = False
        self.setStyleSheet("")
        super().setPlainText(text)

    def mousePressEvent(self, event):
        self.clear_example()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if self.is_example:
            key = event.key()
            if key not in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt):
                self.clear_example()
        super().keyPressEvent(event)


class ButtonEditDialog(QDialog):
    def __init__(self, btn_data, parent=None, is_can_mode: bool = False):
        super().__init__(parent)
        self.setWindowTitle(f"Edytuj {btn_data.get('name', 'Przycisk')}")
        self.btn_data = btn_data
        self.is_can_mode = is_can_mode
        self.delete_requested = False
        
        self.resize(480, 500)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(8)
        
        # Nowy przycisk to taki, który nie był jeszcze włączony/używany
        is_new_btn = not btn_data.get("is_used", False)
        
        top_layout = QFormLayout()
        self.cb_is_used = QCheckBox("Włącz/Aktywuj przycisk")
        self.cb_is_used.setChecked(True if is_new_btn else btn_data.get("is_used", True))
        top_layout.addRow(self.cb_is_used)

        self.le_name = QLineEdit(btn_data.get("name", ""))
        top_layout.addRow("Nazwa:", self.le_name)

        self.cb_show_marker = QCheckBox("Dodaj nazwę jako znacznik do logów TX")
        self.cb_show_marker.setChecked(btn_data.get("show_marker", False))
        top_layout.addRow("", self.cb_show_marker)
        
        self.combo_type = QComboBox()
        self.combo_type.addItems(["push", "toggle", "hold", "trigger", "macro"])
        self.combo_type.setCurrentText(btn_data.get("type", "push"))
        top_layout.addRow("Typ:", self.combo_type)
        
        self.combo_payload_type = QComboBox()
        self.combo_payload_type.addItems(["ASCII", "HEX", "CAN"])
        
        if self.is_can_mode:
            self.combo_payload_type.setCurrentText("CAN")
            self.combo_payload_type.setEnabled(False)
            self.combo_payload_type.setToolTip("W profilu trybu CAN format transmisji przycisków jest na stałe zablokowany na CAN.")
        else:
            self.combo_payload_type.setCurrentText(btn_data.get("payload_type", "ASCII"))
            
        top_layout.addRow("Format TX:", self.combo_payload_type)
        self.main_layout.addLayout(top_layout)
        
        # Ramka z informacją o składni i działaniu wybranego typu przycisku
        self.info_frame = QFrame()
        self.info_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1b1e;
                border: 1px solid #2c2e33;
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        info_layout = QVBoxLayout(self.info_frame)
        info_layout.setContentsMargins(8, 6, 8, 6)
        info_layout.setSpacing(3)
        
        self.info_syntax = QLabel()
        self.info_syntax.setWordWrap(True)
        self.info_syntax.setStyleSheet("font-size: 11px; color: #ffd43b; font-weight: bold; background: transparent; border: none;")
        
        self.info_desc = QLabel()
        self.info_desc.setWordWrap(True)
        self.info_desc.setStyleSheet("font-size: 11px; color: #ced4da; background: transparent; border: none;")
        
        info_layout.addWidget(self.info_syntax)
        info_layout.addWidget(self.info_desc)
        self.main_layout.addWidget(self.info_frame)
        
        self.stack = QStackedWidget()
        
        # Wartości początkowe (dla nowego przycisku w trybie CAN ignorujemy domyślne śmieci UART)
        use_can_defaults = self.is_can_mode or (btn_data.get("payload_type") == "CAN")
        
        # PUSH
        self.page_push = QWidget()
        l_push = QFormLayout(self.page_push)
        push_val = "" if is_new_btn else btn_data.get("tx", "")
        push_ex = CAN_BUTTON_EXAMPLES["push_tx"] if use_can_defaults else ""
        self.le_push_tx = ClickToClearLineEdit(push_val, example_text=push_ex)
        l_push.addRow("TX:", self.le_push_tx)
        self.stack.addWidget(self.page_push)
        
        # TOGGLE
        self.page_toggle = QWidget()
        l_toggle = QFormLayout(self.page_toggle)
        tog_on_val = "" if is_new_btn else btn_data.get("tx_on", "")
        tog_off_val = "" if is_new_btn else btn_data.get("tx_off", "")
        ack_on_val = "" if is_new_btn else btn_data.get("ack_on", "")
        ack_off_val = "" if is_new_btn else btn_data.get("ack_off", "")
        
        self.le_tog_tx_on = ClickToClearLineEdit(tog_on_val, example_text=CAN_BUTTON_EXAMPLES["tog_tx_on"] if use_can_defaults else "")
        self.le_tog_tx_off = ClickToClearLineEdit(tog_off_val, example_text=CAN_BUTTON_EXAMPLES["tog_tx_off"] if use_can_defaults else "")
        self.le_tog_ack_on = ClickToClearLineEdit(ack_on_val, example_text=CAN_BUTTON_EXAMPLES["tog_ack_on"] if use_can_defaults else "")
        self.le_tog_ack_off = ClickToClearLineEdit(ack_off_val, example_text=CAN_BUTTON_EXAMPLES["tog_ack_off"] if use_can_defaults else "")
        
        l_toggle.addRow("TX ON:", self.le_tog_tx_on)
        l_toggle.addRow("TX OFF:", self.le_tog_tx_off)
        l_toggle.addRow("ACK ON:", self.le_tog_ack_on)
        l_toggle.addRow("ACK OFF:", self.le_tog_ack_off)
        self.stack.addWidget(self.page_toggle)
        
        # HOLD
        self.page_hold = QWidget()
        l_hold = QFormLayout(self.page_hold)
        hld_on_val = "" if is_new_btn else btn_data.get("tx_on", "")
        hld_off_val = "" if is_new_btn else btn_data.get("tx_off", "")
        self.le_hld_tx_on = ClickToClearLineEdit(hld_on_val, example_text=CAN_BUTTON_EXAMPLES["hld_tx_on"] if use_can_defaults else "")
        self.le_hld_tx_off = ClickToClearLineEdit(hld_off_val, example_text=CAN_BUTTON_EXAMPLES["hld_tx_off"] if use_can_defaults else "")
        l_hold.addRow("TX (Wciśnięty):", self.le_hld_tx_on)
        l_hold.addRow("TX (Puszczony):", self.le_hld_tx_off)
        self.stack.addWidget(self.page_hold)
        
        # TRIGGER
        self.page_trigger = QWidget()
        l_trig = QFormLayout(self.page_trigger)
        trig_val = "" if is_new_btn else btn_data.get("tx", "")
        self.le_trig_tx = ClickToClearLineEdit(trig_val, example_text=CAN_BUTTON_EXAMPLES["trig_tx"] if use_can_defaults else "")
        self.spin_trig_int = QSpinBox()
        self.spin_trig_int.setRange(10, 600000)
        self.spin_trig_int.setValue(btn_data.get("interval", 1000))
        self.spin_trig_int.setSuffix(" ms")
        l_trig.addRow("TX:", self.le_trig_tx)
        l_trig.addRow("Interwał:", self.spin_trig_int)
        self.stack.addWidget(self.page_trigger)
        
        # MACRO (duże pole QPlainTextEdit z obsługą wielu linii i średników)
        self.page_macro = QWidget()
        l_macro = QVBoxLayout(self.page_macro)
        l_macro.setContentsMargins(0, 0, 0, 0)
        l_macro.setSpacing(4)
        
        lbl_macro_seq = QLabel("Sekwencja komend / ramek:")
        lbl_macro_seq.setStyleSheet("font-weight: bold; color: #ced4da;")
        l_macro.addWidget(lbl_macro_seq)
        
        mac_val = "" if is_new_btn else btn_data.get("tx", "")
        self.le_mac_tx = ClickToClearPlainTextEdit(mac_val, example_text=CAN_BUTTON_EXAMPLES["mac_tx"] if use_can_defaults else "")
        self.le_mac_tx.setMinimumHeight(130)
        l_macro.addWidget(self.le_mac_tx)
        
        lbl_macro_hint = QLabel("💡 Rozdzielaj komendy średnikami ';' lub nowymi liniami. Pauzy czasowe: sleep(milisekundy).")
        lbl_macro_hint.setStyleSheet("color: #868e96; font-size: 11px;")
        l_macro.addWidget(lbl_macro_hint)
        self.stack.addWidget(self.page_macro)
        
        self.main_layout.addWidget(self.stack)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Discard)
        buttons.button(QDialogButtonBox.StandardButton.Discard).setText("Usuń / Wyczyść")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Discard).clicked.connect(self.on_delete)
        self.main_layout.addWidget(buttons)
        
        self.combo_type.currentTextChanged.connect(self.update_stack)
        self.combo_payload_type.currentTextChanged.connect(self.on_payload_type_changed)
        
        self.update_stack(self.combo_type.currentText())
        self.on_payload_type_changed(self.combo_payload_type.currentText())

    def on_payload_type_changed(self, ptype):
        if ptype == "CAN":
            self.le_push_tx.setPlaceholderText(CAN_BUTTON_PLACEHOLDERS["push_tx"])
            self.le_tog_tx_on.setPlaceholderText(CAN_BUTTON_PLACEHOLDERS["tog_tx_on"])
            self.le_tog_tx_off.setPlaceholderText(CAN_BUTTON_PLACEHOLDERS["tog_tx_off"])
            self.le_tog_ack_on.setPlaceholderText(CAN_BUTTON_PLACEHOLDERS["tog_ack_on"])
            self.le_tog_ack_off.setPlaceholderText(CAN_BUTTON_PLACEHOLDERS["tog_ack_off"])
            self.le_hld_tx_on.setPlaceholderText(CAN_BUTTON_PLACEHOLDERS["hld_tx_on"])
            self.le_hld_tx_off.setPlaceholderText(CAN_BUTTON_PLACEHOLDERS["hld_tx_off"])
            self.le_trig_tx.setPlaceholderText(CAN_BUTTON_PLACEHOLDERS["trig_tx"])
            self.le_mac_tx.setPlaceholderText(CAN_BUTTON_PLACEHOLDERS["mac_tx"])
            
            # Wypełnienie pól przykładami CAN, jeśli są puste lub są aktywnymi przykładami
            fields = [
                (self.le_push_tx, CAN_BUTTON_EXAMPLES["push_tx"]),
                (self.le_tog_tx_on, CAN_BUTTON_EXAMPLES["tog_tx_on"]),
                (self.le_tog_tx_off, CAN_BUTTON_EXAMPLES["tog_tx_off"]),
                (self.le_tog_ack_on, CAN_BUTTON_EXAMPLES["tog_ack_on"]),
                (self.le_tog_ack_off, CAN_BUTTON_EXAMPLES["tog_ack_off"]),
                (self.le_hld_tx_on, CAN_BUTTON_EXAMPLES["hld_tx_on"]),
                (self.le_hld_tx_off, CAN_BUTTON_EXAMPLES["hld_tx_off"]),
                (self.le_trig_tx, CAN_BUTTON_EXAMPLES["trig_tx"]),
            ]
            for f, ex in fields:
                if not f.text().strip() or f.is_example:
                    f.set_example(ex)
            if not self.le_mac_tx.toPlainText().strip() or self.le_mac_tx.is_example:
                self.le_mac_tx.set_example(CAN_BUTTON_EXAMPLES["mac_tx"])
        elif ptype == "HEX":
            self.le_push_tx.setPlaceholderText("np. AA 01 02")
            self.le_tog_tx_on.setPlaceholderText("np. AA 01")
            self.le_tog_tx_off.setPlaceholderText("np. AA 00")
            self.le_tog_ack_on.setPlaceholderText("np. AA 01")
            self.le_tog_ack_off.setPlaceholderText("np. AA 00")
            self.le_hld_tx_on.setPlaceholderText("np. AA 01")
            self.le_hld_tx_off.setPlaceholderText("np. AA 00")
            self.le_trig_tx.setPlaceholderText("np. AA 01")
            self.le_mac_tx.setPlaceholderText("np. AA 01; sleep(500); AA 02")
        else:
            self.le_push_tx.setPlaceholderText("")
            self.le_tog_tx_on.setPlaceholderText("")
            self.le_tog_tx_off.setPlaceholderText("")
            self.le_tog_ack_on.setPlaceholderText("")
            self.le_tog_ack_off.setPlaceholderText("")
            self.le_hld_tx_on.setPlaceholderText("")
            self.le_hld_tx_off.setPlaceholderText("")
            self.le_trig_tx.setPlaceholderText("")
            self.le_mac_tx.setPlaceholderText("np. cmd1; sleep(500); cmd2")
            
        self.update_stack(self.combo_type.currentText())
        
    def update_stack(self, text):
        mapping = {"push": 0, "toggle": 1, "hold": 2, "trigger": 3, "macro": 4}
        self.stack.setCurrentIndex(mapping.get(text, 0))
        
        is_can = (self.combo_payload_type.currentText() == "CAN") or self.is_can_mode
        
        if is_can:
            can_syntax_map = {
                "push": (
                    "📌 Składnia CAN: ID#DANE (np. 187#01 02 03 04, 18FEF100#AABB, 65A#R)",
                    "Wysyła pojedynczą ramkę CAN na magistralę natychmiast po kliknięciu."
                ),
                "toggle": (
                    "📌 Składnia CAN: ID#DANE | Wzorzec ACK: ID#DANE* (np. 581#01* lub 581#)",
                    "Przełącznik ON/OFF. Nadaje 'TX ON' lub 'TX OFF'. Kolor zmieni się dopiero po odebraniu ramki pasującej do wzorca ACK!"
                ),
                "hold": (
                    "📌 Składnia CAN: ID#DANE (np. Wciśnięty: 187#01, Puszczony: 187#00)",
                    "Przycisk chwilowy: nadaje ramkę wciśnięcia po naciśnięciu i ramkę puszczenia w momencie zwolnienia."
                ),
                "trigger": (
                    "📌 Składnia CAN: ID#DANE (np. 187#01 02 03 04)",
                    "Generator cykliczny: nadaje ramkę w pętli co zadany interwał (ms). Ponowne kliknięcie zatrzymuje nadawanie."
                ),
                "macro": (
                    "📌 Składnia CAN: sekwencja ramek rozdzielonych ';' lub nowymi liniami, pauzy: sleep(ms)",
                    "Przykład: '187#01 02; sleep(100); 187#00'. Sekwencja wykonywana jest w osobnym wątku roboczym."
                )
            }
            syntax, desc = can_syntax_map.get(text, ("", ""))
        else:
            uart_syntax_map = {
                "push": (
                    "📌 Format: ASCII / HEX (np. AA 01 02)",
                    "Kliknięcie wysyła podaną ramkę jeden raz."
                ),
                "toggle": (
                    "📌 Format: ASCII / HEX | Oczekiwane ACK: bajty lub tekst potwierdzenia",
                    "Przełącza tryb ON/OFF. Stan przycisku zmieni się dopiero po odebraniu potwierdzenia ACK."
                ),
                "hold": (
                    "📌 Format: ASCII / HEX",
                    "Wysyła ramkę wciśnięcia po naciśnięciu przycisku myszą oraz puszczenia po zwolnieniu."
                ),
                "trigger": (
                    "📌 Format: ASCII / HEX",
                    "Pętla asynchroniczna wysyłająca ramkę co zadany interwał (ms)."
                ),
                "macro": (
                    "📌 Format: komendy rozdzielone ';' lub nowymi liniami, pauzy: sleep(ms)",
                    "Wykonuje sekwencję komend rozdzielonych średnikiem lub nową linią z opóźnieniami sleep(ms)."
                )
            }
            syntax, desc = uart_syntax_map.get(text, ("", ""))
            
        self.info_syntax.setText(syntax)
        self.info_desc.setText(desc)

    def on_delete(self):
        self.delete_requested = True
        self.accept()

    def get_data(self):
        btn_id = self.btn_data.get("id", 1)
        if self.delete_requested:
            return get_default_button(btn_id)
            
        t = self.combo_type.currentText()
        res = {
            "id": btn_id,
            "is_used": self.cb_is_used.isChecked(),
            "type": t,
            "name": self.le_name.text(),
            "show_marker": self.cb_show_marker.isChecked(),
            "payload_type": "CAN" if self.is_can_mode else self.combo_payload_type.currentText()
        }
        if t == "push":
            res["tx"] = self.le_push_tx.text().strip()
        elif t == "toggle":
            res["tx_on"] = self.le_tog_tx_on.text().strip()
            res["tx_off"] = self.le_tog_tx_off.text().strip()
            res["ack_on"] = self.le_tog_ack_on.text().strip()
            res["ack_off"] = self.le_tog_ack_off.text().strip()
        elif t == "hold":
            res["tx_on"] = self.le_hld_tx_on.text().strip()
            res["tx_off"] = self.le_hld_tx_off.text().strip()
        elif t == "trigger":
            res["tx"] = self.le_trig_tx.text().strip()
            res["interval"] = self.spin_trig_int.value()
        elif t == "macro":
            res["tx"] = self.le_mac_tx.toPlainText().strip()
            
        return res


class ParserEditDialog(QDialog):
    def __init__(self, parser_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edytuj Parser: {parser_data.get('pattern', '')}")
        
        self.resize(300, 150)
        layout = QFormLayout(self)

        self.le_pattern = QLineEdit(parser_data.get("pattern", ""))
        layout.addRow("Wzór (HEX/Tekst):", self.le_pattern)

        self.le_text = QLineEdit(parser_data.get("text", ""))
        layout.addRow("Zastąp tekstem:", self.le_text)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Discard)
        btns.button(QDialogButtonBox.StandardButton.Discard).setText("Usuń")
        
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        
        self.delete_requested = False
        btns.button(QDialogButtonBox.StandardButton.Discard).clicked.connect(self.on_delete)
        
        layout.addRow(btns)

    def on_delete(self):
        self.delete_requested = True
        self.accept()

    def get_data(self):
        return {
            "pattern": self.le_pattern.text().strip(),
            "text": self.le_text.text().strip()
        }

class FilterEditDialog(QDialog):
    def __init__(self, filter_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edytuj Filtr: {filter_data.get('pattern', '')}")
        
        self.resize(350, 150)
        layout = QFormLayout(self)

        self.le_pattern = QLineEdit(filter_data.get("pattern", ""))
        layout.addRow("Wzór:", self.le_pattern)

        self.combo_action = QComboBox()
        self.combo_action.addItems(["Ukryj", "Koloruj", "Dozwolony (Whitelist)"])
        action_cfg = filter_data.get("action", "hide")
        if action_cfg == "hide": action_val = "Ukryj"
        elif action_cfg == "allow": action_val = "Dozwolony (Whitelist)"
        else: action_val = "Koloruj"
        self.combo_action.setCurrentText(action_val)
        layout.addRow("Akcja:", self.combo_action)

        self.combo_color = QComboBox()
        populate_color_combo(self.combo_color)
        
        current_color = filter_data.get("color", "")
        if current_color:
            for i in range(self.combo_color.count()):
                if self.combo_color.itemData(i) == current_color:
                    self.combo_color.setCurrentIndex(i)
                    break

        self.combo_color.setEnabled(action_val == "Koloruj")
        self.combo_action.currentTextChanged.connect(
            lambda t: self.combo_color.setEnabled(t == "Koloruj")
        )
        layout.addRow("Kolor:", self.combo_color)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Discard)
        buttons.button(QDialogButtonBox.StandardButton.Discard).setText("Usuń")
        
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        self.delete_requested = False
        buttons.button(QDialogButtonBox.StandardButton.Discard).clicked.connect(self.on_delete)
        
        layout.addRow(buttons)

    def on_delete(self):
        self.delete_requested = True
        self.accept()

    def get_data(self):
        sel = self.combo_action.currentText()
        if sel == "Ukryj": action = "hide"
        elif sel == "Dozwolony (Whitelist)": action = "allow"
        else: action = "color"
        
        color = self.combo_color.currentData()
        return {
            "pattern": self.le_pattern.text().strip(),
            "action": action,
            "color": color
        }

class SearchDialog(QDialog):
    def __init__(self, text_edit, parent=None):
        super().__init__(parent)
        self.text_edit = text_edit
        self.setWindowTitle("Szukaj w logach")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setModal(False)
        self.resize(320, 42)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        
        self.le_search = QLineEdit()
        self.le_search.setPlaceholderText("Szukaj...")
        self.le_search.textChanged.connect(self.update_count)
        self.le_search.returnPressed.connect(self.search_forward)
        
        self.lbl_count = QLabel("0 wyników")
        
        self.btn_prev = QPushButton("▲")
        self.btn_prev.setFixedSize(28, 28)
        self.btn_prev.setStyleSheet("padding: 0px;")
        self.btn_prev.clicked.connect(self.search_backward)
        
        self.btn_next = QPushButton("▼")
        self.btn_next.setFixedSize(28, 28)
        self.btn_next.setStyleSheet("padding: 0px;")
        self.btn_next.clicked.connect(self.search_forward)
        
        layout.addWidget(self.le_search)
        layout.addWidget(self.lbl_count)
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.btn_next)

    def update_count(self):
        text = self.le_search.text()
        if not text:
            self.lbl_count.setText("0 wyników")
            cursor = self.text_edit.textCursor()
            cursor.clearSelection()
            self.text_edit.setTextCursor(cursor)
            return
            
        doc = self.text_edit.document()
        cursor = QTextCursor(doc)
        
        count = 0
        while True:
            cursor = doc.find(text, cursor)
            if cursor.isNull():
                break
            count += 1
            
        self.lbl_count.setText(f"{count} wyników")
        self.search_forward(first_time=True)
        
    def search_forward(self, first_time=False):
        text = self.le_search.text()
        if not text:
            return
            
        cursor = self.text_edit.textCursor()
        if first_time:
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            
        found = self.text_edit.find(text)
        if not found and not first_time:
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.text_edit.setTextCursor(cursor)
            self.text_edit.find(text)

    def search_backward(self):
        text = self.le_search.text()
        if not text:
            return
            
        options = QTextDocument.FindFlag.FindBackward
        found = self.text_edit.find(text, options)
        if not found:
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.text_edit.setTextCursor(cursor)
            self.text_edit.find(text, options)

# ==========================================
# 3. WĄTEK POBOCZNY (WORKER)
# ==========================================
class MacroRunner(QThread):
    tx_signal = pyqtSignal(str, str, bool, str)

    def __init__(self, sequence, name, show_marker, payload_type="ASCII", parent=None):
        super().__init__(parent)
        self.sequence = sequence
        self.name = name
        self.show_marker = show_marker
        self.payload_type = payload_type
        
    def run(self):
        # Obsługa sekwencji rozdzielanych średnikami ';' lub nowymi liniami '\n'
        raw_sequence = self.sequence.replace('\r', '').replace('\n', ';')
        commands = raw_sequence.split(';')
        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue
            if cmd.startswith("sleep(") and cmd.endswith(")"):
                try:
                    ms = int(cmd[6:-1])
                    self.msleep(ms)
                except ValueError:
                    pass
            else:
                self.tx_signal.emit(cmd, self.name, self.show_marker, self.payload_type)

class SerialWorker(QThread):
    data_received = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)
    connection_status = pyqtSignal(bool)

    def __init__(self, port, baudrate):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.serial_port = None
        self.is_running = False
        self.tx_queue = queue.Queue()

    def run(self):
        try:
            self.serial_port = serial.Serial(self.port, self.baudrate, timeout=1, write_timeout=1)
            self.is_running = True
            self.connection_status.emit(True)
        except serial.SerialException as e:
            self.error_occurred.emit(f"Błąd otwarcia portu: {e}")
            self.connection_status.emit(False)
            return

        while self.is_running:
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(min(self.serial_port.in_waiting, 4096))
                    if data:
                        self.data_received.emit(data)
                
                while not self.tx_queue.empty():
                    data_to_send = self.tx_queue.get_nowait()
                    try:
                        self.serial_port.write(data_to_send)
                    except serial.SerialTimeoutException:
                        self.error_occurred.emit("Błąd zapisu: Urządzenie nie odbiera danych (Timeout).")

                if self.serial_port.in_waiting == 0 and self.tx_queue.empty():
                    self.msleep(10)
            except serial.SerialException as e:
                self.error_occurred.emit(f"Błąd sprzętowy portu: {e}")
                self.connection_status.emit(False)
                break
            except Exception as e:
                self.error_occurred.emit(f"Utracono połączenie: {e}")
                self.connection_status.emit(False)
                break

        self.is_running = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()

    def stop(self):
        self.is_running = False
        self.wait()

    def send_data(self, data: bytes):
        self.tx_queue.put(data)

    def set_dtr(self, state: bool):
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.dtr = state
            except Exception as e:
                self.error_occurred.emit(f"Błąd ustawienia linii DTR: {e}")

    def set_rts(self, state: bool):
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.rts = state
            except Exception as e:
                self.error_occurred.emit(f"Błąd ustawienia linii RTS: {e}")

# ==========================================
# 4. DIALOGI ZARZĄDZANIA (KONFIGURACJA, FILTRY, PARSERY)
# ==========================================
class ConfigEditDialog(QDialog):
    def __init__(self, cfg_filepath, parent=None):
        super().__init__(parent)
        self.cfg_filepath = cfg_filepath
        self.setWindowTitle(f"Edytor Konfiguracji: {os.path.basename(cfg_filepath)}")
        self.resize(520, 480)
        
        layout = QVBoxLayout(self)
        
        try:
            with open(cfg_filepath, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except Exception:
            self.data = get_default_config()
            
        self.tabs = QTabWidget()

        # ------------------------------------------
        # Zakładka Połączenie (Serial / CAN)
        # ------------------------------------------
        conn_tab = QWidget()
        conn_layout = QVBoxLayout(conn_tab)
        conn_form = QFormLayout()

        self.combo_transport = QComboBox()
        self.combo_transport.addItem(TRANSPORT_LABELS[TRANSPORT_SERIAL], TRANSPORT_SERIAL)
        self.combo_transport.addItem(TRANSPORT_LABELS[TRANSPORT_SLCAN], TRANSPORT_SLCAN)
        cur_transport = self.data.get("transport", TRANSPORT_SERIAL)
        if cur_transport == TRANSPORT_SLCAN:
            self.combo_transport.setCurrentIndex(1)
        else:
            self.combo_transport.setCurrentIndex(0)
        conn_form.addRow("Typ połączenia:", self.combo_transport)

        # Sekcja CAN
        self.can_group = QFrame()
        self.can_group.setStyleSheet("QFrame { background-color: #202024; border: 1px solid #323238; border-radius: 4px; padding: 6px; }")
        can_vbox = QVBoxLayout(self.can_group)
        can_form = QFormLayout()

        self.combo_can_bitrate = QComboBox()
        cur_br = self.data.get("can_bitrate", DEFAULT_CAN_BITRATE)
        for br in CAN_BITRATES:
            self.combo_can_bitrate.addItem(f"{format_bitrate_label(br)} ({br} bps)", br)
            if br == cur_br:
                self.combo_can_bitrate.setCurrentIndex(self.combo_can_bitrate.count() - 1)
        can_form.addRow("Bitrate CAN:", self.combo_can_bitrate)

        self.cb_can_listen_only = QCheckBox("Tryb nasłuchu (Listen-only)")
        self.cb_can_listen_only.setToolTip("Adapter nie generuje bitów ACK ani ramek błędów na magistrali")
        self.cb_can_listen_only.setChecked(bool(self.data.get("can_listen_only", False)))
        can_form.addRow("", self.cb_can_listen_only)

        self.cb_can_watch_auto = QCheckBox("Automatycznie przypinaj każde nowe ID do Live Watch")
        self.cb_can_watch_auto.setToolTip("Każde nowe odebrane CAN ID dostaje własny stały wiersz z błyskiem zmienionych bajtów i czasem cyklu")
        self.cb_can_watch_auto.setChecked(bool(self.data.get("can_watch_auto", True)))
        can_form.addRow("", self.cb_can_watch_auto)

        can_vbox.addLayout(can_form)
        conn_form.addRow("Ustawienia CAN:", self.can_group)

        # Sekcja Serial (UART)
        self.serial_group = QFrame()
        self.serial_group.setStyleSheet("QFrame { background-color: #202024; border: 1px solid #323238; border-radius: 4px; padding: 6px; }")
        serial_vbox = QVBoxLayout(self.serial_group)
        serial_form = QFormLayout()

        self.combo_serial_baud = QComboBox()
        self.combo_serial_baud.addItems(SerialTab.STANDARD_BAUDS)
        cur_baud = str(self.data.get("baudrate", 115200))
        idx_baud = self.combo_serial_baud.findText(cur_baud)
        if idx_baud >= 0:
            self.combo_serial_baud.setCurrentIndex(idx_baud)
        else:
            self.combo_serial_baud.addItem(cur_baud)
            self.combo_serial_baud.setCurrentText(cur_baud)
        serial_form.addRow("Domyślny Baudrate:", self.combo_serial_baud)

        serial_vbox.addLayout(serial_form)
        conn_form.addRow("Ustawienia Serial:", self.serial_group)

        conn_layout.addLayout(conn_form)
        conn_layout.addStretch()
        self.tabs.addTab(conn_tab, "Połączenie")

        def update_conn_sections():
            is_can = self.combo_transport.currentData() == TRANSPORT_SLCAN
            self.can_group.setVisible(is_can)
            self.serial_group.setVisible(not is_can)

        self.combo_transport.currentIndexChanged.connect(update_conn_sections)
        update_conn_sections()
        
        # Zakładka Przyciski
        btn_tab = QWidget()
        btn_layout = QVBoxLayout(btn_tab)
        self.list_btns = QListWidget()
        for i, b in enumerate(self.data.get("buttons", [])):
            status = b.get('name', 'Nieużywany') if b.get('is_used', False) else "Nieużywany"
            self.list_btns.addItem(f"[{i+1}] {status}")
        self.list_btns.itemDoubleClicked.connect(self.edit_button)
        btn_layout.addWidget(QLabel("Kliknij dwukrotnie, aby edytować przycisk:"))
        btn_layout.addWidget(self.list_btns)
        self.tabs.addTab(btn_tab, "Przyciski")
        
        # Zakładka Filtry
        filt_tab = QWidget()
        filt_layout = QVBoxLayout(filt_tab)
        self.list_filters = QListWidget()
        for f_cfg in self.data.get("filters", []):
            self.list_filters.addItem(f"{f_cfg.get('pattern')} -> {f_cfg.get('action')}")
        self.list_filters.itemDoubleClicked.connect(self.edit_filter)
        filt_layout.addWidget(QLabel("Kliknij dwukrotnie, aby usunąć lub edytować filtr:"))
        filt_layout.addWidget(self.list_filters)
        self.tabs.addTab(filt_tab, "Filtry")
        
        # Zakładka Parsery
        pars_tab = QWidget()
        pars_layout = QVBoxLayout(pars_tab)
        self.list_parsers = QListWidget()
        for p in self.data.get("parsers", []):
            self.list_parsers.addItem(f"{p.get('pattern')} -> {p.get('text')}")
        self.list_parsers.itemDoubleClicked.connect(self.edit_parser)
        pars_layout.addWidget(QLabel("Kliknij dwukrotnie, aby usunąć lub edytować parser:"))
        pars_layout.addWidget(self.list_parsers)
        self.tabs.addTab(pars_tab, "Parsery")
        
        layout.addWidget(self.tabs)
        
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Zapisz Ustawienia")
        self.btn_save.setStyleSheet("background-color: #228be6; color: white; font-weight: bold;")
        self.btn_delete = QPushButton("Usuń Konfigurację")
        self.btn_delete.setStyleSheet("background-color: #fa5252; color: white; font-weight: bold;")
        
        self.btn_save.clicked.connect(self.on_save)
        self.btn_delete.clicked.connect(self.on_delete)
        
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_delete)
        layout.addLayout(btn_layout)
        
        self.action_taken = None
        
    def edit_button(self, item):
        idx = self.list_btns.row(item)
        is_can = self.combo_transport.currentData() == TRANSPORT_SLCAN
        dlg = ButtonEditDialog(self.data["buttons"][idx], self, is_can_mode=is_can)
        if dlg.exec():
            self.data["buttons"][idx] = dlg.get_data()
            b = self.data["buttons"][idx]
            status = b.get('name', 'Nieużywany') if b.get('is_used', False) else "Nieużywany"
            item.setText(f"[{idx+1}] {status}")

    def edit_filter(self, item):
        idx = self.list_filters.row(item)
        dlg = FilterEditDialog(self.data["filters"][idx], self)
        if dlg.exec():
            if getattr(dlg, 'delete_requested', False):
                self.data["filters"].pop(idx)
                self.list_filters.takeItem(idx)
            else:
                self.data["filters"][idx] = dlg.get_data()
                item.setText(f"{self.data['filters'][idx].get('pattern')} -> {self.data['filters'][idx].get('action')}")

    def edit_parser(self, item):
        idx = self.list_parsers.row(item)
        dlg = ParserEditDialog(self.data["parsers"][idx], self)
        if dlg.exec():
            if getattr(dlg, 'delete_requested', False):
                self.data["parsers"].pop(idx)
                self.list_parsers.takeItem(idx)
            else:
                self.data["parsers"][idx] = dlg.get_data()
                item.setText(f"{self.data['parsers'][idx].get('pattern')} -> {self.data['parsers'][idx].get('text')}")

    def on_save(self):
        try:
            self.data["transport"] = self.combo_transport.currentData()
            if self.data["transport"] == TRANSPORT_SLCAN:
                self.data["can_bitrate"] = self.combo_can_bitrate.currentData()
                self.data["can_listen_only"] = self.cb_can_listen_only.isChecked()
                self.data["can_watch_auto"] = self.cb_can_watch_auto.isChecked()
            else:
                try:
                    self.data["baudrate"] = int(self.combo_serial_baud.currentText())
                except ValueError:
                    self.data["baudrate"] = 115200
            save_config(self.cfg_filepath, self.data)
            self.action_taken = "saved"
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Nie można zapisać:\n{e}")
            
    def on_delete(self):
        reply = QMessageBox.question(self, "Potwierdzenie", "Czy na pewno chcesz trwale usunąć ten profil?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(self.cfg_filepath)
                self.action_taken = "deleted"
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Błąd", f"Nie można usunąć:\n{e}")


class FilterManagerDialog(QDialog):
    def __init__(self, app_config, parent=None, whitelist_only=False):
        super().__init__(parent)
        self.app_config = app_config
        self.whitelist_only = whitelist_only
        self.setWindowTitle("Zapora (Tylko Dozwolone)" if whitelist_only else "Menadżer Filtrów")
        self.resize(580, 420)
        self.layout = QVBoxLayout(self)
        
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)
        
        # --- Page 0: Table ---
        self.page_table = QWidget()
        self.layout_table = QVBoxLayout(self.page_table)
        
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Aktywny", "Wzór", "Akcja", "Zarządzanie"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.layout_table.addWidget(self.table)
        self.stack.addWidget(self.page_table)
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        self.sort_col = -1
        self.sort_asc = True
        self.table.horizontalHeader().setCursor(Qt.CursorShape.PointingHandCursor)
        
        # --- Page 1: Edit ---
        self.page_edit = QWidget()
        self.layout_edit = QFormLayout(self.page_edit)
        
        self.edit_idx = -1
        self.le_pattern = QLineEdit()
        self.combo_action = QComboBox()
        self.combo_action.addItems(["Ukryj", "Koloruj", "Dozwolony (Whitelist)"])
        self.combo_color = QComboBox()
        populate_color_combo(self.combo_color)
        
        self.combo_action.currentTextChanged.connect(
            lambda t: self.combo_color.setEnabled(t == "Koloruj")
        )
        
        self.layout_edit.addRow("Wzór:", self.le_pattern)
        self.layout_edit.addRow("Akcja:", self.combo_action)
        self.layout_edit.addRow("Kolor:", self.combo_color)
        
        btn_layout = QHBoxLayout()
        self.btn_back = QPushButton("Wstecz")
        self.btn_save = QPushButton("Zapisz")
        self.btn_save.setStyleSheet("background-color: #228be6; color: white;")
        self.btn_del = QPushButton("Usuń")
        self.btn_del.setStyleSheet("background-color: #fa5252; color: white;")
        
        btn_layout.addWidget(self.btn_back)
        btn_layout.addWidget(self.btn_del)
        btn_layout.addWidget(self.btn_save)
        
        self.layout_edit.addRow(btn_layout)
        self.stack.addWidget(self.page_edit)
        
        self.btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btn_save.clicked.connect(self.save_current_edit)
        self.btn_del.clicked.connect(self.delete_current_edit)
        
        self.refresh_table()
        
    def refresh_table(self):
        filters = self.app_config.get("filters", [])
        
        self.shown_indices = []
        for i, f in enumerate(filters):
            if self.whitelist_only and f.get("action") != "allow":
                continue
            self.shown_indices.append(i)
            
        self.table.setRowCount(len(self.shown_indices))
        for row, i in enumerate(self.shown_indices):
            f = filters[i]
            
            is_active = f.get("is_active", True)
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk = QCheckBox()
            chk.setChecked(is_active)
            chk.stateChanged.connect(lambda state, idx=i: self.toggle_active(idx, state))
            chk_layout.addWidget(chk)
            self.table.setCellWidget(row, 0, chk_widget)
            
            item1 = QTableWidgetItem(f.get("pattern", ""))
            item1.setFlags(item1.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, item1)
            
            action = f.get("action", "hide")
            a_text = "Ukryj" if action == "hide" else "Koloruj" if action == "color" else "Dozwolony"
            
            item2 = QTableWidgetItem(a_text)
            item2.setFlags(item2.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if action == "color" and f.get("color"):
                item2.setForeground(QColor(f.get("color")))
            self.table.setItem(row, 2, item2)
            
            widget = QWidget()
            h_layout = QHBoxLayout(widget)
            h_layout.setContentsMargins(2, 2, 2, 2)
            btn_e = QPushButton("Edytuj")
            btn_e.setStyleSheet("QPushButton { padding: 3px 8px; background-color: #228be6; color: white; border: none; border-radius: 3px; } QPushButton:hover { background-color: #1c7ed6; }")
            btn_d = QPushButton("Usuń")
            btn_d.setStyleSheet("QPushButton { padding: 3px 8px; background-color: #fa5252; color: white; border: none; border-radius: 3px; } QPushButton:hover { background-color: #f03e3e; }")
            btn_e.clicked.connect(lambda checked, idx=i: self.open_edit(idx))
            btn_d.clicked.connect(lambda checked, idx=i: self.delete_by_idx(idx))
            h_layout.addWidget(btn_e)
            h_layout.addWidget(btn_d)
            self.table.setCellWidget(row, 3, widget)
            
    def toggle_active(self, idx, state):
        self.app_config["filters"][idx]["is_active"] = (state == 2)
            
    def open_edit(self, idx):
        self.edit_idx = idx
        f = self.app_config["filters"][idx]
        self.le_pattern.setText(f.get("pattern", ""))
        
        action = f.get("action", "hide")
        if action == "hide": self.combo_action.setCurrentText("Ukryj")
        elif action == "allow": self.combo_action.setCurrentText("Dozwolony (Whitelist)")
        else: self.combo_action.setCurrentText("Koloruj")
        
        c = f.get("color", "")
        if c:
            for i in range(self.combo_color.count()):
                if self.combo_color.itemData(i) == c:
                    self.combo_color.setCurrentIndex(i)
                    break
        
        self.stack.setCurrentIndex(1)
        
    def save_current_edit(self):
        f = self.app_config["filters"][self.edit_idx]
        f["pattern"] = self.le_pattern.text()
        a = self.combo_action.currentText()
        if a == "Ukryj": f["action"] = "hide"
        elif a == "Dozwolony (Whitelist)": f["action"] = "allow"
        else: f["action"] = "color"
        f["color"] = self.combo_color.currentData()
        
        self.refresh_table()
        self.stack.setCurrentIndex(0)
        
    def delete_current_edit(self):
        self.delete_by_idx(self.edit_idx)
        self.stack.setCurrentIndex(0)
        
    def delete_by_idx(self, idx):
        reply = QMessageBox.question(self, "Potwierdzenie", "Czy na pewno chcesz usunąć ten filtr?")
        if reply == QMessageBox.StandardButton.Yes:
            self.app_config["filters"].pop(idx)
            self.refresh_table()

    def on_header_clicked(self, logical_index):
        if logical_index in (0, 3):
            return
            
        if self.sort_col == logical_index:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = logical_index
            self.sort_asc = True
            
        if logical_index == 1:
            self.app_config["filters"].sort(key=lambda f: f.get("pattern", "").lower(), reverse=not self.sort_asc)
        elif logical_index == 2:
            self.app_config["filters"].sort(key=lambda f: f.get("action", "hide").lower(), reverse=not self.sort_asc)
            
        self.refresh_table()

class ParserManagerDialog(QDialog):
    def __init__(self, app_config, parent=None):
        super().__init__(parent)
        self.app_config = app_config
        self.setWindowTitle("Menadżer Parserów")
        self.resize(580, 420)
        self.layout = QVBoxLayout(self)
        
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)
        
        # --- Page 0: Table ---
        self.page_table = QWidget()
        self.layout_table = QVBoxLayout(self.page_table)
        
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Aktywny", "Wzór (HEX/Tekst)", "Zastąp tekstem", "Zarządzanie"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.layout_table.addWidget(self.table)
        self.stack.addWidget(self.page_table)
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        self.sort_col = -1
        self.sort_asc = True
        self.table.horizontalHeader().setCursor(Qt.CursorShape.PointingHandCursor)
        
        # --- Page 1: Edit ---
        self.page_edit = QWidget()
        self.layout_edit = QFormLayout(self.page_edit)
        
        self.edit_idx = -1
        self.le_pattern = QLineEdit()
        self.le_text = QLineEdit()
        
        self.layout_edit.addRow("Wzór (HEX/Tekst):", self.le_pattern)
        self.layout_edit.addRow("Zastąp tekstem:", self.le_text)
        
        btn_layout = QHBoxLayout()
        self.btn_back = QPushButton("Wstecz")
        self.btn_save = QPushButton("Zapisz")
        self.btn_save.setStyleSheet("background-color: #228be6; color: white;")
        self.btn_del = QPushButton("Usuń")
        self.btn_del.setStyleSheet("background-color: #fa5252; color: white;")
        
        btn_layout.addWidget(self.btn_back)
        btn_layout.addWidget(self.btn_del)
        btn_layout.addWidget(self.btn_save)
        
        self.layout_edit.addRow(btn_layout)
        self.stack.addWidget(self.page_edit)
        
        self.btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btn_save.clicked.connect(self.save_current_edit)
        self.btn_del.clicked.connect(self.delete_current_edit)
        
        self.refresh_table()
        
    def refresh_table(self):
        parsers = self.app_config.get("parsers", [])
        self.table.setRowCount(len(parsers))
        for i, p in enumerate(parsers):
            is_active = p.get("is_active", True)
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk = QCheckBox()
            chk.setChecked(is_active)
            chk.stateChanged.connect(lambda state, idx=i: self.toggle_active(idx, state))
            chk_layout.addWidget(chk)
            self.table.setCellWidget(i, 0, chk_widget)
            
            self.table.setItem(i, 1, QTableWidgetItem(p.get("pattern", "")))
            self.table.setItem(i, 2, QTableWidgetItem(p.get("text", "")))
            
            widget = QWidget()
            h_layout = QHBoxLayout(widget)
            h_layout.setContentsMargins(2, 2, 2, 2)
            btn_e = QPushButton("Edytuj")
            btn_e.setStyleSheet("QPushButton { padding: 3px 8px; background-color: #228be6; color: white; border: none; border-radius: 3px; } QPushButton:hover { background-color: #1c7ed6; }")
            btn_d = QPushButton("Usuń")
            btn_d.setStyleSheet("QPushButton { padding: 3px 8px; background-color: #fa5252; color: white; border: none; border-radius: 3px; } QPushButton:hover { background-color: #f03e3e; }")
            btn_e.clicked.connect(lambda checked, idx=i: self.open_edit(idx))
            btn_d.clicked.connect(lambda checked, idx=i: self.delete_by_idx(idx))
            h_layout.addWidget(btn_e)
            h_layout.addWidget(btn_d)
            self.table.setCellWidget(i, 3, widget)
            
    def toggle_active(self, idx, state):
        self.app_config["parsers"][idx]["is_active"] = (state == 2)
            
    def open_edit(self, idx):
        self.edit_idx = idx
        p = self.app_config["parsers"][idx]
        self.le_pattern.setText(p.get("pattern", ""))
        self.le_text.setText(p.get("text", ""))
        self.stack.setCurrentIndex(1)
        
    def save_current_edit(self):
        p = self.app_config["parsers"][self.edit_idx]
        p["pattern"] = self.le_pattern.text()
        p["text"] = self.le_text.text()
        self.refresh_table()
        self.stack.setCurrentIndex(0)
        
    def delete_current_edit(self):
        self.delete_by_idx(self.edit_idx)
        self.stack.setCurrentIndex(0)
        
    def delete_by_idx(self, idx):
        reply = QMessageBox.question(self, "Potwierdzenie", "Czy na pewno chcesz usunąć ten parser?")
        if reply == QMessageBox.StandardButton.Yes:
            self.app_config["parsers"].pop(idx)
            self.refresh_table()

    def on_header_clicked(self, logical_index):
        if logical_index in (0, 3):
            return
            
        if self.sort_col == logical_index:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = logical_index
            self.sort_asc = True
            
        if logical_index == 1:
            self.app_config["parsers"].sort(key=lambda p: p.get("pattern", "").lower(), reverse=not self.sort_asc)
        elif logical_index == 2:
            self.app_config["parsers"].sort(key=lambda p: p.get("text", "").lower(), reverse=not self.sort_asc)
            
        self.refresh_table()

# ==========================================
# 5. GŁÓWNY INTERFEJS KARTY (SerialTab)
# ==========================================
class SerialTab(QWidget):
    tab_state_changed = pyqtSignal()
    close_requested = pyqtSignal(object)
    STANDARD_BAUDS = ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600", "1000000"]

    def __init__(self, cli_config="", main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        
        if not os.path.exists(CFG_DIR):
            os.makedirs(CFG_DIR)

        self.worker = None
        self.rx_buffer = bytearray()
        self.text_buffer = ""
        self.has_real_logs = False
        self._last_valid_baud = "115200"
        self.panel_side = "left"
        
        # Struktury dla Live Watch
        self.watch_rows = {} # key -> LiveWatchRowWidget
        self.last_can_timestamps = {} # can_id -> float (timestamp)
        self._unpinned_can_ids = set() # can_ids ręcznie odpięte w bieżącej sesji (pomijane przy can_watch_auto)
        self._known_ports = None # Zbiór portów z poprzedniego skanowania (None = pierwszy rozruch)
        self.watch_body_visible = True
        self.watch_decay_timer = QTimer(self)
        self.watch_decay_timer.setInterval(100)
        self.watch_decay_timer.timeout.connect(self.on_watch_flash_decay)
        
        self.button_states = [False] * 10 
        self.button_timers = [QTimer(self) for _ in range(10)]
        for i, t in enumerate(self.button_timers):
            t.timeout.connect(lambda checked=False, idx=i: self.on_trigger_timeout(idx))
            
        self.gui_buttons = []
        self.macro_runners = []
        
        self.app_settings = load_app_settings()
        self.app_config = get_default_config()
        self.current_cfg_file = ""

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(4, 4, 4, 4)
        outer_layout.setSpacing(4)

        # --- NAGŁÓWEK KARTY W TRYBIE SPLIT VIEW ---
        self.card_header = QFrame()
        self.card_header.setObjectName("SplitCardHeader")
        self.card_header.setFixedHeight(34)
        header_layout = QHBoxLayout(self.card_header)
        header_layout.setContentsMargins(8, 2, 6, 2)
        header_layout.setSpacing(6)
        
        self.lbl_side_badge = QLabel("[LEWA]")
        self.lbl_side_badge.setStyleSheet("color: #74c0fc; font-weight: bold; font-size: 11px; background: transparent;")
        header_layout.addWidget(self.lbl_side_badge)

        self.btn_card_selector = QPushButton("⚪ COM — Profil ▾")
        self.btn_card_selector.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_card_selector.setToolTip("Kliknij, aby przełączyć to okno na inną otwartą kartę")
        self.btn_card_selector.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                padding: 2px 8px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #2f2f37;
                border: 1px solid #3f3f46;
            }
            QPushButton::menu-indicator {
                image: none;
            }
        """)
        self.card_switch_menu = QMenu(self)
        self.card_switch_menu.aboutToShow.connect(self.populate_card_switch_menu)
        self.btn_card_selector.setMenu(self.card_switch_menu)
        header_layout.addWidget(self.btn_card_selector)

        header_layout.addStretch()
        
        self.btn_close_card = QPushButton("✕")
        self.btn_close_card.setFixedSize(22, 22)
        self.btn_close_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close_card.setToolTip("Zamknij tę kartę")
        self.btn_close_card.setStyleSheet("""
            QPushButton { padding: 0px; background: transparent; border: none; color: #a1a1aa; font-weight: bold; font-size: 13px; }
            QPushButton:hover { background-color: #fa5252; color: white; border-radius: 3px; }
        """)
        self.btn_close_card.clicked.connect(lambda: self.close_requested.emit(self))
        header_layout.addWidget(self.btn_close_card)
        
        self.card_header.hide()
        outer_layout.addWidget(self.card_header)

        # --- UKŁAD POZIOMY (Panel akcji + Konsola) ---
        self.content_layout = QHBoxLayout()
        self.content_layout.setContentsMargins(2, 2, 2, 2)
        self.content_layout.setSpacing(6)
        outer_layout.addLayout(self.content_layout, stretch=1)

        # ------------------------------------------
        # PANEL BOCZNY: Zwijany kontener Przyciski + Konfiguracja
        # ------------------------------------------
        self.left_panel_widget = QWidget()
        self.left_panel_widget.setFixedWidth(220)
        left_panel_layout = QVBoxLayout(self.left_panel_widget)
        left_panel_layout.setContentsMargins(0, 0, 0, 0)
        left_panel_layout.setSpacing(6)
        
        left_header_layout = QHBoxLayout()
        lbl_macros = QLabel("Szybkie Akcje (PPM)")
        lbl_macros.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: bold;")
        left_header_layout.addWidget(lbl_macros)
        left_header_layout.addStretch()
        
        self.btn_hide_left = QPushButton("◀ Ukryj")
        self.btn_hide_left.setFixedHeight(22)
        self.btn_hide_left.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hide_left.setToolTip("Zwiń panel przycisków")
        self.btn_hide_left.setStyleSheet("QPushButton { padding: 1px 6px; font-size: 11px; color: #a1a1aa; }")
        self.btn_hide_left.clicked.connect(lambda: self.toggle_left_panel(False))
        left_header_layout.addWidget(self.btn_hide_left)
        left_panel_layout.addLayout(left_header_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        buttons_widget = QWidget()
        self.buttons_layout = QVBoxLayout(buttons_widget)
        self.buttons_layout.setContentsMargins(6, 6, 6, 6)
        self.buttons_layout.setSpacing(6)
        
        for i in range(10):
            btn = QPushButton()
            btn.setFixedSize(198, 44)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, idx=i: self.edit_button_config(idx))
            
            self.gui_buttons.append(btn)
            self.buttons_layout.addWidget(btn)

        self.buttons_layout.addStretch()
        scroll_area.setWidget(buttons_widget)
        left_panel_layout.addWidget(scroll_area)

        cfg_layout = QVBoxLayout()
        cfg_layout.setSpacing(4)
        lbl_cfg = QLabel("Profil konfiguracji (cfg/):")
        lbl_cfg.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        cfg_layout.addWidget(lbl_cfg)
        
        cfg_controls = QHBoxLayout()
        cfg_controls.setSpacing(4)
        self.combo_cfg = QComboBox()
        self.combo_cfg.currentIndexChanged.connect(self.on_config_changed)
        cfg_controls.addWidget(self.combo_cfg, stretch=1)
        
        self.btn_new_cfg = QPushButton("+")
        self.btn_new_cfg.setFixedSize(26, 26)
        self.btn_new_cfg.setStyleSheet("padding: 0px; font-weight: bold;")
        self.btn_new_cfg.setToolTip("Utwórz nowy profil konfiguracji")
        self.btn_new_cfg.clicked.connect(self.create_new_config)
        cfg_controls.addWidget(self.btn_new_cfg)
        
        self.btn_edit_cfg = QPushButton("Edytuj")
        self.btn_edit_cfg.setStyleSheet("padding: 3px 8px;")
        self.btn_edit_cfg.setToolTip("Zbiorcza edycja przycisków, filtrów i parserów profilu")
        self.btn_edit_cfg.clicked.connect(self.edit_current_config)
        cfg_controls.addWidget(self.btn_edit_cfg)
        
        cfg_layout.addLayout(cfg_controls)
        left_panel_layout.addLayout(cfg_layout)

        # ------------------------------------------
        # CZĘŚĆ GŁÓWNA: Pasek Połączenia -> Narzędzia -> Live Watch -> Konsola -> Input
        # ------------------------------------------
        self.right_panel_widget = QWidget()
        self.right_panel_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(self.right_panel_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # --- PASEK 1 (GÓRA): Połączenie i Narzędzia Główne ---
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setSpacing(5)
        
        self.btn_show_left = QPushButton("▶ Akcje")
        self.btn_show_left.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_show_left.setToolTip("Pokaż panel szybkich akcji (po lewej stronie)")
        self.btn_show_left.setStyleSheet("QPushButton { padding: 4px 8px; font-weight: bold; color: #74c0fc; border-color: #228be6; }")
        self.btn_show_left.clicked.connect(lambda: self.toggle_left_panel(True))
        self.btn_show_left.hide()
        top_bar_layout.addWidget(self.btn_show_left)

        top_bar_layout.addWidget(QLabel("Port:"))
        self.port_combo = PortComboBox()
        self.port_combo.currentIndexChanged.connect(lambda: self.tab_state_changed.emit())
        top_bar_layout.addWidget(self.port_combo)

        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setFixedSize(28, 26)
        self.btn_refresh.setStyleSheet("padding: 0px;")
        self.btn_refresh.setToolTip("Odśwież listę portów COM")
        self.btn_refresh.clicked.connect(self.refresh_ports)
        top_bar_layout.addWidget(self.btn_refresh)

        self.lbl_baud = QLabel("Baud:")
        top_bar_layout.addWidget(self.lbl_baud)
        self.baud_combo = QComboBox()
        self.baud_combo.setFixedWidth(95)
        self.baud_combo.addItems(self.STANDARD_BAUDS + ["Własny..."])
        self.baud_combo.setCurrentText("115200")
        self.baud_combo.currentTextChanged.connect(self.on_baud_changed)
        top_bar_layout.addWidget(self.baud_combo)

        self.btn_connect = QPushButton("Połącz")
        self.btn_connect.setFixedWidth(68)
        self.btn_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_connect.setStyleSheet("background-color: #228be6; color: white; font-weight: bold; border: none; padding: 4px 6px;")
        self.btn_connect.clicked.connect(self.toggle_connection)
        top_bar_layout.addWidget(self.btn_connect)

        # Ukryte menu opcji sprzętowych (DTR / RTS / Reset / CAN)
        self.btn_hw_menu = QPushButton("⚙️")
        self.btn_hw_menu.setFixedSize(32, 26)
        self.btn_hw_menu.setStyleSheet("padding: 0px;")
        self.btn_hw_menu.setToolTip("Zaawansowane opcje połączenia (Serial: DTR/RTS/Reset; CAN: Listen-only/Live Watch)")
        self.hw_menu = QMenu(self)
        
        self.action_dtr = QAction("Linia DTR (Data Terminal Ready)", self, checkable=True)
        self.action_dtr.triggered.connect(self.toggle_dtr)
        self.hw_menu.addAction(self.action_dtr)

        self.action_rts = QAction("Linia RTS (Request To Send)", self, checkable=True)
        self.action_rts.triggered.connect(self.toggle_rts)
        self.hw_menu.addAction(self.action_rts)

        self.action_reset_mcu = QAction("🔄 Impuls Reset MCU (DTR/RTS 100ms)", self)
        self.action_reset_mcu.triggered.connect(self.pulse_reset_mcu)
        self.hw_menu.addAction(self.action_reset_mcu)

        # Opcje dedykowane dla CAN
        self.action_listen_only = QAction("Tryb nasłuchu (Listen-only)", self, checkable=True)
        self.action_listen_only.triggered.connect(self.toggle_can_listen_only)
        self.hw_menu.addAction(self.action_listen_only)

        self.action_clear_watch = QAction("Wyzeruj wiersze Live Watch", self)
        self.action_clear_watch.triggered.connect(self.clear_all_watches)
        self.hw_menu.addAction(self.action_clear_watch)
        
        self.btn_hw_menu.setMenu(self.hw_menu)
        top_bar_layout.addWidget(self.btn_hw_menu)

        top_bar_layout.addSpacing(2)
        self.lbl_rx = QLabel("RX:")
        top_bar_layout.addWidget(self.lbl_rx)
        self.radio_ascii = QRadioButton("ASCII")
        self.radio_binary = QRadioButton("HEX")
        self.radio_ascii.toggled.connect(lambda: self.save_current_settings_to_config(force=False))
        top_bar_layout.addWidget(self.radio_ascii)
        top_bar_layout.addWidget(self.radio_binary)

        top_bar_layout.addStretch()

        self.btn_whitelist_warn = QPushButton("⚠ ZAPORA")
        self.btn_whitelist_warn.setStyleSheet("background-color: #e03131; color: white; font-weight: bold; border: none; padding: 4px 6px;")
        self.btn_whitelist_warn.setToolTip("Terminal w trybie ZAPORY! Ignoruje wszystko poza Dozwolonymi filtrami.")
        self.btn_whitelist_warn.clicked.connect(self.open_whitelist_manager)
        top_bar_layout.addWidget(self.btn_whitelist_warn)

        self.btn_toggle_tools = QPushButton("🌪️ Filtry (0)")
        self.btn_toggle_tools.setCheckable(True)
        self.btn_toggle_tools.setToolTip("Pokaż/Ukryj pasek szybkiego dodawania filtrów i parserów")
        self.btn_toggle_tools.toggled.connect(self.toggle_tools_panel)
        top_bar_layout.addWidget(self.btn_toggle_tools)

        self.btn_show_right = QPushButton("Akcje ◀")
        self.btn_show_right.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_show_right.setToolTip("Pokaż panel szybkich akcji (po prawej stronie)")
        self.btn_show_right.setStyleSheet("QPushButton { padding: 4px 8px; font-weight: bold; color: #74c0fc; border-color: #228be6; }")
        self.btn_show_right.clicked.connect(lambda: self.toggle_left_panel(True))
        self.btn_show_right.hide()
        top_bar_layout.addWidget(self.btn_show_right)

        right_layout.addLayout(top_bar_layout)

        # --- PASEK 2: Narzędzia Konsoli (Wyczyść, Zapisz, Marker, Szukaj, Limit) ---
        console_tools_layout = QHBoxLayout()
        console_tools_layout.setSpacing(6)

        self.btn_clear = QPushButton("🗑️ Wyczyść")
        self.btn_clear.clicked.connect(self.console_clear)
        console_tools_layout.addWidget(self.btn_clear)

        self.btn_save_log = QPushButton("💾 Zapisz Logi")
        self.btn_save_log.clicked.connect(self.save_logs)
        console_tools_layout.addWidget(self.btn_save_log)

        self.btn_marker = QPushButton("📌 Marker")
        self.btn_marker.clicked.connect(self.insert_marker)
        console_tools_layout.addWidget(self.btn_marker)

        self.btn_search = QPushButton("🔍 Szukaj")
        self.btn_search.setToolTip("Szukaj w logach (Ctrl+F)")
        self.btn_search.clicked.connect(self.show_search_dialog)
        console_tools_layout.addWidget(self.btn_search)

        console_tools_layout.addStretch()

        console_tools_layout.addWidget(QLabel("Limit:"))
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(100, 100000)
        self.spin_limit.setSingleStep(1000)
        self.spin_limit.setValue(5000)
        console_tools_layout.addWidget(self.spin_limit)

        right_layout.addLayout(console_tools_layout)

        # --- ZWIJANY PANEL: Filtry i Parsery ---
        self.tools_frame = QFrame()
        self.tools_frame.setObjectName("CollapsiblePanel")
        tools_vbox = QVBoxLayout(self.tools_frame)
        tools_vbox.setContentsMargins(8, 8, 8, 8)
        tools_vbox.setSpacing(6)

        # Wiersz Filtrów
        filter_layout = QHBoxLayout()
        self.le_filter_pattern = QLineEdit()
        self.le_filter_pattern.setPlaceholderText("Wzór filtra (np. *temp* lub AA 01*)...")
        self.le_filter_pattern.returnPressed.connect(self.add_filter)
        
        self.combo_filter_action = QComboBox()
        self.combo_filter_action.addItems(["Ukryj", "Koloruj", "Dozwolony (Whitelist)"])
        
        self.combo_filter_color = QComboBox()
        populate_color_combo(self.combo_filter_color)
        self.combo_filter_color.setEnabled(False)
        self.combo_filter_action.currentTextChanged.connect(
            lambda t: self.combo_filter_color.setEnabled(t == "Koloruj")
        )
        
        self.btn_add_filter = QPushButton("+ Dodaj")
        self.btn_add_filter.clicked.connect(self.add_filter)

        self.btn_edit_filter = QPushButton("Menadżer Filtrów")
        self.btn_edit_filter.clicked.connect(self.edit_filter)
        
        filter_layout.addWidget(QLabel("Filtr:"))
        filter_layout.addWidget(self.le_filter_pattern, stretch=1)
        filter_layout.addWidget(self.combo_filter_action)
        filter_layout.addWidget(self.combo_filter_color)
        filter_layout.addWidget(self.btn_add_filter)
        filter_layout.addWidget(self.btn_edit_filter)
        tools_vbox.addLayout(filter_layout)

        # Wiersz Parserów
        parser_layout = QHBoxLayout()
        self.le_parser_pattern = QLineEdit()
        self.le_parser_pattern.setPlaceholderText("Wzór ramki (np. *AA 01*)...")
        self.le_parser_pattern.returnPressed.connect(self.add_parser)
        
        self.le_parser_text = QLineEdit()
        self.le_parser_text.setPlaceholderText("Zastąp tekstem (np. [START])...")
        self.le_parser_text.returnPressed.connect(self.add_parser)
        
        self.btn_add_parser = QPushButton("+ Dodaj")
        self.btn_add_parser.clicked.connect(self.add_parser)

        self.btn_edit_parser = QPushButton("Menadżer Parserów")
        self.btn_edit_parser.clicked.connect(self.edit_parser)
        
        parser_layout.addWidget(QLabel("Parser:"))
        parser_layout.addWidget(self.le_parser_pattern, stretch=1)
        parser_layout.addWidget(self.le_parser_text, stretch=1)
        parser_layout.addWidget(self.btn_add_parser)
        parser_layout.addWidget(self.btn_edit_parser)
        tools_vbox.addLayout(parser_layout)

        self.tools_frame.setVisible(False)
        right_layout.addWidget(self.tools_frame)

        # --- PANEL LIVE WATCH (PRZYPIĘTE LOGI TELEMETRYCZNE U GÓRY KONSOLI) ---
        self.watch_frame = QFrame()
        self.watch_frame.setObjectName("LiveWatchFrame")
        watch_vbox = QVBoxLayout(self.watch_frame)
        watch_vbox.setContentsMargins(8, 4, 8, 6)
        watch_vbox.setSpacing(4)

        watch_header = QHBoxLayout()
        watch_header.setSpacing(8)
        self.lbl_watch_title = QLabel("📌 Live Watch (0)")
        self.lbl_watch_title.setStyleSheet("color: #fcc419; font-weight: bold; font-size: 12px; background: transparent;")
        self.lbl_watch_title.setToolTip("Przypięte logi aktualizowane w miejscu (prefiks '@' z MCU lub PPM w konsoli -> Przypnij)")
        watch_header.addWidget(self.lbl_watch_title)

        self.cb_watch_print = QCheckBox("Pokaż też w konsoli")
        self.cb_watch_print.setStyleSheet("color: #a1a1aa; font-size: 11px; background: transparent;")
        self.cb_watch_print.setToolTip("Gdy odznaczone, przypięte ramki są ukrywane w głównej konsoli na dole")
        self.cb_watch_print.toggled.connect(self.on_watch_print_toggled)
        watch_header.addWidget(self.cb_watch_print)

        watch_header.addStretch()

        self.btn_clear_watches = QPushButton("Odepnij wszystkie")
        self.btn_clear_watches.setFixedHeight(20)
        self.btn_clear_watches.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_watches.setStyleSheet("QPushButton { padding: 1px 6px; font-size: 11px; color: #a1a1aa; }")
        self.btn_clear_watches.clicked.connect(self.clear_all_watches)
        watch_header.addWidget(self.btn_clear_watches)

        # Mały przycisk po prawej stronie do ukrycia/odkrycia przypiętych logów (domyślnie odkryty)
        self.btn_toggle_watch_body = QPushButton("▲ Ukryj")
        self.btn_toggle_watch_body.setFixedHeight(20)
        self.btn_toggle_watch_body.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_watch_body.setToolTip("Zwiń / Rozwiń listę przypiętych wierszy Live Watch")
        self.btn_toggle_watch_body.setStyleSheet("QPushButton { padding: 1px 8px; font-size: 11px; font-weight: bold; color: #fcc419; border-color: #fcc419; }")
        self.btn_toggle_watch_body.clicked.connect(self.toggle_watch_body)
        watch_header.addWidget(self.btn_toggle_watch_body)

        watch_vbox.addLayout(watch_header)

        # Obszar przewijany (suwak pojawia się automatycznie, gdy wysokość przekroczy 70% konsoli)
        self.watch_scroll = QScrollArea()
        self.watch_scroll.setWidgetResizable(True)
        self.watch_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.watch_list_container = QWidget()
        self.watch_list_container.setStyleSheet("background: transparent;")
        self.watch_list_layout = QVBoxLayout(self.watch_list_container)
        self.watch_list_layout.setContentsMargins(0, 0, 0, 0)
        self.watch_list_layout.setSpacing(3)
        self.watch_scroll.setWidget(self.watch_list_container)
        watch_vbox.addWidget(self.watch_scroll)

        self.watch_frame.hide()
        right_layout.addWidget(self.watch_frame)

        # --- KONSOLA GŁÓWNA ---
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #121214;
                border: 1px solid #27272a;
                border-radius: 4px;
                font-family: 'Consolas', 'JetBrains Mono', monospace;
                font-size: 13px;
                padding: 6px;
            }
        """)
        self.spin_limit.valueChanged.connect(self.console.document().setMaximumBlockCount)
        self.console.document().setMaximumBlockCount(5000)
        
        self.search_dialog = None
        self.shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self.console)
        self.shortcut_search.activated.connect(self.show_search_dialog)
        
        self.console.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.console.customContextMenuRequested.connect(self.show_console_context_menu)
        
        right_layout.addWidget(self.console, stretch=1)

        # Pływający pasek przewijania w dół
        self.scroll_btn_layout = QHBoxLayout()
        self.scroll_btn_layout.addStretch()
        self.btn_scroll_down = QPushButton("▼ Wróć do najnowszych logów (Auto-scroll)")
        self.btn_scroll_down.setStyleSheet("background-color: #228be6; color: white; border: none; border-radius: 4px; padding: 3px 12px; font-weight: bold;")
        self.btn_scroll_down.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scroll_down.clicked.connect(self.force_scroll_to_bottom)
        self.btn_scroll_down.hide()
        self.scroll_btn_layout.addWidget(self.btn_scroll_down)
        right_layout.addLayout(self.scroll_btn_layout)
        
        self.console.verticalScrollBar().valueChanged.connect(self.on_scroll_changed)
        self.console.verticalScrollBar().rangeChanged.connect(self.on_scroll_changed)

        # --- PASEK DOLNY: Wprowadzanie komend (TX) ---
        cmd_layout = QHBoxLayout()
        cmd_layout.setSpacing(6)
        
        self.cmd_input = CommandLineEdit()
        self.cmd_input.setPlaceholderText("Wpisz komendę (Enter = wyślij, ↑/↓ = historia)...")
        self.cmd_input.returnPressed.connect(self.send_manual_command) 
        
        self.combo_cmd_format = QComboBox()
        self.combo_cmd_format.addItems(["ASCII", "HEX"])
        self.combo_cmd_format.setToolTip("Format wysyłanej komendy")

        self.combo_eol = QComboBox()
        self.combo_eol.addItem("CRLF (\\r\\n)", "\r\n")
        self.combo_eol.addItem("LF (\\n)", "\n")
        self.combo_eol.addItem("CR (\\r)", "\r")
        self.combo_eol.addItem("Brak EOL", "")
        self.combo_eol.setToolTip("Znak końca linii dodawany do komend ASCII")
        self.combo_calc_eol_state()
        self.combo_cmd_format.currentTextChanged.connect(self.combo_calc_eol_state)
        self.combo_eol.currentIndexChanged.connect(lambda: self.save_current_settings_to_config(force=False))
        
        self.btn_send_cmd = QPushButton("Wyślij ➤")
        self.btn_send_cmd.setFixedWidth(80)
        self.btn_send_cmd.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send_cmd.setStyleSheet("background-color: #228be6; color: white; font-weight: bold; border: none;")
        self.btn_send_cmd.clicked.connect(self.send_manual_command)
        
        cmd_layout.addWidget(self.cmd_input, stretch=1)
        cmd_layout.addWidget(self.combo_cmd_format)
        cmd_layout.addWidget(self.combo_eol)
        cmd_layout.addWidget(self.btn_send_cmd)
        right_layout.addLayout(cmd_layout)

        # Domyślnie lewy panel po lewej, konsola po prawej
        self.content_layout.addWidget(self.left_panel_widget)
        self.content_layout.addWidget(self.right_panel_widget, stretch=1)

        target_cfg = self.app_settings.get("last_config", "default.json")
        if cli_config:
            if not cli_config.endswith('.json'):
                cli_config += '.json'
            target_cfg = cli_config

        self.refresh_ports()
        self.refresh_configs_list(select_file=target_cfg)

    # ==========================================
    # OBSŁUGA LIVE WATCH (PRZYPINANIE, BŁYSKI, 70% WYSOKOŚCI)
    # ==========================================
    def strip_rx_prefix(self, line: str) -> str:
        """Usuwa prefiks 'RX [HH:MM:SS.mmm]: ' jeśli użytkownik zaznaczył linię w konsoli."""
        return re.sub(r'^(?:RX|TX)\s*\[\d{2}:\d{2}:\d{2}\.\d{3}\]:\s*', '', line.strip())

    def extract_watch_key(self, msg: str) -> str:
        """Wyciąga klucz identyfikujący wiadomość (np. '[IO_MGR]' lub pierwsze słowo/tag przed dwukropkiem)."""
        clean = self.strip_rx_prefix(msg).lstrip('@').strip()
        if not clean:
            return ""
        # 1. Jeśli zaczyna się od tagu w nawiasie kwadratowym, np. [IO_MGR] BTN: ...
        m = re.match(r'^(\[[^\]]+\])', clean)
        if m:
            return m.group(1)
        # 2. Jeśli ma postać NAZWA: wartość
        if ':' in clean:
            prefix = clean.split(':', 1)[0].strip()
            if 1 <= len(prefix) <= 28:
                return prefix
        # 3. Pierwszy wyraz
        parts = clean.split()
        return parts[0][:28] if parts else ""

    def insert_watch_row_sorted(self, row: LiveWatchRowWidget):
        if row.sort_key is None:
            self.watch_list_layout.addWidget(row)
            return
        inserted = False
        for i in range(self.watch_list_layout.count()):
            item = self.watch_list_layout.itemAt(i)
            w = item.widget() if item else None
            if isinstance(w, LiveWatchRowWidget) and getattr(w, "sort_key", None) is not None:
                if row.sort_key < w.sort_key:
                    self.watch_list_layout.insertWidget(i, row)
                    inserted = True
                    break
        if not inserted:
            self.watch_list_layout.addWidget(row)

    def pin_to_live_watch(self, key: str, initial_msg: str = ""):
        key = key.strip()
        if not key:
            return
        is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
        if is_can:
            norm_key = normalize_can_id_text(key)
            if norm_key:
                key = norm_key
        self._unpinned_can_ids.discard(key)
        patterns = self.app_config.setdefault("watch_patterns", [])
        if key not in patterns:
            patterns.append(key)
            self.save_current_settings_to_config(force=True)

        if key not in self.watch_rows:
            sort_k = can_id_sort_key(key) if is_can else None
            row = LiveWatchRowWidget(key, self, show_period=is_can, sort_key=sort_k)
            row.unpin_requested.connect(self.unpin_live_watch)
            self.watch_rows[key] = row
            self.insert_watch_row_sorted(row)

        if initial_msg:
            clean_msg = self.strip_rx_prefix(initial_msg).lstrip('@').strip()
            self.watch_rows[key].update_message(clean_msg, self.get_timestamp())
            if not self.watch_decay_timer.isActive():
                self.watch_decay_timer.start()

        self.update_watch_panel_geometry()

    def unpin_live_watch(self, key: str):
        self._unpinned_can_ids.add(key)
        patterns = self.app_config.get("watch_patterns", [])
        if key in patterns:
            patterns.remove(key)
            self.save_current_settings_to_config(force=True)
        row = self.watch_rows.pop(key, None)
        if row:
            row.setParent(None)
            row.deleteLater()
        self.update_watch_panel_geometry()

    def clear_all_watches(self):
        for k in list(self.watch_rows.keys()):
            self._unpinned_can_ids.add(k)
        self.app_config["watch_patterns"] = []
        self.save_current_settings_to_config(force=True)
        for row in self.watch_rows.values():
            row.setParent(None)
            row.deleteLater()
        self.watch_rows.clear()
        self.update_watch_panel_geometry()

    def toggle_watch_body(self):
        self.watch_body_visible = not self.watch_body_visible
        self.watch_scroll.setVisible(self.watch_body_visible)
        self.btn_toggle_watch_body.setText("▲ Ukryj" if self.watch_body_visible else "▼ Pokaż")
        self.update_watch_panel_geometry()

    def on_watch_print_toggled(self, checked: bool):
        self.app_config["watch_print_in_console"] = checked
        self.save_current_settings_to_config(force=True)

    def update_watch_panel_geometry(self):
        count = len(self.watch_rows)
        self.lbl_watch_title.setText(f"📌 Live Watch ({count})")
        if count == 0:
            self.watch_frame.hide()
            return

        self.watch_frame.show()
        if not self.watch_body_visible:
            self.watch_scroll.hide()
            self.watch_frame.setFixedHeight(34)
            return

        self.watch_scroll.show()
        self.watch_frame.setMinimumHeight(0)
        self.watch_frame.setMaximumHeight(16777215)

        # Oblicz 70% dostępnej przestrzeni pionowej (konsola + watch_frame)
        available_h = self.console.height() + (self.watch_frame.height() if self.watch_frame.isVisible() else 0)
        if available_h < 150:
            available_h = max(350, self.height() - 160)
        max_watch_h = max(65, int(available_h * 0.70))

        row_h = 29
        content_h = count * row_h + 4
        scroll_h = min(content_h, max_watch_h - 34)
        self.watch_scroll.setFixedHeight(max(28, scroll_h))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.watch_rows:
            self.update_watch_panel_geometry()

    def on_watch_flash_decay(self):
        now = time.monotonic()
        any_active = False
        for row in self.watch_rows.values():
            if row.render_html(now):
                any_active = True
        if not any_active:
            self.watch_decay_timer.stop()

    def handle_incoming_watch_check(self, raw_msg: str, ts: str):
        """
        Sprawdza, czy odebrana wiadomość ma trafić do Live Watch (przez prefiks '@' lub dopasowanie klucza).
        Zwraca (matched_watch, clean_msg).
        """
        stripped = raw_msg.strip()
        auto_pin = False
        if stripped.startswith('@'):
            auto_pin = True
            stripped = stripped[1:].strip()

        matched_key = None
        for pattern in self.app_config.get("watch_patterns", []):
            if stripped.startswith(pattern) or fnmatch.fnmatch(stripped, f"*{pattern}*"):
                matched_key = pattern
                break

        if auto_pin and not matched_key:
            matched_key = self.extract_watch_key(stripped)
            if matched_key and matched_key not in self.app_config.get("watch_patterns", []):
                self.app_config.setdefault("watch_patterns", []).append(matched_key)
                self.save_current_settings_to_config(force=True)

        if matched_key:
            if matched_key not in self.watch_rows:
                row = LiveWatchRowWidget(matched_key, self)
                row.unpin_requested.connect(self.unpin_live_watch)
                self.watch_rows[matched_key] = row
                self.watch_list_layout.addWidget(row)
                self.update_watch_panel_geometry()

            self.watch_rows[matched_key].update_message(stripped, ts)
            if not self.watch_decay_timer.isActive():
                self.watch_decay_timer.start()
            return True, stripped

        return False, raw_msg

    # ==========================================
    # MENU WYBORU KARTY W NAGŁÓWKU (POMIJA BIEŻĄCĄ KARTĘ)
    # ==========================================
    def populate_card_switch_menu(self):
        self.card_switch_menu.clear()
        if not self.main_window:
            return
            
        other_tabs = [t for t in self.main_window.tab_list if t is not self]
        if not other_tabs:
            act = QAction("Brak innych otwartych kart", self)
            act.setEnabled(False)
            self.card_switch_menu.addAction(act)
            return
            
        for t in other_tabs:
            idx = self.main_window.tab_list.index(t) + 1
            port = t.get_selected_port_device() or "Brak"
            cfg = t.combo_cfg.currentText() or "default.json"
            dot = "🟢" if (t.worker and t.worker.is_running) else "⚪"
            
            is_other_split_side = (
                (self.panel_side == "left" and t is self.main_window.split_right_tab) or
                (self.panel_side == "right" and t is self.main_window.split_left_tab)
            )
            suffix = "   (Zamień miejscami ⇄)" if is_other_split_side else ""
            label = f"[{idx}]  {dot} {port}  —  Profil: {cfg}{suffix}"
            
            act = QAction(label, self)
            act.triggered.connect(lambda checked=False, target=t: self.main_window.switch_split_card(self.panel_side, target))
            self.card_switch_menu.addAction(act)

    # ==========================================
    # POZYCJONOWANIE PANELU AKCJI (LEWA / PRAWA KRAWĘDŹ)
    # ==========================================
    def set_panel_side(self, side: str, show_header: bool = False):
        self.panel_side = side
        self.card_header.setVisible(show_header)
        
        self.content_layout.removeWidget(self.left_panel_widget)
        self.content_layout.removeWidget(self.right_panel_widget)
        
        if side == "right":
            self.content_layout.addWidget(self.right_panel_widget, stretch=1)
            self.content_layout.addWidget(self.left_panel_widget)
            self.btn_hide_left.setText("Ukryj ▶")
        else:
            self.content_layout.addWidget(self.left_panel_widget)
            self.content_layout.addWidget(self.right_panel_widget, stretch=1)
            self.btn_hide_left.setText("◀ Ukryj")
            
        self.update_collapse_buttons()

    def toggle_left_panel(self, show: bool):
        self.left_panel_widget.setVisible(show)
        self.update_collapse_buttons()

    def update_collapse_buttons(self):
        is_visible = not self.left_panel_widget.isHidden()
        if is_visible:
            self.btn_show_left.hide()
            self.btn_show_right.hide()
        else:
            if self.panel_side == "right":
                self.btn_show_left.hide()
                self.btn_show_right.show()
            else:
                self.btn_show_left.show()
                self.btn_show_right.hide()

    def update_header_title(self):
        connected = bool(self.worker and self.worker.is_running)
        dot = "🟢" if connected else "⚪"
        port = self.get_selected_port_device() or "Brak portu"
        cfg = self.combo_cfg.currentText() or "default.json"
        side_label = "LEWA" if self.panel_side == "left" else "PRAWA"
        
        self.lbl_side_badge.setText(f"[{side_label}]")
        is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
        if is_can:
            br_label = format_bitrate_label(self.app_config.get("can_bitrate", DEFAULT_CAN_BITRATE))
            lo_tag = " [LO]" if self.app_config.get("can_listen_only", False) else ""
            mode_tag = f" · CAN {br_label}{lo_tag}"
        else:
            mode_tag = ""
        self.btn_card_selector.setText(f"{dot}  {port}{mode_tag}   —   Profil: {cfg}   ▾")
        
        border_col = "#37b24d" if connected else "#228be6"
        self.card_header.setStyleSheet(f"""
            QFrame#SplitCardHeader {{
                background-color: #232329;
                border-top: 2px solid {border_col};
                border-bottom: 1px solid #323238;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
        """)

    # ==========================================
    # BAUDRATE, BITRATE I INTERFEJS TRANSPORTU
    # ==========================================
    def apply_transport_ui(self):
        is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
        
        self.lbl_baud.setText("Bitrate:" if is_can else "Baud:")
        self.baud_combo.blockSignals(True)
        self.baud_combo.clear()
        
        if is_can:
            current_br = self.app_config.get("can_bitrate", DEFAULT_CAN_BITRATE)
            for br in CAN_BITRATES:
                label = f"{format_bitrate_label(br)}"
                self.baud_combo.addItem(label, br)
                if br == current_br:
                    self.baud_combo.setCurrentIndex(self.baud_combo.count() - 1)
            self.baud_combo.setToolTip("Prędkość transmisji magistrali CAN")
            
            self.lbl_rx.hide()
            self.radio_ascii.hide()
            self.radio_binary.hide()
            self.combo_cmd_format.hide()
            self.combo_eol.hide()
            self.cmd_input.setPlaceholderText("Wpisz ramkę CAN (np. 187#01 02 03, Enter = wyślij)...")
            
            self.action_dtr.setVisible(False)
            self.action_rts.setVisible(False)
            self.action_reset_mcu.setVisible(False)
            self.action_listen_only.setVisible(True)
            self.action_listen_only.setChecked(bool(self.app_config.get("can_listen_only", False)))
            self.action_clear_watch.setVisible(True)
        else:
            self.baud_combo.addItems(self.STANDARD_BAUDS + ["Własny..."])
            saved_baud = str(self.app_config.get("baudrate", 115200))
            self.set_baudrate_value(saved_baud)
            self.baud_combo.setToolTip("Prędkość transmisji portu szeregowego (Baudrate)")
            
            self.lbl_rx.show()
            self.radio_ascii.show()
            self.radio_binary.show()
            self.combo_cmd_format.show()
            self.combo_eol.show()
            self.cmd_input.setPlaceholderText("Wpisz komendę (Enter = wyślij, ↑/↓ = historia)...")
            
            self.action_dtr.setVisible(True)
            self.action_rts.setVisible(True)
            self.action_reset_mcu.setVisible(True)
            self.action_listen_only.setVisible(False)
            self.action_clear_watch.setVisible(False)
            
        self.baud_combo.blockSignals(False)
        self.update_header_title()

    def toggle_can_listen_only(self, checked):
        self.app_config["can_listen_only"] = checked
        self.save_current_settings_to_config(force=True)
        self.update_header_title()
        self.log_info(f"Tryb nasłuchu CAN (Listen-only): {'WŁĄCZONY' if checked else 'WYŁĄCZONY'} (wymaga ponownego połączenia)")

    def set_baudrate_value(self, baud_str: str):
        self.baud_combo.blockSignals(True)
        idx = self.baud_combo.findText(baud_str)
        if idx == -1:
            custom_idx = self.baud_combo.findText("Własny...")
            insert_pos = custom_idx if custom_idx != -1 else self.baud_combo.count()
            self.baud_combo.insertItem(insert_pos, baud_str)
            self.baud_combo.setCurrentIndex(insert_pos)
        else:
            self.baud_combo.setCurrentIndex(idx)
        self._last_valid_baud = baud_str
        self.baud_combo.blockSignals(False)

    def on_baud_changed(self, text: str):
        is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
        if is_can:
            bitrate_val = self.baud_combo.currentData()
            if bitrate_val is not None:
                self.app_config["can_bitrate"] = int(bitrate_val)
                self.save_current_settings_to_config(force=False)
                self.update_header_title()
            return

        if text == "Własny...":
            val, ok = QInputDialog.getInt(
                self, "Własny Baudrate", "Podaj prędkość transmisji (bps):", 
                int(self._last_valid_baud) if self._last_valid_baud.isdigit() else 115200, 
                300, 10000000, 100
            )
            if ok:
                self.set_baudrate_value(str(val))
                self.save_current_settings_to_config(force=False)
            else:
                self.set_baudrate_value(self._last_valid_baud)
        else:
            self._last_valid_baud = text
            self.save_current_settings_to_config(force=False)

    def combo_calc_eol_state(self):
        self.combo_eol.setEnabled(self.combo_cmd_format.currentText() == "ASCII")

    def toggle_tools_panel(self, checked):
        self.tools_frame.setVisible(checked)

    def console_clear(self):
        self.console.clear()
        self.has_real_logs = False

    # ==========================================
    # STEROWANIE LINIAMI DTR / RTS
    # ==========================================
    def toggle_dtr(self, checked):
        if self.worker and self.worker.is_running:
            self.worker.set_dtr(checked)
            self.log_info(f"Linia DTR ustawiona na: {'AKTYWNA (ON)' if checked else 'NIEAKTYWNA (OFF)'}")
        else:
            self.log_info("Połącz się z portem COM, aby sterować linią DTR.")
            self.action_dtr.setChecked(not checked)

    def toggle_rts(self, checked):
        if self.worker and self.worker.is_running:
            self.worker.set_rts(checked)
            self.log_info(f"Linia RTS ustawiona na: {'AKTYWNA (ON)' if checked else 'NIEAKTYWNA (OFF)'}")
        else:
            self.log_info("Połącz się z portem COM, aby sterować linią RTS.")
            self.action_rts.setChecked(not checked)

    def pulse_reset_mcu(self):
        if not self.worker or not self.worker.is_running:
            self.log_info("Połącz się z portem COM, aby wykonać impuls Reset.")
            return
        self.log_info("Wysyłanie impulsu Reset MCU (DTR/RTS 100ms)...")
        self.worker.set_dtr(False)
        self.worker.set_rts(True)
        QTimer.singleShot(100, self._finish_pulse_reset)

    def _finish_pulse_reset(self):
        if self.worker and self.worker.is_running:
            self.worker.set_dtr(self.action_dtr.isChecked())
            self.worker.set_rts(self.action_rts.isChecked())
            self.log_info("Impuls Reset zakończony.")

    # ==========================================
    # ZARZĄDZANIE KONFIGURACJAMI
    # ==========================================
    def refresh_configs_list(self, select_file=None):
        self.combo_cfg.blockSignals(True)
        self.combo_cfg.clear()
        
        files = [f for f in os.listdir(CFG_DIR) if f.endswith('.json') and f != "app_settings.json"]
        
        if "default.json" in files and select_file != "default.json":
            files.remove("default.json")
            
        if not files:
            files = ["default.json"]
            
        self.combo_cfg.addItems(files)
        target_file = select_file if select_file and select_file in files else files[0]
        if target_file:
            self.combo_cfg.setCurrentText(target_file)
        self.combo_cfg.blockSignals(False)
        
        self.on_config_changed()

    def edit_current_config(self):
        if not self.current_cfg_file or not os.path.exists(self.current_cfg_file):
            return
            
        dlg = ConfigEditDialog(self.current_cfg_file, self)
        dlg.exec()
        if dlg.action_taken == "saved":
            self.app_config = load_config(self.current_cfg_file)
            self.refresh_ports()
            self.on_config_changed()
            QMessageBox.information(self, "Zapisano", "Konfiguracja została zaktualizowana.")
        elif dlg.action_taken == "deleted":
            self.refresh_configs_list()

    def create_new_config(self):
        name, ok = QInputDialog.getText(self, "Nowa Konfiguracja", "Podaj nazwę profilu (bez .json):")
        if ok and name:
            filename = name.strip()
            if not filename.endswith('.json'):
                filename += '.json'
                
            filepath = os.path.join(CFG_DIR, filename)
            if not os.path.exists(filepath):
                def_cfg = get_default_config()
                if self.app_config:
                    def_cfg["transport"] = self.app_config.get("transport", TRANSPORT_SERIAL)
                    def_cfg["can_bitrate"] = self.app_config.get("can_bitrate", DEFAULT_CAN_BITRATE)
                    def_cfg["can_listen_only"] = self.app_config.get("can_listen_only", False)
                    def_cfg["can_watch_auto"] = self.app_config.get("can_watch_auto", True)
                save_config(filepath, def_cfg)
                self.log_info(f"Utworzono nową konfigurację: {filename}")
                self.refresh_configs_list(select_file=filename)
            else:
                QMessageBox.warning(self, "Błąd", "Konfiguracja o tej nazwie już istnieje!")

    def on_config_changed(self):
        selected_file = self.combo_cfg.currentText()
        if not selected_file:
            return

        if self.current_cfg_file:
            self.save_current_settings_to_config(force=False)

        if self.worker and self.worker.is_running:
            self.toggle_connection()

        self.current_cfg_file = os.path.join(CFG_DIR, selected_file)
        self.app_config = load_config(self.current_cfg_file)
        self.last_can_timestamps.clear()
        self._unpinned_can_ids.clear()
        
        self.log_info(f"Wczytano konfigurację: {selected_file}")

        self.app_settings["last_config"] = selected_file
        save_app_settings(self.app_settings)

        saved_port = self.app_config.get("port")
        if saved_port:
            for i in range(self.port_combo.count()):
                if self.port_combo.itemData(i, Qt.ItemDataRole.UserRole) == saved_port:
                    self.port_combo.setCurrentIndex(i)
                    break
            
        self.apply_transport_ui()
            
        if self.app_config.get("mode") == "BINARY":
            self.radio_binary.setChecked(True)
        else:
            self.radio_ascii.setChecked(True)

        eol_map = {"CRLF": 0, "LF": 1, "CR": 2, "NONE": 3}
        self.combo_eol.blockSignals(True)
        self.combo_eol.setCurrentIndex(eol_map.get(self.app_config.get("eol", "CRLF"), 0))
        self.combo_eol.blockSignals(False)

        self.cb_watch_print.blockSignals(True)
        self.cb_watch_print.setChecked(self.app_config.get("watch_print_in_console", False))
        self.cb_watch_print.blockSignals(False)

        # Wyczyść widżety watch przy zmianie profilu (pojawią się ponownie po odebraniu pasujących ramek)
        for row in self.watch_rows.values():
            row.setParent(None)
            row.deleteLater()
        self.watch_rows.clear()
        self.update_watch_panel_geometry()

        for i in range(10):
            self.button_states[i] = False 
            self.setup_button(i)
            
        self.refresh_filter_combo()
        self.update_header_title()
        self.tab_state_changed.emit()

    def get_selected_port_device(self):
        idx = self.port_combo.currentIndex()
        if idx >= 0:
            dev = self.port_combo.itemData(idx, Qt.ItemDataRole.UserRole)
            if dev:
                return dev
        return self.port_combo.currentText()

    def get_tab_title(self):
        self.update_header_title()
        connected = bool(self.worker and self.worker.is_running)
        dot = "🟢" if connected else "⚪"
        port = self.get_selected_port_device() or "Brak"
        cfg = self.combo_cfg.currentText() or "default.json"
        is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
        tag = " · CAN" if is_can else ""
        if cfg in (f"{port}.json", f"{port}_CAN.json"):
            return f"{dot} {port}{tag}"
        return f"{dot} {port}{tag} ({cfg.replace('.json', '')})"

    def close_tab(self, skip_log_prompt=False):
        if not skip_log_prompt and self.has_real_logs:
            reply = QMessageBox.question(
                self, 'Zamykanie Karty', 
                f'Karta "{self.combo_cfg.currentText()}" zawiera logi. Czy chcesz je zapisać przed zamknięciem?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return False
            elif reply == QMessageBox.StandardButton.Yes:
                self.save_logs()
                
        self.save_current_settings_to_config(force=True)
        
        if self.worker and self.worker.is_running:
            self.worker.stop()
            self.worker = None
            
        for t in self.button_timers:
            t.stop()
        self.watch_decay_timer.stop()
            
        for runner in self.macro_runners:
            if runner.isRunning():
                runner.terminate()
                runner.wait()
                
        return True

    def save_current_settings_to_config(self, force=False):
        if not self.current_cfg_file:
            return
            
        new_port = self.get_selected_port_device()
        is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
        has_changes = force

        if is_can:
            bitrate_data = self.baud_combo.currentData()
            try:
                new_bitrate = int(bitrate_data if bitrate_data is not None else self.app_config.get("can_bitrate", DEFAULT_CAN_BITRATE))
            except (TypeError, ValueError):
                new_bitrate = DEFAULT_CAN_BITRATE
            if self.app_config.get("can_bitrate") != new_bitrate:
                has_changes = True
                self.app_config["can_bitrate"] = new_bitrate
        else:
            try:
                new_baud = int(self.baud_combo.currentText())
            except ValueError:
                new_baud = 115200
            if self.app_config.get("baudrate") != new_baud:
                has_changes = True
                self.app_config["baudrate"] = new_baud

        new_mode = "ASCII" if self.radio_ascii.isChecked() else "BINARY"
        eol_keys = ["CRLF", "LF", "CR", "NONE"]
        new_eol = eol_keys[self.combo_eol.currentIndex()] if 0 <= self.combo_eol.currentIndex() < 4 else "CRLF"
        
        if self.app_config.get("port") != new_port: has_changes = True
        if self.app_config.get("mode") != new_mode: has_changes = True
        if self.app_config.get("eol") != new_eol: has_changes = True
        
        if has_changes:
            self.app_config["port"] = new_port
            self.app_config["mode"] = new_mode
            self.app_config["eol"] = new_eol
            save_config(self.current_cfg_file, self.app_config)

    # ==========================================
    # LOGIKA FILTRÓW I PARSERÓW RX
    # ==========================================
    def refresh_filter_combo(self):
        filters = self.app_config.get("filters", [])
        parsers = self.app_config.get("parsers", [])
        
        active_filters = sum(1 for f in filters if f.get("is_active", True))
        active_parsers = sum(1 for p in parsers if p.get("is_active", True))
        total_active = active_filters + active_parsers
        
        if hasattr(self, 'btn_toggle_tools'):
            self.btn_toggle_tools.setText(f"🌪️ Filtry ({total_active})")
            
        if hasattr(self, 'btn_whitelist_warn'):
            has_allow = any(f.get("action") == "allow" and f.get("is_active", True) for f in filters)
            self.btn_whitelist_warn.setVisible(has_allow)

    def open_whitelist_manager(self):
        dlg = FilterManagerDialog(self.app_config, self, whitelist_only=True)
        dlg.exec()
        self.save_current_settings_to_config(force=True)
        self.refresh_filter_combo()

    def add_parser(self):
        pattern = self.le_parser_pattern.text().strip()
        p_text = self.le_parser_text.text().strip()
        if not pattern or not p_text:
            return
            
        if "parsers" not in self.app_config:
            self.app_config["parsers"] = []
            
        self.app_config["parsers"].append({
            "pattern": pattern,
            "text": p_text,
            "is_active": True
        })
        self.le_parser_pattern.clear()
        self.le_parser_text.clear()
        self.save_current_settings_to_config(force=True)
        self.refresh_filter_combo()
        self.log_info(f"Dodano parser: {pattern} -> {p_text}")

    def add_filter(self):
        pattern = self.le_filter_pattern.text().strip()
        if not pattern:
            return
            
        sel = self.combo_filter_action.currentText()
        if sel == "Ukryj": action = "hide"
        elif sel == "Dozwolony (Whitelist)": action = "allow"
        else: action = "color"
        color = self.combo_filter_color.currentData()
        
        if "filters" not in self.app_config:
            self.app_config["filters"] = []
            
        self.app_config["filters"].append({
            "pattern": pattern,
            "action": action,
            "color": color,
            "is_active": True
        })
        self.le_filter_pattern.clear()
        self.save_current_settings_to_config(force=True)
        self.refresh_filter_combo()
        self.log_info(f"Dodano filtr ({sel}): {pattern}")
        
    def edit_filter(self):
        dlg = FilterManagerDialog(self.app_config, self)
        dlg.exec()
        self.save_current_settings_to_config(force=True)
        self.refresh_filter_combo()

    def edit_parser(self):
        dlg = ParserManagerDialog(self.app_config, self)
        dlg.exec()
        self.save_current_settings_to_config(force=True)
        self.refresh_filter_combo()

    def process_message_filters(self, msg):
        color = "#d4d4d8" 
        filters = self.app_config.get("filters", [])
        
        allow_filters = [f for f in filters if f["action"] == "allow" and f.get("is_active", True)]
        if allow_filters:
            is_allowed = any(fnmatch.fnmatch(msg, f["pattern"]) for f in allow_filters)
            if not is_allowed:
                return True, msg, ""
        
        for f in filters:
            if not f.get("is_active", True):
                continue
            if fnmatch.fnmatch(msg, f["pattern"]):
                if f["action"] == "hide":
                    return True, msg, ""
                elif f["action"] == "color":
                    color = f["color"]
                    
        parsed_msg = msg
        for p in self.app_config.get("parsers", []):
            if not p.get("is_active", True):
                continue
            if fnmatch.fnmatch(msg, p["pattern"]):
                parsed_msg = p["text"]
                color = "#ffd700"
                break
                
        return False, parsed_msg, color

    # ==========================================
    # SZYBKIE DODAWANIE ZAZNACZENIA DO FILTRA / PARSERA (PPM)
    # ==========================================
    def format_wildcard_selection(self, raw_text: str) -> str:
        clean = raw_text.replace('\u2029', ' ').replace('\n', ' ').replace('\r', ' ').strip()
        clean = clean.strip('*').strip()
        return f"*{clean}*" if clean else ""

    def quick_send_to_filter(self, raw_text: str):
        pattern = self.format_wildcard_selection(raw_text)
        if not pattern:
            return
        QApplication.clipboard().setText(pattern)
        self.btn_toggle_tools.setChecked(True)
        self.le_filter_pattern.setText(pattern)
        self.le_filter_pattern.setFocus()
        self.le_filter_pattern.selectAll()

    def quick_send_to_parser(self, raw_text: str):
        pattern = self.format_wildcard_selection(raw_text)
        if not pattern:
            return
        QApplication.clipboard().setText(pattern)
        self.btn_toggle_tools.setChecked(True)
        self.le_parser_pattern.setText(pattern)
        self.le_parser_text.setFocus()
        self.le_parser_text.selectAll()

    # ==========================================
    # ZARZĄDZANIE PRZYCISKAMI
    # ==========================================
    def edit_button_config(self, idx):
        btn_data = self.app_config["buttons"][idx]
        is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
        dialog = ButtonEditDialog(btn_data, self, is_can_mode=is_can)
        
        if dialog.exec(): 
            new_data = dialog.get_data()
            self.app_config["buttons"][idx] = new_data
            
            self.save_current_settings_to_config(force=True)
            self.setup_button(idx)
            if dialog.delete_requested:
                self.log_info(f"Wyczyszczono przycisk #{idx+1}")
            else:
                self.log_info(f"Zapisano konfigurację dla: {new_data['name']}")

    def setup_button(self, idx):
        btn = self.gui_buttons[idx]
        btn_cfg = self.app_config["buttons"][idx]

        try: btn.clicked.disconnect()
        except TypeError: pass
        try: btn.pressed.disconnect()
        except TypeError: pass
        try: btn.released.disconnect()
        except TypeError: pass

        if self.button_timers[idx].isActive():
            self.button_timers[idx].stop()
        self.button_states[idx] = False

        if btn_cfg.get("is_used", False):
            b_type = btn_cfg.get("type", "toggle")
            name = btn_cfg.get("name", f"Btn {idx+1}")
            is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
            p_type = btn_cfg.get("payload_type", "CAN" if is_can else "ASCII")
            
            if b_type == "toggle":
                state = self.button_states[idx]
                btn.setText(f"🔘 {name}: {'ON' if state else 'OFF'}")
                color = "#37b24d" if state else "#f03e3e"
                btn.setStyleSheet(self.get_btn_style(color))
                btn.setToolTip(f"Typ: TOGGLE ({p_type})\nTX ON: {btn_cfg.get('tx_on')}\nTX OFF: {btn_cfg.get('tx_off')}\nACK ON: {btn_cfg.get('ack_on')}\nACK OFF: {btn_cfg.get('ack_off')}\n\n(PPM: Edytuj)")
                btn.clicked.connect(lambda checked, i=idx: self.on_toggle_clicked(i))
                
            elif b_type == "push":
                btn.setText(f"⚡ {name}")
                btn.setStyleSheet(self.get_btn_style("#228be6"))
                btn.setToolTip(f"Typ: PUSH ({p_type})\nTX: {btn_cfg.get('tx')}\n\n(PPM: Edytuj)")
                btn.clicked.connect(lambda checked, i=idx: self.on_push_clicked(i))
                
            elif b_type == "hold":
                btn.setText(f"⏳ {name}")
                btn.setStyleSheet(self.get_btn_style("#f59f00"))
                btn.setToolTip(f"Typ: HOLD ({p_type})\nWciśnięty: {btn_cfg.get('tx_on')}\nPuszczony: {btn_cfg.get('tx_off')}\n\n(PPM: Edytuj)")
                btn.pressed.connect(lambda i=idx: self.on_hold_pressed(i))
                btn.released.connect(lambda i=idx: self.on_hold_released(i))
                
            elif b_type == "macro":
                btn.setText(f"📜 {name}")
                btn.setStyleSheet(self.get_btn_style("#9c27b0"))
                btn.setToolTip(f"Typ: MACRO ({p_type})\nSekwencja: {btn_cfg.get('tx')}\n\n(PPM: Edytuj)")
                btn.clicked.connect(lambda checked, i=idx: self.on_macro_clicked(i))
                
            elif b_type == "trigger":
                btn.setText(f"🔁 {name}")
                btn.setStyleSheet(self.get_btn_style("#607d8b"))
                btn.setToolTip(f"Typ: TRIGGER ({p_type})\nTX: {btn_cfg.get('tx')}\nInterwał: {btn_cfg.get('interval', 1000)} ms\n\n(PPM: Edytuj)")
                btn.clicked.connect(lambda checked, i=idx: self.on_trigger_clicked(i))
        else:
            btn.setText("+ Przypisz akcję (PPM)")
            btn.setToolTip("Kliknij prawym przyciskiem myszy (PPM), aby skonfigurować ten przycisk.")
            btn.setStyleSheet(self.get_btn_style("unused"))

    # ==========================================
    # LOGOWANIE I PORT COM
    # ==========================================
    def get_timestamp(self):
        now = datetime.now()
        return now.strftime("[%H:%M:%S.") + f"{now.microsecond // 1000:03d}]"

    def log_tx(self, msg, marker=""):
        self.has_real_logs = True
        marker_html = f'<span style="color: #ffaa00; font-weight: bold;">[{marker}] </span>' if marker else ""
        self.append_html_no_autoscroll(f'<span style="color: #4dabf7;">TX {self.get_timestamp()}: </span>{marker_html}<span style="color: #74c0fc;">{msg}</span>')

    def log_rx(self, msg):
        ts = self.get_timestamp()
        matched_watch, clean_msg = self.handle_incoming_watch_check(msg, ts)
        if matched_watch and not self.cb_watch_print.isChecked():
            self.has_real_logs = True
            return

        should_hide, parsed_msg, text_color = self.process_message_filters(clean_msg)
        if should_hide:
            return
            
        self.has_real_logs = True
        self.append_html_no_autoscroll(f'<span style="color: #69db7c;">RX {ts}: </span><span style="color: {text_color};">{html_lib.escape(parsed_msg)}</span>')

    def log_info(self, msg):
        self.append_html_no_autoscroll(f'<span style="color: #71717a; font-style: italic;">ℹ {self.get_timestamp()} {msg}</span>')

    def append_html_no_autoscroll(self, html):
        scrollbar = self.console.verticalScrollBar()
        was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 5
        old_val = scrollbar.value()
        
        self.console.append(html)
        
        if was_at_bottom:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(old_val)

    def on_scroll_changed(self):
        scrollbar = self.console.verticalScrollBar()
        if scrollbar.value() < scrollbar.maximum() - 5:
            self.btn_scroll_down.show()
        else:
            self.btn_scroll_down.hide()

    def force_scroll_to_bottom(self):
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def show_search_dialog(self):
        if not self.search_dialog:
            self.search_dialog = SearchDialog(self.console, self)
        
        console_rect = self.console.geometry()
        global_pos = self.console.mapToGlobal(console_rect.topRight())
        self.search_dialog.move(global_pos.x() - self.search_dialog.width() - 20, global_pos.y() + 10)
        
        self.search_dialog.show()
        self.search_dialog.raise_()
        self.search_dialog.activateWindow()
        self.search_dialog.le_search.setFocus()
        selected = self.console.textCursor().selectedText()
        if selected:
            self.search_dialog.le_search.setText(selected)

    def show_console_context_menu(self, pos):
        menu = self.console.createStandardContextMenu()
        selected = self.console.textCursor().selectedText().strip()
        
        # Pobierz też całą linię pod kursorem (do szybkiego przypięcia do Live Watch bez konieczności zaznaczania)
        cursor_at_pos = self.console.cursorForPosition(pos)
        line_text = cursor_at_pos.block().text().strip()
        clean_line = self.strip_rx_prefix(line_text)

        menu.addSeparator()

        # Opcja Przypnij do Live Watch (z zaznaczenia lub automatycznie z klucza linii pod kursorem)
        is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
        if is_can:
            can_cand = extract_can_id_from_line(clean_line)
            if selected and len(selected) <= 8 and normalize_can_id_text(selected):
                pin_key = normalize_can_id_text(selected)
            elif can_cand:
                pin_key = can_cand
            else:
                pin_key = ""
        else:
            pin_key = self.strip_rx_prefix(selected) if selected and len(selected) <= 32 else self.extract_watch_key(clean_line)

        if pin_key:
            act_pin = QAction(f"📌 Przypnij do Live Watch ({pin_key})", self)
            act_pin.triggered.connect(lambda checked=False, k=pin_key, ln=clean_line: self.pin_to_live_watch(k, ln))
            menu.addAction(act_pin)

        if selected:
            preview = selected.replace('\u2029', ' ').strip('*').strip()
            if len(preview) > 22:
                preview = preview[:22] + "..."
                
            act_to_filter = QAction(f"🌪️ Dodaj do Filtra (*{preview}*)", self)
            act_to_filter.triggered.connect(lambda checked=False, txt=selected: self.quick_send_to_filter(txt))
            menu.addAction(act_to_filter)
            
            act_to_parser = QAction(f"🧩 Dodaj do Parsera (*{preview}*)", self)
            act_to_parser.triggered.connect(lambda checked=False, txt=selected: self.quick_send_to_parser(txt))
            menu.addAction(act_to_parser)
            
        menu.addSeparator()
        action_search = QAction("🔍 Szukaj w logach (Ctrl+F)", self)
        action_search.triggered.connect(self.show_search_dialog)
        menu.addAction(action_search)
        
        action_clear = QAction("🗑️ Wyczyść konsolę", self)
        action_clear.triggered.connect(self.console_clear)
        menu.addAction(action_clear)
        
        menu.exec(self.console.mapToGlobal(pos))

    def refresh_ports(self):
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        current_devices = {p.device for p in ports}

        if self._known_ports is None:
            # Pierwszy skan przy starcie - stan bazowy (nic nie podświetlamy)
            new_ports = set()
            self._known_ports = current_devices
        else:
            # Kolejne kliknięcie odświeżenia
            new_ports = current_devices - self._known_ports
            self._known_ports = current_devices

        for p in ports:
            self.port_combo.addItem(p.device)
            idx = self.port_combo.count() - 1
            full_label = f"{p.device}  —  {p.description}"
            self.port_combo.setItemData(idx, p.device, Qt.ItemDataRole.UserRole)
            self.port_combo.setItemData(idx, full_label, Qt.ItemDataRole.UserRole + 1)
            self.port_combo.setItemData(idx, f"{full_label} [{p.hwid}]", Qt.ItemDataRole.ToolTipRole)
            
        self.port_combo.set_new_ports(new_ports)

        saved_port = self.app_config.get("port") if self.app_config else None
        if saved_port:
            for i in range(self.port_combo.count()):
                if self.port_combo.itemData(i, Qt.ItemDataRole.UserRole) == saved_port:
                    self.port_combo.setCurrentIndex(i)
                    break
        self.port_combo.blockSignals(False)
            
        if not ports:
            self.log_info("Nie znaleziono żadnych portów COM.")
        elif new_ports:
            self.log_info(f"Znaleziono {len(ports)} port(ów) COM (wykryto nowy: {', '.join(sorted(new_ports))}).")
        else:
            self.log_info(f"Znaleziono {len(ports)} port(ów) COM.")
        self.update_header_title()
        self.tab_state_changed.emit()

    def save_logs(self):
        filters = "Strona HTML (*.html);;Markdown z kolorami (*.md);;Zwykły tekst (*.txt);;Wszystkie pliki (*)"
        filename, selected_filter = QFileDialog.getSaveFileName(self, "Zapisz logi", "", filters)
        
        if filename:
            try:
                date_info = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                port_info = f"{self.get_selected_port_device()} ({self.baud_combo.currentText()} bps)"
                cfg_info = self.combo_cfg.currentText()
                
                header_txt = f"==================================================\n" \
                             f"TITLE: Logi Diagnostyczne HMI\n" \
                             f"DATE: {date_info}\n" \
                             f"APP VERSION: {APP_VERSION}\n" \
                             f"PROFILE: {cfg_info}\n" \
                             f"PORT: {port_info}\n" \
                             f"==================================================\n\n"
                             
                header_html = f'<div style="border: 1px solid #555; background-color: #2b2b2b; padding: 10px; margin-bottom: 20px; font-family: monospace; color: #e0e0e0;">' \
                              f'<b>TITLE:</b> Logi Diagnostyczne HMI<br>' \
                              f'<b>DATE:</b> {date_info}<br>' \
                              f'<b>APP VERSION:</b> {APP_VERSION}<br>' \
                              f'<b>PROFILE:</b> {cfg_info}<br>' \
                              f'<b>PORT:</b> {port_info}' \
                              f'</div>\n'

                if filename.endswith(".html") or "HTML" in selected_filter:
                    content = self.console.toHtml()
                    content = re.sub(r'(<body[^>]*>)', r'\1' + header_html, content, count=1)
                    content = content.replace("<body", "<body style=\"background-color: #121214; color: #d4d4d8; font-family: monospace; padding: 15px;\"")
                elif filename.endswith(".md") or "Markdown" in selected_filter:
                    html_full = self.console.toHtml()
                    body_match = re.search(r'<body[^>]*>(.*?)</body>', html_full, re.DOTALL | re.IGNORECASE)
                    body_content = body_match.group(1) if body_match else html_full
                    content = f"# Logi Diagnostyczne\n\n<div style=\"background-color: #121214; color: #d4d4d8; font-family: monospace; padding: 15px; border-radius: 5px;\">\n{header_html}{body_content}\n</div>"
                else:
                    content = header_txt + self.console.toPlainText()
                    
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.log_info(f"Zapisano logi do {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Błąd", f"Nie udało się zapisać pliku:\n{e}")

    def insert_marker(self):
        text, ok = QInputDialog.getText(self, "Marker", "Wpisz tekst markera:")
        if ok and text:
            self.append_html_no_autoscroll(f'<br><span style="color: #ff922b; font-weight: bold; font-size: 13px;">--- 📌 MARKER: {text} ({self.get_timestamp()}) ---</span><br>')

    def toggle_connection(self):
        if self.worker and self.worker.is_running:
            self.worker.stop()
            self.worker = None
            self.handle_connection_status(False)
            self.rx_buffer.clear()
            self.text_buffer = ""
            self.last_can_timestamps.clear()
            self._unpinned_can_ids.clear()
            self.log_info("Rozłączono.")
        else:
            selected_port = self.get_selected_port_device()
            if not selected_port:
                QMessageBox.warning(self, "Błąd", "Nie wybrano portu COM!")
                return

            is_can = self.app_config.get("transport") == TRANSPORT_SLCAN

            if is_can:
                if not CAN_AVAILABLE:
                    QMessageBox.critical(
                        self, "Brak biblioteki python-can",
                        f"Tryb CANable wymaga biblioteki python-can.\n{CAN_IMPORT_ERROR}\n\nZainstaluj ją poleceniem:\npip install python-can"
                    )
                    return

                try:
                    bitrate_data = self.baud_combo.currentData()
                    selected_bitrate = int(bitrate_data if bitrate_data is not None else self.app_config.get("can_bitrate", DEFAULT_CAN_BITRATE))
                except (TypeError, ValueError):
                    selected_bitrate = DEFAULT_CAN_BITRATE

                listen_only = bool(self.app_config.get("can_listen_only", False))

                if os.path.basename(self.current_cfg_file) == "default.json":
                    new_name = f"{selected_port}_CAN.json"
                    new_path = os.path.join(CFG_DIR, new_name)
                    self.current_cfg_file = new_path
                    self.save_current_settings_to_config(force=True)
                    self.refresh_configs_list(select_file=new_name)

                lo_tag = " [Listen-only]" if listen_only else ""
                self.log_info(f"Łączenie z adapterem CANable (slcan) na {selected_port} ({format_bitrate_label(selected_bitrate)}{lo_tag})...")
                self.save_current_settings_to_config(force=False)

                self.last_can_timestamps.clear()
                self._unpinned_can_ids.clear()
                self.worker = CanWorker(selected_port, selected_bitrate, listen_only=listen_only)
                self.worker.frames_received.connect(self.process_received_can_frames)
                self.worker.error_occurred.connect(self.log_info)
                self.worker.connection_status.connect(self.handle_connection_status)
                self.worker.finished.connect(self.worker.deleteLater)
                self.worker.start()
            else:
                try:
                    selected_baud = int(self.baud_combo.currentText())
                except ValueError:
                    QMessageBox.warning(self, "Błąd", "Nieprawidłowa wartość Baudrate!")
                    return

                if os.path.basename(self.current_cfg_file) == "default.json":
                    new_name = f"{selected_port}.json"
                    new_path = os.path.join(CFG_DIR, new_name)
                    self.current_cfg_file = new_path
                    self.save_current_settings_to_config(force=True)
                    self.refresh_configs_list(select_file=new_name)

                self.log_info(f"Łączenie z {selected_port} ({selected_baud} bps)...")
                self.save_current_settings_to_config(force=False)

                self.worker = SerialWorker(selected_port, selected_baud)
                self.worker.data_received.connect(self.process_received_data)
                self.worker.error_occurred.connect(self.log_info)
                self.worker.connection_status.connect(self.handle_connection_status)
                self.worker.finished.connect(self.worker.deleteLater)
                self.worker.start()

    def handle_connection_status(self, connected: bool):
        is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
        if connected:
            self.btn_connect.setText("Rozłącz")
            self.btn_connect.setStyleSheet("background-color: #fa5252; color: white; font-weight: bold; border: none; padding: 4px 6px;")
            self.port_combo.setEnabled(False)
            self.baud_combo.setEnabled(False)
            self.btn_refresh.setEnabled(False)
            self.combo_cfg.setEnabled(False)
            if not is_can:
                self.action_dtr.setChecked(True)
                self.action_rts.setChecked(True)
            self.log_info("Połączono pomyślnie.")
        else:
            self.btn_connect.setText("Połącz")
            self.btn_connect.setStyleSheet("background-color: #228be6; color: white; font-weight: bold; border: none; padding: 4px 6px;")
            self.port_combo.setEnabled(True)
            self.baud_combo.setEnabled(True)
            self.btn_refresh.setEnabled(True)
            self.combo_cfg.setEnabled(True)
            if not is_can:
                self.action_dtr.setChecked(False)
                self.action_rts.setChecked(False)
        self.update_header_title()
        self.tab_state_changed.emit()

    def send_payload(self, payload_str, source_name="Manual", show_marker=False, payload_type="ASCII"):
        if not self.worker or not self.worker.is_running:
            self.log_info(f"Brak aktywnego połączenia. Odrzucono: {source_name}")
            return

        marker_text = source_name if show_marker else ""
        is_can = self.app_config.get("transport") == TRANSPORT_SLCAN

        if is_can or str(payload_type).upper() == "CAN":
            try:
                frame = parse_can_frame(payload_str)
            except CanFrameError as e:
                self.log_info(f"Błąd składni ramki CAN ({source_name}): {e}")
                return
            except Exception as e:
                self.log_info(f"Błąd parsowania CAN ({source_name}): {e}")
                return

            if not hasattr(self.worker, 'send_frame'):
                self.log_info("Bieżący worker nie obsługuje wysyłania ramek CAN!")
                return

            self.worker.send_frame(frame)
            self.log_tx(frame.to_display(), marker=marker_text)
            return

        if str(payload_type).upper() == "ASCII":
            eol_str = self.combo_eol.currentData()
            if eol_str is None:
                eol_str = "\r\n"
            data_to_send = (payload_str + eol_str).encode('utf-8')
            self.worker.send_data(data_to_send)
            self.log_tx(payload_str, marker=marker_text)
        else:
            try:
                data_to_send = bytes.fromhex(payload_str.replace(" ", ""))
                self.worker.send_data(data_to_send)
                self.log_tx(data_to_send.hex(' ').upper(), marker=marker_text)
            except ValueError:
                self.log_info(f"Błąd formatu HEX ({source_name})")

    def send_manual_command(self):
        text = self.cmd_input.text().strip()
        if text:
            self.cmd_input.add_to_history(text)
            is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
            p_type = "CAN" if is_can else self.combo_cmd_format.currentText()
            self.send_payload(text, source_name="Terminal", payload_type=p_type)
            self.cmd_input.clear()

    def on_toggle_clicked(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        is_currently_on = self.button_states[idx]
        payload = btn_cfg.get("tx_off", "") if is_currently_on else btn_cfg.get("tx_on", "")
        is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
        default_ptype = "CAN" if is_can else "ASCII"
        p_type = btn_cfg.get("payload_type") or default_ptype
        self.send_payload(payload, source_name=btn_cfg['name'], show_marker=btn_cfg.get("show_marker", False), payload_type=p_type)

    def on_push_clicked(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
        default_ptype = "CAN" if is_can else "ASCII"
        p_type = btn_cfg.get("payload_type") or default_ptype
        self.send_payload(btn_cfg.get("tx", ""), source_name=btn_cfg['name'], show_marker=btn_cfg.get("show_marker", False), payload_type=p_type)

    def on_hold_pressed(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
        default_ptype = "CAN" if is_can else "ASCII"
        p_type = btn_cfg.get("payload_type") or default_ptype
        self.send_payload(btn_cfg.get("tx_on", ""), source_name=btn_cfg['name'], show_marker=btn_cfg.get("show_marker", False), payload_type=p_type)

    def on_hold_released(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
        default_ptype = "CAN" if is_can else "ASCII"
        p_type = btn_cfg.get("payload_type") or default_ptype
        self.send_payload(btn_cfg.get("tx_off", ""), source_name=btn_cfg['name'], show_marker=btn_cfg.get("show_marker", False), payload_type=p_type)

    def on_macro_clicked(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        sequence = btn_cfg.get("tx", "")
        seq_display = sequence.replace('\r', '').replace('\n', '; ')
        self.log_info(f"Start Macro: {btn_cfg['name']} -> {seq_display}")
        
        self.macro_runners = [r for r in self.macro_runners if r.isRunning()]
        
        is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
        default_ptype = "CAN" if is_can else "ASCII"
        p_type = btn_cfg.get("payload_type") or default_ptype
        runner = MacroRunner(sequence, btn_cfg['name'], btn_cfg.get("show_marker", False), p_type)
        runner.tx_signal.connect(self.send_payload)
        self.macro_runners.append(runner)
        runner.start()

    def on_trigger_clicked(self, idx):
        if not self.worker or not self.worker.is_running:
            self.log_info("Brak połączenia z portem.")
            return
            
        timer = self.button_timers[idx]
        btn = self.gui_buttons[idx]
        cfg = self.app_config["buttons"][idx]
        
        if timer.isActive():
            timer.stop()
            self.button_states[idx] = False
            btn.setStyleSheet(self.get_btn_style("#607d8b"))
            btn.setText(f"🔁 {cfg.get('name', '')}")
        else:
            interval = cfg.get("interval", 1000)
            self.button_states[idx] = True
            btn.setStyleSheet(self.get_btn_style("#e67700"))
            btn.setText(f"⏹ {cfg.get('name', '')} ({interval}ms)")
            self.on_trigger_timeout(idx)
            timer.start(interval)
            
    def on_trigger_timeout(self, idx):
        if not self.worker or not self.worker.is_running:
            self.button_timers[idx].stop()
            self.button_states[idx] = False
            self.setup_button(idx)
            return
            
        cfg = self.app_config["buttons"][idx]
        tx = cfg.get("tx", "")
        if tx:
            is_can = self.app_config.get("transport") == TRANSPORT_SLCAN
            default_ptype = "CAN" if is_can else "ASCII"
            p_type = cfg.get("payload_type") or default_ptype
            self.send_payload(tx, source_name=cfg.get('name', ''), show_marker=cfg.get("show_marker", False), payload_type=p_type)

    def get_btn_style(self, bg_hex):
        if bg_hex == "unused":
            return """
            QPushButton { 
                background-color: #1f1f23; 
                color: #63636e; 
                font-size: 12px; 
                border-radius: 5px; 
                border: 1px dashed #3f3f46; 
            }
            QPushButton:hover { 
                background-color: #27272a; 
                color: #a1a1aa; 
                border-color: #52525b; 
            }
            """
            
        hovers = {
            "#37b24d": "#2f9e44", "#f03e3e": "#e03131",
            "#228be6": "#1c7ed6", "#f59f00": "#f08c00",
            "#9c27b0": "#8e24aa", "#607d8b": "#546e7a",
            "#e67700": "#d9480f"
        }
        presseds = {
            "#37b24d": "#2b8a3e", "#f03e3e": "#c92a2a",
            "#228be6": "#1864ab", "#f59f00": "#e67700",
            "#9c27b0": "#7b1fa2", "#607d8b": "#455a64",
            "#e67700": "#c92a2a"
        }
        hover = hovers.get(bg_hex, bg_hex)
        pressed = presseds.get(bg_hex, bg_hex)
        
        return f"""
        QPushButton {{ background-color: {bg_hex}; color: white; font-weight: bold; font-size: 13px; border-radius: 5px; border: 1px solid rgba(0,0,0,0.3); }}
        QPushButton:hover {{ background-color: {hover}; }}
        QPushButton:pressed {{ background-color: {pressed}; padding-top: 2px; padding-left: 2px; }}
        """

    def process_received_data(self, data: bytes):
        self.rx_buffer.extend(data)
        
        if self.radio_ascii.isChecked():
            try:
                self.text_buffer += data.decode('utf-8', errors='replace')
                while '\n' in self.text_buffer:
                    line, self.text_buffer = self.text_buffer.split('\n', 1)
                    clean_line = line.strip()
                    if clean_line:
                        self.log_rx(clean_line)
                        
                stripped_buffer = self.text_buffer.strip()
                if stripped_buffer in [">", ">>"]:
                    self.log_rx(stripped_buffer)
                    self.text_buffer = ""
            except Exception as e:
                self.log_info(f"Błąd dekodowania: {e}")
        else:
            self.log_rx(data.hex(' ').upper())
        
        for i, btn_cfg in enumerate(self.app_config["buttons"]):
            if not btn_cfg.get("is_used", False) or btn_cfg.get("type") != "toggle":
                continue
                
            if btn_cfg.get("payload_type", "ASCII") == "ASCII":
                ack_on_bytes = btn_cfg.get("ack_on", "").encode('utf-8')
                ack_off_bytes = btn_cfg.get("ack_off", "").encode('utf-8')
            else:
                try:
                    ack_on_bytes = bytes.fromhex(btn_cfg.get("ack_on", "").replace(" ", ""))
                    ack_off_bytes = bytes.fromhex(btn_cfg.get("ack_off", "").replace(" ", ""))
                except ValueError:
                    continue 

            if ack_on_bytes and ack_on_bytes in self.rx_buffer:
                self.log_info(f"-> ACK: {btn_cfg['name']} stan ON")
                self.button_states[i] = True
                self.update_button_visuals(i, True)
                self.rx_buffer = bytearray(self.rx_buffer.replace(ack_on_bytes, b''))

            if ack_off_bytes and ack_off_bytes in self.rx_buffer:
                self.log_info(f"-> ACK: {btn_cfg['name']} stan OFF")
                self.button_states[i] = False
                self.update_button_visuals(i, False)
                self.rx_buffer = bytearray(self.rx_buffer.replace(ack_off_bytes, b''))
            
        if len(self.rx_buffer) > 1024:
            self.rx_buffer.clear()

    def process_received_can_frames(self, frames: list):
        if not frames:
            return

        now_wall = datetime.now()
        ts_str = now_wall.strftime("[%H:%M:%S.") + f"{now_wall.microsecond // 1000:03d}]"

        auto_watch = bool(self.app_config.get("can_watch_auto", True))
        watch_print = bool(self.cb_watch_print.isChecked())
        watch_patterns = self.app_config.setdefault("watch_patterns", [])

        any_watch_updated = False
        html_entries = []

        for frame in frames:
            # 1. Obliczenie okresu Δt (cyklu) dla danego ID
            id_key = frame.id_str()
            now_ts = frame.timestamp or time.time()
            last_ts = self.last_can_timestamps.get(id_key)
            period_ms = (now_ts - last_ts) * 1000.0 if last_ts is not None else None
            self.last_can_timestamps[id_key] = now_ts

            # 2. Weryfikacja ACK dla przycisków typu TOGGLE
            match_key = frame.to_match_key()
            for i, btn_cfg in enumerate(self.app_config["buttons"]):
                if not btn_cfg.get("is_used", False) or btn_cfg.get("type") != "toggle":
                    continue
                ack_on = btn_cfg.get("ack_on", "").strip()
                ack_off = btn_cfg.get("ack_off", "").strip()
                if ack_on:
                    pat_on = normalize_can_ack_pattern(ack_on)
                    if fnmatch.fnmatch(match_key, pat_on):
                        self.log_info(f"-> ACK CAN: {btn_cfg['name']} stan ON ({frame.to_display()})")
                        self.button_states[i] = True
                        self.update_button_visuals(i, True)
                if ack_off:
                    pat_off = normalize_can_ack_pattern(ack_off)
                    if fnmatch.fnmatch(match_key, pat_off):
                        self.log_info(f"-> ACK CAN: {btn_cfg['name']} stan OFF ({frame.to_display()})")
                        self.button_states[i] = False
                        self.update_button_visuals(i, False)

            # 3. Obsługa panelu Live Watch
            is_watched = False
            if id_key in watch_patterns:
                is_watched = True
            elif auto_watch and id_key not in self._unpinned_can_ids:
                watch_patterns.append(id_key)
                is_watched = True

            if is_watched:
                if id_key not in self.watch_rows:
                    row = LiveWatchRowWidget(id_key, self, show_period=True, sort_key=frame.sort_key())
                    row.unpin_requested.connect(self.unpin_live_watch)
                    self.watch_rows[id_key] = row
                    self.insert_watch_row_sorted(row)
                    self.update_watch_panel_geometry()

                self.watch_rows[id_key].update_message(frame.to_display(), ts_str, period_ms=period_ms)
                any_watch_updated = True

            # 4. Przekazanie do konsoli głównej (chyba że ukryto przez Live Watch bez watch_print)
            if is_watched and not watch_print:
                self.has_real_logs = True
                continue

            display_str = frame.to_display()
            should_hide, parsed_msg, text_color = self.process_message_filters(display_str)
            if should_hide:
                continue

            self.has_real_logs = True
            html_entries.append(
                f'<span style="color: #69db7c;">RX {ts_str}: </span><span style="color: {text_color};">{html_lib.escape(parsed_msg)}</span>'
            )

        if any_watch_updated and not self.watch_decay_timer.isActive():
            self.watch_decay_timer.start()

        if html_entries:
            self.append_html_no_autoscroll("<br>".join(html_entries))

    def update_button_visuals(self, idx: int, state: bool):
        btn = self.gui_buttons[idx]
        name = self.app_config["buttons"][idx]["name"]
        
        if state:
            btn.setText(f"🔘 {name}: ON")
            btn.setStyleSheet(self.get_btn_style("#37b24d"))
        else:
            btn.setText(f"🔘 {name}: OFF")
            btn.setStyleSheet(self.get_btn_style("#f03e3e"))

    def closeEvent(self, event):
        self.save_current_settings_to_config(force=False)
        if self.worker and self.worker.is_running:
            self.worker.stop()
        event.accept()


# ==========================================
# 6. GŁÓWNE OKNO APLIKACJI (ZARZĄDZANIE KARTAMI I SYMETRYCZNY SPLIT VIEW)
# ==========================================
class MainWindow(QMainWindow):
    SINGLE_WIDTH = 940
    SPLIT_WIDTH = 1440
    DEFAULT_HEIGHT = 720

    def __init__(self, cli_config=None):
        super().__init__()
        self.setWindowTitle(f"Serial Commander v{APP_VERSION}")
        self.resize(self.SINGLE_WIDTH, self.DEFAULT_HEIGHT)
        
        self.app_settings = load_app_settings()
        self.tab_list = []          # Centralna lista otwartych instancji SerialTab
        self.is_split_mode = False  # Czy aktualnie aktywny jest widok podzielony
        self.split_left_tab = None  # Karta przypisana do lewej strony
        self.split_right_tab = None # Karta przypisana do prawej strony
        self._last_mode_was_split = False
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_vbox = QVBoxLayout(main_widget)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(0)

        # --- GÓRNY PASEK STEROWANIA W TRYBIE SPLIT VIEW ---
        self.split_top_bar = QFrame()
        self.split_top_bar.setStyleSheet("background-color: #202024; border-bottom: 1px solid #27272a;")
        self.split_top_bar.setFixedHeight(38)
        split_bar_layout = QHBoxLayout(self.split_top_bar)
        split_bar_layout.setContentsMargins(12, 4, 10, 4)
        split_bar_layout.setSpacing(8)
        
        lbl_split_info = QLabel("◫ Widok Podzielony (50% / 50%)")
        lbl_split_info.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 12px;")
        split_bar_layout.addWidget(lbl_split_info)

        self.btn_swap_split = QPushButton("⇄ Zamień miejscami")
        self.btn_swap_split.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_swap_split.setStyleSheet("padding: 3px 10px; font-size: 12px;")
        self.btn_swap_split.setToolTip("Zamień miejscami lewą i prawą kartę")
        self.btn_swap_split.clicked.connect(self.swap_split_tabs)
        split_bar_layout.addWidget(self.btn_swap_split)

        self.lbl_hidden_tabs = QLabel("")
        self.lbl_hidden_tabs.setStyleSheet("color: #a1a1aa; font-style: italic; font-size: 11px; margin-left: 6px;")
        split_bar_layout.addWidget(self.lbl_hidden_tabs)
        
        split_bar_layout.addStretch()
        
        self.btn_switch_to_tabs = QPushButton("🗂️ Widok zakładek (1 okno)")
        self.btn_switch_to_tabs.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_switch_to_tabs.setStyleSheet("padding: 4px 10px; font-size: 12px;")
        self.btn_switch_to_tabs.clicked.connect(lambda: self.set_split_mode(False))
        split_bar_layout.addWidget(self.btn_switch_to_tabs)

        self.btn_add_tab_split = QPushButton(" + Nowa Karta ")
        self.btn_add_tab_split.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_tab_split.setStyleSheet("padding: 4px 10px; font-weight: bold; background-color: #228be6; color: white; border: none;")
        self.btn_add_tab_split.clicked.connect(lambda: self.add_new_tab())
        split_bar_layout.addWidget(self.btn_add_tab_split)
        
        self.split_top_bar.hide()
        main_vbox.addWidget(self.split_top_bar)

        # QStackedWidget przełączający pomiędzy klasycznym QTabWidget (page 0) a symetrycznym kontenerem 50/50 (page 1)
        self.view_stack = QStackedWidget()
        main_vbox.addWidget(self.view_stack, stretch=1)
        
        # Strona 0: QTabWidget
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab_by_index)
        
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self.show_tabbar_context_menu)
        
        corner_widget = QWidget()
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(0, 0, 4, 0)
        corner_layout.setSpacing(4)
        
        self.btn_switch_to_split = QPushButton("◫ Widok obok siebie (Lewo / Prawo)")
        self.btn_switch_to_split.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_switch_to_split.setToolTip("Wyświetl dwie wybrane karty obok siebie")
        self.btn_switch_to_split.setStyleSheet("margin: 3px 0px; padding: 4px 10px; color: #74c0fc; border-color: #228be6; font-weight: bold;")
        self.btn_switch_to_split.clicked.connect(lambda: self.set_split_mode(True, auto_collapse=True))
        self.btn_switch_to_split.hide()
        corner_layout.addWidget(self.btn_switch_to_split)

        self.btn_add_tab = QPushButton(" + Nowa Karta ")
        self.btn_add_tab.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_tab.setStyleSheet("margin: 3px 2px; padding: 4px 10px; font-weight: bold;")
        self.btn_add_tab.clicked.connect(lambda: self.add_new_tab())
        corner_layout.addWidget(self.btn_add_tab)
        
        self.tabs.setCornerWidget(corner_widget, Qt.Corner.TopRightCorner)
        self.view_stack.addWidget(self.tabs)

        # Strona 1: Symetryczny kontener 50% / 50%
        self.split_container = QWidget()
        self.split_layout = QHBoxLayout(self.split_container)
        self.split_layout.setContentsMargins(4, 4, 4, 4)
        self.split_layout.setSpacing(6)
        self.view_stack.addWidget(self.split_container)
        
        saved_tabs = self.app_settings.get("open_tabs", [])
        if cli_config:
            self.add_new_tab(cli_config, rebuild=False)
        elif saved_tabs:
            for cfg in saved_tabs:
                self.add_new_tab(cfg, rebuild=False)
        else:
            self.add_new_tab(rebuild=False)
            
        if len(self.tab_list) == 2:
            self.is_split_mode = True
            self.split_left_tab = self.tab_list[0]
            self.split_right_tab = self.tab_list[1]
            
        self.rebuild_view_layout(auto_collapse_on_split=(len(self.tab_list) == 2))

    # ==========================================
    # LOGIKA WYBORU KART I ROZMIARU OKNA
    # ==========================================
    def adjust_window_size_for_mode(self, split_active: bool):
        if split_active == self._last_mode_was_split:
            return
        self._last_mode_was_split = split_active
        
        current_h = max(self.height(), 600)
        if split_active:
            if not self.isMaximized():
                self.resize(self.SPLIT_WIDTH, current_h)
        else:
            if self.isMaximized():
                self.showNormal()
            self.resize(self.SINGLE_WIDTH, current_h)

    def ensure_valid_split_pair(self):
        if len(self.tab_list) < 2:
            self.split_left_tab = None
            self.split_right_tab = None
            self.is_split_mode = False
            return

        if self.split_left_tab not in self.tab_list:
            self.split_left_tab = self.tab_list[0]

        if self.split_right_tab not in self.tab_list or self.split_right_tab == self.split_left_tab:
            for t in self.tab_list:
                if t != self.split_left_tab:
                    self.split_right_tab = t
                    break

    def update_split_info_label(self):
        hidden_count = max(0, len(self.tab_list) - 2)
        if hidden_count > 0:
            self.lbl_hidden_tabs.setText(f"•  W tle: {hidden_count} (kliknij nazwę profilu na pasku karty poniżej, aby przełączyć)")
        else:
            self.lbl_hidden_tabs.setText("•  Kliknij nazwę profilu w nagłówku karty, aby przełączyć okno")

    def switch_split_card(self, side: str, target_tab):
        if target_tab not in self.tab_list:
            return
        if side == "left":
            if target_tab == self.split_right_tab:
                self.split_right_tab = self.split_left_tab
            self.split_left_tab = target_tab
        else:
            if target_tab == self.split_left_tab:
                self.split_left_tab = self.split_right_tab
            self.split_right_tab = target_tab
        self.rebuild_view_layout(auto_collapse_on_split=True)

    def swap_split_tabs(self):
        if self.split_left_tab and self.split_right_tab:
            self.split_left_tab, self.split_right_tab = self.split_right_tab, self.split_left_tab
            self.rebuild_view_layout(auto_collapse_on_split=False)

    def set_split_mode(self, enabled: bool, auto_collapse: bool = False):
        if enabled and len(self.tab_list) >= 2:
            current_tab = self.tabs.currentWidget()
            if current_tab in self.tab_list and self.split_left_tab not in self.tab_list:
                self.split_left_tab = current_tab
            self.is_split_mode = True
            self.ensure_valid_split_pair()
        else:
            self.is_split_mode = False
        self.rebuild_view_layout(auto_collapse_on_split=auto_collapse)

    def show_tabbar_context_menu(self, pos):
        tab_idx = self.tabs.tabBar().tabAt(pos)
        if tab_idx < 0 or tab_idx >= len(self.tab_list):
            return
            
        clicked_tab = self.tab_list[tab_idx]
        menu = QMenu(self)
        
        if len(self.tab_list) >= 2:
            act_left = QAction("◫ Ustaw jako LEWĄ kartę w widoku podzielonym", self)
            act_left.triggered.connect(lambda: self.assign_tab_to_split(clicked_tab, "left"))
            menu.addAction(act_left)
            
            act_right = QAction("◫ Ustaw jako PRAWĄ kartę w widoku podzielonym", self)
            act_right.triggered.connect(lambda: self.assign_tab_to_split(clicked_tab, "right"))
            menu.addAction(act_right)
            menu.addSeparator()
            
        act_close = QAction("✕ Zamknij tę kartę", self)
        act_close.triggered.connect(lambda: self.close_tab_widget(clicked_tab))
        menu.addAction(act_close)
        
        menu.exec(self.tabs.tabBar().mapToGlobal(pos))

    def assign_tab_to_split(self, tab, side: str):
        self.ensure_valid_split_pair()
        self.is_split_mode = True
        self.switch_split_card(side, tab)

    def rebuild_view_layout(self, auto_collapse_on_split=False):
        count = len(self.tab_list)
        if count < 2:
            self.is_split_mode = False
            
        self.tabs.blockSignals(True)
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)
        self.tabs.blockSignals(False)
        
        while self.split_layout.count() > 0:
            item = self.split_layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)

        if self.is_split_mode and count >= 2:
            self.ensure_valid_split_pair()
            self.adjust_window_size_for_mode(True)
            self.split_top_bar.show()
            self.btn_switch_to_split.hide()
            
            for t in self.tab_list:
                if t not in (self.split_left_tab, self.split_right_tab):
                    t.hide()
                    t.setParent(None)
            
            left_tab = self.split_left_tab
            right_tab = self.split_right_tab
            
            left_tab.set_panel_side("left", show_header=True)
            right_tab.set_panel_side("right", show_header=True)
            
            if auto_collapse_on_split:
                left_tab.toggle_left_panel(False)
                right_tab.toggle_left_panel(False)
                
            left_tab.update_header_title()
            right_tab.update_header_title()
            
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.VLine)
            separator.setStyleSheet("background-color: #27272a; max-width: 2px;")
            
            self.split_layout.addWidget(left_tab, stretch=1)
            self.split_layout.addWidget(separator)
            self.split_layout.addWidget(right_tab, stretch=1)
            
            left_tab.show()
            right_tab.show()
            self.update_split_info_label()
            self.view_stack.setCurrentWidget(self.split_container)
        else:
            self.adjust_window_size_for_mode(False)
            self.split_top_bar.hide()
            self.btn_switch_to_split.setVisible(count >= 2)
            
            for tab in self.tab_list:
                tab.set_panel_side("left", show_header=False)
                if count == 1:
                    tab.toggle_left_panel(True)
                self.tabs.addTab(tab, tab.get_tab_title())
                tab.show()
                
            self.tabs.setCurrentIndex(self.tabs.count() - 1)
            self.view_stack.setCurrentWidget(self.tabs)
            
        self.save_tabs_state()

    def save_tabs_state(self):
        tabs_configs = []
        for tab in self.tab_list:
            if hasattr(tab, 'combo_cfg') and tab.combo_cfg.currentText():
                tabs_configs.append(tab.combo_cfg.currentText())
        self.app_settings["open_tabs"] = tabs_configs
        save_app_settings(self.app_settings)
        
    def update_tab_label(self, tab):
        title = tab.get_tab_title()
        idx = self.tabs.indexOf(tab)
        if idx >= 0:
            self.tabs.setTabText(idx, title)
        if self.is_split_mode:
            self.update_split_info_label()
        self.save_tabs_state()

    def add_new_tab(self, cli_config=None, rebuild=True):
        if len(self.tab_list) >= 10:
            QMessageBox.warning(self, "Limit kart", "Osiągnięto maksymalną liczbę otwartych kart (10).")
            return
            
        free_port = None
        if not cli_config:
            available_ports = [p.device for p in serial.tools.list_ports.comports()]
            used_ports = [t.get_selected_port_device() for t in self.tab_list]
            unused_ports = [p for p in available_ports if p not in used_ports]
            
            if not unused_ports and len(self.tab_list) > 0:
                QMessageBox.warning(self, "Brak wolnych portów", "Wszystkie dostępne porty COM w systemie są już przypisane do otwartych kart.")
                return
                
            if unused_ports:
                free_port = unused_ports[0]
            cli_config = "default.json"
            
        tab = SerialTab(cli_config, main_window=self)
        tab.tab_state_changed.connect(lambda t=tab: self.update_tab_label(t))
        tab.close_requested.connect(self.close_tab_widget)
        
        if free_port:
            for i in range(tab.port_combo.count()):
                if tab.port_combo.itemData(i, Qt.ItemDataRole.UserRole) == free_port:
                    tab.port_combo.setCurrentIndex(i)
                    break
                    
        self.tab_list.append(tab)
        
        if rebuild:
            if len(self.tab_list) == 2:
                self.is_split_mode = True
                self.split_left_tab = self.tab_list[0]
                self.split_right_tab = self.tab_list[1]
                self.rebuild_view_layout(auto_collapse_on_split=True)
            elif self.is_split_mode:
                self.split_right_tab = tab
                self.rebuild_view_layout(auto_collapse_on_split=True)
            else:
                self.rebuild_view_layout(auto_collapse_on_split=False)
            
    def close_tab_by_index(self, index):
        if 0 <= index < self.tabs.count():
            tab = self.tabs.widget(index)
            self.close_tab_widget(tab)

    def close_tab_widget(self, tab):
        if tab not in self.tab_list:
            return
        if hasattr(tab, 'close_tab'):
            if not tab.close_tab():
                return
                
        self.tab_list.remove(tab)
        tab.setParent(None)
        tab.deleteLater()
        
        if len(self.tab_list) == 0:
            self.save_tabs_state()
            self.close()
        else:
            if len(self.tab_list) == 2:
                self.is_split_mode = True
            self.ensure_valid_split_pair()
            self.rebuild_view_layout(auto_collapse_on_split=(len(self.tab_list) == 2))

    def closeEvent(self, event):
        tabs_with_logs = sum(1 for tab in self.tab_list if getattr(tab, 'has_real_logs', False))
                
        if tabs_with_logs > 0:
            reply = QMessageBox.question(
                self, 'Zamykanie Programu', 
                f'Masz {tabs_with_logs} kart(y) z niezapisanymi logami.\nCzy na pewno chcesz zamknąć program bez ich zapisywania?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

        for tab in self.tab_list:
            if hasattr(tab, 'close_tab'):
                tab.close_tab(skip_log_prompt=True)
                
        self.save_tabs_state()
        event.accept()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Terminal Diagnostyczny")
    parser.add_argument('--config', type=str, default='', help='Wymuś wczytanie konkretnego pliku np. --config auto.json')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    window = MainWindow(cli_config=args.config)
    window.show()
    sys.exit(app.exec())