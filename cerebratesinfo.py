import collections
import os
import shelve
import json
import enum
import datetime
import logging
import mysysteminfo
from utilities import dprint



CEREBRATE_RECORDS = os.path.join(mysysteminfo.get_hive_directory(), 'cerebrates.db')

MY_RECORD_DEFAULT_NAME = 'myinfo'


class Record(enum.Enum):
	NAME = enum.auto()
	MAC = enum.auto()
	IP = enum.auto()
	LOCATION = enum.auto()
	ROLE = enum.auto()
	STATUS = enum.auto()
	LASTCONTACT = enum.auto()

class Status(enum.Enum):
	AWAKE = enum.auto()
	UNKNOWN = enum.auto()
	ASLEEP = enum.auto()

class Role(enum.Enum):
	OVERMIND = enum.auto()
	QUEEN = enum.auto()
	DRONE = enum.auto()

def default_dictionary():
	return collections.defaultdict(default_dictionary)

initialized = False


def get_cerebrate_names():
    '''Returns an iterator for all known cerebrate names.
    '''
    with shelve.open(CEREBRATE_RECORDS, flag='r') as db:
        for key in db:
            yield db[key].get(Record.NAME, "unknown")

def get_cerebrate_mac(record_attribute, cerebrate_attribute):
    '''Returns the mac of the cerebrate with the given attribute value.
    Returns None if no matches are found.
    '''
    with shelve.open(CEREBRATE_RECORDS, flag='r') as db:
        for key in db:
            if db[key].get(record_attribute, "unknown") == cerebrate_attribute:
                return db[key].get(Record.MAC)
    return None

def get_cerebrate_macs():
    '''Returns a list of all known cerebrate macs.
    '''
    macs = []
    with shelve.open(CEREBRATE_RECORDS, flag='r') as db:
        for key in db:
            macs.append(db[key].get(Record.MAC, "unknown"))
    return macs
    
def get_cerebrate_locations():
    '''Returns a list of all known cerebrate locations.
    '''
    locations = []
    with shelve.open(CEREBRATE_RECORDS, flag='r') as db:
        for key in db:
            locations.append(db[key].get(Record.LOCATION, "unknown"))
    return locations

def update_cerebrate_attribute(mac, record_attribute, attribute_value):
    if not mac:
        return False
    with shelve.open(CEREBRATE_RECORDS, writeback=True) as db:
        if not db.get(mac, None):
            db[mac] = default_dictionary()
            db[mac][Record.MAC] = mac
        db[mac][record_attribute] = attribute_value
    return True

def update_cerebrate_record(cerebrate_record):
    '''Overwrites the appropriate cerebrate record with the given record.
    Creates a new one if the given cerebrate does not exist.
    Returns False if no MAC is given in record.
    '''
    mac = cerebrate_record.get(Record.MAC, None)
    if not mac:
        logging.warning('No MAC address provided in record:')
        logging.info(''.join(("record: ", str(cerebrate_record))))
        return False
    with shelve.open(CEREBRATE_RECORDS, writeback=True) as db:
        if not db.get(mac, None):
            db[mac] = default_dictionary()
        cerebrate_time = cerebrate_record.get(Record.LASTCONTACT, datetime.datetime(1, 1, 1))
        db_time = db[mac].get(Record.LASTCONTACT, datetime.datetime(1, 1, 1))
        if cerebrate_time >= db_time:
            dprint("Updating record:")
            dprint(cerebrate_record)
            db[mac] = cerebrate_record
            return True
        else:
            dprint("Out of date:")
            dprint(cerebrate_record)
            return False
    return True

def get_cerebrate_record(record_attribute, attribute_value):
    '''Returns the first cerebrate found that matches the given attribute value.
    Returns None if no matching cerebrate is found.
    '''
    with shelve.open(CEREBRATE_RECORDS, flag='r') as db:
	    return next((db[key] for key in db if db[key].get(record_attribute, "").upper() == attribute_value.upper()), None)
    return None

def get_overmind_record():
    with shelve.open(CEREBRATE_RECORDS, flag='r') as db:
        return next((db[key] for key in db if db[key].get(Record.ROLE, Role.DRONE) == Role.OVERMIND), get_cerebrate_record(record_attribute=Record.MAC, attribute_value=mysysteminfo.get_mac_address()))

def get_overmind_mac():
    record = get_overmind_record()
    return record.get(Record.MAC, '')

def get_cerebrate_records():
    '''Returns an iterator for all known cerebrate records.
    '''
    with shelve.open(CEREBRATE_RECORDS, flag='r') as db:
        for key in db:
            yield db[key]

def get_cerebrate_records_list():
    '''Returns the full list of all known cerebrate records.
    '''
    records = []
    for record in get_cerebrate_records():
        records.append(record)
    return records

def get_cerebrate_attribute(cerebrate_mac, record_attribute):
    '''Returns the requested attribute value for the given cerebrate.
    Returns an empty string if the cerebrate does not have a value for that attribute.
    '''
    with shelve.open(CEREBRATE_RECORDS, flag='r') as db:
    	return db[cerebrate_mac].get(record_attribute, "")

def update_my_record():
    '''Updates the local cerebrate's record (mostly IP address, but also sets defaults for any attributes without values).
    '''
    my_record = get_cerebrate_record(record_attribute=Record.MAC, attribute_value=mysysteminfo.get_mac_address()) or default_dictionary()
    my_record[Record.NAME] = my_record.get(Record.NAME, MY_RECORD_DEFAULT_NAME)
    my_record[Record.MAC] = my_record.get(Record.MAC, mysysteminfo.get_mac_address())
    my_record[Record.IP] = mysysteminfo.get_ip_address()
    my_record[Record.LASTCONTACT] = datetime.datetime.now()
    my_record[Record.STATUS] = Status.AWAKE
    my_record[Record.ROLE] = my_record.get(Record.ROLE, Role.DRONE)
    update_cerebrate_record(cerebrate_record=my_record)

def update_cerebrate_contact_time(mac):
    if not mac:
        return False
    with shelve.open(CEREBRATE_RECORDS, writeback=True) as db:
        if not db.get(mac, None):
            db[mac] = default_dictionary()
            db[mac][Record.MAC] = mac
        db[mac][Record.LASTCONTACT] = datetime.datetime.now()
    return True

def designate_overmind(mac):
    if not mac:
        return False
    success = False
    with shelve.open(CEREBRATE_RECORDS, writeback=True) as db:
        if not db.get(mac, None):
            db[mac] = default_dictionary()
            db[mac][Record.MAC] = mac
        for record in get_cerebrate_records():
            if record.get(Record.MAC) == mac:
                db[mac][Record.ROLE] = Role.OVERMIND
                success = True
            elif record.get(Record.ROLE, Role.DRONE) == Role.OVERMIND:
                db[record.get(Record.MAC)][Record.ROLE] = Role.QUEEN
    #if success:
        #update_cerebrate_contact_time(mac)
    return success

#for testing
def add_specific_record():
    record = default_dictionary()
    record[Record.NAME] = 'jarvis'
    record[Record.MAC] = '54:04:A6:08:AA:9F'
    record[Record.IP] = '192.168.0.19'
    record[Record.LASTCONTACT] = datetime.datetime(1, 1, 1)
    record[Record.STATUS] = Status.AWAKE
    record[Record.ROLE] = Role.DRONE
    update_cerebrate_record(cerebrate_record=record)

def load():
    '''Handles any setup needed.
    '''
    update_my_record()
    #add_specific_record()

if not initialized:
    initialized = True
    os.makedirs(CEREBRATE_RECORDS, exist_ok=True)
    with shelve.open(CEREBRATE_RECORDS, flag='c'):
        '''do nothing'''
    load()