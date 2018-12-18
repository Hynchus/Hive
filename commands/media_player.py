import vlc
import pafy
from urllib.parse import urlparse
import time
from decorators import threaded, athreaded
from definitions import Command


_commands = {
    '_stop_': {Command.NAME: 'Stop media playback', Command.DESCRIPTION: 'Stops the specified media', Command.USE: 'stop [identifier]', Command.FUNCTION: "close"}
}

active_players = {}


def _new_active_player(identifier:str, player):
    if not identifier:
        raise ValueError
    if identifier in active_players:
        return False
    active_players[identifier] = player
    return True

def _remove_active_player(identifier:str):
    if not identifier:
        raise ValueError
    active_players.pop(identifier, None)

def _play_youtube_video(url:str, identifier:str=None):
    vid = pafy.new(url).getbest().url
    instance = vlc.Instance('--fullscreen')
    player = instance.media_player_new()
    media = instance.media_new(vid)
    media.get_mrl()
    player.set_media(media)
    if not _new_active_player(identifier=(identifier or vid.title), player=player):
        return False
    player.play()
    
def _trigger_flag(self, flag):
    flag = 1

def _play_stream(url:str, identifier:str=None):
    instance = vlc.Instance('--fullscreen')
    player = instance.media_player_new()
    if not _new_active_player(identifier=(identifier or url), player=player):
        return False
    media = instance.media_new(url)
    media.get_mrl()
    player.set_media(media)
    end_reached_flag = 0
    #Not catching the event for some reason
    player.event_manager().event_attach(vlc.EventType().MediaPlayerEndReached, _trigger_flag, end_reached_flag)
    player.play()
    #while end_reached_flag <= 0:
    time.sleep(1)
    stream = media.subitems().item_at_index(0)
    player.set_media(stream)
    player.play()
    stream.release()

@threaded
def play_video(url:str, identifier:str=None):
    '''Plays the video found at given URL in a standalone media player.
    Currently throws exceptions on invalid input.
    '''
    if "youtube" in urlparse(url).netloc.lower():
        _play_youtube_video(url=url, identifier=identifier)
    else:
        _play_stream(url=url, identifier=identifier)
    #while identifier in active_players:
    #    time.sleep(5)

def close_video(identifier:str):
    if identifier not in active_players:
        return False
    active_players[identifier].stop()
    active_players.pop(identifier)
    return True

@athreaded
def close(msg):
    identifier = msg.data.lower().split('stop', 1)[1].strip()
    return close_video(identifier=identifier)