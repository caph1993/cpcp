import collections.abc
from pprint import PrettyPrinter

pprinter = PrettyPrinter()

class Dict(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            return object.__getattribute__(self, key)
    
    def __setattr__(self, key, value):
        self[key] = value

    @staticmethod
    def recursive(d:dict):
        root = Dict(d)
        for k,v in root.items():
            if isinstance(v, dict) and (
                not isinstance(v, Dict)):
                root[k] = Dict.recursive(v)
        return root

    def __str__(self):
        return pprinter.pformat(self)


def deep_update(d, u, _class=dict):
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = deep_update(d.get(k, _class()), v)
        else:
            d[k] = v
    return d


def flatten(d:dict)->dict:
    flat = {}
    q = [('', d)]
    while q:
        prefix, e = q.pop()
        if isinstance(e, dict):
            for key,val in e.items():
                q.append((f'{prefix}.{key}', val))
        else:
            flat[prefix[1:]] = e
    return flat


def unflatten(flat:dict)->dict:
    root = {}
    for key, val in flat.items():
        parent = root
        for sub in key.split('.'):
            parent[sub] = parent.get(sub, {})
            last = parent
            parent = parent[sub]
        last[sub] = val
    return root

