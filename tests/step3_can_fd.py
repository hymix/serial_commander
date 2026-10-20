from __future__ import annotations
import sys
import time
import struct
from dataclasses import dataclass
import can
from candle import CandleBus

# ==============================================================================
# STRUKTURA BINARNA TLV: ot_app_msg_tlv (Little-Endian: <BH)
# typedef struct __attribute__((packed)) {
#     uint8_t  type;       // 1 bajt (typ wiadomości)
#     uint16_t length;     // 2 bajty (długość pola value)
#     uint8_t  value[];    // Payload (do 61 bajtów w pojedynczej ramce CAN FD 64B)
# } ot_app_msg_tlv;
# ==============================================================================

TLV_HEADER_FORMAT = "<BH"
TLV_HEADER_SIZE = struct.calcsize(TLV_HEADER_FORMAT)  # 3 bajty

@dataclass
class OtAppMsgTlv:
    msg_type: int
    value: bytes

    def pack(self, pad_to_length: int | None = 64) -> bytes:
        """
        Pakuje strukturę do postaci binarnej.
        Opcjonalnie dopełnia zerami do zadanej długości (np. 64B dla CAN FD).
        """
        length = len(self.value)
        packed = struct.pack(TLV_HEADER_FORMAT, self.msg_type, length) + self.value
        if pad_to_length is not None and len(packed) < pad_to_length:
            packed += b"\x00" * (pad_to_length - len(packed))
        return packed

    @classmethod
    def unpack(cls, data: bytes) -> tuple[OtAppMsgTlv, bool]:
        """
        Próbuje rozpakować bufor do struktury TLV.
        Zwraca (OtAppMsgTlv, is_valid).
        """
        if len(data) < TLV_HEADER_SIZE:
            return cls(msg_type=0, value=b""), False
        msg_type, length = struct.unpack(TLV_HEADER_FORMAT, data[:TLV_HEADER_SIZE])
        payload = data[TLV_HEADER_SIZE : TLV_HEADER_SIZE + length]
        is_valid = (len(payload) == length)
        return cls(msg_type=msg_type, value=payload), is_valid

# ==============================================================================
# GŁÓWNY TEST CAN FD (500 kbps Nominal / 2 Mbps Data, BRS=True)
# ==============================================================================

def run_can_fd_test(duration: float = 25.0, nominal_bitrate: int = 500_000,
                    data_bitrate: int = 2_000_000, sample_point: float = 80.0) -> None:
    print("=" * 70)
    print(f"FAZA 4: Test CAN FD (Nominal: {nominal_bitrate/1e3:.0f} kbps, Data: {data_bitrate/1e3:.0f} kbps, BRS: True)")
    print(f"        Punkt próbkowania (Sample Point): {sample_point:.1f}% (standard CiA 601-1)")
    print("        oraz binarnej struktury ot_app_msg_tlv (64 bajty)")
    print("=" * 70)

    try:
        print(f"[INIT] Inicjalizacja magistrali CAN FD (Nominal: {nominal_bitrate}, Data: {data_bitrate}, SP: {sample_point}%)...")
        bus = can.Bus(
            interface="candle",
            channel=0,
            bitrate=nominal_bitrate,
            sample_point=sample_point,
            data_bitrate=data_bitrate,
            data_sample_point=sample_point,
            fd=True
        )
        print("[OK] Magistrala CAN FD otwarta pomyślnie.")
    except Exception as e:
        print(f"[BŁĄD INICJALIZACJI CAN FD] {e}")
        return

    try:
        # 1. Przygotowanie przykładowej wiadomości TLV
        sample_payload = b"SerialCommander CAN FD TLV payload test #1"
        tlv_out = OtAppMsgTlv(msg_type=0xA5, value=sample_payload)
        packed_data = tlv_out.pack(pad_to_length=64)

        print("\n[TLV PACK] Przygotowano strukturę ot_app_msg_tlv:")
        print(f"  Type   : 0x{tlv_out.msg_type:02X} ({tlv_out.msg_type})")
        print(f"  Length : {len(tlv_out.value)} bajtów (Little-Endian)")
        print(f"  Value  : {tlv_out.value.decode('ascii', errors='replace')}")
        print(f"  Rozmiar całkowity ramki: {len(packed_data)} bajtów")

        # 2. Tworzenie i wysłanie ramki CAN FD z flagą BRS (Bitrate Switch)
        tx_msg = can.Message(
            arbitration_id=0x321,
            is_extended_id=False,
            is_fd=True,
            bitrate_switch=True,
            data=packed_data
        )

        print(f"\n[TX -> BUS] Nadawanie ramki CAN FD:")
        print(f"  ID: 0x{tx_msg.arbitration_id:03X} | FD: {tx_msg.is_fd} | BRS: {tx_msg.bitrate_switch} | DLC/Bytes: {len(packed_data)}")
        print(f"  Hex (pierwsze 16B): {packed_data[:16].hex(' ').upper()} ...")

        bus.send(tx_msg)
        print("[TX -> BUS] Ramka wysłana do bufora kontrolera.")

        # 3. Pętla nasłuchu
        print(f"\n[NASŁUCH] Rozpoczynam nasłuch magistrali CAN FD przez {duration:.1f} s...")
        print("          (Wyślij teraz ramkę CAN FD ze sniffera, np. o ID 0x322)")

        start_time = time.time()
        received_count = 0
        echo_count = 0

        while (time.time() - start_time) < duration:
            rx_msg = bus.recv(timeout=0.5)
            if rx_msg is not None:
                is_echo = (getattr(rx_msg, "echo_id", None) is not None and rx_msg.echo_id != 0xFFFFFFFF)
                if is_echo:
                    echo_count += 1
                    print(f"  [ECHO TX] ID=0x{rx_msg.arbitration_id:03X} FD={rx_msg.is_fd} BRS={rx_msg.bitrate_switch} Bajtów={len(rx_msg.data)} (Echo własnej ramki)")
                else:
                    received_count += 1
                    ext_str = "EXT" if rx_msg.is_extended_id else "STD"
                    fd_str = "CAN-FD" if rx_msg.is_fd else "CAN-2.0"
                    brs_str = "BRS" if rx_msg.bitrate_switch else "NO-BRS"
                    print(f"\n  [RX <---] ID=0x{rx_msg.arbitration_id:03X} [{ext_str}] [{fd_str}] [{brs_str}] Rozmiar={len(rx_msg.data)}B")
                    print(f"            Hex: {rx_msg.data.hex(' ').upper()}")

                    # Dekodowanie struktury TLV
                    tlv_in, valid = OtAppMsgTlv.unpack(bytes(rx_msg.data))
                    if valid:
                        val_str = tlv_in.value.decode('ascii', errors='replace')
                        print(f"            [DEKODER TLV] Type=0x{tlv_in.msg_type:02X}, Length={len(tlv_in.value)}, Value=\"{val_str}\"")
                    else:
                        print("            [DEKODER TLV] Ramka nie zawiera poprawnego nagłówka TLV")

        print(f"\n[PODSUMOWANIE NASŁUCHU] Odebrano ze sniffera: {received_count}, Ramki Echo TX: {echo_count}")

    except Exception as e:
        print(f"[BŁĄD W TRAKCIE TESTU CAN FD] {e}")
    finally:
        device = getattr(bus, "_device", None)
        bus.shutdown()
        if device is not None and hasattr(device, "close"):
            try:
                device.close()
            except Exception:
                pass
        print("[SHUTDOWN] Magistrala CAN FD została bezpiecznie zamknięta.")

if __name__ == "__main__":
    d_rate = 2_000_000
    sp_val = 80.0
    if len(sys.argv) > 1:
        try:
            d_rate = int(sys.argv[1])
        except ValueError:
            pass
    if len(sys.argv) > 2:
        try:
            sp_val = float(sys.argv[2])
        except ValueError:
            pass
    run_can_fd_test(duration=25.0, nominal_bitrate=500_000, data_bitrate=d_rate, sample_point=sp_val)

