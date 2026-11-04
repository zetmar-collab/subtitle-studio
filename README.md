# Subtitle Studio — lokalny edytor napisów i logo

Działająca aplikacja Windows w Pythonie i PySide6, z eksportem FFmpeg. Wdrożono MVP oraz część funkcji etapów 2–3 ze specyfikacji. To nie jest deklaracja realizacji całej specyfikacji; szczegółowy zakres znajduje się w [docs/STATUS.md](docs/STATUS.md).

## Uruchomienie

Publiczne wydanie zawiera kod źródłowy i instrukcję budowania instalatora Windows. Do pracy z filmem zainstaluj FFmpeg i udostępnij ffmpeg oraz ffprobe w PATH.

Instalator Online dla Windows x64 wymaga Pythona 3.12. Przy pierwszym uruchomieniu pobiera zależności z PyPI do środowiska użytkownika. Kolejne uruchomienia korzystają z zapisanych pakietów. [Wydanie 0.2.1](https://github.com/zetmar-collab/subtitle-studio/releases/tag/v0.2.1)

Kod źródłowy (Python 3.12, Windows x64):

```powershell
python -m pip install -r requirements.txt
python main.py
```

Przykładowy projekt: `examples/Demo.subtitlelogo.json`. Przycisk „Otwórz projekt” pozwala go wczytać. Film to syntetyczna plansza testowa z tonem, nie mowa — ręczne czasy słów służą wyłącznie demonstracji.

## Sprawdzenie i budowa

```powershell
python -m pip install pytest pyinstaller
python -m pytest -q
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
powershell -ExecutionPolicy Bypass -File scripts/build_setup.ps1 -Compiler 'C:\path\to\Inno Setup\ISCC.exe'
```

Setup buduje Inno Setup (sprawdzono 6.7.4). Definicja: `installer/SubtitleStudio.iss`. `python scripts/check_setup.py` instaluje go do osobnego folderu w `build`, sprawdza uruchomienie i eksport, po czym odinstalowuje, kontrolując zachowanie projektu użytkownika. Test odmawia działania, jeżeli wykryje już zainstalowaną kopię tego produktu. Sprawdź licencję używanej wersji kompilatora przed jego użyciem komercyjnym.

Presety i tłumaczenia aplikacji są w repozytorium. Paleta kolorów korzysta z tłumaczenia z instalacji Qt. `python scripts/create_assets.py` regeneruje wbudowany katalog z definicji. `python scripts/create_demo.py` odtwarza materiały demonstracyjne. `python scripts/fetch_dictionaries.py` pobiera opcjonalnie aktualne słowniki z repozytorium LibreOffice i zapisuje dokładny commit źródłowy. Do działania aplikacji sieć nie jest potrzebna.

- [Instrukcja użytkownika](docs/INSTRUKCJA.md)
- [Architektura i decyzje](docs/ARCHITEKTURA.md)
- [Zakres oraz ograniczenia](docs/STATUS.md)
- [Raport testów](docs/TESTY.md)
- [Analiza: co poprawić i co dodać](docs/ANALIZA.md)
- [Biblioteki i licencje](THIRD_PARTY.md)

Wersja 0.2.0 dodaje wizualne palety kolorów i własną ikonę. Źródło ikony: `assets/icon.svg`; `python scripts/create_icon.py` odtwarza PNG i wielorozmiarowy ICO (wymaga Pillow jako narzędzia developerskiego).

![Interfejs aplikacji](docs/colors-ui.png)
