"""Do a Microsoft Academic Graph search"""
import time
from logging import getLogger

from litman.litman import ItemNotFound, load_config
from litman.mag_client import MagClient

ARGS = [(['--list-item'], {'help': 'Item to perform search on'}),
        (['--all', '-a'], {'help': 'Search all items with bib', 'action': 'store_true'}),
        (['--title', '-t'], {'help': 'Perform search on title'})]


logger = getLogger('litman.magsearch')

def search_title(mag_client, title):
    time.sleep(1)
    try:
        print(title)
        entry_json, extended_attr_json = mag_client.title_search(title)
        print(entry_json['Ti'])
        print(extended_attr_json['DN'])
        print(extended_attr_json['DOI'])
        return entry_json, extended_attr_json
    except:
        logger.warn(f'Could not find entry for "{title}"')
        return None


def main(litman, args):
    litmanrc_fn, config = load_config()
    assert 'mag_key' in config
    mag_client = MagClient(config['mag_key'])

    if args.all:
        results = []
        items = litman.get_items(has_bib=True)
        for item in items:
            title = item.bib_entry.fields['title']
            results.append(search_title(mag_client, title))
        print(f'{len([r for r in results if r])}/{len(results)}')
        for res in results:
            if not res:
                continue
            print('https://doi.org/' + res[1]['DOI'])
    elif args.title:
        search_title(mag_client, args.title)
    else:
        for list_name in args.list_items:
            try:
                item = litman.get_item(list_name)
            except ItemNotFound:
                print('Could not find item')
                return

            assert item.has_bib
            # import ipdb; ipdb.set_trace()
            title = item.bib_entry.fields['title']
            search_title(mag_client, title)
