"""Small C-ABI bridge to the Hunspell library shipped in the pinned Windows wheel."""
import codecs
import ctypes
import importlib.util
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

_library = None
_dll_directory = None


def native_folder():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "native" / "hunspell"
    spec = importlib.util.find_spec("enchant")
    if spec is None or not spec.submodule_search_locations:
        raise ImportError("Install the pinned pyenchant Windows wheel")
    return Path(next(iter(spec.submodule_search_locations))) / "data" / "mingw64" / "bin"


def library():
    global _library, _dll_directory
    if _library is not None:
        return _library
    folder = native_folder()
    _dll_directory = os.add_dll_directory(str(folder))
    lib = ctypes.CDLL(str(folder / "libhunspell-1.7-0.dll"))
    handle, char = ctypes.c_void_p, ctypes.c_char_p
    strings = ctypes.POINTER(char)
    declarations = {
        "Hunspell_create": ([char, char], handle), "Hunspell_destroy": ([handle], None),
        "Hunspell_get_dic_encoding": ([handle], char), "Hunspell_spell": ([handle, char], ctypes.c_int),
        "Hunspell_suggest": ([handle, ctypes.POINTER(strings), char], ctypes.c_int),
        "Hunspell_free_list": ([handle, ctypes.POINTER(strings), ctypes.c_int], None),
    }
    for name, (args, result) in declarations.items():
        function = getattr(lib, name)
        function.argtypes, function.restype = args, result
    _library = lib
    return lib


def ansi_path(path):
    absolute = str(Path(path).resolve())
    try:
        return absolute.encode("mbcs")
    except UnicodeEncodeError:
        api = ctypes.WinDLL("kernel32", use_last_error=True).GetShortPathNameW
        api.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        api.restype = ctypes.c_uint32
        buffer = ctypes.create_unicode_buffer(32768)
        if api(absolute, buffer, len(buffer)):
            return buffer.value.encode("mbcs")
        raise OSError("Hunspell cannot access this filename")


class NativeDictionary:
    def __init__(self, base):
        self.handle = None
        self.temporary = None
        base = Path(base)
        self.lib = library()
        aff = base.with_suffix(".aff").read_bytes().lstrip(b"\xef\xbb\xbf")
        match = re.search(rb"(?m)^SET\s+(\S+)", aff)
        if match is None:
            raise ValueError("Hunspell SET encoding is missing")
        with base.with_suffix(".dic").open("rb") as stream:
            line = stream.readline().lstrip(b"\xef\xbb\xbf").strip()
            self.entry_count = int(line.split()[0])
            if not any(line.strip() and not line.lstrip().startswith(b"#") for line in stream):
                raise ValueError("Dictionary has no word records")
        if self.entry_count < 1:
            raise ValueError("Dictionary has no entries")
        try:
            aff_path, dic_path = ansi_path(base.with_suffix(".aff")), ansi_path(base.with_suffix(".dic"))
        except (UnicodeEncodeError, OSError):
            # MinGW Hunspell uses ANSI filenames. Copy only public dictionary files
            # when a Unicode path has no accessible short-name representation.
            self.temporary = tempfile.TemporaryDirectory(prefix="szept-hunspell-")
            local = Path(self.temporary.name) / "dictionary"
            for suffix in (".aff", ".dic"):
                shutil.copyfile(base.with_suffix(suffix), local.with_suffix(suffix))
            aff_path, dic_path = ansi_path(local.with_suffix(".aff")), ansi_path(local.with_suffix(".dic"))
        self.handle = self.lib.Hunspell_create(aff_path, dic_path)
        if not self.handle:
            raise ValueError("Hunspell could not load the dictionary")
        encoding = self.lib.Hunspell_get_dic_encoding(self.handle)
        if not encoding:
            raise ValueError("Dictionary encoding is missing")
        self.encoding = encoding.decode("ascii").replace("microsoft-cp", "cp")
        codecs.lookup(self.encoding)

    def lookup(self, word):
        try:
            value = word.encode(self.encoding)
        except UnicodeEncodeError:
            return False
        return bool(self.lib.Hunspell_spell(self.handle, value))

    def suggest(self, word):
        try:
            value = word.encode(self.encoding)
        except UnicodeEncodeError:
            return []
        result = ctypes.POINTER(ctypes.c_char_p)()
        count = self.lib.Hunspell_suggest(self.handle, ctypes.byref(result), value)
        try:
            return [result[i].decode(self.encoding, "replace") for i in range(max(0, count))]
        finally:
            if result:
                self.lib.Hunspell_free_list(self.handle, ctypes.byref(result), count)

    def __del__(self):
        if self.handle:
            self.lib.Hunspell_destroy(self.handle)
            self.handle = None
        if self.temporary:
            self.temporary.cleanup()
