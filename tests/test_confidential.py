#!/usr/bin/env python3
"""Regression test: confidential items never reach an outside service.

An item tagged `confidential` (an unpublished draft) must be left out of
everything that sends titles, DOIs or text away: citation-graph lookups on
Semantic Scholar and OpenAlex, find-doi's Crossref search, summarize and
themes. citation-graph once sent draft titles to both services.

Run: python3 tests/test_confidential.py
"""
import json, os, shutil, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from litman.litman import LitMan
from litman.citations import scan_corpus


def _item(lit, name, tags):
    os.makedirs(os.path.join(lit, name))
    with open(os.path.join(lit, name, 'ref.bib'), 'w') as f:
        f.write(f'@article{{{name},\n    title = {{A title for {name}}},\n    year = {{2026}}\n}}\n')
    with open(os.path.join(lit, name, 'tags.txt'), 'w') as f:
        f.write(','.join(tags))


def main():
    root = tempfile.mkdtemp(prefix='litman-test-')
    try:
        data = os.path.join(root, 'data')
        lit = os.path.join(data, 'literature')
        os.makedirs(lit)
        _item(lit, 'open2026paper', ['ToRead'])
        _item(lit, 'secret2026paper_draft', ['coauthor_draft', 'confidential'])
        lm = LitMan(data)

        failures = []
        checks = {
            'get_items(shareable=True)': [i.name for i in lm.get_items(shareable=True)],
            'scan_corpus (citation-graph)': list(scan_corpus(lm)),
            'items_missing_doi (find-doi)': [i.name for i in lm.items_missing_doi()],
        }
        for what, names in checks.items():
            if 'secret2026paper_draft' in names or 'open2026paper' not in names:
                failures.append(f'  {what}: {sorted(names)}')
        if len(lm.get_items()) != 2:
            failures.append('  get_items() should still list every item')

        # a draft made confidential after an earlier lookup is pruned from the cache
        from litman import citations
        cache_fn = lm.data_path(citations.CACHE_BASENAME)
        with open(cache_fn, 'w') as f:
            json.dump({'unresolved': {'secret2026paper_draft': 'no title match'}}, f)
        citations.resolve_s2 = lambda papers, cache, save: None
        citations.resolve_openalex = lambda papers, cache, save, mailto=None: save()
        try:
            citations.build(lm)
        except Exception:
            pass   # an empty graph may not render; the cache is what matters here
        with open(cache_fn) as f:
            if 'secret2026paper_draft' in json.dumps(json.load(f)):
                failures.append('  citation cache still holds the confidential item')

        if failures:
            print('FAIL: a confidential item would be sent out')
            print('\n'.join(failures))
            return 1
        print('PASS: confidential items are left out of every outside lookup')
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
