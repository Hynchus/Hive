from collections import defaultdict
from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from resources import resource_handler
from definitions import Command
from mysysteminfo import get_my_directory
from decorators import athreaded
from utilities import get_greedy_match, intersect_strings, dprint, pad_string
from communication import distill_msg, Secretary, Message
from feedback import feedback
from validators.url import url as validate_url
from urllib.parse import urlparse, urljoin, ParseResult
from urllib import request
import cerebratesinfo
import cerebrate_config as cc
import asyncio
import os
import traceback
import enum
import re
from threading import Lock
import pyperclip
from commands import media_player



_commands = {
    '_open_': {Command.NAME: 'Open Browser', Command.DESCRIPTION: 'Opens the browser.', Command.USE: 'open [\'browser\' or sitename]', Command.FUNCTION: "open_browser"},
    '_close_': {Command.NAME: 'Close Browser', Command.DESCRIPTION: 'Closes the browser.', Command.USE: 'close browser', Command.FUNCTION: "close_browser"},
    '_google_': {Command.NAME: 'Google', Command.DESCRIPTION: 'Searches Google for request.', Command.USE: 'google [request]', Command.FUNCTION: "google"},
    '_save_': {Command.NAME: 'Save Site', Command.DESCRIPTION: 'Saves the url currently in clipboard for future access.', Command.USE: 'save [\'as\' save_name]', Command.FUNCTION: "save_site"},
    '_parse_': {Command.NAME: 'Parse URL', Command.DESCRIPTION: 'Parses the url currently in clipboard and prints the return.', Command.USE: 'parse', Command.FUNCTION: "parse"},
    '_search_': {Command.NAME: 'Search Site', Command.DESCRIPTION: 'Searches the site for the given query, provided site\'s search url has been previously saved.', Command.USE: 'search [site name] for [query]', Command.FUNCTION: "search_site"},
    '_list_': {Command.NAME: 'List Web Info', Command.DESCRIPTION: 'Displays the requested information.', Command.USE: 'list [info specifier][filter terms]', Command.FUNCTION: "list_info"},
    '_youtube_': {Command.NAME: 'Play Youtube video', Command.DESCRIPTION: 'Plays the top result on Youtube from given search query', Command.USE: 'youtube [query]', Command.FUNCTION: "youtube"}
}


_DEFAULT_SITE = "https://www.google.ca/"
_WEBSITE_SECTION = "websites"

_browser = None
_browser_lock = Lock()


class Website(resource_handler.Resource_BC):
    '''Holds information about the given website.
    URL is optional, however the returned Website will be empty if no URL is given. Use Website.store_location() on a Website to store a url in it.
    path_name is optional, however only the domain and possibly the search pattern will be stored if path_name is not given.
    Raises ValueError if a given url does not validate.
    '''

    def __init__(self, url:str=None, path_name:str=None):
        self._domain = ""
        self._base = ""
        self._query = ""
        self._paths = {}
        if url:
            self.store_location(url=url, path_name=path_name)
    
    @property
    def domain(self):
        return self._domain

    def update(self, resource):
        '''Updates this resource instance with the given resource instance.
        Raises EnvironmentError if given resource instance does not match this instance.
        '''
        try:
            super().update(resource=resource)
        except:
            raise
        if self.domain != resource.domain:
            return False
        self._paths.update(resource._paths)
        return True

    def _store_query_pattern(self, parsed_url:ParseResult):
        if '=' in parsed_url.query:
            query_string = None
            if '&' in parsed_url.query:
                #organize the terms so that the query term is furthest right
                query_term_found = False
                terms = []
                for term in parsed_url.query.split('&'):
                    if "query" in term:
                        query_term_found = True
                        terms.append(term)
                    elif not query_term_found and 'q' in term:
                        terms.append(term)
                    else:
                        terms.insert(0, term)
                #clear any input to the right of the query term's '='
                terms[len(terms)-1] = ''.join((terms[len(terms)-1].split('=')[0], '='))
                query_string = '&'.join(terms)
            else:
                query_string = ''.join((parsed_url.query.split('=')[0], '='))

            self._query = ''.join((parsed_url.path, '?', query_string))

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
            self._base = '://'.join((parsed_url.scheme, parsed_url.netloc))
        # store domain
        if not self.domain:
            self._domain = parsed_url.netloc
        if not self.domain in parsed_url.netloc:
            feedback("Non-matching domain")
            raise ValueError
        # store query pattern
        self._store_query_pattern(parsed_url=parsed_url)
        # store path
        if not path_name:
            return
        self._paths[path_name] = parsed_url.path

    def is_same_site(self, url:str):
        '''Checks whether the domain of the given site matches the domain of this site.
        Returns True or False.
        '''
        if not validate_url(url):
            return False
        if self.domain != urlparse(url).netloc:
            return False
        return True

    def get_info(self):
        '''Returns a dictionary containing the domain, query, and paths of this website.
        '''
        info = {}
        info["domain"] = self.domain
        info["query"] = self._query
        info["paths"] = self._paths
        return info

    def get_greedy_match(self, match_string:str, minimum_word_size:int=2):
        '''Greedy matches between match_string and stored path names.
        Returns the best match (even if it isn't a good match) as a dict containing "match" and "char_count".
        '''
        possible_matches = [' '.join((self.domain, path_name)) for path_name in self._paths.keys()]
        possible_matches.append(self.domain)
        return get_greedy_match(match_string=match_string, possible_matches=possible_matches, minimum_word_size=minimum_word_size)

    def get_url(self, path_name:str=''):
        '''Returns the URL that matches the given path_name.
        '''
        url = self._base
        for name, path in self._paths.items():
            if name in path_name:
                url = urljoin(base=self._base, url=path)
                break
        return url

    def get_query_url(self, query_string:str=''):
        '''Returns the full URL to search for the given term.
        Requires the query pattern to have been saved previously.
        If no query pattern is currently stored returns None.
        '''
        if not self._query.strip():
            return None
        query = ''.join((self._query, query_string.strip()))
        return urljoin(base=self._base, url=query)

    @staticmethod
    def get_url_greedy_match(match_string:str, query_string:str=None, minimum_word_size:int=2):
        '''Checks all stored Websites and returns the URL that best matches the given request name.
        If query_string is given will return the appropriate URL, provided search pattern has been previously saved.
        Returns None if no saved URL even remotely matches.
        '''
        best_match = {}
        for domain, ws in resource_handler.get_resources(section=_WEBSITE_SECTION):
            contender = ws.get_greedy_match(match_string=match_string, minimum_word_size=minimum_word_size)
            if contender.get("char_count", 0) > best_match.get("char_count", 0):
                best_match = contender
                best_match["domain"] = domain
                best_match["ws"] = ws
        new_url = None
        if best_match.get("char_count", 0) > 0:
            if query_string:
                new_url = best_match["ws"].get_query_url(query_string=query_string)
            else:
                new_url = best_match["ws"].get_url(path_name=best_match["match"])
        return new_url


class _Lock_Bypass():
    '''Used to bypass lock.
    '''
    def __enter__(self):
        dprint("Bypassing lock")
        return True

    def __exit__(self, type, value, traceback):
        dprint("Finished bypassing lock")


async def form_display_string(website_info:dict):
    '''Given appropriate info, returns the display string for the website.
    '''
    details_offset = 0
    search = website_info.get("query", None)

    for path_name in website_info.get("paths", {}).keys():
        details_offset = max(len(path_name), details_offset)

    if search:
        details_offset = max(len("search"), details_offset)
        search = ':'.join((pad_string(string="search", length=details_offset, pad_char='='), search))
    else:
        search = ""
    display_strings = []
    display_strings.append(' | '.join((website_info.get("domain", ""), search)))
    domain_offset = len(website_info.get("domain", ""))
    for path_name, path in website_info.get("paths", {}).items():
        path_string = ':'.join((pad_string(string=path_name, length=details_offset, pad_char='-'), path))
        display_strings.append(' | '.join((pad_string(string="", length=domain_offset), path_string)))
    return '\n'.join(display_strings)

async def list_info(msg):
    if "website" in msg.data:
        #bad use of distill_msg, it needs rework
        distilled = distill_msg(msg=msg, sediment="website")
        distilled = distill_msg(msg=distilled, sediment="list")
        show_all = False
        if "_all_" in distilled.data or "_every" in distilled.data:
            show_all = True
        requested_sites = []
        if not show_all:
            for key in resource_handler.get_resource_keys(section=_WEBSITE_SECTION):
                if intersect_strings(distilled.data, key)["char_count"] >= 4:
                    requested_sites.append(key)
        if len(requested_sites) <= 0:
            show_all = True
        display_strings = []
        for key, ws in resource_handler.get_resources(section=_WEBSITE_SECTION):
            if show_all or key in requested_sites:
                try:
                    display_strings.append(await form_display_string(website_info=ws.get_info()))
                except:
                    traceback.print_exc()
        if len(display_strings) >= 1:
            for display_string in display_strings:
                print("")
                print(display_string)
            return True
    return False

async def parse(msg):
    url = pyperclip.paste()
    print("url = ", url)
    if not validate_url(url):
        return False
    parsed_url = urlparse(url)
    print(parsed_url)
    print()
    ws = Website(url = url, path_name="test")
    print("Stored domain", '\n', ws.domain)
    print("Stored URL", '\n', ws.get_url(path_name="test"))
    search_url = ws.get_query_url()
    if search_url:
        print("Stored search URL", '\n', search_url)

    return True

def _save_url(url, path_name=None):
    if not validate_url(url):
        return
    ws = None
    for _, site in resource_handler.get_resources(section=_WEBSITE_SECTION):
        if site.is_same_site(url=url):
            ws = site
            break
    if not ws:
        ws = Website()
    ws.store_location(url=url, path_name=path_name)
    resources = {ws.domain: ws}
    resource_handler.store_resources(section=_WEBSITE_SECTION, resources=resources)

@athreaded
def save_site(msg):
    '''If clipboard contains a url, it will be saved according to the name given in msg.data.
    Name in msg.data is parsed as anything given after the word "as".
    If no name given, will parse the url and save it according to domain name.
    '''
    url = pyperclip.paste()
    print("url = ", url)
    if not validate_url(url):
        return False
    path_name = None
    data = distill_msg(msg=msg, sediment="save").data.strip()
    if data:
        try:
            path_name = data.split("as")[1].strip()
        except:
            '''no 'as' found, so path_name cannot be extracted from given data'''
    _save_url(url=url, path_name=path_name)
    return True

@athreaded
def search_site(msg):
    data = distill_msg(msg=msg, sediment="search").data.strip()
    if not data:
        return False
    try:
        parsed_data = data.split("for")
        site_name = parsed_data[0]
        query = parsed_data[1]
        try:
            url = Website.get_url_greedy_match(match_string=site_name, query_string=query)
            if url:
                _open_browser(url=url)
        except:
            traceback.print_exc()
    except:
        '''input does not match pattern'''

def get_current_domain():
    if not _browser:
        raise EnvironmentError
    return urlparse(_browser.current_url).netloc

def get_cookies_section(domain:str):
    base = "website_cookies"
    domain_name = domain.strip()
    if not domain_name:
        return base
    return resource_handler.FOLDER_SEPARATOR.join((base, domain_name))

def save_cookies():
    if not _browser:
        return
    cookies = {}
    domain = get_current_domain()
    for cookie in _browser.get_cookies():
        cookies[resource_handler.FOLDER_SEPARATOR.join((domain, cookie.get("name", '')))] = cookie
    resource_handler.store_resources(section=get_cookies_section(domain=domain), resources=cookies)

def load_cookies():
    if not _browser:
        return
    cookie_count = 0
    for _, cookie in resource_handler.get_resources(section=get_cookies_section(domain=get_current_domain())):
        cookie_count += 1
        _browser.add_cookie(cookie_dict=cookie)
    if cookie_count > 0:
        _browser.refresh()

def _save_current_domain():
    if not _browser:
        return
    save_cookies()
    parsed_url = urlparse(_browser.current_url)
    current_domain = '://'.join((parsed_url.scheme, parsed_url.netloc))
    _save_url(url=current_domain)

def _start_browser(lock=_browser_lock):
    global _browser
    _quit_browser(lock=lock)
    with lock:
        if cc.feedback_on_commands():
            feedback("Opening a new browser, just a moment...")
        _browser = Firefox(executable_path=os.path.join(get_my_directory(), "drivers", "geckodriver.exe"))

def _open_tab(url:str="", lock=_browser_lock, recurse=True):
    global _browser
    if not recurse:
        feedback("_open_tab failed on second try")
        raise EnvironmentError
    with lock:
        try:
            handles_before = _browser.window_handles
            _browser.execute_script(''.join(("window.open('", url, "')")))
            new_handle = [handle for handle in _browser.window_handles if handle not in handles_before][0]
            _browser.switch_to.window(new_handle)
            load_cookies()
        except:
            #_browser was closed by an outside force
            _start_browser(lock=_Lock_Bypass())
            _open_tab(url=url, lock=_Lock_Bypass(), recurse=False)

def _open_browser(url:str=None, lock=_browser_lock):
    '''Opens a browser, or a new tab if already open.
    Goes to given URL if specified.
    '''
    global _browser
    try:
        new_url = _DEFAULT_SITE
        if url:
            new_url = url
        with lock:
            if not _browser:
                _start_browser(lock=_Lock_Bypass())
                _browser.get(new_url)
                load_cookies()
            else:
                _open_tab(url=new_url, lock=_Lock_Bypass())
            if cc.feedback_on_commands():
                feedback(''.join((_browser.title, " is open.")))
    except:
        traceback.print_exc()
    return True

@athreaded
def google(msg):
    query = msg.data.lower()
    query = query.split('google', 1)[1].strip()
    with _browser_lock:
        try:
                open_new = True
                if not _browser:
                    _start_browser(lock=_Lock_Bypass())
                    open_new = False
                for handle in _browser.window_handles:
                    _browser.switch_to.window(handle)
                    if _browser.title == "Google":
                        open_new = False
                        break
                if open_new:
                    _open_tab(lock=_Lock_Bypass())
        except:
            '''browser/tab was closed by an outside force'''
            _start_browser(lock=_Lock_Bypass())
        _browser.get(''.join(('https://www.google.ca/search?q=', query)))
        load_cookies()
    return True

@athreaded
def youtube(msg):
    query = msg.data.lower()
    query = query.split('youtube', 1)[1].strip()
    youtube_search = "http://www.youtube.com/results?search_query=" + '+'.join((query.split(' ')))
    html_content = request.urlopen(youtube_search)
    search_results = re.findall(r'href=\"\/watch\?v=(.{11})', html_content.read().decode())
    top_result = "http://www.youtube.com/watch?v=" + search_results[0]
    media_player.play_video(url=top_result, identifier=query)

def _close_handle(handle, lock=_browser_lock):
    try:
        with lock:
            _browser.switch_to.window(handle)
            _save_current_domain()
            _browser.close()
    except:
        traceback.print_exc()
        '''tab (or browser) is already closed'''

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
            data = distill_msg(msg, "close").data.strip()
            if data:
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
                    _close_handle(handle=_browser.current_window_handle, lock=_Lock_Bypass())
                except:
                    _close_handle(handle=_browser.window_handles[len(_browser.window_handles)-1], lock=_Lock_Bypass())
            elif window_title.lower() in _browser.title.lower():
                _close_handle(handle=_browser.current_window_handle, lock=_Lock_Bypass())
            else:
                active_handle = _browser.current_window_handle
                for handle in _browser.window_handles:
                    _browser.switch_to.window(handle)
                    if window_title.lower() in _browser.title.lower():
                        _close_handle(handle=handle, lock=_Lock_Bypass())
                        break
                try:
                    _browser.switch_to.window(active_handle)
                except:
                    '''active handle was closed'''
                    if len(_browser.window_handles) > 0:
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
            while len(_browser.window_handles) > 0:
                _close_handle(_browser.window_handles[0], lock=_Lock_Bypass())
            _browser.quit()
        except:
            '''browser already doesn't exist'''
        finally:
            _browser = None

@athreaded
def open_browser(msg=None):
    url = None
    if msg:
        #get match_string from msg, get URL from Website using match_string
        data = distill_msg(msg=msg, sediment="open").data.strip()
        url = Website.get_url_greedy_match(match_string=data)
        if not url and not "browser" in data:
            return False
    return _open_browser(url=url)
    
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