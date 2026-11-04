from pathlib import Path
from spylls.hunspell import Dictionary

LANGUAGES = ('pl', 'en', 'de', 'fr', 'es', 'it', 'uk')


class Spellchecker:
    def __init__(self, folder, bundled=None):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.cache = {}
        self.bundled = Path(bundled) if bundled else self.folder
        self.user_path = self.folder/'user.txt'
        self.ignored = set(self.user_path.read_text(encoding='utf-8').splitlines()) if self.user_path.exists() else set()

    def dictionary(self, language):
        if language not in self.cache:
            base = self.folder/language
            if not base.with_suffix('.dic').exists():
                base = self.bundled/language
            if not base.with_suffix('.dic').exists() or not base.with_suffix('.aff').exists():
                raise ValueError(f'Brak słownika {language}. Dodaj {language}.dic i {language}.aff do {self.folder}')
            self.cache[language] = Dictionary.from_files(str(base))
        return self.cache[language]

    def check(self, word, language):
        return word in self.ignored or self.dictionary(language).lookup(word)

    def suggest(self, word, language):
        from itertools import islice
        return list(islice(self.dictionary(language).suggest(word), 8))

    def add(self, word):
        self.ignored.add(word)
        self.user_path.write_text('\n'.join(sorted(self.ignored)), encoding='utf-8')
