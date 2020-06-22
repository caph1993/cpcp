from collections import deque
import asyncio, threading


class MyFIFO:
    '''
    push and pop must be called from the same loop
    '''
    def __init__(self, dq=[]):
        self.dq = deque(dq)
        self._new = asyncio.Event()
        self._rem = threading.Condition()
        self._npop = 0
    
    def push(self, elem):
        self.dq.append(elem)
        self._new.set()
    
    def push_fn(self, action, *args, **kwargs):
        self.push((action, args, kwargs))

    async def pop(self):
        while not self.dq:
            await self._new.wait()
            self._new.clear()
        with self._rem:
            first = self.dq.popleft()
            self._npop += 1
            self._rem.notify_all()
        return first

    def clear(self):
        with self._rem:
            self.dq = deque([])
            self._rem.notify_all()

    def wait_flush(self):
        '''
        Wait for current elements in self to be poped
        '''
        n = self._npop + len(self.dq)
        while self._npop < n:
            with self._rem:
                self._rem.wait()
        return

    def __len__(self):
        return len(self.deque)
