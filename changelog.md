# Changelog Serial Commander

Wszystkie znaczące zmiany w tym projekcie będą udokumentowane w tym pliku.

## [1.6.0] - 2026-10-15

### Added
- **Moduł Telemetrii `📌 Live Watch` (`LiveWatchRowWidget`):**
  - Dedykowany panel nad główną konsolą służący do przypinania i odświeżania w jednym miejscu powtarzalnych ramek diagnostycznych i telemetrycznych (np. statusów GPIO, pomiarów ADC, ramek CAN/FDCAN).
  - **Token Diffing & Błysk Zmian (Flash):** Inteligentny algorytm oparty na `difflib.SequenceMatcher` rozbija ramki na pojedyncze tokeny (słowa, liczby, symbole, białe znaki) i porównuje nową wartość z poprzednią. Zmienione dane błyskają na złoto-pomarańczowo (`#5c3c00` / `#ffd43b`) przez `750 ms` (`FLASH_DURATION = 0.75s`), z wygaszaniem odświeżanym przez centralny `watch_decay_timer` co `100 ms`.
  - **Podwójny tryb aktywacji:**
    - **Automatyczny:** Rozpoznawanie prefiksu `@` na początku odebranej linii z mikrokontrolera (np. `@[IO_MGR] BTN: 0x01 | ADC: 512`), automatyczne wyciągnięcie klucza w nawiasach `[...]` lub do pierwszego dwukropka/spacji, przypięcie do wiersza Live Watch oraz usunięcie znaku `@`.
    - **Ręczny z konsoli:** Menu kontekstowe PPM po kliknięciu na linię logu z opcją `📌 Przypnij do Live Watch ('klucz')`.
  - **Filtrowanie strumienia konsoli i ergonomia:**
    - Przypięte ramki są domyślnie ukrywane w głównym oknie konsoli poniżej, aby nie powodować uciekania historii logów (z możliwością włączenia podglądu w konsoli przez opcję `Pokaż też w konsoli`, zapamiętywaną w profilu jako `watch_print_in_console`).
    - **Ochrona geometrii konsoli:** Panel Live Watch skaluje się dynamicznie maksymalnie do **70% wysokości konsoli**, po czym automatycznie aktywuje pionowy pasek przewijania (`QScrollArea`), gwarantując stałą widoczność logów poniżej.
    - Przycisk zwijania `▲ Ukryj / ▼ Pokaż` po prawej stronie oraz przycisk `Odepnij wszystkie`.
    - Licznik odebranych aktualizacji (`#N`) dla każdego wiersza Live Watch oraz przycisk odpinania pojedynczego wiersza (`✕`).
- **Zautomatyzowany Generator Dokumentacji Technicznej (`build_docs/`):**
  - **Generator PDF i PPTX (`build_docs.py`):** Skrypt generujący 11-slajdową instrukcję PDF (`Serial_Commander_Instrukcja.pdf`) przy użyciu `QPdfWriter` i `QPainter` oraz prezentację PowerPoint (`Serial_Commander_Prezentacja.pptx`) z wektorowymi znacznikami, strzałkami i opisami nanoszonymi na zrzuty ekranu.
  - **Automatyczny porządkujący (`cleanup_screenshots.py`):** Skrypt weryfikujący kompletność wymaganych zrzutów ekranu oraz archiwizujący nieużywane pliki graficzne do folderu `_nieuzywane_zrzuty/`.
  - **Podręcznik użytkownika `INSTRUKCJA.md`:** Kompletna dokumentacja techniczna opisująca wszystkie funkcje programu (interfejs, Live Watch, Split View 50/50, filtry, parsery, sterowanie sprzętowe, makra).

### Changed
- Podniesiono wersję aplikacji do `1.6.0` (`APP_VERSION = "1.6.0"`).
- Rozszerzono strukturę profilu konfiguracyjnego JSON o opcje `watch_patterns` oraz `watch_print_in_console`.
- Rozbudowano menu kontekstowe konsoli (PPM) o akcję przypinania logów do Live Watch.
- Uporządkowano plik `.gitignore` o ignorowanie katalogów tymczasowych dokumentacji (`_nieuzywane_zrzuty/`, `annotated_tmp/`) oraz plików tymczasowych (`*.tmp`).

### Fixed
- **Kompatybilność z Python 3.8+:** Wprowadzono `from __future__ import annotations` oraz wyeliminowano użycie generyków PEP 585 w sygnaturach bez odpowiednich importów, zapewniając pełną zgodność z Pythonem 3.8 i nowszymi.
- **Ochrona układu GUI przed przepełnieniem:** Wdrożono limit wysokości panelu Live Watch (maks. 70% konsoli) z elastycznym przewijaniem, zapobiegając wypychaniu konsoli logów poza widoczny obszar ekranu przy dużej liczbie przypiętych zmiennych.

## [1.5.0] - 2026-10-15

### Added
- **Symetryczny Widok Podzielony (Split View 50% / 50%):**
  - Przebudowa architektury `MainWindow` w oparciu o centralną listę kart `tab_list` oraz `QStackedWidget` (`view_stack`) przełączający pomiędzy widokiem pojedynczych zakładek (`QTabWidget`) a symetrycznym kontenerem podzielonym (`split_container`).
  - Idealna symetria 50/50 uzyskana za pomocą `QHBoxLayout` z równymi wagami (`stretch=1`) oraz wymuszeniem `QSizePolicy.Policy.Ignored` w poziomie na kartach `SerialTab` i kontenerach `right_panel_widget` (zapobiega rozpychaniu osi podziału przez pojawiające się elementy, np. przycisk `⚠ ZAPORA`).
  - Dedykowany górny pasek sterowania Split View (`split_top_bar`) z przyciskiem szybkiej zamiany miejscami (`⇄ Zamień miejscami`), powrotem do widoku zakładek oraz licznikiem kart pracujących w tle.
  - Nagłówek karty w widoku podzielonym (`SplitCardHeader`) ze wskaźnikiem strony (`[LEWA]` / `[PRAWA]`), stanem połączenia (`🟢`/`⚪`) oraz interaktywnym przyciskiem menu (`btn_card_selector`), które dynamicznie filtruje bieżącą kartę i pozwala wybrać inną otwartą kartę z tła lub wykonać zamianę miejscami (`Swap ⇄`).
  - Menu kontekstowe na pasku zakładek (`QTabBar`), pozwalające kliknięciem PPM szybko przypisać daną kartę jako lewą lub prawą w widoku podzielonym.
- **Ergonomia i Zwijane Panele w `SerialTab`:**
  - Zwijany panel szybkich akcji (10 przycisków makr) sterowany przyciskami `◀ Ukryj` / `▶ Akcje`, pozwalający oddać pełną szerokość karty dla konsoli logów.
  - Skrajne rozmieszczenie paneli bocznych (`set_panel_side`): lewa karta umieszcza panel po lewej (zewnętrznej) krawędzi, a prawa karta dynamicznie przebudowuje layout i umieszcza panel po prawej (zewnętrznej) krawędzi, dzięki czemu konsole logów w widoku Split View sąsiadują ze sobą w centrum ekranu. Automatyczne zwijanie paneli przy wejściu w Split View.
  - Zwijany panel Filtrów i Parserów (`tools_frame`) sterowany przyciskiem `🌪️ Filtry (N)` na górnym pasku (`N` = liczba aktywnych filtrów i parserów).
  - Dynamicznie generowane dymki (Tooltips) dla przycisków szybkich akcji z pełnym podglądem nadawanych ramek TX i oczekiwanych potwierdzeń ACK. Kafelki nieaktywne otrzymały wyróżniający styl obramowania przerywanego (`dashed`) oraz etykietę `+ Przypisz akcję (PPM)`.
- **Funkcje Terminalowe, Diagnostyczne i Sprzętowe:**
  - Szybkie dodawanie zaznaczonego tekstu z konsoli do Filtra lub Parsera (PPM): menu kontekstowe z opcjami `🌪️ Dodaj do Filtra (*tekst*)` oraz `🧩 Dodaj do Parsera (*tekst*)`. Zaznaczony fragment jest oczyszczany z białych znaków, otaczany wildcardem `*...*`, kopiowany do schowka, a panel narzędzi jest rozwijany z automatycznym ustawieniem fokusu w odpowiednim polu oraz obsługą zatwierdzania klawiszem `Enter`.
  - Customowa kontrolka `PortComboBox`: w stanie spoczynku ma stałą szerokość `82 px` i prezentuje krótki identyfikator portu (np. `COM20`), a po rozwinięciu (`showPopup`) powiększa listę do `320 px` i wyświetla pełne nazwy urządzeń wraz z opisem sterownika.
  - Rozszerzona lista prędkości Baudrate aż do `1000000` bps oraz opcja `Własny...` (`QInputDialog`) umożliwiająca wprowadzenie dowolnej niestandardowej prędkości bez psucia geometrii kontrolki.
  - Sprzętowe menu sterujące (`⚙️` obok `Połącz`): obsługa linii sygnałowych `DTR` i `RTS` w `SerialWorker` (`set_dtr`, `set_rts`) oraz akcja wygenerowania 100 ms impulsu resetującego mikrokontroler (`🔄 Impuls Reset MCU`).
  - Pole wprowadzania poleceń `CommandLineEdit` dziedziczące po `QLineEdit`, czyszczące się po wysłaniu i obsługujące historię wysłanych komend pod klawiszami `Strzałka w górę` / `Strzałka w dół`.
  - Wybór znaku końca linii dla trybu ASCII: `CRLF (\r\n)`, `LF (\n)`, `CR (\r)` oraz `Brak EOL` (zapisywany w pliku `.json` profilu pod kluczem `"eol"`).
- **Stylistyka:**
  - Globalny ciemny motyw inżynierski (`DARK_STYLESHEET`) na poziomie całej aplikacji (`QApplication`), oparty na palecie `#18181b`, `#27272a`, `#121214` z akcentem `#228be6`.
  - Wskaźniki stanu połączenia w tytułach kart (`🟢` połączony, `⚪` rozłączony) wraz z nazwą portu COM.

### Changed
- **Reorganizacja układu `SerialTab`:** Odwrócono ergonomię karty – pasek połączenia, zaawansowane menu sprzętowe, format RX, zapora oraz pasek narzędzi konsoli (`Wyczyść`, `Zapisz Logi`, `Marker`, `Szukaj`, `Limit`) przeniesiono na samą górę okna, natomiast pole wprowadzania komend (`cmd_input`) umieszczono na dole, bezpośrednio pod konsolą logów.
- **Dynamiczne skalowanie okna (`adjust_window_size_for_mode`):** Główne okno aplikacji automatycznie rozszerza się do `SPLIT_WIDTH = 1440` przy przejściu w widok dwóch kart i powraca do kompaktowego rozmiaru pojedynczej karty `SINGLE_WIDTH = 940` przy powrocie do widoku zakładek (zdejmując ewentualną maksymalizację).
- **Atomowy zapis konfiguracji:** Zapis plików `.json` (`save_config`, `save_app_settings`) realizowany jest atomowo poprzez zapis do pliku tymczasowego `.tmp` i podmianę za pomocą `os.replace()`, co chroni konfigurację przed uszkodzeniem.

### Fixed
- **Zapis filtra Whitelist:** W `FilterEditDialog.get_data()` naprawiono błąd, który przy edycji istniejącego filtra typu `Dozwolony (Whitelist)` nadpisywał jego akcję jako `"color"`. Od teraz poprawnie zachowywana i zapisywana jest akcja `"allow"`.
- **Czyszczenie przycisku makra:** Wybranie `Usuń` w `ButtonEditDialog` zwraca teraz domyślną strukturę `get_default_button()` z flagą `"is_used": False`, co natychmiast resetuje wygląd kafelka w GUI do stanu nieaktywnego.
- **Usunięcie martwego kodu:** Usunięto zduplikowaną, nieużywaną metodę `edit_parser` w `SerialTab`, która odwoływała się do nieistniejącego obiektu `combo_active_parsers`.
- **Zabezpieczenie przed odtwarzaniem usuniętych profili:** Metody zapisu konfiguracji weryfikują fizyczne istnienie pliku na dysku (`os.path.exists`), a usunięcie profilu z poziomu okna edycji poprawnie synchronizuje i przełącza wszystkie otwarte karty w `MainWindow` bez ryzyka ponownego zapisania skasowanego pliku.


## [2026-10-05]
### Dodano
- Funkcję wyszukiwania tekstu w konsoli (dostępną przez skrót `Ctrl+F` lub z menu pod prawym przyciskiem myszy). Wyszukiwarka pojawia się jako poręczny popup i oferuje przeszukiwanie logów w przód i w tył, pokazując łączną liczbę znalezionych pasujących wyników.
- Opcję włączania/wyłączania ("Aktywny" checkbox) dla filtrów i parserów bezpośrednio na liście w Menedżerze Filtrów i Menedżerze Parserów. Pozwala to na tymczasowe dezaktywowanie reguł bez konieczności ich usuwania.
- Nową wytyczną do pliku `GEMINI.md` wymagającą dokumentowania wszystkich wprowadzanych modyfikacji w tym pliku (`changelog.md`).
- Przycisk "▼ Wróć do najnowszych (w dół)" w terminalu, który pojawia się po przewinięciu logów do góry i pozwala szybko wrócić do najnowszych wiadomości.

- Niezależne formatowanie TX (wysyłania danych). Od teraz globalne przełączniki "ASCII / HEX" na dole okna sterują wyłącznie sposobem wyświetlania logów (RX) w terminalu. W panelu wysyłania (Manual) pojawiła się nowa lista rozwijana wyboru trybu wysyłania, a każdy z 10 przycisków w konfiguracji otrzymał własne, niezależne pole "Format TX", dzięki czemu mogą one nadawać dane i obsługiwać ACK w żądanym trybie niezależnie od widoku terminala.

### Zmieniono
- Logikę działania autoscrollingu konsoli w `gui.py`. Jeśli użytkownik samodzielnie przewinie wiadomości wyżej (aby zobaczyć historię), napływające nowe logi nie będą go już agresywnie wyrzucać na sam dół. Zastosowano inteligentny `append` bez wywoływania wymuszonego przeskoku do końca dokumentu, o ile użytkownik nie jest na najniższej pozycji suwaka.
- Poprawiono logikę wyświetlania pływającego okienka wyszukiwania (`Ctrl+F`). Odtąd otwiera się ono precyzyjnie w prawym górnym rogu wewnętrznego obszaru konsoli (bez przekłamań współrzędnych). Okienko zachowało funkcję bycia niezależnym panelem narzędziowym (można je dowolnie przeciągać po ekranie).
- Wzbogacono wyszukiwarkę o wsparcie dla symbolu wieloznacznego `*` (wildcards). Można teraz wpisywać m.in. `*test` (kończy się na test), `test*` (zaczyna się na test) lub `*test*` (zawiera test), co program w locie tłumaczy na bezpieczne wyrażenia regularne (regex).

### Naprawiono
- Krytyczny błąd powodujący crash programu podczas próby zapisu logów do pliku. Zjawisko wynikało z kolizji nazw obiektów (klasa `datetime.datetime.now()` wywoływana na module już zaimportowanym jako klasa `datetime`).
