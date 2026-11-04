# Decyzje techniczne

PySide6/Qt Widgets zapewnia lokalny interfejs, czcionki systemowe, dekodowanie podglądu i natywne operacje plikowe. FFmpeg/ffprobe jest osobnym procesem, wywoływanym listą argumentów bez shell. Qt QPainter jest wspólnym silnikiem kompozycji w podglądzie i eksporcie. Wybrano to zamiast drugiego silnika libass, by implementacje animacji nie rozchodziły się pomiędzy trybami. Koszt: kopiowanie klatek i renderowanie tekstu CPU ograniczają wydajność, zwłaszcza w 4K.

```text
ui/window + preview + jobs
  → core/projects        JSON v1, ścieżki względne, atomowy zapis
  → core/subtitles       pysubs2, SBV/TXT, przesunięcie i skalowanie, QC
  → core/spellcheck      spylls + lokalne słowniki Hunspell
  → core/media           ffprobe + Qt Multimedia + fala FFmpeg
  → core/compositor      czysty czas mediów → QPainter → klatka
  → osobny proces export
      FFmpeg decode/fps/scale/pad → RGB → compositor → FFmpeg encode + audio
      → ffprobe: rozmiar, czas, liczba audio → atomowe zastąpienie celu
```

## Model i kontrakty

Nie ma serwera, kont ani bazy danych. Dataclasses są kontraktem między domeną i UI. `Project` zawiera wersję, wideo, ścieżki, grafiki, język, motyw i progi QC. `Segment` przechowuje całkowite ms: początek, koniec, tekst, język, flagę nadania czasów i opcjonalne słowa z absolutnymi czasami filmu. `Track` zawiera styl, widoczność i oryginalną ścieżkę importu. `Logo` ma własne czasy, położenie, szerokość i krycie. Przedziały aktywności są półotwarte `[start,end)`.

`read/write` obsługują treść i czasy napisów. `shift/stretch` zmieniają także czasy słów. `compose(frame, project, ms)` nie zależy od zegara UI. `render(project, target, options, progress, cancelled)` wykonuje eksport i weryfikację. Plik zadania jest osobną migawką projektu; UI odbiera postęp przez mały JSON i zgłasza anulowanie plikiem sygnału. Żaden projekt nie wykonuje kodu.

Podgląd korzysta ze znaczników PTS klatek QVideoSink, eksport z czasu `indeks/FPS` po resamplingu FFmpeg. To zachowuje deterministyczność animacji przy przewijaniu i wyjściowym FPS. Dekodery Qt/FFmpeg mogą dać różnice koloru i doboru klatki przy VFR, a kompresja i podpróbkowanie chroma zmieniają piksele. Zgodność warstw testowana jest przy tym samym rozmiarze i czasie, z tolerancją kodeka. Nie obiecujemy bitowej identyczności skompresowanego obrazu.

Qt offscreen na Windows może mieć pustą bazę fontów. `core/fonts.initialize_fonts()` rejestruje w takim przypadku fonty systemowe i fonty użytkownika. Dzięki temu proces renderowania używa tych samych dostępnych rodzin, co podgląd. Przy przenoszeniu projektu na inny komputer należy zainstalować użyte czcionki; projekt ich nie osadza.

## Bezpieczeństwo i wydajność

Brak transmisji mediów i treści. Import napisów ograniczony do 20 MB, projektu do 40 MB, liczby segmentów do 100000 i grafik do 64. Eksport nie nadpisuje źródłowego wideo, grafik ani znanych źródeł napisów. Ograniczenia rozdzielczości eksportu: 7680×7680, 120 FPS. Wykrywanie mediów ma timeout. Wątki pomocnicze obsługują analizę filmu, falę audio i ładowanie słowników. Eksport ma niezależny proces i zwalnia oba procesy FFmpeg po błędzie/anulowaniu.

Brak sandboxu dekoderów i pełnego fuzzingu. Otwieraj pliki z zaufanych źródeł, aktualizuj biblioteki. Dostępność 4K nie oznacza renderowania w czasie rzeczywistym. Fala audio ma limit dziesięciu godzin i jest redukowana do ok. 1400 pików. Podgląd nie generuje proxy. Historia projektu ograniczona do 60 migawek; duże projekty zwiększają użycie pamięci. Renderowanie CPU jest świadomym fallbackiem, bez deklarowanej obsługi GPU.

## Dokumentacja źródłowa

- https://ffmpeg.org/ffmpeg.html — jawne mapowanie `-map`, wejścia i wyjścia.
- https://ffmpeg.org/ffmpeg-filters.html — scale, pad i fps.
- https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QVideoSink.html — klatki podglądu.
- https://pysubs2.readthedocs.io/en/latest/supported-formats.html — formaty i ograniczenia.
- https://pyinstaller.org/en/stable/usage.html — przenośna paczka onedir.
