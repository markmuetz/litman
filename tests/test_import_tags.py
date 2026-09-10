#!/usr/bin/env python3
"""Regression test: import_pdf must not leak subdirectory tags between files.

`import_pdf` derives a tag from each PDF's subdirectory under the import dir.
It used to build that list with `tags = <subdir parts> + tags`, rebinding the
*parameter* inside the per-file loop, so every file inherited the subdirectory
tags of every file imported before it.

Run: python3 tests/test_import_tags.py
"""
import os, shutil, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from litman.litman import LitMan


def _pdf(path):
    """A minimal one-page PDF -- enough for hashing, symlinking and pdftotext."""
    body = (b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 99 99]>>endobj\n"
            b"trailer<</Root 1 0 R/Size 4>>\n%%EOF\n")
    # vary the bytes so the files hash differently and are not treated as dupes
    with open(path, 'wb') as f:
        f.write(body.replace(b'99 99', b'99 99') + os.path.basename(path).encode())


def main():
    root = tempfile.mkdtemp(prefix='litman-test-')
    try:
        imp = os.path.join(root, 'inbox')
        for sub in ('alpha', 'beta', 'gamma'):
            os.makedirs(os.path.join(imp, sub))
            _pdf(os.path.join(imp, sub, f'paper_{sub}.pdf'))

        data = os.path.join(root, 'data')
        os.makedirs(os.path.join(data, 'literature'))
        lm = LitMan(data)
        lm.import_pdf(imp, tags=['shared'])

        failures = []
        for sub in ('alpha', 'beta', 'gamma'):
            item = lm.get_item(f'paper_{sub}')
            got = set(item.tags)
            want = {sub, 'shared'}
            if got != want:
                failures.append(f'  paper_{sub}: expected {sorted(want)}, got {sorted(got)}')
        if failures:
            print('FAIL: subdirectory tags leaked between files')
            print('\n'.join(failures))
            return 1
        print('PASS: each item carries only its own subdirectory tag, plus the shared tag')
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
