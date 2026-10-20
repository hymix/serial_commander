'''
Author: Jan Lukaszewicz j.lukaszewicz@lincor.pl
Date: 2026-10-19 15:45:59
LastEditors: Jan Lukaszewicz j.lukaszewicz@lincor.pl
LastEditTime: 2026-10-19 15:49:07
FilePath: \serial_commander\tests\step2_classic_can.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''
from __future__ import annotations
import time
import libusb_package
import usb.backend.libusb1

# Wymuszenie inicjalizacji backendu libusb-1.0 dostarczonego przez libusb_package
_backend = libusb_package.get_libusb1_backend()
usb.backend.libusb1.get_backend = lambda **kwargs: _backend

import can
from can.interfaces.gs_usb import GsUsbBus
# Zabezpieczenie przed błędem __str__ zwracającym int w python-can
GsUsbBus.__str__ = lambda self: str(self.channel_info)

def run_classic_can_test(duration: float = 10.0) -> None:
    print("=" * 60)
    print("FAZA 3: Test klasycznego CAN 2.0 (500 kbps, ID: 0x123)")
    print("=" * 60)

    try:
        print("[INIT] Otwieranie magistrali gs_usb (channel=0, bitrate=500000)...")
        bus = can.Bus(interface="gs_usb", channel=0, bitrate=500000)
        print("[OK] Magistrala CAN 2.0 otwarta pomyślnie.")
    except Exception as e:
        print(f"[BŁĄD INICJALIZACJI MAGISTRALI] {e}")
        return

    try:
        # Tworzenie ramki testowej CAN 2.0
        tx_data = bytearray([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88])
        tx_msg = can.Message(
            arbitration_id=0x123,
            is_extended_id=False,
            is_fd=False,
            dlc=8,
            data=tx_data
        )

        print(f"\n[TX -> BUS] Nadawanie ramki: ID=0x{tx_msg.arbitration_id:03X}, DLC={tx_msg.dlc}, Data={tx_data.hex(' ').upper()}")
        bus.send(tx_msg)
        print("[TX -> BUS] Ramka wysłana do bufora kontrolera.")

        print(f"\n[NASŁUCH] Rozpoczynam nasłuch magistrali przez {duration:.1f} s...")
        print("          (Wyślij teraz dowolną ramkę z zewnętrznego sniffera)")
        
        start_time = time.time()
        received_count = 0
        echo_count = 0

        while (time.time() - start_time) < duration:
            rx_msg = bus.recv(timeout=0.5)
            if rx_msg is not None:
                data_hex = rx_msg.data.hex(' ').upper() if rx_msg.data else "<EMPTY>"
                is_echo = (getattr(rx_msg, "echo_id", None) is not None and rx_msg.echo_id != 0xFFFFFFFF)
                if is_echo:
                    # Echo ramki własnej (potwierdzenie sprzętowe nadania TX z gs_usb)
                    echo_count += 1
                    print(f"  [ECHO TX] ID=0x{rx_msg.arbitration_id:03X} DLC={rx_msg.dlc} Data={data_hex} (Echo własnej ramki)")
                else:
                    # Rzeczywista ramka odebrana z magistrali fizycznej
                    received_count += 1
                    ext_flag = "EXT" if rx_msg.is_extended_id else "STD"
                    print(f"  [RX <---] ID=0x{rx_msg.arbitration_id:03X} [{ext_flag}] DLC={rx_msg.dlc} Data={data_hex}")

        print(f"\n[PODSUMOWANIE NASŁUCHU] Odebrano ze sniffera: {received_count}, Ramki Echo TX: {echo_count}")

    except Exception as e:
        print(f"[BŁĄD W TRAKCIE TESTU] {e}")
    finally:
        bus.shutdown()
        print("[SHUTDOWN] Magistrala CAN została bezpiecznie zamknięta.")

if __name__ == "__main__":
    run_classic_can_test(25.0)

