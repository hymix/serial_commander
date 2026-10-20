from __future__ import annotations

"""
Obsługa magistrali CAN i CAN FD dla Serial Commander.
Wspierane interfejsy:
  * CANable z firmware slcan (python-can, interface="slcan")
  * candleLight / STM32G4 z WinUSB (python-can, interface="candle" / gs_usb)

Moduł zawiera:
  * OtAppMsgTlv         – pakowanie/rozpakowywanie binarnej struktury ot_app_msg_tlv (<BH),
  * CanFrame            – lekka reprezentacja ramki CAN 2.0 oraz CAN FD z obsługą BRS i TLV,
  * parse_can_frame()   – parser składni cansend (ID#DANE), CAN FD (ID##1#DANE) oraz TLV (TLV#ID#TYPE#PAYLOAD),
  * normalize_can_ack_pattern() – normalizacja wzorców ACK dla przycisków typu toggle,
  * list_candle_devices() – wykrywanie urządzeń candleLight przez candle_api,
  * CanWorker(QThread)  – wątek komunikacji z adapterami CAN/CAN-FD z buforowaną emisją paczek ramek.

Zasady wątków: CanWorker nigdy nie modyfikuje bezpośrednio obiektów GUI – komunikacja wyłącznie
przez pyqtSignal, dane wychodzące przekazywane przez kolejkę FIFO queue.Queue() (tx_queue).
"""

from dataclasses import dataclass
import queue
import re
import struct
import time
from typing import List, Optional, Tuple, Union

from PyQt6.QtCore import QThread, pyqtSignal

try:
    import can  # python-can
    CAN_AVAILABLE = True
    CAN_IMPORT_ERROR = ""
except Exception as _e:  # pragma: no cover
    can = None
    CAN_AVAILABLE = False
    CAN_IMPORT_ERROR = str(_e)

try:
    import candle_api
    CANDLE_API_AVAILABLE = True
except Exception:
    candle_api = None
    CANDLE_API_AVAILABLE = False

try:
    from candle import CandleBus
    CANDLE_BUS_AVAILABLE = True
except Exception:
    CandleBus = None
    CANDLE_BUS_AVAILABLE = False

try:
    import libusb_package
    import usb.core
    import usb.util
    USB_LIB_AVAILABLE = True
except Exception:
    libusb_package = None
    USB_LIB_AVAILABLE = False

CANDLE_KNOWN_VID_PIDS = [
    (0x1D50, 0x606F),  # OpenMoko / Geschwister Schneider / candleLight
    (0x1D50, 0x606E),  # Alternatywny PID gs_usb
]


# ==========================================
# STAŁE I TYPY TRANSPORTU
# ==========================================
TRANSPORT_SERIAL = "serial"
TRANSPORT_SLCAN = "slcan"
TRANSPORT_CANDLE = "candle"

TRANSPORTS = (TRANSPORT_SERIAL, TRANSPORT_SLCAN, TRANSPORT_CANDLE)
TRANSPORT_LABELS = {
    TRANSPORT_SERIAL: "Serial (UART)",
    TRANSPORT_SLCAN: "CAN – CANable (slcan)",
    TRANSPORT_CANDLE: "CAN / CAN FD – candleLight (WinUSB / gs_usb)",
}


def is_can_transport(transport: Optional[str]) -> bool:
    """Zwraca True, jeśli wybrany transport to magistrala CAN (slcan lub candleLight)."""
    return str(transport) in (TRANSPORT_SLCAN, TRANSPORT_CANDLE)


# Prędkości nominalne (faza arbitrażu)
CAN_BITRATES = [10000, 20000, 50000, 83300, 100000, 125000, 250000, 500000, 750000, 1000000]
DEFAULT_CAN_BITRATE = 500000

# Prędkości fazy danych CAN FD (Data Bitrate / BRS)
CAN_DATA_BITRATES = [500000, 1000000, 2000000, 4000000, 5000000, 8000000]
DEFAULT_CAN_DATA_BITRATE = 2000000

# Tryby ramek CAN dla przycisków i transmisji
CAN_MODE_AUTO = "auto"
CAN_MODE_CLASSIC = "classic"
CAN_MODE_FD_BRS = "fd_brs"
CAN_MODE_FD_NO_BRS = "fd_no_brs"
CAN_MODE_TLV = "tlv"

CAN_FRAME_MODES: List[Tuple[str, str]] = [
    (CAN_MODE_AUTO, "Auto (ze składni / długości)"),
    (CAN_MODE_CLASSIC, "Klasyczny CAN 2.0 (maks. 8B, bez BRS)"),
    (CAN_MODE_FD_BRS, "CAN FD z BRS (do 64B, szybka faza danych)"),
    (CAN_MODE_FD_NO_BRS, "CAN FD bez BRS (do 64B, stała prędkość)"),
    (CAN_MODE_TLV, "Struktura TLV (ot_app_msg_tlv, 64B)"),
]

MAX_STD_ID = 0x7FF
MAX_EXT_ID = 0x1FFFFFFF
MAX_CLASSIC_DLC = 8
MAX_FD_DLC = 64

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


class CandleDeviceInfo(tuple):
    """
    Krotka (ch_id, display_label) z metadanymi stanu urządzenia candleLight.
    Dzięki dziedziczeniu z tuple zachowuje 100% zgodności wstecznej z:
      for ch_id, label in list_candle_devices():
    jednocześnie udostępniając atrybut .is_busy (True, gdy inne oprogramowanie
    zajmuje urządzenie na wyłączność przez WinUSB).
    """
    def __new__(cls, ch_id: str, label: str, is_busy: bool = False, sn: str = "", prod: str = ""):
        inst = super().__new__(cls, (ch_id, label))
        inst.ch_id = ch_id
        inst.label = label
        inst.is_busy = bool(is_busy)
        inst.sn = sn
        inst.prod = prod
        return inst


def list_candle_devices() -> List[CandleDeviceInfo]:
    """
    Zwraca listę podłączonych urządzeń candleLight w postaci obiektów CandleDeviceInfo (ch_id, display_label).
    Automatycznie rozróżnia:
      * Urządzenia wolne (is_busy=False) – gotowe do połączenia,
      * Urządzenia zajęte (is_busy=True) – fizycznie wykryte na szynie USB (VID 1D50),
        ale zablokowane na wyłączność przez inny program (np. HUD ECU Hacker, BusMaster).
    """
    result: List[CandleDeviceInfo] = []
    free_dev_count = 0

    # 1. Wykrywanie dostępnych (wolnych) urządzeń za pośrednictwem candle_api
    if CANDLE_API_AVAILABLE and candle_api is not None:
        try:
            devices = candle_api.list_device()
            for dev_idx, dev in enumerate(devices):
                sn = getattr(dev, "serial_number", "") or f"DEV{dev_idx}"
                prod = getattr(dev, "product", "") or "candleLight"
                ch_count = getattr(dev, "channel_count", 1) or 1
                free_dev_count += 1
                for ch_idx in range(ch_count):
                    ch_id = f"candle:{dev_idx}:{ch_idx}"
                    label = f"{ch_id} — {prod} (SN: {sn})"
                    result.append(CandleDeviceInfo(ch_id, label, is_busy=False, sn=sn, prod=prod))
        except Exception:
            pass

    # 2. Skan fizycznych urządzeń USB za pomocą libusb/pyusb w celu wykrycia urządzeń zajętych
    if USB_LIB_AVAILABLE and libusb_package is not None:
        try:
            raw_devices = []
            for vid, pid in CANDLE_KNOWN_VID_PIDS:
                for d in libusb_package.find(find_all=True, idVendor=vid, idProduct=pid):
                    raw_devices.append(d)

            # Jeśli fizycznych urządzeń USB jest więcej niż tych pomyślnie otwartych przez candle_api,
            # to brakujące urządzenia są zajęte przez inny proces na poziomie WinUSB
            busy_count = max(0, len(raw_devices) - free_dev_count)
            for b_idx in range(busy_count):
                busy_dev_idx = free_dev_count + b_idx
                ch_id = f"candle:{busy_dev_idx}:0"
                label = f"{ch_id} — candleLight (🔒 ZAJĘTY przez inny program)"
                result.append(CandleDeviceInfo(ch_id, label, is_busy=True, prod="candleLight (Zajęty)"))
        except Exception:
            pass

    return result


class CanFrameError(ValueError):
    """Błąd składni ramki CAN wpisanej przez użytkownika."""


# ==========================================
# STRUKTURA BINARNA TLV: ot_app_msg_tlv (<BH)
# ==========================================
TLV_HEADER_FORMAT = "<BH"
TLV_HEADER_SIZE = struct.calcsize(TLV_HEADER_FORMAT)  # 3 bajty


@dataclass
class OtAppMsgTlv:
    msg_type: int
    value: bytes

    def pack(self, pad_to_length: Optional[int] = 64) -> bytes:
        """
        Pakuje strukturę do postaci binarnej (<BH + value).
        Opcjonalnie dopełnia zerami do zadanego rozmiaru (np. 64B dla CAN FD).
        """
        length = len(self.value)
        packed = struct.pack(TLV_HEADER_FORMAT, self.msg_type, length) + self.value
        if pad_to_length is not None and len(packed) < pad_to_length:
            packed += b"\x00" * (pad_to_length - len(packed))
        return packed

    @classmethod
    def unpack(cls, data: bytes) -> Tuple[OtAppMsgTlv, bool]:
        """
        Próbuje rozpakować bufor do struktury TLV.
        Zwraca (OtAppMsgTlv, is_valid).
        """
        if len(data) < TLV_HEADER_SIZE:
            return cls(msg_type=0, value=b""), False
        msg_type, length = struct.unpack(TLV_HEADER_FORMAT, data[:TLV_HEADER_SIZE])
        if length > len(data) - TLV_HEADER_SIZE:
            return cls(msg_type=0, value=b""), False
        payload = data[TLV_HEADER_SIZE : TLV_HEADER_SIZE + length]
        return cls(msg_type=msg_type, value=payload), True

    def value_ascii(self) -> str:
        return self.value.decode("ascii", errors="replace")

    def format_display(self) -> str:
        ascii_val = self.value_ascii()
        has_non_printable = any(c < 32 or c > 126 for c in self.value)
        if has_non_printable:
            return f'TLV[0x{self.msg_type:02X}, len={len(self.value)}]: "{ascii_val}" ({self.value.hex(" ").upper()})'
        return f'TLV[0x{self.msg_type:02X}, len={len(self.value)}]: "{ascii_val}"'


# ==========================================
# RAMKA CAN / CAN FD
# ==========================================
class CanFrame:
    __slots__ = (
        "arbitration_id", "is_extended", "is_remote", "dlc", "data", "timestamp",
        "is_fd", "bitrate_switch", "error_state_indicator"
    )

    def __init__(self, arbitration_id: int, data: bytes = b"", is_extended: bool = False,
                 is_remote: bool = False, dlc: Optional[int] = None, timestamp: float = 0.0,
                 is_fd: bool = False, bitrate_switch: bool = False, error_state_indicator: bool = False):
        self.arbitration_id = int(arbitration_id)
        self.is_extended = bool(is_extended)
        self.is_remote = bool(is_remote)
        self.data = bytes(data) if not is_remote else b""
        self.dlc = int(dlc) if dlc is not None else len(self.data)
        self.timestamp = float(timestamp)
        self.is_fd = bool(is_fd)
        self.bitrate_switch = bool(bitrate_switch)
        self.error_state_indicator = bool(error_state_indicator)

    def id_str(self) -> str:
        """ID w postaci hex: 3 znaki dla standardowego (11-bit), 8 znaków dla rozszerzonego (29-bit)."""
        return f"{self.arbitration_id:08X}" if self.is_extended else f"{self.arbitration_id:03X}"

    def data_str(self, sep: str = " ") -> str:
        return self.data.hex(sep).upper() if sep else self.data.hex().upper()

    def to_display(self, show_tlv: bool = True) -> str:
        """
        Postać wyświetlana w konsoli / Live Watch, np.:
        '187 [8] 01 00 00 00 40 7D 00 00'
        '321 [64] [FD+BRS] A5 2A 00 ... | TLV[0xA5, len=42]: "SerialCommander..."'
        """
        if self.is_remote:
            return f"{self.id_str()} [{self.dlc}] RTR"
        flags = ""
        if self.is_fd:
            flags = " [FD+BRS]" if self.bitrate_switch else " [FD]"
        payload = self.data_str(" ")
        base = f"{self.id_str()} [{self.dlc}]{flags} {payload}".rstrip()
        if show_tlv and len(self.data) >= TLV_HEADER_SIZE:
            tlv, valid = OtAppMsgTlv.unpack(self.data)
            if valid and len(tlv.value) > 0:
                base = f"{base} | {tlv.format_display()}"
        return base

    def to_match_key(self) -> str:
        """Kanoniczna postać do dopasowań ACK: 'ID#DANEHEX' lub 'ID#R'."""
        if self.is_remote:
            return f"{self.id_str()}#R"
        return f"{self.id_str()}#{self.data_str('')}"

    def sort_key(self):
        return (1 if self.is_extended else 0, self.arbitration_id)

    def __repr__(self) -> str:
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


def parse_can_frame(text: str, can_mode: str = CAN_MODE_AUTO) -> CanFrame:
    """
    Parsuje ramkę w składni cansend / CAN FD / TLV:
        187#01 00 00 00 40 7D 00 00        – standardowy CAN 2.0 (do 8 bajtów)
        321#01 02 ... do 64B                – automatyczny CAN FD jeśli > 8 bajtów (BRS=True)
        321##1#01 02 03                     – CAN FD z flagą BRS (1 = BRS, 0 = no-BRS)
        321##1010203                        – CAN FD z BRS bez drugiego separatora
        TLV#321#0xA5#Tekst wiadomości       – automatyczne pakowanie w strukturę ot_app_msg_tlv (64B)
        65A#R  /  65A#R4                   – ramka zdalna (RTR) z opcjonalnym DLC
        3D0#                               – ramka z DLC = 0

    Parametr can_mode pozwala na wymuszenie standardu ramki:
        - "auto": wykrywanie automatyczne ze składni i długości
        - "classic": wymuszenie Klasycznego CAN 2.0 (błąd jeśli > 8B lub składnia '##')
        - "fd_brs": wymuszenie CAN FD z flagą BRS (do 64B)
        - "fd_no_brs": wymuszenie CAN FD bez flagi BRS (do 64B)
        - "tlv": wymuszenie struktury TLV (<BH) dopełnianej do 64B
    Rzuca CanFrameError z czytelnym opisem problemu.
    """
    if text is None:
        raise CanFrameError("pusta ramka")
    s = text.strip()
    if not s:
        raise CanFrameError("pusta ramka")

    mode = str(can_mode or CAN_MODE_AUTO).lower()

    # 1. Składnia TLV helper: TLV#<ID>#<TYPE>#<PAYLOAD>
    if s.upper().startswith("TLV#"):
        if mode == CAN_MODE_CLASSIC:
            raise CanFrameError("Ramka TLV wymaga standardu CAN FD (64B). W trybie 'Klasyczny CAN 2.0' ramki TLV nie są dozwolone.")
        parts = s.split("#", 3)
        if len(parts) < 4:
            raise CanFrameError("niepełna składnia TLV. Wymagane: TLV#<ID>#<TYPE>#<PAYLOAD>, np. TLV#321#0xA5#Hello")
        _, id_txt, type_txt, payload_txt = parts
        arb_id, is_ext = _parse_can_id(id_txt)
        type_str = type_txt.strip()
        try:
            msg_type = int(type_str, 16) if type_str.lower().startswith("0x") else int(type_str)
            if not (0 <= msg_type <= 0xFF):
                raise ValueError()
        except ValueError:
            raise CanFrameError(f"nieprawidłowy typ TLV '{type_str}' (wymagany bajt 0-255 lub 0x00-0xFF)")

        payload_txt = payload_txt.strip()
        # Jeśli payload to ciąg hex ze spacjami i zaczyna się od 'hex:', potraktuj jako bajty
        if payload_txt.lower().startswith("hex:"):
            hex_clean = re.sub(r'[\s.:_\-]', '', payload_txt[4:])
            val_bytes = bytes.fromhex(hex_clean)
        else:
            val_bytes = payload_txt.encode('utf-8')

        tlv = OtAppMsgTlv(msg_type=msg_type, value=val_bytes)
        packed_data = tlv.pack(pad_to_length=MAX_FD_DLC)
        brs_for_tlv = False if mode == CAN_MODE_FD_NO_BRS else True
        return CanFrame(
            arbitration_id=arb_id,
            data=packed_data,
            is_extended=is_ext,
            is_fd=True,
            bitrate_switch=brs_for_tlv,
            dlc=len(packed_data)
        )

    if "#" not in s:
        raise CanFrameError("brak separatora '#'. Format: ID#DANE, np. 187#01 02 03 lub TLV#321#0xA5#Dane")

    # 2. Składnia CAN FD z podwójnym ##: ID##<FLAGS>#<DATA> lub ID##<FLAGS><DATA>
    is_fd_explicit = False
    brs_flag = False
    if "##" in s:
        if mode == CAN_MODE_CLASSIC:
            raise CanFrameError("W trybie 'Klasyczny CAN 2.0' nie można używać składni CAN FD '##'. Zmień '##' na '#' lub zmień standard ramki na CAN FD.")
        is_fd_explicit = True
        id_part, data_part = s.split("##", 1)
        data_part = data_part.strip()
        # Pierwszy znak to flaga (0 = brak BRS, 1 = BRS)
        if data_part and data_part[0] in ("0", "1"):
            brs_flag = (data_part[0] == "1")
            data_part = data_part[1:].lstrip("#").strip()
    else:
        id_part, data_part = s.split("#", 1)

    arb_id, is_ext = _parse_can_id(id_part)
    data_part = data_part.strip()

    # Obsługa RTR (tylko klasyczny CAN)
    if data_part[:1] in ("R", "r"):
        if is_fd_explicit or mode in (CAN_MODE_FD_BRS, CAN_MODE_FD_NO_BRS, CAN_MODE_TLV):
            raise CanFrameError("ramki zdalne (RTR) nie są obsługiwane w standardzie CAN FD")
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
        raise CanFrameError(f"nieparzysta liczba cyfr hex w danych ('{compact}', długość: {len(compact)}). Każdy bajt w CAN to 2 cyfry hex (np. '{compact}0' lub '0{compact}').")

    data = bytes.fromhex(compact) if compact else b""

    # Wymuszenie trybu w zależności od wybranego can_mode
    if mode == CAN_MODE_CLASSIC:
        if len(data) > MAX_CLASSIC_DLC:
            raise CanFrameError(f"W trybie 'Klasyczny CAN 2.0' dopuszczalne jest maksymalnie 8 bajtów (wpisano: {len(data)} B). Skróć dane lub zmień standard ramki na CAN FD.")
        return CanFrame(
            arbitration_id=arb_id,
            data=data,
            is_extended=is_ext,
            is_fd=False,
            bitrate_switch=False
        )

    if mode == CAN_MODE_FD_BRS:
        if len(data) > MAX_FD_DLC:
            raise CanFrameError(f"za dużo danych: {len(data)} B (maksimum CAN FD: 64 bajty)")
        return CanFrame(
            arbitration_id=arb_id,
            data=data,
            is_extended=is_ext,
            is_fd=True,
            bitrate_switch=True
        )

    if mode == CAN_MODE_FD_NO_BRS:
        if len(data) > MAX_FD_DLC:
            raise CanFrameError(f"za dużo danych: {len(data)} B (maksimum CAN FD: 64 bajty)")
        return CanFrame(
            arbitration_id=arb_id,
            data=data,
            is_extended=is_ext,
            is_fd=True,
            bitrate_switch=False
        )

    if mode == CAN_MODE_TLV:
        tlv = OtAppMsgTlv(msg_type=0xA5, value=data)
        packed_data = tlv.pack(pad_to_length=MAX_FD_DLC)
        return CanFrame(
            arbitration_id=arb_id,
            data=packed_data,
            is_extended=is_ext,
            is_fd=True,
            bitrate_switch=True,
            dlc=len(packed_data)
        )

    # Domyślny tryb AUTO (wg składni / rozmiaru)
    if len(data) > MAX_FD_DLC:
        raise CanFrameError(f"za dużo danych: {len(data)} B (maksimum CAN FD: 64 bajty)")

    is_fd = is_fd_explicit or (len(data) > MAX_CLASSIC_DLC)
    if is_fd and not is_fd_explicit:
        brs_flag = True  # Domyślnie włącz BRS dla ramek o rozmiarze > 8B

    return CanFrame(
        arbitration_id=arb_id,
        data=data,
        is_extended=is_ext,
        is_fd=is_fd,
        bitrate_switch=brs_flag
    )


def convert_can_frame_text(text: str, target_mode: str) -> str:
    """
    Konwertuje tekst komendy ramki CAN pomiędzy standardami (Classic, FD z BRS, FD bez BRS, TLV).
    np.
        '187#01 02'         -> '187##1#01 02' (dla fd_brs)
        '187##1#01 02'      -> '187#01 02'    (dla classic)
        '321#01 02 ... 64B' -> '321#01 02 03 04 05 06 07 08' (dla classic, przycięte do 8B)
        '187#01 02'         -> 'TLV#187#0xA5#01 02' (dla tlv)
    """
    if not text:
        return ""
    s = text.strip()
    target = str(target_mode or CAN_MODE_AUTO).lower()

    if s.upper().startswith("TLV#"):
        parts = s.split("#", 3)
        id_part = parts[1] if len(parts) > 1 else "321"
        data_part = "01 02 03 04"
    elif "##" in s:
        id_part, rest = s.split("##", 1)
        rest = rest.strip()
        if rest and rest[0] in ("0", "1"):
            data_part = rest[1:].lstrip("#").strip()
        else:
            data_part = rest
    elif "#" in s:
        id_part, data_part = s.split("#", 1)
        data_part = data_part.strip()
    else:
        id_part = s
        data_part = "01 02 03 04"

    id_part = id_part.strip()
    compact = re.sub(r'[\s.:_\-]', '', data_part)
    if compact and len(compact) % 2 == 0:
        formatted_hex = " ".join(compact[i:i+2] for i in range(0, len(compact), 2)).upper()
    else:
        formatted_hex = data_part.upper()

    if target == CAN_MODE_CLASSIC:
        if compact and len(compact) > 16:
            formatted_hex = " ".join(compact[i:i+2] for i in range(0, 16, 2)).upper()
        return f"{id_part}#{formatted_hex or '01 02 03 04'}"
    elif target == CAN_MODE_FD_BRS:
        return f"{id_part}##1#{formatted_hex or '01 02 03 04'}"
    elif target == CAN_MODE_FD_NO_BRS:
        return f"{id_part}##0#{formatted_hex or '01 02 03 04'}"
    elif target == CAN_MODE_TLV:
        return f"TLV#{id_part}#0xA5#{data_part or 'Wiadomość TLV'}"
    else:
        return f"{id_part}#{formatted_hex}"


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


_LINE_ID_RE = re.compile(r'(?<![0-9A-Fa-f])([0-9A-Fa-f]{8}|[0-9A-Fa-f]{3}) \[\d+\]')


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
        is_fd=frame.is_fd,
        bitrate_switch=frame.bitrate_switch,
        error_state_indicator=frame.error_state_indicator,
    )


def can_message_to_frame(msg) -> CanFrame:
    return CanFrame(
        arbitration_id=msg.arbitration_id,
        data=bytes(msg.data or b""),
        is_extended=bool(msg.is_extended_id),
        is_remote=bool(msg.is_remote_frame),
        dlc=msg.dlc,
        timestamp=msg.timestamp or time.time(),
        is_fd=bool(getattr(msg, "is_fd", False)),
        bitrate_switch=bool(getattr(msg, "bitrate_switch", False)),
        error_state_indicator=bool(getattr(msg, "error_state_indicator", False)),
    )


# ==========================================
# WĄTEK KOMUNIKACJI CAN (slcan / candleLight)
# ==========================================
class CanWorker(QThread):
    """
    Wątek komunikacji sprzętowej z magistralą CAN / CAN FD.
    Obsługuje adaptery:
      - slcan (CANable)
      - candle (candleLight / WinUSB / gs_usb)
    Odbierane ramki są buforowane w paczki (maks. ~20 ms lub 500 ramek),
    aby przy dużym ruchu na magistrali nie obciążać pętli zdarzeń GUI.
    Echo własnych ramek TX jest bezpiecznie odfiltrowywane.
    """
    frames_received = pyqtSignal(list)   # List[CanFrame]
    error_occurred = pyqtSignal(str)
    connection_status = pyqtSignal(bool)

    BATCH_WINDOW_S = 0.02
    BATCH_MAX = 500

    def __init__(self, port: str, bitrate: int, listen_only: bool = False,
                 interface: str = "slcan", data_bitrate: int = DEFAULT_CAN_DATA_BITRATE,
                 fd: bool = False, sample_point: float = 80.0, data_sample_point: float = 80.0):
        super().__init__()
        self.port = str(port)
        self.bitrate = int(bitrate)
        self.data_bitrate = int(data_bitrate)
        self.listen_only = bool(listen_only)
        self.interface = str(interface)
        self.fd = bool(fd)
        self.sample_point = float(sample_point)
        self.data_sample_point = float(data_sample_point)
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
            if self.interface == TRANSPORT_CANDLE:
                # Otwarcie przez natywny backend candle
                channel_idx = 0
                if self.port.startswith("candle:"):
                    parts = self.port.split(":")
                    if len(parts) >= 3 and parts[2].isdigit():
                        channel_idx = int(parts[2])
                elif self.port.isdigit():
                    channel_idx = int(self.port)

                self.bus = can.Bus(
                    interface="candle",
                    channel=channel_idx,
                    bitrate=self.bitrate,
                    sample_point=self.sample_point,
                    data_bitrate=self.data_bitrate,
                    data_sample_point=self.data_sample_point,
                    fd=self.fd,
                    listen_only=self.listen_only,
                )
            else:
                # Domyślny tryb slcan (CANable)
                self.bus = can.Bus(
                    interface="slcan",
                    channel=self.port,
                    bitrate=self.bitrate,
                    listen_only=self.listen_only,
                )
        except Exception as e:
            err_str = str(e)
            if any(term in err_str.lower() for term in ("access denied", "cannot open device", "permission", "busy")):
                self.error_occurred.emit(
                    f"Błąd otwarcia adaptera {self.interface} ({self.port}): Urządzenie jest zablokowane lub używane przez inną aplikację (Access Denied / Busy)."
                )
            else:
                self.error_occurred.emit(f"Błąd otwarcia adaptera CAN ({self.interface}) na {self.port}: {e}")
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
                        # Pomijamy wyłącznie potwierdzenia echo własnych ramek TX (dla gs_usb: echo_id != GS_USB_NONE_ECHO_ID)
                        echo_id = getattr(msg, "echo_id", None)
                        if echo_id is not None and echo_id != 0xFFFFFFFF:
                            pass
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
                device = getattr(self.bus, "_device", None)
                self.bus.shutdown()
                if device is not None and hasattr(device, "close"):
                    try:
                        device.close()
                    except Exception:
                        pass
            except Exception:
                pass
            self.bus = None

    def stop(self):
        self._stop_requested = True
        self.is_running = False
        self.wait()

    def send_frame(self, frame: CanFrame):
        self.tx_queue.put(frame)
