from my_dict import Dict
from subprocess import (Popen, PIPE, DEVNULL, TimeoutExpired, CalledProcessError)
from tempfile import NamedTemporaryFile
from threading import Thread, Timer, Event
from queue import Queue, Empty
import sys, time, io, signal, asyncio

ON_POSIX = 'posix' in sys.builtin_module_names



class MyProcess():
    '''
    Tool for launching a process with support for live stdout/stderr
    handling, as well as timeout, custom input and stdout/stderr
    capturing/non-caputring.
    Uses threads and queues.

    Arguments:
        args: arguments passed to Popen
        shell: passed to Popen
        input: string that simulates stdin
        timeout: None or float timeout in seconds
        check: bool. If true and an error ocurred, throws an exception
        capture_stdout: bool. If true, output is assigned to 'self.stdout'
        live_stdout: None, io.BufferedWriter instance, or any object
            with methods write and flush. If given, write(line) and flush()
            are called for each line of stdout as soon as it is received
            (as soon as the program flushes), with a maximum delay of
            'micro_delay'.
        timeout_stdout: None (infinity) or float. Time in seconds to
            wait for the live_stdout handler after the process terminates.
            Recall that the live_stdout handler may still have some
            remaining lines to handle once the process finishes.
            The additional time will not affect 'self.elapsed'.
        max_stdout: None, int or string. If more than max_stdout bytes
            are received, the process is killed. Notice that if capturing
            and live_stdout are disabled, no bytes will be received at all.
            Accepts string of the form '#', '#k', '#M', '#G', '#T'.
        capture_stderr: (see capture_stdout)
        stderr_handler: (see stdout_handler)
        wait_stderr_handler: (see wait_stdout_handler)
        max_stderr: (see max_stdout)
        encoding: string used for encoding/decoding stdin/stdout/stderr
        micro_delay: float seconds (see stdout_handler)
        block: bool. Blocks the current thread unitl the process finishes.
            If false, you must call wait()

    Returns None but sets:
        self.stdout: string, stdout of the process (if captured)
        self.stderr: string, stderr of the process (if captured)
        self.elapsed: float, approximate elapsed time of the process
            in seconds.
        self.timeout: float, copy of the timeout argument
        self.error: None or string, either 'TimeoutExpired',
            'ExcessOfOutput', 'KeyboardInterrupt',
            'NonZeroExitCode #', or an unexpected exception as string.
        self.returncode: int, exit code of the process
    '''

    def __init__(self, args, shell=False):
        kwargs = locals()
        kwargs.pop('self')
        self.kwargs = Dict(kwargs)

    def run(self, input=None, timeout=None, check=False,
            capture_stdout=False, live_stdout=None,
            timeout_stdout=None,   max_stdout=None,
            capture_stderr=False, live_stderr=None,
            timeout_stderr=None,   max_stderr=None,
            encoding='utf-8', micro_delay=1e-3):
        kwargs = locals()
        kwargs.pop('self')
        self.kwargs.update(kwargs)
        self._start()
        try:
            self._sync.wait()
        except KeyboardInterrupt:
            self._error = 'KeyboardInterrupt'
        except Exception as e:
            self._error = str(e)
        self._sync.wait()
        if check and self.error:
            kw = dict(returncode=self.returncode, cmd=self.kwargs.args)
            raise CalledProcessError(**kw)
        return self

    async def async_run(self, input=None, timeout=None, check=False,
            capture_stdout=False, live_stdout=None,
            timeout_stdout=None,   max_stdout=None,
            capture_stderr=False, live_stderr=None,
            timeout_stderr=None,   max_stderr=None,
            encoding='utf-8', micro_delay=1e-3):
        kwargs = locals()
        kwargs.pop('self')
        self.kwargs.update(kwargs)
        self._start()
        await self._async.wait()
        if check and self.error:
            kw = dict(returncode=self.returncode, cmd=self.kwargs.args)
            raise CalledProcessError(**kw)
        return self

    def run_detached(self, input=None, timeout=None, check=False,
            capture_stdout=False, live_stdout=None,
            timeout_stdout=None,   max_stdout=None,
            capture_stderr=False, live_stderr=None,
            timeout_stderr=None,   max_stderr=None,
            encoding='utf-8', micro_delay=1e-3):
        kwargs = locals()
        kwargs.pop('self')
        self.kwargs.update(kwargs)
        self._start()
        return self

    def _start(self):
        self._done=False
        self._stop=False
        self._error=None
        self._timeout=self._parse_time(self.kwargs.timeout, None)
        self._micro_delay=self.kwargs.micro_delay
        self._encoding=self.kwargs.encoding
        self._max_stdout=self._parse_eng(self.kwargs.max_stdout)
        self._max_stderr=self._parse_eng(self.kwargs.max_stderr)
        self._timeout_stdout=self._parse_time(self.kwargs.timeout_stdout, float('inf'))
        self._timeout_stderr=self._parse_time(self.kwargs.timeout_stderr, float('inf'))
        self._threads={}
        self._check=self.kwargs.check
        self._sync=Event()
        self._async=asyncio.Event()

        self._threads['waiter'] = Thread(target=self._waiter)
        if self._timeout:
            self._threads['timer'] = Timer(self._timeout, self._terminate)

        config = {
            'out': {
                'capture': self.kwargs.capture_stdout,
                'live': self.kwargs.live_stdout,
                'wait': self._timeout_stdout,
                'max_size': self._max_stdout,
            },
            'err': {
                'capture': self.kwargs.capture_stderr,
                'live': self.kwargs.live_stderr,
                'wait': self._timeout_stderr,
                'max_size': self._max_stderr,
            },
        }

        for key,val in config.items():
            piped = val['capture'] or val['live']
            val['pipe'] = PIPE if piped else DEVNULL
        
        self._start = time.time()
        try:
            self._process = Popen(
                self.kwargs.args, shell=self.kwargs.shell,
                stdin=PIPE,
                stdout=config['out']['pipe'],
                stderr=config['err']['pipe'],
                bufsize=1, close_fds=ON_POSIX,
            )
        except FileNotFoundError as e:
            self._stop=True
            self._done=True
            self._sync.set()
            self._async.set()
            self.error=str(e)
            if self.kwargs.check:
                raise
            return
        if self.kwargs.input!=None:
            self._process.stdin.write(self.kwargs.encode(encoding))
        self._process.stdin.close()

        config['out']['source'] = self._process.stdout
        config['err']['source'] = self._process.stderr
        
        self._buffer_stdout = io.StringIO() if config['out']['capture'] else None
        config['out']['buffer'] = self._buffer_stdout
        self._buffer_stderr = io.StringIO() if config['err']['capture'] else None
        config['err']['buffer'] = self._buffer_stderr

        for key, val in config.items():
            queues = [] ; h = {}
            if val['capture']:
                h['capture'] = dict(ostream=val['buffer'], flush=False, wait=float('inf'))
            if val['live']:
                h['handler'] = dict(ostream=val['live'], flush=True, wait=val['wait'])
            for name, kwargs in h.items():
                queues.append(Queue())
                self._threads[f'std{key}_{name}'] = Thread(
                    target=self._live_handler, args=[queues[-1]], kwargs=kwargs,
                )
            if queues:
                self._threads[f'{key}-main'] = Thread(
                    target=self._non_blocking_reader,
                    kwargs=dict(istream=val['source'], queues=queues, max_size=val['max_size'])
                )

        for key, t in self._threads.items():
            t.start()
        return

    def _waiter(self):
        try:
            while not self._stop:
                if self._process.poll()!=None: self._stop=True
                else: time.sleep(self._micro_delay)
            
            if self._process.stdout: self._process.stdout.close()
            if self._process.stderr: self._process.stderr.close()
            
            def get_value(buffer):
                if buffer==None: return None
                value = buffer.getvalue()
                buffer.close()
                return value

            self._end = time.time()
            if 'timer' in self._threads:
                self._threads['timer'].cancel()

            self.stdout = get_value(self._buffer_stdout)
            self.stderr = get_value(self._buffer_stderr)
            self.elapsed = self._end - self._start
            self.timeout = self._timeout
            self.returncode = self._process.wait()
            if self._error:
                self.error = self._error
            elif self.returncode!=0:
                self.error = f'NonZeroExitCode {self.returncode}'
            else:
                self.error = None
            for key, t in self._threads.items():
                if key!='waiter': t.join()
        finally:
            self._done=True
            self._sync.set()
            self._async.set()
        return

    def _terminate(self):
        self._threads['timer'].cancel()
        self._process.kill()
        self._stop = True
        self.error = 'TimeoutExpired'
        return

    def _non_blocking_reader(self, istream, queues, max_size):
        #https://stackoverflow.com/a/4896288/3671939
        for line in iter(istream.readline, b''):
            max_size -= len(line)
            if max_size<0:
                self._stop = True
                self._error = 'ExcessOfOutput'
            if self._stop: break
            line = line.decode(self._encoding)
            for q in queues: q.put(line)
        return istream.close()

    def _live_handler(self, queue, ostream, flush, wait):
        waiting = False
        waiting_start = None
        while not self._stop or waiting:
            try:
                elem = queue.get(timeout=self._micro_delay)
            except Empty:
                waiting = False
            else:
                ostream.write(elem)
                if flush: ostream.flush()
            if self._stop:
                if waiting_start==None:
                    waiting_start = time.time()
                    waiting = True
                if time.time() - waiting_start > wait:
                    waiting = False
        return

    def _parse_eng(self, x):
        units={'k':1e3, 'M':1e6, 'G':1e9, 'T':1e12}
        if x==None: return float('inf')
        elif isinstance(x, int): return x
        elif isinstance(x, float): return round(x)
        elif x.isdigit(): return int(x)
        else: return int(x[:-1])*int(units[x[-1]])

    def _parse_time(self, x, ifNone):
        return ifNone if x==None else x
    
    def is_active(self):
        return self._done==False

    async def kill(self):
        if self.is_active():
            self._stop = True
            self._error = 'KilledByUser'
        self._process.kill()
        while not self._done:
            await asyncio.sleep(1e-3)


class CustomOStream(io.BufferedWriter):
    def __init__(self, write_function, flush_function=None):
        self.write = write_function
        self.flush = flush_function or (lambda:0)
        self.tmp=NamedTemporaryFile('r', suffix='.out')
        self.fileno = self.tmp.fileno # Provide a dummy fileno

    def __del__(self):
        self.tmp.close()
        object.__del__(self)


class TemporaryStdout(io.RawIOBase):
    '''
    Replace stdout temporarily with another stream
    '''
    def __enter__(self):
        self.prev = sys.stdout
        sys.stdout = self

    def __exit__(self, *args):
        sys.stdout = self.prev


if __name__=='__main__':
    exit(0)
    # Testing mode
    cmd1 = ' && '.join(f'sleep 0.25 && echo "{i} "' for i in range(4))
    cmd2 = "python3 -c 'import time; [print(i, flush=True) or time.sleep(0.25) for i in range(4)] ; print(input().upper());'"
    cmd3 = "python3 -c 'import time; [print(i, flush=True) or time.sleep(0.25) for i in range(4)] ; print(input().upper()); exit(1)'"
    cmd4 = "python3 -c 'for i in range(10**6): print(str(0)*i, flush=True)'"

    tests = [
        {
            'title': 'No live printing, no error and capture stdout',
            'cmd': cmd1,
            'kwargs': dict(shell=True, timeout=None)
        },
        {
            'title': 'Print 1..4 (live), no error and capture stdout',
            'cmd': cmd1,
            'kwargs': dict(
                shell=True,
                timeout=1.1,
                stdout_handler=sys.stdout,
            )
        },
        {
            'title': 'Print 1..4 (live), no error and do not capture stdout',
            'cmd': cmd1,
            'kwargs': dict(
                shell=True,
                timeout=1.1,
                stdout_handler=sys.stdout,
                capture_stdout=False,
            )
        },
        {
            'title': 'Print 1..? (live), Timeout error, capture stdout',
            'cmd': cmd1,
            'kwargs': dict(
                shell=True,
                timeout=0.6,
                stdout_handler=sys.stdout,
                capture_stdout=True,
            )
        },
        {
            'title': 'Live printing, Timeout error, no capture, wait for handler',
            'cmd': cmd2,
            'kwargs': dict(
                shell=True,
                timeout=0.6,
                stdout_handler=lambda s: print(s, end='', flush=True) or time.sleep(0.6),
                #wait_stdout_handler=False,
                capture_stdout=False,
            )
        },
        {
            'title': 'Live printing, Excess of Output',
            'cmd': cmd4,
            'kwargs': dict(
                shell=True,
                stdout_handler=sys.stdout,
                max_stdout='1k',
            )
        },
    ]
    for i,test in enumerate(tests):
        print('-'*10, f'TEST {i+1}', '-'*10)
        print(test['title'])
        p = MyProcess(test['cmd'], **test['kwargs'])
        print('Elapsed:', p.elapsed)
        print('Error:', p.error)
        print('Stdout:', p.stdout)

    #MyProcess(['cat', 'z'])

