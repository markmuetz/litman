"""List all items"""
ARGS = [(['-t', '--tag-filter'], {'help': 'tag to filter on', 'default': None}),
        (['-s', '--sort-on'], {'help': 'list to sort on (comma separated)', 'default': 'name'}),
        (['-r', '--reverse'], {'help': 'reverse order', 'action': 'store_true'})]


def main(litman, args):
    sort_on = args.sort_on.split(',')
    litman.list_items(tag_filter=args.tag_filter, 
                      sort_on=sort_on, 
                      reverse=args.reverse)
