#!/usr/bin/env python3
"""Test the embeddings indexes without the model: a fake embedder maps text to
a bag-of-words vector, so similarity is predictable.

Checks: incremental update (only new items embedded), stale rows dropped after a
rename, confidential items never indexed, reference lists stripped from
passages, quoted phrases required in hybrid search, and `similar`.

Run: python3 tests/test_embeddings.py   (needs numpy)
"""
import os, shutil, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import numpy as np
from litman.litman import LitMan
from litman import embeddings as E

VOCAB = ['cold', 'pool', 'squall', 'line', 'shear', 'radiation', 'cloud', 'ice', 'moisture', 'budget']


class Fake:
    calls = 0

    def embed_docs(self, texts):
        Fake.calls += len(texts)
        return E._unit([self._v(t) for t in texts])

    def embed_query(self, q):
        return E._unit([self._v(q)])[0]

    def _v(self, t):
        t = t.lower()
        v = np.array([t.count(w) for w in VOCAB] + [0.01] * (384 - len(VOCAB)), np.float32)
        return v


def _item(lit, name, summary, text, tags=''):
    d = os.path.join(lit, name)
    os.makedirs(d)
    open(os.path.join(d, 'ref.bib'), 'w').write(f'@article{{{name},\n    title = {{{name}}},\n    year = {{2020}}\n}}\n')
    open(os.path.join(d, 'summary.json'), 'w').write(f'{{"topic": "", "summary": "{summary}"}}')
    open(os.path.join(d, 'extracted_text.txt'), 'w').write(text)
    if tags:
        open(os.path.join(d, 'tags.txt'), 'w').write(tags)


def main():
    root = tempfile.mkdtemp(prefix='litman-test-')
    failures = []
    check = lambda ok, msg: ok or failures.append('  ' + msg)
    try:
        data = os.path.join(root, 'data')
        lit = os.path.join(data, 'literature')
        os.makedirs(lit)
        body = ' '.join(['cold pool squall line shear'] * 30)
        refs = '\nReferences\n' + ' '.join(['radiation cloud ice'] * 60)
        _item(lit, 'squall2020', 'cold pool squall line shear', body + refs)
        _item(lit, 'cirrus2020', 'radiation cloud ice', ' '.join(['radiation cloud ice'] * 60))
        _item(lit, 'budget2020', 'moisture budget squall line', ' '.join(['moisture budget of a squall line'] * 40))
        _item(lit, 'secret2026_draft', 'cold pool squall line', body, tags='confidential')
        E._embedder = Fake()
        lm = LitMan(data)

        E.update(lm, chunks_too=True, log=lambda *a: None)
        keys, _, _ = E.load(lm, 'summaries')
        check(sorted(keys) == ['budget2020', 'cirrus2020', 'squall2020'], f'summary keys {keys}')
        ckeys, _, texts = E.load(lm, 'chunks')
        check('secret2026_draft' not in ckeys, 'confidential item has passages')
        check(not any('radiation' in t for k, t in zip(ckeys, texts) if k == 'squall2020'),
              'reference list was not stripped from squall2020')

        n = Fake.calls
        E.update(lm, chunks_too=True, log=lambda *a: None)
        check(Fake.calls == n, f'second update re-embedded {Fake.calls - n} texts')

        os.rename(os.path.join(lit, 'cirrus2020'), os.path.join(lit, 'cirrus2020a'))
        os.rename(os.path.join(lit, 'cirrus2020a', 'ref.bib'), os.path.join(lit, 'cirrus2020a', 'ref.bib'))
        lm = LitMan(data)
        E.update(lm, chunks_too=True, log=lambda *a: None)
        keys, _, _ = E.load(lm, 'summaries')
        ckeys, _, _ = E.load(lm, 'chunks')
        check('cirrus2020' not in keys and 'cirrus2020a' in keys, f'rename not followed: {keys}')
        check('cirrus2020' not in ckeys, 'stale passages kept after rename')

        top = E.search_summaries(lm, 'cloud ice radiation', k=1)
        check(top and top[0][0] == 'cirrus2020a', f'search_summaries: {top}')
        sim = E.similar(lm, 'squall2020', k=1)
        check(sim and sim[0][0] == 'budget2020', f'similar: {sim}')
        hits = E.search_passages(lm, '"moisture budget" squall line', k=5)
        check(hits and all(k == 'budget2020' for k, _, _ in hits), f'quoted phrase not required: {hits}')

        if failures:
            print('FAIL: embeddings\n' + '\n'.join(failures))
            return 1
        print('PASS: incremental, rename-safe, confidential-safe embeddings; search and similar work')
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
