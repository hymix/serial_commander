import sys
import json
import os
import argparse
import fnmatch
import serial
import serial.tools.list_ports
from datetime import datetime
from PyQt6.QtWidgets import (QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QStackedWidget, QApplication, QListWidget, QTabWidget, QMainWindow, QPushButton, 
                             QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, 
                             QComboBox, QLabel, QMessageBox, QLineEdit, 
                             QRadioButton, QScrollArea, QDialog, QFormLayout, 
                             QDialogButtonBox, QCheckBox, QInputDialog, QSpinBox, QTabWidget, QTabBar, QFileDialog)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSize, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QColor

CFG_DIR = "cfg"
APP_SETTINGS_FILE = os.path.join(CFG_DIR, "app_settings.json")
APP_VERSION = "1.0.0"

# ==========================================
# 1. KONFIGURACJA (ŁADOWANIE / ZAPIS)
# ==========================================
def load_app_settings():
    if os.path.exists(APP_SETTINGS_FILE):
        try:
            with open(APP_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
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

def get_default_config():
    config = {
        "port": "",
        "baudrate": 115200,
        "mode": "ASCII",
        "filters": [],
        "buttons": []
    }
    for i in range(10):
        config["buttons"].append({
            "id": i + 1,
            "is_used": False,
            "type": "toggle",          
            "name": f"Przycisk {i+1}",
            "tx": "FF FF",             
            "tx_on": "AA 01 00 55",    
            "tx_off": "AA 00 00 55",   
            "ack_on": "AA 01 00 55",   
            "ack_off": "AA 00 00 55"   
        })
    return config

def load_config(filepath):
    config = get_default_config()
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                config.update(loaded_config)
                # Upewnienie się, że stara konfiguracja ma klucz filters
                if "filters" not in config:
                    config["filters"] = []
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
    combo.setIconSize(QSize(24, 24))
    for hex_code, name in colors:
        pixmap = QPixmap(24, 24)
        pixmap.fill(QColor(hex_code))
        combo.addItem(QIcon(pixmap), "", hex_code)
        combo.setItemData(combo.count() - 1, name, Qt.ItemDataRole.ToolTipRole)

# ==========================================
# 2. OKNA DIALOGOWE EDYCJI
# ==========================================
class ButtonEditDialog(QDialog):
    def __init__(self, btn_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edytuj {btn_data.get('name', 'Przycisk')}")
        self.btn_data = btn_data
        
        self.resize(400, 390)
        self.main_layout = QVBoxLayout(self)
        
        top_layout = QFormLayout()
        self.cb_is_used = QCheckBox("Włącz/Aktywuj przycisk")
        self.cb_is_used.setChecked(btn_data.get("is_used", False))
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
        
        self.main_layout.addLayout(top_layout)
        
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #aaaaaa; font-style: italic; margin-bottom: 5px;")
        self.main_layout.addWidget(self.info_label)
        
        self.stack = QStackedWidget()
        
        # PUSH
        self.page_push = QWidget()
        l_push = QFormLayout(self.page_push)
        self.le_push_tx = QLineEdit(btn_data.get("tx", ""))
        l_push.addRow("TX:", self.le_push_tx)
        self.stack.addWidget(self.page_push)
        
        # TOGGLE
        self.page_toggle = QWidget()
        l_toggle = QFormLayout(self.page_toggle)
        self.le_tog_tx_on = QLineEdit(btn_data.get("tx_on", ""))
        self.le_tog_tx_off = QLineEdit(btn_data.get("tx_off", ""))
        self.le_tog_ack_on = QLineEdit(btn_data.get("ack_on", ""))
        self.le_tog_ack_off = QLineEdit(btn_data.get("ack_off", ""))
        l_toggle.addRow("TX ON:", self.le_tog_tx_on)
        l_toggle.addRow("TX OFF:", self.le_tog_tx_off)
        l_toggle.addRow("ACK ON:", self.le_tog_ack_on)
        l_toggle.addRow("ACK OFF:", self.le_tog_ack_off)
        self.stack.addWidget(self.page_toggle)
        
        # HOLD
        self.page_hold = QWidget()
        l_hold = QFormLayout(self.page_hold)
        self.le_hld_tx_on = QLineEdit(btn_data.get("tx_on", ""))
        self.le_hld_tx_off = QLineEdit(btn_data.get("tx_off", ""))
        l_hold.addRow("TX (Wciśnięty):", self.le_hld_tx_on)
        l_hold.addRow("TX (Puszczony):", self.le_hld_tx_off)
        self.stack.addWidget(self.page_hold)
        
        # TRIGGER
        self.page_trigger = QWidget()
        l_trig = QFormLayout(self.page_trigger)
        self.le_trig_tx = QLineEdit(btn_data.get("tx", ""))
        self.spin_trig_int = QSpinBox()
        self.spin_trig_int.setRange(10, 600000)
        self.spin_trig_int.setValue(btn_data.get("interval", 1000))
        self.spin_trig_int.setSuffix(" ms")
        l_trig.addRow("TX:", self.le_trig_tx)
        l_trig.addRow("Interwał:", self.spin_trig_int)
        self.stack.addWidget(self.page_trigger)
        
        # MACRO
        self.page_macro = QWidget()
        l_macro = QFormLayout(self.page_macro)
        self.le_mac_tx = QLineEdit(btn_data.get("tx", ""))
        self.le_mac_tx.setPlaceholderText("np. cmd1; sleep(500); cmd2")
        l_macro.addRow("Sekwencja:", self.le_mac_tx)
        self.stack.addWidget(self.page_macro)
        
        self.main_layout.addWidget(self.stack)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Discard)
        buttons.button(QDialogButtonBox.StandardButton.Discard).setText("Usuń / Wyczyść")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.delete_requested = False
        buttons.button(QDialogButtonBox.StandardButton.Discard).clicked.connect(self.on_delete)
        self.main_layout.addWidget(buttons)
        
        self.combo_type.currentTextChanged.connect(self.update_stack)
        self.update_stack(self.combo_type.currentText())
        
    def update_stack(self, text):
        mapping = {"push": 0, "toggle": 1, "hold": 2, "trigger": 3, "macro": 4}
        self.stack.setCurrentIndex(mapping.get(text, 0))
        
        infos = {
            "push": "ℹ️ Kliknięcie wysyła podaną ramkę jeden raz.",
            "toggle": "ℹ️ Przełącza tryb ON/OFF. Kolor przycisku na głównym panelu (Zielony/Czerwony) zmieni się TYLKO gdy sprzęt odeśle odpowiednie potwierdzenie w polu ACK.",
            "hold": "ℹ️ Wysyła ramkę wciśnięcia gdy wciśniesz przycisk myszką, oraz ramkę puszczenia w momencie jego zwolnienia.",
            "trigger": "ℹ️ Pętla asynchroniczna. Po kliknięciu będzie wysyłać ramkę w nieskończoność co wskazany interwał (ms). Ponowne kliknięcie zatrzymuje.",
            "macro": "ℹ️ Wykonuje łańcuch komend. Rozdzielaj instrukcje średnikiem. Możesz używać opóźnień wpisując 'sleep(milisekundy)'. Przykład: 'AA 01; sleep(500); BB 02'."
        }
        self.info_label.setText(infos.get(text, ""))

    def on_delete(self):
        self.delete_requested = True
        self.accept()

    def get_data(self):
        t = self.combo_type.currentText()
        res = {
            "id": self.btn_data.get("id"),
            "is_used": self.cb_is_used.isChecked(),
            "type": t,
            "name": self.le_name.text(),
            "show_marker": self.cb_show_marker.isChecked()
        }
        if t == "push":
            res["tx"] = self.le_push_tx.text()
        elif t == "toggle":
            res["tx_on"] = self.le_tog_tx_on.text()
            res["tx_off"] = self.le_tog_tx_off.text()
            res["ack_on"] = self.le_tog_ack_on.text()
            res["ack_off"] = self.le_tog_ack_off.text()
        elif t == "hold":
            res["tx_on"] = self.le_hld_tx_on.text()
            res["tx_off"] = self.le_hld_tx_off.text()
        elif t == "trigger":
            res["tx"] = self.le_trig_tx.text()
            res["interval"] = self.spin_trig_int.value()
        elif t == "macro":
            res["tx"] = self.le_mac_tx.text()
            
        return res


class ParserEditDialog(QDialog):
    def __init__(self, parser_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edytuj Parser: {parser_data.get('pattern', '')}")
        
        self.resize(300, 150)
        layout = QFormLayout(self)

        self.le_pattern = QLineEdit(parser_data.get("pattern", ""))
        layout.addRow("Wzór (HEX):", self.le_pattern)

        self.le_text = QLineEdit(parser_data.get("text", ""))
        layout.addRow("Zastąp tekstem:", self.le_text)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Discard)
        btns.button(QDialogButtonBox.StandardButton.Discard).setText("Usuń")
        
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        
        # Usuń button logic
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
        action = "hide" if self.combo_action.currentText() == "Ukryj" else "color"
        color = self.combo_color.currentData()
        return {
            "pattern": self.le_pattern.text().strip(),
            "action": action,
            "color": color
        }

# ==========================================
# 3. WĄTEK POBOCZNY (WORKER)
# ==========================================

class MacroRunner(QThread):
    tx_signal = pyqtSignal(str, str, bool)

    def __init__(self, sequence, name, show_marker, parent=None):
        super().__init__(parent)
        self.sequence = sequence
        self.name = name
        self.show_marker = show_marker
        
    def run(self):
        commands = self.sequence.split(';')
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
                self.tx_signal.emit(cmd, self.name, self.show_marker)

import queue

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
                # Odbieranie
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(min(self.serial_port.in_waiting, 4096))
                    if data:
                        self.data_received.emit(data)
                
                # Wysyłanie
                while not self.tx_queue.empty():
                    data_to_send = self.tx_queue.get_nowait()
                    try:
                        self.serial_port.write(data_to_send)
                    except serial.SerialTimeoutException:
                        self.error_occurred.emit("Błąd zapisu: Urządzenie nie odbiera danych (Timeout).")
                        # Kontynuujemy pracę, to nie jest błąd krytyczny

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

# ==========================================
# 4. GŁÓWNY INTERFEJS GUI
# ==========================================

class ConfigEditDialog(QDialog):
    def __init__(self, cfg_filepath, parent=None):
        super().__init__(parent)
        self.cfg_filepath = cfg_filepath
        self.setWindowTitle(f"Edytor Konfiguracji: {os.path.basename(cfg_filepath)}")
        self.resize(500, 450)
        
        layout = QVBoxLayout(self)
        
        try:
            with open(cfg_filepath, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except Exception as e:
            self.data = get_default_config()
            
        self.tabs = QTabWidget()
        
        # Zakładka Przyciski
        btn_tab = QWidget()
        btn_layout = QVBoxLayout(btn_tab)
        self.list_btns = QListWidget()
        for i, b in enumerate(self.data.get("buttons", [])):
            self.list_btns.addItem(f"[{i+1}] {b.get('name', 'Nieużywany')}")
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
        dlg = ButtonEditDialog(self.data["buttons"][idx], self)
        if dlg.exec():
            self.data["buttons"][idx] = dlg.get_data()
            item.setText(f"[{idx+1}] {self.data['buttons'][idx].get('name', 'Nieużywany')}")

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
            with open(self.cfg_filepath, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
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
        self.resize(550, 400)
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
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Wzór", "Akcja", "Zarządzanie"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
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
        
        # Connections
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
            
            item0 = QTableWidgetItem(f.get("pattern", ""))
            item0.setFlags(item0.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item0)
            
            action = f.get("action", "hide")
            a_text = "Ukryj" if action == "hide" else "Koloruj" if action == "color" else "Dozwolony"
            
            item1 = QTableWidgetItem(a_text)
            item1.setFlags(item1.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, item1)
            
            widget = QWidget()
            h_layout = QHBoxLayout(widget)
            h_layout.setContentsMargins(2,2,2,2)
            btn_e = QPushButton("Edytuj")
            btn_e.setStyleSheet("QPushButton { padding: 4px 8px; background-color: #228be6; color: white; border: none; border-radius: 3px; } QPushButton:hover { background-color: #1c7ed6; }")
            btn_d = QPushButton("Usuń")
            btn_d.setStyleSheet("QPushButton { padding: 4px 8px; background-color: #fa5252; color: white; border: none; border-radius: 3px; } QPushButton:hover { background-color: #f03e3e; }")
            btn_e.clicked.connect(lambda checked, idx=i: self.open_edit(idx))
            btn_d.clicked.connect(lambda checked, idx=i: self.delete_by_idx(idx))
            h_layout.addWidget(btn_e)
            h_layout.addWidget(btn_d)
            self.table.setCellWidget(row, 2, widget)
            
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
        if logical_index == 2:
            return
            
        if self.sort_col == logical_index:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = logical_index
            self.sort_asc = True
            
        if logical_index == 0:
            self.app_config["filters"].sort(key=lambda f: f.get("pattern", "").lower(), reverse=not self.sort_asc)
        elif logical_index == 1:
            self.app_config["filters"].sort(key=lambda f: f.get("action", "hide").lower(), reverse=not self.sort_asc)
            
        self.refresh_table()

class ParserManagerDialog(QDialog):
    def __init__(self, app_config, parent=None):
        super().__init__(parent)
        self.app_config = app_config
        self.setWindowTitle("Menadżer Parserów")
        self.resize(550, 400)
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
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Wzór (HEX)", "Zastąp tekstem", "Zarządzanie"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
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
        
        self.layout_edit.addRow("Wzór (HEX):", self.le_pattern)
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
        
        # Connections
        self.btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btn_save.clicked.connect(self.save_current_edit)
        self.btn_del.clicked.connect(self.delete_current_edit)
        
        self.refresh_table()
        
    def refresh_table(self):
        parsers = self.app_config.get("parsers", [])
        self.table.setRowCount(len(parsers))
        for i, p in enumerate(parsers):
            self.table.setItem(i, 0, QTableWidgetItem(p.get("pattern", "")))
            self.table.setItem(i, 1, QTableWidgetItem(p.get("text", "")))
            
            widget = QWidget()
            h_layout = QHBoxLayout(widget)
            h_layout.setContentsMargins(2,2,2,2)
            btn_e = QPushButton("Edytuj")
            btn_e.setStyleSheet("QPushButton { padding: 4px 8px; background-color: #228be6; color: white; border: none; border-radius: 3px; } QPushButton:hover { background-color: #1c7ed6; }")
            btn_d = QPushButton("Usuń")
            btn_d.setStyleSheet("QPushButton { padding: 4px 8px; background-color: #fa5252; color: white; border: none; border-radius: 3px; } QPushButton:hover { background-color: #f03e3e; }")
            btn_e.clicked.connect(lambda checked, idx=i: self.open_edit(idx))
            btn_d.clicked.connect(lambda checked, idx=i: self.delete_by_idx(idx))
            h_layout.addWidget(btn_e)
            h_layout.addWidget(btn_d)
            self.table.setCellWidget(i, 2, widget)
            
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
        if logical_index == 2:
            return
            
        if self.sort_col == logical_index:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = logical_index
            self.sort_asc = True
            
        if logical_index == 0:
            self.app_config["parsers"].sort(key=lambda p: p.get("pattern", "").lower(), reverse=not self.sort_asc)
        elif logical_index == 1:
            self.app_config["parsers"].sort(key=lambda p: p.get("text", "").lower(), reverse=not self.sort_asc)
            
        self.refresh_table()

class SerialTab(QWidget):
    def __init__(self, cli_config="", parent=None):
        super().__init__(parent)
        
        if not os.path.exists(CFG_DIR):
            os.makedirs(CFG_DIR)

        self.setWindowTitle("Serial Commander")
        self.resize(1100, 700)
        self.worker = None
        
        self.rx_buffer = bytearray()
        self.text_buffer = ""
        self.has_real_logs = False
        
        self.button_states = [False] * 10 
        self.button_timers = [QTimer(self) for _ in range(10)]
        for i, t in enumerate(self.button_timers):
            t.timeout.connect(lambda checked=False, idx=i: self.on_trigger_timeout(idx))
            
        self.gui_buttons = []
        self.macro_runners = []
        
        self.app_settings = load_app_settings()
        self.app_config = get_default_config()
        self.current_cfg_file = ""

        main_layout = QHBoxLayout(self)

        # ------------------------------------------
        # LEWA STRONA: Przyciski + Wybór Konfiguracji
        # ------------------------------------------
        left_panel_layout = QVBoxLayout()
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(240)
        
        buttons_widget = QWidget()
        self.buttons_layout = QVBoxLayout(buttons_widget)
        self.buttons_layout.setContentsMargins(10, 10, 10, 10)
        
        for i in range(10):
            btn = QPushButton()
            btn.setFixedSize(200, 45)
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, idx=i: self.edit_button_config(idx))
            
            self.gui_buttons.append(btn)
            self.buttons_layout.addWidget(btn)

        self.buttons_layout.addStretch()
        scroll_area.setWidget(buttons_widget)
        left_panel_layout.addWidget(scroll_area)

        cfg_layout = QVBoxLayout()
        cfg_layout.addWidget(QLabel("Wybór konfiguracji (cfg/):"))
        
        cfg_controls = QHBoxLayout()
        self.combo_cfg = QComboBox()
        self.combo_cfg.currentIndexChanged.connect(self.on_config_changed)
        cfg_controls.addWidget(self.combo_cfg, stretch=1)
        
        self.btn_new_cfg = QPushButton("Nowa")
        self.btn_new_cfg.clicked.connect(self.create_new_config)
        cfg_controls.addWidget(self.btn_new_cfg)
        
        self.btn_edit_cfg = QPushButton("Edytuj")
        self.btn_edit_cfg.clicked.connect(self.edit_current_config)
        cfg_controls.addWidget(self.btn_edit_cfg)
        
        cfg_layout.addLayout(cfg_controls)
        left_panel_layout.addLayout(cfg_layout)
        main_layout.addLayout(left_panel_layout)

        # ------------------------------------------
        # PRAWA STRONA: Wprowadzanie komend, Filtry, Konsola
        # ------------------------------------------
        right_layout = QVBoxLayout()

        # Pasek 1: Wprowadzanie komend
        cmd_layout = QHBoxLayout()
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Wpisz komendę (np. help lub AA 01)...")
        self.cmd_input.returnPressed.connect(self.send_manual_command) 
        
        self.btn_send_cmd = QPushButton("Send")
        self.btn_send_cmd.clicked.connect(self.send_manual_command)
        
        cmd_layout.addWidget(self.cmd_input)
        cmd_layout.addWidget(self.btn_send_cmd)
        right_layout.addLayout(cmd_layout)

        # Pasek 2: Filtry RX (Nowy podział ról)
        filter_layout = QHBoxLayout()
        
        self.le_filter_pattern = QLineEdit()
        self.le_filter_pattern.setPlaceholderText("Filtr (np. \"*test*\")")
        
        self.combo_filter_action = QComboBox()
        self.combo_filter_action.addItems(["Ukryj", "Koloruj", "Dozwolony (Whitelist)"])
        
        self.combo_filter_color = QComboBox()
        populate_color_combo(self.combo_filter_color)
        self.combo_filter_color.setEnabled(False) # Domyślnie wyłączone dla akcji 'Ukryj'
        self.combo_filter_action.currentTextChanged.connect(
            lambda t: self.combo_filter_color.setEnabled(t == "Koloruj")
        )
        
        self.btn_add_filter = QPushButton("Dodaj")
        self.btn_add_filter.clicked.connect(self.add_filter)

        self.btn_whitelist_warn = QPushButton("⚠ ZAPORA")
        self.btn_whitelist_warn.setStyleSheet("background-color: #e03131; color: white; font-weight: bold; border-radius: 3px; padding: 4px 10px;")
        self.btn_whitelist_warn.setToolTip("Terminal w trybie ZAPORY! Ignoruje wszystko poza Dozwolonymi filtrami.")
        self.btn_whitelist_warn.clicked.connect(self.open_whitelist_manager)

        self.btn_edit_filter = QPushButton("Menadżer Filtrów")
        self.btn_edit_filter.clicked.connect(self.edit_filter)
        
        filter_layout.addWidget(self.le_filter_pattern)
        filter_layout.addWidget(self.combo_filter_action)
        filter_layout.addWidget(self.combo_filter_color)
        filter_layout.addWidget(self.btn_add_filter)
        filter_layout.addWidget(self.btn_whitelist_warn)
        filter_layout.addStretch()
        filter_layout.addWidget(self.btn_edit_filter)
        
        right_layout.addLayout(filter_layout)

        # Pasek 2b: Parsery Payloadu
        parser_layout = QHBoxLayout()
        
        self.le_parser_pattern = QLineEdit()
        self.le_parser_pattern.setPlaceholderText("Parser (np. AA 01)")
        
        self.le_parser_text = QLineEdit()
        self.le_parser_text.setPlaceholderText("Tekst (np. [START])")
        
        self.btn_add_parser = QPushButton("Dodaj Parser")
        self.btn_add_parser.clicked.connect(self.add_parser)

        self.btn_edit_parser = QPushButton("Menadżer Parserów")
        self.btn_edit_parser.clicked.connect(self.edit_parser)
        
        parser_layout.addWidget(self.le_parser_pattern)
        parser_layout.addWidget(self.le_parser_text)
        parser_layout.addWidget(self.btn_add_parser)
        parser_layout.addStretch()
        parser_layout.addWidget(self.btn_edit_parser)
        
        right_layout.addLayout(parser_layout)

        # Pasek 3: Konsola
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #1e1e1e; font-family: Consolas, monospace; font-size: 13px;")
        right_layout.addWidget(self.console)

        # Pasek 4: Tryby i zasilanie
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Tryb danych:"))
        
        self.radio_binary = QRadioButton("BINARY (HEX)")
        self.radio_ascii = QRadioButton("ASCII")
        mode_layout.addWidget(self.radio_binary)
        mode_layout.addWidget(self.radio_ascii)
        
        self.btn_clear = QPushButton("Clear Console")
        self.btn_clear.clicked.connect(self.console.clear)
        mode_layout.addWidget(self.btn_clear)

        self.btn_save_log = QPushButton("Zapisz Logi")
        self.btn_save_log.clicked.connect(self.save_logs)
        mode_layout.addWidget(self.btn_save_log)

        self.btn_marker = QPushButton("Wstaw Marker")
        self.btn_marker.clicked.connect(self.insert_marker)
        mode_layout.addWidget(self.btn_marker)
        
        mode_layout.addSpacing(20)
        mode_layout.addWidget(QLabel("Limit linii:"))
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(100, 100000)
        self.spin_limit.setSingleStep(1000)
        self.spin_limit.setValue(5000)
        self.spin_limit.valueChanged.connect(self.console.document().setMaximumBlockCount)
        self.console.document().setMaximumBlockCount(5000)
        mode_layout.addWidget(self.spin_limit)
        
        mode_layout.addStretch()
        right_layout.addLayout(mode_layout)

        config_layout = QHBoxLayout()
        config_layout.addWidget(QLabel("Port COM:"))
        
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(100)
        config_layout.addWidget(self.port_combo)

        self.btn_refresh = QPushButton("Odśwież")
        self.btn_refresh.clicked.connect(self.refresh_ports)
        config_layout.addWidget(self.btn_refresh)

        config_layout.addWidget(QLabel("Baudrate:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        config_layout.addWidget(self.baud_combo)

        self.btn_connect = QPushButton("Połącz")
        self.btn_connect.setStyleSheet("background-color: #228be6; color: white; font-weight: bold;")
        self.btn_connect.clicked.connect(self.toggle_connection)
        config_layout.addWidget(self.btn_connect)

        right_layout.addLayout(config_layout)
        main_layout.addLayout(right_layout, stretch=1)

        target_cfg = self.app_settings.get("last_config", "default.json")
        if cli_config:
            if not cli_config.endswith('.json'):
                cli_config += '.json'
            target_cfg = cli_config

        self.refresh_ports()
        self.refresh_configs_list(select_file=target_cfg)

    # ==========================================
    # ZARZĄDZANIE KONFIGURACJAMI
    # ==========================================
    def refresh_configs_list(self, select_file=None):
        self.combo_cfg.blockSignals(True)
        self.combo_cfg.clear()
        
        files = [f for f in os.listdir(CFG_DIR) if f.endswith('.json') and f != "app_settings.json"]
        
        # Jeśli ładujemy ukryty default.json, to musi być on widoczny tylko dla tej karty
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
            # Przeładuj tab
            self.app_config = load_config(self.current_cfg_file)
            self.refresh_ports()
            # update UI ... easiest way is to re-select
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
                save_config(filepath, get_default_config())
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
        
        # self.setWindowTitle(...) handled by MainWindow
        self.log_info(f"Wczytano konfigurację: {selected_file}")

        self.app_settings["last_config"] = selected_file
        save_app_settings(self.app_settings)

        saved_port = self.app_config.get("port")
        if saved_port and saved_port in [self.port_combo.itemText(i) for i in range(self.port_combo.count())]:
            self.port_combo.setCurrentText(saved_port)
            
        saved_baud = str(self.app_config.get("baudrate", 115200))
        if saved_baud in [self.baud_combo.itemText(i) for i in range(self.baud_combo.count())]:
            self.baud_combo.setCurrentText(saved_baud)
            
        if self.app_config.get("mode") == "BINARY":
            self.radio_binary.setChecked(True)
        else:
            self.radio_ascii.setChecked(True)

        for i in range(10):
            self.button_states[i] = False 
            self.setup_button(i)
            
        self.refresh_filter_combo()

    def close_tab(self, skip_log_prompt=False):
        """Wywoływane przy zamykaniu karty. Zwraca True (można zamknąć) lub False (anulowano)."""
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
            
        for runner in self.macro_runners:
            if runner.isRunning():
                runner.terminate()
                runner.wait()
                
        return True

    def save_current_settings_to_config(self, force=False):
        if not self.current_cfg_file:
            return
            
        new_port = self.port_combo.currentText()
        new_baud = int(self.baud_combo.currentText()) if self.baud_combo.currentText() else 115200
        new_mode = "ASCII" if self.radio_ascii.isChecked() else "BINARY"
        
        has_changes = force
        if self.app_config.get("port") != new_port: has_changes = True
        if self.app_config.get("baudrate") != new_baud: has_changes = True
        if self.app_config.get("mode") != new_mode: has_changes = True
        
        if has_changes:
            self.app_config["port"] = new_port
            self.app_config["baudrate"] = new_baud
            self.app_config["mode"] = new_mode
            save_config(self.current_cfg_file, self.app_config)

    # ==========================================
    # LOGIKA FILTRÓW RX
    # ==========================================
    def refresh_filter_combo(self):
        if hasattr(self, 'btn_whitelist_warn'):
            has_allow = any(f.get("action") == "allow" for f in self.app_config.get("filters", []))
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
            "text": p_text
        })
        self.le_parser_pattern.clear()
        self.le_parser_text.clear()
        self.save_current_settings_to_config(force=True)
        self.refresh_filter_combo()
        
    def edit_parser(self):
        idx = self.combo_active_parsers.currentIndex()
        if idx < 0 or "parsers" not in self.app_config:
            return
            
        parser_data = self.app_config["parsers"][idx]
        dlg = ParserEditDialog(parser_data, self)
        if dlg.exec():
            if dlg.delete_requested:
                self.app_config["parsers"].pop(idx)
            else:
                self.app_config["parsers"][idx] = dlg.get_data()
            self.save_current_settings_to_config(force=True)
            self.refresh_filter_combo()

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
            "color": color
        })
        self.le_filter_pattern.clear()
        self.save_current_settings_to_config(force=True)
        self.refresh_filter_combo()
        
        
    def edit_filter(self):
        dlg = FilterManagerDialog(self.app_config, self)
        dlg.exec()
        self.save_current_settings_to_config(force=True)
        self.refresh_filter_combo()

    def edit_parser(self):
        dlg = ParserManagerDialog(self.app_config, self)
        dlg.exec()
        self.save_current_settings_to_config(force=True)

    def process_message_filters(self, msg):
        """Sprawdza wiadomość pod kątem filtrów. Zwraca (should_hide, text_color)."""
        color = "#cccccc" 
        
        filters = self.app_config.get("filters", [])
        
        # 1. Whitelist (jeśli istnieje jakikolwiek filtr 'allow', wiadomość musi pasować do jednego z nich)
        allow_filters = [f for f in filters if f["action"] == "allow"]
        if allow_filters:
            is_allowed = False
            for f in allow_filters:
                if fnmatch.fnmatch(msg, f["pattern"]):
                    is_allowed = True
                    break
            if not is_allowed:
                return True, msg, ""
        
        # 2. Standardowe filtry (Ukryj / Koloruj)
        for f in filters:
            if fnmatch.fnmatch(msg, f["pattern"]):
                if f["action"] == "hide":
                    return True, msg, ""
                elif f["action"] == "color":
                    color = f["color"]
                    
        # Apply Parsers
        parsed_msg = msg
        for p in self.app_config.get("parsers", []):
            if fnmatch.fnmatch(msg, p["pattern"]):
                parsed_msg = p["text"]
                color = "#ffd700" # Złoty kolor dla sparsowanych ramek
                break
                
        return False, parsed_msg, color

    # ==========================================
    # ZARZĄDZANIE PRZYCISKAMI
    # ==========================================
    def edit_button_config(self, idx):
        btn_data = self.app_config["buttons"][idx]
        dialog = ButtonEditDialog(btn_data, self)
        
        if dialog.exec(): 
            new_data = dialog.get_data()
            self.app_config["buttons"][idx] = new_data
            
            self.save_current_settings_to_config(force=True)
            self.setup_button(idx)
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

        if btn_cfg.get("is_used", False):
            b_type = btn_cfg.get("type", "toggle")
            name = btn_cfg.get("name", f"Btn {idx+1}")
            
            if self.button_timers[idx].isActive():
                self.button_timers[idx].stop()
            self.button_states[idx] = False
            
            if b_type == "toggle":
                state = self.button_states[idx]
                btn.setText(f"🔘 {name}: {'ON' if state else 'OFF'}")
                color = "#37b24d" if state else "#f03e3e"
                btn.setStyleSheet(self.get_btn_style(color))
                btn.clicked.connect(lambda checked, i=idx: self.on_toggle_clicked(i))
                
            elif b_type == "push":
                btn.setText(f"⚡ {name}")
                btn.setStyleSheet(self.get_btn_style("#228be6"))
                btn.clicked.connect(lambda checked, i=idx: self.on_push_clicked(i))
                
            elif b_type == "hold":
                btn.setText(f"⏳ {name}")
                btn.setStyleSheet(self.get_btn_style("#f59f00"))
                btn.pressed.connect(lambda i=idx: self.on_hold_pressed(i))
                btn.released.connect(lambda i=idx: self.on_hold_released(i))
                
            elif b_type == "macro":
                btn.setText(f"📜 {name}")
                btn.setStyleSheet(self.get_btn_style("#9c27b0"))
                btn.clicked.connect(lambda checked, i=idx: self.on_macro_clicked(i))
                
            elif b_type == "trigger":
                btn.setText(f"🔁 {name}")
                btn.setStyleSheet(self.get_btn_style("#607d8b"))
                btn.clicked.connect(lambda checked, i=idx: self.on_trigger_clicked(i))
        else:
            btn.setText("Not Used (PPM: Edytuj)")
            btn.setStyleSheet(self.get_btn_style("#333"))

    # ==========================================
    # LOGOWANIE I PORT COM
    # ==========================================
    def get_timestamp(self):
        now = datetime.now()
        return now.strftime("[%H:%M:%S.") + f"{now.microsecond // 1000:03d}]"

    def log_tx(self, msg, marker=""):
        self.has_real_logs = True
        marker_html = f'<span style="color: #ffaa00; font-weight: bold;">[{marker}] </span>' if marker else ""
        self.console.append(f'<span style="color: #4da6ff;">TX {self.get_timestamp()}: </span>{marker_html}<span style="color: #4da6ff;">{msg}</span>')
        self.scroll_to_bottom()

    def log_rx(self, msg):
        should_hide, parsed_msg, text_color = self.process_message_filters(msg)
        if should_hide:
            return
            
        self.has_real_logs = True
        ts = self.get_timestamp()
        self.console.append(f'<span style="color: #66cc66;">RX {ts}: </span><span style="color: {text_color};">{parsed_msg}</span>')
        self.scroll_to_bottom()

    def log_info(self, msg):
        self.console.append(f'<span style="color: #cccccc;">{msg}</span>')
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_combo.addItem(p.device)
            
        saved_port = self.app_config.get("port") if self.app_config else None
        if saved_port and saved_port in [self.port_combo.itemText(i) for i in range(self.port_combo.count())]:
            self.port_combo.setCurrentText(saved_port)
            
        if not ports:
            self.log_info("Nie znaleziono portów COM.")
        else:
            self.log_info(f"Znaleziono {len(ports)} port(ów).")

    def save_logs(self):
        filters = "Strona HTML (*.html);;Markdown z kolorami (*.md);;Zwykły tekst (*.txt);;Wszystkie pliki (*)"
        filename, selected_filter = QFileDialog.getSaveFileName(self, "Zapisz logi", "", filters)
        
        if filename:
            try:
                date_info = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                port_info = f"{self.port_combo.currentText()} ({self.baud_combo.currentText()} bps)"
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
                    import re
                    content = re.sub(r'(<body[^>]*>)', r'\1' + header_html, content, count=1)
                    content = content.replace("<body", "<body style=\"background-color: #1e1e1e; color: #cccccc; font-family: monospace; padding: 15px;\"")
                elif filename.endswith(".md") or "Markdown" in selected_filter:
                    import re
                    html_full = self.console.toHtml()
                    body_match = re.search(r'<body[^>]*>(.*?)</body>', html_full, re.DOTALL | re.IGNORECASE)
                    body_content = body_match.group(1) if body_match else html_full
                    content = f"# Logi Diagnostyczne\n\n<div style=\"background-color: #1e1e1e; color: #cccccc; font-family: monospace; padding: 15px; border-radius: 5px;\">\n{header_html}{body_content}\n</div>"
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
            self.console.append(f'<br><span style="color: #ff9800; font-weight: bold; font-size: 14px;">--- MARKER: {text} ---</span><br>')
            self.scroll_to_bottom()

    def toggle_connection(self):
        if self.worker and self.worker.is_running:
            self.worker.stop()
            self.worker = None
            self.btn_connect.setText("Połącz")
            self.btn_connect.setStyleSheet("background-color: #228be6; color: white; font-weight: bold;")
            self.port_combo.setEnabled(True)
            self.baud_combo.setEnabled(True)
            self.btn_refresh.setEnabled(True)
            self.combo_cfg.setEnabled(True) 
            
            self.rx_buffer.clear()
            self.text_buffer = ""
            self.log_info("Rozłączono.")
        else:
            selected_port = self.port_combo.currentText()
            selected_baud = int(self.baud_combo.currentText())

            if not selected_port:
                QMessageBox.warning(self, "Błąd", "Nie wybrano portu COM!")
                return

            if os.path.basename(self.current_cfg_file) == "default.json":
                new_name = f"{selected_port}.json"
                new_path = os.path.join(CFG_DIR, new_name)
                # Klonuj profil pod nazwę portu
                self.current_cfg_file = new_path
                self.save_current_settings_to_config(force=True)
                self.refresh_configs_list(select_file=new_name)

            self.log_info(f"Próba połączenia: {selected_port} ({selected_baud} bps)...")
            self.save_current_settings_to_config(force=False)

            self.worker = SerialWorker(selected_port, selected_baud)
            self.worker.data_received.connect(self.process_received_data)
            self.worker.error_occurred.connect(self.log_info)
            self.worker.connection_status.connect(self.handle_connection_status)
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker.start()

    def handle_connection_status(self, connected: bool):
        if connected:
            self.btn_connect.setText("Rozłącz")
            self.btn_connect.setStyleSheet("background-color: #fa5252; color: white; font-weight: bold;")
            self.port_combo.setEnabled(False)
            self.baud_combo.setEnabled(False)
            self.btn_refresh.setEnabled(False)
            self.combo_cfg.setEnabled(False) 
            self.log_info("Połączono.")
        else:
            self.btn_connect.setText("Połącz")
            self.btn_connect.setStyleSheet("background-color: #228be6; color: white; font-weight: bold;")
            self.port_combo.setEnabled(True)
            self.baud_combo.setEnabled(True)
            self.btn_refresh.setEnabled(True)
            self.combo_cfg.setEnabled(True) 
            # Nie kasujemy self.worker tutaj, bo wątek może wciąż działać i zrzucać wyjątki.
            # QThread zostanie usunięty bezpiecznie dzięki sygnałowi finished.connect(deleteLater)

    def send_payload(self, payload_str, source_name="Manual", show_marker=False):
        if not self.worker or not self.worker.is_running:
            self.log_info(f"Brak połączenia COM. Odrzucono: {source_name}")
            return

        marker_text = source_name if show_marker else ""

        if self.radio_ascii.isChecked():
            data_to_send = (payload_str + "\r\n").encode('utf-8')
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
            self.send_payload(text, source_name="Terminal")

    def on_toggle_clicked(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        is_currently_on = self.button_states[idx]
        payload = btn_cfg.get("tx_off", "") if is_currently_on else btn_cfg.get("tx_on", "")
        self.send_payload(payload, source_name=btn_cfg['name'], show_marker=btn_cfg.get("show_marker", False))

    def on_push_clicked(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        self.send_payload(btn_cfg.get("tx", ""), source_name=btn_cfg['name'], show_marker=btn_cfg.get("show_marker", False))

    def on_hold_pressed(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        self.send_payload(btn_cfg.get("tx_on", ""), source_name=btn_cfg['name'], show_marker=btn_cfg.get("show_marker", False))

    def on_hold_released(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        self.send_payload(btn_cfg.get("tx_off", ""), source_name=btn_cfg['name'], show_marker=btn_cfg.get("show_marker", False))

    def on_macro_clicked(self, idx: int):
        btn_cfg = self.app_config["buttons"][idx]
        sequence = btn_cfg.get("tx", "")
        self.log_info(f"Start Macro: {btn_cfg['name']} -> {sequence}")
        
        # Clean up old dead runners
        self.macro_runners = [r for r in self.macro_runners if r.isRunning()]
        
        runner = MacroRunner(sequence, btn_cfg['name'], btn_cfg.get("show_marker", False))
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
            btn.setText(f"⏹ {cfg.get('name', '')} (Auto)")
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
            self.send_payload(tx, source_name=cfg.get('name', ''), show_marker=cfg.get("show_marker", False))


    def get_btn_style(self, bg_hex):
        text_c = "#777" if bg_hex == "#333" else "white"
        hovers = {
            "#37b24d": "#2f9e44", "#f03e3e": "#e03131",
            "#228be6": "#1c7ed6", "#f59f00": "#f08c00",
            "#9c27b0": "#8e24aa", "#607d8b": "#546e7a",
            "#e67700": "#d9480f", "#333": "#444"
        }
        presseds = {
            "#37b24d": "#2b8a3e", "#f03e3e": "#c92a2a",
            "#228be6": "#1864ab", "#f59f00": "#e67700",
            "#9c27b0": "#7b1fa2", "#607d8b": "#455a64",
            "#e67700": "#c92a2a", "#333": "#222"
        }
        hover = hovers.get(bg_hex, bg_hex)
        pressed = presseds.get(bg_hex, bg_hex)
        
        return f"""
        QPushButton {{ background-color: {bg_hex}; color: {text_c}; font-weight: bold; font-size: 14px; border-radius: 4px; border: 1px solid rgba(0,0,0,0.4); }}
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
                
            if self.radio_ascii.isChecked():
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
# 5. GŁÓWNE OKNO APLIKACJI (KARTY)
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self, cli_config=None):
        super().__init__()
        self.setWindowTitle("Serial Commander")
        self.resize(1100, 700)
        
        self.app_settings = load_app_settings()
        
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)
        
        self.btn_add_tab = QPushButton(" + Nowa Karta ")
        self.btn_add_tab.clicked.connect(lambda: self.add_new_tab())
        self.tabs.setCornerWidget(self.btn_add_tab, Qt.Corner.TopRightCorner)
        
        saved_tabs = self.app_settings.get("open_tabs", [])
        if cli_config:
            self.add_new_tab(cli_config)
        elif saved_tabs:
            for cfg in saved_tabs:
                self.add_new_tab(cfg)
        else:
            self.add_new_tab()
            
    def save_tabs_state(self):
        tabs_configs = []
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if hasattr(tab, 'combo_cfg') and tab.combo_cfg.currentText():
                tabs_configs.append(tab.combo_cfg.currentText())
        self.app_settings["open_tabs"] = tabs_configs
        save_app_settings(self.app_settings)
        
    def add_new_tab(self, cli_config=None):
        if self.tabs.count() >= 10:
            QMessageBox.warning(self, "Limit kart", "Osiągnięto maksymalną liczbę otwartych kart (10).")
            return
            
        free_port = None
        if not cli_config:
            import serial.tools.list_ports
            available_ports = [p.device for p in serial.tools.list_ports.comports()]
            used_ports = []
            for i in range(self.tabs.count()):
                t = self.tabs.widget(i)
                if hasattr(t, 'port_combo'):
                    used_ports.append(t.port_combo.currentText())
                    
            unused_ports = [p for p in available_ports if p not in used_ports]
            
            if not unused_ports:
                QMessageBox.warning(self, "Brak portów", "Wszystkie dostępne porty COM w systemie są już zajęte przez otwarte karty.\nNie ma sensu otwierać kolejnej.")
                return
                
            free_port = unused_ports[0]
            cli_config = "default.json"
            
        tab = SerialTab(cli_config)
        idx = self.tabs.addTab(tab, "Nowa Karta")
        self.tabs.setCurrentIndex(idx)
        
        def on_tab_changed(text, t=tab):
            self.tabs.setTabText(self.tabs.indexOf(t), text)
            self.save_tabs_state()
            
        tab.combo_cfg.currentTextChanged.connect(on_tab_changed)
        
        if free_port:
            tab.port_combo.setCurrentText(free_port)
            
        if tab.combo_cfg.currentText():
            self.tabs.setTabText(idx, tab.combo_cfg.currentText())
            
        self.save_tabs_state()
            
    def close_tab(self, index):
        tab = self.tabs.widget(index)
        if hasattr(tab, 'close_tab'):
            if not tab.close_tab():
                return
        self.tabs.removeTab(index)
        tab.deleteLater()
        self.save_tabs_state()
        if self.tabs.count() == 0:
            self.close()

    def closeEvent(self, event):
        tabs_with_logs = 0
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if hasattr(tab, 'has_real_logs') and tab.has_real_logs:
                tabs_with_logs += 1
                
        if tabs_with_logs > 0:
            reply = QMessageBox.question(
                self, 'Zamykanie Programu', 
                f'Masz {tabs_with_logs} kart(y) z niezapisanymi logami.\nCzy na pewno chcesz zamknąć program bez ich zapisywania?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if hasattr(tab, 'close_tab'):
                tab.close_tab(skip_log_prompt=True)
                
        self.save_tabs_state()
        event.accept()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Terminal Diagnostyczny")
    parser.add_argument('--config', type=str, default='', help='Wymuś wczytanie konkretnego pliku np. --config auto.json')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    window = MainWindow(cli_config=args.config)
    window.show()
    sys.exit(app.exec())
