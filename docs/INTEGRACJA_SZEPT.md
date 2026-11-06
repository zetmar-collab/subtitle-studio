> Opis wersji 0.5.0. Wspólny zapis sesji i nowe funkcje wersji 0.6.0 opisano w [aktualnym przewodniku](NOWOSCI_0.6.md).

# Subtitle Studio + Szept 0.5.0

Jedno okno i jeden program zawierają edytor filmu oraz pełny moduł lokalnej
transkrypcji Szept z projektu `C:\Users\Marek\Codex\SRT`.
Oryginalny katalog SRT pozostaje samodzielnym projektem.

## Praca

1. W karcie **Film i napisy** otwórz film. Kliknij **Transkrybuj bieżący film**.
   Program sprawdzi jego ścieżkę audio i otworzy kartę **Transkrypcja**.
2. W **Modele i słowniki** wskaż istniejący model albo jawnie pobierz model.
   Modele i słowniki Szept w `%LOCALAPPDATA%/Szept` są współdzielone;
   program nie pobiera ich przy uruchomieniu.
3. Wybierz język, urządzenie CPU lub CUDA i **Transkrybuj**. Możesz też
   otworzyć niezależny plik audio w tej karcie, edytować tekst, podzielić
   segmenty, sprawdzić pisownię i eksportować TXT/SRT/VTT/JSON.
4. Kliknij **Transkrypcja → film**. Powstaje nowa ścieżka napisów bez
   nadpisywania istniejących warstw. Przeliczane są sekundy na milisekundy
   i czasy słów; można następnie wybrać efekt aktywnego słowa i eksport MP4.
5. **Napisy → transkrypcja** przekazuje aktywną ścieżkę do edycji tekstowej
   i sprawdzania pisowni. Zmiany wymagają jawnego ponownego przekazania.

Karty przechowują własne projekty i historię cofania. Projekt filmu zapisuje
warstwy i style, JSON Szept zachowuje oryginał rozpoznania, profil i metadane.
Przed zastąpieniem lub zamknięciem niezapisanych danych program proponuje zapis.
Przy zmianie karty odtwarzanie drugiej karty jest wstrzymywane.

## Dokładność synchronizacji

Adapter odrzuca puste napisy, błędne czasy i nakładające się segmenty Szept.
Przy innym nagraniu pyta o dodanie do aktualnego filmu. Czasy wychodzące poza
aktualny film trzeba poprawić przed przekazaniem.
Czasy słów są zachowywane tylko wtedy, gdy odpowiadają bieżącemu tekstowi,
mieszczą się w segmencie i pozostają poprawne po zaokrągleniu do ms.
Zmieniony tekst nie dostaje nieaktualnego wyrównania ASR.
Transkrypcja i jej synchronizacja wymagają sprawdzenia odsłuchem.

## Architektura i pochodzenie

- `ui/workspace.py`: jedno okno, dwie karty, przekazywanie danych i zamknięcie.
- `core/subtitles/transcription.py`: adapter schematów bez pośredniego SRT.
- `srtstudio/`: moduł Szept, oryginalnie GPL-3.0-or-later,
  https://github.com/zetmar-collab/Szept; zmieniono zakres skrótów,
  paletę okna, ścieżkę instrukcji i nazwę pliku odzyskiwania.
- Procesy ASR i pisowni używają `multiprocessing.spawn`; wspólny punkt
  wejścia obsługuje `freeze_support()` również w EXE.
- Odzyskiwanie transkrypcji: `Szept/subtitle-studio-recovery.json`,
  niezależnie od `Szept/recovery.json` samodzielnej aplikacji.

Połączone wydanie jest GPL-3.0-or-later (`LICENSE`), ponieważ zawiera Szept.
Pierwotny kod Subtitle Studio zachowuje informację MIT
(`docs/SUBTITLE_STUDIO_MIT.txt`). Zależności mają własne licencje.
Podstawą analizy był lokalny kod i dokumentacja obu projektów,
nie propozycje funkcji potraktowane jako wykonane implementacje.
