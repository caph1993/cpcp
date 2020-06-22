from flexx import flx
from .widgets import MyWidget, MyPrompt, MyConsole
from collections import deque
import asyncio, sys, threading, time
from pynput.keyboard import Key, Controller # For document focus on creation
from .utils._dict import Dict
from .utils._fifo import MyFIFO

class MyApp_JS(MyWidget):
    ready = flx.BoolProp(False)

    def init(self):
        super().init()
        with flx.VBox():
            self.wtitle = flx.Label()
            self.wprompt = MyPrompt()
            self.wconsole = MyConsole(flex=1)
        self._init_focus()
        self._init_ready()
        return

    async def _init_focus(self):
        while self.document.hasFocus()==False:
            await self.sleep(50)
        self.wprompt.set_focus()
        return

    async def _init_ready(self):
        while not self.wtitle or not self.wprompt or not self.wconsole:
            await self.sleep(50)
        self._mutate_ready(True)
        return

    @flx.emitter
    def emit_option(self, event):
        return event
    @flx.emitter
    def emit_text(self, event):
        return event
    @flx.emitter
    def emit_escape(self, event):
        return event
    @flx.emitter
    def emit_interrupt(self, event):
        return event

    @flx.reaction('wprompt.emit_option', mode='greedy')
    def listen_option(self, *events):
        return self.emit_option(events[-1])
    @flx.reaction('wprompt.emit_text', mode='greedy')
    def listen_text(self, *events):
        return self.emit_text(events[-1])
    @flx.reaction('wprompt.emit_escape', mode='greedy')
    def listen_escape(self, *events):
        return self.emit_escape(events[-1])
    @flx.reaction('wprompt.emit_interrupt', mode='greedy')
    def listen_interrupt(self, *events):
        return self.emit_interrupt(events[-1])

    @flx.action
    def set_focus(self):
        self.wprompt.set_focus()
    @flx.action
    def set_output(self, text):
        self.wconsole.set_output(text)
    @flx.action
    def append_output(self, text):
        self.wconsole.append_output(text)
    @flx.action
    def clear_output(self, text):
        self.wconsole.clear_output(text)
    @flx.action
    def set_properties(self, kwargs):
        self.wprompt.set_properties(kwargs)
    @flx.action
    def set_title(self, text):
        if self.ready:
            self.wtitle.set_text(text)


class MyApp(flx.PyComponent):

    def init(self):
        self.ready = False
        self.js = MyApp_JS()
        self._interrupt = threading.Event()
        self.term = flx.Dict(fifo=MyFIFO(), size=0, max_size=10**5)
        self.prompts = flx.Dict(fifo=MyFIFO(), ans=MyFIFO(), results={})
        self.actions = MyFIFO()
        asyncio.ensure_future(self._post_init())
        return

    async def _post_init(self):
        while not self.js.ready:
            await asyncio.sleep(50e-3)
        keyboard = Controller()
        keyboard.press(Key.tab) # Focus document
        keyboard.release(Key.tab)
        asyncio.ensure_future(self._writer())
        asyncio.ensure_future(self._prompter())
        asyncio.ensure_future(self._actioner())

    def wait_ready(self):
        while not self.js.ready:
            time.sleep(50e-3)

    @flx.action
    def _set_title(self, title):
        self.js.set_title(title)
    def set_title(self, title):
        self.actions.push_fn(self._set_title, title)

    @flx.reaction('js.emit_escape', mode='greedy')
    def listen_escape(self, *events):
        self.prompts.ans.push(None)

    @flx.reaction('js.emit_text', 'js.emit_option', mode='greedy')
    def listen_prompt(self, *events):
        self.prompts.ans.push(events[-1].value)

    @flx.reaction('js.emit_interrupt', mode='greedy')
    def listen_interrupt(self, *events):
        self._interrupt.set()

    def print(self, *args, end='\n', flush=None):
        self.write(' '.join(str(x) for x in args))
        self.write(end or '')
        if flush or (flush==None and end=='\n'):
            self.flush()

    def clear(self):
        self.term.fifo.clear()
        self.term.fifo.push(None)

    def write(self, data):
        self.term.fifo.push(data)

    def flush(self):
        self.term.fifo.wait_flush()

    async def _writer(self):
        while 1:
            data = await self.term.fifo.pop()
            if data==None:
                self.term.size = 0
                self.js.clear_output()
            else:
                self.term.size += len(data)
                if self.term.size > self.term.max_size:
                    div = '...\n---automatic crop. too much previous output---\n'
                    self.js.set_output(div)
                    data = data[-self.term.max_size:]
                    self.term.size = len(data)
                self.js.append_output(data)
        return

    async def _prompter(self):
        prev = None
        while 1:
            tab, ref, sync = await self.prompts.fifo.pop()

            curr = str(tab)
            if curr!=prev:
                self.js.set_properties(tab)
                self.js.set_focus()
                prev = curr
            
            self.prompts.ans.clear()
            ans = await self.prompts.ans.pop()
            self.prompts.results[ref] = ans
            sync.set()
        return

    async def _actioner(self):
        while 1:
            action, args, kwargs = await self.actions.pop()
            action(*args, **kwargs)
        return

    def prompt(self, message, options,
            placeholder='', prefill='', n_options=5):
        tab = dict(
            options=options,
            above=message,
            prefill=prefill,
            placeholder=placeholder,
            n_options=n_options,
        )
        self.wait_ready()
        ref = time.time()
        sync = threading.Event()
        self.prompts.fifo.push((tab, ref, sync))
        sync.wait()
        ans = self.prompts.results.pop(ref)
        return ans

    def prompt_bool(self, message, default=True):
        options = ['Yes', 'No'] if default==True else ['No', 'Yes']
        ans = self.prompt(message=message, options=options)
        return {'Yes':True, 'No':False}.get(ans)

    async def ask_bool(self, message, default=True, **kwargs):
        options = ['Yes', 'No'] if default==True else ['No', 'Yes']
        ans = await self.ask_multiple(
            message=message,
            options=options,
            **kwargs,
        )
        return ans=='Yes'

    async def alert(self, message):
        await self.ask_multiple(message=message, options=['OK'])
        return

    def get_input(self, message, validator=None, **kwargs):
        error = ':)'
        while error:
            ans = self.prompt(
                message=message,
                options=[], **kwargs,
            )
            error = validator(ans) if ans!=None and validator else None
            if error:
                self.print(error)
        return ans

    def wait_interrupt(self):
        self._interrupt.wait()
        self._interrupt.clear()


if __name__=='__main__':
    _, *args = sys.argv
    app = flx.App(MyGUI_PY)

    title = 'Amigo CPCP'
    icon = 'icon.ico'
    if args and args[0].endswith('browser'):
        app.launch(args[0], title=title, icon=icon)
    else:
        app.launch('app', title=title, icon=icon)
    #app.export('example.html', link=0)
    flx.run()
