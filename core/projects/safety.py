"""Shared protection for all user-selected output paths."""
from pathlib import Path


def source_paths(project):
    paths = [project.video, *(logo.path for logo in project.logos),
             *(track.source for track in project.tracks)]
    transcript = getattr(project, 'transcript', None)
    if transcript:
        paths.append(transcript.get('source', ''))
    return [Path(path).resolve() for path in paths if path]


def protect_output(project, target, suffix=None):
    target = Path(target).resolve()
    if target in source_paths(project):
        raise ValueError('Plik docelowy jest źródłem projektu / Output is a project source.')
    if suffix and target.suffix.lower() != suffix:
        raise ValueError(f'Wymagane rozszerzenie / Required extension: {suffix}')
    return target
