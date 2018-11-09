# Based on wol.py from http://code.activestate.com/recipes/358449-wake-on-lan/
# Amended to use configuration file and hostnames
#
# Copyright (C) Fadly Tabrani, B Tasker
#
# Released under the PSF License See http://docs.python.org/2/license.html
#
#


import socket
import struct
import os
import sys
import configparser
import cerebratesinfo




def wake_cerebrate(cerebrate_mac):
    """ Switches on remote computer using WOL. """

    #try:
    #  macaddress = cerebratesinfo.CerebrateInfo.get_cerebrate_mac(cerebratesinfo.Record.NAME, cerebrate_name)
      #macaddress = myconfig[cerebrate_name]['mac']
    #  if macaddress == None:
    #      return "macaddress for '" + cerebrate_name + "' could not be found."
    #except Exception as e:
    #  return "Exception raised while getting macaddress:\n" + e

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
        send_data = b''.join([send_data,
                             struct.pack('B', int(data[i: i + 2], 16))])

    # Broadcast it to the LAN.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(send_data, ('<broadcast>', 7))
    print(cerebrate_name + " prodded.")
    return True

# NOT BEING USED: loadConfig() is not needed. If needed, make myconfig variable global. 
def loadConfig():
	""" Read in the Configuration file to get CDN specific settings
	"""
	mydir = os.path.dirname(os.path.abspath(__file__))
	myconfig = {}
	Config = configparser.ConfigParser()
	Config.read(mydir+"/.wol_config.ini")
	sections = Config.sections()
	for section in sections:
		options = Config.options(section)

		sectkey = section
		myconfig[sectkey] = {}


		for option in options:
			myconfig[sectkey][option] = Config.get(section,option)


	return myconfig # Useful for testing

def usage():
	print('Usage: wakeuptest.py [cerebrate mac]')



if __name__ == '__main__':
        
        #conf = loadConfig()
        try:
                # Use macaddresses with any seperators.
                if sys.argv[1] == 'list':
                        print('Known Cerebrates:')
                        for i in cerebratesinfo.get_cerebrate_names():
                            print('\t%s' % i)
                        print('')
                else:
                        if not wake_cerebrate(sys.argv[1]):
                                print('Cerebrate name not recognized')
                        else:
                                print('Cerebrate \'%s\' awakens' % sys.argv[1])
        except:
            usage()