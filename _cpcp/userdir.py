from .utils._files import mkdir
import os, glob, shutil

def init_userdir(srcdir):
    d = os.path.join(srcdir, '_cpcp', 'initial_userdir')
    n = 1+len(d)
    pattern = os.path.join(d, '**')
    for src in glob.glob(pattern, recursive=True):
        tgt = os.path.join('cpcp', src[n:])
        if os.path.isdir(src):
            mkdir(tgt)
        elif not os.path.exists(tgt):
            shutil.copy(src, tgt)
    return