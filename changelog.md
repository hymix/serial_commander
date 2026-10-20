# Changelog Serial Commander

Wszystkie znaczące zmiany w tym projekcie będą udokumentowane w tym pliku.

## [1.9.0] - 2026-10-19

### Added
- **Integracja magistrali CAN FD i protokołu candleLight (STM32G4 / WinUSB / gs_usb):**
  - Nowy profil transportu `TRANSPORT_CANDLE` ("CAN / CAN FD – candleLight (WinUSB / gs_usb)") obok UART i CANable slcan.
  - Automatyczne wykrywanie podłączonych adapterów candleLight przez `candle_api.list_device()` z przypisaniem portów w formacie `candle:DEV:CH` (np. `candle:0:0 — Candlelight 2.5 (SN: 2074326D554850142)`).
  - Pełne wsparcie dla CAN FD: faza nominalna arbitrażu (10 kbps – 1 Mbps) oraz szybka faza danych (Data Bitrate: 500 kbps – 8 Mbps) z aktywnym przełączaniem prędkości BRS (Bit Rate Switch) i ładunkiem do 64 bajtów.
  - Bezpieczne zamykanie magistrali (`bus.shutdown()`) oraz automatyczne odfiltrowywanie echa własnych ramek TX (`msg.is_rx == True`).
- **Implementacja binarnej struktury TLV (`ot_app_msg_tlv`):**
  - Klasa `OtAppMsgTlv` w `can_support.py` realizująca pakowanie i rozpakowywanie nagłówka Little-Endian `<BH` (1 bajt typ, 2 bajty długość pola value, ładunek do 61 bajtów w ramce 64B, opcjonalne dopełnienie zerami).
  - Automatyczne dekodowanie struktur TLV w podglądzie ramek w konsoli głównej oraz w wierszach panelu Live Watch (`| TLV[0xA5, len=42]: "..."`).
  - Szybka składnia poleceń z poziomu konsoli i przycisków: `TLV#<ID>#<TYPE>#<PAYLOAD>` (np. `TLV#321#0xA5#Hello CAN FD`) automatycznie pakująca ramkę CAN FD 64B z BRS.
- **Kreator i Nadajnik Ramek CAN FD / TLV (`CanFdTxDialog`):**
  - Dedykowany przycisk `📦 TLV / CAN FD` na dolnym pasku narzędziowym obok pola wprowadzania komend.
  - Wizualny konfigurator ramki (CAN ID, flagi Extended 29-bit, CAN FD, BRS).
  - Przełącznik trybu danych: pakowanie w strukturę binarną `ot_app_msg_tlv` lub surowy bufor Hex (do 64B).
  - Nadawanie jednorazowe (`⚡ Wyślij raz`) oraz cykliczne (`🔁 Nadawaj cyklicznie`) z konfigurowalnym okresem (ms).
  - Funkcja `📋 Kopiuj polecenie` do wklejenia w konsolę lub przypisania do przycisków szybkiej akcji.
- **Konfiguracja Standardu Ramki CAN 2.0 / CAN FD w Przyciskach Szybkich Akcji (10 kafelków):**
  - Nowe pole wyboru `Standard CAN` w `ButtonEditDialog` umożliwiające określenie per-przycisk standardu wysyłanej ramki: `Auto`, `Klasyczny CAN 2.0 (maks. 8B, bez BRS)`, `CAN FD z BRS (do 64B)`, `CAN FD bez BRS (do 64B)` oraz `Struktura TLV (ot_app_msg_tlv, 64B)`.
  - Zestaw kafelków pomocnika szybkiego wstawiania szablonów: `🚗 Szablon CAN 2.0`, `⚡ Szablon CAN FD`, `📦 Szablon TLV` oraz konwerter `🔄 Konwertuj do trybu`.
  - Walidacja na żywo i inteligentna naprawa (`⚡ Napraw automatycznie`) w oknie edycji przycisku (np. automatyczne przełączenie na CAN FD przy danych > 8B w trybie klasycznym).
  - Dynamiczne dymki tooltip na przyciskach odzwierciedlające wybrany standard ramki (`Typ: PUSH (CAN 2.0)`, `Typ: PUSH (CAN FD+BRS)`).
- **Kontekstowe dopasowanie UI w zależności od trybu transportu (`Serial` vs `CANable slcan` vs `candleLight`):**
  - W trybie `Serial`: całkowite ukrycie i wyłączenie opcji CAN (przycisków szablonów, formatu CAN w edycji przycisków, kreatora TLV i ustawień bitrate).
  - W trybie `CANable slcan`: ścisła blokada do standardu Klasyczny CAN 2.0 (maksymalnie 8 bajtów danych, brak opcji CAN FD i BRS w przyciskach, ukrycie przycisku `📦 TLV / CAN FD`).
  - W trybie `candleLight`: pełne wsparcie dla CAN 2.0 oraz CAN FD i TLV (odblokowany przycisk `📦 TLV / CAN FD`, wszystkie szablony i tryby w edycji przycisków).
- **Skrypty weryfikacyjne i testowe niskiego poziomu w katalogu `tests/`:**
  - `tests/step1_usb_check.py` – weryfikacja backendu libusb-1.0 i deskryptorów USB candleLight (1D50:606F),
  - `tests/step2_classic_can.py` – test klasycznego CAN 2.0 (500 kbps, 8 bajtów),
  - `tests/step3_can_fd.py` – test CAN FD (500k / 2000k BRS) oraz pakowania struktury `ot_app_msg_tlv`.
- **Rozszerzenie Generatora Dokumentacji i Prezentacji do 16 Slajdów (`build_docs/`):**
  - Wdrożono dedykowane slajdy 14, 15 i 16 ze skalibrowanymi wektorowymi adnotacjami dla zrzutów: `Zrzut_edytor konfiguracji.png`, `Zrzut_edytor_konfiguracji_przycisku_push.png` oraz `zrzut_can_fd_tlv.png`.
  - Zaktualizowano instrukcję PDF (`Serial_Commander_Instrukcja.pdf`) oraz prezentację PowerPoint (`Serial_Commander_Prezentacja.pptx`).

### Changed
- Podniesiono wersję aplikacji do `1.9.0` (`APP_VERSION`).
- Zaktualizowano okno dialogowe konfiguracji profilu (`ConfigEditDialog`) o wybór interfejsu candleLight, przełącznik CAN FD oraz listę prędkości Data Bitrate.
- Przystosowano pasek narzędziowy karty (`SerialTab`) do wyświetlania prędkości nominalnej `Nominal:` oraz dynamicznych podpowiedzi składni CAN FD.

### Fixed
- **Rozpoznawanie i obsługa stanu zajętości interfejsu candleLight przez inną aplikację:**
  - Rozwiązano problem znikającego portu candleLight z listy rozwijanej (`PortComboBox`), gdy urządzenie USB było otwarte na wyłączność przez inny proces (np. HUD ECU Hacker, BusMaster, inny terminal lub proces w tle).
  - Wprowadzono klasę `CandleDeviceInfo(tuple)` w `can_support.py`, która łączy szybki odczyt API z niskopoziomowym skanem fizycznej obecności magistrali USB (`libusb_package` / `pyusb` dla VID 1D50).
  - Urządzenia zajęte nie znikają już z interfejsu, lecz są wyraźnie oznaczane jako `candle:0:0 🔒` (bordowe tło `#3b1818`, czerwony tekst `#ff8787` w rozwijanej liście portów) oraz symbolem kłódki w nagłówku karty (`🔒 candle:0:0 · CAN`).
  - Próba kliknięcia `Połącz` na zajętym urządzeniu wyświetla natychmiast czytelny dialog ostrzegawczy `QMessageBox.warning` z instrukcją zwolnienia urządzenia w zewnętrznym programie, zapobiegając błędom `RuntimeError / Access Denied` i blokowaniu wątków.
- **Naprawa błędu odbioru ramek CAN / CAN FD w Serial Commander (brak odbioru RX przy sprawnym TX):**
  - Wyeliminowano krytyczny błąd w pętli odczytu `CanWorker.run()`: warunek `elif getattr(msg, 'is_rx', True):` odrzucał odebrane ramki z fizycznej magistrali w backendzie `candle`, gdzie `frame.frame_type.rx` domyślnie przyjmowało wartość `False`. Zmodyfikowano warunek, aby odrzucał wyłącznie potwierdzenia echo z kontrolera `gs_usb` (`msg.echo_id is not None and msg.echo_id != 0xFFFFFFFF`), przywracając pełny odbiór ramek fizycznych.
  - Zmieniono domyślną wartość `watch_print_in_console` z `False` na `True`: automatyczne przypinanie `can_watch_auto: True` przechwytywało każde nowe CAN ID i ukrywało je w głównej konsoli logów. Od teraz odebrane ramki są zawsze widoczne strumieniowo w konsoli oraz w wierszu Live Watch.
  - Zaktualizowano powiązanie w `ConfigEditDialog`: odznaczenie `Włącz CAN FD` blokuje i wyszarza pola Data Bitrate oraz Sample Point, jednoznacznie informując o pracy w czystym standardzie Klasycznego CAN 2.0.
  - Skorygowano profil `cfg/CAN.json`: ustawiono port `candle:0:0`, standardowy Sample Point `80.0%`, Data Bitrate `2000000` (2M) oraz `watch_print_in_console: true`.
- **Rozwiązano problem z transmisją CAN FD 500k / 2 Mbps (Sample Point CiA 601-1):**
  - Wyjaśniono przyczynę awarii przy 2 Mbps: biblioteka `python-can-candle` domyślnie żądała punktu próbkowania `87.5%`, co przy zegarze 160 MHz i 2 Mbps ustawiało `tseg2 = 2` (zaledwie 62.5 ns) oraz powodowało przekroczenie okna TDC i błędy bitowe na snifferach oczekujących standardowego 80.0%. Przy 4 Mbps biblioteka automatycznie przełączała się na 80.0%, a przy 1 Mbps bit trwał 1000 ns, stąd obie te prędkości działały poprawnie.
  - Skonfigurowano domyślny punkt próbkowania na **`80.0%`** (zgodnie ze standardem CiA 601-1 dla CAN FD) w `can_support.py` (`CanWorker`) oraz w skrypcie `tests/step3_can_fd.py`.
  - Dodano selektor punktu próbkowania (`Sample Point (CiA 601-1)`) w oknie edycji konfiguracji profilu (`ConfigEditDialog`).
  - Rozwiązano problem z ponownym otwarciem adaptera (`RuntimeError: Cannot open device`) poprzez bezpośrednie zamykanie `device.close()` w `CanWorker._safe_shutdown()`.
  - Usunięto błąd `AttributeError: 'SerialTab' object has no attribute 'config'` przy łączeniu (`toggle_connection`), zastępując odwołanie właściwym `self.app_config`.

## [1.8.0] - 2026-10-16

### Added
- **Typ przycisku `❓ Query` (Request-Response z precyzyjnym pomiarem czasu reakcji i timeoutem):**
  - Obsługiwany zarówno w trybie UART (tekst ASCII / HEX), jak i CAN (adapter CANable slcan).
  - Po kliknięciu wysyła komendę TX i przechodzi w stan oczekiwania (jaskrawożółte podświetlenie `#fcc419` z ciemnym tekstem `⏳ Nazwa...`).
  - Oczekuje na nadejście odpowiedzi dopasowanej do wzorca `rx_pattern` (`fnmatch` dla tekstu UART, binarnego HEX lub klucza CAN `ID#...*`) w zadanym oknie czasowym `timeout_ms`.
  - Po nadejściu poprawnej odpowiedzi błyska na zielono `#37b24d` wyświetlając precyzyjny czas reakcji urządzenia: `✔ Nazwa (XXms)`.
  - W przypadku upływu limitu czasu bez odpowiedzi błyska na czerwono `#f03e3e`: `✖ Nazwa [TIMEOUT]`.
- **Typ przycisku `🪜 Step` (Przełącznik wielostanowy / Maszyna stanów):**
  - Pozwala zdefiniować uporządkowaną listę kroków (etykieta + ramka TX) w dedykowanej tabeli edytora z możliwością dodawania, usuwania i zmiany kolejności (Góra / Dół).
  - Każde kliknięcie wysyła kolejną ramkę z sekwencji, aktualizuje etykietę na `🪜 Nazwa: Krok` oraz dymek tooltip, zapętlając się w kółko (modulo N).
  - Działa w profilach UART (ASCII/HEX) oraz CAN (sekwencyjna zmiana trybów pracy modułów magistrali).
- **Dynamiczne liczniki kroczące `{CNT}` i `{SEQ}` w ramkach TX:**
  - Funkcja `evaluate_dynamic_tokens()` automatycznie podmienia znaczniki liczników w danych wychodzących przed ich transmisją:
    - `{CNT}` lub `{SEQ}`: licznik kroczący w zakresie `0..255`,
    - `{CNT:min-max}`: licznik dziesiętny w zadanym zakresie (np. `{CNT:00-99}` z zachowaniem szerokości zer wiodących),
    - `{CNT:min-max:X}`: licznik szesnastkowy HEX, np. `{CNT:0-15:X}` dla 4-bitowych liczników sekwencji CAN alive (`0..F`) oraz `{CNT:00-FF:X}` dla 8-bitowych liczników bajtowych.
  - Każdy przycisk utrzymuje swój własny, niezależny stan licznika sekwencji.
- **Intuicyjny Pomocnik Liczników `{CNT}` i Walidator na Żywo (`ButtonEditDialog`):**
  - Dodano dedykowany pasek szybkich szablonów liczników (przyciski-chipy: `+ 1B HEX {CNT:00-FF:X}`, `+ 1B (0..15) {CNT:00-0F:X}`, `+ Półbajt 0{CNT:0-15:X}`, `+ Dec {CNT}`, `+ Dec {CNT:00-99}`) wstawiający gotowe znaczniki do aktywnego pola TX.
  - Wdrożono podgląd na żywo wygenerowanej ramki (`👁 Podgląd wygenerowanej ramki:`) z symulacją sekwencji kolejnych wartości (`➔`).
  - Zaimplementowano walidator składni w locie (`textChanged`) ostrzegający przed nieparzystą liczbą cyfr hex w CAN (np. gdy użyto jednocytrowego tokenu `{CNT:0-15:X}`).
  - Wprowadzono inteligentny przycisk automatycznej naprawy (`⚡ Napraw automatycznie: zamień na {CNT:00-0F:X}`), który jednym ruchem koryguje składnię ramki na pełny 2-cyfrowy bajt.
  - Dodano obsługę jawnego parametru szerokości w formacie tokenów (np. `{CNT:0-15:2X}`).
  - Rozszerzono komunikat błędu `CanFrameError` w `can_support.py` o precyzyjną podpowiedź dotyczącą 2 cyfr hex na bajt.
- **Narzędzie szybkiego zatrzymania pętli `⏹ Stop (N)`:**
  - W nagłówku panelu „Szybkie Akcje” zaimplementowano przycisk `btn_stop_triggers`, który pojawia się automatycznie tylko wtedy, gdy co najmniej jeden przycisk typu `🔁 Trigger` aktywnie nadaje ramki w pętli.
  - Wyświetla liczbę pracujących timerów `⏹ Stop (N)` i jednoetapowo zatrzymuje wszystkie aktywne pętle.
- **Aktualizacja dokumentacji i materiałów szkoleniowych (`build_docs/`):**
  - Dodano Slajd 13 do generatora prezentacji `build_docs/build_docs.py` z kandydatami grafik `zrzut_advanced_buttons.png` oraz szczegółowym opisem wymaganego zrzutu ekranu.
  - Zaktualizowano listę wymaganych zrzutów `REQUIRED_SCREENSHOTS` w `build_docs/cleanup_screenshots.py`.
  - Zaktualizowano podręcznik [`INSTRUKCJA.md`](INSTRUKCJA.md) (Sekcja 4 i 10) z opisem i przykładami użycia nowych typów przycisków oraz tokenów liczników.

### Changed
- Podniesiono wersję aplikacji do `1.8.0` (`APP_VERSION`).
- Zaktualizowano paletę stylów QSS `get_btn_style()` o nowe warianty kolorystyczne: morski cyjan (`#1098ad` dla Step), bursztynowy (`#d97706` dla Query w spoczynku) oraz żółty z ciemnym tekstem (`#fcc419` dla Query w oczekiwaniu na odpowiedź).

### Fixed
- **Precyzyjna kalibracja znaczników w generatorze dokumentacji (`build_docs/build_docs.py`):**
  - Skalibrowano współrzędne i powiązania punktów `[1]`–`[4]` ze zrzutami ekranu na Slajdach 9 (Split View), 11 (Eksport logów i panele akcji), 12 (Tryb magistrali CAN) oraz 13 (Zaawansowane przyciski, licznik `{CNT}` i przycisk Stop pętli).
  - Wyeliminowano rozbieżności między numeracją znaczników na grafice a opisami w punktach (bullets).

## [1.7.2] - 2026-10-16

### Added
- **Blokada formatu transmisji na CAN (`ButtonEditDialog`):**
  - W trybie magistrali CAN (`is_can_mode == True`) pole wyboru "Format TX" jest na stałe zablokowane na wartość `CAN` z podpowiedzią (tooltip) informującą o aktywnym profilu CAN.
- **Dedykowany panel informacyjny o składni CAN dla przycisków:**
  - Wprowadzono estetyczną ramkę informacyjną z dynamicznym opisem składni (`ID#DANE`, `187#01 02`, `18FEF100#AABB`, `65A#R`, wzorce ACK `581#01*`) dostosowaną do aktualnie wybranego typu przycisku (`PUSH`, `TOGGLE`, `HOLD`, `TRIGGER`, `MACRO`).
- **Inteligentne przykłady znikające po kliknięciu (`ClickToClearLineEdit` & `ClickToClearPlainTextEdit`):**
  - Przy tworzeniu nowego przycisku w trybie CAN pola wejściowe są automatycznie wypełniane poprawnymi ramkami demonstracyjnymi (np. `187#01 02 03 04`, `187#01`, `581#01*`) w wyróżniającym się, pochyłym stylu.
  - Kliknięcie myszą w pole (lub rozpoczęcie wpisywania tekstu) natychmiastowo czyści tekst przykładu, umożliwiając bezpośrednie pisanie bez konieczności ręcznego kasowania tekstu.
- **Powiększone wieloliniowe pole sekwencji makra (`ClickToClearPlainTextEdit`):**
  - Zastąpiono jednowierszowe pole `QLineEdit` w trybie `macro` pełnowymiarowym edytorem wieloliniowym z czcionką o stałej szerokości znaków (`Consolas`).
  - Rozszerzono parser wątku `MacroRunner` o pełne wsparcie dla sekwencji rozdzielanych zarówno średnikami `;`, jak i nowymi liniami `\n`.

### Changed
- Zaktualizowano podręcznik [`INSTRUKCJA.md`](INSTRUKCJA.md) (Sekcja 4 i 10) oraz generator dokumentacji [`build_docs/build_docs.py`](build_docs/build_docs.py) (Slajd 4 i 12) o nowe możliwości edytora przycisków i makr.

## [1.7.1] - 2026-10-16

### Added
- **Inteligentne podświetlanie nowo wykrytych portów COM (`PortComboBox`):**
  - Wprowadzono mechanizm różnicowego skanowania portów w `refresh_ports()`, porównujący aktualnie podłączone urządzenia ze zbiorem poprzednio znanych (`_known_ports`).
  - Nowo podłączone porty po naciśnięciu przycisku `🔄` są wyróżniane w rozwiniętym menu `PortComboBox` ciemnozielonym tłem (`#1b4332`), jasnym tekstem (`#8ce99a`) oraz znacznikiem `✨ ... [NOWY]`.
  - W stanie spoczynku kontrolka zachowuje stałą, kompaktową szerokość 82 px (sam identyfikator portu, np. `COM5`), bez zaburzania geometrii pasków narzędziowych ani podziału Split View 50% / 50%.
  - Kolejne kliknięcie przycisku `🔄` (gdy nie wykryto dalszych nowych urządzeń) automatycznie usuwa podświetlenie.
  - Informacja o nazwie nowo wykrytego portu pojawia się bezpośrednio w konsoli logów (`wykryto nowy: COMxx`).
- **Automatyzacja i Walidacja Generatora Dokumentacji (`build_docs/`):**
  - Rozszerzono strukturę slajdów `SLIDES_DATA` w `build_docs/build_docs.py` do 12 slajdów, dodając Slajd 12 dla Trybu Magistrali CAN (`zrzut_can_mode.png`).
  - Wprowadzono pole `image_description` do wszystkich slajdów w `SLIDES_DATA`, precyzujące wymaganą zawartość zrzutów ekranu dla poszczególnych funkcjonalności.
  - Zaimplementowano funkcję `check_and_report_missing_images()`, która weryfikuje obecność grafik na dysku i w razie ich braku wypisuje w terminalu szczegółowy monit z instrukcją co zrzut ma przedstawiać.
  - Wdrożono w `generate_pdf()` i `generate_pptx()` estetyczne ramki zastępcze (placeholdery) informujące o oczekiwaniu na grafikę wraz z formatowanymi wytycznymi.
  - Zaktualizowano mapę `REQUIRED_SCREENSHOTS` w `build_docs/cleanup_screenshots.py` o Slajd 12.
- **Aktualizacja Podręcznika Użytkownika (`INSTRUKCJA.md`):**
  - Zaktualizowano Sekcję 2 o opis podświetlania nowo podłączonych portów COM (`✨ ... [NOWY]`).
  - Powiązano Sekcję 10 (Tryb Magistrali CAN) ze zrzutem ekranu `zrzut_can_mode.png`.

### Changed
- **Aktualizacja Zasad Rozwoju Projektu (`GEMINI.md`):**
  - Wprowadzono do Sekcji 1 i 4 bezwzględny wymóg aktualizowania `INSTRUKCJA.md` oraz `build_docs/build_docs.py` po każdej implementacji nowej funkcji.
  - Nałożono na AI obowiązek każdorazowego proszenia użytkownika o brakujący zrzut ekranu wraz ze szczegółowym opisem jego wymaganej zawartości.

## [1.7.0] - 2026-10-15

### Added
- **Moduł Obsługi Magistrali CAN (`can_support.py`):**
  - Lekka klasa reprezentacji ramki `CanFrame` (arbitration_id, is_extended, is_remote, dlc, data, timestamp), niezależna od python-can na potrzeby testów i formatowania.
  - Parser składni w stylu `cansend` (`parse_can_frame`) z rygorystyczną walidacją i czytelnymi komunikatami błędów (`CanFrameError`): obsługa ramek standardowych 11-bit (`187#01 02`), rozszerzonych 29-bit (`18FEF100#AABB`), zdalnych RTR (`65A#R`, `65A#R4`) oraz pustych o DLC=0 (`3D0#`).
  - Normalizator wzorców potwierdzeń ACK dla przycisków typu TOGGLE (`normalize_can_ack_pattern`) wspierający dopasowania `fnmatch` (np. `581#01*`, `581#`, `*#AA*`).
  - Bezpieczny wątek `CanWorker(QThread)` komunikujący się z biblioteką `python-can` (interfejs `slcan`), wyposażony w kolejkę nadawczą `tx_queue` FIFO oraz grupowanie odbieranych ramek w paczki (`frames_received(list)` do 20 ms lub 500 ramek), co całkowicie eliminuje zamrażanie pętli zdarzeń GUI przy intensywnym ruchu na magistrali.
- **Dedykowany Tryb Telemetrii Live Watch dla CAN:**
  - Wskaźnik czasu cyklu ramki $\Delta t$ w milisekundach (`Δ ... ms`) wyliczany w czasie rzeczywistym z różnicy timestampów kolejnych ramek o danym identyfikatorze.
  - Automatyczne sortowanie wierszy rosnąco według CAN ID (`insert_watch_row_sorted`): najpierw ramki standardowe 11-bit (od `000` do `7FF`), a po nich ramki rozszerzone 29-bit.
  - Błysk zmienionych bajtów w ramce na złoto-pomarańczowo (`#5c3c00` / `#ffd43b`) na 750 ms na poziomie pojedynczych bajtów hex.
  - Automatyczne przechwytywanie identyfikatorów (`can_watch_auto: true`) z inteligentną pamięcią sesyjną (`_unpinned_can_ids`), zapobiegającą ponownemu pojawianiu się identyfikatorów ręcznie odpiętych przez użytkownika.
- **Pełna Integracja CAN z UI i Przyciskami:**
  - Obsługa wysyłania ramek CAN z poziomu dolnego terminala, przycisków szybkich akcji (`PUSH`, `TOGGLE`, `HOLD`, `TRIGGER` jako pętla cykliczna, `MACRO` jako sekwencja ramek z `sleep(ms)`).
  - W edytorze przycisków dodano format `"CAN"` z podpowiedziami składni (np. `187#01 02`, ACK: `581#01*`).
  - Nowa zakładka "Połączenie" w oknie edycji konfiguracji (`ConfigEditDialog`): wybór transportu (`Serial` vs `CAN – CANable (slcan)`), wybór prędkości Bitrate (`10k`..`1M`), przełącznik trybu nasłuchu `Listen-only` oraz automatycznego Live Watch.
  - Automatyczne profilowanie portów CAN: pierwsze połączenie z portem w trybie CAN tworzy profil `COMxx_CAN.json`.
  - Dynamiczne dostosowywanie paska narzędziowego karty (`apply_transport_ui`): zamiana etykiety `Baud:` na `Bitrate:`, ukrywanie opcji UART (ASCII/HEX, EOL, DTR, RTS, Reset MCU) oraz udostępnienie akcji `Listen-only` i `Wyzeruj wiersze Live Watch` w menu sprzętowym.
  - Wyciąganie identyfikatora CAN z linii logu w menu kontekstowym PPM konsoli (`📌 Przypnij do Live Watch`).

### Changed
- Podniesiono wersję aplikacji do `1.7.0` (`APP_VERSION = "1.7.0"`).
- Rozszerzono strukturę konfiguracji profili JSON w `get_default_config()` i `load_config()` o klucze: `transport`, `can_bitrate`, `can_listen_only`, `can_watch_auto` z pełną kompatybilnością wsteczną dla starszych plików konfiguracyjnych.
- Zaktualizowano tytuły kart i nagłówki Split View o oznaczenia CAN (np. `🟢 COM20 · CAN 500k`).

### Fixed
- Zabezpieczono aplikację przed blokowaniem GUI przy natłoku danych na magistrali CAN poprzez buforowanie paczek ramek w `CanWorker`.
- Wyeliminowano problem niepożądanego ponownego przypinania ręcznie usuniętych identyfikatorów CAN w panelu Live Watch przy aktywnym `can_watch_auto`.

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
