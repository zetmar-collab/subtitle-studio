# Subtitle Studio + Szept 0.6.0

Wydanie realizuje poprawki i funkcje z audytu 0.5.0 oraz dodaje lokalną korektę AI przez Ollamę. Oryginalny raport audytu pozostaje dokumentem historycznym; jego numery linii dotyczą kodu 0.5.0.

## Poprawki z audytu

| Pozycja | Zmiana i weryfikacja |
|---|---|
| A1: ochrona źródeł | Wspólna kontrola celu zapisu projektu i presetu; blokuje film, audio, logo i źródła napisów. Testy zachowania pliku bajt po bajcie. |
| A2: odzyskiwanie | Każda sesja ma własny plik i blokadę. Nie usuwa kopii innych aktywnych sesji. Odzyskiwanie starej kopii uzyskuje jej blokadę. |
| A3: brak filmu | Otwarcie projektu bez filmu czyści odtwarzacz, klatkę, metadane, falę i zakres. |
| A4: analiza w tle | Numerowanie żądań odrzuca spóźnione wyniki i błędy. Otwarcie projektu z filmem analizuje go poza GUI. |
| A5/A6: walidacja | Projekt i preset używają wspólnej walidacji stylu; sprawdzane są struktura i granice czasów słów, typy, kolory i metadane. |
| A7: FFmpeg | Obie karty korzystają z jednej usługi lokalizacji: obok EXE, w pakiecie i w PATH. |
| A8: długość audio | Przekazanie ścieżki audio ustala metadane w tle. Zerowa długość jest odrzucana przed usunięciem segmentów ASR i w workerze. |
| A9: podział | Pojedynczego słowa nie można podzielić na pusty napis. Przy aktualnych czasach słów podział używa ich granic; bez nich użytkownik wskazuje podział tekstu. |
| P1: wydajność | Sprawdzanie nakładania po sortowaniu, cache kontroli jakości i ponowne użycie komórek tabeli. |
| P2/P4: wspólne usługi | Analiza mediów w tle; przycisk pisowni filmu prowadzi do wspólnego edytora tekstu i słowników Szept. |
| P3: pamięć | Budżet historii ok. 64 MiB, cache grafik 128 MiB; rozmiar grafik sprawdzany przed dekodowaniem. Bardzo duże grafiki są skalowane do budżetu cache. |
| Procesy | Rollback nieudanego startu workera; niezależny nadzorca anulowania i bezczynności renderera. Fala audio ma anulowanie. |

## Wspólny projekt sesji

**Projekt → Zapisz sesję** albo **Ctrl+S** zapisuje film, warstwy, style, transkrypcję, oryginalny tekst ASR, oceny słów i powiązanie ścieżki. Działa również z karty Transkrypcja. **Zapisz sesję jako** tworzy osobny plik. **Nowa sesja / Ctrl+N** resetuje obie karty po obsłużeniu niezapisanych zmian. Historie edycji pozostają osobne dla obu kart.

Format JSON ma wersję **2**. Pliki wersji 1 są nadal czytane i nie są samoczynnie przepisywane. Zapis nowej wersji następuje dopiero przy zapisie projektu. Aplikacja 0.5.0 nie odczytuje formatu 2; zachowaj poprzedni plik lub użyj „Zapisz sesję jako”, jeżeli potrzebujesz go w starszym programie. Otwieranie z karty Szept rozpoznaje sesję lub pozwala zaimportować samodzielny projekt Szept.

Ponowne **Transkrypcja → film** proponuje aktualizację powiązanej ścieżki i pokazuje liczbę zmian. Aktualizacja zachowuje nazwę i styl. Można zamiast tego dodać osobną ścieżkę albo anulować. Operację można cofnąć.

## Funkcje dostępne w menu Narzędzia

1. **Film → napisy → MP4** — panel etapów: wybór filmu, model/język, ASR, przegląd, przekazanie ze stylem i eksport. Model pobiera się wyłącznie jawnie w menedżerze. Można wracać do obu edytorów między etapami.
2. **Napraw synchronizację** — pokazuje proponowane czasy i pozostałe uwagi czytelności. Niczego nie stosuje przed kliknięciem „Apply”. Zachowuje cały tekst, rozdziela nakładanie, ogranicza napisy do filmu. Zmiana granic unieważnia wyrównanie słów. Wymaga znanej długości filmu i nie dopisuje treści pustych napisów.
3. **Słowa na fali audio** — zaznacz napis. Przeciągaj granice słów lub edytuj ms w tabeli; odsłuchuj słowo z kontekstem i podglądem podświetlenia. Zatwierdzenie zapisuje jedną operację cofania, anulowanie zachowuje poprzednie czasy.
4. **Fragmenty do sprawdzenia** — modelessowa lista flag ASR, brakujących czasów słów i ocen słów poniżej 0,6. Oceny są przybliżone, nie stanowią pewności poprawności. Zaznaczenie prowadzi do segmentu, można odsłuchać, poprawić tekst w edytorze i oznaczyć jako sprawdzony. Oznaczenie można cofnąć.
5. **Kolejka eksportów** — wybierz katalog, nazwę bazową i warianty. Każdy może mieć własne wymiary, dopasowanie/przycięcie oraz pozycję aktywnej ścieżki napisów. Dostępne H.264/MP4, H.265/MP4 i VP9/WebM. Zadania zachowują migawkę projektu, wykonują się kolejno i nie zmieniają się wskutek późniejszej edycji filmu. Istniejące pliki wymagają zgody na nadpisanie.
6. **Pokaz zdjęć i klipów** — ułóż 1–40 materiałów, podaj czasy i osobne audio. Dla samych zdjęć można automatycznie dopasować ekspozycje do długości audio. Opcje: dopasowanie/przycięcie, łagodne przejście przez czerń i powolne przybliżenie zdjęć. Dźwięk wejściowych klipów jest zastępowany. Pokaz można zapętlić do końca audio, zatrzymać ostatnią klatkę albo zakończyć na krótszym materiale.
7. **Pisownia AI · Ollama** — osobna instrukcja w [OLLAMA.md](OLLAMA.md).

## Wznawianie kolejki

Plik `.exports.json` jest zapisywany po zmianie stanu zadania. Jego lokalizacja jest pokazana w oknie kolejki. Po ponownym uruchomieniu wybierz **Wczytaj kolejkę**, wskaż ten plik i kliknij Start. Zadanie przerwane w trakcie renderowania wraca do kolejki i jest wykonywane od początku; ukończone są pomijane. „Ponów błędne” ponawia zadania błędne/anulowane. Jednej kolejki nie mogą równocześnie używać dwie instancje aplikacji. Plik zawiera lokalne migawki projektów, dlatego traktuj go jak własny projekt z tekstem.

## Odtwarzalne środowisko i testy

Zależności produkcyjne są zamknięte w `requirements-lock.txt` z hashami. Bootstrap Online instaluje je z `--require-hashes`. Definicja CI Windows sprawdza testy, wybrane błędy Ruff i zależności. Od publikacji 0.6.1 workflow działa także w [GitHub Actions](https://github.com/zetmar-collab/subtitle-studio/actions/workflows/check.yml).

Budowanie może użyć izolowanego Pythona: `powershell -File scripts/build.ps1 -Python .venv/Scripts/python.exe`. Bieżące wyniki testów i zakres sprawdzenia opisuje [TESTY.md](TESTY.md).
