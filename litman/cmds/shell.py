"""Launches IPython shell"""
ARGS = [(['--failsafe'], {'action': 'store_true'})]


def main(litman, args):
    import IPython

    if not args.failsafe:
        # Load up useful modules
        import litman
        from litman import LitMan
        from litman.litman import load_config, ItemNotFound
        
        _, conf = load_config()
        lm = LitMan(conf['litman_dir'])
        print('Made  LitMan object: lm')

    # IPython.start_ipython(argv=[])
    # This is better because it allows you to access e.g. args, config.
    IPython.embed()
