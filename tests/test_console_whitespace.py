from __future__ import annotations

"""
Test renderowania konsoli bez sprzętu: wielokrotne spacje i znaki HTML.

Sprawdza, że:
  * log_rx() / log_tx() zachowują ciągi spacji (wyrównanie kolumn, np. tabela IO_HELP z V-BOX),
  * znaki < > & w treści RX / TX oraz w nazwie markera są widoczne dosłownie,
  * wiersz panelu Watch (LiveWatchRowWidget.render_html) zachowuje spacje między tokenami,
  * zapis TXT (toPlainText) i HTML (toHtml -> ponowne wczytanie) zachowuje spacje.

Uruchomienie:  python tests/test_console_whitespace.py
"""

import os
import re
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QTextEdit
from PyQt6.QtGui import QTextDocument

app = QApplication.instance() or QApplication(sys.argv)

from gui import SerialTab, LiveWatchRowWidget

LINES = [
    "[IO] | Komenda            | Wartosci  | Opis                                           |",
    "[IO] +--------------------+-----------+------------------------------------------------+",
    "ADC:   42 (  7%)",
    "  wiodace i koncowe spacje   ",
    "ZRODLO#<UART|IO> & <b>nie pogrubione</b>",
]


class _Checked:
    def isChecked(self):
        return True


class ConsoleStub:
    """Minimalny obiekt z metodami logowania SerialTab – bez budowania całego okna."""
    log_tx = SerialTab.log_tx
    log_rx = SerialTab.log_rx
    append_html_no_autoscroll = SerialTab.append_html_no_autoscroll
    get_timestamp = SerialTab.get_timestamp
    get_uart_can_response_color = staticmethod(SerialTab.get_uart_can_response_color)

    def __init__(self):
        self.console = QTextEdit()
        self.cb_watch_print = _Checked()
        self.has_real_logs = False

    def handle_incoming_watch_check(self, msg, ts):
        return False, msg

    def process_message_filters(self, msg):
        return False, msg, "#d4d4d8"


def strip_prefix(line: str, prefix: str) -> str:
    m = re.match(rf"{prefix} \[\d\d:\d\d:\d\d\.\d{{3}}\]: ", line)
    assert m, f"brak prefiksu {prefix} w {line!r}"
    return line[m.end():]


def test_rx_tx():
    w = ConsoleStub()
    for line in LINES:
        w.log_rx(line)
        w.log_tx(line)
    w.log_tx("CFG?", marker="<M&1>")
    out = w.console.toPlainText().split("\n")
    assert len(out) == 2 * len(LINES) + 1, out
    for i, line in enumerate(LINES):
        assert strip_prefix(out[2 * i], "RX") == line, out[2 * i]
        assert strip_prefix(out[2 * i + 1], "TX") == line, out[2 * i + 1]
    assert strip_prefix(out[-1], "TX") == "[<M&1>] CFG?", out[-1]

    # Zapis HTML: ponowne wczytanie toHtml() daje te same znaki
    reloaded = QTextEdit()
    reloaded.setHtml(w.console.toHtml())
    assert reloaded.toPlainText() == w.console.toPlainText()


def test_watch_row():
    row = LiveWatchRowWidget("key")
    msg = "ADC: %4lu  -> 1023   (100%)  <ok>"
    row.update_message(msg, "[10:00:00.000]")
    row.update_message(msg.replace("1023", "  12"), "[10:00:00.100]")
    # QLabel (RichText) używa tego samego parsera HTML co QTextDocument
    doc = QTextDocument()
    doc.setHtml(row.lbl_content.text())
    plain = doc.toPlainText()
    assert plain == "[10:00:00.100] " + msg.replace("1023", "  12"), repr(plain)


if __name__ == "__main__":
    test_rx_tx()
    test_watch_row()
    print(f"OK: {len(LINES)} linii RX/TX, marker, zapis HTML, wiersz Watch")
