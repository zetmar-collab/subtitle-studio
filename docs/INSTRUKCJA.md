# Instrukcja użytkownika

## Film i napisy

1. Wybierz „Otwórz film” (Ctrl+O) albo przeciągnij plik na okno. Panel po lewej pokaże rozmiar, FPS, kodek i strumienie. Fala audio powstaje w tle. Odtwarzanie obsługuje Qt Multimedia; import i eksport sprawdza zewnętrzny FFmpeg. Dostępność nietypowych kodeków w podglądzie może się różnić od eksportu.
2. „Importuj napisy” (Ctrl+I) otwiera plik. Wybierz Auto lub konkretne kodowanie, np. cp1250. Kolejny import dodaje nową ścieżkę, jeżeli aktualna zawiera już segmenty. Zaznacz ścieżkę na liście po lewej, aby ją edytować.
3. Tabela przyjmuje `HH:MM:SS.mmm` lub liczbę milisekund. Tekst i język edytuje się bezpośrednio w komórkach. Języki słowników: `pl`, `en`, `de`, `fr`, `es`, `it`, `uk`.
4. TXT bez czasów ma ostrzeżenie „Brak czasów”. Zaznacz wiersz, ustaw pozycję odtwarzacza i użyj „Początek ◷” oraz „Koniec ◷” lub wpisz oba czasy. Program blokuje eksport segmentów bez poprawnych czasów.

## Synchronizacja i edycja

„Przesuń ms” zmienia zaznaczone segmenty; bez zaznaczenia zmienia całą aktywną ścieżkę. Wartość 500 oznacza pół sekundy później. Ujemne wyniki są blokowane. „Dwa punkty” przyjmuje cztery liczby w milisekundach: źródło A, źródło B, wynik A, wynik B. Ta operacja skaluje także odstępy i czasy słów.

„Podziel” działa w pozycji odtwarzacza wewnątrz zaznaczonego segmentu i dzieli tekst według środka listy słów. „Połącz” wymaga kilku sąsiadujących wierszy. Edycja treści lub granic unieważnia wcześniejsze czasy słów, aby nie pozostawić błędnego dopasowania. Ctrl+Z/Ctrl+Y cofa i ponawia operacje projektu. Zaznaczenie i pozycja odtwarzacza nie należą do historii.

Kliknięcie na osi czasu przewija film. Strzałki lewo/prawo przesuwają pozycję o przybliżony interwał klatki z nominalnego FPS; przy VFR nie jest to gwarancja przejścia do dokładnie sąsiedniej klatki. Spacja przełącza odtwarzanie poza edycją komórki, F11 przełącza pełny ekran. Suwak nuty zmienia głośność podglądu.

QC ustawia limity liczby znaków na sekundę, znaków w wierszu i minimalnego czasu wyświetlania. Tabela sygnalizuje także nieprawidłowe czasy, nakładanie segmentów i wyjście poza film. Ostrzeżenia o nakładaniu dotyczą aktywnej ścieżki; przy kilku ścieżkach sprawdź też wizualnie ich położenie.

## Styl i animacje

Zaznacz ścieżkę, wybierz jeden z ośmiu presetów i dostosuj czcionkę, rozmiar, obrys, kolory oraz animację. Rozmiar odnosi się do kadru o wysokości 1080 px i skaluje się z wysokością eksportu. Pozycja X/Y jest środkiem pola tekstowego w procentach kadru. Możesz przeciągać je w podglądzie lub wybrać jeden z dziewięciu punktów siatki. Własny preset można zapisać i odczytać jako JSON.

Efekty: static, fade, left, right, up, typewriter, words, highlight, pop. Typewriter i words korzystają z pola „Czas animacji”. Efekt „Aktywne słowo” domyślnie dzieli czas segmentu równo między widoczne słowa. To przybliżenie. Aby dopasować efekt do mowy, zaznacz wiersz i otwórz „Słowa”. Czasy początkowe w tabeli można skorygować w milisekundach filmu. Po zapisaniu tych ustawień ręczne czasy mają pierwszeństwo.

Kolory wybiera się wizualnie: kliknij próbkę przy „Kolor napisów”, „Kolor obrysu”, „Kolor tła” lub „Aktywne słowo”. Paleta pokazuje wybrany kolor, pozwala wskazać kolor z ekranu i ustawić kanał alfa. Szachownica próbki oznacza przezroczystość. Zatrzymaj film na aktywnym napisie, aby widzieć zmiany bezpośrednio na obrazie. Odtwarzanie zostaje wstrzymane na czas wyboru. OK zatwierdza zmianę jako jeden krok Cofnij, Anuluj przywraca poprzedni kolor. Kodu HEX nie trzeba wpisywać.

W projekcie/presetach kolor jest zapisywany jako `#RRGGBB` lub `#AARRGGBB`, np. `#b8000000` to półprzezroczysta czerń, `#00000000` to brak tła. Style źródłowe ASS/VTT/TTML są normalizowane do tekstu; aplikacja korzysta z własnego stylu ścieżki. Eksport SRT/VTT/ASS zapisuje treść i czasy, a wygląd aplikacji pozostaje w projekcie i wypalonym filmie.

## Logo

„Dodaj logo” (Ctrl+L) importuje obraz. PNG zachowuje alfa, GIF używa pierwszej klatki. Wybierz warstwę logo, przeciągnij ją w podglądzie lub ustaw X/Y. Rozmiar to szerokość obrazu jako procent szerokości filmu: **100% = pełna szerokość kadru**, niezależnie od liczby pikseli pliku logo. Proporcje logo są zachowane. Krycie 50% mnoży istniejący kanał alfa przez 0,5.

Początek i koniec logo podaje się w ms. Domyślnie logo jest widoczne przez cały film. Można dodawać wiele grafik, zmieniać kolejność i widoczność. Grafiki są nakładane po ścieżkach tekstowych; kolejność obu grup jest stała. Położenie środka blisko krawędzi może wyprowadzić część warstwy poza obraz — sprawdź podgląd.

## Pisownia offline

„Pisownia” ładuje lokalne słowniki Hunspell w tle i sprawdza zaznaczone wiersze lub całą aktywną ścieżkę. Wyświetla sugestie do indywidualnego zatwierdzenia. Można zignorować wyraz albo dodać go do własnego słownika. Pierwsze załadowanie dużego słownika może potrwać. Nie ma automatycznej korekty ani analizy gramatyki. Własne słowniki `pl.dic` i `pl.aff` itd. umieść w katalogu `dictionaries` danych aplikacji; mają pierwszeństwo przed dołączonymi.

## Projekty i odzyskiwanie

Ctrl+S zapisuje wersjonowany JSON, z relatywnymi ścieżkami do mediów, jeżeli to możliwe. Projekt nie zawiera samych filmów — przenoś je razem z nim. Brakujące wideo i grafiki można wskazać ponownie przy otwarciu. Co 30 sekund zmieniony projekt trafia do kopii awaryjnej w `%LOCALAPPDATA%/LocalTools/Subtitle Studio`. Po przerwaniu aplikacji następny start proponuje odzyskanie. Przy zwykłym zamknięciu pojawia się pytanie o niezapisane zmiany.

„Nowy projekt” (Ctrl+N) otwiera pusty projekt i pozostawia wybrany język oraz motyw. Jeśli są niezapisane zmiany, możesz je zapisać, odrzucić lub anulować operację.

## Eksport

Ctrl+E otwiera profile MP4 H.264/AAC, MP4 H.265/AAC, WebM VP9/Opus i MKV H.264/AAC. Wybierz rozdzielczość, FPS i CRF (niższy = wyższa jakość i większy plik). Zmiana proporcji dopasowuje obraz z czarnymi pasami; nie rozciąga go. Wybrany rozmiar eksportu jest następnie widoczny w podglądzie. Eksport konwertuje VFR do wybranego stałego FPS.

Możesz wyeksportować pierwsze 10 sekund. Postęp, ETA i przycisk anulowania są na dole. Projekt jest kopiowany na początku renderowania, więc dalsza edycja nie zmienia trwającego zadania. Wszystkie źródłowe ścieżki audio są jawnie mapowane i ponownie kodowane; brakujący koder zgłasza błąd. Nie ma eksportu z gwarancją braku strat.

Wynik powstaje w pliku tymczasowym obok docelowego. Dopiero po sprawdzeniu ffprobe zastępuje docelowy plik. Anulowanie usuwa plik tymczasowy i pozostawia poprzedni wynik. Przy awarii systemu może pozostać plik `.subtitle-*.mp4` lub analogiczny w folderze eksportu; można usunąć go po zakończeniu wszystkich zadań. Nie zamykaj aplikacji podczas renderowania — najpierw anuluj zadanie.

Gdy aplikacja nie uruchamia się, diagnostykę startu znajdziesz w `%LOCALAPPDATA%/SubtitleStudio/startup.log`. Log zapisuje typ wyjątku i miejsca w kodzie, bez treści segmentów i bez wartości zmiennych.
