> Dokument historyczny modułu Szept. W Subtitle Studio 0.6.0 Ctrl+S zapisuje wspólną sesję obu kart; aktualne zasady opisuje [przewodnik 0.6](NOWOSCI_0.6.md). Nowe pliki JSON z metadanymi sprawdzenia wymagają aktualnej wersji programu.

# Szept — lokalna transkrypcja audio

<img src="assets/szept.png" width="72" height="72" alt="Ikona Szept — biała fala dźwiękowa na zielonym tle">

Aplikacja desktopowa Windows 10/11 x64: faster-whisper, PySide6, edytor tekstu i napisów, odtwarzacz oraz lokalna kontrola ortografii Hunspell. Interfejs polski i angielski, motywy jasny, ciemny i systemowy. Bez konta, płatnego API i telemetrii.

Repozytorium: [zetmar-collab/Szept](https://github.com/zetmar-collab/Szept). Kod źródłowy, testy i skrypty instalatora są publiczne na GPL-3.0-or-later. [Pobierz publiczny instalator sieciowy](https://github.com/zetmar-collab/Szept/releases/latest). Pełny pakiet zawierający zewnętrzne biblioteki pozostaje osobnym wydaniem roboczym; zobacz [status dystrybucji](docs/PUBLIC_RELEASE.md).

## Zalecana instalacja: setup sieciowy

Uruchom **Szept-Web-Setup-1.1.2-x64.exe** z sekcji [Releases](https://github.com/zetmar-collab/Szept/releases). Podczas instalacji pobiera około **462 MiB** z python.org, PyPI i oficjalnego FFmpeg-Builds. Potrzebuje internetu oraz około 4 GB wolnego miejsca. Sprawdza SHA-256 każdego pliku. Modele mowy pobiera się później w aplikacji.

Program instaluje się bez administratora, domyślnie w `%LOCALAPPDATA%\Programs\Szept Web`. Używa własnego Pythona i nie zmienia instalacji systemowej ani pełnej edycji Szept. Po instalacji i pobraniu potrzebnego modelu działa lokalnie, także bez internetu. Skróty tej edycji mają grupę **Szept Web**. [Szczegóły i instrukcja budowania](docs/WEB_SETUP.md).

## Pełny instalator Windows — wydanie robocze

Lokalny pełny pakiet ma nazwę `dist/setup/Szept-Setup-<wersja>-x64.exe`. Instalator ma język polski i angielski, pozwala wybrać folder i opcjonalny skrót na pulpicie. Instaluje program dla bieżącego użytkownika bez administratora; domyślnie w `%LOCALAPPDATA%\Programs\Szept`. Wymaga Windows 10 1809 lub nowszego, x64. Modele pobiera się w aplikacji. Deinstalacja zachowuje modele, słowniki i pliki użytkownika. Szczegóły budowania i testowania: [docs/SETUP.md](docs/SETUP.md).

## Uruchomienie EXE

Otwórz `dist/Szept/Szept.exe`. Zachowaj **cały folder Szept**, w tym `_internal`; samo przeniesienie EXE nie wystarczy. Pakiet zawiera Python, Qt, biblioteki ASR i FFmpeg/ffprobe. Nie wymaga instalacji Pythona ani administratora. Modeli nie dołączono.

1. Otwórz **Modele i słowniki**. Wybierz `small` (domyślny kompromis) lub `large-v3` (większe wymagania). Kliknij **Pobierz wybrany model**. Można też wskazać istniejący model CTranslate2. Menedżer pokazuje przybliżony rozmiar, faktyczne zajęcie dysku, postęp transferu, anulowanie i usuwanie.
2. Otwórz kartę **Słowniki pisowni**, wybierz język i kliknij **Pobierz / zainstaluj**. Katalog ma 22 pakiety w 18 językach, w tym polski, regionalny angielski, niemiecki i portugalski oraz francuski, hiszpański, ukraiński i inne. Angielski USA jest również wbudowany. Inne pakiety importuj jako parę `.aff` i `.dic` albo ZIP/OXT; dla archiwum wybierz właściwą parę i podaj kod języka. Słownik jest sprawdzany przed instalacją. Lista w edytorze odświeża się od razu. Liczba języków pisowni jest niezależna od liczby języków ASR.
3. Otwórz lub upuść audio, wybierz język lub automatyczne wykrycie, model oraz CPU. NVIDIA wymaga zgodnego CUDA 12, cuDNN 9 i wystarczającej pamięci. Niepowodzenie GPU pozwala przełączyć wybór na CPU; ponowny start jest jawny.
4. Kliknij **Transkrybuj**. Anulowanie kończy proces wraz z jego FFmpeg i zachowuje odebrane segmenty jako niepełny projekt. Postęp wskazuje przetworzony czas nagrania, a nie przewidywany czas zakończenia. Brak sztucznej ETA.
5. Zaznacz wiersz napisów, by ustawić odsłuch. Tekst wybranego segmentu edytujesz **pod tabelą**. Początek i koniec można edytować dwuklikiem w komórkę (`HH:MM:SS,mmm` lub sekundy). Widok **Tekst ciągły** udostępnia każdy segment jako osobny akapit. Enter wpisuje spację; zmiany struktury wykonuj przez **Podziel przy kursorze** i **Połącz z następnym**. Te akcje zachowują granice projektu.
6. Błędy ortograficzne mają czerwoną falistą linię. Menu słowa daje propozycje, ignorowanie jednego wystąpienia, ignorowanie wszystkich wystąpień oraz trwały słownik użytkownika. W menedżerze przycisk **Moje słowa** pozwala usuwać lub dopisywać wyrazy osobno dla języków. Podpowiedzi działają w osobnym procesie z limitem 8 s; kontrola reszty tekstu działa niezależnie. Apostrofy i akcenty Unicode są obsługiwane spójnie, a adresy, e-maile i identyfikatory z cyframi są pomijane. Można wyłączyć sprawdzanie albo użyć **Sprawdź ponownie** po awarii. Kontrola nie modyfikuje tekstu. To ortografia, nie gramatyka.
7. Wybór słownika zmienia domyślne sprawdzanie. Przycisk **Język dla zaznaczenia / segmentu** stosuje go do segmentu albo segmentów objętych zaznaczeniem tekstu; zakres jest segmentowy, nie pojedyncze słowa wewnątrz akapitu.
8. Eksportuj TXT, SRT, WebVTT albo JSON projektu. TXT nie zawiera czasów, chyba że włączysz odpowiednią opcję. JSON zachowuje oryginalną transkrypcję, edycje, czasy słów, profil i informację o niepełnym wyniku. Zapis projektu i eksport JSON są tym samym schematem. Eksport nie zapisuje podkreśleń.

**Ctrl+O** audio, **Ctrl+S** projekt, **Ctrl+Shift+S** eksport, **Ctrl+Z / Ctrl+Y** cofanie/ponawianie, **Ctrl+F** szukanie, **Ctrl+Spacja** odsłuch segmentu. Historia grupuje szybkie pisanie, ma do 150 stanów i cel około 64 MiB (zawsze co najmniej dwa stany). Po otwarciu JSON zaczyna się nowa historia. Oryginalny tekst pozostaje w projekcie.

## Dane i praca offline

Domyślny katalog: `%LOCALAPPDATA%/Szept`. Zawiera modele, słowniki, `words-<język>.json` oraz `recovery.json`. Ustawienia interfejsu i ścieżki zapisuje QSettings w `HKEY_CURRENT_USER/Software/Szept/Szept`. Folder modeli można zmienić. Usuwanie w menedżerze obejmuje wyłącznie model z katalogu aplikacji, nigdy wskazany zewnętrzny folder.

Nagrania i tekst nie są wysyłane. Sieć wykorzystują tylko jawne przyciski pobierania: Hugging Face dla modeli i repozytorium LibreOffice dla pakietów pisowni. Identyfikator rewizji i pochodzenie pobranych zasobów są zapisywane obok nich. W transkrypcji wymuszono `local_files_only=True`. Po instalacji zasobów można odłączyć internet.

Projekt z niezapisanymi zmianami jest zapisywany co 3 sekundy. Po awarii aplikacja proponuje odzyskanie. Przy brakującym nagraniu proponuje wskazanie pliku. Wyjście ostrzega o niezapisanych zmianach. Czyste zamknięcie usuwa plik odzyskiwania; zapisany projekt pozostaje. Tekst projektu jest lokalnym plikiem jawnym, bez szyfrowania.

## Napisy i ograniczenia

- Domyślny profil: 2 wiersze, 42 znaki, 17 znaków/s, 1–7 sekund. Ustawienia są zaleceniami czytelności. Nadmiar znaków nie usuwa ani nie skraca wypowiedzi. Liczenie znaków używa punktów kodowych Unicode, a nie szerokości ekranowej czy klastrów grafemów; dla niektórych systemów pisma profil wymaga dostosowania.
- Segmenty są dzielone według rzeczywistych czasów słów, długości, interpunkcji i profilu. Długie wyrazy nie są rozcinane. ASR i jego czasy są przybliżone. Zmiana tekstu i podział bez zachowanych czasów słów oznacza potrzebę weryfikacji synchronizacji. Nie jest to miara ortografii.
- SRT/VTT blokują czasy ujemne, zerowe po zaokrągleniu do ms, nakładanie/kolejność, wyjście poza nagranie oraz puste napisy. Nie naprawiają czasów automatycznie. Ostrzeżenia czytelności nie blokują zapisu. Nie ma automatycznej propozycji naprawy wszystkich czasów; popraw je w tabeli.
- TXT zapisuje bieżące akapity bez walidacji osi czasu. SRT nie akceptuje wpisanych znaczników `<...>`, aby odtwarzacz nie potraktował ich jako stylu. VTT escapuje `&`, `<` i `>`.
- Audio bada ffprobe. Obsługa kontenera zależy od rzeczywistej kompilacji FFmpeg, kodeka i stanu pliku. Uszkodzone i chronione DRM pliki mogą nie działać. Odtwarzacz Qt może obsługiwać mniej kontenerów niż importer FFmpeg.
- Rozpoznawanie używa VAD i czasów słów. Audio jest dekodowane po **10 minut**, co ogranicza RAM zależny od długości nagrania. Przecięta na granicy okna wypowiedź może być gorsza; segmenty przy granicach oznaczono do sprawdzenia. Nie jest to pełny streaming ani diarization. Automatyczny język jest ustalany w pierwszym oknie, nie zmienia się automatycznie w nagraniu wielojęzycznym.
- Krótkie, ciche i zaszumione próbki mogą dać mylny język lub tekst. Wskaźnik detekcji pochodzi z modelu i nie jest skalibrowaną gwarancją poprawności.
- Menedżer nie pobiera modeli `.en`. `large-v3` obsługuje dodatkowo `yue`; pozostałe modele katalogowe używają 99 języków Whisper. Dla zewnętrznego modelu lista języków jest odczytywana ze znaczników jego tokenizer.json (gdy ich brak, pokazywany jest tylko angielski). Silnik sprawdza obsługę wybranego języka po załadowaniu. Model musi być zgodnym modelem Whisper w formacie faster-whisper.
- Brak ASS, diarization, rozpoznawania dźwięków i korekty LLM. Pliki użytkownika nie są usuwane. Modele nie są pobierane w tle podczas startu.

## Uruchomienie ze źródeł

Windows x64, Python **3.12.10**, FFmpeg i ffprobe w PATH. Wersje wszystkich zależności są w `requirements-lock.txt`; bezpośrednie w `requirements.txt`.

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
.venv/Scripts/python.exe main.py
```

Można też uruchomić `powershell -ExecutionPolicy Bypass -File scripts/run.ps1`. Pierwsza instalacja wymaga internetu. Dostępny `uv` może zastąpić pip: `uv pip install --python .venv/Scripts/python.exe -r requirements-lock.txt`.

## Testy i budowanie

Model tiny pobrany za zgodą użytkownika został przetestowany na syntetycznych próbkach PL/EN, języku automatycznym, ciszy i szumie na CPU z zablokowaną siecią procesu. Wyniki: `test-artifacts/asr/report.json`. Powtórzenie: `.venv/Scripts/python.exe scripts/asr_acceptance.py`; skrypt nie pobiera zasobów bez jawnego `--download`. Próbki testowe są syntetyczne i nie stanowią benchmarku jakości dla naturalnej mowy. Wersja 1.0.1 poprawia zgodność dekodowania z PyAV 19 oraz zapis rzeczywistych metadanych ASR do JSON.

```powershell
.venv/Scripts/python.exe -m pytest -q
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
```

Budowanie wymaga FFmpeg/ffprobe w PATH i tworzy `dist/Szept/Szept.exe` wraz z `_internal`. Skrypt zbiera licencje z **faktycznie zainstalowanych** pakietów i dane licencyjne kompilacji FFmpeg. Nie pobiera modeli. Ten sam lock zapewnia te same wersje, ale nie gwarantuje identycznych bajtów EXE na różnych komputerach.

Architektura, źródła weryfikacji, licencje i rzeczywisty zakres testów: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/THIRD_PARTY.md](docs/THIRD_PARTY.md), [docs/TEST_REPORT.md](docs/TEST_REPORT.md). Audyt błędów, zmian 1.1.0 i proponowanych nowych funkcji: [docs/AUDIT_1.1.md](docs/AUDIT_1.1.md).

## English quick start

Run `dist/Szept/Szept.exe` and keep the entire folder. In Settings choose English. In Models and dictionaries, explicitly download a multilingual Whisper model (small recommended), or locate a compatible existing CTranslate2 model. Open audio, select recording language or automatic detection, choose CPU and Transcribe. Edit captions in the panel beneath the table or the Continuous text tab. Play a segment to verify its approximate timing. Export current edits as UTF-8 TXT, SRT, WebVTT or a JSON project. Models and recordings stay local. Downloads are the only application network operations. NVIDIA requires compatible CUDA 12 and cuDNN 9; CPU works without CUDA. See the test report for unverified acceptance criteria.

## Licencja

Kod Szept: GPL-3.0-or-later, tekst w `LICENSE`. Biblioteki, modele, słowniki i narzędzia mają własne licencje; zobacz `docs/THIRD_PARTY.md` i zebrane `docs/licenses/`. Instalator sieciowy pobiera zewnętrzne biblioteki bezpośrednio od dostawców, z ich licencjami w prywatnym runtime. Sam setup nie zawiera tych binariów. Pakiety nie mają podpisu cyfrowego. Publiczna redystrybucja osobnego pełnego pakietu wymaga jeszcze uzupełnienia corresponding source dołączonych bibliotek; sam odnośnik do upstreamu nie zastępuje tych materiałów.
