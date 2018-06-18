from graphviz import Digraph
from litman import LitMan
from litman.litman import load_config

dot = Digraph('papers')

_, conf = load_config()
lm = LitMan(conf['litman_dir'])
mag_items = lm.get_items(has_mag=True)

for item in mag_items:
    if item.cites or item.cited_by:
       dot.node(item.name, item.name)
       
for item in mag_items:
    for ref_item in item.cites:
        dot.edge(item.name, ref_item)
        
dot.render()
