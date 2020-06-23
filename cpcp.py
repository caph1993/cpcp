from flexx import flx
from app import MyApp
from _cpcp.utils._process import MyProcess
from _cpcp.utils._dict import Dict
from _cpcp.utils._interrupt import terminate_thread
from _cpcp.utils._string import split_numbers
from _cpcp.utils._files import (load_json, save_json,
    mkdir, sys_open)
from _cpcp.cli import MyCLI
from _cpcp.problem_library import ProblemLibrary
from _cpcp.version_manager import (
    version_main, version_init)
from _cpcp.downloader import Downloader
from _cpcp.userdir import init_userdir
from subprocess import Popen
from webruntime.util.icon import Icon
from subprocess import run, PIPE, DEVNULL
from string import ascii_uppercase
from tempfile import NamedTemporaryFile
from string import Formatter
import sys, os, glob, time, re, json, io, traceback
import asyncio, threading, platform, multiprocessing
from threading import Thread
from asyncio import ensure_future as nowait
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from _thread import interrupt_main
import shutil


class CPCP():

    commands = [
        'Summary',
        'Open source code',
        'Test all',
        'Settings',
        'List in/out (ls)',
        'Quit',
        'Change problem',
        'Download tool',
        'Delete empty testcases',
        'Create source from template',
        'Open statement',
        'Open templates',
        'Open problem folder',
        'New testcase',
    ]

    def main(self, UI):
        UI.wait_ready()
        self.UI = UI
        self.lib = ProblemLibrary()
        self.UI.print(f'\nRoot: {os.getcwd()}')
        self.change_problem(escape=False)

        self.limits = Dict(time_limit=10,
            max_output='50M')

        while 1:
            options = [
                *self.commands,
                *[f'Test {f}' for f in self.ls['in']],
                *[f'Open {f}' for f in sum(self.ls.values(), [])],
            ]
            command = self.UI.choice(
                message=None,
                options=options,
                placeholder='Type your command...',
            )
            if command==None: continue
            self.UI.clear()
            try:
                self.handle(command)
            except:
                self.UI.print(traceback.format_exc())
        return

    def change_problem(self, i=0, escape=True):
        keys = 'language platform id'.split()
        if self.lib.ready:
            problem = self.lib.problem
            problem = {k:problem[k] for k in keys}
        else:
            problem = {k:'' for k in keys}

        pcache = os.path.join('cpcp', 'cache', 'problem.json')
        cache = load_json(pcache, {})
        problem.update(cache)
        while 0<=i<=3:
            self.UI.set_title('{language} {platform} {id}'.format(**problem))
            if i==0:
                x = self.UI.choice(
                    message='Choose a language',
                    placeholder='Type...',
                    prefill=problem['language'],
                    options=self.lib.languages,
                )
                if x!=None:
                    problem['language'] = x
            elif i==1:
                x = self.UI.choice(
                    message='Choose a platform',
                    placeholder='Type...',
                    prefill=problem['platform'],
                    options=self.lib.platforms,
                )
                if x!=None:
                    problem['platform'] = x
            elif i==2:
                x = self.UI.prompt(
                    message=f'Type the problem id',
                    prefill=problem['id'],
                    placeholder='Type...',
                )
                if x!=None:
                    problem['id'] = x
            elif i==3:
                try:
                    self.lib.set_problem(**problem)
                except AssertionError as e:
                    x = None
                    self.UI.print(e)
                else:
                    x = ''
            if x==None: i-=1
            else: i+=1
            if i<0 and not escape: i=0
        save_json(pcache, problem)
        self.UI.set_title('{language} {platform} {id}'.format(**problem))
        self.UI.clear()
        self.create_source()
        self.ls_update()
        self.ls_print(clear=False)
        return

    def create_source(self, overwrite=False):
        mkdir(self.lib.problem.dir)
        source = self.lib.problem.source
        template = self.lib.template
        self.UI.print(f'Creating {source} from template:')
        if os.path.exists(source) and os.path.getsize(source)>0:
            self.UI.print('    Skipping. File already exists.')
        elif os.path.exists(template):
            self.UI.print(f'    Copying {template}')
            MyProcess(['cp', template, source]).run()
            self.UI.print('Done')
        else:
            self.UI.print(f'    Setting empty file: template not found {template}')
            MyProcess(['touch', source]).run()
        return

    def handle(self, command):
        if command=='Quit':
            self.quit()

        elif command=='List in/out (ls)':
            self.ls_update()
            self.ls_print()

        elif command=='Summary':
            self.run(self.ls['in'], summary=True)

        elif command=='Test all':
            self.run(self.ls['in'], summary=False)

        elif command.startswith('Test '):
            self.run([command[5:]], summary=False)

        elif command=='Open statement':
            sys_open(self.lib.problem.statement)

        elif command=='Open problem folder':
            sys_open(self.lib.problem.dir)

        elif command=='Open source code':
            sys_open(self.lib.problem.source, create=True)
            
        elif command=='Open templates':
            self.open_templates()

        elif command.startswith('Open '):
            sys_open(command[5:])

        elif command=='Download tool':
            self.download()
            self.ls_update()
            self.ls_print(clear=False)

        elif command=='New testcase':
            self.new_testcase()
            self.ls_update()
            self.ls_print(clear=False)
            
        elif command=='Delete empty testcases':
            self.ls_delete_empty()
            self.ls_update()
            self.ls_print(clear=False)

        elif command=='Change problem':
            self.change_problem(escape=True)

        elif command=='Settings':
            sys_open('cpcp/settings.json')
            
        elif command=='Create source from template':
            self.create_source()

        else:
            print(f'Unknown command: {command}')
        return


    def _threaded(func):
        def wrapper(self, *args, **kwargs):
            Thread(target=func, args=(self, *args), kwargs=kwargs).start()
        wrapper.__name__=func.__name__
        return wrapper


    def _interruptable(func):
        def wrapper(self, *args, **kwargs):
            def f(shared, self, args, kwargs):
                shared['ret'] = func(self, *args, **kwargs)
                shared['done'] = True
            shared = Dict(done=False, ret=None)
            t = Thread(target=f, args=(shared,self,args,kwargs))
            self.UI._interrupt.clear()
            t.start()
            while not shared['done']:
                time.sleep(1e-3)
                if self.UI._interrupt.is_set():
                    self.UI.print('Keyboard interruption...')
                    terminate_thread(t, KeyboardInterrupt)
                    self.UI._interrupt.clear()
            t.join()
            return shared['ret']
        wrapper.__name__=func.__name__
        return wrapper

    def execute(self, sample_in, sample_out, tmp_exe=None, verbose=True):
        assert tmp_exe or not self.lib.language.compiler, 'You must compile first'
        cmd_exec = self.lib.language.executer.format(tmp_exe=tmp_exe)
        cmd = f'{cmd_exec} < {sample_in}'
        p = MyProcess(cmd, shell=True)
        p.run(
            timeout=self.limits.time_limit,
            max_stdout=self.limits.max_output,
            live_stdout=self.UI if verbose else None,
            capture_stdout=True,
            capture_stderr=True,
        )
        error = p.error or p.stderr
        if verbose and error:
            self.UI.print(error)
        elif verbose and not p.stdout:
            self.UI.print('\nWarning: Your program printed nothing!\n')
        if self.limits.time_limit!=None and p.elapsed >= self.limits.time_limit:
            veredict = 'TL'
        elif error:
            veredict = 'RE'
        elif not sample_out or not os.path.exists(sample_out):
            veredict = '¿?'
        elif p.stdout==read_file(sample_out):
            veredict = 'AC'
        else:
            veredict = 'WA'
        return veredict, p.elapsed

    @_interruptable
    def run(self, inputs, summary=False):
        language = self.lib.problem.language
        if not inputs:
            return self.UI.print('No input files found. Use the downlad tool or the new testcase tool.')
        with NamedTemporaryFile() as exe:
            tmp_exe = exe.name
        try:
            cmdc = self.lib.language.compiler.format(tmp_exe=tmp_exe)
            cmdx = self.lib.language.executer.format(tmp_exe=tmp_exe)
            self.UI.print(f'Compiling...\n  {cmdc}')
            try:
                MyProcess(cmdc, shell=True).run(
                    check=True, live_stderr=self.UI,
                    live_stdout=self.UI)
            except:
                self.UI.print(f'\nCompilation failed. Command used:')
                self.UI.print(f'    {cmdc}')
                return
            self.UI.print(f'Running... (ctrl+c to interrupt)\n  {cmdx}')
            self.UI.print()
            if summary:
                self.UI.print('Execution summary:')
                self.UI.print('    Judgements:')
            else:
                self.UI.print('-'*20)

            sample_io = self.lib.problem.sample_io
            fmt_in = sample_io.format(io_ext='in',
                io_num=r'(?P<num>\d+)')
            regex = re.compile(fmt_in)
            total_time = 0
            for sample_in in inputs:
                m = regex.fullmatch(sample_in)
                if m:
                    num = m.groupdict().get('num')
                    sample_out = sample_io.format(
                        io_num=num, io_ext='out')
                else:
                    sample_out = sample_in[:-3]+'.out'
                if not summary:
                    self.UI.print(f'Input: {sample_in}')
                veredict, exec_time = self.execute(
                    sample_in, sample_out,
                    tmp_exe=tmp_exe,
                    verbose=not summary,
                )
                total_time += exec_time
                if not summary:
                    self.UI.print(f'Judgement: {veredict} ({exec_time:.2f} s)')
                    self.UI.print('-'*20)
                else:
                    self.UI.print(f'       {veredict} ({exec_time:.2f} s) for {sample_in}')
            if summary:
                self.UI.print(f'    Total time:  {total_time:.2f} s')
        finally:
            if os.path.exists(tmp_exe):
                MyProcess(['rm', tmp_exe]).run()
        return

    def quit(self):
        interrupt_main()

    def ls_update(self):
        ls = {}
        for ext in ['in', 'out']:
            files = glob.glob(f'{self.lib.problem.dir}/*.{ext}')
            empty = [f for f in files if os.path.getsize(f)==0]
            files = [f for f in files if f not in empty]
            files = sorted(files, key=lambda f:
                ('sample' not in f, split_numbers(f)))
            ls[ext] = files
            ls[ext+'_empty'] = empty
        self.ls = ls
        return

    def ls_print(self, clear=True):
        if clear:
            self.UI.clear()
        if any(v for k,v in self.ls.items()):
            self.UI.print('\nInput/output files and possible actions:\n')
            for x in self.ls['in']:
                self.UI.print(' + Test/open   ', x)
            for x in self.ls['out']:
                self.UI.print(' + Open        ', x)
            for x in self.ls['in_empty']+self.ls['out_empty']:
                self.UI.print(' + Open (empty)', x)
        else:
            self.UI.print('   No input/output files found locally.')
            self.UI.print('   Use the download tool!')
        return

    def ls_delete_empty(self):
        for f in self.ls['in_empty']+self.ls['out_empty']:
            self.UI.print('Deleting', f, end='...')
            try: os.remove(f)
            except Exception as e: self.UI.print(e)
            else: self.UI.print('ok')
        self.UI.print('Done')

    def open_templates(self):
        self.UI.print(f'\nName your templates properly! (see settings)')
        self.UI.alert('You will access the templates folder.')
        mkdir(self.lib.templates_dir)
        sys_open(self.lib.templates_dir)

    @_interruptable
    def download(self):
        return Downloader().download(
            self.UI, self.lib.problem,
            self.lib.platform)

    def new_testcase(self):
        custom_io = self.lib.problem.custom_io
        def exists(i):
            for ext in 'in out'.split():
                f = custom_io.format(io_num=i, io_ext=ext)   
                if not os.path.exists(f):
                    return False
            return True
        i = next(i for i in range(1, 10**5) if not exists(i))
        fname = custom_io.format(io_num=i, io_ext='in')
        if self.UI.confirm(f'Opening {fname}. Ok?'):
            self.UI.print(f'Creating {fname}')
            sys_open(fname, create=True)
        fname = custom_io.format(io_num=i, io_ext='out')
        if self.UI.confirm(f'Opening {fname}. Ok?'):
            self.UI.print(f'Creating {fname}')
            sys_open(fname, create=True)
        return

    def create_path(self, path=None):
        if path==None: path=self.lib.problem.dir
        self.UI.print(f'Creating dir {path}')
        MyProcess(['mkdir', '-p', path]).run()

    def xdg_open(self, path, touch=False):
        self.UI.print(f'Opening {path}...')
        path = os.path.abspath(path)
        exists = os.path.exists(path)
        if not exists and touch:
            self.UI.print('Not found. Creating empty file.')
            MyProcess(['touch', path]).run()
            exists = True
        if exists:
            MyProcess(['xdg-open', path]).run_detached()
        else:
            self.UI.print('Not found:', path)
        return exists


def main():
    META = Dict()
    META.version = 'v1.1.0'
    META.source = os.path.realpath(__file__)
    META.srcdir = os.path.dirname(os.path.realpath(__file__))
    META.exetag = f'CPCP-{platform.system()}-{platform.machine()}'
    META.releases_url = 'https://api.github.com/repos/caph1993/cpcp/releases/latest'
    
    arg0, *args = sys.argv
    META.mode = args[0] if args else 'firefox-app'
    META.args = args[1:]
    executable = os.path.realpath(sys.executable)
    dev = executable!=os.path.realpath(arg0)
    if executable == os.path.realpath(arg0):
        META.exe = executable
        META.wdir = os.path.dirname(executable)
    else:
        META.exe = None # dev mode, no executable
        META.wdir = META.srcdir

    os.chdir(META.wdir)

    init_userdir(META.srcdir)
    version_init(META.version, META.exe)

    cpcp = CPCP()
    if META.mode.startswith('--update-step='):
        update_step(int(META.mode[14:]), *META.args)
    elif META.mode=='cli':
        cpp.main(MyCLI())
    else:
        app = flx.App(MyApp)
        title = 'CPCP'
        icon = os.path.join('_cpcp', 'icon.png')
        icon = os.path.join(META.srcdir, icon)
        UI = app.launch(META.mode, title=title, icon=icon)
        t = Thread(target=cpcp.main, args=[UI])
        t.setDaemon(True)
        t.start()
        t = Thread(target=version_main, args=[UI, META])
        t.setDaemon(True)
        t.start()
        flx.run()
        sys.exit(0)
    return


if __name__=='__main__':
    main()

'''
TODO:
 (OK) Better fuzzy match
 (OK) Implement the Run #, Input # and Output #
 (OK) Implement the platform and language selection menu
 (OK) Implement the problem_id selection menu
 (OK) Go back with escape
 (OK) Make latest used options appear first in fuzzy filter
 (OK) Fix Placeholders
 (OK) Check if disposing the box elements instead of the box itself looks better
 (OK) Input autofocus. Maybe using RAWJS, or TAB+TAB?
 (OK) Live console output
 (OK) Organize classes
 (OK) Open problem folder, code statement
 (OK) Output limit
 (OK) Run all and summary
 (OK) Change MyStdout with TemporaryStream or something better
 (OK) Confirmation dialog
 (OK) Set title and logo
 (OK) Ask string dialog
 (OK) Change frontend logic to only this modifiable tabs: MyFilter, String input, Alert
 (OK) Console bottom scroll
 (OK) KeyboardInterrupt from GUI
 (OK) Run #
 (OK) Rename/restyle the buttons instead of creating them again
 (OK) Use alternative up/down overflow in MyFuzzyfilter
 (OK) Create executable app
 (OK) Improve sample_in[:-3]+'.out'
 (OK) New input/output
 (OK) Download with confirmation dialogs
 (OK) Create settings file
 (OK) Set root path in settings or handle it
 (OK) Organize folder structure|
 (OK) Create from templates
 (OK) Open templates
 (OK) Make UI non async and blocking
 (OK) Plugin system (move everything to a cpcp folder)
 (OK) Updates system
 (OK) Autodestroy old versions
 (OK) Reorganize Problem attributes
 (OK) Fix long labels (not supported)
 + let cpp match c++
 + Darker theme (or selectable)
 + Fix options spacing
'''