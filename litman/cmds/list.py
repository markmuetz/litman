"""List all items"""
ARGS = [(['--tag-filter', '-t'], {'help': 'tag to filter on', 'default': None}),
        (['--sort-on', '-s'], {'help': 'list to sort on (comma separated)', 'default': 'name'}),
        (['--level', '-l'], {'help': 'level to show', 'default': None, 'type': int}),
        (['--reverse', '-r'], {'help': 'reverse order', 'action': 'store_true'})]


def main(litman, args):
    sort_on = args.sort_on.split(',')
    litman.list_items(tag_filter=args.tag_filter, 
                      sort_on=sort_on, 
                      reverse=args.reverse,
                      level=args.level)
