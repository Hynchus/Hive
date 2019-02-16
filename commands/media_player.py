import vlc
import pafy
from urllib.parse import urlparse
import time
import validators
from decorators import threaded, athreaded
from definitions import Command
from utilities import get_greedy_match
from feedback import feedback
import pyperclip
import streamlink


_commands = {
    '_play_': {Command.NAME: 'Start media playback', Command.DESCRIPTION: 'Starts playing the media link currently in clipboard', Command.USE: 'play media', Command.FUNCTION: "open"},
    '_stop_': {Command.NAME: 'Stop media playback', Command.DESCRIPTION: 'Stops the specified media', Command.USE: 'stop [identifier]', Command.FUNCTION: "close"}
}

_active_instance = None
_active_player = None


def _create_vlc_player():
    global _active_instance
    global _active_player
    instance_args = ['--video-on-top', '--play-and-exit']
    #if timeout > 0:
        #instance_args.append('--stop-time')
        #instance_args.append(str(timeout))
    _active_instance = vlc.Instance(instance_args)
    _active_player = _active_instance.media_player_new()
    _active_player.set_fullscreen(True)
    return _active_player

def get_media_player():
    global _active_player
    if _active_instance and _active_player:
        player = _active_player
    else:
        player = _create_vlc_player()
        _active_player = player
    return player

def _is_url(input:str):
    return validators.url(input)

def _set_player_media(content:str):
    global _active_instance
    player = get_media_player()
    try:
        media = _active_instance.media_new(content)
    except:
        media = _active_instance.media_new_path(content)
    media.get_mrl()
    player.set_media(media)

def _play_youtube_video(url:str, identifier:str=None):
    vid = pafy.new(url).getbest()
    _set_player_media(content=vid.url)
    get_media_player().play()
    
def _trigger_flag(self, flag):
    flag = 1

def _set_youtube(link:str):
    try:
        vid = pafy.new(link).getbest()
        _set_player_media(content=vid.url)
        return True
    except:
        ''' Not Youtube '''
    return False

def _set_stream(link:str):
    try:
        streams = streamlink.streams(link)
        stream = streams["best"]
        _set_player_media(content=stream.url)
        return True
    except:
        ''' Not a stream '''
    return False

def _set_local(link:str):
    try:
        _set_player_media(content=link)
        return True
    except:
        ''' Not a local file '''
    return False

def _play_media(link:str):
    ''' Attempts to parse and play the media at the given link. '''
    success = False
    if not success:
        success = _set_youtube(link=link)
    if not success:
        success = _set_stream(link=link)
    if not success:
        success = _set_local(link=link)
    if not success:
        return False
    #end_reached_flag = 0
    #Not catching the event for some reason
    #player.event_manager().event_attach(vlc.EventType().MediaPlayerEndReached, _trigger_flag, end_reached_flag)
    player = get_media_player()
    player.play()
    try:
        # If it's a stream we need to do this
        time.sleep(1)   # This is bad, would be better if we could catch the MediaPlayerEndReached event
        stream = player.media.subitems().item_at_index(0)
        player.set_media(stream)
        player.play()
        stream.release()
    except:
        '''This wasn't a stream'''
    return True

def close_media():
    global _active_instance
    global _active_player
    get_media_player().stop()
    _active_instance = None
    _active_player = None

@threaded
def play_video(url:str, identifier:str=None):
    '''Plays the video found at given URL in a standalone media player.
    Currently throws exceptions on invalid input.
    '''
    feedback("Starting up '", identifier, "'")
    #if "youtubetest" in urlparse(url).netloc.lower():
    #    _play_youtube_video(url=url, identifier=identifier)
    #else:
    if validators.url(url):
        _play_media(link=url)

def stop_media():
    if _active_player:
        _active_player.stop()
    # if identifier not in active_players:
    #     return False
    # active_players[identifier].stop()
    # active_players.pop(identifier)
    # return True

@athreaded
def open(msg):
    _play_media(pyperclip.paste())

@athreaded
def close(msg):
    #identifier = msg.data.lower().split('stop', 1)[1].strip()
    #full_identifier = get_greedy_match(match_string=identifier, possible_matches=active_players.keys())["match"]
    #if full_identifier == None:
        #return False
    return close_media()