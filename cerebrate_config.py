import enum
import asyncio

MY_VERSION = 0.45

COMMAND = "cmd"
REMOTE_COMMAND = "remotecmd"
FILE_TRANSFER = "filetransfer"
CLOSE_CONNECTION = "close connection"

RECIPROCATE = "reciprocate"
OVERRULE = "overrule"

SUCCESS = "success"
READY = "ready"
FINISHED = "finished"

LOCATION = "location"
NAME = "name"

# Operation flags
update_in_progress = False
restart_cerebrate_on_terminate = False

# Config flags
__feedback_on_commands = 0   # If anything above 0 returns True, otherwise False (feedback_on_commands())
debug_in_effect = False


class FileLocation(enum.Enum):
    SOURCE = enum.auto()
    HIVE = enum.auto()
    ABSOLUTE = enum.auto()

class State(enum.Enum):
    INITIALIZING = enum.auto()
    LISTENING = enum.auto()
    COORDINATING = enum.auto()
    TERMINATING = enum.auto()

accept_audio_control = asyncio.Event()

my_state = State.INITIALIZING
my_state_event = {State.INITIALIZING: asyncio.Event(),
            State.LISTENING: asyncio.Event(),
            State.COORDINATING: asyncio.Event(),
            State.TERMINATING: asyncio.Event()}

def change_my_state(state: State):
    global my_state
    global my_state_event
    if my_state == State.TERMINATING:
        return
    my_state = state
    for flag in my_state_event:
        if flag == state:
            my_state_event[flag].set()
        else:
            my_state_event[flag].clear()

def feedback_on_commands(vote:bool=None):
    '''If 'vote' is given, votes for whether cerebrate should give feedback.
    Returns True or False for whether feedback has been voted yes or not.
    '''
    global __feedback_on_commands
    if vote != None:
        if vote:
            __feedback_on_commands += 1
        else:
            __feedback_on_commands -= 1
    return __feedback_on_commands > 0


change_my_state(state=State.INITIALIZING)
accept_audio_control.clear()