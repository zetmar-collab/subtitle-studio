"""Reusable banner looks: built-in templates plus user templates stored as JSON.

A template stores appearance and geometry only. Text, name, times, keyframes
and the identifier always come from the banner it is applied to.
"""
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from core.projects.model import Banner

STYLE_KEYS = ('x', 'y', 'width', 'height', 'font', 'font_size', 'bold', 'color', 'background',
              'border_color', 'border_width', 'radius', 'padding', 'opacity', 'align', 'auto_fit',
              'animation', 'animation_ms')
LIMIT = 100

BUILTIN = {
    'Pasek dolny / Lower third': dict(x=32, y=82, width=56, height=12, font_size=48, background='#d0101820',
                                      color='#ffffff', radius=8, padding=18, align='left',
                                      animation='slide_left', animation_ms=450),
    'Tytuł / Title': dict(x=50, y=45, width=80, height=22, font_size=110, background='#00000000',
                          color='#ffffff', border_width=0, radius=0, animation='fade', animation_ms=600),
    'Etykieta / Tag': dict(x=16, y=10, width=24, height=8, font_size=40, background='#ffcf3a',
                           color='#141414', radius=40, padding=10, animation='pop', animation_ms=300),
    'Ostrzeżenie / Alert': dict(x=50, y=14, width=70, height=12, font_size=56, background='#c62828',
                                color='#ffffff', border_color='#ffffff', border_width=4, radius=12,
                                animation='slide_down', animation_ms=350),
}


def default_path():
    from PySide6.QtCore import QStandardPaths
    folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    return folder / 'banner_templates.json'


def style_of(banner):
    data = asdict(banner)
    return {key: data[key] for key in STYLE_KEYS}


def check(style):
    """Validate a template by applying it to a default banner."""
    if not isinstance(style, dict) or set(style) - set(STYLE_KEYS):
        raise ValueError('Nieprawidłowy szablon baneru / Invalid banner template')
    return style_of(Banner(**dict(style_of(Banner()), **style)).validate())


def load_user(path=None):
    path = Path(path or default_path())
    try:
        if path.stat().st_size > 2_000_000:
            return {}
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    templates = {}
    if isinstance(data, dict):
        for name, style in list(data.items())[:LIMIT]:
            try:
                if isinstance(name, str) and 0 < len(name) <= 80 and name not in BUILTIN:
                    templates[name] = check(style)
            except (TypeError, ValueError):
                continue  # one damaged entry must not hide the others
    return templates


def all_templates(path=None):
    result = {name: check(style) for name, style in BUILTIN.items()}
    result.update(load_user(path))
    return result


def save_user(name, banner, path=None):
    name = name.strip() if isinstance(name, str) else ''
    if not name or len(name) > 80 or name in BUILTIN:
        raise ValueError('Podaj nową nazwę szablonu (do 80 znaków) / Enter a new template name (max 80)')
    path = Path(path or default_path())
    templates = load_user(path)
    if name not in templates and len(templates) >= LIMIT:
        raise ValueError(f'Limit {LIMIT} szablonów / Limit: {LIMIT} templates')
    templates[name] = style_of(banner.validate())
    write(templates, path)


def delete_user(name, path=None):
    path = Path(path or default_path())
    templates = load_user(path)
    if name not in templates:
        raise ValueError('Można usunąć tylko własny szablon / Only user templates can be deleted')
    del templates[name]
    write(templates, path)


def write(templates, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            json.dump(templates, file, ensure_ascii=False, indent=2)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def apply(banner, name, path=None):
    """Return a copy of banner with the named template's look applied."""
    templates = all_templates(path)
    if name not in templates:
        raise ValueError('Nieznany szablon baneru / Unknown banner template')
    return Banner(**dict(asdict(banner), **templates[name])).validate()
