from tempfile import TemporaryDirectory
import re, json, shutil, os
from subprocess import run
import subprocess, os, platform


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

def save_json(path, obj, indent=2):
    folder, fname = os.path.split(path)
    with TemporaryDirectory() as tmp:
        tmp_file = os.path.join(tmp, fname)
        with open(tmp_file, 'w') as f:
            json.dump(obj, f, indent=indent)
        if os.path.exists(path):
            os.remove(path)
        mkdir(folder)
        shutil.move(tmp_file, path)
    return

def mkdir(*path):
    path = os.path.join(*path)
    if not os.path.exists(path):
        run(['mkdir', '-p', path], check=True)
    assert os.path.isdir(path)
    return

def sys_open(filepath, create=False):
    if create and not os.path.exists(filepath):
        with open(filepath,'w'):
            pass
    if platform.system() == 'Darwin':
        subprocess.call(('open', filepath))
    elif platform.system() == 'Windows':
        os.startfile(filepath)
    else: # Linux
        subprocess.call(('xdg-open', filepath))
    return
