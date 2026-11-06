"""Conservative byte accounting for retained undo/redo snapshots."""
import sys


def byte_size(value):
    pending, seen, total = [value], set(), 0
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item)); total += sys.getsizeof(item)
        if isinstance(item,dict):
            pending.extend(item.keys()); pending.extend(item.values())
        elif isinstance(item,(list,tuple)):
            pending.extend(item)
    return total


def trim(owner, budget=64*1024*1024):
    cache = getattr(owner,'_history_sizes',{})
    for state in owner.history + owner.future:
        if id(state) not in cache:
            cache[id(state)] = (state,byte_size(state))
    def retained():
        return sum(cache[id(state)][1] for state in owner.history+owner.future)
    while len(owner.history)>1 and (len(owner.history)>60 or retained()>budget):
        owner.history.pop(0)
    while len(owner.future)>1 and retained()>budget:
        owner.future.pop(0)
    ids={id(state) for state in owner.history+owner.future}
    owner._history_sizes={key:value for key,value in cache.items() if key in ids}
