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
                         CAN_DATA_BITRATES, DEFAULT_CAN_DATA_BITRATE,
                         TRANSPORT_SERIAL, TRANSPORT_SLCAN, TRANSPORT_CANDLE, TRANSPORTS, TRANSPORT_LABELS,
                         is_can_transport, list_candle_devices, OtAppMsgTlv,
                         CanFrameError, CanWorker, parse_can_frame, normalize_can_ack_pattern,
                         normalize_can_id_text, extract_can_id_from_line, can_id_sort_key,
                         format_bitrate_label, CAN_MODE_AUTO, CAN_MODE_CLASSIC, CAN_MODE_FD_BRS, CAN_MODE_FD_NO_BRS, CAN_MODE_TLV, CAN_FRAME_MODES, convert_can_frame_text, TLV_HEADER_SIZE)

CFG_DIR = "cfg"
APP_SETTINGS_FILE = os.path.join(CFG_DIR, "app_settings.json")
APP_VERSION = "1.9.0"

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
        "ack_off": "AA 00 00 55",
        "rx_pattern": "",
        "timeout": 1000,
        "steps": [],
        "current_step": 0,
        "can_mode": CAN_MODE_AUTO
    }

def get_default_config():
    config = {
        "transport": TRANSPORT_SERIAL,      # "serial" (UART) | "slcan" (CANable) | "candle" (candleLight CAN FD)
        "port": "",
        "baudrate": 115200,
        "mode": "ASCII",
        "eol": "CRLF",
        "can_bitrate": DEFAULT_CAN_BITRATE,
        "can_data_bitrate": DEFAULT_CAN_DATA_BITRATE,
        "can_sample_point": 80.0,
        "can_data_sample_point": 80.0,
        "can_fd_enabled": True,
        "can_listen_only": False,
        "can_watch_auto": True,
        "filters": [],
        "parsers": [],
        "watch_patterns": [],
        "watch_print_in_console": True,
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
                    config["watch_print_in_console"] = True
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
                try:
                    if int(config.get("can_data_bitrate", DEFAULT_CAN_DATA_BITRATE)) not in CAN_DATA_BITRATES:
                        config["can_data_bitrate"] = DEFAULT_CAN_DATA_BITRATE
                    else:
                        config["can_data_bitrate"] = int(config["can_data_bitrate"])
                except (TypeError, ValueError):
                    config["can_data_bitrate"] = DEFAULT_CAN_DATA_BITRATE
                if "can_sample_point" not in config:
                    config["can_sample_point"] = 80.0
                if "can_data_sample_point" not in config:
                    config["can_data_sample_point"] = 80.0
                if "can_fd_enabled" not in config:
                    config["can_fd_enabled"] = True
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
    """W spoczynku wyświetla tylko krótki kod portu (np. COM20 lub candle:0:0), a po rozwinięciu pełny opis urządzenia ze statusem dostępności."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(92)
        self.new_ports = set()

    def set_new_ports(self, new_ports: set[str]):
        self.new_ports = set(new_ports)
        self._apply_item_styles()

    def _apply_item_styles(self):
        for i in range(self.count()):
            dev = self.itemData(i, Qt.ItemDataRole.UserRole)
            is_busy = bool(self.itemData(i, Qt.ItemDataRole.UserRole + 2))
            if is_busy:
                # Ostrzeżenie: urządzenie zajęte przez inny proces
                self.setItemData(i, QColor("#3b1818"), Qt.ItemDataRole.BackgroundRole)
                self.setItemData(i, QColor("#ff8787"), Qt.ItemDataRole.ForegroundRole)
            elif dev in self.new_ports:
                self.setItemData(i, QColor("#1b4332"), Qt.ItemDataRole.BackgroundRole)
                self.setItemData(i, QColor("#8ce99a"), Qt.ItemDataRole.ForegroundRole)
            else:
                self.setItemData(i, None, Qt.ItemDataRole.BackgroundRole)
                self.setItemData(i, None, Qt.ItemDataRole.ForegroundRole)

    def showPopup(self):
        for i in range(self.count()):
            dev = self.itemData(i, Qt.ItemDataRole.UserRole)
            full_desc = self.itemData(i, Qt.ItemDataRole.UserRole + 1)
            is_busy = bool(self.itemData(i, Qt.ItemDataRole.UserRole + 2))
            if full_desc:
                if is_busy:
                    self.setItemText(i, f"🔒 {full_desc}")
                elif dev in self.new_ports:
                    self.setItemText(i, f"✨ {full_desc}  [NOWY]")
                else:
                    self.setItemText(i, full_desc)
        self.view().setMinimumWidth(380)
        super().showPopup()

    def hidePopup(self):
        super().hidePopup()
        for i in range(self.count()):
            short_dev = self.itemData(i, Qt.ItemDataRole.UserRole)
            is_busy = bool(self.itemData(i, Qt.ItemDataRole.UserRole + 2))
            if short_dev:
                if is_busy:
                    self.setItemText(i, f"{short_dev} 🔒")
                else:
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
# 2. OKNA DIALOGOWE EDYCJI I POMOCNIKI
# ==========================================

CNT_PATTERN = re.compile(r'\{(?:CNT|SEQ)(?::([0-9a-fA-F]+)-([0-9a-fA-F]+)(?::([a-zA-Z0-9]+))?)?\}')

def evaluate_dynamic_tokens(text: str, counter_dict: dict, counter_scope_id) -> str:
    """
    Zastępuje w tekście komendy/ramki znaczniki licznika kroczącego:
    - {CNT} lub {SEQ}: standardowy licznik kroczący (0..255)
    - {CNT:min-max}: zakres min..max (dziesiętny, np. {CNT:0-15}, {CNT:00-99})
    - {CNT:min-max:X} lub {CNT:min-max:HEX}: format szesnastkowy wielkimi literami (np. {CNT:0-15:X}, {CNT:00-FF:X})
    - {CNT:min-max:x}: format szesnastkowy małymi literami
    """
    if not text or ("{CNT" not in text and "{SEQ" not in text):
        return text

    def replacer(match):
        raw_min = match.group(1)
        raw_max = match.group(2)
        raw_fmt = match.group(3) or ""
        fmt_upper = raw_fmt.upper()
        is_hex = "X" in fmt_upper or "HEX" in fmt_upper or any(c in "abcdefABCDEF" for c in (raw_min or "")) or any(c in "abcdefABCDEF" for c in (raw_max or ""))
        
        base = 16 if (is_hex and any(c in "abcdefABCDEF" for c in (raw_min or "") + (raw_max or ""))) else 10
        try:
            min_val = int(raw_min, base) if raw_min else 0
            max_val = int(raw_max, base) if raw_max else 255
        except ValueError:
            min_val, max_val = 0, 255

        if min_val > max_val:
            min_val, max_val = max_val, min_val

        key = (counter_scope_id, match.group(0))
        cur_val = counter_dict.get(key, min_val)
        next_val = min_val if cur_val >= max_val else cur_val + 1
        counter_dict[key] = next_val

        w_match = re.search(r'(\d+)', raw_fmt)
        explicit_width = int(w_match.group(1)) if w_match else 0

        if is_hex:
            if explicit_width > 0:
                width = explicit_width
            elif raw_min and raw_min.startswith("0") and len(raw_min) > 1:
                width = len(raw_min)
            elif raw_max and any(c in "abcdefABCDEF" for c in raw_max):
                width = len(raw_max)
            else:
                width = len(f"{max_val:X}")
            char = 'x' if 'x' in raw_fmt else 'X'
            return f"{cur_val:0{width}{char}}"
        else:
            width = explicit_width if explicit_width > 0 else (len(raw_min) if (raw_min and raw_min.startswith("0") and len(raw_min) > 1) else 0)
            if width > 0:
                return f"{cur_val:0{width}d}"
            return str(cur_val)

    return CNT_PATTERN.sub(replacer, text)


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
    "query_tx": "187#01",
    "query_rx": "581#*",
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
    "query_tx": "np. 187#01",
    "query_rx": "np. 581#* lub 581#01*",
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
    def __init__(self, btn_data, parent=None, is_can_mode: bool = False,
                 transport: str = TRANSPORT_SERIAL, can_fd_enabled: bool = True):
        super().__init__(parent)
        self.setWindowTitle(f"Edytuj {btn_data.get('name', 'Przycisk')}")
        self.btn_data = btn_data
        
        # Ustalenie transportu i flag trybu CAN / CAN FD
        if transport == TRANSPORT_SERIAL and is_can_mode:
            transport = TRANSPORT_SLCAN
        self.transport = str(transport)
        self.is_can_mode = is_can_transport(self.transport) or bool(is_can_mode)
        # Tryb CAN FD jest dostępny WYŁĄCZNIE dla adaptera candleLight z włączoną obsługą FD:
        self.can_fd_capable = (self.transport == TRANSPORT_CANDLE) and bool(can_fd_enabled)
        
        self.delete_requested = False
        self.autofix_target = None
        self.autofix_replacement = None
        self.autofix_action = None
        
        self.resize(570, 650)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(6)
        self.main_layout.setContentsMargins(10, 8, 10, 8)
        
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
        self.combo_type.addItems(["push", "toggle", "hold", "trigger", "macro", "query", "step"])
        self.combo_type.setCurrentText(btn_data.get("type", "push"))
        top_layout.addRow("Typ:", self.combo_type)
        
        self.combo_payload_type = QComboBox()
        if self.is_can_mode:
            self.combo_payload_type.addItem("CAN")
            self.combo_payload_type.setCurrentText("CAN")
            self.combo_payload_type.setEnabled(False)
            if self.can_fd_capable:
                self.combo_payload_type.setToolTip("W profilu CAN / CAN FD (candleLight) format przycisków jest zablokowany na CAN.")
            else:
                self.combo_payload_type.setToolTip("W profilu CANable (slcan) format przycisków jest zablokowany na CAN (wyłącznie klasyczny CAN 2.0).")
        else:
            self.combo_payload_type.addItems(["ASCII", "HEX"])
            cur_p = btn_data.get("payload_type", "ASCII")
            self.combo_payload_type.setCurrentText(cur_p if cur_p in ("ASCII", "HEX") else "ASCII")
            self.combo_payload_type.setToolTip("Format transmisji portu szeregowego: ASCII (tekst) lub HEX (bajty binarne).")
            
        top_layout.addRow("Format TX:", self.combo_payload_type)

        self.lbl_can_mode = QLabel("Standard CAN:")
        self.combo_can_mode = QComboBox()
        if self.can_fd_capable:
            # Dla candleLight CAN FD: pełne wsparcie formatów CAN 2.0 i CAN FD
            for mode_key, mode_title in CAN_FRAME_MODES:
                self.combo_can_mode.addItem(mode_title, mode_key)
            self.combo_can_mode.setToolTip("Wybierz standard ramki: Klasyczny CAN 2.0 (maks. 8B), CAN FD z BRS (do 64B), CAN FD bez BRS lub TLV.")
        else:
            # Dla CANable (slcan): WYŁĄCZNIE klasyczny standard CAN 2.0 (maks. 8B)
            self.combo_can_mode.addItem("Klasyczny CAN 2.0 (maks. 8B, standard)", CAN_MODE_CLASSIC)
            self.combo_can_mode.addItem("Auto (ze składni, maks. 8B)", CAN_MODE_AUTO)
            self.combo_can_mode.setToolTip("Adapter CANable (slcan) obsługuje wyłącznie standard Klasyczny CAN 2.0 (maks. 8B). Tryb CAN FD jest dostępny tylko dla adaptera candleLight.")

        cur_can_mode = btn_data.get("can_mode", CAN_MODE_AUTO if self.can_fd_capable else CAN_MODE_CLASSIC)
        idx_can = self.combo_can_mode.findData(cur_can_mode)
        if idx_can >= 0:
            self.combo_can_mode.setCurrentIndex(idx_can)
        else:
            self.combo_can_mode.setCurrentIndex(0)

        self.lbl_can_mode.setVisible(self.is_can_mode)
        self.combo_can_mode.setVisible(self.is_can_mode)
        self.combo_can_mode.currentIndexChanged.connect(lambda *args: self.validate_and_preview())
        top_layout.addRow(self.lbl_can_mode, self.combo_can_mode)
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

        # Pomocnik szybkiego wstawiania liczników {CNT}
        self.token_helper_frame = QFrame()
        self.token_helper_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1b1e;
                border: 1px dashed #3f3f46;
                border-radius: 6px;
                padding: 4px 8px;
            }
        """)
        helper_layout = QVBoxLayout(self.token_helper_frame)
        helper_layout.setContentsMargins(6, 4, 6, 4)
        helper_layout.setSpacing(4)
        
        lbl_helper_title = QLabel("💡 Szybkie wstawianie licznika {CNT} (kliknij, aby wstawić do pola TX):")
        lbl_helper_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #69db7c; background: transparent; border: none;")
        helper_layout.addWidget(lbl_helper_title)
        
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(4)
        
        chip_style = """
            QPushButton {
                background-color: #27272a;
                color: #e4e4e7;
                font-size: 10px;
                font-weight: 500;
                padding: 3px 6px;
                border: 1px solid #3f3f46;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #228be6;
                color: white;
                border-color: #4dabf7;
            }
        """
        
        btn_chip_1 = QPushButton("+ 1B HEX {CNT:00-FF:X}")
        btn_chip_1.setToolTip("Wstawia 1-bajtowy licznik szesnastkowy 00..FF (dokładnie 2 cyfry hex).")
        btn_chip_1.setStyleSheet(chip_style)
        btn_chip_1.clicked.connect(lambda: self.insert_token("{CNT:00-FF:X}"))
        
        btn_chip_2 = QPushButton("+ 1B 0..15 {CNT:00-0F:X}")
        btn_chip_2.setToolTip("Wstawia 1-bajtowy licznik szesnastkowy z zakresem 0..15 (00..0F, dokładnie 2 cyfry hex).")
        btn_chip_2.setStyleSheet(chip_style)
        btn_chip_2.clicked.connect(lambda: self.insert_token("{CNT:00-0F:X}"))

        btn_chip_3 = QPushButton("+ Półbajt 0{CNT:0-15:X}")
        btn_chip_3.setToolTip("Wstawia 4-bitowy licznik 0..F w parze z zerem wiodącym (00..0F), zachowując wymagane 2 cyfry hex na bajt w CAN.")
        btn_chip_3.setStyleSheet(chip_style)
        btn_chip_3.clicked.connect(lambda: self.insert_token("0{CNT:0-15:X}"))

        btn_chip_4 = QPushButton("+ Dec {CNT}")
        btn_chip_4.setToolTip("Wstawia standardowy licznik dziesiętny 0..255.")
        btn_chip_4.setStyleSheet(chip_style)
        btn_chip_4.clicked.connect(lambda: self.insert_token("{CNT}"))

        btn_chip_5 = QPushButton("+ Dec {CNT:00-99}")
        btn_chip_5.setToolTip("Wstawia dwucyfrowy licznik dziesiętny 00..99 o stałej szerokości.")
        btn_chip_5.setStyleSheet(chip_style)
        btn_chip_5.clicked.connect(lambda: self.insert_token("{CNT:00-99}"))
        
        chips_layout.addWidget(btn_chip_1)
        chips_layout.addWidget(btn_chip_2)
        chips_layout.addWidget(btn_chip_3)
        chips_layout.addWidget(btn_chip_4)
        chips_layout.addWidget(btn_chip_5)
        chips_layout.addStretch()
        helper_layout.addLayout(chips_layout)

        self.can_chips_widget = QWidget()
        can_chips_layout = QHBoxLayout(self.can_chips_widget)
        can_chips_layout.setContentsMargins(0, 2, 0, 0)
        can_chips_layout.setSpacing(4)

        btn_can_classic = QPushButton("🚗 Szablon CAN 2.0 (8B)")
        btn_can_classic.setToolTip("Wstawia ramkę klasycznego CAN 2.0 (8 bajtów) i ustawia standard na Klasyczny CAN 2.0.")
        btn_can_classic.setStyleSheet(chip_style)
        btn_can_classic.clicked.connect(self.insert_can_classic_template)
        can_chips_layout.addWidget(btn_can_classic)

        # Kafelki CAN FD i TLV dostępne TYLKO dla candleLight CAN FD:
        self.btn_can_fd = QPushButton("⚡ Szablon CAN FD (64B)")
        self.btn_can_fd.setToolTip("Wstawia pełną ramkę CAN FD (64 bajty) z flagą BRS (##1#) i ustawia standard na CAN FD z BRS.")
        self.btn_can_fd.setStyleSheet(chip_style)
        self.btn_can_fd.clicked.connect(self.insert_can_fd_template)

        self.btn_can_tlv = QPushButton("📦 Szablon TLV (64B)")
        self.btn_can_tlv.setToolTip("Wstawia składnię TLV#<ID>#<TYPE>#<PAYLOAD> do pakowania w ot_app_msg_tlv i ustawia standard TLV.")
        self.btn_can_tlv.setStyleSheet(chip_style)
        self.btn_can_tlv.clicked.connect(self.insert_can_tlv_template)

        can_chips_layout.addWidget(self.btn_can_fd)
        can_chips_layout.addWidget(self.btn_can_tlv)
        self.btn_can_fd.setVisible(self.can_fd_capable)
        self.btn_can_tlv.setVisible(self.can_fd_capable)

        btn_can_convert = QPushButton("🔄 Konwertuj do trybu")
        btn_can_convert.setToolTip("Konwertuje aktualnie wpisaną ramkę do standardu wybranego w polu 'Standard CAN'.")
        btn_can_convert.setStyleSheet("""
            QPushButton {
                background-color: #1c7ed6;
                color: white;
                font-size: 10px;
                font-weight: bold;
                padding: 3px 8px;
                border: 1px solid #228be6;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1971c2;
            }
        """)
        btn_can_convert.clicked.connect(self.convert_current_tx_to_can_mode)
        can_chips_layout.addWidget(btn_can_convert)
        can_chips_layout.addStretch()
        self.can_chips_widget.setVisible(self.is_can_mode)
        helper_layout.addWidget(self.can_chips_widget)
        self.main_layout.addWidget(self.token_helper_frame)
        
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
        
        # QUERY (Zapytanie / Request-Response z timeoutem)
        self.page_query = QWidget()
        l_query = QFormLayout(self.page_query)
        query_tx_val = "" if is_new_btn else btn_data.get("tx", "")
        query_tx_ex = CAN_BUTTON_EXAMPLES["query_tx"] if use_can_defaults else ""
        self.le_query_tx = ClickToClearLineEdit(query_tx_val, example_text=query_tx_ex)

        query_rx_val = "" if is_new_btn else btn_data.get("rx_pattern", "")
        query_rx_ex = CAN_BUTTON_EXAMPLES["query_rx"] if use_can_defaults else ""
        self.le_query_rx = ClickToClearLineEdit(query_rx_val, example_text=query_rx_ex)

        self.spin_query_timeout = QSpinBox()
        self.spin_query_timeout.setRange(50, 30000)
        self.spin_query_timeout.setValue(btn_data.get("timeout", 1000))
        self.spin_query_timeout.setSingleStep(100)
        self.spin_query_timeout.setSuffix(" ms")

        l_query.addRow("Zapytanie (TX):", self.le_query_tx)
        l_query.addRow("Oczekiwana odp. (RX):", self.le_query_rx)
        l_query.addRow("Limit czasu (Timeout):", self.spin_query_timeout)
        self.stack.addWidget(self.page_query)

        # STEP (Przełącznik wielostanowy / Stepper)
        self.page_step = QWidget()
        l_step = QVBoxLayout(self.page_step)
        l_step.setContentsMargins(0, 0, 0, 0)
        l_step.setSpacing(6)

        lbl_step_hint = QLabel("Zdefiniuj kolejne stany / kroki (przełączane cyklicznie po kliknięciu):")
        lbl_step_hint.setStyleSheet("color: #ced4da; font-weight: bold; font-size: 11px;")
        l_step.addWidget(lbl_step_hint)

        self.table_steps = QTableWidget()
        self.table_steps.setColumnCount(2)
        self.table_steps.setHorizontalHeaderLabels(["Etykieta stanu / kroku", "Komenda / Ramka TX"])
        self.table_steps.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table_steps.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_steps.setColumnWidth(0, 160)
        self.table_steps.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_steps.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        l_step.addWidget(self.table_steps)

        step_btn_layout = QHBoxLayout()
        self.btn_add_step = QPushButton("+ Dodaj krok")
        self.btn_del_step = QPushButton("Usuń krok")
        self.btn_step_up = QPushButton("▲ W górę")
        self.btn_step_down = QPushButton("▼ W dół")
        step_btn_layout.addWidget(self.btn_add_step)
        step_btn_layout.addWidget(self.btn_del_step)
        step_btn_layout.addWidget(self.btn_step_up)
        step_btn_layout.addWidget(self.btn_step_down)
        l_step.addLayout(step_btn_layout)
        self.stack.addWidget(self.page_step)

        self.btn_add_step.clicked.connect(lambda: self.on_add_step())
        self.btn_del_step.clicked.connect(self.on_del_step)
        self.btn_step_up.clicked.connect(self.on_step_up)
        self.btn_step_down.clicked.connect(self.on_step_down)

        # Wypełnienie kroków dla tabeli STEP
        existing_steps = btn_data.get("steps", [])
        if existing_steps:
            for s in existing_steps:
                self.on_add_step(label=s.get("label", ""), tx=s.get("tx", ""))
        else:
            if use_can_defaults:
                self.on_add_step(label="Krok 1 (0%)", tx="187#00")
                self.on_add_step(label="Krok 2 (50%)", tx="187#7F")
                self.on_add_step(label="Krok 3 (100%)", tx="187#FF")
            else:
                self.on_add_step(label="Krok 1", tx="MODE 1")
                self.on_add_step(label="Krok 2", tx="MODE 2")
                self.on_add_step(label="Krok 3", tx="MODE 3")
        
        self.main_layout.addWidget(self.stack)
        
        # Ramka podglądu wygenerowanej ramki i walidacji składni
        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet("""
            QFrame {
                background-color: #121316;
                border: 1px solid #2e3035;
                border-radius: 6px;
                padding: 6px 8px;
            }
        """)
        prev_layout = QVBoxLayout(self.preview_frame)
        prev_layout.setContentsMargins(8, 6, 8, 6)
        prev_layout.setSpacing(4)
        
        prev_header_layout = QHBoxLayout()
        self.lbl_preview_title = QLabel("👁 Podgląd wygenerowanej ramki:")
        self.lbl_preview_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #a1a1aa; background: transparent; border: none;")
        prev_header_layout.addWidget(self.lbl_preview_title)
        
        self.lbl_preview_val = QLabel("")
        self.lbl_preview_val.setStyleSheet("font-family: Consolas, monospace; font-size: 11px; color: #ffd43b; background: transparent; border: none;")
        self.lbl_preview_val.setWordWrap(True)
        prev_header_layout.addWidget(self.lbl_preview_val, 1)
        prev_layout.addLayout(prev_header_layout)
        
        status_row_layout = QHBoxLayout()
        self.lbl_preview_status = QLabel("")
        self.lbl_preview_status.setStyleSheet("font-size: 11px; background: transparent; border: none;")
        self.lbl_preview_status.setWordWrap(True)
        status_row_layout.addWidget(self.lbl_preview_status, 1)
        
        self.btn_autofix = QPushButton("⚡ Napraw automatycznie")
        self.btn_autofix.setStyleSheet("""
            QPushButton {
                background-color: #e03131;
                color: white;
                font-size: 11px;
                font-weight: bold;
                padding: 3px 10px;
                border-radius: 4px;
                border: 1px solid #fa5252;
            }
            QPushButton:hover {
                background-color: #f03e3e;
            }
        """)
        self.btn_autofix.setVisible(False)
        self.btn_autofix.clicked.connect(self.apply_autofix)
        status_row_layout.addWidget(self.btn_autofix)
        
        prev_layout.addLayout(status_row_layout)
        self.main_layout.addWidget(self.preview_frame)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Discard)
        buttons.button(QDialogButtonBox.StandardButton.Discard).setText("Usuń / Wyczyść")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Discard).clicked.connect(self.on_delete)
        self.main_layout.addWidget(buttons)
        
        self.combo_type.currentTextChanged.connect(self.update_stack)
        self.combo_payload_type.currentTextChanged.connect(self.on_payload_type_changed)

        # Połączenie sygnałów aktualizacji walidacji na żywo
        self.le_push_tx.textChanged.connect(self.validate_and_preview)
        self.le_tog_tx_on.textChanged.connect(self.validate_and_preview)
        self.le_tog_tx_off.textChanged.connect(self.validate_and_preview)
        self.le_hld_tx_on.textChanged.connect(self.validate_and_preview)
        self.le_hld_tx_off.textChanged.connect(self.validate_and_preview)
        self.le_trig_tx.textChanged.connect(self.validate_and_preview)
        self.le_mac_tx.textChanged.connect(self.validate_and_preview)
        self.le_query_tx.textChanged.connect(self.validate_and_preview)
        self.table_steps.itemChanged.connect(lambda item: self.validate_and_preview())
        
        self.update_stack(self.combo_type.currentText())
        self.on_payload_type_changed(self.combo_payload_type.currentText())
        self.validate_and_preview()

    def on_add_step(self, label="", tx=""):
        r = self.table_steps.rowCount()
        self.table_steps.insertRow(r)
        is_can = (self.combo_payload_type.currentText() == "CAN") or self.is_can_mode
        default_label = label if label else f"Krok {r+1}"
        default_tx = tx if tx else ("187#00" if is_can else "")
        self.table_steps.setItem(r, 0, QTableWidgetItem(default_label))
        self.table_steps.setItem(r, 1, QTableWidgetItem(default_tx))
        self.table_steps.selectRow(r)

    def on_del_step(self):
        cur_row = self.table_steps.currentRow()
        if cur_row >= 0:
            self.table_steps.removeRow(cur_row)

    def on_step_up(self):
        r = self.table_steps.currentRow()
        if r > 0:
            item0_text = self.table_steps.item(r, 0).text() if self.table_steps.item(r, 0) else ""
            item1_text = self.table_steps.item(r, 1).text() if self.table_steps.item(r, 1) else ""
            prev0_text = self.table_steps.item(r - 1, 0).text() if self.table_steps.item(r - 1, 0) else ""
            prev1_text = self.table_steps.item(r - 1, 1).text() if self.table_steps.item(r - 1, 1) else ""
            self.table_steps.setItem(r, 0, QTableWidgetItem(prev0_text))
            self.table_steps.setItem(r, 1, QTableWidgetItem(prev1_text))
            self.table_steps.setItem(r - 1, 0, QTableWidgetItem(item0_text))
            self.table_steps.setItem(r - 1, 1, QTableWidgetItem(item1_text))
            self.table_steps.selectRow(r - 1)

    def on_step_down(self):
        r = self.table_steps.currentRow()
        if r >= 0 and r < self.table_steps.rowCount() - 1:
            item0_text = self.table_steps.item(r, 0).text() if self.table_steps.item(r, 0) else ""
            item1_text = self.table_steps.item(r, 1).text() if self.table_steps.item(r, 1) else ""
            next0_text = self.table_steps.item(r + 1, 0).text() if self.table_steps.item(r + 1, 0) else ""
            next1_text = self.table_steps.item(r + 1, 1).text() if self.table_steps.item(r + 1, 1) else ""
            self.table_steps.setItem(r, 0, QTableWidgetItem(next0_text))
            self.table_steps.setItem(r, 1, QTableWidgetItem(next1_text))
            self.table_steps.setItem(r + 1, 0, QTableWidgetItem(item0_text))
            self.table_steps.setItem(r + 1, 1, QTableWidgetItem(item1_text))
            self.table_steps.selectRow(r + 1)

    def on_payload_type_changed(self, ptype):
        is_can = (ptype == "CAN") or self.is_can_mode
        if hasattr(self, "lbl_can_mode") and hasattr(self, "combo_can_mode"):
            self.lbl_can_mode.setVisible(is_can)
            self.combo_can_mode.setVisible(is_can)
        if hasattr(self, "can_chips_widget"):
            self.can_chips_widget.setVisible(is_can)
        if hasattr(self, "btn_can_fd"):
            self.btn_can_fd.setVisible(is_can and self.can_fd_capable)
        if hasattr(self, "btn_can_tlv"):
            self.btn_can_tlv.setVisible(is_can and self.can_fd_capable)
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
            self.le_query_tx.setPlaceholderText(CAN_BUTTON_PLACEHOLDERS["query_tx"])
            self.le_query_rx.setPlaceholderText(CAN_BUTTON_PLACEHOLDERS["query_rx"])
            
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
                (self.le_query_tx, CAN_BUTTON_EXAMPLES["query_tx"]),
                (self.le_query_rx, CAN_BUTTON_EXAMPLES["query_rx"]),
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
            self.le_query_tx.setPlaceholderText("np. 01 03 00 00 00 02")
            self.le_query_rx.setPlaceholderText("np. 01 03*")
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
            self.le_query_tx.setPlaceholderText("np. AT+STATUS?")
            self.le_query_rx.setPlaceholderText("np. *OK* lub *READY*")
            
        self.update_stack(self.combo_type.currentText())
        
    def insert_can_classic_template(self):
        idx = self.combo_can_mode.findData(CAN_MODE_CLASSIC)
        if idx >= 0:
            self.combo_can_mode.setCurrentIndex(idx)
        w = self.get_active_tx_widget()
        if isinstance(w, ClickToClearLineEdit):
            w.setText("187#01 02 03 04 05 06 07 08")
            w.setFocus()
        elif isinstance(w, ClickToClearPlainTextEdit):
            w.setPlainText("187#01 02 03 04 05 06 07 08")
            w.setFocus()
        self.validate_and_preview()

    def insert_can_fd_template(self):
        idx = self.combo_can_mode.findData(CAN_MODE_FD_BRS)
        if idx >= 0:
            self.combo_can_mode.setCurrentIndex(idx)
        w = self.get_active_tx_widget()
        fd_example = "321##1#01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F 10"
        if isinstance(w, ClickToClearLineEdit):
            w.setText(fd_example)
            w.setFocus()
        elif isinstance(w, ClickToClearPlainTextEdit):
            w.setPlainText(fd_example)
            w.setFocus()
        self.validate_and_preview()

    def insert_can_tlv_template(self):
        idx = self.combo_can_mode.findData(CAN_MODE_TLV)
        if idx >= 0:
            self.combo_can_mode.setCurrentIndex(idx)
        w = self.get_active_tx_widget()
        tlv_example = "TLV#321#0xA5#Komenda testowa"
        if isinstance(w, ClickToClearLineEdit):
            w.setText(tlv_example)
            w.setFocus()
        elif isinstance(w, ClickToClearPlainTextEdit):
            w.setPlainText(tlv_example)
            w.setFocus()
        self.validate_and_preview()

    def convert_current_tx_to_can_mode(self):
        cur_mode = self.combo_can_mode.currentData() or CAN_MODE_AUTO
        if not self.can_fd_capable:
            cur_mode = CAN_MODE_CLASSIC
        w = self.get_active_tx_widget()
        if isinstance(w, ClickToClearLineEdit):
            new_txt = convert_can_frame_text(w.text().strip(), cur_mode)
            if new_txt:
                w.setText(new_txt)
        elif isinstance(w, ClickToClearPlainTextEdit):
            lines = w.toPlainText().splitlines()
            new_lines = []
            for line in lines:
                l_s = line.strip()
                if l_s and not l_s.lower().startswith("sleep"):
                    new_lines.append(convert_can_frame_text(l_s, cur_mode))
                else:
                    new_lines.append(line)
            w.setPlainText("\n".join(new_lines))
        self.validate_and_preview()

    def update_stack(self, text):
        mapping = {"push": 0, "toggle": 1, "hold": 2, "trigger": 3, "macro": 4, "query": 5, "step": 6}
        self.stack.setCurrentIndex(mapping.get(text, 0))
        
        is_can = (self.combo_payload_type.currentText() == "CAN") or self.is_can_mode
        
        if is_can:
            can_syntax_map = {
                "push": (
                    "📌 Składnia CAN: ID#DANE (np. 187#01 02 03 04, 18FEF100#AABB, 65A#R)",
                    "Wysyła pojedynczą ramkę CAN natychmiast po kliknięciu. Liczniki: {CNT:00-FF:X} (1B) lub 0{CNT:0-15:X} (4-bit)."
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
                    "Generator cykliczny: nadaje ramkę w pętli co zadany interwał (ms). Liczniki: {CNT:00-FF:X} (1B) lub 0{CNT:0-15:X} (4-bit). Pamiętaj: dane w CAN muszą mieć parzystą liczbę cyfr HEX!"
                ),
                "macro": (
                    "📌 Składnia CAN: sekwencja ramek rozdzielonych ';' lub nowymi liniami, pauzy: sleep(ms)",
                    "Przykład: '187#01 02; sleep(100); 187#00'. Sekwencja wykonywana jest w osobnym wątku roboczym."
                ),
                "query": (
                    "📌 Składnia CAN: Zapytanie ID#DANE | Oczekiwana odp: ID#DANE* (np. 7DF#... | 7E8#*)",
                    "Wysyła ramkę zapytania i oczekuje na ramkę odpowiedzi w czasie Timeout. Sukces = zielony [OK], przekroczenie czasu = czerwony [TIMEOUT]."
                ),
                "step": (
                    "📌 Składnia CAN: ID#DANE dla każdego kroku w tabeli poniżej",
                    "Przełącznik wielostanowy (krokowy). Każde kliknięcie wysyła kolejny krok (cyklicznie 1..N) i aktualizuje etykietę na kafelku."
                )
            }
            syntax, desc = can_syntax_map.get(text, ("", ""))
        else:
            uart_syntax_map = {
                "push": (
                    "📌 Format: ASCII / HEX (np. AA 01 02)",
                    "Kliknięcie wysyła podaną ramkę jeden raz. Obsługuje licznik kroczący {CNT}."
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
                    "Pętla asynchroniczna wysyłająca ramkę co zadany interwał (ms). Obsługuje licznik {CNT}."
                ),
                "macro": (
                    "📌 Format: komendy rozdzielone ';' lub nowymi liniami, pauzy: sleep(ms)",
                    "Wykonuje sekwencję komend rozdzielonych średnikiem lub nową linią z opóźnieniami sleep(ms)."
                ),
                "query": (
                    "📌 Format: ASCII / HEX | Oczekiwana odp: wzorzec (*OK*, 01 03* itp.)",
                    "Wysyła zapytanie i oczekuje na odpowiedź pasującą do wzorca w zadanym czasie. Sukces = zielony [OK], brak odpowiedzi = czerwony [TIMEOUT]."
                ),
                "step": (
                    "📌 Format: ASCII / HEX dla każdego kroku w tabeli poniżej",
                    "Przełącznik wielostanowy. Każde kliknięcie wysyła kolejną wartość z listy i wyświetla aktualny stan na kafelku."
                )
            }
            syntax, desc = uart_syntax_map.get(text, ("", ""))
            
        self.info_syntax.setText(syntax)
        self.info_desc.setText(desc)
        self.validate_and_preview()

    def get_active_tx_widget(self):
        t = self.combo_type.currentText()
        if t == "push":
            return self.le_push_tx
        elif t == "toggle":
            if self.le_tog_tx_off.hasFocus():
                return self.le_tog_tx_off
            return self.le_tog_tx_on
        elif t == "hold":
            if self.le_hld_tx_off.hasFocus():
                return self.le_hld_tx_off
            return self.le_hld_tx_on
        elif t == "trigger":
            return self.le_trig_tx
        elif t == "macro":
            return self.le_mac_tx
        elif t == "query":
            return self.le_query_tx
        elif t == "step":
            return None
        return self.le_push_tx

    def insert_token(self, token: str):
        w = self.get_active_tx_widget()
        if isinstance(w, ClickToClearLineEdit):
            w.clear_example()
            w.insert(token)
            w.setFocus()
        elif isinstance(w, ClickToClearPlainTextEdit):
            w.clear_example()
            w.insertPlainText(token)
            w.setFocus()
        elif self.combo_type.currentText() == "step":
            row = self.table_steps.currentRow()
            if row < 0 and self.table_steps.rowCount() > 0:
                row = 0
            if row >= 0:
                item = self.table_steps.item(row, 1)
                if item:
                    item.setText(item.text() + token)
        self.validate_and_preview()

    def get_current_tx_text(self):
        w = self.get_active_tx_widget()
        if isinstance(w, ClickToClearLineEdit):
            if getattr(w, "is_example", False):
                return ""
            return w.text().strip()
        elif isinstance(w, ClickToClearPlainTextEdit):
            if getattr(w, "is_example", False):
                return ""
            lines = [l.strip() for l in w.toPlainText().splitlines() if l.strip() and not l.strip().lower().startswith("sleep")]
            return lines[0] if lines else ""
        elif self.combo_type.currentText() == "step":
            row = self.table_steps.currentRow()
            if row < 0 and self.table_steps.rowCount() > 0:
                row = 0
            if row >= 0:
                item = self.table_steps.item(row, 1)
                return item.text().strip() if item else ""
        return ""

    def validate_and_preview(self):
        raw_text = self.get_current_tx_text()
        self.btn_autofix.setVisible(False)
        self.autofix_target = None
        self.autofix_replacement = None

        if not raw_text:
            self.lbl_preview_val.setText("(brak danych TX lub aktywny przykład)")
            self.lbl_preview_status.setText("💡 Wpisz komendę/ramkę lub kliknij przycisk pomocnika powyżej.")
            self.lbl_preview_status.setStyleSheet("color: #868e96; font-size: 11px;")
            return

        dummy_counters = {}
        s0 = evaluate_dynamic_tokens(raw_text, dummy_counters, "preview")
        s1 = evaluate_dynamic_tokens(raw_text, dummy_counters, "preview")
        s2 = evaluate_dynamic_tokens(raw_text, dummy_counters, "preview")

        if "{CNT" in raw_text or "{SEQ" in raw_text:
            self.lbl_preview_val.setText(f"{s0}  ➔  {s1}  ➔  {s2}")
        else:
            self.lbl_preview_val.setText(s0)

        is_can = (self.combo_payload_type.currentText() == "CAN") or self.is_can_mode
        ptype = self.combo_payload_type.currentText()

        if is_can or ptype == "CAN":
            can_mode = self.combo_can_mode.currentData() if hasattr(self, 'combo_can_mode') else CAN_MODE_AUTO
            # Blokada składni CAN FD na adapterze CANable slcan:
            if not self.can_fd_capable:
                if "##" in s0 or s0.upper().startswith("TLV#"):
                    self.lbl_preview_status.setText("⚠️ Adapter CANable (slcan) nie obsługuje składni CAN FD ('##' / 'TLV#'). Dozwolony tylko klasyczny CAN 2.0 (maks. 8B).")
                    self.lbl_preview_status.setStyleSheet("color: #ff6b6b; font-size: 11px; font-weight: bold;")
                    self.autofix_action = "strip_double_hash"
                    self.btn_autofix.setText("⚡ Usuń '##' (zamień na '#')")
                    self.btn_autofix.setVisible(True)
                    return
                can_mode = CAN_MODE_CLASSIC
            try:
                frame0 = parse_can_frame(s0, can_mode=can_mode)
                frame1 = parse_can_frame(s1, can_mode=can_mode)
                id_fmt = f"0x{frame0.arbitration_id:08X}" if frame0.is_extended else f"0x{frame0.arbitration_id:03X}"
                ext_lbl = "29-bit" if frame0.is_extended else "11-bit"
                if frame0.is_remote:
                    self.lbl_preview_status.setText(f"✅ Poprawna ramka RTR: ID {id_fmt} ({ext_lbl}), DLC: {frame0.dlc}")
                else:
                    data_hex = frame0.data.hex(' ').upper()
                    if frame0.is_fd:
                        brs_str = " [FD+BRS]" if frame0.bitrate_switch else " [FD]"
                        if s0.upper().startswith("TLV#") or can_mode == CAN_MODE_TLV:
                            tlv_info = f" | {OtAppMsgTlv.unpack(frame0.data)[0].format_display()}" if len(frame0.data) >= TLV_HEADER_SIZE else ""
                            self.lbl_preview_status.setText(f"✅ Poprawna ramka CAN FD TLV: ID {id_fmt} ({ext_lbl}), DLC: {frame0.dlc} B{brs_str}{tlv_info}")
                        else:
                            self.lbl_preview_status.setText(f"✅ Poprawna ramka CAN FD: ID {id_fmt} ({ext_lbl}), DLC: {frame0.dlc} B{brs_str}  |  Dane: [{data_hex}]")
                    else:
                        self.lbl_preview_status.setText(f"✅ Poprawna ramka Klasyczny CAN 2.0: ID {id_fmt} ({ext_lbl}), DLC: {frame0.dlc} B  |  Dane: [{data_hex}]")
                self.lbl_preview_status.setStyleSheet("color: #69db7c; font-size: 11px; font-weight: bold;")
            except (CanFrameError, Exception) as e:
                err_msg = str(e)
                self.lbl_preview_status.setText(f"⚠️ {err_msg}")
                self.lbl_preview_status.setStyleSheet("color: #ff6b6b; font-size: 11px; font-weight: bold;")

                # Sprawdź błędy CAN i zaoferuj dedykowany autofix
                if "Klasyczny CAN 2.0" in err_msg and "CAN FD" in err_msg:
                    if self.can_fd_capable:
                        self.autofix_action = "switch_to_fd"
                        self.btn_autofix.setText("⚡ Przełącz na CAN FD z BRS")
                        self.btn_autofix.setVisible(True)
                    else:
                        self.autofix_action = "trim_to_8b"
                        self.btn_autofix.setText("⚡ Przytnij dane do 8 bajtów")
                        self.btn_autofix.setVisible(True)
                elif "##" in err_msg:
                    self.autofix_action = "strip_double_hash"
                    self.btn_autofix.setText("⚡ Usuń '##' (zamień na '#')")
                    self.btn_autofix.setVisible(True)
                else:
                    # Sprawdź, czy błąd wynika z nieparzystej liczby cyfr powiązanej z {CNT...}
                    m_tok = re.search(r'\{(CNT|SEQ):([0-9a-fA-F]+)-([0-9a-fA-F]+):([a-zA-Z0-9]+)\}', raw_text)
                    if m_tok:
                        c_name, r_min, r_max, r_fmt = m_tok.groups()
                        if "x" in r_fmt.lower() and len(r_min) == 1 and (len(r_max) == 1 or r_max in ("15", "F", "f")):
                            max_hex = "0F" if r_max in ("15", "F", "f") else f"{int(r_max, 16):02X}"
                            min_hex = f"{int(r_min, 16):02X}"
                            self.autofix_target = m_tok.group(0)
                            self.autofix_replacement = f"{{{c_name}:{min_hex}-{max_hex}:{r_fmt}}}"
                            self.btn_autofix.setText(f"⚡ Napraw: zamień na {self.autofix_replacement}")
                            self.btn_autofix.setVisible(True)
        elif ptype == "HEX":
            compact = re.sub(r'[\s.:_\-]', '', s0)
            if compact and not _HEX_RE.match(compact):
                self.lbl_preview_status.setText("⚠️ Ciąg zawiera znaki spoza szesnastkowego HEX!")
                self.lbl_preview_status.setStyleSheet("color: #ff6b6b; font-size: 11px; font-weight: bold;")
            elif len(compact) % 2 != 0:
                self.lbl_preview_status.setText(f"⚠️ Nieparzysta liczba cyfr HEX ({len(compact)} cyfr). W trybie HEX każdy bajt to 2 cyfry!")
                self.lbl_preview_status.setStyleSheet("color: #ff6b6b; font-size: 11px; font-weight: bold;")
            else:
                byte_cnt = len(compact) // 2
                self.lbl_preview_status.setText(f"✅ Poprawny ciąg BINARY HEX ({byte_cnt} bajtów).")
                self.lbl_preview_status.setStyleSheet("color: #69db7c; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_preview_status.setText("✅ Poprawna komenda tekstowa ASCII.")
            self.lbl_preview_status.setStyleSheet("color: #69db7c; font-size: 11px; font-weight: bold;")

    def apply_autofix(self):
        if getattr(self, "autofix_action", None) == "switch_to_fd":
            idx = self.combo_can_mode.findData(CAN_MODE_FD_BRS)
            if idx >= 0:
                self.combo_can_mode.setCurrentIndex(idx)
            self.autofix_action = None
            self.btn_autofix.setVisible(False)
            self.validate_and_preview()
            return
        elif getattr(self, "autofix_action", None) == "strip_double_hash":
            w = self.get_active_tx_widget()
            if isinstance(w, ClickToClearLineEdit):
                w.setText(w.text().replace("##1#", "#").replace("##0#", "#").replace("##", "#"))
            elif isinstance(w, ClickToClearPlainTextEdit):
                w.setPlainText(w.toPlainText().replace("##1#", "#").replace("##0#", "#").replace("##", "#"))
            self.autofix_action = None
            self.btn_autofix.setVisible(False)
            self.validate_and_preview()
            return
        elif getattr(self, "autofix_action", None) == "trim_to_8b":
            w = self.get_active_tx_widget()
            if isinstance(w, ClickToClearLineEdit):
                new_txt = convert_can_frame_text(w.text().strip(), CAN_MODE_CLASSIC)
                if new_txt:
                    w.setText(new_txt)
            self.autofix_action = None
            self.btn_autofix.setVisible(False)
            self.validate_and_preview()
            return

        if not self.autofix_target or not self.autofix_replacement:
            return
        w = self.get_active_tx_widget()
        if isinstance(w, ClickToClearLineEdit):
            w.setText(w.text().replace(self.autofix_target, self.autofix_replacement))
        elif isinstance(w, ClickToClearPlainTextEdit):
            w.setPlainText(w.toPlainText().replace(self.autofix_target, self.autofix_replacement))
        elif self.combo_type.currentText() == "step":
            row = self.table_steps.currentRow()
            if row < 0 and self.table_steps.rowCount() > 0:
                row = 0
            if row >= 0:
                item = self.table_steps.item(row, 1)
                if item:
                    item.setText(item.text().replace(self.autofix_target, self.autofix_replacement))
        self.validate_and_preview()

    def accept(self):
        if self.delete_requested:
            super().accept()
            return
        raw_text = self.get_current_tx_text()
        is_can = (self.combo_payload_type.currentText() == "CAN") or self.is_can_mode
        if raw_text and is_can:
            dummy = {}
            s0 = evaluate_dynamic_tokens(raw_text, dummy, "check")
            can_mode = self.combo_can_mode.currentData() if hasattr(self, 'combo_can_mode') else CAN_MODE_AUTO
            try:
                parse_can_frame(s0, can_mode=can_mode)
            except (CanFrameError, Exception) as e:
                ret = QMessageBox.warning(
                    self, 
                    "Ostrzeżenie o błędzie składni CAN", 
                    f"Wprowadzona ramka zawiera błąd składni:\n\n{e}\n\nCzy na pewno chcesz zapisać mimo błędu?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if ret != QMessageBox.StandardButton.Yes:
                    return
        super().accept()

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
            "payload_type": "CAN" if self.is_can_mode else self.combo_payload_type.currentText(),
            "can_mode": self.combo_can_mode.currentData() if hasattr(self, 'combo_can_mode') else CAN_MODE_AUTO
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
        elif t == "query":
            res["tx"] = self.le_query_tx.text().strip()
            res["rx_pattern"] = self.le_query_rx.text().strip()
            res["timeout"] = self.spin_query_timeout.value()
        elif t == "step":
            steps_data = []
            for r in range(self.table_steps.rowCount()):
                lbl_item = self.table_steps.item(r, 0)
                tx_item = self.table_steps.item(r, 1)
                lbl = lbl_item.text().strip() if lbl_item else f"Krok {r+1}"
                tx = tx_item.text().strip() if tx_item else ""
                steps_data.append({"label": lbl, "tx": tx})
            res["steps"] = steps_data
            
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
        self.combo_transport.addItem(TRANSPORT_LABELS[TRANSPORT_CANDLE], TRANSPORT_CANDLE)
        cur_transport = self.data.get("transport", TRANSPORT_SERIAL)
        idx_t = self.combo_transport.findData(cur_transport)
        self.combo_transport.setCurrentIndex(idx_t if idx_t >= 0 else 0)
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
        self.lbl_can_bitrate = QLabel("Bitrate CAN (Nominal):")
        can_form.addRow(self.lbl_can_bitrate, self.combo_can_bitrate)

        # Opcje CAN FD (tylko dla candleLight)
        self.can_fd_frame = QWidget()
        can_fd_layout = QFormLayout(self.can_fd_frame)
        can_fd_layout.setContentsMargins(0, 0, 0, 0)
        self.cb_can_fd = QCheckBox("Włącz CAN FD (faza szybkich danych BRS, do 64B)")
        self.cb_can_fd.setChecked(bool(self.data.get("can_fd_enabled", True)))
        can_fd_layout.addRow(self.cb_can_fd)

        self.combo_can_data_bitrate = QComboBox()
        cur_dbr = self.data.get("can_data_bitrate", DEFAULT_CAN_DATA_BITRATE)
        for dbr in CAN_DATA_BITRATES:
            self.combo_can_data_bitrate.addItem(f"{format_bitrate_label(dbr)} ({dbr} bps)", dbr)
            if dbr == cur_dbr:
                self.combo_can_data_bitrate.setCurrentIndex(self.combo_can_data_bitrate.count() - 1)
        self.lbl_data_bitrate = QLabel("Data Bitrate (CAN FD):")
        can_fd_layout.addRow(self.lbl_data_bitrate, self.combo_can_data_bitrate)

        self.combo_can_sample_point = QComboBox()
        sp_options = [
            ("80.0% — Standard CiA 601-1 (Zalecany dla CAN FD)", 80.0),
            ("75.0% — Długie linie / Większe opóźnienia", 75.0),
            ("70.0% — Alternatywny", 70.0),
            ("87.5% — Klasyczny CAN (Wysoki)", 87.5),
        ]
        cur_sp = float(self.data.get("can_data_sample_point", 80.0))
        for label, val in sp_options:
            self.combo_can_sample_point.addItem(label, val)
            if abs(val - cur_sp) < 0.1:
                self.combo_can_sample_point.setCurrentIndex(self.combo_can_sample_point.count() - 1)
        self.lbl_sample_point = QLabel("Sample Point (CiA 601-1):")
        can_fd_layout.addRow(self.lbl_sample_point, self.combo_can_sample_point)

        def on_fd_toggled(checked):
            self.combo_can_data_bitrate.setEnabled(checked)
            self.combo_can_sample_point.setEnabled(checked)
            self.lbl_data_bitrate.setEnabled(checked)
            self.lbl_sample_point.setEnabled(checked)

        self.cb_can_fd.toggled.connect(on_fd_toggled)
        on_fd_toggled(self.cb_can_fd.isChecked())

        can_form.addRow(self.can_fd_frame)

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
            cur_trans = self.combo_transport.currentData()
            is_can = is_can_transport(cur_trans)
            is_candle = (cur_trans == TRANSPORT_CANDLE)
            self.can_group.setVisible(is_can)
            self.serial_group.setVisible(not is_can)
            if hasattr(self, "can_fd_frame"):
                self.can_fd_frame.setVisible(is_candle)
            else:
                self.cb_can_fd.setVisible(is_candle)
                self.combo_can_data_bitrate.setVisible(is_candle)
            self.lbl_can_bitrate.setText("Bitrate CAN (Nominal):" if is_candle else "Bitrate CAN:")

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
        trans = self.combo_transport.currentData()
        is_can = is_can_transport(trans)
        can_fd_on = bool(self.cb_can_fd.isChecked()) if trans == TRANSPORT_CANDLE else False
        dlg = ButtonEditDialog(self.data["buttons"][idx], self, is_can_mode=is_can, transport=trans, can_fd_enabled=can_fd_on)
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
            if is_can_transport(self.data["transport"]):
                self.data["can_bitrate"] = self.combo_can_bitrate.currentData()
                self.data["can_data_bitrate"] = self.combo_can_data_bitrate.currentData()
                if hasattr(self, "combo_can_sample_point"):
                    sp_val = float(self.combo_can_sample_point.currentData() or 80.0)
                    self.data["can_sample_point"] = sp_val
                    self.data["can_data_sample_point"] = sp_val
                self.data["can_fd_enabled"] = self.cb_can_fd.isChecked()
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
            
# ==========================================
# DIALOG KREATORA / NADAJNIKA CAN FD & TLV
# ==========================================
class CanFdTxDialog(QDialog):
    """Kreator i nadajnik ramek CAN / CAN FD oraz binarnej struktury ot_app_msg_tlv (<BH)."""
    def __init__(self, parent_tab, parent=None):
        super().__init__(parent)
        self.tab = parent_tab
        self.setWindowTitle("📦 Kreator i Nadajnik Ramek CAN FD / TLV")
        self.resize(540, 480)
        
        self.timer_cyclic = QTimer(self)
        self.timer_cyclic.timeout.connect(self._send_cyclic_tick)

        layout = QVBoxLayout(self)

        # Parametry nagłówka CAN
        hdr_box = QFrame()
        hdr_box.setStyleSheet("QFrame { background-color: #202024; border: 1px solid #323238; border-radius: 4px; padding: 6px; }")
        hdr_vbox = QVBoxLayout(hdr_box)
        hdr_form = QFormLayout()

        self.edit_id = QLineEdit("321")
        self.edit_id.setPlaceholderText("np. 321 (11-bit) lub 18FEF100 (29-bit)")
        hdr_form.addRow("CAN ID (Hex):", self.edit_id)

        flags_layout = QHBoxLayout()
        self.cb_ext = QCheckBox("ID Rozszerzone (29-bit)")
        self.cb_fd = QCheckBox("CAN FD")
        self.cb_fd.setChecked(True)
        self.cb_brs = QCheckBox("BRS (Fast Data Bitrate)")
        self.cb_brs.setChecked(True)
        flags_layout.addWidget(self.cb_ext)
        flags_layout.addWidget(self.cb_fd)
        flags_layout.addWidget(self.cb_brs)
        hdr_form.addRow("Flagi ramki:", flags_layout)

        hdr_vbox.addLayout(hdr_form)
        layout.addWidget(hdr_box)

        # Format danych (Payload)
        data_box = QFrame()
        data_box.setStyleSheet("QFrame { background-color: #202024; border: 1px solid #323238; border-radius: 4px; padding: 6px; }")
        data_vbox = QVBoxLayout(data_box)

        mode_layout = QHBoxLayout()
        self.radio_tlv = QRadioButton("Struktura binarna TLV (ot_app_msg_tlv: <BH, 64B)")
        self.radio_raw = QRadioButton("Surowe dane Hex (do 64 bajtów)")
        self.radio_tlv.setChecked(True)
        mode_layout.addWidget(self.radio_tlv)
        mode_layout.addWidget(self.radio_raw)
        data_vbox.addLayout(mode_layout)

        # Panel TLV
        self.tlv_widget = QWidget()
        tlv_form = QFormLayout(self.tlv_widget)
        self.edit_tlv_type = QLineEdit("0xA5")
        self.edit_tlv_type.setPlaceholderText("np. 0xA5 lub 165")
        self.edit_tlv_val = QLineEdit("SerialCommander CAN FD TLV payload")
        self.edit_tlv_val.setPlaceholderText("Tekst wartości do spakowania w TLV")
        tlv_form.addRow("Typ TLV (Type):", self.edit_tlv_type)
        tlv_form.addRow("Wartość TLV (Value):", self.edit_tlv_val)
        data_vbox.addWidget(self.tlv_widget)

        # Panel RAW HEX
        self.raw_widget = QWidget()
        raw_form = QFormLayout(self.raw_widget)
        self.edit_raw_hex = QLineEdit("11 22 33 44 55 66 77 88 AA BB CC DD EE FF 00 11")
        self.edit_raw_hex.setPlaceholderText("Bajty hex oddzielone spacjami")
        raw_form.addRow("Dane Hex:", self.edit_raw_hex)
        data_vbox.addWidget(self.raw_widget)
        self.raw_widget.hide()

        def on_mode_change():
            is_tlv = self.radio_tlv.isChecked()
            self.tlv_widget.setVisible(is_tlv)
            self.raw_widget.setVisible(not is_tlv)
            self.update_preview()

        self.radio_tlv.toggled.connect(on_mode_change)
        layout.addWidget(data_box)

        # Podgląd ramki
        prev_box = QFrame()
        prev_box.setStyleSheet("QFrame { background-color: #1a1a1e; border: 1px solid #2e2e34; border-radius: 4px; padding: 6px; }")
        prev_vbox = QVBoxLayout(prev_box)
        prev_hdr = QLabel("Podgląd generowanej ramki:")
        prev_hdr.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        self.lbl_preview = QLabel("...")
        self.lbl_preview.setWordWrap(True)
        self.lbl_preview.setStyleSheet("font-family: monospace; color: #ffd43b; font-size: 11px;")
        prev_vbox.addWidget(prev_hdr)
        prev_vbox.addWidget(self.lbl_preview)
        layout.addWidget(prev_box)

        # Nadawanie
        tx_layout = QHBoxLayout()
        self.btn_send_once = QPushButton("⚡ Wyślij raz")
        self.btn_send_once.setStyleSheet("background-color: #228be6; color: white; font-weight: bold; padding: 6px 12px;")
        self.btn_send_once.clicked.connect(self.send_once)

        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(10, 10000)
        self.spin_interval.setValue(100)
        self.spin_interval.setSuffix(" ms")

        self.btn_send_cyclic = QPushButton("🔁 Nadawaj cyklicznie")
        self.btn_send_cyclic.setStyleSheet("background-color: #2b8a3e; color: white; font-weight: bold; padding: 6px 12px;")
        self.btn_send_cyclic.clicked.connect(self.toggle_cyclic)

        self.btn_copy_cmd = QPushButton("📋 Kopiuj polecenie")
        self.btn_copy_cmd.clicked.connect(self.copy_command)

        tx_layout.addWidget(self.btn_send_once)
        tx_layout.addWidget(QLabel("Interwał:"))
        tx_layout.addWidget(self.spin_interval)
        tx_layout.addWidget(self.btn_send_cyclic)
        tx_layout.addWidget(self.btn_copy_cmd)
        layout.addLayout(tx_layout)

        self.edit_id.textChanged.connect(self.update_preview)
        self.edit_tlv_type.textChanged.connect(self.update_preview)
        self.edit_tlv_val.textChanged.connect(self.update_preview)
        self.edit_raw_hex.textChanged.connect(self.update_preview)
        self.cb_ext.toggled.connect(self.update_preview)
        self.cb_fd.toggled.connect(self.update_preview)
        self.cb_brs.toggled.connect(self.update_preview)

        self.update_preview()

    def build_frame_command(self) -> str:
        raw_id = self.edit_id.text().strip()
        clean_id = (raw_id[2:] if raw_id.lower().startswith("0x") else raw_id) or "321"

        if self.radio_tlv.isChecked():
            raw_type = self.edit_tlv_type.text().strip() or "0xA5"
            val_text = self.edit_tlv_val.text()
            return f"TLV#{clean_id}#{raw_type}#{val_text}"
        else:
            raw_hex = self.edit_raw_hex.text().strip()
            if self.cb_fd.isChecked():
                brs_ch = "1" if self.cb_brs.isChecked() else "0"
                return f"{clean_id}##{brs_ch}#{raw_hex}"
            else:
                return f"{clean_id}#{raw_hex}"

    def update_preview(self):
        try:
            cmd = self.build_frame_command()
            frame = parse_can_frame(cmd)
            display_text = frame.to_display()
            self.lbl_preview.setText(f"Polecenie: {cmd}\nRamka:     {display_text}\nRozmiar:   {frame.dlc}B (FD: {frame.is_fd}, BRS: {frame.bitrate_switch})")
        except Exception as e:
            self.lbl_preview.setText(f"[Błąd składni]: {e}")

    def send_once(self):
        cmd = self.build_frame_command()
        if self.tab:
            self.tab.send_payload(cmd, source_name="CAN FD TX", payload_type="CAN")

    def _send_cyclic_tick(self):
        self.send_once()

    def toggle_cyclic(self):
        if self.timer_cyclic.isActive():
            self.timer_cyclic.stop()
            self.btn_send_cyclic.setText("🔁 Nadawaj cyklicznie")
            self.btn_send_cyclic.setStyleSheet("background-color: #2b8a3e; color: white; font-weight: bold; padding: 6px 12px;")
        else:
            self.send_once()
            self.timer_cyclic.start(self.spin_interval.value())
            self.btn_send_cyclic.setText("⏹ Zatrzymaj")
            self.btn_send_cyclic.setStyleSheet("background-color: #e67700; color: white; font-weight: bold; padding: 6px 12px;")

    def copy_command(self):
        from PyQt6.QtWidgets import QApplication
        cmd = self.build_frame_command()
        QApplication.clipboard().setText(cmd)
        if self.tab:
            self.tab.log_info(f"Skopiowano polecenie CAN FD do schowka: {cmd}")

    def closeEvent(self, event):
        self.timer_cyclic.stop()
        super().closeEvent(event)

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
            
        self.button_counters = {}
        self.button_step_indices = [0] * 10
        self.active_queries = {}
        self.query_restore_timers = [QTimer(self) for _ in range(10)]

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
        
        self.btn_stop_triggers = QPushButton("⏹ Stop")
        self.btn_stop_triggers.setFixedHeight(22)
        self.btn_stop_triggers.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop_triggers.setToolTip("Zatrzymaj wszystkie aktywne pętle nadawania (Triggery)")
        self.btn_stop_triggers.setStyleSheet("QPushButton { padding: 1px 6px; font-size: 11px; color: #fa5252; border: 1px solid #fa5252; font-weight: bold; } QPushButton:hover { background-color: #fa5252; color: white; }")
        self.btn_stop_triggers.clicked.connect(self.stop_all_triggers)
        self.btn_stop_triggers.hide()
        left_header_layout.addWidget(self.btn_stop_triggers)

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

        self.btn_can_fd_builder = QPushButton("📦 TLV / CAN FD")
        self.btn_can_fd_builder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_can_fd_builder.setStyleSheet("background-color: #2b8a3e; color: white; font-weight: bold; border: none; padding: 4px 8px;")
        self.btn_can_fd_builder.setToolTip("Otwórz kreator i nadajnik ramek CAN FD oraz struktur binarnych TLV")
        self.btn_can_fd_builder.clicked.connect(self.open_can_fd_builder)
        self.btn_can_fd_builder.hide()
        
        cmd_layout.addWidget(self.cmd_input, stretch=1)
        cmd_layout.addWidget(self.btn_can_fd_builder)
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
        is_can = is_can_transport(self.app_config.get("transport"))
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
        idx = self.port_combo.currentIndex()
        is_busy = bool(self.port_combo.itemData(idx, Qt.ItemDataRole.UserRole + 2)) if idx >= 0 else False
        dot = "🟢" if connected else ("🔒" if is_busy else "⚪")
        port = self.get_selected_port_device() or "Brak portu"
        cfg = self.combo_cfg.currentText() or "default.json"
        side_label = "LEWA" if self.panel_side == "left" else "PRAWA"
        
        self.lbl_side_badge.setText(f"[{side_label}]")
        is_can = is_can_transport(self.app_config.get("transport"))
        if is_can:
            trans = self.app_config.get("transport")
            br_label = format_bitrate_label(self.app_config.get("can_bitrate", DEFAULT_CAN_BITRATE))
            lo_tag = " [LO]" if self.app_config.get("can_listen_only", False) else ""
            if trans == TRANSPORT_CANDLE:
                dbr_label = format_bitrate_label(self.app_config.get("can_data_bitrate", DEFAULT_CAN_DATA_BITRATE))
                fd_on = self.app_config.get("can_fd_enabled", True)
                fd_tag = f"/{dbr_label}" if fd_on else " (2.0)"
                mode_tag = f" · CAN FD {br_label}{fd_tag}{lo_tag}"
            else:
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
    def open_can_fd_builder(self):
        trans = self.app_config.get("transport", TRANSPORT_SERIAL)
        if trans != TRANSPORT_CANDLE:
            QMessageBox.information(
                self, "Informacja",
                "Kreator TLV / CAN FD jest dostępny wyłącznie dla adaptera candleLight w trybie CAN FD.\n\n"
                f"Bieżący profil używa: {TRANSPORT_LABELS.get(trans, trans)}."
            )
            return
        dlg = CanFdTxDialog(self, self)
        dlg.exec()

    def apply_transport_ui(self):
        trans = self.app_config.get("transport", TRANSPORT_SERIAL)
        is_can = is_can_transport(trans)
        is_candle = (trans == TRANSPORT_CANDLE)
        
        self.lbl_baud.setText("Nominal:" if is_candle else ("Bitrate:" if is_can else "Baud:"))
        self.baud_combo.blockSignals(True)
        self.baud_combo.clear()
        
        if is_can:
            current_br = self.app_config.get("can_bitrate", DEFAULT_CAN_BITRATE)
            for br in CAN_BITRATES:
                label = f"{format_bitrate_label(br)}"
                self.baud_combo.addItem(label, br)
                if br == current_br:
                    self.baud_combo.setCurrentIndex(self.baud_combo.count() - 1)
            self.baud_combo.setToolTip("Prędkość nominalna magistrali CAN" if is_candle else "Prędkość transmisji magistrali CAN")
            
            self.lbl_rx.hide()
            self.radio_ascii.hide()
            self.radio_binary.hide()
            self.combo_cmd_format.hide()
            self.combo_eol.hide()
            # Przycisk TLV / CAN FD dostępny WYŁĄCZNIE dla candleLight w trybie CAN FD:
            is_candle_fd = is_candle and bool(self.app_config.get("can_fd_enabled", True))
            if hasattr(self, "btn_can_fd_builder"):
                self.btn_can_fd_builder.setVisible(is_candle_fd)

            if is_candle:
                self.cmd_input.setPlaceholderText("CAN FD: 321#01 02, 321##1#01 02, TLV#321#0xA5#Tekst (Enter = wyślij)...")
            else:
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
            if hasattr(self, "btn_can_fd_builder"):
                self.btn_can_fd_builder.hide()
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
        is_can = is_can_transport(self.app_config.get("transport"))
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
        self.cb_watch_print.setChecked(self.app_config.get("watch_print_in_console", True))
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
        idx = self.port_combo.currentIndex()
        is_busy = bool(self.port_combo.itemData(idx, Qt.ItemDataRole.UserRole + 2)) if idx >= 0 else False
        dot = "🟢" if connected else ("🔒" if is_busy else "⚪")
        port = self.get_selected_port_device() or "Brak"
        cfg = self.combo_cfg.currentText() or "default.json"
        is_can = is_can_transport(self.app_config.get("transport"))
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
        for t in self.query_restore_timers:
            t.stop()
        for q in self.active_queries.values():
            q_timer = q.get("timer")
            if q_timer:
                q_timer.stop()
        self.active_queries.clear()
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
        is_can = is_can_transport(self.app_config.get("transport"))
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
        trans = self.app_config.get("transport", TRANSPORT_SERIAL)
        is_can = is_can_transport(trans)
        can_fd_on = bool(self.app_config.get("can_fd_enabled", True))
        dialog = ButtonEditDialog(btn_data, self, is_can_mode=is_can, transport=trans, can_fd_enabled=can_fd_on)
        
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
        if self.query_restore_timers[idx].isActive():
            self.query_restore_timers[idx].stop()
        if idx in self.active_queries:
            q_timer = self.active_queries[idx].get("timer")
            if q_timer:
                q_timer.stop()
            del self.active_queries[idx]

        if btn_cfg.get("is_used", False):
            b_type = btn_cfg.get("type", "toggle")
            name = btn_cfg.get("name", f"Btn {idx+1}")
            is_can = is_can_transport(self.app_config.get("transport"))
            p_type = btn_cfg.get("payload_type", "CAN" if is_can else "ASCII")
            
            if is_can:
                trans = self.app_config.get("transport", TRANSPORT_SERIAL)
                if trans == TRANSPORT_SLCAN:
                    p_type = "CAN 2.0"
                else:
                    c_mode = btn_cfg.get("can_mode", CAN_MODE_AUTO)
                    mode_str = {
                        CAN_MODE_CLASSIC: "CAN 2.0",
                        CAN_MODE_FD_BRS: "CAN FD+BRS",
                        CAN_MODE_FD_NO_BRS: "CAN FD",
                        CAN_MODE_TLV: "CAN FD TLV",
                        CAN_MODE_AUTO: "CAN Auto",
                    }.get(c_mode, "CAN")
                    p_type = mode_str

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

            elif b_type == "query":
                btn.setText(f"❓ {name}")
                btn.setStyleSheet(self.get_btn_style("#d97706"))
                btn.setToolTip(f"Typ: QUERY ({p_type})\nTX: {btn_cfg.get('tx')}\nOczekiwane RX: {btn_cfg.get('rx_pattern')}\nTimeout: {btn_cfg.get('timeout', 1000)} ms\n\n(Klik: Wyślij zapytanie | PPM: Edytuj)")
                btn.clicked.connect(lambda checked, i=idx: self.on_query_clicked(i))
                
            elif b_type == "step":
                steps = btn_cfg.get("steps", [])
                step_idx = self.button_step_indices[idx] % max(1, len(steps))
                cur_step = steps[step_idx] if steps else {"label": "Brak kroków", "tx": ""}
                step_label = cur_step.get("label", f"Krok {step_idx+1}")
                btn.setText(f"🪜 {name}: {step_label}")
                btn.setStyleSheet(self.get_btn_style("#1098ad"))
                btn.setToolTip(f"Typ: STEP ({p_type})\nKrok: {step_idx+1}/{max(1, len(steps))} ({step_label})\nTX: {cur_step.get('tx', '')}\n\n(Klik: Wyślij i przełącz krok | PPM: Edytuj)")
                btn.clicked.connect(lambda checked, i=idx: self.on_step_clicked(i))
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
        is_can = is_can_transport(self.app_config.get("transport"))
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

        trans = self.app_config.get("transport") if self.app_config else None
        if trans == TRANSPORT_CANDLE:
            candle_devs = list_candle_devices()
            current_devices = {item[0] for item in candle_devs}
            new_ports = set()
            busy_ports = []
            for item in candle_devs:
                ch_id, label = item[0], item[1]
                is_busy = getattr(item, "is_busy", False)
                if is_busy:
                    busy_ports.append(ch_id)
                disp_text = f"{ch_id} 🔒" if is_busy else ch_id
                self.port_combo.addItem(disp_text)
                idx = self.port_combo.count() - 1
                self.port_combo.setItemData(idx, ch_id, Qt.ItemDataRole.UserRole)
                self.port_combo.setItemData(idx, label, Qt.ItemDataRole.UserRole + 1)
                self.port_combo.setItemData(idx, is_busy, Qt.ItemDataRole.UserRole + 2)
                tooltip = f"{label}\nUrządzenie jest zajęte przez inną aplikację (brak dostępu WinUSB / Access Denied)." if is_busy else label
                self.port_combo.setItemData(idx, tooltip, Qt.ItemDataRole.ToolTipRole)

            self.port_combo._apply_item_styles()

            saved_port = self.app_config.get("port") if self.app_config else None
            if saved_port:
                for i in range(self.port_combo.count()):
                    if self.port_combo.itemData(i, Qt.ItemDataRole.UserRole) == saved_port:
                        self.port_combo.setCurrentIndex(i)
                        break
            self.port_combo.blockSignals(False)
            
            free_count = len(candle_devs) - len(busy_ports)
            if not candle_devs:
                self.log_info("Nie znaleziono żadnych urządzeń candleLight (WinUSB).")
            elif busy_ports and free_count == 0:
                self.log_info(f"⚠️ Wykryto interfejs candleLight ({', '.join(busy_ports)}), ale jest ZAJĘTY przez inną aplikację (Access Denied).")
            elif busy_ports:
                self.log_info(f"Znaleziono interfejsy candleLight: {free_count} wolny(ch), {len(busy_ports)} zajęty(ch) przez inny program.")
            else:
                self.log_info(f"Znaleziono {len(candle_devs)} interfejs(ów) candleLight.")
            self.update_header_title()
            self.tab_state_changed.emit()
            return

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

            trans = self.app_config.get("transport", TRANSPORT_SERIAL)
            is_can = is_can_transport(trans)

            if is_can:
                if not CAN_AVAILABLE:
                    QMessageBox.critical(
                        self, "Brak biblioteki python-can",
                        f"Tryb CAN wymaga biblioteki python-can.\n{CAN_IMPORT_ERROR}\n\nZainstaluj ją poleceniem:\npip install python-can"
                    )
                    return

                if trans == TRANSPORT_CANDLE:
                    idx = self.port_combo.currentIndex()
                    is_busy = bool(self.port_combo.itemData(idx, Qt.ItemDataRole.UserRole + 2)) if idx >= 0 else False
                    if is_busy:
                        QMessageBox.warning(
                            self, "Interfejs zajęty",
                            f"Urządzenie candleLight ({selected_port}) jest obecnie używane przez inną aplikację "
                            f"(np. HUD ECU Hacker, inny terminal lub proces w tle) i nie zezwala na współdzielenie dostępu WinUSB.\n\n"
                            f"Zamknij połączenie w tamtym programie, kliknij 'Odśwież' (⟳) i spróbuj połączyć się ponownie."
                        )
                        self.log_info(f"❌ Połączenie anulowane: interfejs {selected_port} jest zajęty przez inną aplikację.")
                        return

                try:
                    bitrate_data = self.baud_combo.currentData()
                    selected_bitrate = int(bitrate_data if bitrate_data is not None else self.app_config.get("can_bitrate", DEFAULT_CAN_BITRATE))
                except (TypeError, ValueError):
                    selected_bitrate = DEFAULT_CAN_BITRATE

                listen_only = bool(self.app_config.get("can_listen_only", False))
                data_bitrate = int(self.app_config.get("can_data_bitrate", DEFAULT_CAN_DATA_BITRATE))
                fd_enabled = bool(self.app_config.get("can_fd_enabled", True))

                safe_port = selected_port.replace(":", "_").replace("/", "_")
                if os.path.basename(self.current_cfg_file) == "default.json":
                    new_name = f"{safe_port}_CANFD.json" if trans == TRANSPORT_CANDLE else f"{safe_port}_CAN.json"
                    new_path = os.path.join(CFG_DIR, new_name)
                    self.current_cfg_file = new_path
                    self.save_current_settings_to_config(force=True)
                    self.refresh_configs_list(select_file=new_name)

                sample_point = float(self.app_config.get("can_sample_point", 80.0))
                data_sample_point = float(self.app_config.get("can_data_sample_point", 80.0))

                lo_tag = " [Listen-only]" if listen_only else ""
                if trans == TRANSPORT_CANDLE:
                    fd_tag = f" / Data {format_bitrate_label(data_bitrate)} (SP: {data_sample_point:.0f}%)" if fd_enabled else " (2.0)"
                    self.log_info(f"Łączenie z candleLight ({selected_port}) — Nominal {format_bitrate_label(selected_bitrate)}{fd_tag}{lo_tag}...")
                else:
                    self.log_info(f"Łączenie z adapterem CANable (slcan) na {selected_port} ({format_bitrate_label(selected_bitrate)}{lo_tag})...")
                self.save_current_settings_to_config(force=False)

                self.last_can_timestamps.clear()
                self._unpinned_can_ids.clear()
                self.worker = CanWorker(selected_port, selected_bitrate, listen_only=listen_only,
                                        interface=trans, data_bitrate=data_bitrate, fd=fd_enabled,
                                        sample_point=sample_point, data_sample_point=data_sample_point)
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
        is_can = is_can_transport(self.app_config.get("transport"))
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

    def resolve_dynamic_tokens(self, text: str, btn_idx: int = -1) -> str:
        return evaluate_dynamic_tokens(text, self.button_counters, btn_idx)

    def send_payload(self, payload_str, source_name="Manual", show_marker=False, payload_type="ASCII", btn_idx=-1):
        if not self.worker or not self.worker.is_running:
            self.log_info(f"Brak aktywnego połączenia. Odrzucono: {source_name}")
            return

        scope_id = btn_idx if btn_idx >= 0 else source_name
        payload_str = evaluate_dynamic_tokens(payload_str, self.button_counters, scope_id)

        marker_text = source_name if show_marker else ""
        is_can = is_can_transport(self.app_config.get("transport"))

        if is_can or str(payload_type).upper() == "CAN":
            can_mode = CAN_MODE_AUTO
            if 0 <= btn_idx < len(self.app_config.get("buttons", [])):
                can_mode = self.app_config["buttons"][btn_idx].get("can_mode", CAN_MODE_AUTO)
            try:
                frame = parse_can_frame(payload_str, can_mode=can_mode)
            except (CanFrameError, Exception) as e:
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
            is_can = is_can_transport(self.app_config.get("transport"))
            p_type = "CAN" if is_can else self.combo_cmd_format.currentText()
            self.send_payload(text, source_name="Terminal", payload_type=p_type, btn_idx=-1)
            self.cmd_input.clear()

    def on_toggle_clicked(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        is_currently_on = self.button_states[idx]
        payload = btn_cfg.get("tx_off", "") if is_currently_on else btn_cfg.get("tx_on", "")
        is_can = is_can_transport(self.app_config.get("transport"))
        default_ptype = "CAN" if is_can else "ASCII"
        p_type = btn_cfg.get("payload_type") or default_ptype
        self.send_payload(payload, source_name=btn_cfg['name'], show_marker=btn_cfg.get("show_marker", False), payload_type=p_type, btn_idx=idx)

    def on_push_clicked(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        is_can = is_can_transport(self.app_config.get("transport"))
        default_ptype = "CAN" if is_can else "ASCII"
        p_type = btn_cfg.get("payload_type") or default_ptype
        self.send_payload(btn_cfg.get("tx", ""), source_name=btn_cfg['name'], show_marker=btn_cfg.get("show_marker", False), payload_type=p_type, btn_idx=idx)

    def on_hold_pressed(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        is_can = is_can_transport(self.app_config.get("transport"))
        default_ptype = "CAN" if is_can else "ASCII"
        p_type = btn_cfg.get("payload_type") or default_ptype
        self.send_payload(btn_cfg.get("tx_on", ""), source_name=btn_cfg['name'], show_marker=btn_cfg.get("show_marker", False), payload_type=p_type, btn_idx=idx)

    def on_hold_released(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        is_can = is_can_transport(self.app_config.get("transport"))
        default_ptype = "CAN" if is_can else "ASCII"
        p_type = btn_cfg.get("payload_type") or default_ptype
        self.send_payload(btn_cfg.get("tx_off", ""), source_name=btn_cfg['name'], show_marker=btn_cfg.get("show_marker", False), payload_type=p_type, btn_idx=idx)

    def on_macro_clicked(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        sequence = btn_cfg.get("tx", "")
        seq_display = sequence.replace('\r', '').replace('\n', '; ')
        self.log_info(f"Start Macro: {btn_cfg['name']} -> {seq_display}")
        
        self.macro_runners = [r for r in self.macro_runners if r.isRunning()]
        
        is_can = is_can_transport(self.app_config.get("transport"))
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
        self.update_stop_triggers_button()
            
    def on_trigger_timeout(self, idx):
        if not self.worker or not self.worker.is_running:
            self.button_timers[idx].stop()
            self.button_states[idx] = False
            self.setup_button(idx)
            self.update_stop_triggers_button()
            return
            
        cfg = self.app_config["buttons"][idx]
        tx = cfg.get("tx", "")
        if tx:
            is_can = is_can_transport(self.app_config.get("transport"))
            default_ptype = "CAN" if is_can else "ASCII"
            p_type = cfg.get("payload_type") or default_ptype
            self.send_payload(tx, source_name=cfg.get('name', ''), show_marker=cfg.get("show_marker", False), payload_type=p_type, btn_idx=idx)

    def stop_all_triggers(self):
        stopped_count = 0
        for idx, timer in enumerate(self.button_timers):
            if timer.isActive():
                timer.stop()
                self.button_states[idx] = False
                stopped_count += 1
                btn = self.gui_buttons[idx]
                cfg = self.app_config["buttons"][idx]
                btn.setStyleSheet(self.get_btn_style("#607d8b"))
                btn.setText(f"🔁 {cfg.get('name', '')}")
        self.update_stop_triggers_button()
        if stopped_count > 0:
            self.log_info(f"Zatrzymano wszystkie aktywne pętle Trigger ({stopped_count}).")

    def update_stop_triggers_button(self):
        active_count = sum(1 for t in self.button_timers if t.isActive())
        if active_count > 0:
            self.btn_stop_triggers.setText(f"⏹ Stop ({active_count})")
            self.btn_stop_triggers.show()
        else:
            self.btn_stop_triggers.hide()

    def on_query_clicked(self, idx: int):
        if not self.worker or not self.worker.is_running:
            self.log_info("Brak aktywnego połączenia z portem.")
            return

        btn_cfg = self.app_config["buttons"][idx]
        tx_raw = btn_cfg.get("tx", "").strip()
        rx_pattern = btn_cfg.get("rx_pattern", "").strip()
        timeout_ms = int(btn_cfg.get("timeout", 1000))
        is_can = is_can_transport(self.app_config.get("transport"))
        default_ptype = "CAN" if is_can else "ASCII"
        p_type = btn_cfg.get("payload_type") or default_ptype

        if idx in self.active_queries:
            old_timer = self.active_queries[idx].get("timer")
            if old_timer:
                old_timer.stop()
            del self.active_queries[idx]
        if self.query_restore_timers[idx].isActive():
            self.query_restore_timers[idx].stop()

        self.send_payload(tx_raw, source_name=btn_cfg['name'], show_marker=btn_cfg.get("show_marker", False), payload_type=p_type, btn_idx=idx)

        btn = self.gui_buttons[idx]
        btn.setText(f"⏳ {btn_cfg['name']}...")
        btn.setStyleSheet(self.get_btn_style("#fcc419"))

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda i=idx: self.on_query_timeout(i))
        timer.start(timeout_ms)

        self.active_queries[idx] = {
            "timer": timer,
            "rx_pattern": rx_pattern,
            "payload_type": p_type,
            "start_time": time.time(),
            "timeout": timeout_ms,
            "tx": tx_raw
        }

    def on_query_timeout(self, idx: int):
        if idx not in self.active_queries:
            return
        q_data = self.active_queries.pop(idx)
        btn_cfg = self.app_config["buttons"][idx]
        btn = self.gui_buttons[idx]

        btn.setText(f"✖ {btn_cfg['name']} [TIMEOUT]")
        btn.setStyleSheet(self.get_btn_style("#f03e3e"))
        self.log_info(f"-> QUERY TIMEOUT: {btn_cfg['name']} (brak odpowiedzi na '{q_data.get('tx', '')}' w {q_data.get('timeout')} ms)")

        try:
            self.query_restore_timers[idx].disconnect()
        except TypeError:
            pass
        self.query_restore_timers[idx].timeout.connect(lambda i=idx: self.restore_query_button_visual(i))
        self.query_restore_timers[idx].start(1500)

    def handle_query_success(self, idx: int, match_preview: str):
        if idx not in self.active_queries:
            return
        q_data = self.active_queries.pop(idx)
        timer = q_data.get("timer")
        if timer:
            timer.stop()

        elapsed_ms = int((time.time() - q_data["start_time"]) * 1000)
        btn_cfg = self.app_config["buttons"][idx]
        btn = self.gui_buttons[idx]

        btn.setText(f"✔ {btn_cfg['name']} ({elapsed_ms}ms)")
        btn.setStyleSheet(self.get_btn_style("#37b24d"))
        self.log_info(f"-> Odpowiedź QUERY: {btn_cfg['name']} ODEBRANO w {elapsed_ms} ms [{match_preview}]")

        try:
            self.query_restore_timers[idx].disconnect()
        except TypeError:
            pass
        self.query_restore_timers[idx].timeout.connect(lambda i=idx: self.restore_query_button_visual(i))
        self.query_restore_timers[idx].start(1200)

    def restore_query_button_visual(self, idx: int):
        self.query_restore_timers[idx].stop()
        if idx not in self.active_queries:
            btn_cfg = self.app_config["buttons"][idx]
            if btn_cfg.get("is_used", False) and btn_cfg.get("type") == "query":
                btn = self.gui_buttons[idx]
                btn.setText(f"❓ {btn_cfg['name']}")
                btn.setStyleSheet(self.get_btn_style("#d97706"))

    def on_step_clicked(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        steps = btn_cfg.get("steps", [])
        if not steps:
            self.log_info(f"Brak zdefiniowanych kroków dla przycisku: {btn_cfg['name']}")
            return

        cur_idx = self.button_step_indices[idx] % len(steps)
        step = steps[cur_idx]
        tx_raw = step.get("tx", "")
        step_label = step.get("label", f"Krok {cur_idx+1}")

        is_can = is_can_transport(self.app_config.get("transport"))
        default_ptype = "CAN" if is_can else "ASCII"
        p_type = btn_cfg.get("payload_type") or default_ptype

        source_name = f"{btn_cfg['name']} [{step_label}]"
        self.send_payload(tx_raw, source_name=source_name, show_marker=btn_cfg.get("show_marker", False), payload_type=p_type, btn_idx=idx)

        # Przełączenie na kolejny krok
        next_idx = (cur_idx + 1) % len(steps)
        self.button_step_indices[idx] = next_idx
        next_step = steps[next_idx]
        next_label = next_step.get("label", f"Krok {next_idx+1}")

        btn = self.gui_buttons[idx]
        btn.setText(f"🪜 {btn_cfg['name']}: {next_label}")
        btn.setToolTip(f"Typ: STEP ({p_type})\nKolejny krok: {next_idx+1}/{len(steps)} ({next_label})\nTX: {next_step.get('tx', '')}\n\n(Klik: Wyślij krok | PPM: Edytuj)")

    def check_uart_queries(self, incoming: str, is_hex: bool = False):
        if not self.active_queries:
            return
        for i in list(self.active_queries.keys()):
            q_data = self.active_queries.get(i)
            if not q_data:
                continue
            rx_pat = q_data.get("rx_pattern", "").strip()
            if not rx_pat:
                continue
            p_type = q_data.get("payload_type", "ASCII")

            matched = False
            if p_type == "HEX" or is_hex:
                clean_incoming = incoming.replace(" ", "")
                clean_pat = rx_pat.replace(" ", "")
                if fnmatch.fnmatch(incoming, rx_pat) or fnmatch.fnmatch(clean_incoming, clean_pat):
                    matched = True
            else:
                if fnmatch.fnmatch(incoming, rx_pat) or rx_pat in incoming:
                    matched = True

            if matched:
                self.handle_query_success(i, incoming)

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
            "#e67700": "#d9480f", "#1098ad": "#0c8599",
            "#d97706": "#b45309", "#fcc419": "#fab005"
        }
        presseds = {
            "#37b24d": "#2b8a3e", "#f03e3e": "#c92a2a",
            "#228be6": "#1864ab", "#f59f00": "#e67700",
            "#9c27b0": "#7b1fa2", "#607d8b": "#455a64",
            "#e67700": "#c92a2a", "#1098ad": "#087f5b",
            "#d97706": "#92400e", "#fcc419": "#f59f00"
        }
        hover = hovers.get(bg_hex, bg_hex)
        pressed = presseds.get(bg_hex, bg_hex)
        text_color = "#18181b" if bg_hex == "#fcc419" else "white"
        
        return f"""
        QPushButton {{ background-color: {bg_hex}; color: {text_color}; font-weight: bold; font-size: 13px; border-radius: 5px; border: 1px solid rgba(0,0,0,0.3); }}
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
                        self.check_uart_queries(clean_line, is_hex=False)
                        
                stripped_buffer = self.text_buffer.strip()
                if stripped_buffer in [">", ">>"]:
                    self.log_rx(stripped_buffer)
                    self.check_uart_queries(stripped_buffer, is_hex=False)
                    self.text_buffer = ""
            except Exception as e:
                self.log_info(f"Błąd dekodowania: {e}")
        else:
            hex_str = data.hex(' ').upper()
            self.log_rx(hex_str)
            self.check_uart_queries(hex_str, is_hex=True)
        
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

            # 2b. Weryfikacja odpowiedzi dla przycisków typu QUERY (CAN)
            for i in list(self.active_queries.keys()):
                q_data = self.active_queries.get(i)
                if not q_data:
                    continue
                rx_pat = q_data.get("rx_pattern", "").strip()
                if not rx_pat:
                    continue
                can_pat = normalize_can_ack_pattern(rx_pat)
                if fnmatch.fnmatch(match_key, can_pat):
                    self.handle_query_success(i, frame.to_display())

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