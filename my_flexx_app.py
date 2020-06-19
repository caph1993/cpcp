from flexx import flx
from my_flexx_widgets import MyWidget, MyPrompt, MyConsole
from collections import deque
import asyncio, sys
from pynput.keyboard import Key, Controller # For document focus on creation

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
        self.js = MyApp_JS()
        self.term = flx.Dict(dq=deque(), size=0, sync=asyncio.Event(), max_size=10**5)
        self._interrupt = asyncio.Event()
        self._sync = asyncio.Event()
        self._data = None
        self.tabs_stack = []
        asyncio.ensure_future(self._post_init())
        asyncio.ensure_future(self._writer())
        return

    async def _post_init(self):
        while not self.js.ready:
            await asyncio.sleep(50e-3)
        keyboard = Controller()
        keyboard.press(Key.tab) # Focus document
        keyboard.release(Key.tab)

    @flx.action
    def set_title(self, title):
        self.js.set_title(title)

    @flx.reaction('js.emit_escape', mode='greedy')
    def listen_escape(self, *events):
        tab = self.current_tab()
        self.pop_tab()
        self._data = flx.Dict(value=None)
        self._sync.set()

    @flx.reaction('js.emit_text', 'js.emit_option', mode='greedy')
    def listen_prompt(self, *events):
        self._data = events[-1]
        self._sync.set()

    @flx.reaction('js.emit_interrupt', mode='greedy')
    def listen_interrupt(self, *events):
        self._interrupt.set()

    def print(self, *args, end='\n', flush=True):
        self.write(' '.join(str(x) for x in args))
        self.write(end)
        self.flush()

    def clear(self):
        self.js.clear_output()
        self.term.size = 0

    def write(self, data):
        self.term.dq.append(data)
        self.term.sync.set()

    def flush(self):
        pass

    async def _writer(self):
        while 1:
            if not self.term.dq:
                await self.term.sync.wait()
                self.term.sync.clear()
            data = self.term.dq.popleft()
            self.term.size += len(data)
            if self.term.size > self.term.max_size:
                div = '...\n---automatic crop. too much previous output---\n'
                self.js.set_output(div)
                data = data[-self.term.max_size:]
                self.term.size = len(data)
            self.js.append_output(data)

    async def ask_multiple(self,
            message, options, placeholder='', prefill='',
            n_options=5):
        tab = dict(
            options=options,
            above=message,
            prefill=prefill,
            placeholder=placeholder,
            n_options=n_options,
        )
        replace = str(self.current_tab())!=str(tab)
        if replace: self.push_tab(tab)
        self._sync.clear()
        await self._sync.wait()
        ans = self._data.value
        if replace: self.pop_tab()
        return ans

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

    async def ask_string(self, message, validator=None, **kwargs):
        error = ':)'
        while error:
            ans = await self.ask_multiple(
                message=message,
                options=[], **kwargs,
            )
            error = validator(ans) if ans!=None and validator else None
            if error:
                self.print(error)
        return ans

    async def wait_interrupt(self):
        await self._interrupt.wait()
        self._interrupt.clear()

    def current_tab(self):
        return self.tabs_stack and self.tabs_stack[-1]

    def push_tab(self, kwargs):
        '''Go to the given tab'''
        self.tabs_stack.append(kwargs)
        self.js.set_properties(kwargs)
        self.js.set_focus()

    def pop_tab(self):
        '''Go to previous tab if there is'''
        tab = self.tabs_stack.pop()
        if self.tabs_stack:
            tab = self.tabs_stack.pop()
        self.push_tab(tab)


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
