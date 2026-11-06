import functools
import itertools
import json
import re
import unicodedata
from collections import OrderedDict
from pathlib import Path

from .dictionaries import language_code, load_dictionary
from .project import atomic_write

WORDS = re.compile(r"[^\W\d_]+(?:['’ʼ-][^\W\d_]+)*", re.UNICODE)
SKIP = re.compile(r"(?:https?://|www\.)\S+|[\w.+-]+@[\w.-]+\.\w+|\b[\w-]+\.(?:wav|mp3|flac|m4a|srt|vtt|json|txt|exe)\b", re.I)
JOINERS = "'’ʼ-"


def canonical(word):
    return unicodedata.normalize("NFC", word).replace("’", "'").replace("ʼ", "'")


def word_spans(text):
    """Python Unicode offsets, including decomposed accents and internal apostrophes."""
    skipped = iter(SKIP.finditer(text))
    skip = next(skipped, None)
    i = 0
    while i < len(text):
        while skip and i >= skip.end():
            skip = next(skipped, None)
        if skip and skip.start() <= i < skip.end():
            i = skip.end()
            continue
        if not unicodedata.category(text[i]).startswith("L"):
            i += 1
            continue
        start = i
        i += 1
        while i < len(text) and (unicodedata.category(text[i])[0] in "LMN" or text[i] in JOINERS + "_"):
            i += 1
        end = i
        while end > start and text[end - 1] in JOINERS:
            end -= 1
        word = text[start:end]
        if word and not any(c.isdigit() or c == "_" for c in word) and (start == 0 or not (text[start - 1].isdigit() or text[start - 1] == "_")):
            yield start, end, word


def spell_loop(root, commands, output):
    """Isolated worker with bounded dictionary/word caches and explicit failure states."""
    dictionaries = OrderedDict()
    while True:
        task = commands.get()
        if task is None:
            return
        token, operation, language, text = task
        try:
            if language not in dictionaries:
                d = load_dictionary(root, language)
                @functools.lru_cache(maxsize=50000)
                def lookup(word, dictionary=d):
                    value = canonical(word)
                    return bool(dictionary.lookup(value) or ("-" in value and all(dictionary.lookup(w) for w in value.split("-") if w)))
                dictionaries[language] = (d, lookup)
                if len(dictionaries) > 3:
                    dictionaries.popitem(last=False)
            dictionaries.move_to_end(language)
            d, lookup = dictionaries[language]
            if operation == "check":
                result = {word: lookup(word) for _, _, word in word_spans(text)}
                output.put((token, operation, language, result))
            else:
                suggestions = []
                for value in itertools.islice(d.suggest(canonical(text)), 6):
                    if value not in suggestions:
                        suggestions.append(value)
                        output.put((token, "suggest_partial", language, list(suggestions)))
                output.put((token, "suggest", language, suggestions))
        except Exception as error:
            kind = "missing" if isinstance(error, FileNotFoundError) else "invalid"
            output.put((token, operation + "_error", language, dict(kind=kind, detail=type(error).__name__)))


def user_words(root, language):
    try:
        language_code(language)
        data = json.loads((Path(root) / f"words-{language}.json").read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(isinstance(w, str) for w in data):
            return set()
        return {canonical(w).casefold() for w in data}
    except (OSError, ValueError, TypeError):
        return set()


def save_user_words(root, language, words):
    language_code(language)
    atomic_write(Path(root) / f"words-{language}.json", json.dumps(sorted({canonical(w.strip()).casefold() for w in words if w.strip()}), ensure_ascii=False))


def add_word(root, language, word):
    words = user_words(root, language)
    words.add(canonical(word).casefold())
    save_user_words(root, language, words)
