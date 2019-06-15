# coding: utf-8
import os
import re
import string

import requests
import simplejson


def gen_journal_abbr_name_map(output_dir):
    pages = {}
    for p in string.ascii_uppercase:
        pages[p] =  requests.get(f'https://images.webofknowledge.com/WOK48B5/help/WOS/{p}_abrvjt.html')
    pages['0-9'] = requests.get(f'https://images.webofknowledge.com/WOK48B5/help/WOS/0-9_abrvjt.html')

    jmap = {}
    for page in pages.values():
        # HTML is really janky. trying to read it with e.g. BeautifulSoup will cause recursion errors.
        # Just split on linebreaks and use a regex to grab what I need.
        lines = page.text.split('\n')
        jabbrs = [re.match('.*<DD>\t(?P<jabbr>.*)', l).groups()[0] for l in lines if re.match('.*<DD>\t(?P<jabbr>.*)', l)]
        jnames = [re.match('.*<DT>(?P<jname>.*)', l).groups()[0] for l in lines if re.match('.*<DT>(?P<jname>.*)', l)]
        jmap.update(dict(zip(jabbrs, jnames)))
        
    with open(os.path.join(output_dir, 'web_of_knowledge_journal_abbr_name_map.json'), 'w') as f:
        simplejson.dump(jmap, f, indent=2)


def load_journal_abbr_name_map(output_dir):
    with open(os.path.join(output_dir, 'web_of_knowledge_journal_abbr_name_map.json'), 'r') as f:
        return simplejson.load(f)
