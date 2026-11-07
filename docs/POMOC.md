# Subtitle Studio — pomoc i skróty klawiszowe

Pomoc otworzysz z menu **Pomoc → Instrukcja obsługi** lub klawiszem **F1**.
Nie wymaga internetu. Przycisk „Skróty klawiszowe” i **Ctrl+F1** prowadzą do
tabeli skrótów. Pole wyszukiwania przeszukuje aktualnie otwarty rozdział;
Enter przechodzi do następnego wystąpienia. „Wstecz” wraca do poprzedniego
rozdziału, a „Spis treści” do tej strony. Escape zamyka okno pomocy.

## Od filmu do gotowych napisów

1. **Otwórz film**. Program odczyta jego parametry i przygotuje falę audio.
2. W panelu **Krok po kroku** wybierz język i model rozpoznawania mowy.
   Modele instaluje się w „Modele i słowniki”. Pobranie wymaga internetu;
   samo rozpoznawanie odbywa się lokalnie.
3. Kliknij **Rozpoznaj mowę**. Zaczekaj na zakończenie, popraw tekst
   i sprawdź czasy w karcie **Rozpoznawanie mowy**.
4. **Zastosuj napisy** przekazuje wynik do filmu. Przy ponownym przekazaniu
   możesz zaktualizować powiązaną ścieżkę, zachowując jej styl, dodać osobną
   albo anulować. Samo przełączanie kart nie przekazuje zmian.
5. W karcie **Film i napisy** wybierz styl i ustaw wygląd. Opcjonalnie dodaj logo.
6. **Eksportuj film** zapisuje gotowy film. Po sukcesie program zapyta,
   czy odtworzyć wynik w domyślnym odtwarzaczu Windows. „Nie teraz” nie usuwa
   filmu; przycisk „Otwórz film” przy wyniku pozwala uruchomić go później.

Masz gotowy plik napisów? Zamiast rozpoznawania użyj **Importuj napisy**.
Masz tylko zdjęcie i nagranie? Skorzystaj z **Więcej → Obraz + audio**.

## Pliki, projekty i kopie awaryjne

**Zapisz projekt / Zapisz sesję** zapisuje plik JSON z tekstem, czasami,
warstwami, stylami i transkrypcją obu kart. **Zapisz sesję jako** tworzy
osobny plik. Film, audio i logo pozostają osobnymi plikami: projekt ich
nie zawiera. Przenosząc projekt na inny komputer, skopiuj także media.
Przy otwieraniu można ponownie wskazać brakujące pliki.

**Eksportuj napisy** zapisuje tekst i czasy w formacie napisów.
**Eksportuj film** zapisuje film z napisami i logo jako częścią obrazu.
Zapis projektu nie tworzy gotowego filmu.

**Nowa sesja** czyści obie karty po pytaniu o niezapisane zmiany. Cofanie
i ponawianie dotyczą edycji w aktualnej karcie; historie obu kart są osobne.
Zmiany mają kopie awaryjne. Po nieoczekiwanym zamknięciu program proponuje
odzyskanie. Nie otwieraj jednej kopii odzyskiwania w dwóch instancjach.

## Edycja napisów i synchronizacja

- Zaznacz ścieżkę po lewej, a następnie wiersz w tabeli. Tekst edytuj
  w komórce; czasy przyjmują `HH:MM:SS.mmm` albo milisekundy.
- **Dodaj napis** tworzy napis w miejscu odtwarzania. **Usuń** usuwa
  zaznaczone wiersze. Zmianę można cofnąć.
- **Podziel** dzieli zaznaczony napis w miejscu odtwarzania; wybiera granicę
  słów lub prosi o wskazanie podziału tekstu. **Połącz** łączy sąsiednie wiersze.
- **Synchronizacja → Przesuń napisy w czasie** przesuwa zaznaczone napisy,
  a bez zaznaczenia całą ścieżkę. `500` oznacza pół sekundy później.
- **Dopasuj do dwóch punktów** przelicza czasy na podstawie dwóch par
  punktów źródłowych i docelowych. Sprawdź rezultat przed eksportem.
- **Czasy poszczególnych słów** i **Słowa na fali audio** służą dokładnemu
  dopasowaniu efektów słownych do nagrania. Zmiana tekstu lub granic napisu
  może unieważnić wcześniejsze dopasowanie słów.
- **Sprawdzanie → Sprawdź napisy** ustawia limity czytelności. Uwagi tabeli
  wskazują między innymi nieprawidłowe czasy, nakładanie i zbyt szybki tekst.
- Importowany TXT bez czasów trzeba zsynchronizować. Nie można eksportować
  napisów z nieprawidłowymi czasami.

Oś czasu pozwala zaznaczać napisy i przeciągać ich granice. Suwak pod
podglądem przewija film. **I** i **O** ustawiają zakres; „Pętla zakresu”
powtarza ten fragment, a „Przyciągaj” ułatwia dopasowanie granic.
Powiększenie osi ułatwia precyzję. Jej przycisk „Dopasuj oś” pokazuje cały film.

## Wygląd, animacje i logo

Właściwości po prawej zależą od zaznaczenia: ścieżka napisów pokazuje
ustawienia tekstu, a logo ustawienia grafiki. Wybierz gotowy styl lub ustaw
czcionkę, rozmiar, obrys i kolory. Rozmiar tekstu odnosi się do wysokości
1080 pikseli i skaluje z rozmiarem filmu. Paleta kolorów umożliwia ustawienie
przezroczystości; szachownica oznacza przezroczyste tło. Anulowanie palety
przywraca poprzedni kolor, a zatwierdzenie stanowi jeden krok cofania.

Animacje: bez animacji, zanikanie, wjazd z lewej/prawej/dołu, maszyna do
pisania, kolejne słowa, aktywne słowo i powiększenie. Efekty słowne są
najdokładniejsze z poprawnymi czasami słów. Bez nich program korzysta
z przybliżenia. Sprawdź podgląd i krótki eksport próbny.

Pozycja X/Y to procenty kadru. Można także wybrać punkt siatki lub przesunąć
obiekt myszą w podglądzie. **Dodaj logo** obsługuje grafiki, w tym PNG
z przezroczystością. Szerokość 100% oznacza szerokość całego filmu.
Ustaw widoczność, początek i koniec w milisekundach. Warstwy można ukrywać,
przesuwać w kolejności i usuwać. Własny styl można zapisać i wczytać z JSON.

Język, jasny/ciemny/systemowy motyw i rozmiar interfejsu zmienisz nad edytorem.
Skale 100%, 115% i 130% powiększają tekst. Przy małym oknie użyj pasków
przewijania i separatorów paneli. Panel „Krok po kroku” można zamknąć
i ponownie otworzyć. F11 przełącza pełny ekran całej aplikacji.

## Rozpoznawanie mowy, pisownia i korekta AI

Wybierz język nagrania lub wykrywanie automatyczne, pobrany lokalny model
oraz procesor CPU albo obsługiwaną kartę NVIDIA. Większy model może być
dokładniejszy, ale potrzebuje więcej pamięci i czasu. Postęp i „Anuluj”
dotyczą aktualnego zadania. Przed rozpoczęciem ponownego rozpoznawania
program pyta o zastąpienie dotychczasowych napisów.

Tabela **Napisy** i **Tekst ciągły** pokazują tę samą transkrypcję.
Odsłuchuj fragmenty podczas poprawiania. **Fragmenty do sprawdzenia**
zbierają ostrzeżenia modelu; ocena modelu nie gwarantuje poprawności.
Zmiana tekstu powinna być sprawdzona odsłuchem.

Pisownia korzysta z lokalnych słowników. Nazwy własne mogą być podkreślone.
Wybierz sugestię, zignoruj słowo albo dodaj je do słownika użytkownika.
Słownik można ustawić osobno dla języka lub zaznaczenia.

**Korekta AI** wymaga uruchomionej lokalnej Ollamy i pobranego modelu
tekstowego. Wybierz zakres tekstu, uruchom analizę i zatwierdź tylko wybrane
propozycje. Program nie stosuje ich automatycznie. Sprawdź nazwy i znaczenie
zdań. Modeli nie dołączono do instalatora. [Szczegóły Ollamy](OLLAMA.md).

## Eksport i odtwarzanie gotowego filmu

Domyślnie wybierz MP4, oryginalny rozmiar i jakość standardową lub wysoką.
**Zaawansowane ustawienia** udostępniają kodek, FPS i CRF. Niższy CRF
oznacza zwykle wyższą jakość i większy plik. Zmiana proporcji może dodać
pasy. Eksport ma stały FPS i ponownie koduje obraz; nie jest bezstratny.

Możesz wybrać zaznaczony zakres oraz próbę pierwszych 10 sekund tego zakresu.
Wynik powstaje na podstawie migawki projektu z początku eksportu: późniejsza
edycja nie zmienia trwającego zadania. Postęp i przycisk anulowania są na dole.
Poprawnie zakończony plik jest sprawdzany przed zastąpieniem wyniku.
Anulowanie zachowuje poprzedni plik. Błąd oferuje ponowienie i szczegóły.

Po sukcesie kliknij **Odtwórz film**, aby uruchomić odtwarzacz skojarzony
z rozszerzeniem pliku w Windows. Program nie instaluje własnego odtwarzacza.
Jeżeli uruchomienie się nie powiedzie, skonfiguruj aplikację domyślną w
ustawieniach Windows. „Pokaż w folderze” otwiera folder wyniku.
Kreatory obrazu z audio, łączenia i pokazu zdjęć także proponują odtworzenie.
Kolejka proponuje odtworzenie ostatniego poprawnego wyniku po zakończeniu serii;
nie przerywa renderowania pytaniem po każdym wariancie.

## Pozostałe narzędzia

- **Więcej → Połącz filmy** łączy klipy w wybranej kolejności.
  [Instrukcja montażu, zakresu i osi czasu](CONCAT.md).
- **Więcej → Obraz + audio** tworzy film ze zdjęcia lub klipu i osobnego
  dźwięku. Wybierz format, dopasowanie z pasami lub przycięcie i zachowanie
  długości. Dźwięk pochodzi z wybranego osobnego nagrania.
- **Narzędzia → Pokaz zdjęć i klipów** układa materiały z muzyką,
  opcjonalnymi przejściami i ruchem zdjęć. [Opis narzędzi](NOWOSCI_0.6.md).
- **Narzędzia → Napraw synchronizację** pokazuje propozycje czasów.
  Sprawdź je i zastosuj świadomie; nie zmienia treści napisów.
- **Narzędzia → Kolejka eksportów** zapisuje kilka wariantów rozmiaru
  i kadru. Każde zadanie ma własną migawkę. Kolejkę można zatrzymać,
  wznowić z pliku `.exports.json` i ponowić błędne zadania.

<a name="skroty"></a>

## Skróty klawiszowe — wspólne okno programu

Skróty dotyczą aktywnego okna. Escape zamyka zwykłe okno dialogowe;
nie wymusza zamknięcia trwającego eksportu. Podczas wpisywania tekstu
Delete, Insert, spacja, strzałki i I/O nie powinny uruchamiać montażu.

| Skrót | Czynność |
|---|---|
| F1 | Instrukcja obsługi |
| Ctrl+F1 | Tabela skrótów |
| Shift+F1 | Informacje o aplikacji i licencjach |
| F2 | Karta Film i napisy |
| F3 | Karta Rozpoznawanie mowy |
| F4 | Przewodnik Krok po kroku |
| F6 | Rozpoznaj mowę z bieżącego filmu |
| F7 | Sprawdź pisownię w aktywnej karcie |
| F11 | Pełny ekran całego programu |
| Ctrl+N | Nowa wspólna sesja |
| Ctrl+Shift+O | Otwórz wspólną sesję |
| Ctrl+S | Zapisz wspólną sesję, z dowolnej karty |
| Ctrl+Shift+S | Zapisz wspólną sesję jako |
| Ctrl+Shift+R | Przekaż napisy filmu do edycji tekstu |
| Ctrl+Shift+G | Zastosuj transkrypcję w filmie |
| Ctrl+Shift+A | Korekta AI przez lokalną Ollamę |
| Ctrl+Shift+H | Napraw synchronizację |
| Ctrl+Shift+W | Edytuj czasy słów na fali audio |
| Ctrl+Shift+F | Fragmenty do sprawdzenia |
| Ctrl+Shift+Q | Kolejka eksportów |
| Ctrl+Shift+P | Pokaz zdjęć i klipów |

### Karta Film i napisy

| Skrót | Czynność |
|---|---|
| Ctrl+O | Otwórz film |
| Ctrl+I | Importuj napisy |
| Ctrl+L | Dodaj logo |
| Ctrl+E | Eksportuj film |
| Ctrl+Shift+E | Eksportuj plik napisów |
| Ctrl+J | Połącz filmy |
| Ctrl+Shift+V | Film z obrazu i audio |
| Ctrl+Z / Ctrl+Y | Cofnij / ponów |
| Spacja | Odtwórz / wstrzymaj podgląd |
| Strzałka w lewo / prawo | Poprzednia / następna przybliżona klatka |
| Home / End | Początek / koniec filmu |
| Ctrl+strzałka w lewo / prawo | Poprzednia / następna granica napisu |
| Insert | Dodaj napis |
| Delete | Usuń zaznaczone napisy |
| Ctrl+B | Podziel napis |
| Ctrl+Shift+B | Połącz zaznaczone sąsiednie napisy |
| Ctrl+D | Duplikuj zaznaczone napisy |
| Shift+Delete | Usuń napisy i domknij odstępy |
| Ctrl+F | Znajdź i zamień, poza edycją komórki |
| Ctrl+Shift+T | Przesuń napisy w czasie |
| Ctrl+Shift+K | Ustaw kontrolę jakości napisów |
| Ctrl+= / Ctrl+- | Powiększ / pomniejsz oś czasu |
| I / O | Ustaw początek / koniec zakresu |

### Karta Rozpoznawanie mowy

| Skrót | Czynność |
|---|---|
| Ctrl+O | Otwórz audio lub film do transkrypcji |
| Ctrl+Shift+E | Eksportuj transkrypcję / plik napisów |
| Ctrl+Z / Ctrl+Y | Cofnij / ponów edycję transkrypcji |
| Ctrl+F | Przejdź do pola wyszukiwania tekstu |
| Ctrl+Spacja | Odsłuchaj zaznaczony segment |

W samodzielnym oknie edytora (bez wspólnej otoczki) Ctrl+Shift+S eksportuje
napisy, a w samodzielnym Szept — transkrypcję. We wspólnym programie ten
skrót zawsze oznacza **Zapisz sesję jako**. Standardowe kopiowanie,
wklejanie i zaznaczanie tekstu: Ctrl+C, Ctrl+V, Ctrl+A.
Tab i Shift+Tab przechodzą między kontrolkami, Enter zatwierdza typowy
formularz, a Alt udostępnia menu. W oknie pomocy Ctrl+F ustawia kursor
w polu wyszukiwania.

W kreatorach **Obraz + audio**, **Połącz filmy** i **Pokaz zdjęć i klipów**
**Ctrl+Enter** rozpoczyna tworzenie, a **Ctrl+.** anuluje bieżące zadanie.

## Wymagania i rozwiązywanie problemów

- Windows x64. Standardowy instalator i ZIP zawierają Python i biblioteki.
  Instalator Online wymaga osobnego Pythona 3.12 i internetu na pierwszy start.
- Do analizy i eksportu potrzebne są **FFmpeg i ffprobe**, dostępne w PATH
  albo folderze aplikacji. Instalator ich nie dołącza.
- Brak modelu: otwórz „Modele i słowniki”, pobierz model albo wskaż lokalny.
  Problemy z GPU: sprawdź sterowniki i wymagania CUDA lub użyj CPU.
- Nieudany eksport: sprawdź miejsce na dysku, uprawnienia do folderu,
  prawidłowe czasy napisów i dostępność plików źródłowych. Otwórz szczegóły
  błędu. Zapisz projekt przed zamknięciem programu.
- Film nie odtwarza się w podglądzie: obsługa kodeków Qt i FFmpeg może się
  różnić. Spróbuj standardowego MP4 H.264/AAC.
- Diagnostyka startu: `%LOCALAPPDATA%/SubtitleStudio/startup.log`.
  [Instalacja](INSTALATOR.md), [szczegółowa instrukcja](INSTRUKCJA.md),
  [integracja transkrypcji](INTEGRACJA_SZEPT.md), [obsługa Szept](SZEPT.md),
  [poprawki rozpoznawania i animacji](POPRAWKI_0.6.1.md),
  [zakres i ograniczenia](STATUS.md). Informacje o licencjach otwiera **Shift+F1**;
  pełny wykaz znajduje się w pliku `THIRD_PARTY.md` obok programu.

Materiały pozostają na komputerze podczas lokalnego przetwarzania.
Pobieranie modeli i słowników wymaga połączenia z ich źródłami. Plik
projektu i kolejka mogą zawierać prywatny tekst i ścieżki plików — udostępniaj
je świadomie. Nie publikuj nagrań ani projektów bez sprawdzenia ich treści.
