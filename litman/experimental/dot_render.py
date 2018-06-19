from collections import Counter

from graphviz import Digraph
from litman import LitMan
from litman.litman import load_config, ItemNotFound

dot = Digraph('papers')

_, conf = load_config()
lm = LitMan(conf['litman_dir'])

l0_mag_items = lm.get_items(has_mag=True, level=0)
lm1_mag_items = lm.get_items(has_mag=True, level=-1)

added_items = Counter()
       
for item in l0_mag_items:
    for ref_item_name in item.cites:
        try:
            ref_item = lm.get_item(ref_item_name)
        except ItemNotFound:
            continue
        if ref_item.level == 0:
            if item.name not in added_items:
                added_items[item.name] += 1
                dot.node(item.name, item.name)
            if ref_item.name not in added_items:
                added_items[ref_item.name] += 1
                dot.node(ref_item.name, ref_item.name)

            dot.edge(item.name, ref_item.name)
        
for lm1_item in lm1_mag_items:
    # import ipdb; ipdb.set_trace()
    l0_count = 0
    for item_name in lm1_item.cited_by:
        try:
            ref_item = lm.get_item(item_name)
        except ItemNotFound:
            continue
        if ref_item.level == 0:
            l0_count += 1

    if l0_count >= 20:
        for item_name in lm1_item.cited_by:
            try:
                ref_item = lm.get_item(item_name)
            except ItemNotFound:
                continue
            if ref_item.level == 0:
                if lm1_item.name not in added_items:
                    added_items[lm1_item.name] += 1
                    dot.node(lm1_item.name, lm1_item.get_authors()[0].lower() + str(lm1_item.year()) + lm1_item.title().split(' ')[0].lower())
                if ref_item.name not in added_items:
                    added_items[ref_item.name] += 1
                    dot.node(ref_item.name, ref_item.name)

                dot.edge(ref_item.name, lm1_item.name)
        
dot.render()
