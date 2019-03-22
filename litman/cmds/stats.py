"""Get some stats on all files"""
ARGS = [(['--plot', '-p'], {'help': 'Plot years', 'action': 'store_true'}) ]


def main(litman, args):
    stats = litman.stats()
    for key, stat in stats.items():
        print(key)
        for entry in stat.most_common()[:40]:
            print(f'  {entry}')

    if args.plot:
        import pylab as plt
        year_items = sorted(stats['year'].items(), key=lambda x: x[0])

        num_papers = []
        years = range(year_items[0][0], year_items[-1][0])
        for year in years:
            if year in stats['year']:
                num_papers.append(stats['year'][year])
            else:
                num_papers.append(0)
        plt.plot(years, num_papers)
        plt.xlabel('years')
        plt.ylabel('# papers')
        plt.show()
