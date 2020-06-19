from my_flexx_app import MyApp
from flexx import flx
from webruntime.util.icon import Icon
from my_process import MyProcess
from my_dict import Dict
from my_terminal import TerminalUI
from subprocess import run, PIPE, DEVNULL
from urllib.request import urlopen
from html.parser import HTMLParser
from string import ascii_uppercase
from tempfile import NamedTemporaryFile
from string import Formatter
import sys, os, glob, time, re, json, io, signal, asyncio
import collections.abc


def deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d

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
    MyProcess(['mv', tmp, fname]).run()
    return

def my_order(text): # Sort strings with numbers and letters
    atoi = lambda x: int(x) if x.isdigit() else x
    return [atoi(x) for x in re.split(r'(\d+)', text)]


class ProblemLibrary():

    def __init__(self, default_settings='default_settings.json'):
        self.user_settings = 'settings.json'

        settings = load_json(default_settings, check=True)
        usettings = load_json(self.user_settings, {})
        deep_update(settings, usettings)

        self.settings = Dict(settings)
        self.config = None
        self.current = {
            **settings.get('default_problem', {}),
            **settings.get('current_problem', {}),
        }
        self.set_problem()

    def set_problem(self,
            language=None,
            platform=None,
            problem_id=None,
            time_limit=None,
            max_output=None,):
        given = locals()
        latest = load_json(self.user_settings, {}).get('current_problem', {})
        self.current = {
            key: given[key] if given[key]!=None else latest.get(key, val)
            for key, val in self.current.items()
        }
        self.settings.current_problem = self.current
        save_json(self.user_settings, self.settings)
        self.config = None

        language = self.settings.languages.get(self.current['language'])
        platform = self.settings.platforms.get(self.current['platform'])
        problem_id = self._parse_problem_id(platform, self.current['problem_id'])

        errors = {}
        if not language:
            msg='Unknown language {language}'.format(**self.current)
            errors['language'] = msg
        if not platform:
            msg='Unknown platform {platform}'.format(**self.current)
            errors['platform'] = msg
        if platform and not problem_id:
            tups = platform['id_parser'].items()
            msg = (
                '\nInvalid problem ID "{problem_id}"'.format(**self.current)
                +'\nExpected format for {platform}: "{id}"'.format(**platform)
                +'\n'+'\n'.join(f'    {k}: {v}' for k,v in tups)+'\n'
            )
            errors['problem_id'] = msg

        if not errors:
            try:
                config = self._parse_config({**self.current, **language,
                    **platform, **problem_id, **self.settings.dirtree,})
            except Exception as e:
                errors['config'] = e
                print(e)
                raise
            else:
                self.config = Dict(config)
        return errors

    def _parse_problem_id(self, platform, problem_id):
        if not platform:
            parsed = None
        else:
            regex = platform['id']
            parser = platform['id_parser']
            replace = {k: f'(?P<{k}>{v})' for k, v in parser.items()}
            try: regex = regex.format(**replace)
            except KeyError: parsed = None
            else:
                regex = re.compile(regex).fullmatch(problem_id)
                if regex==None: parsed = None
                else: parsed = regex.groupdict()
        return parsed

    def _parse_config(self, config):
        # Analize string formats
        nostr = {k:v for k,v in config.items() if not isinstance(v, str)}
        config = {k:v for k,v in config.items() if isinstance(v, str)}

        # Toposort string dependencies
        topo = []
        R = {k:[] for k in config}
        depdeg = {k:0 for k in config}
        for k in config:
            for d in config:
                if '{'+d+'}' in config[k]:
                    depdeg[k]+=1
                    R[d].append(k)
        z = [k for k in config if depdeg[k]==0]
        while z:
            u = z.pop()
            topo.append(u)
            for v in R.pop(u):
                depdeg[v] -= 1
                if depdeg[v]==0:
                    z.append(v)
        circular = [k for k in config if k not in topo]
        assert not circular, f'Circular references: {circular}\n{config}'

        # Replace dependencies and save to self
        norep = ['num', 'tmp_program', 'in_or_out'] # future replacement, dont replace now
        for k in norep:
            config[k] = '{'+k+'}'

        for k in topo:
            config[k] = config[k].format_map(config)
        for k in norep:
            del config[k]
        config.update(nostr)
        return config

    def __getattr__(self, key):
        if key!='config' and self.config and key in self.config:
            value = self.config[key]
        else:
            value = object.__getattribute__(self, key)
        return value

    def format(self, fmt_str, **kwargs):
        return fmt_str.format(**self.config, **kwargs)

    def __repr__(self):
        if self.config:
            value = self.format('{platform} {id} ({language})')
        else:
            value = '{platform} {problem_id} ({language})'.format(**self.current)
        return value


class CPCP(ProblemLibrary):

    _process = None
    cache_file = '.cpcp.json'
    commands = [
        'Summary',
        'Open source code',
        'Test all',
        'Settings',
        'List in/out (ls)',
        'Quit',
        'Change language',
        'Change platform',
        'Change problem_id',
        'Download tool',
        'Delete empty testcases',
        'Create source from template',
        'Open statement',
        'Open templates',
        'Open problem folder',
        'New testcase',
        'Interrupt',
    ]

    async def start(self, UI=None):
        self.UI = UI or TerminalUI()
        if self.set_problem():
            tabs = [
                ('language', self.change_language),
                ('platform', self.change_platform),
                ('problem_id', self.change_problem_id),
            ]
            i = 0
            while i<3:
                self.UI.set_title(f'{self}')
                key, func = tabs[i]
                esc, errors = await func()
                if esc: i=max(0,i-1)
                elif key not in errors: i+=1
            self.UI.set_title(f'{self}')
        asyncio.ensure_future(
            self.interrupt_listener()
        )
        await self.main()


    async def main(self):
        self._process = None
        self.ls_update()
        self.UI.print('Directory:', os.getcwd())
        self.ls_print()
        while 1:
            options = [
                *self.commands,
                *[f'Test {f}' for f in self.ls['in']],
                *[f'Open {f}' for f in sum(self.ls.values(), [])],
            ]
            self.UI.set_title(f'{self}')
            self._waiting_command=True
            command = await self.UI.ask_multiple(
                message=None,
                options=options,
                placeholder='Type your command...',
            )
            self._waiting_command=False
            if command==None: continue
            if not self._process or not self._process.is_active():
                self.UI.clear()
            await self.handle(command)
        return

    async def interrupt_listener(self):
        while 1:
            await self.UI.wait_interrupt()
            if self._waiting_command:
                await self.interrupt()
        return

    async def handle(self, command):
        if command=='Quit':
            self.quit()

        elif command=='List in/out (ls)':
            self.ls_update()
            self.ls_print()

        elif command=='Summary':
            asyncio.ensure_future(
                self.run(self.ls['in'], summary=True)
            )

        elif command=='Test all':
            asyncio.ensure_future(
                self.run(self.ls['in'], summary=False)
            )

        elif command.startswith('Test '):
            asyncio.ensure_future(
                self.run([command[5:]], summary=False)
            )

        elif command=='Open statement':
            self.xdg_open(self.statement)

        elif command=='Open problem folder':
            self.xdg_open(self.path)

        elif command=='Open source code':
            self.xdg_open(self.source, touch=True)
            
        elif command=='Open templates':
            await self.open_templates()

        elif command.startswith('Open '):
            self.xdg_open(command[5:])

        elif command=='Interrupt':
            await self.interrupt()

        elif command=='Download tool':
            #asyncio.ensure_future(self.download())
            await self.download()

        elif command=='New testcase':
            await self.new_testcase()
            
        elif command=='Delete empty testcases':
            await self.ls_delete_empty()

        elif command=='Change language':
            esc, errors = await self.change_language()

        elif command=='Change platform':
            esc, errors = await self.change_platform()

        elif command=='Change problem_id':
            esc, errors = await self.change_problem_id()
            
        elif command=='Settings':
            self.xdg_open('settings.json')
            
        elif command=='Create source from template':
            self.create_source()

        else:
            print(f'Unknown command: {command}')
        return

    def _assert_config(func):
        def wrapper(self, *args, **kwargs):
            assert self.config, 'You must select a problem first'
            return func(self, *args, **kwargs)
        wrapper.__name__=func.__name__
        return wrapper

    @_assert_config
    async def execute(self, sample_in, sample_out, tmp_program=None, verbose=True):
        assert tmp_program or not self.compiler, 'You must compile first'
        cmd_exec = self.format(self.executer, tmp_program=tmp_program)
        cmd = f'{cmd_exec} < {sample_in}'
        self._process = MyProcess(cmd, shell=True)
        p = await self._process.async_run(
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

    @_assert_config
    async def run(self, inputs, summary=False):
        if self._process and self._process.is_active():
            await self.interrupt()
            self.UI.clear()
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
                veredict, exec_time = await self.execute(
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

    @_assert_config
    def ls_update(self):
        ls = {}
        for ext in ['in', 'out']:
            files = glob.glob(self.format('{path}/*') + f'.{ext}')
            empty = [f for f in files if not read_file(f).strip()]
            files = [f for f in files if f not in empty]
            files = sorted(files, key=lambda f: ('sample' not in f, my_order(f)))
            ls[ext] = files
            ls[ext+'_empty'] = empty
        self.ls = ls
        return

    @_assert_config
    def ls_print(self):
        self.UI.clear()
        self.UI.print('\nInput/output files and possible actions:\n')
        for x in self.ls['in']:
            self.UI.print(' + Test/open   ', x)
        for x in self.ls['out']:
            self.UI.print(' + Open        ', x)
        for x in self.ls['in_empty']+self.ls['out_empty']:
            self.UI.print(' + Open (empty)', x)
        if all(not v for k,v in self.ls.items()):
            self.UI.print('   No input/output files found locally.')
            self.UI.print('   Use the download tool!')
        return

    @_assert_config
    async def ls_delete_empty(self):
        for f in self.ls['in_empty']+self.ls['out_empty']:
            self.UI.print('Deleting', f, end='...')
            try: os.remove(f)
            except Exception as e: self.UI.print(e)
            else: self.UI.print('ok')
        self.UI.print('Done')

    @_assert_config
    def create_source(self, overwrite=False):
        self.create_path()
        self.UI.print(f'Creating {self.source} from template:')
        if os.path.exists(self.source):
            self.UI.print('    Skipping. File already exists.')
        elif os.path.exists(self.template):
            self.UI.print(f'    Copying {self.template}')
            MyProcess(['cp', self.template, self.source]).run()
            self.UI.print('Done')
        else:
            self.UI.print(f'    Setting empty file: template not found {self.template}')
            MyProcess(['touch', self.source]).run()
        return

    @_assert_config
    async def open_templates(self):
        fmt = self.settings.dirtree['template']
        self.UI.print(f'\nTemplates use the format "{fmt}"')
        self.UI.print('\nYour languages and extensions:')
        for x in self.settings.languages.values():
            self.UI.print('   + .{extension:6s} {language}'.format(**x))
        await self.UI.alert('You will access the templates folder. Read below for info on new templates.')
        self.create_path(self.config.templates_path)
        self.xdg_open(self.config.templates_path)

    @_assert_config
    async def interrupt(self):
        if not self._process or not self._process.is_active():
            self.UI.print('No active process to interrupt.')
        else:
            self.UI.print('Interrupting process...')
            await self._process.kill()
            self.UI.clear()
            self.UI.print('Process stopped')
            self.UI.print('-'*10)
        return

    @_assert_config
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

    @_assert_config
    async def download(self):
        #self.UI.print('Download not yet implemented')
        #return
        # Get url
        if hasattr(self, 'url'):
            url = self.url
        else:
            prefill = ''
            if os.path.exists(self.statement):
                prefill = read_file(self.statement)
                prefill = prefill[prefill.find('url='):]
                prefill = prefill[4:prefill.find('"')]
            url = self.UI.ask_string(
                '    Type the problem url (html or pdf) or q to cancel: ',
                prefill=prefill,
                check=lambda s: s.lower()=='q' or (s.startswith('http') and ' ' not in s.strip()), 
                msg='URL can not contain spaces and must start with http or https',
            ).strip()
            if url.lower()=='q':
                return

        # Save light statement file
        self.UI.print('\nCreating statement quick access...')
        self.UI.print(f'    Source:      {url}')
        self.UI.print(f'    Destination: {self.statement}')
        stmt = '<html><head><meta http-equiv="refresh" content="0; url={url}"/></head></html>'
        with open(self.statement, 'w') as f:
            f.write(stmt.format(url=url))

        sample_in = self.config.sample.replace('{in_or_out}', 'in')
        sample_out = self.config.sample.replace('{in_or_out}', 'out')
        # Save samples
        if hasattr(self, 'downloader'):
            self.UI.print(f'Dowloading sample io...')
            self.UI.print(f'    Source:      {url}')
            self.UI.print(f'    Destination: {sample_in}')
            self.UI.print(f'                 {sample_out}')
            try:
                prev = sys.stdout
                sys.stdout = self.UI
                await self.downloader(self)
            finally:
                sys.stdout = prev
        else:
            #self.cls()
            self.UI.print('URL:', url)
            msg=(f'\n    No download script found for {self.platform}'
                f'    I will help you to copy/paste the test cases manually.\n')
            self.UI.print
            if not await self.UI.ask_bool(msg+'\n Would yoy like to proceed?'):
                return
            if await self.UI.ask_bool(f'    Open statement?'):
                self.xdg_open(self.statement)
            num=1
            while 1:
                fname = sample_in.format(num=num)
                if await self.UI.ask_bool(f'Testcase {num}. Open {fname}?.'):
                    self.xdg_open(fname, touch=True)
                else:
                    break
                fname = sample_out.format(num=num)
                if await self.UI.ask_bool(f'Testcase {num}. Open {fname}?'):
                    self.xdg_open(fname, touch=True)
                else:
                    break
                num+=1
        return

    @_assert_config
    def create_path(self, path=None):
        if path==None: path=self.path
        self.UI.print(f'Creating dir {path}')
        MyProcess(['mkdir', '-p', path]).run()

    def xdg_open(self, path, touch=False):
        self.UI.print(f'Opening {path}...')
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

    async def change_language(self):
        language = await self.UI.ask_multiple(
            message='Choose a language',
            placeholder='Type...',
            options=[x for x in self.settings.languages],
        )
        esc = language==None
        errors = self.set_problem(language=language)
        if not esc and not errors:
            self.create_source()
        return esc, errors

    async def change_platform(self):
        platform = await self.UI.ask_multiple(
            message='Choose a platform',
            placeholder='Type...',
            options=[x for x in self.settings.platforms],
        )
        esc = platform==None
        errors = self.set_problem(platform=platform)
        if not esc and not errors:
            self.create_source()
        return esc, errors

    async def change_problem_id(self):
        def validator(problem_id):
            errors = self.set_problem(problem_id=problem_id)
            error = errors.get('problem_id')
            return error
        problem_id = await self.UI.ask_string(
            message=f'Type the problem_id',
            placeholder='Type...',
            validator=validator,
        )
        esc = problem_id==None
        errors = self.set_problem(problem_id=problem_id)
        if not esc and not errors:
            self.create_source()
        return esc, errors


def main():
    arg0, *args = sys.argv
    here = os.path.dirname(os.path.realpath(__file__))
    sysx = os.path.realpath(sys.executable)
    arg0 = os.path.realpath(arg0)
    host = here if sysx!=arg0 else os.path.dirname(arg0)
    
    os.chdir(host)

    cpcp = CPCP(os.path.join(here, 'default_settings.json'))
    mode = ('firefox-app' if not args else args[0]).lower()

    if mode=='cli':
        asyncio.ensure_future(cpcp.start(app))
    else:
        app = flx.App(MyApp)
        title = 'CPCP'
        icon = os.path.join(here, 'icon.png')
        GUI = app.launch(mode, title=title, icon=icon)
        asyncio.ensure_future(cpcp.start(GUI))
        #app.export('example.html', link=0)
        flx.run()

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
 + Updates system
 + Plugin system (move everything to a cpcp folder)
 + Fix long labels
 + let cpp match c++
 + Darker theme (or selectable)
 + Fix options spacing
'''