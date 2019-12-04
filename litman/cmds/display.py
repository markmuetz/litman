"""Dislpay a given litman item"""
from litman.litman import ItemNotFound

ARGS = [(['list_items'], {'nargs': '+', 'help': 'Display list item'})]


def main(litman, args):
    for item_name in args.list_items:
        try:
            item = litman.get_item(item_name)
        except ItemNotFound:
            print('Could not find item')
            continue
        print(f'Name: {item.name}')
        item.display()
