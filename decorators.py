import functools
import threading
import cerebrate_config as cc


def console_only(func):
    '''Decorator that rejects any Message not containing "console" in header.
    If rejected, returns an async function that retuns False.
    '''
    functools.wraps(func)
    def wrapper(msg):
        if "console" in msg.header:
            return func(msg)
        async def rejected():
            return False
        return rejected()
    return wrapper

def threaded(func):
    '''Decorator that runs the decorated function in a thread of its own.
    Decorated function cannot be async (asyncio).
    '''
    functools.wraps(func)
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        thread.start()
        def success():
            return True
        return success()
    return wrapper

def athreaded(func):
    '''Decorator that runs the decorated function in a thread of its own.
    Decorated function cannot be async (asyncio).
    Caller must use await when calling decorated function.
    '''
    functools.wraps(func)
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        thread.start()
        async def success():
            return True
        return success()
    return wrapper

def print_func_name(func):
    '''Decorator that prints the function name on enter (if cc.debug_in_effect is set).
    '''
    functools.wraps(func)
    def wrapper_print_func_name(*args, **kwargs):
        if cc.debug_in_effect:
            print("\n", func.__name__, "(", args, ", ", kwargs, ")\n")
        return func(*args, **kwargs)
    return wrapper_print_func_name