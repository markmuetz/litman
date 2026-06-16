"""Launches IPython shell"""
ARGS = [(['--failsafe'], {'action': 'store_true'})]


def main(litman, args):
    import IPython

    if not args.failsafe:
        # Load up useful modules
        import litman
        from litman import LitMan, LitItem, load_config, ItemNotFound

        print(80 * '=')
        _, conf = load_config()
        lm = LitMan(conf['litman_dir'])
        print('Created LitMan object: lm')
        print(80 * '=')
        print('')

    # IPython.start_ipython(argv=[])
    # This is better because it allows you to access e.g. args, config.
    IPython.embed()
