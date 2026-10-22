#!/usr/bin/env python3
"""Regression test: finishing a summary batch must tolerate a concurrent run.

Two `litman summarize` runs at once share `.summarize_batch.json`: the second
resumes the first's batch, finishes it and removes the state, and the first
then crashed with FileNotFoundError at `os.remove`. Clearing the state must
also leave alone a newer batch's state written by another run.

Run: python3 tests/test_summarize_state.py
"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from litman.cmds.summarize import _clear_state


def main():
    with tempfile.TemporaryDirectory() as d:
        fn = os.path.join(d, '.summarize_batch.json')

        _clear_state(fn, 'batch_a')                 # already gone: no error

        with open(fn, 'w') as f:
            json.dump({'batch_id': 'batch_b', 'items': ['x2020y']}, f)
        _clear_state(fn, 'batch_a')                 # another run's batch: kept
        assert os.path.exists(fn)

        _clear_state(fn, 'batch_b')                 # our batch: removed
        assert not os.path.exists(fn)
    print('ok')


if __name__ == '__main__':
    main()
