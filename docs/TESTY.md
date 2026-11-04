# Weryfikacja

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
