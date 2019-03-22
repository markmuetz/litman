"""List all items"""
ARGS = [(['--tag-filter', '-t'], {'help': 'tag to filter on', 'default': None}),
        (['--has-filters'], {'help': 'has attr filter on (comma sep, e.g. <has>=True)', 'default': None}),
        (['--sort-on', '-s'], {'help': 'list to sort on (comma separated)', 'default': 'name'}),
        (['--reverse', '-r'], {'help': 'reverse order', 'action': 'store_true'})]


def main(litman, args):
    sort_on = args.sort_on.split(',')
    kwargs = {}
    if args.has_filters:
        for has_filter in args.has_filters.split(','):
            has_name, has_val = has_filter.split('=')
            kwargs[has_name] = has_val == 'True'
    litman.list_items(tag_filter=args.tag_filter, 
                      sort_on=sort_on, 
                      reverse=args.reverse,
                      **kwargs)
