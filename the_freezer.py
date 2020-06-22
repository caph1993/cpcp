import PyInstaller.__main__
from flexx.util import freeze
from tempfile import TemporaryDirectory
import os, asyncio, inspect, shutil

def app_main():
    # Install hook so we we can import modules from source when frozen.
    from flexx.util import freeze
    freeze.install()
    # Run your app as usual
    import flexx as flx
    from cpcp import main
    main()
    return


def create_executable(app_main, *args, exec_name='MyFlexxApp', js_modules=['flexx']):
    here = os.path.dirname(os.path.abspath(__file__))
    with TemporaryDirectory() as tmp:
        tmp_app = '_tmp_app_main.py'
        try:
            with open(tmp_app, 'w') as f:
                f.write(inspect.getsource(app_main))
                f.write(f'\n{app_main.__name__}()\n')
            for mod in js_modules:
                freeze.copy_module(mod, tmp)
            tmp_build = os.path.join(tmp, 'build')
            tmp_source = os.path.join(tmp, 'source')
            PyInstaller.__main__.run([
                f'--name={exec_name}', '--onefile', '--windowed', '--clean',
                f'--workpath={tmp_build}', '--distpath=.',
                f'--add-data={tmp_source}{os.pathsep}source',
                *args, tmp_app
            ])
            print(f'FINISHED\n-----\nContents of {exec_name}.spec:')
            with open(f'{exec_name}.spec') as f:
                print(f.read())
            print(f'SUCCESS')
        finally:
            try: os.remove(tmp_app)
            except OSError: pass
            try: os.remove(f'{exec_name}.spec')
            except OSError: pass
            try: shutil.rmtree(f'__pycache__')
            except: pass
    return

create_executable(
    app_main,
    '--hidden-import=pkg_resources.py2_warn', # BUG between pyinstaller and setuptools
    '--exclude-module=numpy', # Custom numpy exclusion
    '--icon=favicon.ico',
    '--add-data=icon.png:.',
    '--add-data=default_settings.json:.',
    exec_name='CPCP',
    js_modules=[
        'flexx',
        '_cpcp.widgets',
        '_cpcp.app',
    ],
)
