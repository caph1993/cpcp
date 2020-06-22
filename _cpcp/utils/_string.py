import re

def split_numbers(text):
    '''
    Useful for sorting strings with numbers and letters
    like version tags
    '''
    atoi = lambda x: int(x) if x.isdigit() else x
    values = re.split(r'(\d+)', text)
    tup = tuple(atoi(x) for x in values)
    return tup


