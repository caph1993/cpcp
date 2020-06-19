import readline, sys, os

class TerminalUI():

    def clear(self):
        os.system('cls' if os.name=='nt' else 'clear')

    def print(self, *args, end='\n', flush=True):
        self.write(' '.join(str(x) for x in args))
        self.write(end)
        self.flush()

    def write(self, data):
        sys.__stdout__.write(data)

    def flush(self):
        sys.__stdout__.flush()

    def ask_string(prompt, prefill='', check=None, msg=None):
        if check==None:
            check = lambda s: True
        readline.set_startup_hook(lambda: readline.insert_text(prefill))
        first = True
        while 1:
            try: s = input(prompt)
            finally: readline.set_startup_hook()
            if check(s):
                break
            if msg!=None:
                print(msg)
        return s

    def ask_yes_no(prompt, prefill='', default=None):
        def parse(s):
            if s.lower().startswith('y'): return True
            if s.lower().startswith('n'): return False
            if not s: return default
            return None
        opts = ['y/n', 'Y/n', 'y/N'][0+bool(default)+default!=None]
        prompt += ' [{opts}] '
        ans = ask_string(prompt, prefill=prefill,
            check=lambda s: parse(s)!=None,
            msg='Please type yes or no'
        )
        return parse(ans)
