try:
    import sys
    import os
    import enum
    import signal
    import asyncio
    from aioconsole import ainput
    import audio, cerebrate_config as cc, cerebratesinfo, command, communication, mysysteminfo, utilities
    from utilities import dprint, get_cerebrate_file_names
    from resources import resource_handler
    import traceback
    import logging
    from contextlib import suppress
except ImportError:
    install_requirements()
    restart_cerebrate()

def sigint_handler(signum, frame):
    asyncio.ensure_future(terminate(), loop=asyncio.get_event_loop())

async def console_listener():
    prompt = "\n)))"
    while not cc.my_state_event[cc.State.TERMINATING].is_set():
        await cc.my_state_event[cc.State.LISTENING].wait()
        cmd = await ainput(''.join((prompt, " ")))
        cmd = cmd.strip()
        await cc.my_state_event[cc.State.LISTENING].wait()
        await command.run_command(msg=communication.Message("cmd", "console", data=cmd))

async def audio_listener(loop):
    await cc.my_state_event[cc.State.LISTENING].wait()
    while not cc.my_state_event[cc.State.TERMINATING].is_set():
        try:
            voice_input = await audio.get_voice_input(loop)
            if not voice_input:
                continue
            if not cc.accept_audio_control.is_set():
                if not "eddie" in voice_input.lower():
                    dprint("ignore input")
                    continue
            voice_input = voice_input.replace('Eddie', '', 1).strip()
            await command.run_command(msg=communication.Message("cmd", "voice", data=voice_input))
        except EnvironmentError:
            cc.accept_audio_control.clear()
        except Exception:
            traceback.print_exc()
            
def start_listeners(loop):
    communication.initialize(loop=loop)
    asyncio.ensure_future(console_listener(), loop=loop)
    asyncio.ensure_future(audio_listener(loop), loop=loop)

def setup_loop():
    loop = asyncio.get_event_loop()
    return loop

def say_hello():
    #Assume everyone is asleep
    for mac in cerebratesinfo.get_cerebrate_macs():
        cerebratesinfo.update_cerebrate_attribute(mac=mac, record_attribute=cerebratesinfo.Record.STATUS, attribute_value=cerebratesinfo.Status.ASLEEP)
    #Set self status to awake
    cerebratesinfo.update_cerebrate_attribute(mac=mysysteminfo.get_mac_address(), record_attribute=cerebratesinfo.Record.STATUS, attribute_value=cerebratesinfo.Status.AWAKE)
    #Assume we are the only cerebrate up, temporarily designate ourself as Overmind
    cerebratesinfo.designate_overmind(mac=mysysteminfo.get_mac_address())
    #Contact existing Overmind, if there is one
    communication.Secretary.broadcast_message(msg=communication.Message('acknowledge', data={"version": cc.MY_VERSION}))

async def designate_successor():
    '''Establishes a new Overmind among the remaining (awake) cerebrates.
    Returns the new Overmind's mac address.
    '''
    successor_mac = cerebratesinfo.get_overmind_mac()
    if mysysteminfo.get_mac_address() == successor_mac:
        for record in cerebratesinfo.get_cerebrate_records():
            if record.get(cerebratesinfo.Record.MAC) == mysysteminfo.get_mac_address():
                continue
            if record.get(cerebratesinfo.Record.STATUS, cerebratesinfo.Status.UNKNOWN) == cerebratesinfo.Status.AWAKE:
                if cerebratesinfo.designate_overmind(mac=record.get(cerebratesinfo.Record.MAC, None)):
                    received = await communication.Secretary.communicate_message(cerebrate_mac=record.get(cerebratesinfo.Record.MAC, None), msg=communication.Message("assume_overmind", data=None))
                    if received == cc.SUCCESS:
                        successor_mac = record.get(cerebratesinfo.Record.MAC)
                        break
    return successor_mac
    
async def say_goodbye():
    #Set someone else as Overmind
    successor_mac = await designate_successor()
    #Tell Overmind that we are going to sleep
    # If no other cerebrate is online we end up sending this to ourselves, which is ignored
    cerebratesinfo.update_cerebrate_attribute(mac=mysysteminfo.get_mac_address(), record_attribute=cerebratesinfo.Record.STATUS, attribute_value=cerebratesinfo.Status.ASLEEP)
    cerebratesinfo.update_cerebrate_contact_time(mac=mysysteminfo.get_mac_address())
    await communication.Secretary.communicate_message(cerebrate_mac=successor_mac, msg=communication.Message("update_records", data=[cerebratesinfo.get_cerebrate_record(record_attribute=cerebratesinfo.Record.MAC, attribute_value=mysysteminfo.get_mac_address())]))
    
def update_requirements():
    if not os.path.exists(os.path.join(os.path.dirname(__file__), 'development_cerebrate')):
        return False
    dprint("Updating requirements")
    import subprocess
    subprocess.Popen(['pip', 'freeze'], stdout=open(os.path.join(os.path.dirname(__file__), 'requirements.edy'), 'w'))
    return True

def install_requirements():
    print("Installing requirements")
    import subprocess
    for directoryname, filenames, _ in os.walk(os.path.dirname(__file__)):
        for filename in filenames:
            if os.path.splitext(filename)[1] == '.whl':
                try:
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install', os.path.join(directoryname, filename)])
                except Exception as ex:
                    print("Could not install ", filename)
                    dprint(ex)
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.edy'])

def restart_cerebrate():
    print("Restarting cerebrate...")
    os.execv(sys.executable, ['python'] + sys.argv)

async def terminate(msg=None, loop=None):
    await say_goodbye()
    cc.change_my_state(state=cc.State.TERMINATING)
    if not loop:
        loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.stop()

if __name__ == '__main__':
    logging.basicConfig(filename='cerebrate.log')
    signal.signal(signalnum=signal.SIGINT, handler=sigint_handler)
    loop = setup_loop()
    start_listeners(loop=loop)
    say_hello()
    try:
        print("\nCerebrate online\n")
        cc.change_my_state(state=cc.State.LISTENING)
        with suppress(asyncio.CancelledError):
            loop.run_forever()
    except Exception as e:
        print("EXCEPTION")
        traceback.print_exc()
    finally:
        print("\nCerebrate going offline...")
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        print("Cerebrate offline\n")
        if cc.restart_cerebrate_on_terminate:
            restart_cerebrate()