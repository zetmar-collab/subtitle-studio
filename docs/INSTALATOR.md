# Instalator Windows

Wynik: `dist/SubtitleStudio-Setup-0.7.1-x64.exe`. Zachowano identyfikator produktu z wersji 0.1.0, aby instalator rozpoznawał aktualizację istniejącej instalacji.

Wariant Online powstaje przez `python scripts/build_online_setup.py`. Skrypt zbiera bieżące pliki widoczne dla Git i kompiluje `SubtitleStudio-Setup-0.7.1-Online-x64.exe`. Wymaga lokalnego kompilatora Inno Setup albo argumentu `--compiler`. Pierwsze uruchomienie korzysta z Pythona 3.12 i pobiera pakiety z PyPI. Narzędzia FFmpeg i ffprobe są odczytywane z PATH.

- Instalacja dla bieżącego użytkownika, bez podnoszenia uprawnień.
- Domyślny katalog: `%LOCALAPPDATA%/Programs/SubtitleStudio`.
- Polski i angielski język kreatora; wybór języka aplikacji nadal jest dostępny w jej oknie.
- Skrót w menu Start i opcjonalny skrót na pulpicie.
- Deinstalator zarejestrowany w ustawieniach aplikacji Windows.
- Brak automatycznego uruchamiania programu po cichej instalacji.
- Zachowanie projektów i danych użytkownika podczas odinstalowania.
- Python i biblioteki Qt są w paczce. Zewnętrzne `ffmpeg.exe`/`ffprobe.exe` muszą być dostępne w PATH lub folderze programu; instalator ich nie pobiera.

Definicję instalatora stanowi `installer/SubtitleStudio.iss`; skrypt budowania to `scripts/build_setup.ps1`. Użyty kompilator: Inno Setup 6.7.4, pobrany z oficjalnego wydania `jrsoftware/issrc`, z poprawnym podpisem Pyrsys B.V. Przestrzegaj licencji kompilatora, zwłaszcza przy zastosowaniach komercyjnych. Wynikowy instalator aplikacji nie jest podpisany cyfrowo.

Budowa po utworzeniu folderu `dist/SubtitleStudio`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_setup.ps1 -Compiler 'C:\path\to\ISCC.exe'
```

Test: `python scripts/check_setup.py`. Tworzy unikalny katalog w `build/installer-smoke`, instaluje tam gotowy setup z pominięciem ikon, sprawdza identyczność EXE i wykonuje rzeczywisty test podglądu/eksportu. Następnie tworzy przykładowy projekt użytkownika w folderze aplikacji i sprawdza, że deinstalator zachowuje go, usuwa program i wyrejestrowuje produkt. Logi instalatora i deinstalatora pozostają w folderze testowym. Raport: `docs/setup-test.json`.

Test działa na aktualnym Windows; nie stanowi potwierdzenia działania na czystej maszynie Windows 10/11. Nie zmienia istniejącej zainstalowanej kopii produktu: w razie znalezienia jej wpisu test przerywa się przed instalacją.
