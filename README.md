# Serial Commander

Zaawansowany, asynchroniczny terminal klastrowy do debugowania i wysyłania komend do urządzeń na porcie szeregowym (COM), stworzony w technologii PyQt6 oraz PySerial.

## Główne Możliwości
1. **Multi-Tab Architecture:**
   * Otwieraj wiele niezależnych sesji urządzeń w kartach. Każda ma własny wątek odczytujący, dedykowany plik JSON i obsługę portu COM.
   * Moduł zapobiegający otwarciu duplikatów portu – aplikacja dba, aby nowy port był poprawnie przypisywany.
2. **Klawiatura Konfigurowalnych Przycisków (10 slotów):**
   * Elastyczny system programowania zachowań przycisku z formularzem edycji na PPM.
   * `⚡ Push` - jednorazowe wysłanie ramki (w HEX lub ASCII).
   * `🔘 Toggle` - włącznik sprzętowy z rygorystycznym sprzętowym weryfikowaniem potwierdzeń odpowiedzi (ACK). Kolor zmieni się na zielony *tylko*, gdy urządzenie odpowie określoną sekwencją bajtów.
   * `⏳ Hold` - stan sprzętu zmienia się, dopóki trzymasz wciśnięty przycisk myszy.
   * `🔁 Trigger` - wbudowany asynchroniczny generator (pętla) wysyłający klatkę non-stop w zadanych odstępach czasowych (ms).
   * `📜 Macro` - silnik sekwencyjny. Pozwala zapisać ciąg instrukcji oddzielonych średnikiem. Umożliwia wykorzystywanie instrukcji np. `sleep(500)`, aby odczekać milisekundy przed kolejną paczką bajtów. Posiada thread-safe sygnały zrzucające dane na konsole.
3. **Zaawansowany RX Filter & Parser (fnmatch):**
   * Maskuj i koloruj w logach przychodzące ramki sprzętowe dopasowując je do wzorców z gwiazdką (np. `*error*` koloruj na żółto).
   * Zmieniaj tekst przed wyświetleniem na terminalu.
   * **System Zapory (Whitelist):** Jeżeli dodasz zaledwie jeden filtr "Dozwolony", cały terminal sprzętowy zaciska nasłuchiwacz tylko i wyłącznie na te zadeklarowane frazy, włączając tryb alarmowy w GUI.
4. **Rozbudowany Eksport i Konsola:**
   * Konsola z czcionką monospaced, logująca TX, RX z ułamkami sekund i zachowująca rygor thead-safe.
   * Eksport sesji sprzętowej do pliku raportu: `HTML` z CSS, `Markdown` lub zrzut Raw `TXT` w celu załączenia np. do zadań w systemach Jira/Trello.
5. **UI / UX Design:**
   * Pełny Qt Style Sheets z interaktywnymi efektami wciskania przycisków (`:pressed`, przesunięcie tekstu).
   * Intuicyjne okna typu `QTableWidget` i `QStackedWidget` ze sztywną architekturą braku błędu "miliona okien modalnych". Zintegrowane tabele do usuwania/edycji filtrów i parserów na żywo.

6. **Znaczniki (Markers) i Sortowanie:**
   * Opcjonalne tagowanie logów TX nazwą przycisku, który wywołał zdarzenie (świetne do monitorowania, która automatyzacja wysłała dany pakiet).
   * Alfabetyczne, twarde sortowanie list (Filtry/Parsery) na żywo po kliknięciu w kolumny w menedżerach.
