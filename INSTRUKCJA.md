# Serial Commander v1.7.0 — Dokumentacja i Instrukcja Obsługi

**Serial Commander** to zaawansowany, wielowątkowy terminal diagnostyczny COM / HMI stworzony w technologii Python (`PyQt6`, `pyserial`, `python-can`), zaprojektowany specjalnie do debugowania systemów wbudowanych (STM32, ESP32, adaptery CANable slcan, sieci CAN, RS-485 oraz protokołów binarnych i ASCII).

---

## 1. Główny Interfejs i Ergonomia Pracy

![Główny interfejs i Live Watch](obraz_4.png)

Układ programu został zoptymalizowany pod kątem naturalnego skupienia wzroku podczas debugowania sprzętu:
1. **Pasek Zakładek (Góra):** Wyświetla otwarte sesje wraz z wizualnym statusem połączenia:
   * `🟢 COM22` — port aktywny (połączony),
   * `⚪ COM20` — port w spoczynku (rozłączony).
2. **Górny Pasek Połączenia i Narzędzi:** Zawiera konfigurację portu, prędkości, trybu odbioru (`ASCII` / `HEX`) oraz narzędzia konsoli (`🗑️ Wyczyść`, `💾 Zapisz Logi`, `📌 Marker`, `🔍 Szukaj`, `Limit linii`).
3. **Lewy Panel „Szybkie Akcje (PPM)”:** Zawiera 10 programowalnych przycisków oraz wybór profilu `.json`. Panel można w każdej chwili zwinąć przyciskiem **`◀ Ukryj`**, oddając 100% szerokości dla konsoli.
4. **Sekcja `📌 Live Watch`:** Przypięte ramki telemetryczne odświeżane w czasie rzeczywistym nad głównym strumieniem logów.
5. **Dolny Pasek Komend (TX):** Umieszczony bezpośrednio pod najnowszymi logami. Obsługuje:
   * wysyłanie komend klawiszem `Enter`,
   * **historię wysłanych komend** pod strzałkami `↑` (Góra) oraz `↓` (Dół),
   * wybór formatu (`ASCII` / `HEX`) oraz znaku końca linii (`CRLF \r\n`, `LF \n`, `CR \r`, `Brak EOL`).

---

## 2. Wybór Portu COM i Prędkości Baudrate

![Rozwinięta lista portów COM](Zrzut ekranu 2026-10-15 144322.png)

* **Inteligentny `PortComboBox`:** W stanie spoczynku lista wyboru portu jest wąska (`82 px`) i pokazuje wyłącznie sam numer portu (np. `COM20`), oszczędzając miejsce na pasku narzędziowym. Po kliknięciu lista automatycznie rozszerza się do `340 px` i wyświetla pełną nazwę sterownika z systemu (np. `STMicroelectronics Virtual COM Port`, `USB-Enhanced-SERIAL CH343`).
* **Przycisk `🔄` i wykrywanie nowych portów:** Odświeża listę dostępnych w systemie portów COM w locie. Nowo podłączone urządzenia (np. wpięty konwerter USB-UART lub adapter CANable) są po rozwinięciu listy wyróżniane ciemnozielonym tłem, jasnym tekstem oraz etykietą **`✨ COMxx — Opis... [NOWY]`**. Ponowne kliknięcie `🔄` (gdy nie ma dalszych nowych portów) automatycznie usuwa podświetlenie.
* **Prędkość Baudrate:** Zawiera szereg standardowych prędkości aż do **`1000000` bps**. Na samym dole listy znajduje się opcja **`Własny...`**, która pozwala wpisać dowolną niestandardową prędkość transmisji.

---

## 3. Sterowanie Sprzętowe Liniami DTR / RTS i Reset MCU

![Menu sprzętowe DTR RTS Reset](Zrzut ekranu 2026-10-15 144357.png)

Obok przycisku `Połącz` / `Rozłącz` znajduje się przycisk menu sprzętowego **`⚙️`**, przydatny podczas pracy z płytkami podłączonymi bezpośrednio przez konwerter USB-UART lub wbudowany debugger:
* **`Linia DTR (Data Terminal Ready)`** — ręczne wymuszenie stanu logicznego na pinie DTR.
* **`Linia RTS (Request To Send)`** — ręczne wymuszenie stanu logicznego na pinie RTS.
* **`🔄 Impuls Reset MCU (DTR/RTS 100ms)`** — generuje 100-milisekundowy impuls resetujący mikrokontroler, pozwalając uchwycić w konsoli logi startowe bootloadera bez sięgania ręką do przycisku Reset na płytce.

---

## 4. Programowalne Przyciski „Szybkie Akcje” i Sprzętowy ACK

![Edycja przycisku Szybkich Akcji](Zrzut ekranu 2026-10-15 144053.png)

> **Wskazówka:** Aby skonfigurować lub edytować dowolny z 10 przycisków po lewej stronie, **kliknij na niego Prawym Przyciskiem Myszy (PPM)**. Po najechaniu kursorem na skonfigurowany przycisk wyświetli się dymek (Tooltip) z podglądem przypisanych ramek.

Każdy przycisk może pracować w jednym z **5 trybów** (w formacie `ASCII` lub `HEX`):
1. **`⚡ Push` (Niebieski):** Pojedyncze kliknięcie wysyła zdefiniowaną ramkę `TX` jeden raz.
2. **`🔘 Toggle` (Zielony ON / Czerwony OFF):** Przełącznik dwustanowy z **weryfikacją sprzętową ACK**. Kliknięcie wysyła ramkę `TX ON` lub `TX OFF`, ale **kolor i stan przycisku na panelu zmieni się TYLKO wtedy, gdy urządzenie odeśle zdefiniowaną ramkę potwierdzenia (`ACK ON` / `ACK OFF`)**.
3. **`⏳ Hold` (Pomarańczowy):** Wysyła ramkę `TX (Wciśnięty)` w momencie naciśnięcia przycisku myszą oraz `TX (Puszczony)` w momencie zwolnienia przycisku.
4. **`🔁 Trigger` (Szaroniebieski / Pomarańczowy w pracy):** Generator pętli asynchronicznej. Po kliknięciu cyklicznie wysyła ramkę `TX` co zadany interwał (w milisekundach) aż do ponownego kliknięcia.
5. **`📜 Macro` (Fioletowy):** Wykonuje sekwencję komend rozdzielonych średnikiem z obsługą opóźnień czasowych, np.:
   `AA 01; sleep(500); BB 02; sleep(1000); CC 03`.

Kliknięcie **`Usuń / Wyczyść`** w oknie edycji natychmiastowo resetuje przycisk do stanu nieużywanego (`+ Przypisz akcję (PPM)`).

---

## 5. Praca z Konsolą: Zaznaczanie Tekstu i Menu Kontekstowe (PPM)

![Menu kontekstowe konsoli PPM](Zrzut ekranu 2026-10-15 144223.png)

> **Ważne:** Aby w menu kontekstowym (PPM) pojawiły się opcje szybkiego dodawania do Filtra oraz Parsera, **najpierw zaznacz myszką interesujący Cię fragment tekstu w konsoli logów**, a następnie kliknij Prawym Przyciskiem Myszy.

Dostępne akcje w menu PPM konsoli:
* **`📌 Przypnij do Live Watch (klucz)`** — automatycznie wyciąga identyfikator modułu (np. `CAN2_TX` lub `[IO_MGR]`) i przypina go do tablicy telemetrycznej u góry ekranu.
* **`🌪️ Dodaj do Filtra (*tekst*)`** — automatycznie otacza zaznaczony fragment gwiazdkami (np. `*CAN2_TX*`), kopiuje go do schowka, rozwija szufladę filtrów i wkleja gotowy wzorzec.
* **`🧩 Dodaj do Parsera (*tekst*)`** — wkleja zaznaczony fragment z gwiazdkami `*...*` jako wzór parsera i ustawia kursor bezpośrednio w polu tekstu zastępczego.
* **`🔍 Szukaj w logach (Ctrl+F)`** — otwiera pływającą wyszukiwarkę z licznikiem trafień i nawigacją `▲` / `▼`.
* **`▼ Wróć do najnowszych logów (Auto-scroll)`** — gdy przewiniesz konsolę w górę, automatyczne przewijanie zatrzymuje się, abyś mógł spokojnie analizować historię. Kliknięcie niebieskiego pływającego przycisku u dołu przywraca podgląd na żywo.

---

## 6. Moduł `📌 Live Watch` — Telemetria i Błyski Zmian

![Panel Live Watch i szuflada filtrów](Zrzut ekranu 2026-10-15 143034.png)

Moduł **Live Watch** pozwala obserwować często odświeżane ramki statusowe w jednym stałym wierszu u góry konsoli (jak w analizatorach magistrali CAN):
* **Dwa sposoby przypinania:**
  1. **Ręcznie z GUI:** Kliknij PPM na linię w konsoli -> `📌 Przypnij do Live Watch`.
  2. **Automatycznie z kodu mikrokontrolera (`@`):** Jeśli wyślesz po UART linię poprzedzoną znakiem `@` (np. `@[IO_MGR] BTN: 0x000 | ADC: 514`), program sam rozpozna prefiks `[IO_MGR]`, przypnie go do Live Watch i usunie znak `@`.
* **Podświetlanie zmian (Token Diffing):** Program dzieli wiadomość na pojedyncze wartości i porównuje z poprzednim stanem. Stały tekst pozostaje szary, a **tylko te wartości, które uległy zmianie (np. `531` i `13%`), błyskają przez 750 ms na złoto-pomarańczowo**.
* **Ukrywanie w głównym logu:** Przypięte ramki są domyślnie wycinane z głównego okna konsoli poniżej, aby nie powodować przewijania innych logów. Zaznaczenie opcji **`Pokaż też w konsoli`** przywraca ich podwójne wyświetlanie.
* **Ergonomia i limit 70%:** Przycisk **`▲ Ukryj`** po prawej stronie pozwala zwinąć listę przypięć. Jeśli liczba przypiętych wierszy przekroczy **70% wysokości konsoli**, automatycznie włącza się suwak przewijania.

---

## 7. Filtry RX, Parsery oraz Tryb `⚠ ZAPORA` (Whitelist)

![Tryb Zapory i szuflada filtrów](Zrzut ekranu 2026-10-15 144422.png)

Kliknięcie przycisku **`🌪️ Filtry (N)`** rozwija szufladę szybkiego zarządzania ruchem przychodzącym:
* **Filtry RX (`Ukryj` / `Koloruj` / `Dozwolony`):**
  * `Ukryj` — całkowicie ignoruje linie pasujące do wzorca (np. `*main task*`).
  * `Koloruj` — wyróżnia pasujące logi jednym z 16 kolorów.
  * `Dozwolony (Whitelist)` — włącza **Tryb Zapory (`⚠ ZAPORA`)**. Na górnym pasku zapala się czerwony przycisk ostrzegawczy, a terminal odrzuca wszystkie logi poza tymi, które pasują do reguł Whitelist.
* **Parsery Payloadu:** Pozwalają zastąpić surowe ramki (np. `*AA 01*`) czytelnym opisem (np. `[START SYSTEMU]`) wyświetlanym w złotym kolorze.

![Menadżer Filtrów](Zrzut ekranu 2026-10-15 143147.png)

W oknach **Menadżer Filtrów** oraz **Menadżer Parserów** możesz w każdej chwili włączać i wyłączać poszczególne reguły za pomocą checkboxa **`Aktywny`**, sortować je klikając w nagłówki kolumn lub edytować.

---

## 8. Symetryczny Widok Podzielony (Split View 50% / 50%)

![Widok podzielony ze zwiniętymi panelami](Zrzut ekranu 2026-10-15 143340.png)

Gdy otworzysz dwie karty (lub klikniesz przycisk **`◫ Widok obok siebie (Lewo / Prawo)`**), program przechodzi w tryb równoległej pracy na dwóch portach COM:
* **Idealna symetria 50% / 50%:** Okno automatycznie rozszerza się do `1440 px`, a obie karty zajmują dokładnie po połowie ekranu.
* **Skrajne położenie paneli bocznych:** Panele przycisków domyślnie zwijają się na zewnętrzne krawędzie okna: **`▶ Akcje`** na lewym skraju dla lewej karty oraz **`Akcje ◀`** na prawym skraju dla prawej karty.

![Widok podzielony z rozwiniętymi panelami na skrajach](Zrzut ekranu 2026-10-15 143355.png)

Po rozwinięciu paneli szybkich akcji znajdują się one po przeciwnych, skrajnych stronach ekranu, dzięki czemu obie konsole logów zawsze sąsiadują bezpośrednio ze sobą w centrum.

---

## 9. Przełączanie Kart w Widoku Podzielonym (Obsługa 3+ Kart)

![Menu wyboru karty w nagłówku Split View](Zrzut ekranu 2026-10-15 144530.png)

Gdy masz otwartych więcej niż 2 karty (np. 3 lub 4 porty COM jednocześnie):
* **Wybór karty bezpośrednio w miejscu nazwy profilu:** Kliknij na nazwę portu/profilu w nagłówku lewego lub prawego okna (np. **`[LEWA] 🟢 COM22 — Profil: COM22.json ▾`**).
* **Brak duplikatów w menu:** Rozwinięta lista wyświetla wyłącznie pozostałe otwarte karty (karta aktualnie widoczna w tym oknie jest ukryta na liście).
* **Zamiana miejscami (`Swap ⇄`):** Wybór karty przypisanej obecnie do drugiej połowy ekranu (lub kliknięcie przycisku **`⇄ Zamień miejscami`** na górnej belce) błyskawicznie zamienia miejscami lewą i prawą kartę.
* **Powrót do pojedynczego okna:** Kliknięcie **`🗂️ Widok zakładek (1 okno)`** przełącza interfejs z powrotem na klasyczne zakładki i automatycznie zmniejsza szerokość okna głównego do kompaktowego rozmiaru pojedynczej karty (`940 px`).

---

## 10. Tryb Magistrali CAN (Adapter CANable / slcan)

![Tryb Magistrali CAN i telemetria Live Watch](zrzut_can_mode.png)

W wersji **1.7.0** aplikacja Serial Commander zyskała natywną obsługę magistrali CAN za pośrednictwem popularnych adapterów **CANable** (lub kompatybilnych z firmware `slcan` udostępniających wirtualny port COM).

### Konfiguracja i Połączenie z CAN
1. Podłącz adapter CANable do komputera przez USB. Zostanie wykryty jako standardowy port COM (np. `COM20`).
2. Kliknij przycisk **`Edytuj`** obok profilu konfiguracyjnego i przejdź do zakładki **`Połączenie`**.
3. Jako **Typ połączenia** wybierz **`CAN – CANable (slcan)`**.
4. Wybierz prędkość transmisji **Bitrate CAN** (standardowe prędkości: `10k`, `20k`, `50k`, `83.3k`, `100k`, `125k`, `250k`, `500k`, `750k`, `1M`).
5. Opcjonalnie włącz:
   * **`Tryb nasłuchu (Listen-only)`** — adapter nie wysyła bitów ACK ani ramek błędów (idealne do bezpiecznego monitorowania magistrali pojazdu lub maszyny bez zakłócania ruchu).
   * **`Automatycznie przypinaj każde nowe ID do Live Watch`** — automatyczne monitorowanie wszystkich pojawiających się na magistrali identyfikatorów.
6. Kliknij **`Zapisz Ustawienia`**. Pasek karty automatycznie dostosuje się do trybu CAN (przełącznik prędkości zmieni się na `Bitrate:`, a kontrolki tekstowe UART zostaną ukryte).
7. Kliknij **`Połącz`**. Przy pierwszym połączeniu profil zostanie automatycznie zapisany jako `COMxx_CAN.json`.

### Nadawanie Ramek CAN (Składnia `cansend`)
W polu wprowadzania komend u dołu lub w przyciskach szybkich akcji stosuj standardową składnię `ID#DANE`:
* `187#01 02 03 04` — ramka standardowa (11-bit ID `0x187`, 4 bajty danych, spacje są dozwolone).
* `187#01020304` — ta sama ramka w postaci zwartej bez spacji.
* `18FEF100#AABB` — ramka rozszerzona (29-bit ID `0x18FEF100`, 2 bajty danych).
* `65A#R` lub `65A#R4` — ramka zdalna RTR (z opcjonalnym kodem DLC).
* `3D0#` — ramka z zerową długością danych (DLC = 0).

### Telemetria Live Watch w Trybie CAN
W trybie CAN panel **Live Watch** działa jak profesjonalny analizator magistrali:
* **Sortowanie według ID:** Ramki są automatycznie uporządkowane rosnąco według CAN ID (najpierw ramki 11-bit, potem 29-bit).
* **Pomiar czasu cyklu ($\Delta t$):** Obok licznika aktualizacji `#N` wyświetlany jest w czasie rzeczywistym czas cyklu od poprzedniej ramki o tym samym ID (np. `Δ   100 ms`).
* **Błysk Zmian Bajtów:** Zmienione bajty w ramce podświetlają się na złoto-pomarańczowo na 750 ms, pozwalając natychmiast dostrzec zmienne telemetryczne (np. odczyty czujników, liczniki alive).
* **Odpinanie:** Kliknięcie `✕` odepnie dany identyfikator, a sesyjny mechanizm zapamięta wybór i nie będzie go ponownie automatycznie przechwytywał.

### Przyciski Szybkich Akcji i Potwierdzenia ACK w CAN
* W edytorze przycisków (`PPM na przycisk`) wybierz format payloadu **`CAN`**.
* Dla przycisków **`🔘 Toggle`** możesz zdefiniować potwierdzenie ACK dopasowywane do odebranej ramki CAN za pomocą wzorców z gwiazdką, np.:
  * `TX ON`: `187#01`, `ACK ON`: `581#01*`
  * `TX OFF`: `187#00`, `ACK OFF`: `581#00*`
  * `ACK ON`: `581#` (dopasowanie do dowolnej ramki z ID `0x581`).
* Przycisk **`🔁 Trigger`** działa w trybie CAN jako cykliczny generator ramki co zadany interwał w milisekundach.
* Przycisk **`📜 Macro`** pozwala wykonać sekwencję ramek z opóźnieniami, np. `187#01; sleep(100); 187#00`.