import socket
import enum
import os
from sys import platform
from uuid import getnode

_my_mac_address = None

class OS(enum.Enum):
	LINUX = enum.auto()
	WINDOWS = enum.auto()
	OTHER = enum.auto()

def get_ip_address():
	return socket.gethostbyname(socket.gethostname())

def get_mac_address():
	return _my_mac_address

def get_os():
	if platform == "win32":
		return OS.WINDOWS
	elif platform == "linux" or platform == "linux2":
		return OS.LINUX
	return OS.OTHER

def get_my_directory():
	return os.path.dirname(os.path.abspath(__file__))

def get_hive_directory():
	return os.path.join((os.getenv('APPDATA') if os.name == 'nt' else '~'), 'hive')


_my_mac_address = ':'.join(("%012X" % getnode())[i:i+2] for i in range(0, 12, 2))

print("\nCerebrate system info:")
print("\tIP : " + get_ip_address())
print("\tMAC: " + get_mac_address())
print("\tOS : " + get_os().name)
print("\tDIR: " + get_my_directory())
print("")