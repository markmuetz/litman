"""Do a Microsoft Academic Graph search"""
from logging import getLogger

import json

from litman.litman import ItemNotFound, load_config, LitItem
from litman.experimental.mag_client import MagClient, HttpException, PaperNotFound

ARGS = [(['--item', '-i'], {'help': 'Item to perform search on'}),
        (['--force', '-f'], {'help': 'Force refresh', 'action': 'store_true'}),
        (['--show-all', '-s'], {'help': 'Show all info', 'action': 'store_true'}),
        (['--tag-filter', '-t'], {'help': 'tag to filter on', 'default': None}),
        (['--has-filters'], {'help': 'has attr filter on (comma sep, e.g. <has>=True)', 'default': None}),
        (['--mag-items-only', '-m'], {'help': 'only perform on mag_items', 'action': 'store_true'}),
        (['--title'], {'help': 'Perform search on title'})]


logger = getLogger('litman.mag_search')


def search_title(litman, item, mag_client, title, force):
    try:
        entry = mag_client.title_search(title)
        logger.info(entry['Ti'])

        if 'E' in entry and 'DOI' in entry['E']:
            logger.info(entry['E']['DOI'])
        else:
            logger.info('NO DOI')
        return title, entry
    except HttpException as e:
        logger.error(f'HTTP Exception "{e}"')
        raise
    except PaperNotFound:
        logger.warn(f'Could not find entry for "{title}"')
        return title, None


def search_id(litman, item, mag_client, force):
    try:
        if item and item.has_mag and not force:
            logger.info(f'Using existing for {item.name}')
            entry = item.mag_entry()
        else:
            entry = mag_client.get_single_entry(f'Id={item.name}')
            if item:
                item.add_mag_data(entry)

        return item.name, entry
    except HttpException as e:
        logger.error(f'HTTP Exception "{e}"')
        raise
    except PaperNotFound:
        logger.warn(f'Could not find entry for "{title}"')
        return title, None, None


def main(litman, args):
    litmanrc_fn, config = load_config()
    assert 'mag_key' in config
    mag_client = MagClient(config['mag_key'])

    if args.title:
        title, entry = search_title(litman, None, mag_client, args.title, args.force)
        if args.show_all:
            print(json.dumps(entry, indent=2))
    elif args.item:
        try:
            item = litman.get_item(args.item)
        except ItemNotFound:
            logger.info('Could not find item')
            return

        title = item.title()
        title, entry = search_title(litman, item, mag_client, title, args.force)
        if args.show_all:
            print(json.dumps(entry, indent=2))
    else:
        results = []

        if args.mag_items_only:
            items = litman.get_items(tag_filter='mag_ref')
            for i, item in enumerate(items):
                logger.info(f'Getting MAG data for {item.name}: {i + 1}/{len(items)}')
                title, entry = search_id(litman, item, mag_client, args.force)
                results.append((title, entry))

                if args.show_all:
                    print(json.dumps(entry, indent=2))
        else:
            kwargs = {}
            if args.has_filters:
                for has_filter in args.has_filters.split(','):
                    has_name, has_val = has_filter.split('=')
                    kwargs[has_name] = has_val == 'True'

            items = litman.get_items(tag_filter=args.tag_filter, **kwargs)
            for i, item in enumerate(items):
                if not item.title():
                    logger.info(f'No title for {item.name}')
                    results.append((None, None))
                    continue
                logger.info(f'Getting MAG data for {item.name}: {i + 1}/{len(items)}')
                title, entry = search_title(litman, item, mag_client, item.title(), args.force)
                results.append((title, entry))

                if args.show_all:
                    print(json.dumps(entry, indent=2))

        total = len(items)
        no_entry = 0
        no_doi = 0
        complete = 0
        for title, entry in results:
            if not entry:
                no_entry += 1
                logger.info(f'{title}: Not Found')
                continue
            elif 'DOI' not in entry['E']:
                no_doi += 1
                logger.info(f'{title}: No DOI')
            else:
                complete += 1
                logger.info(f'{title}: https://doi.org/{entry["E"]["DOI"]}')

        logger.info(f'complete: {complete}, {100 * complete/total} %')
        logger.info(f'no_doi: {no_doi}, {100 * no_doi/total} %')
        logger.info(f'no_entry: {no_entry}, {100 * no_entry/total} %')
        logger.info(f'total: {total}')
