from collections import defaultdict
from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from resources import resource_handler
from definitions import Command
from mysysteminfo import get_my_directory
from decorators import athreaded
from utilities import intersect_strings, get_greedy_match, dprint
from communication import distill_msg, Secretary, Message
from feedback import feedback
from validators.url import url as validate_url
from urllib.parse import urlparse, urljoin
import cerebratesinfo
import cerebrate_config as cc
import asyncio
import os
import traceback
import enum
from threading import Lock
import pyperclip



_commands = {
    '_open_': {Command.NAME: 'Open Browser', Command.DESCRIPTION: 'Opens the browser.', Command.USE: 'open [\'browser\' or sitename]', Command.FUNCTION: "open_browser"},
    '_close_': {Command.NAME: 'Close Browser', Command.DESCRIPTION: 'Closes the browser.', Command.USE: 'close browser', Command.FUNCTION: "close_browser"},
    '_google_': {Command.NAME: 'Google', Command.DESCRIPTION: 'Searches Google for request.', Command.USE: 'google [request]', Command.FUNCTION: "google"},
    '_save_': {Command.NAME: 'Save Site', Command.DESCRIPTION: 'Saves the url currently in clipboard for future access.', Command.USE: 'save [\'as\' save_name]', Command.FUNCTION: "save_site"},
    '_parse_': {Command.NAME: 'Parse URL', Command.DESCRIPTION: 'Parses the url currently in clipboard and prints the return.', Command.USE: 'parse', Command.FUNCTION: "parse"}
}


_DEFAULT_SITE = "https://www.google.ca/"
_WEBSITE_SECTION = "websites"

_browser = None
_browser_lock = Lock()


class Website:
    '''Holds information about the given website.
    Raises ValueError if the given url does not validate.
    '''
    _domain = None
    _base = None
    _query = None
    _paths = {}

    def __init__(self, url:str=None, path_name:str=None):
        if url:
            self.store_location(url=url, path_name=path_name)
    
    @property
    def domain(self):
        return self._domain

    def store_location(self, url:str, path_name:str=None):
        '''Stores the given URL as the given name.
        If no name is given only stores the domain, and also the query pattern if it is in the url.
        '''
        if not validate_url(url):
            feedback("Url fails validation")
            raise ValueError
        parsed_url = urlparse(url)
        # store scheme
        if not self._base:
            self._base = '://'.join((parsed_url._scheme, parsed_url._netloc))
        # store domain
        if not self.domain:
            self._domain = parsed_url.netloc
        if not self.domain in parsed_url.netloc:
            feedback("Non-matching domain")
            raise ValueError
        # store query format
        if not self._query and not parsed_url.query.isspace():
            self._query = ''.join((parsed_url.path, '?', parsed_url.query.split('=')(0)))
        # store path
        if not path_name:
            return
        self._paths[path_name] = parsed_url.path

    def is_same_site(self, url:str):
        if not validate_url(url):
            return False
        if self.domain != urlparse(url).netloc:
            return False
        return True

    def get_best_match(self, match_string:str):
        ''' Greedy matches between match_string and stored path names.
        Returns the best match (even if it isn't a good match) as a dict containing "match" and "char_count".
        '''
        possible_matches = [' '.join((self.domain, path_name)) for path_name in self._paths.keys()]
        return get_greedy_match(match_string=match_string, possible_matches=possible_matches)

    def get_url(self, path_name:str=''):
        url = self._base
        for name, path in self._paths.items():
            if name in path_name:
                url = urljoin(base=self._base, url=path)
                break
        return url

    def get_query_url(self, query_string:str):
        '''Returns the full URL to search for the given term.
        Requires the query pattern to have been saved previously.
        If no query pattern is currently stored returns None.
        '''
        if self._query.isspace():
            return None
        query = '='.join((self._query, query_string))
        return urljoin(base=self._base, url=query)


class _Lock_Bypass():
    '''Used to bypass lock.
    '''
    def __enter__(self):
        dprint("Bypassing lock")
        return True

    def __exit__(self, type, value, traceback):
        dprint("Finished bypassing lock")


async def parse(msg):
    url = pyperclip.paste()
    print("url = ", url)
    if not validate_url(url):
        return False
    parsed_url = urlparse(url)
    print(parsed_url)
    return True

async def save_site(msg):
    '''If clipboard contains a url, it will be saved according to the name given in msg.data.
    Name in msg.data is parsed as anything given after the word "as".
    If no name given, will parse the url and save it according to domain name.
    '''
    url = pyperclip.paste()
    print("url = ", url)
    if not validate_url(url):
        return False
    path_name = None
    data = distill_msg(msg, "save").data.strip()
    if not data.isspace():
        try:
            path_name = data.split("as")[1].strip()
        except:
            '''no 'as' found, so path_name cannot be extracted from given data'''
    ws = None
    for _, site in resource_handler.get_resources(section=_WEBSITE_SECTION):
        if site.is_same_site(url=url):
            ws = site
            break
    if not ws:
        ws = Website()
    ws.store_location(url=url, path_name=path_name)
    resources = {ws.domain: ws}
    resource_handler.set_resources(section=_WEBSITE_SECTION, resources=resources)
    return True

def _open_browser(msg=None, lock=_browser_lock):
    '''Opens a browser, or a new tab if already open. Goes to target page if specified in Message.'''
    global _browser
    try:
        new_url = _DEFAULT_SITE
        if msg:
            '''extract location to get'''
            match_string = distill_msg(msg, "open").data.lower()
            if not match_string.isspace():
                best_match = {}
                for domain, ws in resource_handler.get_resources(section=_WEBSITE_SECTION):
                    contender = ws.get_best_match(match_string=match_string)
                    if contender.get("char_count", 0) > best_match.get("char_count", 0):
                        best_match = contender
                        best_match["domain"] = domain
                site_found = False
                if best_match.get("char_count", 0) > 0:
                    ws = resource_handler.get_resource(section=_WEBSITE_SECTION, key=best_match.get("domain"))
                    new_url = ws.get_url(path_name=best_match.get("match"))
                    site_found = True
                if not site_found:
                    if "this" in msg.data:
                        try:
                            possible_url = pyperclip.paste
                            if validate_url(possible_url):
                                new_url = possible_url
                        except:
                            '''pyperclip didn't have a url'''
                    elif not "browser" in msg.data:
                        return False
        with lock:
            if not _browser:
                if cc.feedback_on_commands():
                    feedback("Opening a new browser, just a moment...")
                _browser = Firefox(executable_path=os.path.join(get_my_directory(), "drivers", "geckodriver.exe"))
                _browser.get(new_url)
            else:
                handles_before = _browser.window_handles
                _browser.execute_script(''.join(("window.open('", new_url, "')")))
                new_handle = [handle for handle in _browser.window_handles if handle not in handles_before][0]
                _browser.switch_to.window(new_handle)
            if cc.feedback_on_commands():
                feedback(''.join((_browser.title, " is open.")))
    except:
        traceback.print_exc()
        _close_browser(msg)
        return _open_browser(msg)
    return True

@athreaded
def google(msg):
    query = msg.data.lower()
    query = query.split('google', 1)[1].strip()
    try:
        with _browser_lock:
            open_new = True
            if not _browser:
                _open_browser(lock=_Lock_Bypass())
            for handle in _browser.window_handles:
                _browser.switch_to.window(handle)
                if _browser.title == "Google":
                    open_new = False
                    break
            if open_new:
                _open_browser(lock=_Lock_Bypass())
            _browser.get(''.join(('https://www.google.ca/search?q=', query)))
    except:
        '''browser/tab was closed between opening and url get'''
    return True

def _close_browser(msg=None, lock=_browser_lock):
    '''Closes the current window, or the target window if given in Message.'''
    global _browser
    try:
        window_title = None
        if msg:
            '''extract window to close'''
            open_window_titles = []
            for handle in _browser.window_handles:
                _browser.switch_to.window(handle)
                open_window_titles.append(_browser.title)
            data = distill_msg(msg, "close").data
            if data != "":
                match = get_greedy_match(match_string=data, possible_matches=open_window_titles)
                if match.get("char_count", 0) > 2:
                    window_title = match.get("match", None)
                if not window_title:
                    if "browser" in data:
                        _quit_browser()
                    else:
                        return False
        with lock:
            if not window_title:
                try:
                    _browser.close()
                except:
                    _browser.switch_to.window(_browser.window_handles[len(_browser.window_handles)-1])
                    _browser.close()
            elif window_title.lower() in _browser.title.lower():
                _browser.close()
            else:
                active_handle = _browser.current_window_handle
                for handle in _browser.window_handles:
                    _browser.switch_to.window(handle)
                    if window_title.lower() in _browser.title.lower():
                        _browser.close()
                        break
                try:
                    _browser.switch_to.window(active_handle)
                except:
                    '''active handle was closed'''
                    _browser.switch_to.window(_browser.window_handles[len(_browser.window_handles)-1])
        if len(_browser.window_handles) <= 0:
            _quit_browser()
    except:
        '''all windows are closed (or browser is already closed)'''
        if cc.debug_in_effect:
            traceback.print_exc()
        _quit_browser()
    return True

def _quit_browser(lock=_browser_lock):
    '''Terminates the entire browser.'''
    global _browser
    with lock:
        try:
            _browser.quit()
        except:
            '''browser already doesn't exist'''
            if cc.debug_in_effect:
                traceback.print_exc()   
        finally:
            _browser = None

@athreaded
def open_browser(msg=None):
    return _open_browser(msg)
    
@athreaded
def close_browser(msg=None):
    return _close_browser(msg)

async def terminate():
    """Closes any open browsers (opened by cerebrate).
    Waits until cc.my_state_event[TERMINATING] is set.
    """
    await cc.my_state_event[cc.State.TERMINATING].wait()
    _quit_browser()

asyncio.ensure_future(terminate(), loop=asyncio.get_event_loop())