from flexx import flx
from _cpcp.utils._process import MyProcess
from _cpcp.utils._dict import Dict
from _cpcp.utils._interrupt import terminate_thread
from _cpcp.utils._files import load_json, save_json
from _cpcp.cli import MyCLI
from _cpcp.app import MyApp
from _cpcp.app import MyApp
from _cpcp.downloader import Downloader
from _cpcp.problem_library import ProblemLibrary

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
        'Interrupt',
    ]

    def main(self, UI):
        UI.wait_ready()
        self.UI = UI
        self.lib = ProblemLibrary()

        self.change_problem(escape=False)

        self.ls_update()
        self.UI.print('Directory:', os.getcwd())
        self.ls_print()
        #self.self_updater()
        while 1:
            options = [
                *self.commands,
                *[f'Test {f}' for f in self.ls['in']],
                *[f'Open {f}' for f in sum(self.ls.values(), [])],
            ]
            command = self.UI.prompt(
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
        cache = load_json('cpcp/cache.json', {})
        problem.update(cache)
        while 0<=i<=3:
            self.UI.set_title('{language} {platform} {id}'.format(**problem))
            if i==0:
                x = self.UI.prompt(
                    message='Choose a language',
                    placeholder='Type...',
                    prefill=problem['language'],
                    options=self.lib.languages,
                )
                if x!=None:
                    problem['language'] = x
            elif i==1:
                x = self.UI.prompt(
                    message='Choose a platform',
                    placeholder='Type...',
                    prefill=problem['platform'],
                    options=self.lib.platforms,
                )
                if x!=None:
                    problem['platform'] = x
            elif i==2:
                x = self.UI.get_input(
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
            if i<0 and not escape:
                i=0
        save_json('cpcp/cache.json', problem)
        self.UI.set_title('{language} {platform} {id}'.format(**problem))
        self.UI.print(self.lib)
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
            self.xdg_open(self.lib.problem.statement)

        elif command=='Open problem folder':
            self.xdg_open(self.lib.problem.dir)

        elif command=='Open source code':
            self.xdg_open(self.lib.problem.source, touch=True)
            
        elif command=='Open templates':
            #await self.open_templates()
            self.UI.print('Not ready')

        elif command.startswith('Open '):
            self.xdg_open(command[5:])

        elif command=='Download tool':
            self.download()

        elif command=='New testcase':
            #await self.new_testcase()
            self.UI.print('Not ready')
            
        elif command=='Delete empty testcases':
            self.ls_delete_empty()

        elif command=='Change problem':
            self.change_problem(escape=True)

        elif command=='Settings':
            self.xdg_open('cpcp/settings.json')
            
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
            while not shared['done'] and not self.UI._interrupt.is_set():
                time.sleep(1e-3)
            if not shared['done']:
                self.UI.print('Terminating...')
                terminate_thread(t, KeyboardInterrupt)
                t.join()
                self.UI.print('Terinated')
            return shared['ret']
        wrapper.__name__=func.__name__
        return wrapper

    def execute(self, sample_in, sample_out, tmp_program=None, verbose=True):
        assert tmp_program or not self.compiler, 'You must compile first'
        cmd_exec = self.format(self.executer, tmp_program=tmp_program)
        cmd = f'{cmd_exec} < {sample_in}'
        p = self._process = MyProcess(cmd, shell=True)
        p.run(
            timeout=self.time_limit,
            max_stdout=self.max_output,
            live_stdout=self.UI if verbose else None,
            capture_stdout=True,
            capture_stderr=True,
        )
        error = p.error or p.stderr
        if verbose and error:
            self.UI.print(error)
        elif verbose and not p.stdout:
            self.UI.print('\nWarning: Your program printed nothing!\n')
        if self.time_limit!=None and p.elapsed >= self.time_limit:
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
        if not inputs:
            return self.UI.print('No input files found. Use the downlad tool or the new testcase tool.')
        with NamedTemporaryFile() as program:
            tmp_program = program.name
        try:
            cmdc = self.format(self.compiler, tmp_program=tmp_program)
            try:
                self._process=MyProcess(cmdc, shell=True).run(check=True)
            except Exception as e:
                print(e)
                self.UI.print(f'\nCompilation failed ({self.language}).\n   Command: {cmdc}')
                return
            self.UI.print(f'Compilation ok ({self.language}): {cmdc}')

            cmdx = self.format(self.executer, tmp_program=tmp_program)
            self.UI.print(f'Execution line ({self.language}): {cmdx}')
            if summary:
                self.UI.print()
                self.UI.print('Execution summary:')
                self.UI.print('    Judgements:')
            else:
                self.UI.print('-'*20)

            fmt = self.config.sample
            fmt_in = fmt.replace('{in_or_out}', 'in')
            fmt_in = fmt_in.replace('{num}', r'(?P<num>\d+)')
            regex = re.compile(fmt_in)
            total_time = 0
            for sample_in in inputs:
                m = regex.fullmatch(sample_in)
                if m:
                    num = m.groupdict().get('num')
                    sample_out = fmt.format(num=num, in_or_out='out')
                else:
                    sample_out = sample_in[:-3]+'.out'
                if not summary:
                    self.UI.print(f'Input: {sample_in}')
                    self.UI.print(f'Expected output: {sample_out}')
                veredict, exec_time = self.execute(
                    sample_in, sample_out,
                    tmp_program=tmp_program,
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
            if os.path.exists(tmp_program):
                MyProcess(['rm', tmp_program]).run()
        return

    def quit(self):
        sys.exit(0)

    def ls_update(self):
        ls = {}
        for ext in ['in', 'out']:
            files = glob.glob(f'{self.lib.problem.dir}/*.{ext}')
            empty = [f for f in files if not read_file(f).strip()]
            files = [f for f in files if f not in empty]
            files = sorted(files, key=lambda f: ('sample' not in f, my_order(f)))
            ls[ext] = files
            ls[ext+'_empty'] = empty
        self.ls = ls
        return

    def ls_print(self):
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

    def create_source(self, overwrite=False):
        self.create_path()
        source = self.lib.problem.source
        template = self.lib.template
        self.UI.print(f'Creating {source} from template:')
        if os.path.exists(source):
            self.UI.print('    Skipping. File already exists.')
        elif os.path.exists(template):
            self.UI.print(f'    Copying {template}')
            MyProcess(['cp', template, source]).run()
            self.UI.print('Done')
        else:
            self.UI.print(f'    Setting empty file: template not found {template}')
            MyProcess(['touch', source]).run()
        return

    async def open_templates(self):
        fmt = self.settings.dirtree['template']
        self.UI.print(f'\nTemplates use the format "{fmt}"')
        self.UI.print('\nYour languages and extensions:')
        for x in self.settings.languages.values():
            self.UI.print('   + .{extension:6s} {language}'.format(**x))
        await self.UI.alert('You will access the templates folder. Read below for info on new templates.')
        self.create_path(self.config.templates_path)
        self.xdg_open(self.config.templates_path)

    @_interruptable
    def download(self):
        return Downloader().download(
            self.UI, self.lib.problem,
            self.lib.platform)

    async def new_testcase(self):
        fmt_in = self.config.custom.replace('{in_or_out}', 'in')
        fmt_out = self.config.custom.replace('{in_or_out}', 'out')
        def exists(i):
            fmt = self.config.custom
            ein = os.path.exists(fmt_in.format(num=i))
            eout = os.path.exists(fmt_out.format(num=i))
            return ein and eout
        i = next(i for i in range(1, 10**5) if not exists(i))
        fname = fmt_in.format(num=i)
        if await self.UI.ask_bool(f'Opening {fname}. Ok?'):
            self.UI.print(f'Creating {fname}')
            self.xdg_open(fname, touch=True)
        fname = fmt_out.format(num=i)
        if await self.UI.ask_bool(f'Opening {fname}. Ok?'):
            self.UI.print(f'Creating {fname}')
            self.xdg_open(fname, touch=True)
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
    global META

    META = Dict()
    META.version = 'v0.0.0'
    META.source = os.path.realpath(__file__)
    META.srcdir = os.path.dirname(os.path.realpath(__file__))
    META.bintag = f'CPCP-{platform.system()}-{platform.machine()}'
    META.releases_url = 'https://api.github.com/repos/caph1993/cpcp/releases/latest'
    
    arg0, *META.args = sys.argv
    executable = os.path.realpath(sys.executable)
    dev = executable!=os.path.realpath(arg0)
    if executable == os.path.realpath(arg0):
        META.binary = executable
        META.wdir = os.path.dirname(executable)
    else:
        META.binary = None # dev mode, no executable
        META.wdir = META.srcdir

    META.mode = ('firefox-app' if not META.args else META.args[0]).lower()
    os.chdir(META.wdir)

    cpcp = CPCP()
    if META.mode=='cli':
        cpp.main(MyCLI())
    else:
        app = flx.App(MyApp)
        title = 'CPCP'
        icon = os.path.join(META.srcdir, 'icon.png')
        UI = app.launch(META.mode, title=title, icon=icon)
        t = Thread(target=cpcp.main, args=[UI])
        t.setDaemon(True)
        t.start()
        flx.run()
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
 (OK) Organize folder structure
 (OK) Create from templates
 (OK) Open templates
 (OK) Make UI non async and blocking
 (OK) Plugin system (move everything to a cpcp folder)
 + Updates system
 + Reorganize Problem attributes
 + Fix long labels
 + let cpp match c++
 + Darker theme (or selectable)
 + Fix options spacing
'''