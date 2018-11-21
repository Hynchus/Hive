import asyncio
import cerebrate_config as cc
import copy

_loop = None

_queue = []
_coroutine_queued = asyncio.Event()


def initialize_async_queue(event_loop=None):
    '''Initializes the queue's loop. Must have a loop given or already running.
    Cannot be run multiple times.
    '''
    global _loop
    if _loop:
        return
    if not event_loop:
        event_loop = asyncio.get_event_loop()
    _loop = event_loop
    asyncio.ensure_future(_handle_queue(), loop=_loop)

async def _handle_queue():
    global _queue
    while not cc.my_state_event[cc.State.TERMINATING].is_set():
        await _coroutine_queued.wait()
        temp_queue = copy.deepcopy(_queue)
        _coroutine_queued.clear()
        for coroutine in temp_queue:
            _queue.remove(coroutine)
            asyncio.ensure_future(coroutine, loop=_loop)
        

def queue_coroutine(coroutine):
    '''Queues the given coroutine to be run in the current event_loop.
    Does not return anything.
    '''
    global _queue
    if not coroutine:
        return
    _queue.append(coroutine)
    _coroutine_queued.set()
