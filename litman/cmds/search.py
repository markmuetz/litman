import re

from litman.setup_logging import bcolors


ARGS = [(['search_str'], {'nargs': 1, 'help': 'Term to search for'}),
        (['--ignore-case', '-i'], {'help': 'Ignore case when searching', 'action': 'store_true'}),
        (['--num-matches-only', '-n'], {'help': 'Only show number of matches', 'action':'store_true'}),
        (['--context', '-c'], {'help': 'Amount of context chars to include', 'type':int, 'default': 30})]


def main(litman, args):
    all_matches = litman.search(args.search_str[0], args.ignore_case)
    for item, matches in all_matches:
        if args.num_matches_only:
            print(f'{item.name}:{len(matches)}')
            continue

        for match in matches:
            span = match.span()
            start_index = max(span[0] - args.context, 0)
            end_index = min(span[1] + args.context, len(item.extracted_text))
            match_with_context = item.extracted_text[start_index:end_index]
            if args.ignore_case:
                flags =  re.IGNORECASE
            else:
                flags = 0
            match = re.search(args.search_str[0], match_with_context, flags=flags).group()
            colour_sub = bcolors.BOLD + bcolors.OKBLUE + match + bcolors.ENDC
            print(item.name + ':', end='')
            print(re.sub(args.search_str[0], colour_sub, match_with_context.replace('\n', ''), flags=flags))
