"""Run with:

export FLASK_APP=litman_web.py
export FLASK_DEBUG=1
flask run
"""
from flask import Flask, request
from flask import render_template

from litman import LitMan, load_config

app = Flask(__name__)

litmanrc_fn, config = load_config()
litman = LitMan(config['litman_dir'])


@app.route('/')
def index():
    return render_template('index.html', litman_dir=config['litmad_dir'])


@app.route('/items')
def list_items():
    tag_filter = request.args.get('tag_filter', None)
    sort_on = request.args.getlist('sort_on')
    if not sort_on:
        sort_on = ['name']

    items = litman.get_items(tag_filter)
    for sort in sort_on:
        items = sorted(items, key=lambda item: getattr(item, sort))

    return render_template('items.html', items=items, curr_sorts='')


@app.route('/item/<item_name>')
def show_item(item_name):
    item = litman.get_item(item_name)
    return render_template('item.html', item=item)


