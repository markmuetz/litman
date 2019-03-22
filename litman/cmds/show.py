"""Show information about a given item"""
from litman.litman import ItemNotFound

ARGS = [(['list_item'], {'nargs': 1, 'help': 'Show information about a list item'})]


def main(litman, args):
    try:
        item = litman.get_item(args.list_item[0])
    except ItemNotFound:
        print('Could not find item')
        return
    print(f'Name: {item.name}')
    print(f'DOI: {item.doi_url()}')
    print(f'title: {item.title()}')
    print(f'authors: {item.authors()}')
    print(f'year: {item.year()}')
    print(f'has_pdf: {item.has_pdf}')
    print(f'has_bib: {item.has_bib}')
    print(f'has_extracted_text: {item.has_extracted_text}')
    print(f'tags: {item.tags}')
    if item.has_bib:
        print('===============')
        print('= bib entry   =')
        print('===============')
        print(item.bib_entry())
        print('===============')
    if item.has_extracted_text:
        print('===============')
        print('= pdf text    =')
        print('===============')
        print('\n'.join(item.extracted_text().split('\n')[:20]))
        print('===============')
    if item.has_extracted_text:
        print('===============')
        print('= Notes       =')
        print('===============')
        print(item.notes())
        print('===============')
