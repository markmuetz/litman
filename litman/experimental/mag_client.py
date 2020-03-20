import re
import time
from logging import getLogger

import requests
import json

logger = getLogger('litman.magsearch')


class PaperNotFound(Exception):
    pass


class HttpException(Exception):
    pass


DEFAULT_ATTRS = ','.join(['Id', 'Ti', 'Y', 'RId', 'E'])


class OldLitman:
    def build_refs(self, level=None, create_items=True):
        mag_items = self.get_items(has_mag=True, level=level)
        mag_id_dict = dict([(item.mag_entry()['Id'], item) for item in mag_items])
        for item in mag_items:
            if 'RId' not in item.mag_entry():
                logger.warn(f'No RId for {item.name}')
                continue
            for ref_mag_id in set(item.mag_entry()['RId']):
                if ref_mag_id in mag_id_dict:
                    ref_item = mag_id_dict[ref_mag_id]
                    logger.info(f'{item.name} -> {ref_item.name}')
                else:
                    try:
                        ref_item = self.get_item(str(ref_mag_id))
                        logger.info(f'Item already exists {ref_mag_id}')
                    except:
                        if create_items:
                            logger.info(f'Creating ref for {ref_mag_id}')
                            ref_item = self.create_item(str(ref_mag_id), item.level - 1)
                        else:
                            ref_item = None
                    if ref_item:
                        ref_item.append_tag('mag_ref')

                item.add_cites(ref_mag_id)
                if ref_item:
                    ref_item.add_cited_by(item.name)

    def build_local_refs(self, level=None, create_items=True):
        mag_items = self.get_items(has_mag=True, level=level)
        mag_id_dict = {}
        for item in mag_items:
            mag_id = item.mag_entry()['Id']
            if mag_id in mag_id_dict:
                logger.warn(f'Duplicate entries for {item.name}')
            mag_id_dict[mag_id] = item

        for item in mag_items:
            if 'RId' not in item.mag_entry():
                logger.warn(f'No RId for {item.name}')
                continue
            for ref_mag_id in set(item.mag_entry()['RId']):
                if ref_mag_id in mag_id_dict:
                    ref_item = mag_id_dict[ref_mag_id]
                    logger.info(f'{item.name} -> {ref_item.name}')
                else:
                    try:
                        ref_item = self.get_item(str(ref_mag_id))
                        logger.info(f'Item already exists {ref_mag_id}')
                    except:
                        ref_item = None

                if ref_item:
                    item.local_cites.append(ref_item)
                    ref_item.local_cited_by.append(item)



class MagClient:
    BASE_URL = 'https://api.labs.cognitive.microsoft.com/academic/v1.0'

    def __init__(self, key):
        self.key = key
        self._session = requests.Session()

    def _format_evalutate_url(self, expr, attributes, count):
        if count:
            count_args = f'count={count}&'
        else:
            count_args = ''
        return f'{self.BASE_URL}/evaluate?expr={expr}&attributes={attributes}&{count_args}subscription-key={self.key}'

    def _format_interpret_url(self, query):
        return f'{self.BASE_URL}/interpret?query={query}&subscription-key={self.key}'

    def _parse_evaluate_response_text(self, resp_text):
        resp_json = json.loads(resp_text)
        return resp_json['entities']

    def _parse_interpret_response_text(self, resp_text):
        resp_json = json.loads(resp_text)
        return resp_json

    def _get_url(self, req_url, sleep=True):
        resp = self._session.get(req_url)
        if resp.status_code != 200:
            logger.error(resp.text)
            raise HttpException(resp.text)

        if sleep:
            time.sleep(1)
        return resp

    def evaluate(self, expr, attributes=DEFAULT_ATTRS, count=None):
        req_url = self._format_evalutate_url(expr, attributes, count)
        logger.debug(req_url)
        resp = self._get_url(req_url)
        entities = self._parse_evaluate_response_text(resp.text)
        logger.debug(f'{len(entities)} entities returned')
        return entities

    def interpret(self, query):
        req_url = self._format_interpret_url(query)
        logger.debug(req_url)
        resp = self._get_url(req_url)
        interpret_json = self._parse_interpret_response_text(resp.text)
        return interpret_json

    def get_single_entry(self, expr):
        entities = self.evaluate(expr, count=1)

        if len(entities) == 0:
            raise PaperNotFound('No entries returned')
        assert len(entities) == 1

        entry_json = entities[0]
        if 'E' in entry_json:
            extended_attr_json = json.loads(entry_json['E'])
            entry_json['E'] = extended_attr_json
        return entry_json

    def title_search(self, title):
        interpret_json = self.interpret(title)

        for interpretation in interpret_json['interpretations']:
            expr = interpretation['rules'][0]['output']['value']
            logger.debug(expr)

            try:
                entry_json = self.get_single_entry(expr)

                if 'Ti' in entry_json:
                    logger.debug(entry_json['Ti'])
                return entry_json

            except PaperNotFound:
                logger.warn(f'Could not find paper: "{title}"')
                raise
        else:
            # No interpretations.
            logger.warn(f'Could not build interpretations for: "{title}"')
            raise PaperNotFound('No interpretations')

    def find_cited_by(self, mag_id):
        expr = f'RId={mag_id}'
        entities = self.evaluate(expr, attributes=['Id'], count=100000)
        return entities

