import asyncio
import sys
import os
from shutil import copyfile
import traceback
import functools
from collections import defaultdict
from aioconsole import ainput
import cerebrate_config as cc, mysysteminfo
from definitions import CEREBRATE_FILE_EXTENSIONS


async def prompt(prompt_string:str):
    '''Prints the given prompt_string and waits on user input.
    Returns user input.
    '''
    return await ainput(''.join(("\n\t", prompt_string, ": ")))

def aprint(*args):
    '''Attempts to print things with asynchronosity in mind to preserve and display current input.
    WIP
    '''
    current_input = ''
    print(*args)
    print(''.join(("\n)))", current_input)), end='')

def dprint(*args):
    '''If cc.debug_in_effect is set then will print given arguments, otherwise will do nothing.
    '''
    if cc.debug_in_effect:
        print(*args)

def move_file(current_path, destination_path):
    '''Moves a file from current_path to destination_path.
    Returns True if successful, False if not.
    '''
    if not os.path.exists(current_path):
        return False
    try:
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        os.replace(current_path, destination_path)
    except:
        traceback.print_exc()
        return False
    return True

def backup_file(file_path):
    '''Copies the given file to a backup folder in the same directory.
    Returns False if unable to.
    '''
    if not os.path.exists(file_path):
        return False
    location = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    destination = os.path.join(location, "backup")
    return copyfile(file_path, os.path.join(destination, filename))

def restore_file(file_path):
    '''Replaces the given file with its backup, if it exists.
    Returns False if unable to.
    '''
    location = os.path.dirname(file_path)
    if not os.path.exists(location):
        return False
    filename = os.path.basename(file_path)
    backup = os.path.join(location, "backup", filename)
    if not os.path.exists(backup):
        return False
    return copyfile(backup, file_path)

async def get_cerebrate_file_names():
    '''Returns a list of the names of files involved in cerebrate's execution.
    '''
    file_names = []
    source_directory = mysysteminfo.get_my_directory()
    for dirname, subdirnames, filenames in os.walk(source_directory):
        subdirnames = [subdir for subdir in subdirnames if 'backup' not in subdir]
        for filename in filenames:
            if 'backup' in filename:
                continue
            extension = os.path.splitext(filename)[1]
            if extension in CEREBRATE_FILE_EXTENSIONS:
                file_names.append(os.path.join(dirname, filename))
    return file_names

def intersect_strings(item_one:str, item_two:str, minimum_word_size:int=2):
    '''Intersects two strings to find matching sequences of characters (hopefully words).
    Returns a result dictionary containing an integer 'char_count' and list of matches 'result_strings'.
    '''
    item_one = item_one.lower()
    item_two = item_two.lower()
    intersect_result = {'char_count': 0, 'result_strings': []}
    item_one_start_index = 0
    while item_one_start_index < len(item_one):
        item_one_end_index = len(item_one)
        while item_one_end_index > item_one_start_index:
            possible_match = item_one[item_one_start_index:item_one_end_index]
            if len(possible_match) > minimum_word_size and possible_match in item_two:
                intersect_result['char_count'] += (item_one_end_index - item_one_start_index)
                intersect_result['result_strings'].append(possible_match)
                item_two = item_two.replace(possible_match, '', 1)
                item_one_start_index = item_one_end_index - 1
                break
            item_one_end_index -= 1
        item_one_start_index += 1
    return intersect_result

def get_greedy_match(match_string:str, possible_matches:list, minimum_word_size:int=2):
    '''Picks from possible_matches the string with the greediest matching with match_string and returns it.
    minimum_word_size is the floor for matching character sequences.
    Returns a dict containing "match" and "char_count".
    '''
    matches = defaultdict()
    for possible_match in possible_matches:
        result = intersect_strings(item_one=match_string, item_two=possible_match, minimum_word_size=minimum_word_size)
        matches[possible_match] = result.get("char_count", 0)
    if len(matches) <= 0:
        return {"match": None, "char_count": None}
    match = sorted(matches.items(), key=lambda x: x[1], reverse=True)[0]
    return {"match": match[0], "char_count": match[1]}

def run_coroutine(coroutine):
    '''Attempts to run the given coroutine in the current event loop.
    If there isn't one a temporary event loop is created to run the coroutine.
    Does not return anything.
    '''
    if not coroutine:
        return
    loop = None
    run_loop_manually = False
    try:
        loop = asyncio.get_event_loop()
    except:
        loop = asyncio.new_event_loop()
        run_loop_manually = True
    if run_loop_manually:
        loop.run_until_complete(coroutine)
    else:
        asyncio.ensure_future(coroutine)