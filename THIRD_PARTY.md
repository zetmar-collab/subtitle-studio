# Zależności i redystrybucja

Połączona aplikacja: GPL-3.0-or-later, zobacz LICENSE. Pierwotny kod Subtitle Studio: MIT (docs/SUBTITLE_STUDIO_MIT.txt). Moduł srtstudio pochodzi z Szept (GPL-3.0-or-later), zobacz docs/INTEGRACJA_SZEPT.md. Licencja aplikacji nie obejmuje bibliotek i słowników osób trzecich.

Ikona `assets/icon.svg` i jej pochodne PNG/ICO są własnymi zasobami tego projektu na licencji MIT. `assets/i18n/qtbase_pl.qm` pochodzi z tłumaczeń Qt dostarczonych z PySide6; obowiązują warunki Qt, wymienione poniżej i w dołączonych tekstach licencji.

| Składnik | Wersja użyta | Licencja / uwagi |
|---|---|---|
| Python | 3.12.10 | PSF, biblioteka standardowa i runtime w paczce PyInstaller |
| PySide6 / Qt | 6.12.0 | PySide6 LGPL-3.0 / GPL-2.0 / GPL-3.0; używane moduły Qt na warunkach LGPL. Oddzielne biblioteki w `_internal`, bez statycznego linkowania |
| shiboken6 | 6.12.0 | LGPL/GPL, zawiadomienia w paczce |
| pysubs2 | 1.9.1 | MIT |
| charset-normalizer | 3.4.9 | MIT |
| spylls | 0.1.7 | MIT |
| PyInstaller | 6.22.2, narzędzie budowy | GPL z wyjątkiem dla generowanych paczek |
| pytest | 9.1.1, tylko testy | MIT |
| FFmpeg/ffprobe CLI | zewnętrzna instalacja użytkownika | LGPL lub GPL zależnie od konfiguracji; **nie dołączono** tych EXE |
| Hunspell dictionaries | commit w `assets/dictionaries/sources.json` | Różne licencje upstream. Oryginalne README/COPYING/LICENSE w `assets/dictionaries/licenses` |

Qt Multimedia zawiera także własne dynamiczne biblioteki FFmpeg z dystrybucji Qt. Nie należy ich mylić z zewnętrznym ffmpeg.exe używanym przez eksporter. Licencje i informacje o elementach osób trzecich z wheel Qt kopiowane są przez skrypt `scripts/collect_licenses.py`. Paczka jest folderem onedir, aby umożliwić zastąpienie zgodnych bibliotek współdzielonych; cały kod i skrypt odbudowy aplikacji są udostępnione w tym repozytorium. Aplikacja nie zabrania reverse engineeringu potrzebnego do debugowania zmian w bibliotekach LGPL.

Źródła Qt/PySide6 i instrukcje odbudowy: https://download.qt.io/official_releases/QtForPython/pyside6/ oraz https://code.qt.io/cgit/pyside/pyside-setup.git/ i https://code.qt.io/cgit/qt/qtmultimedia.git/ (tag v6.12.0). Licencje źródłowe Qt: https://doc.qt.io/qt-6/licenses-used-in-qt.html. Paczki wydania zawierają zawiadomienia i teksty licencji w katalogu `licenses`. Kod aplikacji, lockfile oraz skrypty odbudowy są dostępne w repozytorium i w archiwum `SubtitleStudio-source.zip` przy tym samym wydaniu. Licencje i źródła bibliotek pozostają objęte warunkami ich autorów; szczegóły dostarczone z wheel są zachowane w paczce.

Zewnętrzny FFmpeg na komputerze budowy to kompilacja `N-124716-g054dffd133-win64-gpl`, z kodekiem libx264. Nie jest kopiowana do wyniku. Jeżeli dołączysz własny ffmpeg.exe/ffprobe.exe, zweryfikuj `ffmpeg -version`, `ffmpeg -buildconf` i licencje użytych kodeków oraz dołącz odpowiadające źródła i zawiadomienia. Zobacz https://ffmpeg.org/legal.html.

Słowniki pobrano z oficjalnego repozytorium https://github.com/LibreOffice/dictionaries. Zachowano oryginalne zawiadomienia bez ujednolicania ich licencji. Angielski używa en_US, niemiecki de_DE_frami, hiszpański es_ES. Szczegóły wszystkich baz zapisuje manifest. Słowniki są oddzielnymi plikami danych; można je zastąpić zgodną parą .dic/.aff.

## Moduł transkrypcji Szept

Szept (GPL-3.0-or-later) używa faster-whisper 1.2.1 (MIT), CTranslate2 4.8.4 (MIT), PyAV 19.0.2 (BSD), ONNX Runtime (MIT) i PyEnchant 3.3.0 (LGPL). Metadane i teksty licencji rzeczywiście zainstalowanych zależności zbiera scripts/collect_licenses.py. DLL Hunspell i GCC mają oddzielne zawiadomienia w assets/licenses/Szept-native. Modele nie są dołączone do instalatora.
