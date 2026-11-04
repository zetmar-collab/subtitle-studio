# Analiza Subtitle Studio — 2026-11-03

Przegląd obejmuje kod aplikacji i instalatora, uruchomiony interfejs, testy GUI i rzeczywisty pipeline FFmpeg. Wnioski dotyczą obecnej wersji lokalnej; nie są certyfikacją wszystkich kodeków, Windows 10 ani wielogodzinnych materiałów.

## Ocena

Podstawa jest sensowna: lokalne media, wersjonowane projekty, zachowanie oryginałów, osobny proces eksportu, jawne mapowanie audio i jeden renderer warstw dla podglądu i eksportu. Nie rekomenduję przepisywania aplikacji na inny framework. Największą wartość teraz dają usprawnienia edycji, czytelności i skalowania do większej liczby segmentów.

## Wprowadzone w 0.2.0

- Cztery wizualne przyciski kolorów: napisy, obrys, tło i aktywne słowo. Próbka pokazuje rzeczywisty kolor, a szachownica przezroczystość.
- Pełna paleta Qt, wybór z ekranu, barwa/nasycenie, RGB/HTML i kanał alfa. Okno palety ma polskie etykiety w polskiej wersji interfejsu.
- Zmiana koloru od razu aktualizuje podgląd. Odtwarzanie jest wstrzymywane na czas wyboru. OK tworzy jeden krok Cofnij; Anuluj przywraca poprzedni kolor. Niezatwierdzony kolor nie trafia do autosave.
- Obrys jest rysowany przed wypełnieniem liter. Wcześniej mógł zakrywać wybrany kolor przy mniejszym tekście; teraz wnętrze litery zachowuje kolor.
- Własna ikona: okno i nagłówek, EXE, ikona skrótów oraz instalator. Plik ICO zawiera rozmiary od 16 do 256 px; źródło jest edytowalnym SVG.
- Zmiana właściwości od razu oznacza projekt jako niezapisany w tytule okna.

## Co poprawić w pierwszej kolejności

| Priorytet | Obserwacja w kodzie / interfejsie | Zalecana poprawka |
|---|---|---|
| Wysoki | `refresh()` w `ui/window.py` odtwarza wszystkie komórki po pojedynczej edycji. Zaznaczenie odnosi się do numeru wiersza, więc po dodaniu i sortowaniu może wskazywać inny segment. | Wprowadzić stabilne identyfikatory segmentów i zachować zaznaczenie/scroll; zastąpić tabelę modelem QAbstractTableModel aktualizującym zmienione wiersze. |
| Wysoki | `core/subtitles/service.py::warnings()` sprawdza nakładanie każdego segmentu z każdym. QC jest wykonywane przy odświeżeniu GUI. | Sprawdzać przedziały po sortowaniu i aktualizować QC dla zmienionego fragmentu; kosztowne obliczenia przenieść poza wątek GUI. |
| Wysoki | `compose()` przechodzi przez wszystkie segmenty dla każdej klatki, nawet jeśli aktywny jest jeden. | Dodać indeks przedziałów czasowych, uwzględniający także nakładające się segmenty, i cache układu tekstu. |
| Wysoki | `open_video()` ma analizę w tle, ale nie odrzuca wyników starszego żądania importu. Dwa szybko wybrane pliki mogą zakończyć analizę w odwrotnej kolejności. | Nadać importom identyfikatory żądań i akceptować tylko wynik ostatniego. |
| Wysoki | Import napisów i `probe()` podczas otwierania projektu są wykonywane synchronicznie. Limit pliku napisów sprawdzany jest dopiero po `read_bytes()`. | Sprawdzić rozmiar przed odczytem, dodać limitowany odczyt i przenieść parsowanie/analizę projektu do zadania w tle. |
| Średni | Lista presetów może pokazywać „Klasyczne”, mimo że projekt demonstracyjny ma własny zmodyfikowany styl highlight. | Oznaczać „Własny styl” lub rozpoznawać zgodność wszystkich właściwości z presetem. |
| Średni | Panel właściwości jest długi; część kontrolek napisów pozostaje widoczna po wybraniu logo. | Oddzielne sekcje kontekstowe „Napisy”, „Animacja”, „Logo”, z możliwością zwijania. |
| Średni | Ostrzeżenia QC dotyczą tylko jednej ścieżki i nie obejmują wyjścia warstw poza kadr. | Dodać bezpieczne marginesy, obrys pola tekstu i kontrolę kolizji pomiędzy widocznymi ścieżkami. |
| Średni | „Pisownia” prowadzi przez wiele kolejnych okien sugestii. | Podkreślenia w edytorze, panel błędów i sugestie w menu kontekstowym; słowniki pozostawić lokalne. |
| Średni | Animacja maszyny do pisania wylicza układ na podstawie aktualnie widocznego fragmentu. | Obliczać układ dla pełnej linijki, a ujawniać kolejne glify bez przeskoków łamania wierszy. |
| Średni | Błędy eksportu są ogólne, a odczyt/zapis potoków FFmpeg jest blokujący. | Dodać kontrolowane timeouty i diagnostykę błędów kodera; sprawdzić reakcję anulowania na zatrzymanym dekoderze/pełnym dysku. |
| Średni | Dane JSON walidują część liczb, ale nie wszystkie typy, kolory, progi QC i czasy słów. | Centralna walidacja schematu projektu i presetów, z czytelnym opisem błędnego pola. |

Pomiar obecnego QC na bieżącym komputerze dla niepokrywających się segmentów: 1000 segmentów — 0,0488 s; 5000 — 1,233 s. To pojedynczy pomiar funkcji, nie pełny benchmark. Wzrost jest zgodny z kosztem kwadratowym widocznym w kodzie i uzasadnia priorytet optymalizacji GUI.

Próba GUI potwierdziła zmianę tożsamości zaznaczenia: zaznaczono drugi segment „Drugi”, edycja tekstu zachowała jego zaznaczenie, ale dodanie segmentu w czasie 0 i sortowanie pozostawiło zaznaczony wiersz 1 z tekstem „Pierwszy”. Osobno potwierdzono etykietę presetu „Klasyczne” przy faktycznym efekcie `highlight`.

## Co dodać

1. **Wygodniejsza synchronizacja:** zoom osi czasu, przeciąganie początku/końca segmentu, przyciąganie do kursora i sąsiednich segmentów, odtwarzanie zaznaczonego fragmentu w pętli.
2. **Dokładna nawigacja:** przechodzenie między segmentami i rzeczywistymi klatkami według PTS; obecne strzałki korzystają z nominalnego FPS, co jest przybliżeniem dla VFR.
3. **Przygotowanie do eksportu:** ekran sprawdzający dostępność FFmpeg, koderów i audio, podsumowanie profilu oraz wskazanie źródłowych błędów przed startem.
4. **Napisy osadzone w filmie:** lista dostępnych tekstowych strumieni i import wybranego języka, z osobną informacją dla napisów obrazowych wymagających OCR.
5. **Styl pojedynczego segmentu:** wyjątki od stylu ścieżki, szerokość pola, marginesy, wyrównanie, interlinia i subtelny cień.
6. **Lokalna transkrypcja i wyrównanie słów:** opcjonalny moduł, z pobieraniem modeli na życzenie i jawnym poziomem pewności. Ręczne czasy słów nadal powinny być dostępne.
7. **Eksport produkcyjny:** wybór ścieżek audio, tryb kadrowania do pionu, kolejka zadań, zapis profili i wznowienie po błędzie. GPU dopiero po testach konkretnego kodera.
8. **Organizacja pracy:** ostatnie projekty, „Zapisz jako”, identyfikatory segmentów, historia operacji z opisami oraz zapamiętywanie układu okna.

Najbliższy sensowny etap: zachowanie zaznaczenia + szybsze QC, następnie lepsza oś czasu i kontrola czytelności. Automatyczne rozpoznawanie mowy warto dodawać po ustabilizowaniu tych podstaw.

## Weryfikacja zmian

Testy obejmują podgląd i zatwierdzenie koloru, anulowanie z przywróceniem alfa, pojedynczy krok undo/redo, blokadę autosave podczas podglądu, zapis/odczyt kolorów obrysu/tła/aktywnego słowa, polskie etykiety palety, zachowanie koloru wnętrza liter i wielorozmiarowy plik ikony. Sprawdzenie EXE i instalatora wykonują skrypty `check_package.py` i `check_setup.py`; wyniki są zapisywane w `docs`.

Dokumentacja wykorzystanych mechanizmów Qt: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QColorDialog.html oraz https://doc.qt.io/qtforpython-6/PySide6/QtGui/QIcon.html.
