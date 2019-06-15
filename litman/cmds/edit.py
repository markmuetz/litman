"""Edit a field for a given litman item"""
import subprocess as sp
from litman.litman import ItemNotFound

ARGS = [(['list_item'], {'nargs': 1, 'help': 'List item to edit'}),
        (['field'], {'nargs': 1, 'help': 'Field to edit'})]


def main(litman, args):
    try:
        item = litman.get_item(args.list_item[0])
    except:
        print('Could not find item')
        return

    allowed_fields = ['bib', 'notes', 'title', 'tags']

    assert args.field[0] in allowed_fields, f'field not in {allowed_fields}'

    field_fn = getattr(item, args.field[0] + '_fn')

    sp.call(f'vim {field_fn}'.split())
