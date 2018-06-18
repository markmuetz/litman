"""Find all articles that are cited by and item or items"""
from logging import getLogger

import simplejson

from litman.litman import ItemNotFound, load_config, LitItem
from litman.mag_client import MagClient, HttpException, PaperNotFound

ARGS = [(['--item', '-i'], {'help': 'Item to perform search on'}),
        (['--tag-filter', '-t'], {'help': 'tag to filter on', 'default': None}),
        (['--level', '-l'], {'help': 'level to show', 'default': None, 'type': int}),
        (['--create-items', '-c'], {'help': 'tag to filter on', 'action': 'store_true'})]

logger = getLogger('litman.mag_search')


def _find_cited_by(litman, mag_client, item, create_items):
    logger.info(f'Finding forward entries (cited-by) for {item.name}')
    entities = mag_client.find_cited_by(item.mag_entry()['Id'])
    for entity in entities:
        mag_id = entity['Id']
        try:
            fwd_item = litman.get_item(str(mag_id))
            logger.info(f'Found existing {fwd_item}: {fwd_item.title()}')
        except ItemNotFound:
            entry = mag_client.get_single_entry(f'Id={mag_id}')
            if create_items:
                logger.info(f'Creating item for {mag_id}')
                fwd_item = litman.create_item(litman, str(mag_id), level=item.level + 1)
                fwd_item.add_mag_data(entry)


def main(litman, args):
    litmanrc_fn, config = load_config()
    assert 'mag_key' in config
    mag_client = MagClient(config['mag_key'])

    if args.item:
        try:
            item = litman.get_item(args.item)
        except ItemNotFound:
            logger.info('Could not find item')
            return

        assert item.has_mag

        _find_cited_by(litman, mag_client, item, args.create_items)
    else:
        items = litman.get_items(has_mag=True, level=args.level)
        for item in items:
            _find_cited_by(litman, mag_client, item, args.create_items)

    litman.build_refs(level=args.level + 1, create_items=False)
