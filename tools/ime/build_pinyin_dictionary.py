"""Convert the pinned AOSP PinyinIME lexicon into ROC's compact offline table."""

import argparse
import gzip
import hashlib
from pathlib import Path
import re


SOURCE_SHA256 = '408700f28a56091fa07f3b849a0f134fbfc71e6b2ae9b3f52973a5b076f599ff'


def build(source, output):
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError('Expected the pinned AOSP 65,105-row PinyinIME dictionary')
    spellings = {}
    for line in data.decode('utf-16').splitlines():
        word, frequency, _, *syllables = line.split()
        spelling = ''.join(syllables)
        if not re.fullmatch('[a-z]+', spelling) or len(word) != len(syllables):
            raise ValueError('Invalid dictionary entry')
        words = spellings.setdefault(spelling, {})
        words[word] = max(words.get(word, 0), float(frequency))
    with output.open('xb') as writer:
        with gzip.GzipFile(filename='', fileobj=writer, mode='wb', mtime=0) as compressed:
            for spelling, words in sorted(spellings.items()):
                for word, frequency in sorted(words.items(), key=lambda entry: (-entry[1], entry[0])):
                    compressed.write(f'{spelling}\t{word}\t{frequency:.12g}\n'.encode('utf-8'))
    print(f'{sum(map(len, spellings.values()))} entries, {len(spellings)} spellings')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    options = parser.parse_args()
    build(options.source, options.output)
