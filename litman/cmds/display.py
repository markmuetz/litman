from litman.litman import ItemNotFound

ARGS = [(['list_item'], {'nargs': 1, 'help': 'Show information about a list item'})]


def main(litman, args):
    try:
        item = litman.get_item(args.list_item[0])
    except:
        print('Could not find item')
        return
    print(f'Name: {item.name}')
    item.display()
