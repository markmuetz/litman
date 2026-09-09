import os

import litman.cmds as cmds
from litman.command_parser import parse_commands
from litman.setup_logging import setup_logger, add_file_logging
from litman.litman import LitMan, load_config

LITMAN_BASEDIR = '$HOME/LitMan/literature'

ARGS = [(['--DEBUG', '-D'], {'action': 'store_true', 'default': False}),
        (['--litman-dir', '-l'], {'help': f'LitMan directory (default: litman_dir from '
                                          f'$HOME/.litmanrc, else {LITMAN_BASEDIR})',
                                  'default': None})]


def main(argv):
    litman_cmds, args = parse_commands('litman', ARGS, cmds, argv[1:])
    cmd = litman_cmds[args.cmd_name]

    if args.DEBUG:
        debug = True
    else:
        debug = False

    logger = setup_logger(debug, colour=True)
    cmd_string = ' '.join(argv)
    litmanrc_fn, config = load_config()
    # Precedence: an explicit --litman-dir, then $HOME/.litmanrc, then the
    # built-in default. The config used to win unconditionally, which silently
    # ignored --litman-dir on any machine that had a .litmanrc.
    if args.litman_dir is not None:
        litman_dir = args.litman_dir
    elif config:
        litman_dir = config['litman_dir']
    else:
        litman_dir = LITMAN_BASEDIR
    # Expand whichever source won, so a .litmanrc shared between machines can say
    # $HOME/LitManData (or ~/LitManData) instead of a per-machine absolute path.
    litman_dir = os.path.expanduser(os.path.expandvars(litman_dir))

    if not os.path.exists(litman_dir):
        print(f'LitMan dir set to: {litman_dir}')
        print('You can change your LitMan dir by editing $HOME/.litmanrc')
        print('e.g.')
        print('')
        print('[LitMan]')
        print('litman_dir = /path/to/dir')
        print('')
        r = input(f'Create LitMan dir: {litman_dir}? (y/[n]): ')
        if r.lower() != 'y':
            logger.debug(f'user exiting')
            print('Exiting')
            return
        os.makedirs(litman_dir)

    add_file_logging(os.path.join(litman_dir, '.litman.log'))

    logger.debug(f'CMD: {cmd_string}')
    if litmanrc_fn and os.path.exists(litmanrc_fn):
        logger.debug(f'reading config {litmanrc_fn}')
    logger.debug(f'using litman_dir {litman_dir}')

    litman = LitMan(litman_dir)

    logger.debug(f'dispatching to {cmd}')
    return cmd.main(litman, args)
