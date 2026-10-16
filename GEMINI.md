# Wytyczne dla AI (Gemini) - Rozwój Serial Commander

Ten dokument opisuje architekturę, zrealizowane funkcjonalności oraz zasady, których należy bezwzględnie przestrzegać podczas generowania kodu i modyfikacji tej aplikacji.

## 1. Stos technologiczny i Główne Zasady
*   **Język i Kompatybilność:** Python 3.8 oraz nowsze (wymóg pełnej zgodności z Python 3.8+; na początku plików należy stosować `from __future__ import annotations` oraz unikać bezpośredniego subscriptingu typów wbudowanych PEP 585 bez odpowiednich importów).
*   **GUI:** `PyQt6` (bezwzględny wymóg, nie używać PyQt5, PySide ani Tkinter).
*   **Port Szeregowy i Magistrala CAN:** `pyserial` (dla UART) oraz `python-can` (dla adaptera CANable z firmware `slcan`).
*   **Architektura Wielowątkowości (Thread Safety):**
    *   Komunikacja sprzętowa z portem szeregowym (`pyserial`) odbywa się wyłącznie w dedykowanym wątku `SerialWorker(QThread)` z wykorzystaniem bezpiecznej kolejki FIFO `queue.Queue()` dla danych wychodzących (`tx_queue`).
    *   Komunikacja z magistralą CAN (`python-can`, interfejs `slcan`) odbywa się wyłącznie w wątku `CanWorker(QThread)` z buforowaną emisją paczek ramek (`frames_received(list)`) do 20 ms / 500 ramek, aby zapobiec przeciążeniu pętli zdarzeń Qt.
    *   Wątki poboczne (`SerialWorker`, `CanWorker`, `MacroRunner`) nigdy nie modyfikują bezpośrednio obiektów GUI – komunikacja z głównym wątkiem odbywa się wyłącznie przez mechanizm sygnałów i slotów (`pyqtSignal`), aby zapobiec blokowaniu GUI (zamrażaniu okna).
    *   Operacje wizualne (np. zmiana koloru, dopisywanie do konsoli) mogą być wykonywane **tylko** z poziomu głównego wątku (Main Thread).
*   **Zwięzłość:** Generuj tylko modyfikowane fragmenty kodu, chyba że użytkownik wyraźnie poprosi o "wygenerowanie kodu w całości".
*   **Edycja i Kodowanie Plików:** Ze względu na polskie znaki w kodzie (np. "Połącz", "Rozłącz") i specyfikę systemu Windows, bezwzględnie unikaj używania komend terminalowych PowerShell (takich jak `Get-Content` i `Set-Content`) do modyfikacji plików tekstowych. PowerShell domyślnie niszczy kodowanie UTF-8 bez BOM powodując tzw. mojibake. Używaj wyłącznie natywnego narzędzia `replace_file_content` lub w razie konieczności krótkich skryptów Python z `encoding="utf-8"`.
*   **Changelog:** Zawsze, gdy wprowadzane są jakiekolwiek zmiany w kodzie lub projekcie, bezwzględnie dodaj nowy wpis do pliku `changelog.md`. Wpis musi zawierać numer wersji/datę (w formacie YYYY-MM-DD) oraz zwięzły opis wprowadzonych nowości, modyfikacji lub poprawek w podziale na sekcje (*Added*, *Changed*, *Fixed*).

## 2. Architektura Aplikacji (Wersja 1.7.0)

Aplikacja składa się z następujących głównych komponentów:

1.  **`MainWindow` i Symetryczny Split View (50% / 50%):**
    *   **Zarządzanie kartami:** Zrezygnowano z trzymania kart wyłącznie w `QTabWidget` na rzecz centralnej listy `self.tab_list` oraz `QStackedWidget` (`self.view_stack`), który płynnie przełącza pomiędzy widokiem pojedynczych zakładek (Page 0: `QTabWidget`) a symetrycznym widokiem podzielonym Lewo/Prawo (Page 1: `self.split_container`).
    *   **Idealna symetria 50/50:** W widoku Split View zastosowano `QHBoxLayout` z równymi wagami (`stretch=1` dla lewej i prawej karty) oraz wymuszono `QSizePolicy.Policy.Ignored` w poziomie na `SerialTab` i `right_panel_widget`. Zapobiega to przesuwaniu osi podziału ekranu, gdy na jednej z kart pojawi się dodatkowy element (np. `⚠ ZAPORA`).
    *   **Dynamiczne skalowanie okna (`adjust_window_size_for_mode`):** Okno główne automatycznie rozszerza się do `SPLIT_WIDTH = 1440` po wejściu w widok dwóch kart i zmniejsza z powrotem do kompaktowego rozmiaru pojedynczej karty (`SINGLE_WIDTH = 940`) po powrocie do widoku zakładek (zdejmując ewentualną maksymalizację przez `showNormal()`).
    *   **Przełączanie kart w nagłówku (`SplitCardHeader`):** Każda z dwóch widocznych kart posiada nagłówek z oznaczeniem strony (`[LEWA]` / `[PRAWA]`), wskaźnikiem stanu połączenia oraz przyciskiem menu (`self.btn_card_selector`). Kliknięcie rozwija dynamiczne menu (`populate_card_switch_menu`), które wyświetla pozostałe karty w tle, **pomijając kartę aktualnie wybraną w tym oknie**. Wybór karty z drugiego okna wykonuje zamianę miejscami (`Swap ⇄`).
    *   **Menu kontekstowe na pasku zakładek (`QTabBar`):** Kliknięcie PPM na zakładkę pozwala szybko przypisać ją jako lewą lub prawą kartę w widoku podzielonym.

2.  **`SerialTab` (Wnętrze karty, ergonomia i obsługa UART / CAN):**
    *   Każda karta to w pełni niezależna instancja z własnym portem COM, konfiguracją profilu i workerem (`SerialWorker` dla UART lub `CanWorker` dla CANable slcan).
    *   **Odwrócony układ góra–dół:** Pasek połączenia (`Port`, `Baud/Bitrate`, `Połącz`, menu sprzętowe `⚙️`, formatowanie, `⚠ ZAPORA`, `🌪️ Filtry (N)`) oraz pasek narzędzi konsoli (`Wyczyść`, `Zapisz Logi`, `Marker`, `Szukaj`, `Limit`) znajdują się na samej górze. Pole wprowadzania komend (`cmd_input`) znajduje się na samym dole, bezpośrednio pod konsolą logów.
    *   **Dynamiczne dostosowanie interfejsu (`apply_transport_ui`):** W trybie UART wyświetla wybór `Baud:`, przełącznik RX ASCII/HEX oraz formaty TX i EOL. W trybie CAN ukrywa opcje znakowe i sterowanie liniami DTR/RTS, a wyświetla listę prędkości `Bitrate:` (`10k` do `1M`), menu `Listen-only` oraz placeholder `187#01 02 03`.
    *   **Skrajne rozmieszczenie paneli bocznych (`set_panel_side`):** 
        *   Karta po lewej stronie ma panel szybkich akcji po swojej lewej (zewnętrznej) krawędzi (`▶ Akcje` / `◀ Ukryj`).
        *   Karta po prawej stronie dynamicznie przebudowuje swój layout i umieszcza panel szybkich akcji po swojej prawej (zewnętrznej) krawędzi (`Akcje ◀` / `Ukryj ▶`).
        *   W widoku Split View panele boczne domyślnie się zwijają, aby obie konsole logów sąsiadowały ze sobą bezpośrednio w centrum okna.
    *   **Zwijany panel Filtrów i Parserów (`tools_frame`):** Chowany kontener sterowany przyciskiem `🌪️ Filtry (N)` na górnym pasku (`N` to suma aktywnych filtrów i parserów).
    *   **Zwijany panel Szybkich Akcji:** Możliwość całkowitego ukrycia panelu 10 przycisków makr przyciskiem `◀ Ukryj` / `▶ Akcje`, aby oddać 100% szerokości karty dla konsoli logów.

3.  **Moduł Telemetrii `📌 Live Watch` (`LiveWatchRowWidget`):**
    *   Dedykowany kontener nad główną konsolą służący do przypinania i odświeżania w jednym stałym wierszu powtarzalnych ramek diagnostycznych (np. statusów ADC, GPIO, ramek CAN/FDCAN).
    *   **Token Diffing & Flash:** Algorytm oparty o `difflib.SequenceMatcher` rozbija nową linię na tokeny słowne, liczbowe i symbole, porównuje ze stanem poprzednim i podświetla zmienione wartości (w CAN: zmienione bajty) na złoto-pomarańczowo (`#5c3c00` / `#ffd43b`) przez `FLASH_DURATION = 0.75 s`. Wygaszanie koordynuje centralny `watch_decay_timer` (co 100 ms).
    *   **Czas Cyklu Ramki $\Delta t$ (CAN):** W trybie CAN każdy wiersz wyświetla etykietę `Δ ... ms` wyliczaną na podstawie odstępu czasu od poprzedniej odebranej ramki o danym ID.
    *   **Sortowanie według CAN ID:** Automatyczne wstawianie wierszy z zachowaniem kolejności rosnącej (`insert_watch_row_sorted`), najpierw ramki 11-bit, potem 29-bit.
    *   **Podwójna aktywacja:** Automatyczne przechwytywanie w trybie UART (prefiks `@`, np. `@[IO_MGR]...`) lub w trybie CAN (`can_watch_auto: true`), a także ręczne przypinanie z menu PPM konsoli. Posiada pamięć sesyjną `_unpinned_can_ids` chroniącą przed re-pinowaniem ramek odpiętych przez usera.
    *   **Ochrona widoku konsoli:** Przypięte ramki są domyślnie ukrywane w konsoli poniżej (opcja `watch_print_in_console` w profilu). Wysokość panelu Live Watch jest ograniczona do **maks. 70% wysokości konsoli**, po przekroczeniu której włącza się pionowy suwak `QScrollArea`. Posiada przycisk zwijania `▲ Ukryj / ▼ Pokaż` oraz `Odepnij wszystkie`.

4.  **Moduł Magistrali CAN (`can_support.py`):**
    *   **`CanFrame`:** Lekka, niezależna struktura ramki CAN (obsługuje ID 11-bit, 29-bit, RTR, DLC, timestamp, `to_display()`, `to_match_key()`).
    *   **`parse_can_frame(text)`:** Parser składni w stylu `cansend` (np. `187#01 02 03`, `18FEF100#AABB`, `65A#R`, `3D0#`) z walidacją `CanFrameError`.
    *   **`CanWorker(QThread)`:** Dedykowany wątek komunikacyjny wykorzystujący `python-can` z interfejsem `slcan`. Kolejka nadawcza FIFO `tx_queue` i buforowana emisja odebranych ramek (`frames_received(list)`).

5.  **`SerialWorker` (Dziedziczy z QThread):**
    *   Nieskończona pętla odczytująca asynchronicznie dane z bufora portu COM UART (metoda `run` oparta na `in_waiting`).
    *   Bezpieczna kolejka FIFO `queue.Queue()` dla danych wychodzących (`tx_queue`).
    *   Obsługa linii sprzętowych: `set_dtr(state: bool)` oraz `set_rts(state: bool)`.
    *   Emisja sygnałów `data_received`, `connection_status`, `error_occurred`.

6.  **`MacroRunner` (Dziedziczy z QThread):**
    *   Wątek asynchroniczny do wykonywania skryptów (komendy TX oddzielone `;` oraz pauzy `sleep(ms)`). Komunikuje się z panelem GUI używając sygnału `tx_signal`. Obsługuje komendy tekstowe UART oraz ramki CAN.

6.  **System Konfiguracji (JSON) i Bezpieczeństwo Danych (`cfg/`):**
    *   **Atomowy zapis:** Wszystkie operacje zapisu (`save_config`, `save_app_settings`) zapisują dane najpierw do pliku tymczasowego `.tmp`, a następnie podmieniają plik docelowy za pomocą `os.replace()`, co zapobiega uszkodzeniu plików w razie awarii zasilania lub nagłego zamknięcia.
    *   **Kompatybilność wsteczna:** Nowe opcje (np. `watch_patterns`, `watch_print_in_console`, `eol`) muszą być zdefiniowane w `get_default_config()` i posiadać bezpieczne fallbacki w `load_config()`.
    *   **Ochrona przed odtworzeniem:** Metody `save_current_settings_to_config` oraz `on_config_changed` weryfikują `os.path.exists()`, aby nie odtwarzać skasowanych konfiguracji.
    *   Wsparcie dla profili przypisywanych automatycznie do portów (np. `COM3.json`). Aplikacja inteligentnie podpowiada wolne porty przy tworzeniu nowych kart.

7.  **Customowe Kontrolki i Dialogi:**
    *   **`PortComboBox`:** W stanie spoczynku ma stałą szerokość `82 px` i wyświetla sam port (np. `COM20`), a po rozwinięciu (`showPopup`) rozszerza się do `340 px` z pełnym opisem ze sterownika (`COM20 — USB-SERIAL CH340`). Nowo wykryte porty po odświeżeniu są podświetlane w rozwiniętej liście na zielono (`#1b4332` / `#8ce99a`) z etykietą `✨ ... [NOWY]`, a ponowne odświeżenie bez zmian usuwa podświetlenie.
    *   **`CommandLineEdit`:** Obsługuje historię komend pod strzałkami `Góra` / `Dół` i czyści się po wysłaniu.
    *   **`SearchDialog`:** Niezależne okienko wyszukiwania w logach (`Ctrl+F`) z obsługą przeszukiwania w przód/tył i symboli wieloznacznych `*` (wildcards).
    *   **Zarządcy (Menadżery) Tablicowi:** Okna `FilterManagerDialog` i `ParserManagerDialog` oparte na `QTableWidget` z opcją włączania/wyłączania ("Aktywny") oraz twardego sortowania.

8.  **Automatyzacja Dokumentacji (`build_docs/`):**
    *   **`build_docs.py`:** Generuje instrukcję PDF (`Serial_Commander_Instrukcja.pdf`) i prezentację PowerPoint (`Serial_Commander_Prezentacja.pptx`) z wektorowymi znacznikami i strzałkami.
    *   **`cleanup_screenshots.py`:** Weryfikuje obecność wymaganych grafik i archiwizuje niepotrzebne zrzuty do folderu `_nieuzywane_zrzuty/`.
    *   **`INSTRUKCJA.md`:** Pełny podręcznik użytkownika zintegrowany ze strukturą repozytorium.

## 3. Zrealizowane Funkcjonalności (Co już działa)

### A. Dynamiczne Przyciski (10 sztuk) i System QSS
Oparte na systemie Qt Style Sheets (QSS) dynamicznie generowanym w `get_btn_style`. Posiadają efekty wciśnięcia (przesuwający padding o 2px) i podświetlenia (hover). Formularz edycji ukrywa niepotrzebne pola w zależności od typu (`QStackedWidget`).
*   **Nieaktywne:** Kafelki ze stylem przerywanego obramowania (`dashed`), ciemnoszary tekst `+ Przypisz akcję (PPM)`.
*   **Typ `toggle` (ON/OFF):** 🔘 Wysyła `tx_on` lub `tx_off`. Zmiana koloru następuje dopiero po sprzętowym ACK.
*   **Typ `push` (Jednorazowe):** ⚡ Wysyłają ramkę `tx` po kliknięciu. Brak obsługi ACK.
*   **Typ `hold` (Chwilowe):** ⏳ Wysyłają `tx_on` podczas wciśnięcia (`pressed`) i `tx_off` po puszczeniu (`released`).
*   **Typ `macro` (Skryptowe):** 📜 Odpalają ciąg komend z opóźnieniami w tle.
*   **Typ `trigger` (Sekwencyjne):** 🔁 (Bezczynny) / ⏹ (Pracuje). Pętla na obiekcie `QTimer` wysyłająca ramki co zadany `interval` (w ms).
*   **Dynamiczne Tooltips:** Każdy przycisk generuje dymek z pełnym podglądem nadawanych ramek TX i oczekiwanych potwierdzeń ACK.
*   **Wyczyszczenie przycisku:** W `ButtonEditDialog` przycisk `Usuń` przywraca domyślny stan `get_default_button()`, czyszcząc przypisanie kafelka.

### B. Konsola Logów, Komunikacja i Eksport
*   **Dwa tryby RX:** ASCII oraz BINARY (HEX). Niezależne formatowanie TX w panelu wysyłania i na przyciskach.
*   **Wybór znaku końca linii (`EOL`):** `CRLF (\r\n)`, `LF (\n)`, `CR (\r)` oraz `Brak EOL` z zapisem w profilu JSON pod kluczem `"eol"`.
*   **Eksport Logów:** Zapis sesji do HTML (z kolorowaniem ułamków sekund), TXT oraz Markdown z meta-danymi.
*   **Smart Autoscroll:** Konsola inteligentnie zatrzymuje autoscroll przy przewinięciu w górę i wyświetla przycisk powrotu do najnowszych wiadomości.
*   **Wyszukiwarka Logów (`Ctrl+F`):** Pływający popup z obsługą przeszukiwania w przód/tył i dopasowań wieloznacznych (`*test*`).
*   **Oznaczanie Logów (Markers):** Przycisk `📌 Marker` oraz flaga `show_marker` na przyciskach wstrzykująca nazwę akcji do logu.

### C. Zaawansowane Filtrowanie RX i Zapora
*   Oparte o bibliotekę `fnmatch` (wildcardy `*...*`). Tryby: "Ukryj", "Koloruj" oraz "Dozwolony (Whitelist)".
*   **Szybkie dodawanie z zaznaczenia konsoli (PPM):** Menu kontekstowe `🌪️ Dodaj do Filtra (*tekst*)` oraz `🧩 Dodaj do Parsera (*tekst*)` automatycznie normalizuje frazę, otacza ją gwiazdkami, kopiuje do schowka, otwiera zwijany panel i ustawia fokus klawiatury.
*   **Tryb Zapory (Whitelist):** Jeżeli na aktywnej karcie istnieje reguła "Dozwolony", terminal całkowicie blokuje pozostałe dane i wyświetla czerwony przycisk `⚠ ZAPORA`.

### D. Moduł Telemetrii Live Watch
*   Błyskawiczne odświeżanie zmiennych w miejscu bez uciekania strumienia konsoli.
*   Automatyczne podświetlanie różnic tokenów (`difflib`) z wygaszaniem (`750 ms`).
*   Automatyczne przechwytywanie prefiksu `@` z mikrokontrolera lub ręczne przypinanie z menu PPM konsoli.
*   Elastyczny suwak i limit wysokości panelu do 70% konsoli.

### E. Sterowanie Sprzętowe i Prędkości Transmisji
*   **Ukryte menu sprzętowe (`⚙️` obok `Połącz`):** Przełączanie linii `DTR` i `RTS` oraz generowanie 100 ms impulsu resetu MCU (`🔄 Impuls Reset MCU`).
*   **Elastyczny Baudrate:** Standardowe prędkości aż do 1 000 000 bps + opcja `Własny...` (`QInputDialog`) dla dowolnych niestandardowych wartości.

### F. Globalny Ciemny Motyw (`DARK_STYLESHEET`)
*   Spójna ciemna paleta inżynierska aplikacji (`#18181b`, `#27272a`, `#121214`, akcent `#228be6`).
*   Wskaźniki stanu połączenia w tytułach kart (`🟢` połączony, `⚪` rozłączony) wraz z nazwą portu COM.

## 4. Wytyczne dla przyszłych iteracji (Rules for future development)

1.  **Kompatybilność Wersji Pythona (Python 3.8+):**
    *   Kod musi być w pełni kompatybilny z Pythonem 3.8 oraz nowszymi.
    *   Na początku każdego pliku ze skryptami Pythona stosuj `from __future__ import annotations`.
    *   Unikaj składni PEP 585 (`tuple[...]`, `list[...]`, `dict[...]`) bezpośrednio w sygnaturach funkcji bez odpowiednich zabezpieczeń.
2.  **Architektura Wielowątkowości (Thread Safety):**
    *   Komunikacja sprzętowa z portem szeregowym (`pyserial`) odbywa się wyłącznie w wątku `SerialWorker(QThread)` z wykorzystaniem bezpiecznej kolejki `queue.Queue()` dla danych wychodzących (`tx_queue`).
    *   Wątki poboczne (`SerialWorker`, `MacroRunner`) nigdy nie modyfikują bezpośrednio obiektów GUI – komunikacja z głównym wątkiem odbywa się wyłącznie przez sygnały `pyqtSignal`.
3.  **Bezpieczeństwo Plików Konfiguracyjnych (`cfg/*.json`):**
    *   Zapis plików `.json` (`save_config`, `save_app_settings`) musi zawsze odbywać się atomowo: najpierw zapis do pliku tymczasowego `.tmp`, a następnie podmiana przez `os.replace()`.
    *   Każde nowe pole dodawane do konfiguracji profilu musi mieć zdefiniowaną wartość domyślną w `get_default_config()` oraz fallback w `load_config()`, aby starsze pliki konfiguracyjne ładowały się bez błędów `KeyError`.
    *   Nigdy nie zapisuj konfiguracji do plików, które nie istnieją fizycznie na dysku (`not os.path.exists(self.current_cfg_file)`), aby uniknąć ponownego odtwarzania skasowanych profili.
4.  **Dyscyplina Geometrii i Symetrii (Split View 50% / 50%):**
    *   Ze względu na tryb Split View (50% / 50%), paski narzędziowe wewnątrz karty muszą być kompaktowe.
    *   Główny widget `SerialTab` oraz kontener `right_panel_widget` muszą utrzymywać politykę `QSizePolicy.Policy.Ignored` w poziomie, aby żadna z połówek ekranu nie rozpychała drugiej (np. po pojawieniu się przycisku `⚠ ZAPORA`).
    *   W widoku podzielonym (Split View) panele przycisków muszą zawsze znajdować się na zewnętrznych krawędziach okna (`left` dla lewej karty, `right` dla prawej karty).
5.  **Konwencje dla Live Watch, Filtrów i Parserów:**
    *   Wzorce filtrów i parserów opierają się na dopasowaniu `fnmatch` (wildcard `*tekst*`). Każda funkcja automatycznego tworzenia filtrów/parserów powinna domyślnie otaczać frazę gwiazdkami `*...*`.
    *   W module `LiveWatchRowWidget` błyski zmian (`FLASH_DURATION = 0.75 s`) opierają się na tokenizacji i `difflib.SequenceMatcher`, a odświeżanie wygaszania realizuje centralny `watch_decay_timer` (100 ms).
    *   Automatyczne przechwytywanie w Live Watch reaguje na linie z prefiksem `@` (np. `@[MODUL]...`), wycinając znak `@` i przypinając klucz.
    *   Wysokość panelu Live Watch jest ograniczona do maksymalnie 70% wysokości konsoli, po czym włącza się pionowy suwak `QScrollArea`.
6.  **Ramki z danymi (Binary/Hex):** Pamiętaj, że aplikacja ma służyć m.in. do testowania protokołów binarnych (np. `ot_app_msg_tlv`). Zawsze przewiduj, że użytkownik wpisze ramkę szesnastkową ze spacjami, dlatego zawsze używaj bezpiecznego parsowania: `bytes.fromhex(payload.replace(" ", ""))`.
7.  **Parsowanie RX dla przycisków:** Bufor binarnego odczytu potwierdzeń (`self.rx_buffer`) musi być niezależny od bufora tekstowego (`self.text_buffer`). Gdy przycisk (toggle) odnajdzie swoje ACK w `self.rx_buffer`, musi precyzyjnie wyciąć tylko ten zidentyfikowany ciąg bajtów (`replace(ack, b'')`), aby nie zniszczyć reszty danych. Bufor posiada zabezpieczenie przed przepełnieniem (czyszczenie powyżej 1024 bajtów).
8.  **Autozapis:** Unikaj ciągłego, bezwarunkowego zapisu na dysk w głównej pętli. Zapisuj wywołując `self.save_current_settings_to_config(force=True)` tylko w momencie zmiany logiki konfiguracji przez usera (np. edycja przycisku, dodanie/edycja filtra).
9.  **Zasady Dokumentacji i Skryptów Narzędziowych:**
    *   Wszelkie narzędzia generatora dokumentacji (`build_docs/`) korzystają ze skalibrowanych współrzędnych i nie mogą zaśmiecać repozytorium plikami roboczymi.
    *   Katalogi tymczasowe `annotated_tmp/`, `_nieuzywane_zrzuty/` oraz pliki `*.tmp` muszą być bezwzględnie ignorowane w `.gitignore`.
10. **Edycja i Kodowanie Plików:** Ze względu na polskie znaki w kodzie (np. "Połącz", "Rozłącz") i specyfikę systemu Windows, bezwzględnie unikaj używania komend terminalowych PowerShell (takich jak `Get-Content` i `Set-Content`) do modyfikacji plików tekstowych. PowerShell domyślnie niszczy kodowanie UTF-8 bez BOM powodując tzw. mojibake. Używaj wyłącznie natywnego narzędzia `replace_file_content` lub w razie konieczności krótkich skryptów Python z `encoding="utf-8"`.
11. **Changelog:** Zawsze, gdy wprowadzane są jakiekolwiek zmiany w kodzie lub projekcie, bezwzględnie dodaj nowy wpis do pliku `changelog.md`. Wpis musi zawierać numer wersji i datę (w formacie YYYY-MM-DD) oraz zwięzły opis wprowadzonych nowości, modyfikacji lub poprawek w podziale na sekcje (*Added*, *Changed*, *Fixed*).
12. **Magistrala CAN i Adapter CANable (slcan):**
    *   Komunikacja CAN z adapterem CANable odbywa się za pośrednictwem modułu `can_support.py` i dedykowanego wątku `CanWorker(QThread)` (`python-can`, interface=`slcan`).
    *   Składnia wysyłania ramek odpowiada standardowi `cansend`: `ID#DANE` (np. `187#01 02 03`, `18FEF100#AABB`, `65A#R` dla RTR, `3D0#` dla 0-DLC). Wszelkie ramki muszą być walidowane przez `parse_can_frame(text)`, który wyrzuca `CanFrameError` z czytelnym komunikatem błędu.
    *   Potwierdzenia ACK w przyciskach TOGGLE w trybie CAN są normalizowane przez `normalize_can_ack_pattern()` i dopasowywane do klucza `CanFrame.to_match_key()` za pomocą `fnmatch` (np. `581#01*`, `581#`).
    *   Aby zapobiec blokowaniu GUI przy dużym obciążeniu magistrali, `CanWorker` grupuje odbierane ramki w paczki (`frames_received(list)`) w oknie do 20 ms lub 500 ramek.
    *   Wiersze Live Watch w trybie CAN są sortowane rosnąco według CAN ID (`can_id_sort_key`), a czas cyklu $\Delta t$ jest obliczany i wyświetlany w milisekundach obok licznika aktualizacji (`Δ ... ms`).
    *   Ręcznie odpięte ramki CAN są rejestrowane w sesyjnym zbiorze `_unpinned_can_ids`, co chroni przed ich natychmiastowym ponownym przechwyceniem przez automat `can_watch_auto`.

## 5. Do poprawy i wdrożenia na przyszłe sesje
*   **Refaktoryzacja gui.py:** Plik osiągnął ponad 3300 linii kodu (tzw. monolith). Należy rozważyć podzielenie go na strukturę modułową w podfolderach (np. `components/` dla kontrolek i paneli, `dialogs/` dla okien modalnych, `workers/` dla wątków pobocznych `SerialWorker` i `MacroRunner`).
*   **Dodatkowa walidacja HEX:** Makra i przyciski wysyłają obecnie kod przy cichej akceptacji ewentualnych błędów. Przydałby się szerszy system raportowania błędów parsowania komend użytkownikowi (aby nie ignorować błędów wprowadzania za pomocą gołego bloku `except Exception as e: pass`).
*   **Rozszerzenie makr:** Warto dodać funkcjonalność pętli dla makr (np. `loop(5)`) i wsparcie dla warunkowego czekania na odpowiedź (np. `wait_for(ACK_HEX, timeout)`), co stworzyłoby kompletny język skryptowy testowania HMI.
