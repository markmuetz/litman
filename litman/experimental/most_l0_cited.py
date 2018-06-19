from litman import LitMan
from litman.litman import load_config, ItemNotFound

_, conf = load_config()
lm = LitMan(conf['litman_dir'])
lm1_mag_items = lm.get_items(has_mag=True, level=-1)
print(sorted([(len([ii for ii in i.cited_by if lm.get_item(ii).level == 0]), i, i.title()[:30]) for i in lm1_mag_items], key=lambda x: x[0])[::-1][:30])
