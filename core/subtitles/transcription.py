"""Explicit conversion between the two project schemas (milliseconds / seconds)."""
import re
from core.projects.model import Segment, Track
from srtstudio.project import Project, Segment as SpeechSegment, issues


def normalized(text):
    return ' '.join(text.split())


def aligned_words(text, words, start, end, key):
    """Never attach old ASR alignment to edited text or rounded invalid times."""
    if not words or normalized(' '.join(w[key] for w in words)) != normalized(text):
        return []
    if any(len(w[key].split()) != 1 for w in words):
        return []
    if any(not start <= w['start'] < w['end'] <= end for w in words):
        return []
    if any(a['end'] > b['start'] for a, b in zip(words, words[1:])):
        return []
    return words


def to_track(project):
    # Validate untrusted/imported Szept projects with their existing schema reader.
    project = Project.loads(project.dumps())
    if not project.segments:
        raise ValueError('Brak napisów do przekazania / No subtitles to transfer.')
    result = []
    for index, speech in enumerate(project.segments):
        errors, _ = issues(project, index)
        if errors:
            raise ValueError(f'Segment {index + 1}: {", ".join(errors)}')
        start, end = round(speech.start * 1000), round(speech.end * 1000)
        words = [dict(text=w['word'].strip(), start=round(w['start'] * 1000),
                      end=round(w['end'] * 1000)) for w in speech.words]
        for converted, source in zip(words,speech.words):
            if 'probability' in source:
                converted['probability'] = source['probability']
        words = aligned_words(speech.text, words, start, end, 'text')
        language = speech.spell_language or project.language
        if language in ('auto', 'off'):
            language = project.language if project.language != 'auto' else 'pl'
        result.append(Segment(start, end, speech.text, language, words,
                              original=speech.original,review=speech.review,checked=speech.checked))
    return Track(name='Szept — transkrypcja', segments=result, source=project.source)


def to_transcript(track, source='', duration=0):
    if not track.segments:
        raise ValueError('Brak napisów do przekazania / No subtitles to transfer.')
    result = []
    for segment in track.segments:
        if not segment.timed or segment.start < 0 or segment.end <= segment.start or not segment.text.strip():
            raise ValueError('Popraw treść i czasy napisów / Correct subtitle text and timing.')
        words = [dict(word=w.get('text',segment.text.split()[i]), start=w['start'] / 1000,
                      end=w['end'] / 1000, **({'probability':w['probability']} if 'probability' in w else {}))
                 for i,w in enumerate(segment.words)]
        words = aligned_words(segment.text, words, segment.start / 1000, segment.end / 1000, 'word')
        language = segment.language.replace('-', '_')
        if not re.fullmatch(r'[a-z]{2,3}(?:_[A-Za-z0-9]{2,8}){0,2}', language):
            language = ''
        result.append(SpeechSegment(segment.start / 1000, segment.end / 1000,
                                    segment.text, segment.original or segment.text, words,
                                    segment.review or not bool(words), language,checked=segment.checked))
    language = result[0].spell_language.split('_')[0] if result[0].spell_language else 'pl'
    project = Project(source=source, duration=duration / 1000, language=language,
                      segments=result, original_text='\n'.join(s.original for s in result))
    return Project.loads(project.dumps())
