import ctypes

def terminate_thread(thread, exception=SystemExit):
    """
    https://stackoverflow.com/a/15274929/3671939
    Terminates a python thread from another thread.
    :param thread: a threading.Thread instance
    """
    if not thread.isAlive():
        return

    exc = ctypes.py_object(exception)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_long(thread.ident), exc)
    if res == 0:
        raise ValueError("nonexistent thread id")
    elif res > 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread.ident, None)
        raise SystemError("PyThreadState_SetAsyncExc failed") 


if __name__=='__main__':
    import time
    from threading import Thread
    def test1():
        for i in range(5):
            print(f'I am alive at {i}')
            time.sleep(1)
        return
    t=Thread(target=test1)
    t.start()
    time.sleep(1.5)
    terminate_thread(t, exception=KeyboardInterrupt)

    def test2():
        print('This is test2')
        t=Thread(target=test1)
        t.start()
        time.sleep(1.5)
        terminate_thread(t)
        print('End of test2')
        return
    t=Thread(target=test2)
    t.start()
    time.sleep(2.5)
    terminate_thread(t)

    print('BYE')
