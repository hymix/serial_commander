# Changelog Serial Commander

Wszystkie znaczące zmiany w tym projekcie będą udokumentowane w tym pliku.

## [2026-10-05]
### Dodano
- Funkcję wyszukiwania tekstu w konsoli (dostępną przez skrót `Ctrl+F` lub z menu pod prawym przyciskiem myszy). Wyszukiwarka pojawia się jako poręczny popup i oferuje przeszukiwanie logów w przód i w tył, pokazując łączną liczbę znalezionych pasujących wyników.
- Opcję włączania/wyłączania ("Aktywny" checkbox) dla filtrów i parserów bezpośrednio na liście w Menedżerze Filtrów i Menedżerze Parserów. Pozwala to na tymczasowe dezaktywowanie reguł bez konieczności ich usuwania.
- Nową wytyczną do pliku `GEMINI.md` wymagającą dokumentowania wszystkich wprowadzanych modyfikacji w tym pliku (`changelog.md`).
- Przycisk "▼ Wróć do najnowszych (w dół)" w terminalu, który pojawia się po przewinięciu logów do góry i pozwala szybko wrócić do najnowszych wiadomości.

### Zmieniono
- Logikę działania autoscrollingu konsoli w `gui.py`. Jeśli użytkownik samodzielnie przewinie wiadomości wyżej (aby zobaczyć historię), napływające nowe logi nie będą go już agresywnie wyrzucać na sam dół. Zastosowano inteligentny `append` bez wywoływania wymuszonego przeskoku do końca dokumentu, o ile użytkownik nie jest na najniższej pozycji suwaka.
- Poprawiono logikę wyświetlania pływającego okienka wyszukiwania (`Ctrl+F`). Odtąd otwiera się ono precyzyjnie w prawym górnym rogu wewnętrznego obszaru konsoli (bez przekłamań współrzędnych). Okienko zachowało funkcję bycia niezależnym panelem narzędziowym (można je dowolnie przeciągać po ekranie).
- Wzbogacono wyszukiwarkę o wsparcie dla symbolu wieloznacznego `*` (wildcards). Można teraz wpisywać m.in. `*test` (kończy się na test), `test*` (zaczyna się na test) lub `*test*` (zawiera test), co program w locie tłumaczy na bezpieczne wyrażenia regularne (regex).

### Naprawiono
- Krytyczny błąd powodujący crash programu podczas próby zapisu logów do pliku. Zjawisko wynikało z kolizji nazw obiektów (klasa `datetime.datetime.now()` wywoływana na module już zaimportowanym jako klasa `datetime`).
