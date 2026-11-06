# Lokalna korekta AI przez Ollamę

Otwórz **Pisownia AI · Ollama** przyciskiem nad kartami albo w menu Narzędzia. Ta sama akcja jest dostępna z karty Transkrypcja. Klasyczne słowniki Hunspell nadal działają niezależnie.

1. Uruchom zainstalowaną Ollamę. Domyślny adres to `http://127.0.0.1:11434`. Aplikacja dopuszcza tylko lokalny adres `localhost`, `127.0.0.1` lub `::1`, nie używa proxy i nie wykonuje przekierowań HTTP.
2. Kliknij **Odśwież modele** i wybierz już pobrany model tekstowy. Modele zawierające `cloud` w nazwie, bez lokalnych plików lub zgłaszające zdalny backend są odrzucane. Modele embeddingowe nie służą do korekty. Program nie pobiera modeli i nie uruchamia instalacji Ollamy.
3. Wybierz ścieżkę filmu z listy albo transkrypcję Szept. Domyślnie sprawdzane są wszystkie napisy wybranego źródła; ograniczenie do zaznaczenia trzeba włączyć samodzielnie. Licznik i pole „Tekst do wysłania” pokazują zakres. Ponowne otwarcie okna wybiera bieżącą kartę; gdy aktywna ścieżka filmu jest pusta, wybierana jest pierwsza ścieżka z tekstem. Domyślny tryb obejmuje pisownię; opcjonalnie można włączyć gramatykę i interpunkcję.
4. Kliknij **Sprawdź lokalnie przez AI**. Tekst jest przetwarzany w osobnym procesie, w ograniczonych partiach. Komunikat pokazuje model i numery sprawdzanych napisów. Modele obsługujące reasoning domyślnie korzystają z „Dokładniejszej analizy modelu”; wyłączenie może przyspieszyć odpowiedź, ale na próbce Gemmy zmniejszyło liczbę wykrytych błędów. Możesz anulować zadanie. Pojedynczy segment może mieć do 3000 znaków; dłuższy trzeba podzielić. Limit czasu na partię można zmienić. Przekroczenie limitu długości odpowiedzi jest zgłaszane jako błąd, a nie jako brak poprawek.
5. Porównaj „Przed” i „Propozycja”. Pełny tekst wybranego wiersza widać pod tabelą. Propozycje są początkowo niezaznaczone. Zaznacz wybrane poprawki albo użyj „Zaznacz wszystko”, następnie kliknij **Zastosuj zaznaczone**.

Zastosowanie zmian zachowuje czasy segmentów i oryginalny tekst. Zmienione napisy tracą poprzednie czasy słów, ponieważ nie odpowiadają już nowej treści; są oznaczane do sprawdzenia. Zmiany można cofnąć. Jeśli podczas pracy AI zmieni się projekt, tekst lub czas wskazanych segmentów, aplikacja odmówi użycia nieaktualnych propozycji i poprosi o ponowne sprawdzenie.

## Modele i jakość

Na tym komputerze sprawdzono lokalny **Gemma4:e2b** na syntetycznym zdaniu: „Ktury kolor wybrać? To napewno dobry pomysł.” Model zaproponował „Który kolor wybrać? To na pewno dobry pomysł.” To próba działania integracji, nie benchmark jakości. Mały `llama3.2:3b` na tej samej próbce wprowadził również błędne zmiany. Dlatego poprawki wymagają przeglądu, a program nie deklaruje, że tekst bez propozycji AI jest bezbłędny. Przy pierwszym uruchomieniu model może potrzebować więcej czasu na załadowanie.

Jeśli nie zapisano preferencji i taki model jest dostępny, lista wskazuje `Gemma4:e2b`. Można wybrać inny lokalny model. Obsługa zależy od zdolności modelu do zwracania poprawnego JSON; niepoprawna odpowiedź jest odrzucana bez zmiany tekstu.

## Lokalność i dokumentacja API

Aplikacja wysyła tekst wyłącznie do zweryfikowanego lokalnego endpointu. Przed wysłaniem tekstu sprawdza pobrane modele i ich metadane. Nie używa klucza API ani mechanizmu pobierania modeli. Treść korekty nie jest zapisywana w dzienniku aplikacji; pliki prywatnego zadania w katalogu tymczasowym są sprzątane po zakończeniu/anulowaniu. Ollama jest osobnym, lokalnie zainstalowanym serwerem z własną konfiguracją.

Integracja używa [listy modeli](https://docs.ollama.com/api/tags) oraz [generowania odpowiedzi ze schematem JSON](https://docs.ollama.com/api/generate). Ollama obsługuje także chmurę, dlatego aplikacja filtruje takie modele. Użytkownik może dodatkowo wyłączyć funkcje chmurowe całego serwera zgodnie z [oficjalnym FAQ Ollamy](https://docs.ollama.com/faq); aplikacja nie zmienia globalnej konfiguracji serwera.
