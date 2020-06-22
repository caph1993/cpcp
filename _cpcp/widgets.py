from flexx import flx

class MyWidget(flx.Widget):

    def init(self):
        global eval
        super().init()
        self.sleep = eval("(t)=>new Promise(r=>setTimeout(r, t))")
        self.document = eval("document")


class MyLineEdit(flx.LineEdit):

    no_capture = [
        'ArrowUp', 'ArrowDown',
        'Enter', 'Escape', 'Tab',
    ]
    
    @flx.emitter
    def key_down(self, e):
        """Overload to avoid capturing and odd behaviour of special keys"""
        ev = self._create_key_event(e)
        if ev.key in self.no_capture:
            e.preventDefault()
        else:
            ev = super().key_down(e)
        return ev

class MyDots(flx.Label):
    def __init__(self, *args, **kwargs):
        kwargs['style']='''
        height:8px; max-height:8px; min-height:8px;
        display: inline-flex; align-items: center; 
        justify-content: center;
        background-color: #f8f8f8;
        border-color: #f8f8f8;
        color: #777;
        '''
        super().__init__(*args,**kwargs)

    def set_visible(self, visible):
        self.node.style.visibility='visible' if visible else 'hidden'


class MyPrompt(MyWidget):
    
    options = flx.ListProp([])
    n_options = flx.IntProp(5)
    ref = flx.StringProp('MyID')

    def init(self):
        super().init()
        self.label = {}
        with flx.VBox() as self.wmain:
            self.label['above'] = flx.Label(text='Text above')
            with flx.HBox():
                self.winput = MyLineEdit(flex=1)
            with flx.VBox():
                self.dots_above = MyDots(text='···')
                with flx.VBox() as self.woptions_box:
                    pass
                self.dots_below = MyDots(text='···')
        self.woptions = []
        self.show_more = 0
        self.index = 0
        self.shift = 0
        self.focus_element = self.winput

    @flx.emitter
    def emit_option(self, option):
        return dict(value=option, ref=self.ref, text=self.winput.text)
    @flx.emitter
    def emit_text(self, text):
        return dict(value=text, ref=self.ref)
    @flx.emitter
    def emit_escape(self):
        return dict(ref=self.ref)
    @flx.emitter
    def emit_interrupt(self):
        return dict(ref=self.ref)

    @flx.action
    def set_focus(self):
        self._set_focus()
    async def _set_focus(self):
        elem = self.focus_element
        while elem.node.offsetParent == None:
            await self.sleep(50)
        elem.node.focus()
        return
    
    async def select_text(self):
        await self.sleep(50)
        self.winput.node.select()
        return

    @flx.action
    def set_properties(self, kwargs):
        if 'prefill' in kwargs:
            self.winput.set_text(kwargs.pop('prefill'))
            self.select_text()
        if 'placeholder' in kwargs:
            self.winput.set_placeholder_text(kwargs.pop('placeholder'))
        for key in ['above']:
            if key in kwargs:
                value = kwargs.pop(key)
                elem = self.label[key]
                if value is None:
                    elem.set_text('hidden')
                    elem.node.hidden=True
                else:
                    elem.node.hidden=False
                    elem.set_text(value)
        if 'ref' in kwargs:
            self._mutate_ref(kwargs['ref'])
        keys = ['options', 'n_options']
        if any([key in kwargs for key in keys]):
            kw = kwargs
            kw['options'] = kw.get('options', self.options)
            kw['n_options'] = kw.get('n_options', self.n_options)
            self.set_options(kw.pop('options'), kw.pop('n_options'))
        for key, val in kwargs.items():
            print(f'Error: unhandled key={key}, val={val}')
        return

    @flx.action
    def set_options(self, options, n_options=None):
        if n_options==None: n_options=5
        if not self.winput: return
        self._mutate_options(options)
        self._mutate_n_options(n_options)
        self.pre_match = {}
        for s in self.options:
            self.pre_match[s] = self.my_grams(s)
        self.filtered = self.options
        self.index = 0
        self.shift = 0
        self.redraw_options()

    @flx.reaction('woptions_box.children*.pointer_click')
    def _listen_clicks(self, *events):
        for ev in events:
            self.listen_click(ev.source.text)
    def listen_click(self, option):
        self.winput.node.select() # Select text
        self.emit_option(option)
        self.options.remove(option)
        self.options.insert(0, option)
        self.index = 0
        self.shift = 0
        self.redraw_options()
        return

    @flx.reaction('key_down')
    def listen_keys(self, *events):
        for ev in events:
            if ev.modifiers=='Ctrl' and ev.key=='c' and self.winput.text=='':
                self.emit_interrupt()
            elif ev.modifiers:
                continue
            elif ev.key == 'Escape':
                self.emit_escape()
            elif ev.key == 'Enter':
                if len(self.woptions):
                    option = self.woptions[self.index].text
                    self.listen_click(option)
                else:
                    self.emit_text(self.winput.text)
            elif ev.key == 'ArrowDown':
                if self.index+1<len(self.woptions): self.index+=1
                elif self.shift+self.n_options<len(self.filtered): self.shift+=1
                self.redraw_options()
            elif ev.key == 'ArrowUp':
                redraw=True
                if self.index>0: self.index-=1
                elif self.shift: self.shift-=1
                else: redraw=False
                if redraw: self.redraw_options()
        return

    @flx.reaction('winput.text')
    def listen_winput(self, *events):
        if self.winput.text=='':
            self.filtered = self.options
        else:
            score = self.fuzzy_scores(self.winput.text)
            thr = max(max(score.values())/2, 1/3)
            self.filtered = sorted(
                [s for s in self.options if score[s]>thr],
                key=lambda s: -score[s],
            )
        self.index = 0
        self.shift = 0
        self.redraw_options()
        return

    def redraw_options(self):
        to_show = self.filtered[self.shift:self.shift+self.n_options]
        with self.woptions_box:
            while len(self.woptions) < len(to_show):
                self.woptions.append(flx.Button())
            while len(self.woptions) > len(to_show):
                self.woptions.pop().dispose()
        for i in range(len(to_show)):
            self.woptions[i].set_text(to_show[i])
            style = 'background:#ccc' if i==self.index else 'background:#eee'
            self.woptions[i].node.style = style
        if len(self.options)==1:
            self.winput.node.hidden=True
            self.focus_element = self.woptions[0]
        else:
            self.winput.node.hidden=False
            self.focus_element = self.winput
        self.dots_above.set_visible(self.shift>0)
        self.dots_below.set_visible(len(self.filtered)-self.shift>self.n_options)
        return

    def my_grams(self, s):
        n = len(s) ; s = s.lower() ; g = {}
        for i in range(n):
            g[s[i]] = (g[s[i]] or 0)+1
            if i+1<n: g[s[i]+s[i+1]] = (g[s[i]+s[i+1]] or 0) + 1
            if i+2<n: g[s[i]+s[i+2]] = (g[s[i]+s[i+1]] or 0) + 1
        return g

    def fuzzy_scores(self, text):
        x = self.my_grams(text)
        score = {}
        for key,y in self.pre_match.items():
            hits=total=0
            z = y.copy()
            for k,v in x.items():
                z[k] = (z[k] or 0)-x[k]
                hits += z[k]>=0
                total += 1
            score[key] = hits / total
        return score


class MyConsole(MyWidget):
    text = flx.StringProp('')

    def init(self):
        super().init(flex=1)
        self.wconsole = flx.MultiLineEdit(
            style=(
                'height:100%;'
                'width:100%;'
                'background:#222225;'
                'font-family: monospace;'
                'font-size: larger;'
                'color:white;'
                'overflow-y:scroll'
            )
        )
        self.scrolling = 0

    @flx.action
    def set_output(self, text):
        self.wconsole.set_text(text)
        self.bottom_scroll()
    @flx.action
    def append_output(self, text):
        self.set_output(self.wconsole.text+text)
    @flx.action
    def clear_output(self, text):
        self.wconsole.set_text('')

    async def bottom_scroll(self,text):
        # workaround for scrolling after element actually grows
        self.scrolling += 1
        if self.scrolling==1:
            elem = self.wconsole.node
            while self.scrolling > 0:
                await self.sleep(10)
                elem.scrollTop = elem.scrollHeight
                self.scrolling -= 1

