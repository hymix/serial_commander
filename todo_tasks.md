# Plan Wdrożeniowy (Terminal Diagnostyczny)

## Faza 1: Niezawodność i Stabilność
- [DONE] Task 1.1: Wdrożenie atomowego zapisu (Atomic Save) w funkcji save_config.
- [DONE] Task 1.2: Dławienie sygnałów (Signal Throttling/Chunking) w SerialWorker, aby uniknąć zamrażania GUI.
- [DONE] Task 1.3: Wdrożenie limitu wielkości konsoli (QTextEdit) z polem konfiguracyjnym w GUI (np. max 5000 linii).

## Faza 2: Przebudowa Architektury (System Kart)
- [DONE] Task 2.1: Wydzielenie logiki połączenia i GUI z SerialApp do nowej klasy SerialTab (dziedziczącej po QWidget).
- [DONE] Task 2.2: Stworzenie nowej klasy głównej (MainWindow) z QTabWidget oraz przyciskiem dodawania/usuwania nowych kart.
- [DONE] Task 2.3: Zapewnienie niezależności konfiguracji i wątków (SerialWorker) pomiędzy kartami.

## Faza 3: Funkcjonalności "Pro"
- [DONE] Task 3.1: Eksport Logów (Przycisk do zapisu zawartości konsoli do pliku .txt ze znacznikiem czasu).
- [DONE] Task 3.2: Markery Czasowe (Przycisk/pole do wstrzykiwania wizualnego odcięcia/notatki w strumieniu logów).
- [DONE] Task 3.3: Makra (Nowy typ przycisku macro, który pozwala wysyłać kilka komend z opóźnieniami np. AA; delay(100); BB).
- [DONE] Task 3.4: Konfigurowalny Parser (Narzędzie GUI do definiowania reguł podmieniania/parsowania trudnych ramek HEX na tekst ludzki).
