## Weryfikacja 0.6.1

Próba przed publikacją: 200 testów zaliczonych, 1 opcjonalny test słownika pominięty (102,23 s na bieżącym Windows). Podczas kontroli w GitHub Actions wykryto wyścig przy sprzątaniu anulowanego eksportu na Windows. Dodano oczekiwanie na procesy, zamykanie potoków i krótkie ponowienie blokady pliku tymczasowego oraz dwie regresje. Pełny zestaw po tej poprawce obejmuje 203 przypadki, w tym jeden opcjonalny test słownika.

Nowe regresje: przycisk filmu uruchamia ASR po analizie, filtr plików obejmuje wideo, podgląd odświeża czas przy przewijaniu, okno Ollamy wysyła cały zakres przez rzeczywisty osobny proces do lokalnego serwera testowego i po ponownym otwarciu wybiera bieżącą kartę. Sprawdzono stałość pozycji liter/słów/tła, czasy ASR, pauzy, nieaktualne wyrównanie, emoji i zawijanie długich słów. Eksport i zgodność pikseli obejmują wszystkie 9 efektów.

W rzeczywistej próbie GUI: MP4 z polską mową → Whisper tiny (5 segmentów, 32 słowa) → przekazanie napisów. Osobna próba GUI Ollamy z lokalnym Gemma4:e2b przesłała dwa syntetyczne napisy i zastosowała obie poprawki z zachowaniem czasów. Tryb dokładniejszej analizy wykrył na tej próbce więcej błędów niż wyłączony reasoning; nie jest to benchmark jakości.

Gotowy EXE 0.6.1 powtórzył tę samą próbę MP4 → ASR i okno Ollamy → lokalny model → zastosowanie dwóch poprawek. Raport: `regression-0.6.1-frozen.json`. Dodatkowa kontrola paczki sprawdziła podgląd, ikonę, eksport, kolejkę, tworzenie i łączenie filmów oraz pokaz zdjęć. Testowano na bieżącym Windows, bez czystej maszyny wirtualnej.

## Weryfikacja 0.6.0

188 testów zaliczonych, 1 opcjonalny test słownika PL pominięty. Ruff E9/F63/F7/F82: bez błędów. Testy wykonano w izolowanym środowisku z zależnościami z lockfile i hashami.

Sprawdzono rzeczywiste procesy FFmpeg: tworzenie i łączenie filmów, pokaz zdjęć z audio, kolejność obrazów, ruch zdjęcia w zdekodowanych klatkach, kolejkę dwóch proporcji i anulowanie z zachowaniem poprzedniego wyniku. Kontrolowane testy obejmują blokujący odczyt renderera oraz nieudany start procesu.

AI: testy lokalnego serwera HTTP sprawdzają JSON, partie, błędne identyfikatory, wykluczenie modeli chmurowych i adresów zdalnych, przekierowania oraz zachowanie tekstu/czasów/undo. Wykonano także rzeczywistą korektę i próbę GUI z lokalnym Gemma4:e2b na syntetycznym zdaniu. To nie jest benchmark jakości korekty ani naturalnej mowy.

Audyt pip-audit: 34 zależności produkcyjne, 0 znanych podatności, 0 pominiętych. Wynik dotyczy stanu bazy w chwili tego sprawdzenia. CI jest zdefiniowane lokalnie; nie uruchamiano go w GitHub.

Pomiar lokalny: kontrola jakości 6000 segmentów po zmianie: 4.38 ms (w audycie 0.5.0: 1994,8 ms). Pomiar nie obejmuje tworzenia elementów GUI. Tabela nadal korzysta z QTableWidget; bardzo duże projekty wymagają dalszych pomiarów.

## Integracja 0.5.0

138 testów zaliczonych, 1 pominięty (opcjonalny zewnętrzny słownik PL). Przeniesiono testy modelu, audio, pisowni i GUI Szept. Adapter sprawdza jednostki czasu, nieaktualne czasy słów, walidację, cofanie, skróty klawiaturowe i anulowanie zamknięcia.

Sprawdzono rzeczywiste ASR z lokalnym tiny na syntetycznych próbkach PL i EN oraz ciszy; w procesie testowym zablokowano połączenia sieciowe. Test EXE sprawdza obie karty, Hunspell w osobnym procesie, przekazywanie w obie strony i zapis projektu. Nie jest to benchmark jakości naturalnej mowy ani test CUDA.

# Weryfikacja

Wersja 0.4.0 przeszła 80 testów (`python -m pytest -q`, 29,28 s). Nowe testy renderują zdjęcie z audio w sześciu rozmiarach, sprawdzają pasy i centralne kadrowanie, długość wyniku, powtarzanie/zatrzymanie/skrócenie klipu, częstotliwość wybranego dźwięku, anulowanie i ochronę oryginałów. Test GUI uruchamia rzeczywisty proces kreatora i sprawdza podgląd. Kontrola paczki dodatkowo tworzy pionowy MP4 przez gotowy EXE.

Wersja 0.3.0 przeszła 67 testów (`python -m pytest -q`, 18,32 s na bieżącym komputerze). Testy rozszerzeń obejmują rzeczywiste łączenie H.264/AAC, kolejność klipów, różne proporcje, ciszę przy braku audio, anulowanie, pracę dialogu w osobnym procesie, zoom/przyciąganie/undo oraz eksport zakresu z napisami i audio. [Opis funkcji](CONCAT.md)

Wynik 2026-10-31: **39 testów zakończonych powodzeniem**, `python -m pytest -q`, czas 10,26 s na bieżącym komputerze (Windows 11 x64, Python 3.12.10, PySide6 6.12.0). Testy uruchamiają rzeczywisty FFmpeg, nie zastępują go mockiem. Qt uruchamiane jest w trybie offscreen, z jawnym załadowaniem czcionek systemowych.

Testy jednostkowe obejmują roundtrip Unicode SRT/VTT/ASS, stare kodowanie cp1250, TXT bez czasów, synchronizację z czasami słów, QC, względne ścieżki projektu i odrzucanie nieznanego schematu. Testy GUI sprawdzają edycję treści, undo/redo, PL/EN, motyw i właściwości stylu.

Testy renderera sprawdzają deterministyczne przewijanie dla dziewięciu efektów oraz zmianę podświetlanego słowa. Integracja generuje film z audio, renderuje go z polskimi napisami i PNG z alfa/kryciem 50%, porównuje klatki wynikowe ze wspólnym rendererem dla pięciu efektów i kontroluje obecność audio. Średni dopuszczalny błąd pikseli to 3/255 z uwagi na H.264 i YUV420. Dodatkowo sprawdzane są anulowanie z zachowaniem istniejącego celu, usuwanie plików tymczasowych, pionowa rozdzielczość i uszkodzony nagłówek wideo.

Dalsze testy obejmują import SBV/MicroDVD/MPL2/TTML/SAMI, kodery H.265/VP9 i kontener MKV, źródło VFR 1080p z dwiema ścieżkami audio oraz przesunięciem napisów +500 ms. Test GUI uruchamia rzeczywisty proces `main.py --render` i odbiera jego zakończenie. Test kolejki pracy weryfikuje dostarczenie wyniku z tła do GUI — chroni przed utratą sygnału po zwolnieniu QRunnable.

Uruchomiono także podgląd Qt Multimedia rzeczywistego projektu demonstracyjnego: klatka została odkodowana, obecna była jedna ścieżka tekstowa, jedno logo i 800 punktów obwiedni audio, bez błędu odtwarzacza. Zrzut `docs/screenshot.png` pokazuje tekst, logo, falę audio i polski interfejs. Kontrola obrazu wykryła brak fontów w domyślnej bazie offscreen; poprawka `core/fonts.py` ładuje czcionki Windows w rendererze i testach.

Ograniczenia: testy na bieżącym Windows, bez czystej VM. Obecność ścieżki audio nie dowodzi słuchowej poprawności każdego możliwego kodeka. Syntetyczny ton nie testuje zgodności napisów z prawdziwą wypowiedzią. Brak testów wydajności wielogodzinnych projektów i wszystkich kodeków/kontenerów. Paczka jest lokalnym buildem bez podpisu.

## Test paczki Windows — 2026-11-03

Ponowny pełny przebieg testów źródłowych: **39 passed in 11.11s**. `python scripts/check_dictionaries.py` potwierdził poprawne i niepoprawne słowa we wszystkich siedmiu słownikach: pl, en, de, fr, es, it, uk. Każdy słownik był sprawdzany w osobnym procesie.

`python scripts/check_package.py` zakończył się powodzeniem. Uruchomiono gotowy `SubtitleStudio.exe` z PATH bez ścieżek developerskiego Pythona. Potwierdzono odkodowaną klatkę, jedną ścieżkę napisów, jedno logo, 800 punktów obwiedni i brak błędu odtwarzacza. Następnie ten sam EXE uruchomiono jako proces eksportu: wynik 640×360, 2000 ms, jedna ścieżka audio. Dane maszynowe: `docs/package-smoke.json`; zrzut EXE: `docs/packaged.png`; film wynikowy: `examples/Przykładowy eksport.mp4`.

Test wykrył niezgodną bibliotekę `icuuc.dll` pobraną przez analizę zależności PyInstaller z otoczenia budowania. Qt potrzebuje systemowego API ICU, a ta biblioteka miała inne nazwy symboli. Skrypt `fix_runtime.py` usuwa ją z paczki, pozwalając użyć systemowego ICU Windows, oraz ujednolica MSVC runtime. Skrypt budowania wymaga teraz pomyślnego testu EXE przed utworzeniem ZIP. Nie zastępuje to testu na czystej VM Windows 10/11.

Porównanie klatki rzeczywiście wyeksportowanej przez EXE z kompozycją podglądu w 750 ms dało średni błąd **2,0312/255** przy progu 5/255. Materiał zawiera polski tekst, aktywne słowo i przezroczyste logo. Tym samym test paczki sprawdza obecność wypalonych warstw, nie tylko strumienie i rozdzielczość.

## Instalator — 2026-11-03

`python scripts/check_setup.py`: instalacja do osobnego folderu w workspace zakończona powodzeniem; zainstalowany EXE zgodny bajtowo z wersją przenośną. Zainstalowana aplikacja przeszła test podglądu i eksportu z weryfikacją obrazu. Deinstalacja usunęła EXE i wpis produktu w rejestrze, zachowując utworzony w folderze aplikacji projekt użytkownika. Szczegółowy raport z hashem testowanego setupu: `docs/setup-test.json`. Test pomija tworzenie skrótów i nie zastępuje testu w czystej VM.

## Wersja 0.2.0 — wizualne kolory i ikona

Nowe testy `tests/test_colors.py`: podgląd/akceptacja koloru jako jeden krok undo/redo, anulowanie alfa i pomijanie autosave w czasie podglądu, roundtrip obrysu/tła/aktywnego słowa, wizualna próbka alfa, kolor wnętrza liter mimo obrysu, polska paleta i obecność rozmiarów ikony. Kontrola paczki dodatkowo porównuje osadzony zasób ikony 256 px z plikiem ICO, sprawdza ikonę okna i cztery przyciski kolorów w gotowym EXE.

Pełny przebieg po zmianach: **48 testów zaliczonych**, `python -m pytest -q` (12,28 s na bieżącym komputerze). Zrzuty `docs/colors-ui.png` i `docs/color-picker.png` pokazują nowy panel i polską paletę.
