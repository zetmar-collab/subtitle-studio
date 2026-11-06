# Rozszerzenia inspirowane archiwum Concat

Przejrzano lokalne archiwum `Concat-main.zip`, w szczególności opis aplikacji, listę skrótów i dokument licencjonowania. Archiwum zawiera 1602 wpisy i około 47 MB danych po rozpakowaniu. Concat przedstawia rozbudowany edytor wielościeżkowy z napisami, efektami, klatkami kluczowymi i lokalnymi modelami AI.

Wersja Subtitle Studio 0.3.0 dodaje poniższe funkcje we własnym kodzie Python/Qt i przez istniejące narzędzia FFmpeg.

| Funkcja w Concat | Realizacja w Subtitle Studio |
|---|---|
| Przycinanie i przesuwanie klipów na osi | Przesuwanie napisów oraz zmiana ich początku/końca myszką. Każde przeciągnięcie jest jednym krokiem Cofnij. |
| Przyciąganie i zoom | Przyciąganie do kursora, sąsiednich napisów i krawędzi filmu, powiększenie do 3200%, przewijanie poziome. |
| Duplikowanie i ripple delete | Ctrl+D duplikuje zaznaczone napisy z czasami słów. Shift+Delete usuwa wybrane przedziały z aktywnej ścieżki napisów i przesuwa późniejsze napisy. |
| Nawigacja po cięciach | Ctrl+lewo/prawo przechodzi do poprzedniego/następnego początku lub końca widocznego napisu, Home/End do granic filmu. |
| Praca nad fragmentem | Zakres I–O z zapętleniem odtwarzania i eksportem samego fragmentu. Czasy napisów i logo są odnoszone do oryginalnego filmu. |
| Łączenie materiałów | Osobne okno z kolejką 2–40 filmów, zmianą kolejności, normalizacją obrazu/FPS i eksportem połączonego MP4. |

## Obsługa osi czasu

Kliknij blok napisu, aby zaznaczyć wiersz w tabeli i ustawić pozycję odtwarzacza. Przeciągnij środek bloku, aby przesunąć go w czasie. Przeciągnij lewą/prawą krawędź, aby zmienić granice. Opcja „Przyciągaj” pomaga wyrównać czas do sąsiedniego segmentu lub kursora. Przesuwanie zachowuje czasy słów. Zmiana granic czyści je i włącza domyślne przybliżenie efektu aktywnego słowa.

Powiększenie osi zmieniają przyciski −/+, Ctrl+rolka oraz Ctrl+=/Ctrl+−. Przycisk „Dopasuj oś” pokazuje cały film. Powiększoną oś przewija dolny pasek. Zielony pasek nad falą audio przedstawia zakres I–O. Skróty I i O ustawiają jego granice na pozycji odtwarzania. Włączenie „Pętla zakresu” pozwala wielokrotnie odsłuchać fragment. W oknie eksportu zaznacz „Eksportuj zakres I–O”, aby zapisać ten fragment do filmu.

Ctrl+D kopiuje zaznaczone segmenty za koniec zaznaczonej grupy. Wynik musi mieścić się w długości filmu. Shift+Delete domyka czas usuniętych napisów w aktywnej ścieżce. Ta operacja dotyczy synchronizacji tekstu. Obraz i dźwięk źródłowego filmu mają własną ciągłą oś czasu. Przy nakładaniu innego napisu na usuwany przedział aplikacja prosi o zwykłe usunięcie lub rozdzielenie segmentów.

## Łączenie filmów

„Połącz filmy” (Ctrl+J) otwiera kolejkę. Dodaj pliki, ustaw kolejność, wybierz rozmiar i FPS, a następnie „Połącz i zapisz MP4”. Wszystkie filmy są dopasowywane z zachowaniem proporcji i pasami. Każdy plik wnosi pierwszą ścieżkę audio. Film bez audio otrzymuje ciszę. Wyjście ma H.264/AAC stereo 48 kHz. Łączenie wymaga ponownego kodowania i miejsca na pliki tymczasowe w folderze wyniku.

Postęp jest widoczny w oknie łączenia. „Anuluj zadanie” usuwa pliki tymczasowe i zachowuje poprzedni plik docelowy. Po zakończeniu można otworzyć wynik w edytorze i dodać do niego napisy/logo. Aplikacja pyta wtedy o zapis bieżącego projektu.

Concat ma także narzędzia AI, automatyczne maski, animacje klatek kluczowych, filtry GPU i wiele osi montażowych. Opisana aktualizacja koncentruje się na funkcjach wyszczególnionych w tabeli.

## Testy

Testy obejmują przeciąganie granicy z przyciąganiem i cofnięcie, zachowanie czasów słów przy duplikowaniu i domykaniu, zapis zakresu w projekcie, eksport fragmentu z audio i właściwymi czasami warstw, łączenie filmów o różnych proporcjach, dodanie ciszy, zachowanie kolejności i anulowanie. Test okna łączenia uruchamia rzeczywisty proces roboczy i sprawdza wynik FFmpeg.
