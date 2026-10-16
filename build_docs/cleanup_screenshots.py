'''
Author: Jan Lukaszewicz j.lukaszewicz@lincor.pl
Date: 2026-10-15 15:11:04
LastEditors: Jan Lukaszewicz j.lukaszewicz@lincor.pl
LastEditTime: 2026-10-15 15:11:11
FilePath: \serial_commander\build_docs\cleanup_screenshots.py
'''
from __future__ import annotations

import os
import shutil

# Ustaw na True, jeśli chcesz trwale usunąć nieużywane zrzuty z dysku.
# Domyślnie (False) skrypt bezpiecznie przenosi je do podfolderu '_nieuzywane_zrzuty'.
DELETE_PERMANENTLY = False
BACKUP_DIR = "_nieuzywane_zrzuty"

# Dokładna mapa plików wykorzystywanych w 12 slajdach (build_docs.py)
REQUIRED_SCREENSHOTS = {
    "Slajd 1 (Główny interfejs)": ["obraz_4.png", "Zrzut ekranu 2026-10-15 143034.png"],
    "Slajd 2 (Lista portów COM)": ["Zrzut ekranu 2026-10-15 144322.png"],
    "Slajd 3 (Menu DTR / RTS / Reset)": ["Zrzut ekranu 2026-10-15 144357.png"],
    "Slajd 4 (Edycja przycisku ACK)": ["Zrzut ekranu 2026-10-15 144053.png"],
    "Slajd 5 (Menu PPM w konsoli)": ["Zrzut ekranu 2026-10-15 144223.png"],
    "Slajd 6 (Moduł Live Watch)": ["Zrzut ekranu 2026-10-15 143034.png", "obraz_4.png"],
    "Slajd 7 (Filtry i tryb ZAPORA)": ["Zrzut ekranu 2026-10-15 144422.png"],
    "Slajd 8 (Menadżer Filtrów)": ["Zrzut ekranu 2026-10-15 143147.png"],
    "Slajd 9 (Split View 50/50 zwinięty)": ["Zrzut ekranu 2026-10-15 143340.png", "Zrzut ekranu 2026-10-15 144514.png"],
    "Slajd 10 (Split View wybór karty)": ["Zrzut ekranu 2026-10-15 144530.png"],
    "Slajd 11 (Split View rozwinięte akcje)": ["Zrzut ekranu 2026-10-15 143355.png"],
    "Slajd 12 (Tryb Magistrali CAN)": ["zrzut_can_mode.png", "Zrzut ekranu CAN mode.png", "Zrzut ekranu 2026-10-16 CAN.png"],
}

def cleanup_screenshots():
    # Zapewnij, że pracujemy w katalogu skryptu (build_docs)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    keep_files = set()
    missing_slides = []

    print("=== 1. WERYFIKACJA ZRZUTÓW WYMAGANYCH DO DOKUMENTACJI ===")
    for slide_name, candidates in REQUIRED_SCREENSHOTS.items():
        found = None
        for cand in candidates:
            if os.path.exists(cand):
                found = cand
                keep_files.add(cand)
                break
        if found:
            print(f"  [OK]   {slide_name:<38} -> {found}")
        else:
            print(f"  [BRAK] {slide_name:<38} -> Szukano: {candidates[0]}")
            missing_slides.append((slide_name, candidates[0]))

    # Szukamy wszystkich plików graficznych zrzutów ekranu w bieżącym katalogu
    all_pngs = [
        f for f in os.listdir(".")
        if os.path.isfile(f) and f.lower().endswith(".png")
        and (f.startswith("Zrzut ekranu") or f.startswith("obraz"))
    ]

    unused_files = [f for f in all_pngs if f not in keep_files]

    print("\n=== 2. CZYSZCZENIE NIEUŻYWANYCH ZRZUTÓW EKRANU ===")
    if not unused_files:
        print("  Brak nadmiarowych zrzutów ekranu — w folderze są tylko wykorzystywane pliki!")
    else:
        if not DELETE_PERMANENTLY:
            os.makedirs(BACKUP_DIR, exist_ok=True)

        for f in unused_files:
            if DELETE_PERMANENTLY:
                os.remove(f)
                print(f"  [USUNIĘTO]    {f}")
            else:
                dst = os.path.join(BACKUP_DIR, f)
                if os.path.exists(dst):
                    os.remove(dst)
                shutil.move(f, dst)
                print(f"  [PRZENIESIONO] {f}  ->  {BACKUP_DIR}/")

    # Usunięcie tymczasowego folderu z adnotacjami PowerPointa (jeśli istnieje)
    if os.path.exists("annotated_tmp") and os.path.isdir("annotated_tmp"):
        shutil.rmtree("annotated_tmp")
        print("  [WYCZYSZCZONO] Usunięto folder tymczasowy 'annotated_tmp/'")

    print("\n=== PODSUMOWANIE ===")
    print(f"  Pozostawiono aktywnych zrzutów : {len(keep_files)}")
    print(f"  Oczyszczono zbędnych zrzutów   : {len(unused_files)}")
    if missing_slides:
        print("\n  [!] UWAGA — brakuje plików dla następujących slajdów:")
        for s_name, expected in missing_slides:
            print(f"      - {s_name}: upewnij się, że plik nazywa się '{expected}'")

if __name__ == "__main__":
    cleanup_screenshots()