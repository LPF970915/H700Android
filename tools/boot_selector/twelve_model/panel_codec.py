"""Finite shared LCD-program codec, using event ranges rather than RAM buffers.

Sources are complete pinned traces. Copy tokens refer to an earlier program or
to a nonoverlapping earlier range of the same program. Decoding cannot cycle.
This module performs no image or hardware I/O.
"""
from collections import defaultdict


def encode(events, previous):
    events = tuple(events)
    programs = list(previous) + [events]
    own = len(previous)
    if own >= 16 or not (0 < len(events) <= 640):
        raise ValueError('LCD program count bound')
    index = defaultdict(list)
    for program, source in enumerate(programs):
        for offset, event in enumerate(source):
            index[event].append((program, offset))
    costs = [0] * (len(events) + 1)
    choices = {}
    for pos in range(len(events) - 1, -1, -1):
        kind, value = events[pos]
        if kind not in (1, 2, 3) or not 0 <= value <= 255:
            raise ValueError('LCD event bound')
        # 1=wait, 2=command without data, 3=standalone data.
        token = {1: 2, 2: 3, 3: 1}[kind]
        best = (2 + costs[pos + 1], 1, bytes((token, value)))
        if kind == 1:
            end = pos + 1
            while end < len(events) and events[end][0] == 2 and end - pos <= 123:
                size = end - pos
                candidate = (2 + size + costs[end + 1], size + 1,
                             bytes((3 + size, value))
                             + bytes(v for k, v in events[pos + 1:end + 1]))
                if candidate[0] < best[0]:
                    best = candidate
                end += 1
        for source_id, offset in index[events[pos]]:
            if source_id == own and offset >= pos:
                continue
            source = programs[source_id]
            size = 0
            while (size < 514 and pos + size < len(events)
                   and offset + size < len(source)
                   and (source_id < own or offset + size < pos)
                   and events[pos + size] == source[offset + size]):
                size += 1
            for count in range(3, size + 1):
                if 3 + costs[pos + count] < best[0]:
                    word = (source_id << 19) | (offset << 9) | (count - 3)
                    best = (3 + costs[pos + count], count,
                            (word | 0x800000).to_bytes(3, 'big'))
        costs[pos] = best[0]
        choices[pos] = best[1:]
    output = bytearray()
    pos = 0
    while pos < len(events):
        count, token = choices[pos]
        output.extend(token)
        pos += count
    assert len(output) == costs[0]
    return bytes(output)


def compile_programs(streams):
    remaining = sorted(set(tuple(rows) for rows in streams))
    originals, encoded = [], []
    while remaining:
        # Deterministic greedy dictionary order; no source names determine policy.
        output, rows = min(((encode(rows, originals), rows) for rows in remaining),
                           key=lambda item: (len(item[0]), item[1]))
        encoded.append(output)
        originals.append(rows)
        remaining.remove(rows)
    return originals, encoded


def decode(programs, counts, program, start=0, count=None, depth=0):
    if (not 0 <= program < len(programs) or depth > 16
            or not 0 <= start <= counts[program]):
        raise ValueError('LCD range bound')
    count = counts[program] - start if count is None else count
    if count < 0 or start + count > counts[program]:
        raise ValueError('LCD range count')
    raw, pos, cursor, output = programs[program], 0, 0, []
    while cursor < start + count:
        if pos >= len(raw):
            raise ValueError('Truncated LCD program')
        token = raw[pos]
        pos += 1
        if token & 128:
            if pos + 2 > len(raw):
                raise ValueError('Truncated LCD copy')
            word = ((token & 127) << 16) | (raw[pos] << 8) | raw[pos + 1]
            pos += 2
            source, offset, size = word >> 19, (word >> 9) & 1023, (word & 511) + 3
            if source > program or (source == program and offset + size > cursor):
                raise ValueError('Cyclic/forward LCD copy')
            block = decode(programs, counts, source, offset, size, depth + 1)
        elif token in (1, 2, 3):
            if pos >= len(raw):
                raise ValueError('Truncated LCD literal')
            block = [({1: 3, 2: 1, 3: 2}[token], raw[pos])]
            pos += 1
        elif 4 <= token <= 126:
            size = token - 3
            if pos + size + 1 > len(raw):
                raise ValueError('Truncated LCD command data')
            block = [(1, raw[pos])] + [(2, value) for value in raw[pos + 1:pos + size + 1]]
            pos += size + 1
        else:
            raise ValueError('Invalid LCD token')
        low, high = max(start - cursor, 0), min(len(block), start + count - cursor)
        output.extend(block[low:high])
        cursor += len(block)
    if len(output) != count:
        raise ValueError('LCD decoded range size')
    return output
