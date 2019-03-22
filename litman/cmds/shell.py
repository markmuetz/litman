"""Launches IPython shell"""
ARGS = [(['--failsafe'], {'action': 'store_true'})]


def main(litman, args):
    import IPython

    if not args.failsafe:
        # Load up useful modules
        import litman
        from litman import LitMan, LitItem, load_config, ItemNotFound
        from litman.experimental.mag_client import MagClient, HttpException, PaperNotFound
        
        print(80 * '=')
        _, conf = load_config()
        lm = LitMan(conf['litman_dir'])
        print('Created LitMan object: lm')

        if 'mag_key' in conf:
            mag_client = MagClient(conf['mag_key'])
            print('Created MagClient object: mag_client')
        print(80 * '=')
        print('')

    # IPython.start_ipython(argv=[])
    # This is better because it allows you to access e.g. args, config.
    IPython.embed()
