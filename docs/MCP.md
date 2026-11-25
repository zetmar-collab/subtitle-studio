# Sterowanie Subtitle Studio przez AI (MCP)

Serwer stdio udostępnia 23 narzędzia do sterowania rzeczywistym oknem programu.
Agent może utworzyć film, dodać napisy, banery i logo, sprawdzić podgląd,
zapisać edytowalny projekt i wyeksportować gotowy film. Długie zadania zwracają
identyfikator; wynik jest gotowy dopiero po stanie `done` z `studio_get_job`.

## Podłączenie do otwartego programu

1. Otwórz **Narzędzia → Sterowanie AI · MCP** (`Ctrl+Shift+M`).
2. Kliknij **Wybierz folder i włącz**. Wskaż folder zawierający media i miejsce na wyniki.
3. Panel pokaże konfigurację JSON oraz polecenia dla Codex CLI i Claude Code.
   Skopiuj odpowiednie polecenie do terminala klienta AI. Konfiguracja klienta nie jest
   zmieniana przez Subtitle Studio.
4. Odśwież połączenia MCP klienta. Poproś agenta o `studio_get_state` i sprawdź zwrócony folder.

Konfiguracja `--connect` wskazuje konkretną instancję okna. Po ponownym uruchomieniu
połączenia skopiuj nowy identyfikator. **Wyłącz połączenie** odcina nowe polecenia;
rozpoczęte zadanie trwa dalej i można je anulować w panelu. Zamknięcie programu
wymaga zakończenia albo anulowania zadań. Rozpoznawanie przerywa się po bieżącym etapie.

## Stała konfiguracja uruchamiająca nowe okno

W paczce Windows użyj `SubtitleStudio-MCP.exe` obok `SubtitleStudio.exe`.
Dostosuj ścieżki programu oraz istniejącego folderu projektu:

```powershell
codex mcp add subtitle-studio -- "C:\Programy\SubtitleStudio\SubtitleStudio-MCP.exe" --root "C:\Filmy\Projekt"
claude mcp add --transport stdio subtitle-studio -- "C:\Programy\SubtitleStudio\SubtitleStudio-MCP.exe" --root "C:\Filmy\Projekt"
```

Dla innych klientów obsługujących stdio:

```json
{
  "mcpServers": {
    "subtitle-studio": {
      "command": "C:\\Programy\\SubtitleStudio\\SubtitleStudio-MCP.exe",
      "args": ["--root", "C:\\Filmy\\Projekt"]
    }
  }
}
```

Każde uruchomienie z `--root` tworzy nowe okno. Okno pozostaje otwarte po odłączeniu
klienta, aby można było obejrzeć i zapisać projekt. Przy pracy w jednym istniejącym
oknie używaj konfiguracji `--connect` z panelu.

Ze źródeł zastąp EXE lokalnym Pythonem i dodaj `main.py --mcp`:

```powershell
codex mcp add subtitle-studio -- "C:\Users\Marek\Codex\Subtitle\.venv\Scripts\python.exe" "C:\Users\Marek\Codex\Subtitle\main.py" --mcp --root "C:\Filmy\Projekt"
```

Zależności instaluje `python -m pip install --require-hashes -r requirements-lock.txt`.
Wymagane są FFmpeg i ffprobe zgodnie z główną instrukcją programu.

## Przykładowe polecenie dla AI

> Sprawdź stan Subtitle Studio i pliki w udostępnionym folderze. Utwórz nowy
> pięciosekundowy film 1280×720 z granatowym tłem. Poczekaj na zakończenie zadania.
> Dodaj baner „Witaj!” z fioletowym tłem u góry, o szerokości 60% i wysokości 20%.
> Dodaj napis „Mój pierwszy film” od 0 do 4000 ms. Zapisz podgląd PNG i sprawdź go.
> Zapisz projekt jako projekt.json, wyeksportuj gotowy.mp4 i sprawdź stan done.

`studio_set_banner(properties={...})` zwraca `banner_id`. Przekazanie tego ID
aktualizuje istniejący baner. `x` i `y` określają środek w procentach kadru;
`width` i `height` są niezależnymi wymiarami w procentach. Dostępne są tekst,
font, kolory, ramka, zaokrąglenie, krycie, wyrównanie i dopasowanie tekstu.
`start` i `end` są w milisekundach, zakres `[start,end)`.
`animation` (`none`, `fade`, `slide_up`, `slide_down`, `slide_left`, `slide_right`, `pop`)
i `animation_ms` ustawiają wejście i wyjście. `keyframes` to lista
`{ms, x, y, scale}` z rosnącym `ms` (`scale` w procentach 10–400) — także w
`studio_add_logo`. `template` z `studio_list_banner_templates` nadaje wygląd,
a jawne `properties` go nadpisują.

`studio_preview` zwraca opis JSON i obraz PNG do obejrzenia przez agenta
(`include_image=false` wyłącza obraz). `studio_export_video` i `studio_preview`
przyjmują `fit` (`fit` z pasami, `crop` z przycięciem) i `crop_x` 0–100, np.
pionowy 1080×1920 z poziomego filmu: `fit="crop"`.

## Narzędzia

| Cel | Narzędzia `studio_…` |
|---|---|
| Stan i materiały | `get_state`, `list_assets`, `list_fonts` |
| Projekt | `new_project`, `open_project`, `save_project`, `open_video` |
| Tworzenie filmu | `create_blank_video`, `create_video`, `join_videos`, `create_slideshow` |
| Napisy | `set_captions`, `import_captions`, `set_caption_style`, `transcribe`, `export_captions` |
| Grafika | `set_banner`, `list_banner_templates`, `remove_banner`, `add_logo`, `preview` |
| Wynik i postęp | `export_video`, `get_job`, `cancel_job` |

Parametry i opisy są dostępne przez listę narzędzi MCP. Eksport używa sekund;
napisy, banery i podgląd — milisekund. `track_index` liczy od zera.
Transkrypcja wymaga wcześniej pobranego lokalnego modelu Whisper w udostępnionym
folderze (`model_path`). Serwer korzysta z dostarczonych mediów albo jednolitego
tła z ciszą; nie generuje głosu, muzyki ani obrazów przez usługi zewnętrzne.

## Zakres dostępu

Połączenie działa przez lokalny kanał Qt z dostępem użytkownika systemowego,
bez portu TCP. Pliki wejściowe i wyniki muszą znajdować się w wybranym folderze;
ścieżki wychodzące poza niego, także przez dowiązania, są odrzucane.
Agent nie otrzymuje narzędzia do wykonywania poleceń powłoki.

Zmiany projektu można cofnąć w edytorze. Zastąpienie istniejącego wyniku wymaga
`overwrite=true`, a odrzucenie niezapisanego projektu — `discard_changes=true`.
Nie wolno nadpisać plików źródłowych projektu. Eksport MCP zwraca stan zadania;
plik można odtworzyć ręcznie. Podczas operacji AI nie edytuj równolegle tego
samego projektu ręcznie.

Panel **Sterowanie AI · MCP** prowadzi dziennik zmian i błędów AI (bez
odpytywania stanu) oraz udostępnia **Cofnij do stanu sprzed AI**. Polecenie
zmieniające projekt jest odrzucane, gdy poprzednie jeszcze czeka na FFmpeg.
Po zamknięciu klienta uruchomionego z `--root` okno pozostaje otwarte z projektem,
ale przestaje przyjmować polecenia.

Serwer korzysta z [oficjalnego Python SDK MCP](https://py.sdk.modelcontextprotocol.io/).
