import sys
import asyncio
import pickle
import socket
import traceback
import logging
from contextlib import suppress
import os
import copy
from datetime import datetime
from decorators import print_func_name
import cerebrate_config as cc, cerebratesinfo, command, mysysteminfo, remote_command, utilities
from utilities import dprint


BROADCAST = '255.255.255.255'
TCP_PORT = 8888  # the base communication port, used for short communication and initializing prolonged communication
UDP_PORT = 9999

MAX_BYTE_TRANSFER = 1024
COMMUNICATION_TIMEOUT = 14

EOF = "_end_of_write_"

BY_REQUEST = "by request"
TIMEOUT = "timed out"

event_loop = None

class Message:
    """A Message object for standardized communication in Cerebrate program.
    Header contains intended destination/function for Message, Data contains data.
    """
    sender_mac = None
    sender_ip = None
    header = None
    data = None

    def __init__(self, *headers, data:list=None):
        self.sender_mac = mysysteminfo.get_mac_address()
        self.sender_ip = mysysteminfo.get_ip_address()
        self.header = [header for header in headers if header]
        self.data = data


def distill_msg(msg, sediment):
    '''Moves the first sediment from msg.data to msg.header.
    Returns the distilled msg.
    '''
    distilled = copy.deepcopy(msg)
    if sediment.lower() in distilled.data.lower():
        distilled.header.append(sediment.lower())
        distilled.data = distilled.data.replace(sediment, '', 1).strip()
    return distilled

async def handle_message(msg):
    '''Parses the message header and calls the appropriate function(s).
    Returns an action, Message pair.
    '''
    success = True
    try:
        Secretary._made_contact(mac=msg.sender_mac, ip=msg.sender_ip)
        if cc.CLOSE_CONNECTION in msg.header:
            return cc.CLOSE_CONNECTION, BY_REQUEST
        elif cc.FILE_TRANSFER in msg.header:
            return cc.FILE_TRANSFER, BY_REQUEST
        else:
            return await remote_command.run_command(msg)
    except Exception as ex:
        success = False
        traceback.print_exc()
        logging.error(ex)
        return cc.CLOSE_CONNECTION, "ERROR"
    finally:
        if success:
            Secretary._made_contact(mac=msg.sender_mac, time=True)

class Secretary(asyncio.Protocol):
    """Handles connections with other Cerebrates.
    """
    terminating = True
    tcp_server = None
    udp_server = None

    _no_active_connections = asyncio.Event()
    connections = []

    @staticmethod
    def _timed_out(mac):
        '''Makes a note that they may be asleep.
        '''
        cerebratesinfo.update_cerebrate_attribute(mac=mac, record_attribute=cerebratesinfo.Record.STATUS, attribute_value=cerebratesinfo.Status.UNKNOWN)

    @staticmethod
    def _made_contact(mac, ip=None, time=None):
        '''
        If given an IP address will update the record and mark them as awake.
        If time is True will update contact time.
        '''
        if ip:
            cerebratesinfo.update_cerebrate_attribute(mac=mac, record_attribute=cerebratesinfo.Record.IP, attribute_value=ip)
            cerebratesinfo.update_cerebrate_attribute(mac=mac, record_attribute=cerebratesinfo.Record.STATUS, attribute_value=cerebratesinfo.Status.AWAKE)
        if time:
            cerebratesinfo.update_cerebrate_contact_time(mac=mac)


    @staticmethod
    async def _read_message(reader):
        '''Reads a message from reader and returns it.
        '''
        if not reader:
            return None
        received = await reader.read(MAX_BYTE_TRANSFER)
        data = b''
        while received != EOF:
            data = data + received
            received = await reader.read(MAX_BYTE_TRANSFER)
        msg = pickle.loads(data)
        return msg

    @staticmethod
    async def _write_message(writer, msg):
        '''Writes a message to the reader.
        Returns True if successful.
        '''
        if not writer:
            return False
        if not msg:
            return False
        #print("\n Sending ", msg, "\n")
        data = pickle.dumps(msg)
        index = 0
        while index < len(data):
            start_index = index
            index += MAX_BYTE_TRANSFER
            fragment = data[start_index:index]
            writer.write(fragment)
        writer.write(EOF)
        await writer.drain()
        return True

    @staticmethod
    async def close_connection(reader, writer, close_reason=None):
        if (reader, writer) in Secretary.connections:
            Secretary.connections.remove((reader, writer))
            if len(Secretary.connections) <= 0:
                Secretary._no_active_connections.set()
        else:
            logging.error("(reader, writer) closed but not in connections list.")
        data = cc.FINISHED
        if close_reason:
            data = close_reason
        await Secretary._write_message(writer=writer, msg=Message(cc.CLOSE_CONNECTION, data=data))
        writer.close()

    @staticmethod
    @print_func_name
    async def __receive_files(reader, writer):
        data = None
        while not Secretary.terminating:
            await Secretary._write_message(writer=writer, msg=cc.READY)
            msg = await Secretary._read_message(reader=reader)
            if cc.CLOSE_CONNECTION in msg.header:
                return BY_REQUEST
            #Get proper directory to save this file to
            location = msg.data.get(cc.LOCATION, cc.FileLocation.ABSOLUTE)
            if location == cc.FileLocation.SOURCE:
                location = mysysteminfo.get_my_directory()
            elif location == cc.FileLocation.HIVE:
                location = mysysteminfo.get_hive_directory()
            else:
                location = ""
            filename = msg.data.get(cc.NAME, None)
            if not filename:
                return "no cc.NAME included"
            file_path = os.path.join(location, filename)
            #backup file we're overwriting, just in case
            utilities.backup_file(file_path=file_path)
            try:
                with open(file_path, 'w+') as new_file:
                    await Secretary._write_message(writer=writer, msg=cc.READY)
                    data = await Secretary._read_message(reader=reader)
                    while data != cc.FINISHED:
                        new_file.write(data)
                        await Secretary._write_message(writer=writer, msg=cc.READY)
                        data = await Secretary._read_message(reader=reader)
            except Exception as ex:
                logging.error(ex)
                traceback.print_exc()
                utilities.restore_file(file_path=file_path)
                return "failed while receiving/writing file"
                
        return "secretary terminating"

    @staticmethod
    @print_func_name
    async def __communicate(reader, writer):
        ''' Communicates with the cerebrate on the other end of reader, writer pair.
        Returns the reason (as string) for the end of communication.
        '''
        while not Secretary.terminating:
            msg = await Secretary._read_message(reader=reader)
            if msg.sender_mac == mysysteminfo.get_mac_address():
                return "schizophrenia"
            action, message = await handle_message(msg=msg)
            if action == cc.CLOSE_CONNECTION:
                return message
            elif action == cc.FILE_TRANSFER:
                return await Secretary.__receive_files(reader=reader, writer=writer)
            else:
                await Secretary._write_message(writer=writer, msg=message)
        return "secretary terminating"
    
    @staticmethod
    @print_func_name
    async def __connection_made(reader, writer):
        '''Handles TCP connections (both incoming and outgoing).
        Throws asyncio.TimeoutError.
        '''
        if (reader, writer) in Secretary.connections:
            return "duplicate"
        else:
            Secretary.connections.append((reader, writer))
            Secretary._no_active_connections.clear()
        close_reason = "secretary closing"
        try:
            if not Secretary.terminating:
                fut = Secretary.__communicate(reader=reader, writer=writer)
                close_reason = await asyncio.wait_for(fut=fut, timeout=COMMUNICATION_TIMEOUT, loop=event_loop)
        except asyncio.TimeoutError:
            close_reason = TIMEOUT
            raise asyncio.TimeoutError()
        except Exception as _:
            traceback.print_exc()
        finally:
            with suppress(RuntimeError):
                await Secretary.close_connection(reader=reader, writer=writer, close_reason=close_reason)
        return close_reason

    @staticmethod
    @print_func_name
    async def __initiate_connection(cerebrate_mac):
        '''Tries to open a connection with given cerebrate.
        Throws an asyncio.TimeoutError if no connection is made.
        Returns a reader, writer pair. Both will be None if no connection is made.
        '''
        if cerebrate_mac == mysysteminfo.get_mac_address():
            return None, None
        global event_loop
        cerebrate_ip = cerebratesinfo.get_cerebrate_attribute(cerebrate_mac=cerebrate_mac, record_attribute=cerebratesinfo.Record.IP)
        reader, writer = None, None
        try:
            fut = asyncio.open_connection(host=cerebrate_ip, port=TCP_PORT, loop=event_loop)
            reader, writer = await asyncio.wait_for(fut, timeout=3)
            Secretary._made_contact(mac=cerebrate_mac, ip=cerebrate_ip)
        except asyncio.TimeoutError:
            print("Failed to connect to ", cerebrate_ip)
            raise asyncio.TimeoutError()
        return reader, writer

    @staticmethod
    @print_func_name
    async def communicate_message(cerebrate_mac, msg:Message):
        """Opens a TCP connection with the given cerebrate, provided they are running a Secretary.
        Returns a cc.SUCCESS if connection and initial write are successful.
        No guarantee after that.
        """
        dprint(msg.header)
        dprint(msg.data)
        print("communicating: ", msg.header)
        result_string = "Fail"
        try:
            reader, writer = await Secretary.__initiate_connection(cerebrate_mac=cerebrate_mac)
            if not reader or not writer:
                return result_string
            await Secretary._write_message(writer=writer, msg=msg)
            asyncio.ensure_future(Secretary.__connection_made(reader=reader, writer=writer))
            result_string = cc.SUCCESS
        except asyncio.TimeoutError:
            print(cerebrate_mac, " timed out")
            Secretary._timed_out(mac=cerebrate_mac)
        return result_string

    @staticmethod
    async def __transfer_file(reader, writer, file_name):
        #Determine file location
        filename = file_name
        location = os.path.dirname(file_name)
        if mysysteminfo.get_my_directory() in location:
            location = cc.FileLocation.SOURCE
            filename = filename.replace(mysysteminfo.get_my_directory(), '', 1)
        elif mysysteminfo.get_hive_directory() in location:
            location = cc.FileLocation.HIVE
            filename = filename.replace(mysysteminfo.get_hive_directory(), '', 1)
        else:
            location = cc.FileLocation.ABSOLUTE
        #Send header
        header = Message("file header", data={cc.LOCATION: location, cc.NAME: filename})
        await Secretary._write_message(writer=writer, msg=header)
        #Send file
        with open(file_name, 'r') as open_file:
            data = open_file.read(512)
            while data:
                response = await Secretary._read_message(reader=reader)
                if response == cc.CLOSE_CONNECTION:
                    break
                elif response != cc.READY:
                    #wait for ready
                    continue
                await Secretary._write_message(writer=writer, msg=data)
                data = open_file.read(512)
        #One last wait for READY response
        response = ""
        while response != cc.READY:
            response = await Secretary._read_message(reader=reader)
            if response == cc.CLOSE_CONNECTION:
                return False
        #Send 'eof'
        await Secretary._write_message(writer=writer, msg=cc.FINISHED)
        return True

    @staticmethod
    async def transfer_files(cerebrate_mac, file_names):
        '''Transfers the files (passed as file paths) to the given cerebrate mac.
        Returns True on successful file transfer.
        '''
        try:
            reader, writer = await Secretary.__initiate_connection(cerebrate_mac=cerebrate_mac)
            await Secretary._write_message(writer=writer, msg=Message(cc.FILE_TRANSFER))
            for file_name in file_names:
                response = await Secretary._read_message(reader=reader)
                if response == cc.READY:
                    if not await Secretary.__transfer_file(reader=reader, writer=writer, file_name=file_name):
                        return False
                elif response == cc.CLOSE_CONNECTION:
                    return False
            #receiver sends ready response, so we consume it here before sending close connection
            await Secretary._read_message(reader=reader)
        except asyncio.TimeoutError:
            print(cerebrate_mac, " timed out")
            Secretary._timed_out(mac=cerebrate_mac)
            return False
        except:
            traceback.print_exc()
            return False
        finally:
            await Secretary.close_connection(reader=reader, writer=writer)
        return True

    class UDPServerProtocol:
        def connection_made(self, transport):
            self.transport = transport

        def datagram_received(self, data, addr):
            msg = pickle.loads(data)
            if Secretary.terminating:
                return
            if msg.sender_mac == mysysteminfo.get_mac_address():
                return
            try:
                asyncio.ensure_future(handle_message(msg=msg))
            except Exception as _:
                traceback.print_exc()

    @staticmethod
    @print_func_name
    def send_message(cerebrate_mac, msg:Message):
        '''Sends a UDP message to given cerebrate.
        '''
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cerebrate_ip = cerebratesinfo.get_cerebrate_attribute(cerebrate_mac=cerebrate_mac, record_attribute=cerebratesinfo.Record.IP)
        s.sendto(pickle.dumps(msg), (cerebrate_ip, UDP_PORT))

    @staticmethod
    @print_func_name
    def broadcast_message(msg:Message):
        '''Sends a UDP message to broadcast address.
        '''
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
        s.sendto(pickle.dumps(msg), (BROADCAST, UDP_PORT))

    @staticmethod
    def initialize(loop):
        """Initializes the Secretary, starting a server to accept incoming connections.
        """
        global event_loop
        if not event_loop:
            return False
        Secretary.terminating = False
        Secretary._no_active_connections.set()
        #setup tcp
        tcp_server_coroutine = asyncio.start_server(Secretary.__connection_made, host=mysysteminfo.get_ip_address(), port=TCP_PORT, loop=event_loop)
        Secretary.tcp_server = event_loop.run_until_complete(tcp_server_coroutine)
        #setup udp
        Secretary.udp_server = event_loop.create_datagram_endpoint(Secretary.UDPServerProtocol, local_addr=(mysysteminfo.get_ip_address(), UDP_PORT))
        Secretary.udp_server = event_loop.run_until_complete(Secretary.udp_server)

    @staticmethod
    async def terminate():
        """Shuts down the Secretary, closing current connections and rejecting future connections.
        """
        Secretary.terminating = True
        with suppress(asyncio.CancelledError):
            await Secretary._no_active_connections.wait()
        if Secretary.tcp_server != None:
            Secretary.tcp_server.close()
            Secretary.tcp_server = None
        if Secretary.udp_server != None:
            Secretary.udp_server.close()
            Secretary.udp_server = None


async def terminate():
    """Terminates the Messenger and Secretary.
    Waits until cc.my_state_event[TERMINATING] is set.
    """
    global event_loop
    await cc.my_state_event[cc.State.TERMINATING].wait()
    await Secretary.terminate()
    event_loop = None

def initialize(loop):
    """Initializes the Secretary and sets the event_loop.
    """
    global event_loop
    event_loop = loop
    Secretary.initialize(loop=loop)
    asyncio.ensure_future(terminate(), loop=loop)
    

