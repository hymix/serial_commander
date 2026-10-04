# Wytyczne dla AI (Gemini) - Rozwój Serial Commander

Ten dokument opisuje architekturę, zrealizowane funkcjonalności oraz zasady, których należy bezwzględnie przestrzegać podczas generowania kodu i modyfikacji tej aplikacji.

## 1. Stos technologiczny i Główne Zasady
*   **Język:** Python 3
*   **GUI:** `PyQt6` (bezwzględny wymóg, nie używać PyQt5, PySide ani Tkinter).
*   **Port Szeregowy:** `pyserial`.
*   **Wątki:** Interfejs użytkownika i obsługa portu COM są ściśle odseparowane. Komunikacja sprzętowa musi odbywać się w wątku pobocznym (`QThread`) z użyciem mechanizmu sygnałów i slotów (`pyqtSignal`), aby zapobiec blokowaniu GUI (zamrażaniu okna).
*   **Zarządzanie stanem okna:** Operacje wizualne (np. zmiana koloru, dopisywanie do konsoli) mogą być wykonywane **tylko** z poziomu głównego wątku (Main Thread).
*   **Zwięzłość:** Generuj tylko modyfikowane fragmenty kodu, chyba że użytkownik wyraźnie poprosi o "wygenerowanie kodu w całości".

## 2. Obecna Architektura Aplikacji

Aplikacja składa się z następujących głównych komponentów:
1.  **`MainWindow` i `SerialTab`:** Interfejs oparty o karty (`QTabWidget`). Każda karta to instancja `SerialTab` działająca w pełni niezależnie (własny COM, własna konfiguracja, własny worker).
2.  **`SerialWorker` (Dziedziczy z QThread):** Nieskończona pętla odczytująca asynchronicznie dane z bufora sprzętowego (metoda `run` oparta na `in_waiting`). Emisja sygnałów `data_received`, `connection_status`, `error_occurred`. Metoda `send_data` (thread-safe z `pyserial`).
3.  **`MacroRunner` (Dziedziczy z QThread):** Wątek asynchroniczny do wykonywania skryptów (komendy TX oddzielone `;` oraz pauzy `sleep(ms)`). Komunikuje się z panelem GUI używając sygnałów `tx_signal`, aby aktualizować logi.
4.  **System Konfiguracji (JSON) i Smart COM Allocation:** 
    *   Wsparcie dla profili przypisywanych automatycznie do portów (np. `COM3.json`). Aplikacja inteligentnie podpowiada wolne porty przy tworzeniu nowych kart.
5.  **Zarządcy (Menadżery) Tablicowi:** Konfiguracje zaawansowane korzystają z okien `QDialog` opartych na `QStackedWidget` i `QTableWidget` z przypisanymi w rzędach przyciskami (Edytuj/Usuń).

## 3. Zrealizowane Funkcjonalności (Co już działa)

### A. Dynamiczne Przyciski (10 sztuk) i System QSS
Oparte na systemie Qt Style Sheets (QSS) dynamicznie generowanym w `get_btn_style`. Posiadają efekty wciśnięcia (tzw. pressed, przesuwający padding o 2px) i podświetlenia (hover). Formularz edycji ukrywa niepotrzebne pola w zależności od typu (QStackedWidget).
*   **Nieaktywne:** Szare, nasłuchujące prawego (PPM) do edycji.
*   **Typ `toggle` (ON/OFF):** 🔘 Wysyła `tx_on` lub `tx_off`. Zmiana koloru następuje dopiero po sprzętowym ACK.
*   **Typ `push` (Jednorazowe):** ⚡ Wysyłają ramkę `tx` po kliknięciu. Brak obsługi ACK.
*   **Typ `hold` (Chwilowe):** ⏳ Wysyłają `tx_on` podczas wciśnięcia (`pressed`) i `tx_off` po puszczeniu (`released`).
*   **Typ `macro` (Skryptowe):** 📜 Odpalają ciąg komend z opóźnieniami w tle.
*   **Typ `trigger` (Sekwencyjne):** 🔁 (Bezczynny) / ⏹ (Pracuje). Pętla na obiekcie `QTimer` strzelająca asynchronicznie ramkami co zadany `interval` (w ms).

### B. Konsola Logów, Komunikacja i Eksport
*   **Dwa tryby:** ASCII oraz BINARY (HEX).
*   **Eksport Logów:** Możliwość zapisu wygenerowanej sesji do HTML (z zachowaniem kolorowania ułamków sekund), TXT oraz Markdown z wstrzykniętymi meta-danymi.
*   Zoptymalizowane globalne zamykanie aplikacji - przy zamykaniu głównego okna system pyta o zapis logów tylko raz zbiorczo, pomijając karty zawierające tylko systemowe komunikaty o połączeniu.

### C. Zaawansowane Filtrowanie RX i Zapora
*   Działa w oparciu o bibliotekę `fnmatch`. Posiada tryby "Ukryj" i "Koloruj".
*   **Tryb Zapory (Whitelist):** Trzecia akcja to "Dozwolony". Jeśli na aktywnej karcie istnieje chociaż jedna taka reguła, terminal całkowicie blokuje inne odbierane dane. Wyświetlany jest wtedy agresywny, czerwony przycisk "⚠ ZAPORA", który otwiera wyselekcjonowanego Menadżera Filtrów pokazującego tylko dozwolone reguły.


### D. Nowe funkcje (Ostatnia sesja)
*   **Oznaczanie Logów (Markers):** Każdy przycisk posiada nową flagę show_marker. Jeśli jest włączona, przycisk dołącza swoją nazwę do wysyłanego logu na konsoli (np. [Dioda ON]), co jest niezwykle użyteczne w pętlach Trigger i Macro.
*   **Sortowanie Konfiguracji:** Twarde sortowanie w pamięci po kliknięciu w nagłówki tabel (Wzór, Akcja, Zastąp) w Menedżerach Filtrów i Parserów. Sortowanie modyfikuje stan struktury JSON, dzięki czemu porządek zostaje zachowany na stałe.
*   **Nazewnictwo:** Projekt nosi oficjalną nazwę **Serial Commander**.
## 4. Wytyczne dla przyszłych iteracji (Rules for future development)

1.  **Rozszerzanie struktury JSON:** Jeśli dodajesz nowe ustawienia, dodaj je najpierw w funkcji `get_default_config()`, a następnie obsłuż ich doczytywanie ze starych plików w `load_config()` stosując bezpieczne metody `.get()`, np. `btn_cfg.get("new_feature", default_value)`.
2.  **Ramki z danymi (Binary/Hex):** Pamiętaj, że aplikacja ma służyć m.in. do testowania protokołów (np. `ot_app_msg_tlv`). Zawsze przewiduj, że użytkownik wpisze ramkę szesnastkową ze spacjami, dlatego zawsze używaj bezpiecznego parsowania: `bytes.fromhex(payload.replace(" ", ""))`.
3.  **Parsowanie RX dla przycisków:** Bufor binarnego odczytu potwierdzeń (`self.rx_buffer`) musi być niezależny od bufora tekstowego (`self.text_buffer`). Gdy przycisk (toggle) odnajdzie swoje ACK w `self.rx_buffer`, musi precyzyjnie wyciąć tylko ten zidentyfikowany ciąg bajtów (`replace(ack, b'')`), aby nie zniszczyć reszty danych. Dodatkowo bufor ma zabezpieczenie przed przepełnieniem (czyszczenie powyżej 1024 bajtów).
4.  **Autozapis:** Unikaj ciągłego, bezwarunkowego zapisu na dysk w głównej pętli. Zapisuj wywołując `self.save_current_settings_to_config(force=True)` tylko w momencie zmiany logiki konfiguracji przez usera (np. edycja przycisku, dodanie/edycja filtra).
5.  **Edycja i Kodowanie Plików:** Ze względu na polskie znaki w kodzie (np. "Połącz", "Rozłącz") i specyfikę systemu Windows, bezwzględnie unikaj używania komend terminalowych PowerShell (takich jak `Get-Content` i `Set-Content`) do modyfikacji plików tekstowych. PowerShell domyślnie niszczy kodowanie UTF-8 bez BOM powodując tzw. mojibake. Używaj wyłącznie natywnego narzędzia `replace_file_content` lub w razie konieczności krótkich skryptów Python z `encoding="utf-8"`.
## 5. Do poprawy i wdrożenia na przyszłe sesje
*   **Refaktoryzacja gui.py:** Plik staje się bardzo duży (tzw. monolith). Należy rozważyć podzielenie go na struktury MVC lub przynajmniej wyniesienie klas zdefiniowanych jako QDialog oraz komponentów pracujących w wątkach (np. MacroRunner, SerialWorker) do osobnych plików modułów (np. w folderze components/).
*   **Dodatkowa walidacja HEX:** Makra i przyciski wysyłają obecnie kod przy cichej akceptacji ewentualnych błędów. Przydałby się szerszy system raportowania użytkownikowi błędów parsowania komend (aby nie ignorować błędów wprowadzania za pomocą gołego bloku except Exception as e: pass).
*   **Rozszerzenie makr:** Warto by było dodać funkcjonalność pętli dla makr (np. loop(5)) i wsparcie dla warunkowego czekania na odpowiedź (np. wait_for(ACK_HEX, timeout)), co stworzyłoby kompletny język skryptowy testowania HMI.
