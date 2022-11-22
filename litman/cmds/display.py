"""Dislpay a given litman item"""
from litman.litman import ItemNotFound

ARGS = [(['list_items'], {'nargs': '+', 'help': 'Display list item'})]


def main(litman, args):
    for item_name in args.list_items:
        try:
            item = litman.get_item(item_name, allow_partial=True)
        except ItemNotFound as e:
            print(f'Could not find item: {e}')
            continue
        print(f'Name: {item.name}')
        item.display()
