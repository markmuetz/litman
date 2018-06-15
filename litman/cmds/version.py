"""Print version info"""
from litman.version import get_version

ARGS = [(['-l', '--long'], {'help': 'print long version',
                            'action': 'store_true'})]
RUN_OUTSIDE_SUITE = True


def main(suite, args):
    if args.long:
        print('Version ' + get_version('long'))
    else:
        print('Version ' + get_version())
