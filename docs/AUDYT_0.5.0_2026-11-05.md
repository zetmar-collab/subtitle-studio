# Audyt Subtitle Studio + Szept 0.5.0

Data: 5 listopada 2026. Zakres: lokalny stan roboczy katalogu `C:\Users\Marek\Codex\Subtitle`, w tym nowe i niezatwierdzone pliki integracji. Audyt wykonano zgodnie ze skillem code-audit. Nie zmieniono kodu aplikacji.

## 1. Podsumowanie

Aplikacja desktopowa Python 3.12 / PySide6 łączy edytor filmu, warstw napisów i logo, renderowanie FFmpeg, tworzenie filmu z obrazu i audio oraz lokalną transkrypcję faster-whisper. Dane są w plikach JSON; aplikacja nie korzysta z bazy danych ani serwera HTTP. Główne punkty wejścia to `main.py`, `ui/workspace.py`, `ui/window.py` i `srtstudio/ui.py`.

Podstawowe ścieżki działania mają testy i działają. Największe ryzyka dotyczą ochrony plików użytkownika, współdzielenia odzyskiwania między instancjami oraz niepełnego resetowania i walidacji stanu. Potwierdzono **9 błędów: 2 o ważności wysokiej i 7 średniej**. Nie potwierdzono błędu o ważności krytycznej.

### Weryfikacja

- `python -m pytest -q`: **138 passed, 1 skipped**, 33,80 s. Pominięto test rzeczywistego słownika polskiego, ponieważ jego opcjonalnej próbki nie ma w lokalizacji wymaganej przez test.
- `python -m ruff check core ui srtstudio main.py --select E9,F63,F7,F82 --output-format concise`: **All checks passed**. To kontrola błędów składni i wybranych błędów logicznych, nie pełny audyt stylu ani typów.
- Dodatkowe próby wykonano w osobnych procesach, na tymczasowych plikach i z izolowanym katalogiem danych Qt. Atrapy użyte do sterowania kolejnością odpowiedzi i sprawdzania logiki ASR są wskazane poniżej.
- Przejrzano strukturę, README, instrukcje, zależności, punkt startowy, modele, adapter, interfejs, procesy robocze, renderowanie, importer/eksporter napisów, słowniki, skrypty pakowania i różnice Git.
- Nie przebudowywano ani nie publikowano instalatorów. W tym audycie nie testowano CUDA, czystej maszyny Windows ani aktualnych baz CVE. `mypy` i `pip-audit` nie są dostępne w użytym środowisku. Nie oceniano jakości ASR na naturalnych nagraniach.

## 2. Błędy krytyczne i funkcjonalne

Brak potwierdzonych problemów krytycznych. Poniżej problemy wymagające naprawy, uporządkowane według wpływu.

### A1. Zapis projektu może nadpisać źródłowy film

- **Ważność: Wysoki. Potwierdzone.**
- Lokalizacja: [ui/window.py:971](C:/Users/Marek/Codex/Subtitle/ui/window.py:971), [core/projects/model.py:104](C:/Users/Marek/Codex/Subtitle/core/projects/model.py:104); analogicznie zapis presetu: [ui/window.py:954](C:/Users/Marek/Codex/Subtitle/ui/window.py:954).
- Problem: zapis projektu przekazuje wybraną ścieżkę bez kontroli kolizji z filmem, logo i źródłami ścieżek. `save()` zastępuje docelowy plik JSON-em. Zapis presetu również zapisuje bez takiej ochrony. Filtr rozszerzeń i standardowe pytanie o nadpisanie nie zastępują tej kontroli.
- Odtworzenie: plik tymczasowy `source.mp4` z treścią kontrolną ustawiono jako film projektu i jako wynik wyboru miejsca zapisu. `save_project()` zwrócił `True`, a zawartość źródła została zastąpiona JSON-em.
- Wpływ: możliwa utrata oryginalnego materiału po wskazaniu go jako celu zapisu. Eksport filmu ma kontrolę źródeł, lecz zapis projektu i presetu jej nie stosuje.
- Minimalna poprawka: wspólny walidator celu zapisu, blokujący wszystkie źródła bieżącego projektu; walidacja rozszerzenia projektu/presetu przed zapisem. Stosować go we wszystkich operacjach zapisu, również w warstwie usług.

### A2. Druga instancja może usunąć odzyskiwanie pierwszej

- **Ważność: Wysoki. Potwierdzone.**
- Lokalizacja: [ui/window.py:50](C:/Users/Marek/Codex/Subtitle/ui/window.py:50), [ui/window.py:1056](C:/Users/Marek/Codex/Subtitle/ui/window.py:1056), [ui/window.py:1224](C:/Users/Marek/Codex/Subtitle/ui/window.py:1224), [main.py:55](C:/Users/Marek/Codex/Subtitle/main.py:55). Transkrypcja również używa jednej nazwy pliku: [srtstudio/ui.py:1122](C:/Users/Marek/Codex/Subtitle/srtstudio/ui.py:1122).
- Problem: wszystkie instancje mają ten sam plik `recovery.autosave.json`, a zamknięcie okna usuwa go bez sprawdzenia właściciela. Wspólny punkt startowy nie ma blokady pojedynczej instancji. Nazwa odzyskiwania Szept jest oddzielona od samodzielnego Szepta, ale pozostaje wspólna dla wielu kopii połączonej aplikacji.
- Odtworzenie: dwa obiekty `Window` dostały ten sam tymczasowy plik odzyskiwania. Pierwsze zapisało zmiany; zamknięcie drugiego, czystego okna usunęło ten plik. Dwie instancje procesu korzystają z tego samego domyślnego katalogu Qt.
- Wpływ: utrata możliwości odzyskania pracy pierwszej instancji po awarii; możliwe wzajemne nadpisywanie kopii.
- Minimalna poprawka: `QLockFile` dla wspólnej aplikacji albo osobne identyfikatory sesji i pliki odzyskiwania. Usuwać tylko kopię należącą do zamykanej sesji.

### A3. Projekt bez filmu zachowuje poprzednie wideo

- **Ważność: Średni. Potwierdzone.**
- Lokalizacja: [ui/window.py:1048](C:/Users/Marek/Codex/Subtitle/ui/window.py:1048).
- Problem: gdy wczytany projekt ma `video=''`, metoda pozostawia poprzednie `self.info`, źródło odtwarzacza i stan podglądu. Reset wykonuje tylko gałąź obsługująca rzeczywisty film.
- Odtworzenie: po wczytaniu pustego projektu `project.video` było puste, ale `player.source()` nadal wskazywało `old.mp4`, a `info['duration']` nadal wynosiło 9000 ms.
- Wpływ: napisy nowego projektu mogą być oglądane na poprzednim filmie; oś czasu i kontrola jakości używają błędnej długości.
- Minimalna poprawka: wspólna operacja resetowania stanu multimediów, wykonywana także podczas otwarcia projektu bez filmu. Załadować i zweryfikować projekt przed zatwierdzeniem zmiany stanu.

### A4. Starsza analiza filmu może zastąpić nowszy wybór

- **Ważność: Średni. Potwierdzone sterowanym testem kolejności odpowiedzi.**
- Lokalizacja: [ui/window.py:692](C:/Users/Marek/Codex/Subtitle/ui/window.py:692).
- Problem: wywołania `open_video()` sprawdzają tożsamość projektu, ale dwa otwarcia w tym samym projekcie mają tę samą tożsamość. Nie ma numeru żądania.
- Odtworzenie: zlecono analizę `first.mp4`, następnie `second.mp4`. Ręcznie dostarczono wyniki w odwrotnej kolejności. Oba zostały zaakceptowane; na końcu wybrany został `first.mp4`.
- Wpływ: szybkie otwarcie drugiego filmu może kończyć się pracą na pierwszym.
- Minimalna poprawka: identyfikator najnowszego żądania; ignorować sukcesy i błędy wcześniejszych żądań. Istniejący mechanizm `preview_request` w kreatorze obrazu i audio stanowi gotowy wzorzec.

### A5. Niepełna walidacja czasów słów w JSON

- **Ważność: Średni. Potwierdzone.**
- Lokalizacja: [core/projects/model.py:95](C:/Users/Marek/Codex/Subtitle/core/projects/model.py:95), użycie danych: [core/compositor/render.py:119](C:/Users/Marek/Codex/Subtitle/core/compositor/render.py:119).
- Problem: walidowane są czasy segmentu i długość tekstu, ale nie struktura `words`, wymagane klucze, typy i granice czasów. Walidacja pozostałych pól stylu i segmentu także jest niepełna.
- Odtworzenie: projekt z efektem `highlight` i `words=[{}]` przechodzi `Project.from_data()`. Próba wyrenderowania aktywnego segmentu kończy się `KeyError: 'start'`.
- Wpływ: uszkodzony lub spreparowany projekt psuje podgląd/eksport zamiast zostać odrzucony przy otwarciu. To problem odporności lokalnego parsera; nie wykazano wykonania dowolnego kodu.
- Minimalna poprawka: pełna walidacja struktury, typów, skończoności liczb, kolejności i granic czasów słów oraz dozwolonych efektów i kolorów. Błąd powinien wskazywać ścieżkę/segment/słowo, a poprzedni projekt powinien pozostać aktywny.

### A6. Akceptowany preset może utworzyć projekt nieczytelny dla własnego loadera

- **Ważność: Średni. Potwierdzone.**
- Lokalizacja: [ui/window.py:960](C:/Users/Marek/Codex/Subtitle/ui/window.py:960), rygorystyczniejszy odczyt projektu: [core/projects/model.py:93](C:/Users/Marek/Codex/Subtitle/core/projects/model.py:93).
- Problem: importer presetu sprawdza tylko rozmiar fontu i pozycję. Pomija m.in. szerokość, obrys i czas animacji.
- Odtworzenie: preset `{"width":0}` został zastosowany. Następnie `Project.from_data()` dla danych tego samego projektu zgłosił nieprawidłowy styl.
- Wpływ: zapisany projekt może nie dać się ponownie otworzyć; worker eksportu również wczytuje projekt i może go odrzucić.
- Minimalna poprawka: jeden walidator `Style`, wspólny dla presetów, projektów i renderowania; zastosowanie presetu dopiero po pełnej walidacji.

### A7. Transkrypcja nie znajduje FFmpeg leżącego obok EXE

- **Ważność: Średni. Potwierdzone przez sprawdzenie rozwiązywania ścieżki, bez uruchamiania atrapy EXE.**
- Lokalizacja: [srtstudio/audio.py:12](C:/Users/Marek/Codex/Subtitle/srtstudio/audio.py:12), porównanie: [core/media/tools.py:11](C:/Users/Marek/Codex/Subtitle/core/media/tools.py:11).
- Problem: edytor szuka narzędzi obok aplikacji i w PATH; Szept szuka w `_internal/bin` i w PATH. Instalator dopuszcza dostarczenie narzędzi obok programu.
- Odtworzenie: w symulacji pakietu z `ffmpeg.exe` obok `SubtitleStudio.exe` i bez narzędzia w PATH funkcja edytora znalazła plik, a Szept zgłosił `FileNotFoundError`. To samo dotyczy ffprobe.
- Wpływ: konfiguracja wystarczająca do montażu i eksportu może nie wystarczyć do transkrypcji.
- Minimalna poprawka: wspólna usługa lokalizacji narzędzi, respektująca te same katalogi i pokazująca faktycznie wybraną ścieżkę.

### A8. Powrót do transkrypcji projektu audio może mieć długość 0

- **Ważność: Średni. Potwierdzone na poziomie adaptera i sterowania workerem.**
- Lokalizacja: [ui/workspace.py:95](C:/Users/Marek/Codex/Subtitle/ui/workspace.py:95), [srtstudio/ui.py:580](C:/Users/Marek/Codex/Subtitle/srtstudio/ui.py:580), [srtstudio/engine.py:98](C:/Users/Marek/Codex/Subtitle/srtstudio/engine.py:98).
- Problem: gdy projekt filmu nie ma wideo, ale ścieżka wskazuje audio, długość pochodzi z `editor.info`, zwykle 0. Jest odzyskiwana tylko z już istniejącej, zgodnej sesji transkrypcji. Przekazanie danych nie wykonuje ponownego probe audio.
- Odtworzenie: ścieżkę z audio i poprawnym segmentem przekazano przy `editor.info['duration']=0` i niezainicjalizowanej karcie Szept. Powstał projekt o długości 0. Test workera z atrapą modelu wykazał zdarzenia `loading`, następnie `done`, bez dekodowania i segmentów. Ta próba sprawdzała logikę zakresu, nie jakość ani działanie sieci neuronowej.
- Wpływ: po ponownym otwarciu projektu audio pasek odsłuchu może mieć zerowy zakres. Ponowne ASR może skasować bieżącą listę segmentów i zakończyć się pustym wynikiem.
- Minimalna poprawka: asynchronicznie ustalić metadane źródła przy przekazywaniu; przed wyczyszczeniem segmentów sprawdzić dodatni, skończony czas nagrania.

### A9. Podział napisu jednowyrazowego tworzy pusty segment

- **Ważność: Średni. Potwierdzone.**
- Lokalizacja: [ui/window.py:820](C:/Users/Marek/Codex/Subtitle/ui/window.py:820).
- Problem: tekst dzielony jest zawsze według połowy liczby słów, niezależnie od pozycji kursora w czasie i dostępnych czasów słów.
- Odtworzenie: napis `Słowo`, zakres 0–1000 ms, kursor 500 ms. Wynik: teksty `['Słowo', '']`.
- Wpływ: powstaje pusty napis; przy dłuższej wypowiedzi podział może rozdzielić tekst niezgodnie z rzeczywistą mową i usuwa wyrównanie słów.
- Minimalna poprawka: odmówić podziału bez dwóch niepustych części. Jeżeli czasy słów są aktualne, dzielić przy najbliższej granicy słowa do kursora; w pozostałych przypadkach poprosić o punkt podziału tekstu.

## 3. Bezpieczeństwo

Najważniejsze potwierdzone problemy ochrony danych to A1 i A2. Odporność na nieprawidłowe dane wejściowe wymaga napraw A5 i A6.

Pozytywne mechanizmy widoczne w kodzie:

- FFmpeg uruchamiany jest listą argumentów, bez składania poleceń powłoki.
- Import archiwum słownika czyta wybraną parę do stałych nazw, zamiast wypakowywać ścieżki ZIP: [srtstudio/dictionaries.py:153](C:/Users/Marek/Codex/Subtitle/srtstudio/dictionaries.py:153). Obecne są limity rozmiaru i kontrola integralności pobieranych pakietów słowników.
- Publikowanie katalogów i usuwanie modeli kontroluje docelową ścieżkę i dowiązania: [srtstudio/dictionaries.py:91](C:/Users/Marek/Codex/Subtitle/srtstudio/dictionaries.py:91), [srtstudio/managers.py:187](C:/Users/Marek/Codex/Subtitle/srtstudio/managers.py:187).
- Eksport filmu pracuje na pliku tymczasowym i podmienia cel po weryfikacji. Szept wymusza lokalne pliki modelu w ASR.

W przeszukanych katalogach kodu nie znaleziono dopasowań do sprawdzanych wzorców kluczy prywatnych i wybranych tokenów dostępowych. Nie stanowi to pełnego audytu wszystkich formatów sekretów. CORS, CSRF i sesje HTTP nie dotyczą obecnej lokalnej architektury.

Zależności bezpośrednie mają przypięte wersje, ale brak pełnego lockfile zależności przechodnich i ich hashy. Bootstrap instaluje z `requirements.txt`: [installer/bootstrap.py:28](C:/Users/Marek/Codex/Subtitle/installer/bootstrap.py:28). Zalecenie: odtwarzalne środowisko, pełna lista wersji i hashy oraz osobny automatyczny audyt aktualnych podatności. W tym przeglądzie nie potwierdzano ani nie wykluczano konkretnych CVE.

## 4. Wydajność i jakość

### P1. Kontrola nakładania napisów ma złożoność O(n²)

- Lokalizacja: [core/subtitles/service.py:89](C:/Users/Marek/Codex/Subtitle/core/subtitles/service.py:89), wywołanie przy odświeżeniu tabeli: [ui/window.py:414](C:/Users/Marek/Codex/Subtitle/ui/window.py:414).
- Jednorazowy pomiar dla niepokrywających się segmentów: 1000 — **55,2 ms**, 3000 — **472,5 ms**, 6000 — **1994,8 ms**, bez tworzenia komórek tabeli. Pomiar dotyczy aktualnego komputera.
- Wpływ: przy dłuższych transkrypcjach pojedyncza edycja uruchamia kosztowne sprawdzenie i odbudowę całej tabeli w wątku GUI.
- Poprawka: algorytm przedziałowy po sortowaniu, cache wyników oraz aktualizacja zmienionych wierszy. Docelowo model tabeli zamiast odtwarzania wszystkich `QTableWidgetItem`.

### P2. Niektóre operacje nadal blokują główny wątek

- Otwieranie projektu wykonuje `probe()` synchronicznie: [ui/window.py:1048](C:/Users/Marek/Codex/Subtitle/ui/window.py:1048); timeout procesu wynosi 30 s: [core/media/tools.py:21](C:/Users/Marek/Codex/Subtitle/core/media/tools.py:21).
- Propozycje pisowni edytora filmu są pobierane synchronicznie: [ui/window.py:927](C:/Users/Marek/Codex/Subtitle/ui/window.py:927). Szept ma już osobny proces i limit czasu dla propozycji.
- Poprawka: współdzielić usługę zadań/metadanych oraz izolowany silnik pisowni. Czas blokowania na konkretnych uszkodzonych plikach i dużych słownikach wymaga osobnych pomiarów.

### P3. Pamięć ograniczana jest liczbą elementów, nie bajtami

- Historia filmu trzyma do 60 pełnych kopii projektu: [ui/window.py:353](C:/Users/Marek/Codex/Subtitle/ui/window.py:353). W Szept istnieje już limit wielkości historii, który może posłużyć jako wzorzec.
- Cache grafik trzyma do 32 pełnych obrazów, a limit 80 MP sprawdzany jest po dekodowaniu: [core/compositor/render.py:8](C:/Users/Marek/Codex/Subtitle/core/compositor/render.py:8). Obraz 80 MP przy 4 bajtach/piksel to około 320 MB; 32 takie obrazy to teoretycznie około 10 GB. To oszacowanie, nie test wyczerpywania pamięci.
- Poprawka: budżet bajtów dla historii i cache, sprawdzanie wymiarów przed dekodowaniem, skalowane warianty podglądu. Nie przeprowadzano destrukcyjnej próby OOM.

### P4. Po integracji pozostały równoległe usługi

Dwie implementacje lokalizacji FFmpeg doprowadziły do A7. Są też dwa modele projektu, dwa silniki pisowni, różne katalogi słowników i różne zasady zapisu. Słownik zainstalowany przez menedżer Szept nie staje się automatycznie słownikiem `core.spellcheck`.

Nie trzeba od razu scalać całych edytorów. Najpierw warto wydzielić wspólne usługi: metadane i narzędzia, bezpieczny zapis, walidacja, słowniki oraz historia. Duże klasy okien powinny następnie delegować operacje projektu do tych usług.

### Ryzyka wymagające dalszej weryfikacji

- Anulowanie eksportu jest sprawdzane pomiędzy klatkami; blokujące `decoder.stdout.read()` i `encoder.stdin.write()` nie mają niezależnego nadzorcy anulowania: [core/export/worker.py:65](C:/Users/Marek/Codex/Subtitle/core/export/worker.py:65). Nie odtworzono zawieszenia rzeczywistego dekodera; potrzebny jest kontrolowany test awarii i limitu czasu.
- Błąd podczas `multiprocessing.Process.start()` nie ma rollbacku w `Job.start()`: [srtstudio/jobs.py:33](C:/Users/Marek/Codex/Subtitle/srtstudio/jobs.py:33). Potrzebna próba wymuszonego błędu startu i sprawdzenie przywracania kontrolek oraz sprzątania kolejki i katalogu pracy.

## 5. Brakujące testy

Najważniejsze testy regresji do dodania:

1. Zapis projektu i presetu na ścieżkę filmu, logo, audio i źródła napisów — plik źródłowy musi pozostać identyczny bajtowo.
2. Dwie instancje i właściciel odzyskiwania; zamknięcie jednej nie usuwa ani nie podmienia danych drugiej.
3. Otwarcie projektu bez filmu po projekcie z filmem; pełne wyczyszczenie odtwarzacza, metadanych, klatki i zakresu.
4. Odwrócona kolejność wyników analizy dwóch filmów oraz spóźniony błąd wcześniejszego żądania.
5. Uszkodzone `words`, błędne typy, wartości nieskończone i nieprawidłowe style; odrzucenie bez zmiany aktywnego projektu.
6. Każdy zaakceptowany preset musi dać się zapisać, odczytać i wyrenderować.
7. Pakiet EXE z narzędziami wyłącznie obok EXE, bez FFmpeg w PATH — obie karty mają działać.
8. Projekt audio: zapis, ponowne uruchomienie, przekazanie do Szept i ustalenie dodatniej długości. ASR z długością 0 nie może usuwać segmentów ani zgłaszać sukcesu.
9. Podział jednego słowa oraz podział przy rzeczywistych granicach słów ASR.
10. Wydajność tabeli przy 6000–10 000 segmentów, limit historii, anulowanie zablokowanego procesu i nieudany start workera.

W audycie nie dopisywano tych testów do repozytorium, zgodnie z zakresem przeglądu bez zmian w kodzie.

## 6. Propozycje funkcji

Obecna aplikacja nie ma bazy danych; poniższe funkcje mogą nadal korzystać z wersjonowanych plików projektu. Zakres M oznacza zmianę kilku modułów, L — zmianę obejmującą interfejs i format danych lub kilka etapów przetwarzania.

| Funkcja | Problem użytkownika i działanie | Priorytet | Szacowany zakres |
|---|---|---|---|
| Wspólny projekt sesji | Jeden zapis obejmujący film, style, transkrypcję, oryginalny tekst i powiązane media; jedno odzyskiwanie i polecenie „Nowy projekt”. | MVP | L: interfejs Qt, model/wersjonowanie JSON, zapis i migracja odczytu, testy obu kart; bez DB. |
| Aktualizacja powiązanej ścieżki | Ponowne przekazanie poprawionej transkrypcji aktualizuje wskazaną ścieżkę zamiast zawsze dodawać następną; zachowuje jej styl i pokazuje różnice. | MVP | M: identyfikatory segmentów/ścieżek, adapter, interfejs potwierdzenia, undo i testy; bez DB. |
| Prowadzony proces „Film → napisy → MP4” | Użytkownik wybiera źródło, język i styl, sprawdza wynik ASR, a następnie eksportuje. Poszczególne etapy mają jawny status i możliwość powrotu. | Ważne | M: interfejs etapów, koordynator istniejących workerów, obsługa błędów, testy integracyjne; bez DB. |
| Propozycje naprawy synchronizacji | Program proponuje poprawki nakładania, zerowych czasów i wyjścia poza film; pokazuje podgląd zmian, zachowuje treść i umożliwia cofnięcie. | Ważne | M: walidator/algorytm przedziałów, okno różnic, testy granic i czasów słów; bez DB. |
| Edycja słów na fali audio | Przeciąganie granic słów, odsłuch krótkiej pętli i natychmiastowy podgląd aktywnego słowa. Ułatwia korektę przybliżonych czasów ASR. | Ważne | L: oś czasu Qt, model czasów słów, transport audio, testy interakcji; bez DB. |
| Kolejka eksportów i wariantów obrazu | Jedno zlecenie tworzy np. 16:9, 9:16 i 1:1, z osobnym kadrem/pozycją napisów; kolejka pozwala wznowić pozostałe zadania po błędzie. | Ważne | L: profile wyjścia, kolejka workerów, zapis zleceń, kontrola zasobów i testy; bez DB. |
| Pokaz wielu zdjęć z audio | Lista zdjęć i klipów, czasy ekspozycji, przejścia oraz opcjonalny delikatny ruch zdjęcia; uzupełnia obecny kreator pojedynczego obrazu. | Później | L: edytor listy materiałów, schemat osi klipów, filtry FFmpeg, testy długości i kadrowania; bez DB. |
| Lista fragmentów do sprawdzenia | Zbiera segmenty oznaczone `review`, granice okien ASR i słowa o słabych ocenach modelu. Kliknięcie odtwarza kontekst, a poprawki można oznaczyć jako sprawdzone. | Ważne | M: interfejs przeglądu, zachowanie metadanych przez adapter, testy filtrowania i odsłuchu; bez DB. |

## 7. Plan działania

1. **Ochrona danych:** A1 i A2 oraz odpowiadające im testy blokujące regresję. Wspólny walidator zapisu i jasno określony właściciel sesji.
2. **Spójność stanu i wejścia:** A3–A8. Reset mediów, numerowanie żądań, pełna walidacja modeli/presetów, wspólne ścieżki narzędzi i ustalanie długości audio przed ASR.
3. **Operacje napisów:** A9 i testy podziału według czasów słów. Zachować możliwość cofnięcia każdej operacji.
4. **Wydajność:** zastąpić sprawdzanie O(n²), odchudzić odświeżanie tabeli, ograniczyć historię/cache bajtami, przenieść blokujące zadania poza GUI.
5. **Wspólne usługi i środowisko:** bezpieczny zapis, metadane, pisownia, pełny lockfile, automatyczne testy źródeł i EXE. Zatwierdzić testowany stan w Git, aby wynik miał jednoznaczny punkt odniesienia.
6. **Rozwój:** najpierw wspólny projekt i aktualizacja powiązanej ścieżki, potem prowadzony proces, korekta synchronizacji i przegląd ASR. Kolejka wariantów i pokaz zdjęć po ustabilizowaniu modelu danych.

Naprawy nie zostały wdrożone w ramach tego audytu. Nie zmieniono aplikacji, instalatorów ani publikacji GitHub; dodano wyłącznie ten raport.
