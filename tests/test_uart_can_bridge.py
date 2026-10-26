from __future__ import annotations

"""
Test logiki mostu UART -> CAN (Nucleo, firmware can_uart_bridge) bez sprzętu.

Sprawdza, że linie składane przez Serial Commander dla trybu UART→CAN:
  * mają poprawny prefiks magistrali i flagi FD/BRS wynikające ze standardu ramki,
  * po stronie odbiorcy (parse_can_frame, ten sam algorytm co w firmware) dają identyczną ramkę,
  * polecenia sterujące (CFG, BUS, MODE, HELP) przechodzą bez zmian,
  * błędy składni są zgłaszane przed wysłaniem.

Uruchomienie:  python tests/test_uart_can_bridge.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from can_support import (CAN_MODE_AUTO, CAN_MODE_CLASSIC, CAN_MODE_FD_BRS, CAN_MODE_FD_NO_BRS, CAN_MODE_TLV,
                         CanFrameError, parse_can_frame, build_uart_can_line, build_uart_can_cfg_line,
                         compose_uart_can_text, is_uart_can_control_command, normalize_uart_can_settings,
                         uart_can_settings_label)

FRAME_CASES = [
    # (tekst, magistrala, standard, oczekiwana linia UART)
    ("321#01 02 03", 1, CAN_MODE_AUTO, "CAN1:321#01 02 03"),
    ("321#01 02 03", 1, CAN_MODE_FD_BRS, "CAN1:321##1#01 02 03"),
    ("321#01 02 03", 2, CAN_MODE_FD_NO_BRS, "CAN2:321##0#01 02 03"),
    ("321#01 02 03", 1, CAN_MODE_TLV, "CAN1:TLV#321#0xA5#hex:01 02 03"),
    ("321#0102030405060708090A", 1, CAN_MODE_AUTO, "CAN1:321##1#01 02 03 04 05 06 07 08 09 0A"),
    ("0x18DAF110#02 10 03", 1, CAN_MODE_CLASSIC, "CAN1:18DAF110#02 10 03"),
    ("65A#R4", 1, CAN_MODE_AUTO, "CAN1:65A#R4"),
    ("65A#R", 2, CAN_MODE_AUTO, "CAN2:65A#R"),
    ("3D0#", 1, CAN_MODE_AUTO, "CAN1:3D0#"),
    ("CAN2:187#01", 1, CAN_MODE_AUTO, "CAN2:187#01"),
    ("TLV#321#0xA5#Hello", 1, CAN_MODE_AUTO, "CAN1:TLV#321#0xA5#Hello"),
]

ERROR_CASES = [
    ("321#01 02 03 04 05 06 07 08 09", CAN_MODE_CLASSIC),   # > 8 B w Classic
    ("321#123", CAN_MODE_AUTO),                              # nieparzysta liczba cyfr
    ("321##1#01", CAN_MODE_CLASSIC),                         # składnia FD w Classic
    ("65A#R", CAN_MODE_FD_BRS),                              # RTR w FD
    ("TLV#321#0xA5#Zażółć", CAN_MODE_AUTO),                  # znaki spoza ASCII
    ("321", CAN_MODE_AUTO),                                  # brak '#'
]


def same_frame(a, b) -> bool:
    return ((a.arbitration_id, a.is_extended, a.is_fd, a.bitrate_switch, a.is_remote, a.dlc, a.data)
            == (b.arbitration_id, b.is_extended, b.is_fd, b.bitrate_switch, b.is_remote, b.dlc, b.data))


def test_frames():
    for text, bus, mode, expected in FRAME_CASES:
        line, frame = build_uart_can_line(text, bus, mode)
        assert line == expected, f"{text!r} ({mode}): {line!r} != {expected!r}"
        # Odbiorca (Nucleo) parsuje linię bez prefiksu w trybie auto -> ta sama ramka
        received = parse_can_frame(line.split(":", 1)[1])
        assert same_frame(frame, received), f"{text!r}: {frame} != {received}"


def test_errors():
    for text, mode in ERROR_CASES:
        try:
            build_uart_can_line(text, 1, mode)
        except CanFrameError:
            continue
        raise AssertionError(f"brak błędu dla {text!r} ({mode})")


def test_control_commands():
    for cmd in ("CFG?", "CFG#1#FD_BRS#500k#2M", "BUS#2", "bus?", "MODE#auto", "HELP"):
        assert is_uart_can_control_command(cmd), cmd
        assert build_uart_can_line(cmd, 2, CAN_MODE_CLASSIC) == (cmd, None)
    assert not is_uart_can_control_command("321#01")
    assert build_uart_can_cfg_line(1, "FD_BRS", "500k", "2M") == "CFG#1#FD_BRS#500k#2M"
    assert build_uart_can_cfg_line(2, "FD", "1M", "8M") == "CFG#2#FD#1M"
    assert build_uart_can_cfg_line(1, "classic", "250k") == "CFG#1#CLASSIC#250k"


def test_compose_and_settings():
    assert compose_uart_can_text("321", "01 02") == "321#01 02"
    assert compose_uart_can_text("321", "") == "321#"
    assert compose_uart_can_text("", "CFG?") == "CFG?"
    assert compose_uart_can_text("321", "Hello", CAN_MODE_TLV) == "TLV#321#0xA5#Hello"
    assert compose_uart_can_text("321", "01 02", CAN_MODE_TLV) == "321#01 02"
    s = normalize_uart_can_settings({"bus": "7", "frame_mode": "xyz", "nominal": "5M"})
    assert s["bus"] == 1 and s["frame_mode"] == CAN_MODE_AUTO and s["nominal"] == "500k"
    assert uart_can_settings_label({"bus": 2, "frame_mode": CAN_MODE_FD_BRS}) == "CAN2 FD+BRS"


if __name__ == "__main__":
    test_frames()
    test_errors()
    test_control_commands()
    test_compose_and_settings()
    print(f"OK: {len(FRAME_CASES)} ramek, {len(ERROR_CASES)} błędów, polecenia sterujące i ustawienia")
