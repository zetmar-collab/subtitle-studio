# Poprawki 0.6.1

## Transkrypcja z filmu

Otwórz film w karcie „Film i napisy”, wybierz lokalny model Whisper i język w karcie „Transkrypcja”, a następnie kliknij **Transkrybuj bieżący film**. Przycisk analizuje nagranie i uruchamia ASR. Jeśli film został już przeanalizowany, od razu rozpoczyna ASR. Ponowne rozpoznawanie istniejących napisów wymaga potwierdzenia ich zastąpienia.

W karcie „Transkrypcja” przycisk **Otwórz audio / film** pozwala też wybrać bezpośrednio MP4, MKV, MOV i inne obsługiwane pliki wideo. Po takim otwarciu kliknij „Transkrybuj”. Osobny WAV nie jest wymagany. Film musi mieć ścieżkę audio; używana jest pierwsza ścieżka audio, miksowana do mono. Program nie wykonuje OCR napisów wtopionych w obraz.

## Ollama

Otwórz **Pisownia AI · Ollama**. Wybierz lokalny model i źródło tekstu. Dla filmu można wybrać konkretną ścieżkę. Domyślny zakres to wszystkie napisy tego źródła; przed uruchomieniem widoczna jest liczba i podgląd tekstu. Opcja „Tylko zaznaczone segmenty” ogranicza zakres wyłącznie po jej włączeniu.

Podczas pracy widać nazwę modelu i zakres partii. Dokładniejsza analiza jest domyślnie włączona dla modeli, które ją obsługują; może wymagać więcej czasu. Zmiana tego ustawienia nie włącza chmury. Propozycje nadal wymagają zaznaczenia i zatwierdzenia. [Pełna instrukcja](OLLAMA.md).

## Dziewięć efektów napisów

Lista animacji ma czytelne nazwy polskie i angielskie. Efekty „Maszyna do pisania” oraz „Kolejne słowa” zachowują pozycję i pełny układ tekstu oraz tła, zamiast przeliczać je według aktualnie odsłoniętego fragmentu. Nie rozcinają znaków złożonych i emoji. Długie słowa zawijają się do szerokości napisu.

„Kolejne słowa” wykorzystują aktualne czasy słów ASR lub edytora „Słowa”. Bez takich czasów odsłaniają słowa równomiernie w ustawionym czasie animacji. „Aktywne słowo” utrzymuje podświetlenie poprzedniego słowa w przerwie do następnego; bez aktualnego wyrównania używa równego podziału długości segmentu. Przewinięcie zatrzymanego filmu od razu aktualizuje czas efektu. Ten sam renderer obsługuje podgląd i eksport.

## Zakres weryfikacji

Testy obejmują wywołanie przycisku transkrypcji filmu po rzeczywistej analizie audio, filtr wyboru wideo, pełną ścieżkę okno AI → osobny proces → lokalne HTTP → zastosowanie propozycji oraz ponowne otwarcie okna na obu kartach. Animacje sprawdzane są przez porównanie pikseli i eksport FFmpeg dla wszystkich dziewięciu efektów.

Na tym komputerze wykonano również próbę z filmem MP4 z syntetyczną polską mową, lokalnym Whisper tiny oraz lokalnym Gemma4:e2b. Nie jest to benchmark naturalnej mowy ani gwarancja wykrycia każdego błędu językowego.
