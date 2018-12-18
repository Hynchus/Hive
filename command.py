import os
import sys
import enum
import functools
import traceback
from importlib import import_module, util
from utilities import aprint, dprint, intersect_strings
from definitions import Command
from communication import distill_msg
from commands import emit, info, system, web, media_player
import cerebrate_config as cc, mysysteminfo


COMMANDS_DIRECTORY = os.path.join(mysysteminfo.get_my_directory(), "commands")


command_modules = []


async def _shutdown_(msg):
    return "'shutdown' not implemented yet"

async def _shut_down_(msg):
    return _shutdown_(msg)

async def _start_(msg):
    return "'start' not implemented yet"

async def _stop_(msg):
    return "'stop' not implemented yet"

async def _what_(msg):
    return "'what' not implemented yet"

#async def _location_(msg):
#    return "'location' not implemented yet"

def format_header(header):
    formatted_header = []
    for cmd in header:
        formatted_command = cmd.replace(".", " ")
        formatted_command = formatted_command.lower()
        formatted_command = formatted_command.replace(",", " ")
        formatted_command = formatted_command.replace(" ", "_")
        formatted_header.append(formatted_command)
    return formatted_header

def format_command(cmd):
    formatted_command = cmd.replace(".", " ")
    formatted_command = formatted_command.lower()
    formatted_command = formatted_command.replace(",", " ")
    formatted_command = formatted_command.split(" ")
    formatted_command = ''.join([''.join(("_", item, "_")) for item in formatted_command])
    return formatted_command

def get_all_commands():
    '''Generator for all possible commands.
    Yields module_name, command_key, command_dict tuple.
    '''
    for module_name in command_modules:
        module = sys.modules[module_name]
        for command_key, command_dict in module._commands.items():
            yield module_name, command_key, command_dict

async def run_command(msg):
    if cc.my_state_event[cc.State.TERMINATING].is_set():
        return False
    cc.change_my_state(state=cc.State.COORDINATING)
    formatted_command = format_command(cmd=msg.data)
    for module_name, command_key, command_dict in get_all_commands():
        if command_key in formatted_command:
        #if intersect_strings(command_key, formatted_command).get("char_count", 0) >= 2:
        # test = command_key.split(" ")
        # try:
        #     answer = set(test).issubset(set(formatted_command))
        # except:
        #     traceback.print_exc()
        # if answer:
            #actually run the command
            dprint(command_key)
            module_function = getattr(sys.modules[module_name], command_dict[Command.FUNCTION])
            result = await module_function(msg)
            if result != False:
                cc.change_my_state(state=cc.State.LISTENING)
                return result
    aprint("I don't know what you mean by \'", msg.data, "\'.")
    cc.change_my_state(state=cc.State.LISTENING)
    return False

def load_commands():
    global command_modules
    dprint("Loading commands...")
    command_modules = []
    for module_filename in os.listdir(COMMANDS_DIRECTORY):
        module_name, extension = os.path.splitext(module_filename)
        if "__init__" in module_name or extension != ".py":
            continue
        try:
            #import module
            #module = import_module(os.path.join(COMMANDS_DIRECTORY, module_filename))
            #spec = util.spec_from_file_location(os.path.splitext(module_filename)[0], os.path.join(COMMANDS_DIRECTORY, module_filename))
            #dprint(spec)
            #mod = util.module_from_spec(spec)
            #spec.loader.exec_module(mod)
            #dprint(mod.__name__)
            #mod = sys.modules[mod.__name__]
            #collect module's commands
            mod_path = '.'.join((os.path.basename(COMMANDS_DIRECTORY), module_name))
            mod = sys.modules[mod_path]
            if mod._commands != None:
                dprint(mod_path, " commands: ", mod._commands)
                command_modules.append(mod_path)
        except Exception as _:
            traceback.print_exc()

load_commands()