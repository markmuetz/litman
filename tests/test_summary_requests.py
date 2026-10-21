#!/usr/bin/env python3
"""Regression test: summary batch requests must leave room for thinking.

Haiku 5.5 thinks by default and thinking counts against max_tokens. The old
cap (800, set for Haiku 4.5) could be used up by thinking, truncating the JSON
summary. Requests must also carry an explicit effort, and keep the structured
output format alongside it in output_config.

Run: python3 tests/test_summary_requests.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from litman import ai


class FakeItem:
    def __init__(self, name, text):
        self.name, self._text = name, text

    def extracted_text(self):
        return self._text


def main():
    items = [FakeItem('a2020x', 'Some extracted text.'), FakeItem('empty', '  ')]
    requests, names = ai.build_summary_requests(items)
    assert names == ['a2020x'], names          # empty text is skipped
    params = requests[0]['params']
    assert params['model'] == ai.SUMMARY_MODEL
    assert params['max_tokens'] >= 4000, params['max_tokens']
    oc = params['output_config']
    assert oc['effort'] == ai.SUMMARY_EFFORT
    assert oc['format']['type'] == 'json_schema'
    assert 'temperature' not in params and 'thinking' not in params
    assert ai.THEMES_EFFORT in ('high', 'xhigh', 'max')
    assert ai.MAX_TEXT_CHARS >= 150000, ai.MAX_TEXT_CHARS  # long reviews fit
    print('ok')


if __name__ == '__main__':
    main()
