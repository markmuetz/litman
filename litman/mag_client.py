import re
import time
from logging import getLogger

import requests
import simplejson

from litman.common_words import COMMON_WORDS

logger = getLogger('litman.magsearch')


def _build_title_expr_str(title):
    # repleace punctuation with space
    title = re.sub(r'[^\w\s]', ' ', title )
    split_title = [s.strip() for s in title.lower().split(' ') if s != '']
    logger.debug(split_title)
    assert len(split_title) >= 1
    if len(split_title) == 1:
        return title
    else:
        split_title = list(set(split_title) - COMMON_WORDS)
        l_word = split_title[0]
        r_word = split_title[1]
        expr = f'And(W=%27{l_word}%27,W=%27{r_word}%27)'
        for r_word in split_title[2:]:
            expr = f'And({expr},W=%27{r_word}%27)'
        return expr


class MagClient:
    BASE_URL = 'https://api.labs.cognitive.microsoft.com/academic/v1.0'

    def __init__(self, key):
        self.key = key

    def _format_evalutate_url(self, expr, attributes):
        return f'{self.BASE_URL}/evaluate?expr={expr}&attributes={attributes}&count=1&subscription-key={self.key}'

    def _parse_response_text(self, resp_text):
        logger.debug(resp_text)
        resp_json = simplejson.loads(resp_text)
        num_entries = len(resp_json['entities'])
        if num_entries > 1:
            logger.warn('{num_entries} returned')
        elif num_entries == 0:
            raise Exception('No entries returned')

        entry_json = resp_json['entities'][0]
        extended_attr_json = simplejson.loads(entry_json['E'])
        return entry_json, extended_attr_json

    def evaluate(self, expr, attributes):
        req_url = self._format_evalutate_url(expr, attributes)
        logger.debug(req_url)
        resp = requests.get(req_url)
        # import ipdb; ipdb.set_trace()
        assert(resp.status_code == 200)
        entry_json, extended_attr_json = self._parse_response_text(resp.text)
        return entry_json, extended_attr_json

    def title_search(self, title):
        method = 'evaluate'
        expr = _build_title_expr_str(title)
        logger.debug(expr)
        attributes = ','.join(['Id', 'Ti', 'Y', 'E'])

        entry_json, extended_attr_json = self. evaluate(expr, attributes)
        logger.debug(entry_json['Ti'])
        return entry_json, extended_attr_json

    def get_citations(self, entry_ids):
        #for entry_id in extended_attr_json['PR']:
        for entry_id in entry_ids:
            expr = f'And(Id={entry_id})'
            request_url = format_url(method, expr, attributes)
            entry_json, extended_attr_json = parse_response_text(requests.get(request_url).text)
            logger.debug(entry_json['Ti'])
            time.sleep(1)
