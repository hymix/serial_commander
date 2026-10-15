from __future__ import annotations

"""
Obsługa magistrali CAN dla Serial Commander (adapter CANable z firmware slcan).

Moduł zawiera:
  * CanFrame            – lekka reprezentacja ramki CAN niezależna od python-can (łatwa do testów),
  * parse_can_frame()   – parser składni w stylu `cansend` (ID#DANE) z czytelnymi komunikatami błędów,
  * normalize_can_ack_pattern() – normalizacja wzorców ACK dla przycisków typu toggle,
  * CanWorker(QThread)  – wątek komunikacji z adapterem (python-can, interface="slcan").

Zasady wątków: CanWorker nigdy nie dotyka GUI – komunikuje się wyłącznie sygnałami pyqtSignal,
a ramki do wysłania odbiera przez bezpieczną kolejkę queue.Queue() (tx_queue).
"""

import queue
import re
import time
from typing import List, Optional, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

try:
    import can  # python-can
    CAN_AVAILABLE = True
    CAN_IMPORT_ERROR = ""
except Exception as _e:  # pragma: no cover - zależy od środowiska
    can = None
    CAN_AVAILABLE = False
    CAN_IMPORT_ERROR = str(_e)

# ==========================================
# STAŁE
# ==========================================
TRANSPORT_SERIAL = "serial"
TRANSPORT_SLCAN = "slcan"
TRANSPORTS = (TRANSPORT_SERIAL, TRANSPORT_SLCAN)
TRANSPORT_LABELS = {
    TRANSPORT_SERIAL: "Serial (UART)",
    TRANSPORT_SLCAN: "CAN – CANable (slcan)",
}

# Prędkości obsługiwane przez protokół slcan w python-can (komendy S0..S9)
CAN_BITRATES = [10000, 20000, 50000, 83300, 100000, 125000, 250000, 500000, 750000, 1000000]
DEFAULT_CAN_BITRATE = 500000

MAX_STD_ID = 0x7FF
MAX_EXT_ID = 0x1FFFFFFF
MAX_CLASSIC_DLC = 8

_HEX_RE = re.compile(r'^[0-9A-Fa-f]+$')


def format_bitrate_label(bitrate: int) -> str:
    """500000 -> '500k', 1000000 -> '1M', 83300 -> '83.3k'."""
    try:
        bitrate = int(bitrate)
    except (TypeError, ValueError):
        return str(bitrate)
    if bitrate >= 1000000 and bitrate % 1000000 == 0:
        return f"{bitrate // 1000000}M"
    if bitrate % 1000 == 0:
        return f"{bitrate // 1000}k"
    return f"{bitrate / 1000:.1f}k"


class CanFrameError(ValueError):
    """Błąd składni ramki CAN wpisanej przez użytkownika."""


# ==========================================
# RAMKA CAN
# ==========================================
class CanFrame:
    __slots__ = ("arbitration_id", "is_extended", "is_remote", "dlc", "data", "timestamp")

    def __init__(self, arbitration_id: int, data: bytes = b"", is_extended: bool = False,
                 is_remote: bool = False, dlc: Optional[int] = None, timestamp: float = 0.0):
        self.arbitration_id = int(arbitration_id)
        self.is_extended = bool(is_extended)
        self.is_remote = bool(is_remote)
        self.data = bytes(data) if not is_remote else b""
        self.dlc = int(dlc) if dlc is not None else len(self.data)
        self.timestamp = float(timestamp)

    def id_str(self) -> str:
        """ID w postaci hex: 3 znaki dla standardowego (11-bit), 8 znaków dla rozszerzonego (29-bit)."""
        return f"{self.arbitration_id:08X}" if self.is_extended else f"{self.arbitration_id:03X}"

    def data_str(self, sep: str = " ") -> str:
        return self.data.hex(sep).upper() if sep else self.data.hex().upper()

    def to_display(self) -> str:
        """Postać wyświetlana w konsoli / Live Watch, np. '187 [8] 01 00 00 00 40 7D 00 00'."""
        if self.is_remote:
            return f"{self.id_str()} [{self.dlc}] RTR"
        payload = self.data_str(" ")
        return f"{self.id_str()} [{self.dlc}] {payload}".rstrip()

    def to_match_key(self) -> str:
        """Kanoniczna postać do dopasowań ACK: 'ID#DANEHEX' lub 'ID#R'."""
        if self.is_remote:
            return f"{self.id_str()}#R"
        return f"{self.id_str()}#{self.data_str('')}"

    def sort_key(self):
        return (1 if self.is_extended else 0, self.arbitration_id)

    def __repr__(self) -> str:  # pragma: no cover - pomoc przy debugowaniu
        return f"CanFrame({self.to_match_key()})"


def _parse_can_id(id_part: str) -> Tuple[int, bool]:
    raw = id_part.strip()
    if raw.lower().startswith("0x"):
        raw = raw[2:]
    if not raw:
        raise CanFrameError("brak identyfikatora ID przed znakiem '#'")
    if not _HEX_RE.match(raw):
        raise CanFrameError(f"ID '{id_part.strip()}' nie jest liczbą szesnastkową")
    if len(raw) > 8:
        raise CanFrameError(f"ID '{raw}' jest za długie (maks. 8 cyfr hex)")
    value = int(raw, 16)
    is_ext = len(raw) == 8 or value > MAX_STD_ID
    if value > MAX_EXT_ID:
        raise CanFrameError(f"ID 0x{value:X} poza zakresem 29-bit (maks. 0x1FFFFFFF)")
    return value, is_ext


def parse_can_frame(text: str) -> CanFrame:
    """
    Parsuje ramkę w składni zbliżonej do `cansend`:
        187#01 00 00 00 40 7D 00 00   – ID standardowe, spacje dozwolone
        187#01000000407D0000          – to samo bez spacji
        18FEF100#AABB                 – ID rozszerzone (8 cyfr hex lub wartość > 0x7FF)
        65A#R  /  65A#R4              – ramka zdalna (RTR) z opcjonalnym DLC
        3D0#                          – ramka z DLC = 0
    Rzuca CanFrameError z czytelnym opisem problemu.
    """
    if text is None:
        raise CanFrameError("pusta ramka")
    s = text.strip()
    if not s:
        raise CanFrameError("pusta ramka")
    if "#" not in s:
        raise CanFrameError("brak separatora '#'. Format: ID#DANE, np. 187#01 02 03")

    id_part, data_part = s.split("#", 1)
    arb_id, is_ext = _parse_can_id(id_part)

    data_part = data_part.strip()
    if data_part[:1] in ("R", "r"):
        dlc_txt = data_part[1:].strip()
        dlc = 0
        if dlc_txt:
            if not dlc_txt.isdigit() or int(dlc_txt) > MAX_CLASSIC_DLC:
                raise CanFrameError(f"nieprawidłowy DLC ramki RTR: '{dlc_txt}' (dozwolone 0–8)")
            dlc = int(dlc_txt)
        return CanFrame(arb_id, b"", is_extended=is_ext, is_remote=True, dlc=dlc)

    compact = re.sub(r'[\s.:_\-]', '', data_part)
    if compact and not _HEX_RE.match(compact):
        raise CanFrameError(f"dane '{data_part}' zawierają znaki spoza hex")
    if len(compact) % 2 != 0:
        raise CanFrameError(f"nieparzysta liczba cyfr hex w danych ('{compact}')")
    data = bytes.fromhex(compact) if compact else b""
    if len(data) > MAX_CLASSIC_DLC:
        raise CanFrameError(f"za dużo danych: {len(data)} B (klasyczny CAN: maks. 8 bajtów)")
    return CanFrame(arb_id, data, is_extended=is_ext)


def normalize_can_id_text(id_text: str) -> str:
    """Normalizuje tekst ID do postaci wyświetlanej ('187', '18FEF100'). Zwraca '' gdy to nie jest ID."""
    try:
        value, is_ext = _parse_can_id(id_text)
    except CanFrameError:
        return ""
    return f"{value:08X}" if is_ext else f"{value:03X}"


def normalize_can_ack_pattern(pattern: str) -> str:
    """
    Normalizuje wzorzec ACK przycisku toggle do porównania (fnmatch) z CanFrame.to_match_key().
      '581#01*'      -> '581#01*'
      '0x581#01 02'  -> '581#0102*'   (brak wildcardu = dopasowanie prefiksu danych)
      '581#'         -> '581#*'       (dowolne dane z danego ID)
      '*#AA*'        -> '*#AA*'       (wildcard w ID pozostaje bez zmian)
    """
    if not pattern:
        return ""
    p = re.sub(r'\s+', '', pattern).upper()
    if "#" not in p:
        # Sam identyfikator – dowolne dane
        norm_id = normalize_can_id_text(p)
        return f"{norm_id or p}#*"
    id_part, data_part = p.split("#", 1)
    if not any(ch in id_part for ch in "*?["):
        norm_id = normalize_can_id_text(id_part)
        if norm_id:
            id_part = norm_id
    if data_part not in ("R",) and not any(ch in data_part for ch in "*?["):
        data_part = data_part + "*"
    return f"{id_part}#{data_part}"


_LINE_ID_RE = re.compile(r'(?<![0-9A-Fa-f])([0-9A-Fa-f]{8}|[0-9A-Fa-f]{3}) \[\d\]')


def extract_can_id_from_line(line: str) -> str:
    """Wyciąga ID ramki z linii konsoli w formacie '... 187 [8] 01 02 ...'. Gdy brak – próbuje potraktować tekst jako ID."""
    if not line:
        return ""
    m = _LINE_ID_RE.search(line)
    if m:
        return m.group(1).upper()
    candidate = line.strip()
    if 1 <= len(candidate) <= 10:
        return normalize_can_id_text(candidate)
    return ""


def can_id_sort_key(id_text: str):
    try:
        value = int(id_text, 16)
    except (TypeError, ValueError):
        return (2, 0)
    return (1 if len(id_text) == 8 else 0, value)


# ==========================================
# KONWERSJA python-can <-> CanFrame
# ==========================================
def frame_to_can_message(frame: CanFrame):
    if not CAN_AVAILABLE:
        raise RuntimeError("Biblioteka python-can nie jest zainstalowana")
    return can.Message(
        arbitration_id=frame.arbitration_id,
        is_extended_id=frame.is_extended,
        is_remote_frame=frame.is_remote,
        dlc=frame.dlc,
        data=None if frame.is_remote else frame.data,
        is_fd=False,
    )


def can_message_to_frame(msg) -> CanFrame:
    return CanFrame(
        msg.arbitration_id,
        bytes(msg.data or b""),
        is_extended=msg.is_extended_id,
        is_remote=msg.is_remote_frame,
        dlc=msg.dlc,
        timestamp=msg.timestamp or time.time(),
    )


# ==========================================
# WĄTEK KOMUNIKACJI CAN (slcan / CANable)
# ==========================================
class CanWorker(QThread):
    """
    Odpowiednik SerialWorker dla magistrali CAN. Odbierane ramki są grupowane w paczki
    (maks. ~20 ms lub 500 ramek), aby przy dużym obciążeniu magistrali nie zalewać pętli zdarzeń GUI.
    """
    frames_received = pyqtSignal(list)   # List[CanFrame]
    error_occurred = pyqtSignal(str)
    connection_status = pyqtSignal(bool)

    BATCH_WINDOW_S = 0.02
    BATCH_MAX = 500

    def __init__(self, port: str, bitrate: int, listen_only: bool = False, interface: str = "slcan"):
        super().__init__()
        self.port = port
        self.bitrate = int(bitrate)
        self.listen_only = bool(listen_only)
        self.interface = interface
        self.bus = None
        self.is_running = False
        self._stop_requested = False
        self.tx_queue: "queue.Queue[CanFrame]" = queue.Queue()

    def run(self):
        if not CAN_AVAILABLE:
            self.error_occurred.emit(f"Brak biblioteki python-can ({CAN_IMPORT_ERROR}). Zainstaluj: pip install python-can")
            self.connection_status.emit(False)
            return
        try:
            self.bus = can.Bus(
                interface=self.interface,
                channel=self.port,
                bitrate=self.bitrate,
                listen_only=self.listen_only,
            )
        except Exception as e:
            self.error_occurred.emit(f"Błąd otwarcia adaptera CAN na {self.port}: {e}")
            self.connection_status.emit(False)
            self._safe_shutdown()
            return

        if self._stop_requested:
            self._safe_shutdown()
            return

        self.is_running = True
        self.connection_status.emit(True)

        try:
            while self.is_running:
                batch: List[CanFrame] = []
                msg = self.bus.recv(timeout=0.005)
                deadline = time.monotonic() + self.BATCH_WINDOW_S
                while msg is not None:
                    if msg.is_error_frame:
                        self.error_occurred.emit("Odebrano ramkę błędu magistrali CAN (Error Frame).")
                    else:
                        batch.append(can_message_to_frame(msg))
                    if len(batch) >= self.BATCH_MAX or time.monotonic() >= deadline:
                        break
                    msg = self.bus.recv(timeout=0)
                if batch:
                    self.frames_received.emit(batch)

                while not self.tx_queue.empty():
                    frame = self.tx_queue.get_nowait()
                    try:
                        self.bus.send(frame_to_can_message(frame), timeout=0.5)
                    except Exception as e:
                        self.error_occurred.emit(f"Błąd wysyłania ramki {frame.to_display()}: {e}")
        except Exception as e:
            self.error_occurred.emit(f"Utracono połączenie z adapterem CAN: {e}")
            self.connection_status.emit(False)
        finally:
            self.is_running = False
            self._safe_shutdown()

    def _safe_shutdown(self):
        if self.bus is not None:
            try:
                self.bus.shutdown()
            except Exception:
                pass
            self.bus = None

    def stop(self):
        self._stop_requested = True
        self.is_running = False
        self.wait()

    def send_frame(self, frame: CanFrame):
        self.tx_queue.put(frame)
