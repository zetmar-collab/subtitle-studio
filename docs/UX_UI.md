# Uproszczenie interfejsu desktopowego

Zmiany po recenzji UX/UI z 6 listopada 2026 r. dotyczą głównego okna,
edytora filmu, zintegrowanego rozpoznawania mowy i eksportu filmu.

- Ekran pustego projektu wyjaśnia cel i udostępnia przycisk otwarcia filmu.
- Panel „Krok po kroku” jest widoczny od początku; można go zamknąć i otworzyć
  ponownie przyciskiem u góry. Etapy reagują na dostępność filmu i napisów.
- Wspólna paleta obejmuje otoczkę aplikacji, obie karty, jasny i ciemny motyw.
- Język interfejsu jest wspólny. Nazwy w głównych paskach, stylach i animacjach
  są wyświetlane w wybranym języku.
- Podstawowy tekst ma 14 px; wybór 100%, 115% i 130% ustawia odpowiednio
  14, 16 i 18 px oraz zapisuje preferencję poza plikiem projektu.
- Edytor udostępnia podstawowe operacje bezpośrednio, pozostałe grupuje
  w menu „Synchronizacja”, „Sprawdzanie” i „Więcej”.
- Właściwości pokazują ustawienia zaznaczonego obiektu: napisów albo logo.
- Eksport domyślnie proponuje MP4, oryginalny rozmiar i prosty wybór jakości.
  Kodeki, FPS i CRF są dostępne po rozwinięciu ustawień zaawansowanych.
- Zapisany film można otworzyć lub wyświetlić jego folder. Błąd eksportu
  oferuje ponowienie; szczegóły techniczne są rozwijane osobno.
- Kontrolki odtwarzacza i formularzy mają opisowe nazwy dostępności.
  Zwiększono widoczność fokusu, pól wyboru i ostrzeżeń w obu motywach.
- Przy małym oknie lub powiększeniu treści pozostają dostępne przez
  przewijanie. Układ rozpoznawania mowy rozdziela edycję i wybór języka.

## Weryfikacja

`tests/test_ui_usability.py` sprawdza zachowanie tekstu i historii przy zmianie
języka, motywu i skali, kontekstowe właściwości, małe okno, eksport zakresu,
jakość, otwieranie wyniku oraz ponowienie po błędzie. Pozostałe testy GUI
obejmują zapis i odzyskiwanie sesji, edycję i rzeczywisty proces eksportu.

Zrzuty kontrolne w `output/ux/` powstają lokalnie i nie są wersjonowane.
Kontrola odbywała się przez renderowanie Qt w trybie offscreen; nie zastępuje
odsłuchu czytnika ekranu ani testu na fizycznym monitorze ze skalowaniem Windows.
Instalator i opublikowane wydania nie są automatycznie przebudowywane.
