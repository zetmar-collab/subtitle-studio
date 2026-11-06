# 0.7.0 — 2026-11-06

- Ekran startowy i widoczny przewodnik „Krok po kroku” z dostępnością etapów zależną od stanu projektu.
- Wspólny jasny i ciemny motyw obu kart, spójny język i rozmiar interfejsu 100%, 115% oraz 130%.
- Uporządkowane narzędzia synchronizacji i sprawdzania oraz kontekstowe właściwości napisów i logo.
- Prosty eksport MP4 z wyborem jakości; kodeki, FPS i CRF w ustawieniach zaawansowanych.
- Otwieranie gotowego filmu i folderu, ponawianie eksportu po błędzie oraz osobne szczegóły diagnostyczne.
- Czytelniejsze pola wyboru, fokus, etykiety dostępności i ostrzeżenia; obsługa małego okna przez przewijanie.
- Poprawione zwalnianie okien Qt przy zamykaniu i testy regresji interfejsu.

# 0.6.1

- Usunięto wyścig przy anulowaniu eksportu na Windows: procesy i potoki są zamykane przed sprzątaniem, z krótkim ponowieniem blokady pliku tymczasowego.
- Przycisk transkrypcji bieżącego filmu uruchamia ASR po analizie jego audio; wybór pliku w Szept obejmuje audio i wideo.
- Ollama sprawdza domyślnie wszystkie napisy. Dodano wybór ścieżki, podgląd tekstu i licznik wysyłanego zakresu; ponowne otwarcie wybiera aktualną kartę.
- Widoczny etap pracy modelu i opcjonalna dokładniejsza analiza dla modeli z reasoningiem; jawny komunikat o przekroczeniu limitu odpowiedzi.
- Stały układ tekstu i tła animacji liter/słów, czasy ASR dla kolejnych słów, stabilne podświetlenie w przerwach, walidacja aktualności słów, pełne znaki złożone oraz łamanie długich słów.
- Natychmiastowe odświeżenie efektu po przewinięciu zatrzymanego filmu. Czytelne nazwy dziewięciu efektów.

# 0.6.0

- Naprawiono A1–A9 z audytu: ochrona źródeł, odzyskiwanie sesji, reset mediów, spóźnione wyniki, walidacja projektu/presetów, wspólne narzędzia, długość audio i podział napisów.
- Wspólny projekt JSON v2 obu kart z odczytem v1 oraz aktualizacja powiązanej ścieżki bez utraty stylu.
- Dodano panel procesu filmu, propozycje naprawy synchronizacji, edycję słów na fali i przegląd fragmentów ASR.
- Dodano wznawialną kolejkę wariantów eksportu oraz pokaz zdjęć i klipów z audio, przybliżeniem i przejściami przez czerń.
- Dodano korektę AI przez lokalną Ollamę: wybór pobranego modelu, partie tekstu, anulowanie, podgląd i zastosowanie wybranych propozycji z undo.
- Szybsza kontrola jakości, limity pamięci, niezależne anulowanie renderera i rollback startu workera.
- Lockfile produkcyjny z hashami oraz definicja testów/audytu zależności CI.

# 0.5.0

- Połączono Subtitle Studio i Szept w jednym oknie z dwiema kartami.
- Dodano lokalną transkrypcję, edycję tekstu, słowniki oraz przekazywanie filmu i napisów bez pośrednich plików SRT.
- Adapter zachowuje aktualne czasy słów, przelicza sekundy na ms i odrzuca niepoprawną synchronizację.
- Wspólny EXE obsługuje procesy ASR i pisowni; oddzielono odzyskiwanie od samodzielnego Szept.
- Połączone wydanie na GPL-3.0-or-later z zachowaniem oryginalnego zawiadomienia MIT.

# Changelog

## 0.4.0 — 2026-11-04

Dodano tworzenie MP4 ze zdjęcia lub klipu oraz osobnego audio. Kreator ma podgląd kadru, proporcje 16:9/9:16/1:1/4:5/4:3, własne wymiary, dopasowanie z pasami lub przycięcie, FPS i CRF. Film można powtarzać, zatrzymać na ostatniej klatce albo zakończyć na krótszym pliku. Wspólny proces roboczy obsługuje postęp, anulowanie i ochronę oryginałów.

## 0.3.0 — 2026-11-04

Dodano zoom, przewijanie i edycję napisów myszką na osi, przyciąganie granic, duplikowanie i domykanie czasu napisów. Zakres I–O można zapętlać i eksportować z poprawnymi czasami warstw. Nowe okno łączy filmy o różnych rozmiarach/FPS i z różną dostępnością audio do MP4. Funkcje opracowano po przeglądzie archiwum Concat.

## 0.2.1 — 2026-11-04

Dodano „Nowy projekt” z ochroną niezapisanych zmian. „Aktywne słowo” działa na zwykłych napisach i korzysta z ręcznych czasów, jeśli je zapisano. „Maszyna do pisania” i „słowo po słowie” respektują czas animacji, a zanikanie osiąga pełne krycie także w krótkich segmentach.

## 0.2.0 — 2026-11-03

Wizualny wybór kolorów napisów, obrysu, tła i aktywnego słowa, z podglądem na filmie, alfa, obsługą anulowania i undo. Wypełnienie liter jest rysowane po obrysie dla czytelności. Dodano własną ikonę do okna, EXE i instalatora oraz raport analizy z priorytetami dalszych zmian.

## 0.1.0 — 2026-10-31

Pierwsza lokalna implementacja edytora, synchronizacji, animacji, logo, projektów i eksportu. Zakres niepełny względem dokumentu źródłowego, szczegóły w docs/STATUS.md. Brak podpisanego instalatora i testu w czystej maszynie Windows.
