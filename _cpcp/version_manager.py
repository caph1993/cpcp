from urllib.request import urlopen
from tempfile import TemporaryDirectory
from subprocess import Popen, run
import json, shutil, os, sys, time, traceback
from .utils._files import load_json, save_json
from .utils._string import split_numbers
from _thread import interrupt_main

VER = os.path.join('cpcp','cache','version.json')
ON_POSIX = 'posix' in sys.builtin_module_names

def _restart(new_exe):
    if ON_POSIX:
        run(['chmod', '+x', new_exe], check=True)
    Popen([new_exe])
    interrupt_main()
    return


def version_init(version, exe):
    x = load_json(VER, {})
    x = {v:e for v,e in x.items() if os.path.isfile(e)}
    save_json(VER, x)
    if not exe: # Dev mode. Restart disabled
        return
    x[version] = exe
    latest = max(x.keys(), key=split_numbers)
    latest_exe = x[latest]
    if latest!=version and exe!=latest_exe:
        print('Restarting to new version')
        _restart(latest_exe)
    else:
        print('Running latest local version')
        for v, e in x.items():
            if v!=latest and e!=latest_exe:
                try: os.remove(e)
                except: pass
        x = {v:e for v,e in x.items() if os.path.isfile(e)}
        save_json(VER, x)
    return


def version_main(UI, META):
    v0 = META.version
    exe = META.exe
    exetag = META.exetag
    releases_url = META.releases_url
    srcdir = META.srcdir
    while 1:
        while 1:
            UI.set_version(f'{v0} (checking...)')
            try:
                v1, url, size = _get_latest_version(
                    releases_url, exetag)
            except:
                UI.set_version(f'{v0} (network error)')
                time.sleep(5)
                print(traceback.format_exc())
            else:
                break
        if v1==v0:
            text='latest'
        else:
            text='click to update'
        UI.set_version(f'{v0} ({text})')
        UI._version.clear()
        UI._version.wait()
        if v1==v0:
            UI.print('You have the latest version of this software already.')
        else:
            fname=f'CPCP-{v1}-{exetag}'
            new_exe = os.path.join('.', fname)
            UI.set_version(f'{v0} (updating...)')
            with TemporaryDirectory() as tmp:
                tmp_exe = os.path.join(tmp, fname)
                try:
                    for p in _downloader(url, size, tmp_exe):
                        progress = round(p*100)
                        UI.set_version(f'{v0} ({progress}%)')
                except:
                    UI.print(traceback.format_exc())
                    shutil.rmtree(tmp)
                else:
                    UI.set_version(f'{v0} (restarting)')
                    UI.print(f'Latest version downloaded')
                    shutil.move(tmp_exe, new_exe)
            UI.print('App will restart soon...')
            _restart(new_exe)
    return



def _get_latest_version(releases_url, binary_tag):
    latest = urlopen(releases_url)
    latest = json.loads(latest.read().decode())
    latest_version = latest.get('tag_name')
    
    for asset in latest.get('assets', []):
        if asset['name']==binary_tag:
            url = asset['browser_download_url']
            size = asset['size']
    return latest_version, url , size


def _downloader(url, size, dest):
    if os.path.exists(dest):
        yield 1
    else:
        resp = urlopen(url)
        n_parts = 100
        acum = 0
        blocksize = max(1, size//n_parts)
        with open(dest, 'wb') as f:
            for i in range(n_parts+1):
                data = resp.read(blocksize)
                f.write(data)
                acum += len(data)
                yield acum/size
    return


if __name__=='__main__':
    pass