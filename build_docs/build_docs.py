import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import (QImage, QPainter, QColor, QPen, QFont, QPageSize, 
                         QPageLayout, QPdfWriter, QBrush)
from PyQt6.QtCore import Qt, QRectF, QPointF, QMarginsF

# ==============================================================================
# SKALIBROWANA KONFIGURACJA 11 SLAJDÓW (POPRAWIONE POZYCJE STRZAŁEK I ZNAKÓW)
# ==============================================================================

SLIDES_DATA = [
    {
        "title": "1. Serial Commander v1.6 — Architektura i Główny Interfejs",
        "subtitle": "Nowoczesny terminal diagnostyczny HMI / COM stworzony do pracy z systemami Embedded",
        "image_candidates": ["obraz_4.png", "Zrzut ekranu 2026-10-15 143034.png"],
        "annotations": [
            {"num": 1, "target": (0.31, 0.05), "badge": (0.31, 0.14), "color": "#37b24d"},
            {"num": 2, "target": (0.58, 0.11), "badge": (0.58, 0.03), "color": "#228be6"},
            {"num": 3, "target": (0.11, 0.45), "badge": (0.21, 0.45), "color": "#f59f00"},
            {"num": 4, "target": (0.32, 0.31), "badge": (0.26, 0.24), "color": "#fcc419"},
            {"num": 5, "target": (0.48, 0.97), "badge": (0.48, 0.88), "color": "#4dabf7"},
        ],
        "bullets": [
            "[1] Wielokartowość ze statusem Live: Zielona kropka (● COM22) oznacza aktywne połączenie, biała (○ COM20) port w spoczynku.",
            "[2] Górny Pasek Połączenia i Narzędzi: Szybki dostęp do portu, prędkości Baudrate, formatu RX (ASCII/HEX), wyszukiwarki i markerów.",
            "[3] Zwijany Panel Szybkich Akcji (PPM): 10 programowalnych przycisków (możesz go całkowicie ukryć przyciskiem '◀ Ukryj').",
            "[4] Sekcja Live Watch: Przypięte ramki telemetryczne odświeżane w miejscu ze złotym podświetleniem zmieniających się wartości.",
            "[5] Dolny Pasek Komend (TX): Wpisywanie komend bezpośrednio pod logami, obsługa historii (strzałki ↑ / ↓) oraz wybór końca linii (EOL)."
        ]
    },
    {
        "title": "2. Inteligentny Wybór Portu COM i Prędkości Baudrate",
        "subtitle": "Kompaktowy widok w spoczynku oraz pełna identyfikacja sterowników po rozwinięciu listy",
        "image_candidates": ["Zrzut ekranu 2026-10-15 144322.png"],
        "annotations": [
            {"num": 1, "target": (0.30, 0.11), "badge": (0.23, 0.11), "color": "#228be6"},
            {"num": 2, "target": (0.58, 0.20), "badge": (0.68, 0.20), "color": "#fcc419"},
            {"num": 3, "target": (0.37, 0.11), "badge": (0.37, 0.04), "color": "#69db7c"},
            {"num": 4, "target": (0.46, 0.11), "badge": (0.46, 0.04), "color": "#f59f00"},
        ],
        "bullets": [
            "[1] PortComboBox w spoczynku: Zajmuje tylko 82 px szerokości i wyświetla wyłącznie krótki kod portu (np. COM20).",
            "[2] Rozwinięta lista urządzeń: Automatycznie poszerza się do 320 px, pokazując pełną nazwę sterownika (np. STLink, CH343, FTDI).",
            "[3] Odświeżanie portów (Odśwież): Błyskawiczne skanowanie nowo podłączonych konwerterów USB-UART bez restartu aplikacji.",
            "[4] Rozbudowany Baudrate: Standardowe prędkości aż do 1 000 000 bps oraz opcja 'Własny...' na dole listy dla nietypowych zegarów UART."
        ]
    },
    {
        "title": "3. Sterowanie Liniami Sprzętowymi (DTR / RTS / Reset MCU)",
        "subtitle": "Zdalny restart mikrokontrolera i kontrola linii sterujących konwertera USB-UART",
        "image_candidates": ["Zrzut ekranu 2026-10-15 144357.png"],
        "annotations": [
            {"num": 1, "target": (0.61, 0.11), "badge": (0.55, 0.04), "color": "#fcc419"},
            {"num": 2, "target": (0.60, 0.18), "badge": (0.48, 0.18), "color": "#4dabf7"},
            {"num": 3, "target": (0.60, 0.25), "badge": (0.48, 0.25), "color": "#fa5252"},
        ],
        "bullets": [
            "[1] Ukryte Menu Sprzętowe (⚙): Umieszczone tuż obok przycisku Połącz/Rozłącz, nie zajmuje miejsca podczas standardowej pracy np. z RS-485.",
            "[2] Ręczne wysterowanie DTR i RTS: Niezależne przełączanie stanu logicznego na liniach Data Terminal Ready oraz Request To Send.",
            "[3] Impuls Reset MCU (100 ms): Jednym kliknięciem wyzwala sprzętowy restart płytki (np. ESP32 / STM32) i od razu przechwytuje logi bootloadera."
        ]
    },
    {
        "title": "4. Panel Szybkich Akcji (PPM) i Potwierdzenia Sprzętowe ACK",
        "subtitle": "5 typów przycisków sterujących oraz inteligentna weryfikacja wykonania rozkazu przez sprzęt",
        "image_candidates": ["Zrzut ekranu 2026-10-15 144053.png"],
        "annotations": [
            {"num": 1, "target": (0.18, 0.23), "badge": (0.26, 0.23), "color": "#228be6"},
            {"num": 2, "target": (0.52, 0.40), "badge": (0.76, 0.40), "color": "#fcc419"},
            {"num": 3, "target": (0.52, 0.65), "badge": (0.76, 0.65), "color": "#37b24d"},
            {"num": 4, "target": (0.56, 0.77), "badge": (0.76, 0.77), "color": "#fa5252"},
        ],
        "bullets": [
            "[1] Konfiguracja pod Prawym Przyciskiem Myszy (PPM): Kliknij PPM na dowolny przycisk po lewej stronie, aby otworzyć jego edytor.",
            "[2] 5 Trybów Pracy: Push (jednorazowy), Toggle (przełącznik ON/OFF), Hold (wciśnięty/puszczony), Trigger (pętla czasowa ms), Macro (sekwencja z sleep).",
            "[3] Sprzętowy ACK w trybie Toggle: Kolor przycisku zmieni się na Zielony (ON) lub Czerwony (OFF) TYLKO wtedy, gdy urządzenie odeśle ramkę potwierdzenia ACK!",
            "[4] Przycisk Usuń / Wyczyść: Natychmiastowo resetuje wybrany slot do stanu nieużywanego ('+ Przypisz akcję (PPM)')."
        ]
    },
    {
        "title": "5. Interaktywna Konsola: Zaznaczanie Tekstu i Menu PPM",
        "subtitle": "Błyskawiczne tworzenie filtrów, parserów oraz przypięć Live Watch wprost ze strumienia logów",
        "image_candidates": ["Zrzut ekranu 2026-10-15 144223.png"],
        "annotations": [
            {"num": 1, "target": (0.41, 0.55), "badge": (0.29, 0.55), "color": "#4dabf7"},
            {"num": 2, "target": (0.43, 0.71), "badge": (0.29, 0.71), "color": "#fcc419"},
            {"num": 3, "target": (0.43, 0.76), "badge": (0.29, 0.79), "color": "#69db7c"},
            {"num": 4, "target": (0.83, 0.92), "badge": (0.62, 0.92), "color": "#228be6"},
        ],
        "bullets": [
            "[1] WAŻNE — Zaznacz tekst w konsoli: Aby zobaczyć opcje szybkiego dodawania do Filtra i Parsera, najpierw zaznacz myszką interesujący Cię fragment logu!",
            "[2] Przypnij do Live Watch: Jednym kliknięciem PPM wyciąga nagłówek linii (np. CAN2_TX) i przypina go do tablicy telemetrycznej u góry ekranu.",
            "[3] Dodaj do Filtra / Parsera (*nazwa*): Automatycznie otacza zaznaczony tekst gwiazdkami (*CAN2_TX*), rozwija szufladę filtrów i wkleja gotowy wzorzec.",
            "[4] Inteligentny Auto-scroll: Gdy przewiniesz logi w górę, autoscroll pauzuje, a na dole pojawia się przycisk szybkiego powrotu do najnowszych linii."
        ]
    },
    {
        "title": "6. Moduł Live Watch — Telemetria i Błyski Zmian (Token Diffing)",
        "subtitle": "Podgląd zmiennych procesowych i ramek CAN w jednym miejscu bez przewijania konsoli",
        "image_candidates": ["Zrzut ekranu 2026-10-15 143034.png", "obraz_4.png"],
        "annotations": [
            {"num": 1, "target": (0.31, 0.31), "badge": (0.27, 0.24), "color": "#fcc419"},
            {"num": 2, "target": (0.84, 0.35), "badge": (0.76, 0.24), "color": "#ff922b"},
            {"num": 3, "target": (0.43, 0.31), "badge": (0.52, 0.24), "color": "#69db7c"},
            {"num": 4, "target": (0.95, 0.31), "badge": (0.95, 0.23), "color": "#4dabf7"},
        ],
        "bullets": [
            "[1] Dwa sposoby aktywacji: Ręcznie przez PPM w konsoli lub automatycznie z kodu C mikrokontrolera poprzez wysłanie znaku '@' na początku linii (np. @[IO_MGR]...).",
            "[2] Błyski zmienionych wartości (Token Diffing): Algorytm porównuje tokeny nowej i starej ramki — zmieniające się liczby (np. ADC: 531 / 13%) błyskają na złoto przez 750 ms.",
            "[3] Odciążenie głównej konsoli: Przypięte logi są domyślnie ukrywane w głównym oknie poniżej, chyba że zaznaczysz checkbox 'Pokaż też w konsoli'.",
            "[4] Zwijanie i limit 70% wysokości: Przycisk '▲ Ukryj' po prawej stronie zwija sekcję, a przy dużej liczbie wierszy (powyżej 70% konsoli) włącza się suwak."
        ]
    },
    {
        "title": "7. Filtry, Parsery Payloadu oraz Tryb Zapory (Whitelist)",
        "subtitle": "Pełna kontrola nad tym, co i w jakiej formie wyświetla się w oknie terminala",
        "image_candidates": ["Zrzut ekranu 2026-10-15 144422.png"],
        "annotations": [
            {"num": 1, "target": (0.94, 0.11), "badge": (0.94, 0.04), "color": "#228be6"},
            {"num": 2, "target": (0.85, 0.11), "badge": (0.80, 0.04), "color": "#e03131"},
            {"num": 3, "target": (0.63, 0.21), "badge": (0.75, 0.15), "color": "#fcc419"},
            {"num": 4, "target": (0.38, 0.26), "badge": (0.28, 0.35), "color": "#69db7c"},
        ],
        "bullets": [
            "[1] Szuflada Filtrów i Parserów: Rozwijana przyciskiem 'Filtry (N)', gdzie N pokazuje łączną liczbę aktywnych reguł w bieżącym profilu.",
            "[2] Tryb ▲ ZAPORA (Whitelist): Gdy aktywujesz choć jeden filtr 'Dozwolony', zapala się czerwony ostrzegawczy przycisk ZAPORA, a terminal blokuje całą resztę ruchu.",
            "[3] Trzy akcje filtrów: 'Ukryj' (wycina szum), 'Koloruj' (wyróżnia ważne linie wybranym kolorem z palety 16 barw) oraz 'Dozwolony (Whitelist)'.",
            "[4] Parsery Payloadu: Automatycznie podmieniają surowe ciągi znaków lub bajty HEX (np. *AA 01*) na czytelne komunikaty tekstowe w złotym kolorze."
        ]
    },
    {
        "title": "8. Menadżer Filtrów i Parserów — Zarządzanie Regułami",
        "subtitle": "Szybkie włączanie, wyłączanie, sortowanie i edycja reguł bez ich usuwania z profilu",
        "image_candidates": ["Zrzut ekranu 2026-10-15 143147.png"],
        "annotations": [
            {"num": 1, "target": (0.27, 0.32), "badge": (0.17, 0.32), "color": "#69db7c"},
            {"num": 2, "target": (0.43, 0.28), "badge": (0.43, 0.18), "color": "#4dabf7"},
            {"num": 3, "target": (0.68, 0.32), "badge": (0.83, 0.32), "color": "#fcc419"},
        ],
        "bullets": [
            "[1] Checkbox 'Aktywny': Pozwala tymczasowo wyłączyć dany filtr lub regułę Whitelist jednym kliknięciem, zachowując ją w pliku konfiguracyjnym .json.",
            "[2] Sortowanie po kolumnach: Kliknięcie w nagłówek tabeli ('Wzór' lub 'Akcja') sortuje listę alfabetycznie rosnąco lub malejąco.",
            "[3] Szybka edycja i usuwanie: Przyciski 'Edytuj' i 'Usuń' w każdym wierszu pozwalają zmodyfikować wzorzec lub kolor w locie."
        ]
    },
    {
        "title": "9. Symetryczny Widok Podzielony (Split View 50% / 50%)",
        "subtitle": "Równoległa diagnostyka dwóch portów COM (np. Nadajnik CAN1 i Odbiornik CAN2) na jednym ekranie",
        "image_candidates": ["Zrzut ekranu 2026-10-15 143340.png", "Zrzut ekranu 2026-10-15 144514.png"],
        "annotations": [
            {"num": 1, "target": (0.50, 0.50), "badge": (0.50, 0.35), "color": "#228be6"},
            {"num": 2, "target": (0.02, 0.17), "badge": (0.09, 0.25), "color": "#fcc419"},
            {"num": 3, "target": (0.97, 0.17), "badge": (0.89, 0.25), "color": "#fcc419"},
            {"num": 4, "target": (0.85, 0.06), "badge": (0.74, 0.06), "color": "#69db7c"},
        ],
        "bullets": [
            "[1] Sztywna symetria 50% / 50%: Obie karty mają zawsze identyczną szerokość co do piksela, niezależnie od włączonych kontrolek czy ostrzeżenia ZAPORA.",
            "[2] & [3] Skrajne rozmieszczenie przycisków Akcji: Przyciski rozwijania paneli bocznych ('▶ Akcje' i 'Akcje ◀') lądują na zewnętrznych krawędziach okna.",
            "[4] Automatyczne skalowanie okna: Wejście w Split View rozszerza okno do 1440 px, a kliknięcie 'Widok zakładek (1 okno)' zmniejsza je z powrotem do 940 px."
        ]
    },
    {
        "title": "10. Split View — Przełączanie Kart w Nagłówku (Obsługa 3+ Kart)",
        "subtitle": "Swobodny wybór dowolnej z otwartych w tle kart na lewą lub prawą połowę ekranu",
        "image_candidates": ["Zrzut ekranu 2026-10-15 144530.png"],
        "annotations": [
            {"num": 1, "target": (0.14, 0.12), "badge": (0.35, 0.12), "color": "#fcc419"},
            {"num": 2, "target": (0.28, 0.17), "badge": (0.39, 0.17), "color": "#69db7c"},
            {"num": 3, "target": (0.17, 0.06), "badge": (0.17, 0.02), "color": "#4dabf7"},
        ],
        "bullets": [
            "[1] Wybór karty w miejscu nazwy profilu: Kliknięcie w nagłówek '[LEWA] ● COM22 — Profil: COM22.json ▾' otwiera menu przełączania przypisanego okna.",
            "[2] Inteligentne filtrowanie menu: Lista pokazuje wyłącznie pozostałe otwarte karty (pomijając kartę aktualnie widoczną w tym oknie, by nie wprowadzać chaosu).",
            "[3] Błyskawiczna zamiana miejscami (Swap ⇄): Przycisk '⇄ Zamień miejscami' na górnej belce (lub wybór sąsiedniej karty z menu) natychmiast zamienia lewe okno z prawym."
        ]
    },
    {
        "title": "11. Profile Konfiguracji (cfg/), Narzędzia Raportowe i Eksport Logów",
        "subtitle": "Trwały zapis ustawień stanowiskowych, eksport do HTML/Markdown oraz obsługa z linii komend (CLI)",
        "image_candidates": ["Zrzut ekranu 2026-10-15 143355.png"],
        "annotations": [
            {"num": 1, "target": (0.06, 0.17), "badge": (0.15, 0.25), "color": "#fcc419"},
            {"num": 2, "target": (0.93, 0.17), "badge": (0.83, 0.25), "color": "#fcc419"},
            {"num": 3, "target": (0.08, 0.97), "badge": (0.08, 0.88), "color": "#69db7c"},
            {"num": 4, "target": (0.26, 0.21), "badge": (0.26, 0.13), "color": "#4dabf7"},
        ],
        "bullets": [
            "[1] & [2] Rozwinięte panele na skrajach w Split View: Pełny dostęp do 20 przycisków szybkich akcji jednocześnie przy zachowaniu sąsiadujących konsol w centrum.",
            "[3] Zarządzanie Profilami (cfg/*.json): Automatyczny, atomowy zapis konfiguracji portu, przycisków, filtrów i przypięć Live Watch dla każdego urządzenia.",
            "[4] Eksport Logów (HTML / MD / TXT) i Markery: Zapis przebiegu sesji z metryczką diagnostyczną (Data, Wersja, Port) i pełnym zachowaniem kolorów w formacie HTML/MD."
        ]
    }
]


def find_image_path(candidates):
    for name in candidates:
        if os.path.exists(name):
            return name
    return None


def draw_annotated_image(img_path, annotations):
    """Wczytuje zrzut ekranu i rysuje na nim strzałki oraz ponumerowane kółka (1, 2, 3...)."""
    image = QImage(img_path).convertToFormat(QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    w = image.width()
    h = image.height()
    radius = max(14, int(min(w, h) * 0.022))

    font = QFont("Segoe UI", int(radius * 0.75), QFont.Weight.Bold)
    painter.setFont(font)

    for ann in annotations:
        tx, ty = ann["target"][0] * w, ann["target"][1] * h
        bx, by = ann["badge"][0] * w, ann["badge"][1] * h
        col = QColor(ann.get("color", "#fcc419"))

        # Linia łącząca z czarną obwódką dla kontrastu na ciemnym tle
        pen_bg = QPen(QColor(0, 0, 0, 220), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_bg)
        painter.drawLine(QPointF(bx, by), QPointF(tx, ty))

        pen_fg = QPen(col, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_fg)
        painter.drawLine(QPointF(bx, by), QPointF(tx, ty))

        # Punkt docelowy (kropka z obwódką)
        painter.setBrush(QBrush(col))
        painter.setPen(QPen(QColor("#000000"), 2))
        painter.drawEllipse(QPointF(tx, ty), 6, 6)

        # Kółko z numerem (Badge)
        painter.setBrush(QBrush(col))
        painter.setPen(QPen(QColor("#18181b"), 3))
        badge_rect = QRectF(bx - radius, by - radius, radius * 2, radius * 2)
        painter.drawEllipse(badge_rect)

        # Numer wewnątrz kółka
        painter.setPen(QColor("#000000") if col.lightness() > 130 else QColor("#ffffff"))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, str(ann["num"]))

    painter.end()
    return image


def generate_pdf(output_pdf="Serial_Commander_Instrukcja.pdf"):
    writer = QPdfWriter(output_pdf)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape)
    writer.setResolution(300)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))

    painter = QPainter(writer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    pw = writer.width()
    ph = writer.height()

    for idx, slide in enumerate(SLIDES_DATA):
        if idx > 0:
            writer.newPage()

        # Ciemne tło slajdu (#18181b)
        painter.fillRect(0, 0, pw, ph, QColor("#18181b"))

        # Górny pasek akcentowy
        painter.fillRect(0, 0, pw, int(ph * 0.012), QColor("#228be6"))

        # Nagłówek slajdu
        margin_x = int(pw * 0.04)
        title_font = QFont("Segoe UI", 18, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRectF(margin_x, ph * 0.025, pw - 2 * margin_x, ph * 0.055),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, slide["title"])

        sub_font = QFont("Segoe UI", 11, QFont.Weight.Normal)
        painter.setFont(sub_font)
        painter.setPen(QColor("#74c0fc"))
        painter.drawText(QRectF(margin_x, ph * 0.072, pw - 2 * margin_x, ph * 0.04),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, slide["subtitle"])

        # Zrzut ekranu z adnotacjami (Środek slajdu: 12% -> 71% wysokości)
        img_path = find_image_path(slide["image_candidates"])
        img_box = QRectF(margin_x, ph * 0.12, pw - 2 * margin_x, ph * 0.58)

        if img_path:
            annotated_img = draw_annotated_image(img_path, slide["annotations"])
            scaled_img = annotated_img.scaled(
                int(img_box.width()), int(img_box.height()),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            ix = img_box.x() + (img_box.width() - scaled_img.width()) / 2
            iy = img_box.y() + (img_box.height() - scaled_img.height()) / 2

            # Ramka wokół zrzutu
            painter.setPen(QPen(QColor("#3f3f46"), 4))
            painter.drawRect(QRectF(ix - 2, iy - 2, scaled_img.width() + 4, scaled_img.height() + 4))
            painter.drawImage(QPointF(ix, iy), scaled_img)
        else:
            painter.setPen(QPen(QColor("#fa5252"), 2, Qt.PenStyle.DashLine))
            painter.drawRect(img_box)
            painter.drawText(img_box, Qt.AlignmentFlag.AlignCenter,
                             f"Brak pliku obrazu: {slide['image_candidates'][0]}")

        # Sekcja opisów punktowych na dole slajdu (72% -> 96% wysokości)
        desc_box = QRectF(margin_x, ph * 0.72, pw - 2 * margin_x, ph * 0.24)
        painter.fillRect(desc_box, QColor("#202026"))
        painter.setPen(QPen(QColor("#2f2f37"), 2))
        painter.drawRect(desc_box)

        bullet_font = QFont("Segoe UI", 9)
        painter.setFont(bullet_font)
        painter.setPen(QColor("#e4e4e7"))

        bullets = slide["bullets"]
        line_h = desc_box.height() / max(len(bullets), 1)
        for b_idx, b_text in enumerate(bullets):
            by = desc_box.y() + b_idx * line_h
            text_rect = QRectF(desc_box.x() + 25, by, desc_box.width() - 50, line_h)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                             f"•  {b_text}")

        # Stopka ze stroną
        footer_font = QFont("Segoe UI", 8)
        painter.setFont(footer_font)
        painter.setPen(QColor("#71717a"))
        painter.drawText(QRectF(margin_x, ph * 0.965, pw - 2 * margin_x, ph * 0.03),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         f"Serial Commander v1.6.0 — Dokumentacja Techniczna  |  Slajd {idx + 1} / {len(SLIDES_DATA)}")

    painter.end()
    print(f"[OK] Wygenerowano dokumentację PDF: {output_pdf}")


def generate_pptx(output_pptx="Serial_Commander_Prezentacja.pptx"):
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
    except ImportError:
        print("[INFO] Pominięto generowanie .pptx (zainstaluj pakiet: pip install python-pptx)")
        return

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    os.makedirs("annotated_tmp", exist_ok=True)

    for idx, slide_data in enumerate(SLIDES_DATA):
        slide = prs.slides.add_slide(blank_layout)
        bg = slide.background
        fill = bg.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor(24, 24, 27)

        # Tytuł i podtytuł
        tb = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(12.3), Inches(0.9))
        tf = tb.text_frame
        p1 = tf.paragraphs[0]
        p1.text = slide_data["title"]
        p1.font.size = Pt(22)
        p1.font.bold = True
        p1.font.color.rgb = RGBColor(255, 255, 255)

        p2 = tf.add_paragraph()
        p2.text = slide_data["subtitle"]
        p2.font.size = Pt(13)
        p2.font.color.rgb = RGBColor(116, 192, 252)

        # Obraz z adnotacjami
        img_path = find_image_path(slide_data["image_candidates"])
        if img_path:
            ann_img = draw_annotated_image(img_path, slide_data["annotations"])
            tmp_file = os.path.join("annotated_tmp", f"slide_{idx+1}.png")
            ann_img.save(tmp_file)
            slide.shapes.add_picture(tmp_file, Inches(1.2), Inches(1.1), height=Inches(4.2))

        # Punkty opisowe na dole
        tb_desc = slide.shapes.add_textbox(Inches(0.5), Inches(5.4), Inches(12.3), Inches(1.9))
        tf_desc = tb_desc.text_frame
        tf_desc.word_wrap = True
        for b_idx, b_text in enumerate(slide_data["bullets"]):
            p = tf_desc.paragraphs[0] if b_idx == 0 else tf_desc.add_paragraph()
            p.text = f"• {b_text}"
            p.font.size = Pt(11)
            p.font.color.rgb = RGBColor(228, 228, 231)

    prs.save(output_pptx)
    print(f"[OK] Wygenerowano prezentację PowerPoint: {output_pptx}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    generate_pdf("Serial_Commander_Instrukcja.pdf")
    generate_pptx("Serial_Commander_Prezentacja.pptx")