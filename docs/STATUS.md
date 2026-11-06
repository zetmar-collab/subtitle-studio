## Aktualizacja 0.6.0

Zrealizowane poprawki i nowe funkcje opisuje [NOWOSCI_0.6.md](NOWOSCI_0.6.md), a lokalną korektę AI [OLLAMA.md](OLLAMA.md). Poniższe opisy wcześniejszych wersji pozostawiono jako historię zmian.

## Aktualizacja 0.5.0

Dodano ASR przez integrację Szept: lokalny Whisper, edycja tekstu, słowniki i przekazywanie napisów z czasami słów. Dalsze opisy ograniczeń ASR z wcześniejszych wersji mają charakter historyczny. Szczegóły: INTEGRACJA_SZEPT.md.

# Rzeczywisty zakres implementacji

Wersja 0.4.0 dodaje kreator filmu ze zdjęcia/wideo oraz osobnego audio. Gotowy wynik ma MP4 H.264/AAC, wybrane proporcje i rozmiar, z dopasowaniem lub centralnym kadrowaniem.

## Gotowe

- Lokalny interfejs PySide6, edycja segmentów, kilka ścieżek, czasy ms, ręczne czasy słów.
- Dodawanie, usuwanie, dzielenie i łączenie, szukanie/zamiana, przesuwanie oraz korekta dwoma punktami.
- QC z konfigurowalnymi progami, fala audio, przewijanie po osi, głośność i pełny ekran.
- Wspólny renderer QPainter: static, fade, lewo, prawo, góra, maszyna, słowo po słowie, ręczne highlight i pop.
- Zoom i przewijanie osi, przesuwanie napisów i ich granic myszką, przyciąganie, duplikowanie, domykanie czasu napisów, zakres I–O i pętla.
- Łączenie 2–40 filmów do MP4 H.264/AAC, z dopasowaniem obrazu i ujednoliceniem FPS/audio.
- Osiem edytowalnych presetów, zapis i import własnego JSON, pozycja w siatce i przeciąganie warstw.
- Wizualne palety kolorów napisów, obrysu, tła i aktywnego słowa: alfa, podgląd na filmie, anulowanie i undo; własna ikona aplikacji/EXE/instalatora.
- Wiele grafik PNG/JPEG/WebP/BMP/GIF (pierwsza klatka), alfa, szerokość jako % filmu, krycie, przedziały widoczności, kolejność w grupie.
- Projekty JSON v1, relatywne ścieżki, ponowne wskazanie wideo i grafik, autosave i odzyskanie, cofanie/ponawianie.
- PL/EN, motywy dark/light/system. Nazwy techniczne efektów i część okien pomocniczych mają wspólne etykiety.
- Lokalna kontrola pisowni z indywidualnym zatwierdzaniem i własnym słownikiem; obsługa siedmiu języków po pobraniu słowników przez scripts/fetch_dictionaries.py, bez gramatyki i bez wykrywania języka.
- Eksport MP4 H.264/H.265, WebM VP9, MKV H.264, źródłowy rozmiar/1080p/4K/pion/kwadrat, fit z pasami, FPS/CRF, wszystkie źródłowe audio, test pierwszych 10 s.
- Osobny proces renderowania, procent/ETA, anulowanie, bezpieczny plik tymczasowy i kontrola wyniku przez ffprobe.
- Przenośny folder z EXE, instalator Windows dla bieżącego użytkownika, deinstalator i skrypty powtarzalnej budowy.

## Macierz napisów

| Format | Import | Eksport | Ograniczenia |
|---|---|---|---|
| SRT | Tak | Tak | Treść i czasy; brak zaawansowanych stylów |
| VTT | Tak | Tak | Ustawienia cue, regiony i oryginalne style nie są zachowywane |
| ASS/SSA | Tak | ASS | Treść i czasy; oryginalne style, tagi, karaoke i fonty osadzone nie są zachowywane |
| TTML/DFXP | Tak, parser pysubs2 | Nie | Ograniczony podzbiór parsera, bez zachowania układu i stylów; bez gwarancji wszystkich profili TTML |
| SAMI/SMI | Tak, parser pysubs2 | Nie | Bez zachowania CSS i wielojęzycznych klas SAMI |
| MicroDVD SUB | Tak | Nie | Liczba klatek przeliczana przez FPS bieżącego filmu; przed importem otwórz film |
| MPL2 | Tak | Nie | Rozpoznawanie po treści; normalizacja stylów |
| SBV | Tak | Nie | Standardowe bloki czasowe `h:mm:ss.sss,h:mm:ss.sss` |
| TXT | Tak | Nie bez czasów | Każdy niepusty wiersz staje się segmentem bez nadanych czasów |
| PGS / VobSub | Nie | Nie | Obrazowe napisy wymagają OCR |

Podgląd i eksport korzystają ze stylu aplikacji, nie stylów pliku wejściowego. Eksport ASS zapisuje zwykły styl biblioteki; własne animacje pozostają w JSON i wypalanym filmie.

## Częściowe lub niewdrożone wymagania

- Pełny zestaw testów akceptacyjnych specyfikacji **nie jest zamknięty**: brak testu w czystej maszynie Windows bez narzędzi programistycznych i bez zainstalowanego FFmpeg; brak podpisu cyfrowego.
- Brak ASR, forced alignment, automatycznej synchronizacji do mowy, OCR i automatycznego wykrywania języka.
- Brak ekstrakcji napisów osadzonych w kontenerze, spektrogramu i markerów pauz.
- Pisownia pokazuje kolejne okna sugestii; nie ma podkreśleń w edytorze i menu kontekstowego ani gramatyki. Słowniki są ładowane na żądanie i zużywają dodatkową pamięć.
- Styl wspólny dla ścieżki; brak wyjątków stylu pojedynczego segmentu/słowa, regulacji cienia, interlinii, odstępów, dowolnego wyrównania i pełnego zarządzania marginesami. Brak ostrzeżenia o wyjściu tekstu lub logo poza kadr.
- Presety mają nazwy i bieżący podgląd, bez siatki animowanych miniatur.
- Logo: brak SVG, obrotu, blokowania warstw i dowolnego przeplatania tekstu z grafikami. Suwak szerokości 1–100% kadru, brak trybu procentu oryginalnych pikseli.
- W eksporcie brak kadrowania do wypełnienia, bitrate, wyboru audio, AV1 i GPU. Kodery muszą być dostępne w zewnętrznym FFmpeg. Brak automatycznej instalacji FFmpeg.
- Nominalny FPS służy przybliżonemu przewijaniu klatkowym, VFR jest konwertowany do CFR; to nie jest edytor bezstratnej osi PTS. Na niektórych plikach obrót lub nietypowe proporcje pikseli mogą wymagać dalszych testów.
- Metadane/HDR/rozdziały/oryginalne ścieżki napisów nie są przenoszone; wynik jest standardowym obrazem RGB→YUV420, bez zarządzania HDR. Brak logu FFmpeg udostępnionego w UI, zaawansowanego recovery zadań i proxy.

Te punkty są jawną listą dalszych prac, a nie ukrytymi przełącznikami lub deklaracją dostępności.
