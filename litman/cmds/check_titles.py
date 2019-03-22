"""Check all titles, and let user modify them"""
import re
from logging import getLogger

logger = getLogger('litman.cmds')

ARGS = [(['--tag-filter', '-t'], {'help': 'tag to filter on', 'default': None})]


def enter_title(item):
    r = input('Enter title: ')
    logger.info(f'Set title to {r}')
    item.set_title(r)

def main(litman, args):
    items = litman.get_items(tag_filter=args.tag_filter)

    for item in items:
        if item.title():
            logger.debug(f'{item.name} has title: {item.title()}')
            continue
        print(f'==============================================')
        print(f'= Check title for {item.name}:')
        print(f'==============================================')
        print(f'')

        if item.has_extracted_text:
            print('---------------')
            print('- pdf text    -')
            print('---------------')
            print('\n'.join(item.extracted_text().split('\n')[:20]))
            print('---------------')

        r = input('Can see title? (y/[n]): ')
        if r == 'y':
            enter_title(item)
            continue

        item.display()
        r = input('Can see title now? (y/[n]): ')
        if r == 'y':
            enter_title(item)
            continue

        print('Do a search:')
        match = re.match('(?P<auth>\D*)(?P<year>\d*)(?P<first_word>\D*)', item.name)
        if match:
            auth, year, first_word = match.groups()
            print(f'https://scholar.google.co.uk/scholar?q={auth}+{year}+{first_word}')
            print(f'https://academic.microsoft.com/?q={auth} {year} {first_word}')
        else:
            print('https://scholar.google.co.uk/scholar')
            print('https://academic.microsoft.com/')
        r = input('Can see title now? (y/[n]): ')
        if r == 'y':
            enter_title(item)
            continue

        print('No title entered')
