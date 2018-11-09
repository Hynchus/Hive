import speech_recognition as sr
import logging
from utilities import dprint
import asyncio
import threading

fs = 48000
duration = 5

r = sr.Recognizer()
mic = None

def get_microphones():
    '''Returns the list of names of microphones available on the system
    '''
    return sr.Microphone.list_microphone_names()

def list_microphones():
    '''Prints the list of microphone names and their index
    '''
    print("")
    index = 0
    for microphone in get_microphones():
        print(index, ": ", microphone)
        index += 1
    if mic:
        print("\nCurrent microphone: ", mic.device_index)

def setup_microphone(mic_index="default"):
    '''Sets up a given (or default if none given) microphone for future input.
    Returns True if successful or False if not.
    '''
    global mic
    if type(mic_index) is int:
        mic = sr.Microphone(device_index=mic_index)
    else:
        mic = sr.Microphone()
    if not mic:
        logging.error(''.join(("Could not establish mic ", str(mic_index))))
        return False
    return True

async def get_voice_input(loop):
    '''Waits for a line of input from system microphone.
    Throws an EnvironmentError if no microphone could be setup.
    '''
    if not mic:
        if not setup_microphone():
            raise EnvironmentError
    try:
        result_future = asyncio.Future()
        def threaded_listen():
            global mic
            global r
            result = None
            with mic as source:
                try:
                    audio = r.listen(source, phrase_time_limit=10)
                    result = r.recognize_google(audio)
                except Exception as ex:
                    dprint(ex)
            if result:
                loop.call_soon_threadsafe(result_future.set_result, result)
            else:
                loop.call_soon_threadsafe(result_future.set_exception, ValueError)
            return True
        listener_thread = threading.Thread(target=threaded_listen)
        listener_thread.daemon = True
        listener_thread.start()
        return await result_future
    except Exception as ex:
        dprint(ex)
    return None


    



# sd.default.device = 21, 3
# print(sd.query_devices())
# print("recording...")
# output = sd.rec(int(duration * fs), samplerate=fs, channels=2)
# sd.wait()
# print("finished recording")
# print("playing...")
# sd.play(output, fs)
# sd.wait()
# print("finished playing")


# def callback(indata, outdata, frames, time, status):
#     if status:
#         print(status)
#     outdata[:] = indata

# with sd.RawStream(channels=2, dtype='int24', callback=callback):
#     sd.sleep(int(duration * 1000))
