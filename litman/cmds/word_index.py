"""Build a word-frequency / inverted index across all extracted text"""
import os
import json

from litman.word_index import build_word_index

ARGS = [
    (['--min-count', '-m'], {'type': int, 'default': 3, 'help': 'Drop words rarer than this'}),
    (['--tag-filter', '-t'], {'default': None, 'help': 'Only items carrying this tag'}),
]


def main(litman, args):
    items = litman.get_items(args.tag_filter, has_extracted_text=True)
    print(f'Indexing {len(items)} items with extracted text...')
    index = build_word_index(items, min_count=args.min_count)

    json_fn = os.path.join(litman.litman_dir, 'word_index.json')
    txt_fn = os.path.join(litman.litman_dir, 'word_index.txt')

    with open(json_fn, 'w') as f:
        json.dump(index, f, indent=2)

    with open(txt_fn, 'w') as f:
        f.write('count\tdocs\tword\n')
        for w, d in sorted(index.items(), key=lambda kv: kv[1]['count'], reverse=True):
            f.write(f"{d['count']}\t{d['docs']}\t{w}\n")

    print(f'{len(index)} terms -> {json_fn}')
    print(f'              -> {txt_fn} (grep-friendly, sorted by frequency)')
