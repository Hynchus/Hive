import os
import enum
import asyncio
import mysysteminfo
import shelve


CEREBRATE_CONFIG_PATH = os.path.join(mysysteminfo.get_hive_directory(), 'cerebrate_config.db')

class Config_Keys(enum.Enum):
    debug_in_effect = "debug"


my_version = 0.46

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

# Config values (frequently checked)
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

def set_config(config_key:str, config_value):
    with shelve.open(CEREBRATE_CONFIG_PATH, writeback=True) as db:
        db[config_key] = config_value
    set_frequent_config_keys(config_key, config_value)

def get_config(config_key:str):
    with shelve.open(CEREBRATE_CONFIG_PATH, flag='r') as db:
        if config_key in db:
            value = db[config_key]
            return value
        else:
            return False

def set_frequent_config_keys(config_key:str, config_value):
    if config_key == Config_Keys.debug_in_effect:
        debug_in_effect = config_value

def load_frequent_config_keys():
    with shelve.open(CEREBRATE_CONFIG_PATH, flag='r') as db:
        debug_in_effect = db.get(Config_Keys.debug_in_effect, False)

change_my_state(state=State.INITIALIZING)
accept_audio_control.clear()