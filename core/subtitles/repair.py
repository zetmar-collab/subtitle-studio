"""Non-destructive timing proposals; text is never shortened or removed."""
from copy import deepcopy


def propose(segments, duration, minimum=600):
    if type(duration) is not int or duration <= 0 or len(segments) > duration:
        raise ValueError('Brak miejsca na poprawne czasy / Not enough timeline space')
    result = deepcopy(segments)
    result.sort(key=lambda segment: segment.start)
    previous = 0
    for index, segment in enumerate(result):
        latest = duration - (len(result)-index-1)
        start = max(previous,min(max(0,segment.start),latest-1))
        desired = max(segment.end,start+max(1,minimum))
        if index+1 < len(result) and result[index+1].start > start:
            desired = min(desired,max(start+1,result[index+1].start))
        end = min(latest,max(start+1,desired))
        if (start,end) != (segment.start,segment.end):
            segment.words = []
            segment.review = True; segment.checked = False
        segment.start,segment.end,segment.timed = start,end,True
        previous = end
    return result
