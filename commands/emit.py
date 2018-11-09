import cerebrate_config as cc
from definitions import Command
from utilities import aprint
import cerebratesinfo, communication, mysysteminfo
import socket, struct

_commands = {
    '_message_': {Command.NAME: 'Message', Command.DESCRIPTION: 'Communicates a message to intended cerebrate(s) through text and audio, if possible.', Command.USE: 'message [target(s)][message]', Command.FUNCTION: "send_message"},
    '_wake': {Command.NAME: 'Wake Cerebrate', Command.DESCRIPTION: 'Wake up intended cerebrate(s), if possible.', Command.USE: 'wake [cerebrate specifier(s)]', Command.FUNCTION: "wake"}
}

async def send_message(msg):
    data = msg.data
    recipients = []
    for cerebrate in cerebratesinfo.get_cerebrate_records():
        name = cerebrate.get(cerebratesinfo.Record.NAME, "")
        if name in data:
            mac = cerebrate.get(cerebratesinfo.Record.MAC, "")
            if not mac in recipients:
                recipients.append(mac)
                communication.distill_msg(msg, name)
    for cerebrate in cerebratesinfo.get_cerebrate_records():
        location = cerebrate.get(cerebratesinfo.Record.LOCATION, "")
        if location in data:
            mac = cerebrate.get(cerebratesinfo.Record.MAC, "")
            if not mac in recipients:
                recipients.append(mac)    
                communication.distill_msg(msg, location)
    if recipients.__len__() <= 0:
        recipients = cerebratesinfo.get_cerebrate_macs()
        recipients.remove(mysysteminfo.get_mac_address())
    for recipient in recipients:
        await communication.Secretary.communicate_message(cerebrate_mac=recipient, msg=communication.Message('display_message', data=msg.data))
    # speak msg
    #aprint("Message communicated")
    return True

def wake_cerebrate(cerebrate_mac):
    '''Attempts to wake given cerebrate.
    Target system must have wake on magic packet enabled.
    Raises a ValueError if the given mac is unrecognizable.
    '''
    # Check macaddress format and try to compensate.
    cerebrate_name = cerebratesinfo.get_cerebrate_attribute(cerebrate_mac=cerebrate_mac, record_attribute=cerebratesinfo.Record.NAME)
    if len(cerebrate_mac) == 12:
        pass
    elif len(cerebrate_mac) == 12 + 5:
        sep = cerebrate_mac[2]
        cerebrate_mac = cerebrate_mac.replace(sep, '')
    else:
        raise ValueError('Incorrect MAC address format')

    # Pad the synchronization stream.
    data = ''.join(['FFFFFFFFFFFF', cerebrate_mac * 20])
    send_data = b''

    # Split up the hex values and pack.
    for i in range(0, len(data), 2):
        send_data = b''.join([send_data, struct.pack('B', int(data[i: i + 2], 16))])

    # Broadcast it to the LAN.
    # This is done manually here because the communication module pickles the data, so won't work for this.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(send_data, ('<broadcast>', 7))
    if cc.feedback_on_commands():
        print(cerebrate_name + " prodded.")
    return True

async def wake(msg):
    '''Tries to wake a cerebrate based on given name or location
    '''
    for cerebrate in cerebratesinfo.get_cerebrate_records():
        name_matched = cerebrate.get(cerebratesinfo.Record.NAME, "unknown").lower() in msg.data.lower()
        location_matched = cerebrate.get(cerebratesinfo.Record.LOCATION, "unknown").lower() in msg.data.lower()
        if name_matched or location_matched:
            return wake_cerebrate(cerebrate.get(cerebratesinfo.Record.MAC, None))


    # for name in cerebratesinfo.get_cerebrate_names():
    #     if name.lower() in msg.data.lower():
    #         record = cerebratesinfo.get_cerebrate_record(record_attribute=cerebratesinfo.Record.NAME, attribute_value=name)
    #         if record != None:
    #             return wake_cerebrate(record.get(cerebratesinfo.Record.MAC))
    # for location in cerebratesinfo.get_cerebrate_locations():
    #     if location.lower() in msg.data.lower():
    #         record = cerebratesinfo.get_cerebrate_record(record_attribute=cerebratesinfo.Record.LOCATION, attribute_value=location)
    #         if record != None:
    #             return wake_cerebrate(record.get(cerebratesinfo.Record.MAC))
    #aprint("No target recognized in given wake command\n'", msg.header, msg.data, "'")
    return False