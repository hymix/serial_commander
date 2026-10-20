from __future__ import annotations
import usb.core
import usb.util
import libusb_package

def check_candlelight_usb() -> bool:
    print("Szukanie urządzenia candleLight (1D50:606F)...")
    if hasattr(libusb_package, "get_libusb1_backend"):
        backend = libusb_package.get_libusb1_backend()
    elif hasattr(libusb_package, "get_usb_backend"):
        backend = libusb_package.get_usb_backend()
    else:
        backend = None

    dev = usb.core.find(idVendor=0x1D50, idProduct=0x606F, backend=backend)
    
    if dev is None:
        print("[BŁĄD] Nie znaleziono urządzenia 1D50:606F!")
        return False
        
    print(f"[OK] Wykryto urządzenie: Bus {dev.bus}, Address {dev.address}")
    try:
        mfg = usb.util.get_string(dev, dev.iManufacturer)
        prod = usb.util.get_string(dev, dev.iProduct)
        sn = usb.util.get_string(dev, dev.iSerialNumber)
        print(f"     Manufacturer: {mfg}")
        print(f"     Product:      {prod}")
        print(f"     Serial:       {sn}")
        print("[SUKCES] Niskopoziomowy dostęp przez WinUSB + libusb działa!")
        return True
    except (usb.core.USBError, ValueError) as e:
        print(f"[BŁĄD DOSTĘPU USB] {e}")
        return False

if __name__ == "__main__":
    check_candlelight_usb()

