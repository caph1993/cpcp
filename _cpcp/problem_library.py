from .utils._dict import Dict, deep_update, flatten, unflatten
from .utils._files import load_json, save_json
import os, re

CFG = os.path.dirname(os.path.realpath(__file__))
CFG = os.path.join(CFG, 'settings.json')

def recursive_formatting(d:dict):
    '''
    Convert {'a':'{b.c}{b.c}', 'b':{'c':'y'}} into
    {'a':'yy', 'b':{'c':'y'}}
    '''
    #flatten the dictionary with dot notation
    flat = flatten(d)

    #Build dependencies and references graph
    refs = {key:[] for key in flat}
    deps = {key:[] for key in flat}
    for key, s in flat.items():
        if not isinstance(s, str) or key.endswith('.re_parser'):
            continue # skip element
        for e in flat:
            if '{'+e+'}' in s:
                deps[key].append(e)
                refs[e].append(key)

    # Toposort string dependencies
    topo = []
    deg = {k:len(v) for k,v in deps.items()}
    q = [k for k,n in deg.items() if n==0]
    while q:
        u = q.pop()
        topo.append(u)
        for v in refs[u]:
            deg[v] -= 1
            if deg[v]==0:
                q.append(v)
    circular = [k for k in flat if k not in topo]
    assert not circular, f'Circular references: {circular}\n{config}'

    # Format strings
    flat_ready = {}
    for key in topo:
        val = flat[key]
        for k in deps[key]:
            val = val.replace('{'+k+'}', flat_ready[k])  
        flat_ready[key] = val

    return unflatten(flat_ready)


class ProblemLibrary(Dict):

    def __init__(self):
        self.user_settings = os.path.abspath(
            'cpcp/settings.json')
        cfg = self.load_settings()
        cfg['languages'] = [l for l in cfg['languages']]
        cfg['platforms'] = [l for l in cfg['platforms']]
        cfg = Dict.recursive(cfg)
        deep_update(self, cfg, Dict)
        self.ready = False

    def load_settings(self):
        cfg = load_json(CFG, check=True)
        user = load_json(self.user_settings, {})
        deep_update(cfg, user)
        return cfg

    def set_problem(self, language, platform, id):
        self.ready = False
        cfg = self.load_settings()
        languages = cfg.pop('languages')
        platforms = cfg.pop('platforms')
        cfg['languages'] = [l for l in languages]
        cfg['platforms'] = [l for l in platforms]

        cfg['problem'].update(language=language,
            platform=platform, id=id)
        assert language in languages, f'No such langage {language}'
        cfg['language']=languages[language]
        cfg['language']['name']=language
        assert platform in platforms, f'No such langage {platform}'
        cfg['platform']=platforms[platform]
        cfg['platform']['name']=platform

        cfg = recursive_formatting(cfg)
        regex = cfg['platform']['re_parser']
        parsed = re.compile(regex).fullmatch(id)
        assert parsed!=None, (
            f'Invalid problem id for {platform}:\n'
            f' + Input: "{id}"\n'
            f' + RegEx: "{regex}"'
        )
        cfg['platform'].update(parsed.groupdict())
        cfg = recursive_formatting(cfg)
        cfg = Dict.recursive(cfg)
        deep_update(self, cfg, Dict)
        self.ready = True
        return

    def format(self, fmt_str, **kwargs):
        return fmt_str.format(**{**self, **kwargs})

if __name__=='__main__':
    lib = ProblemLibrary()
    lib.set_problem(
        language='python3',
        platform='codeforces',
        id='123A'
    )
    print(lib)
