from tempfile import NamedTemporaryFile
import re, json, shutil, os


def read_file(fname):
    with open(fname) as f: 
        content = f.read()
    return content

def load_json(fname, on_error=None, check=False):
    try:
        s = read_file(fname)
        s = re.sub(",[ \t\r\n]+}", "}", s)
        s = re.sub(",[ \t\r\n]+\]", "]", s)
        obj = json.loads(s)
    except:
        obj = on_error
        if check: raise
    return obj

def save_json(fname, obj, indent=2):
    with NamedTemporaryFile(suffix='.json') as x:
        tmp = x.name
    with open(tmp, 'w') as f:
        json.dump(obj, f, indent=indent)
    shutil.move(tmp, fname)
    return

def mkdir(*path):
    path = os.path.join(*path)
    if not os.path.exists(path):
        run(['mkdir', '-p', path], check=True)
    assert os.path.is_directory(path)
    return
