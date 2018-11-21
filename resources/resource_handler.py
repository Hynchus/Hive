import os
import shelve
import datetime
import cerebratesinfo
import communication
import asyncio
import traceback
from utilities import run_coroutine
from definitions import Resource
from mysysteminfo import get_hive_directory, get_mac_address
from abc import ABC, abstractmethod

RESOURCES_BASE_LOCATION = os.path.join(get_hive_directory(), "resources")
RESOURCE_FILE_EXTENSION = "res"

MODIFIED_TIME = "res_modified_time"
RESOURCE_VALUE = "res_value"

initialized = False


class Resource_BC(ABC):
	'''Base class for resource classes.
	'''
	@abstractmethod
	def update(self, resource):
		'''Updates this resource instance with the given resource instance.
		If given resource instance class does not match this one an EnvironmentError will be raised.
		'''
		if type(resource) != type(self):
			raise EnvironmentError


def _get_file_location(section:str):
	filename = '.'.join((section, RESOURCE_FILE_EXTENSION))
	filepath = os.path.join(RESOURCES_BASE_LOCATION, section)
	if not os.path.exists(filepath):
		os.makedirs(filepath, exist_ok=True)
	return os.path.join(filepath, filename)

def _update_resources_modified_time(resources:dict):
	'''Updates resources modified time to now.
	Returns resources.
	'''
	for key, value in resources.items():
		if type(value) is dict and value.get(MODIFIED_TIME, None):
			value[MODIFIED_TIME] = datetime.datetime.now()
		else:
			value = {RESOURCE_VALUE: value, MODIFIED_TIME: datetime.datetime.now()}
		resources[key] = value
	return resources

def propagate_resources(section:str, timestamped_resources:dict):
	overmind_mac = cerebratesinfo.get_overmind_mac()
	msg = communication.Message("update_resources", ':'.join((str(Resource.SECTION), section)), data=[timestamped_resources])
	if get_mac_address() == overmind_mac:
		run_coroutine(communication.Secretary.broadcast_message(msg=msg))
	else:
		run_coroutine(communication.Secretary.communicate_message(cerebrate_mac=overmind_mac, msg=msg))

def store_resources(section:str, resources:dict):
	'''Saves  resources for later reference, overwriting existing records with the same keys.
	Returns False if unsuccessful.
	'''
	try:
		if len(resources) <= 0:
			return True
		timestamped_resources = _update_resources_modified_time(resources)
		update_resources(section=section, resources=resources)
		if get_mac_address() != cerebratesinfo.get_overmind_mac():
			propagate_resources(section=section, timestamped_resources=timestamped_resources)
	except Exception:
		traceback.print_exc()
		return False
	return True

def update_resources(section:str, resources:dict):
	'''Updates resources if the given resources are more recent.
	Returns a dict of the updated resources.
	'''
	# NOT FULLY CORRECT: If local copy of resource has had more recent changes it will not accept the given resource even if given contains changes local has not seen
	updated_resources = {}
	try:
		with shelve.open(filename=_get_file_location(section=section), flag='c', writeback=True) as s:
			for key, value in resources.items():
				if key not in s.keys():
					s[key] = value
					updated_resources[key] = value
				elif value.get(MODIFIED_TIME, datetime.datetime(1, 1, 1)) > s[key].get(MODIFIED_TIME, datetime.datetime(1, 1, 1)):
					try:
						#if resource is derived from Resource_BC
						s[key][RESOURCE_VALUE].update(value[RESOURCE_VALUE])
						s[key][MODIFIED_TIME] = value[MODIFIED_TIME]
					except:
						#resource is not derived from Resource_BC
						s[key] = value
					updated_resources[key] = s[key]
	except:
		raise
	if len(updated_resources) > 0 and get_mac_address() == cerebratesinfo.get_overmind_mac():
		propagate_resources(section=section, timestamped_resources=updated_resources)
	return updated_resources

def get_resource(section:str, key:str):
	'''Retrieves the specified resource value.
	Returns None if it could not be found.
	'''
	try:
		resource_value = None
		with shelve.open(filename=_get_file_location(section=section), flag='r') as s:
			resource_value = s.get(key, None)
			if resource_value:
				resource_value = resource_value.get(RESOURCE_VALUE, resource_value)
	except:
		'''section doesn't exist or resource was saved incorrectly'''
	return resource_value

def get_resources(section:str, with_timestamp=False):
	'''Generator for resources in given section.
	Yields key, value tuples.
	'''
	try:
		with shelve.open(filename=_get_file_location(section=section), flag='r') as s:
			for key, value in s.items():
				if not with_timestamp:
					value = value.get(RESOURCE_VALUE, value)
				yield key, value
	except:
		'''section doesn't exist'''
		return

def get_resource_keys(section:str):
	'''Returns a list of all keys in given section.
	'''
	keys = []
	try:
		with shelve.open(filename=_get_file_location(section=section), flag='r') as s:
			keys = list(s.keys())
	except:
		'''section doesn't exist'''
	return keys

def get_all_resources_by_section(with_timestamp=False):
	'''Generator for all sections.
	Yields section and a dict of resources.
	'''
	for dirname, _, _ in os.walk(RESOURCES_BASE_LOCATION):
		section = os.path.basename(dirname)
		resources = {}
		for key, value in get_resources(section=section, with_timestamp=with_timestamp):
			resources[key] = value
		yield section, resources

def get_all_resources():
	'''Generator for all resources.
	Yields section, key, value tuples.
	'''
	for dirname, _, _ in os.walk(RESOURCES_BASE_LOCATION):
		section = os.path.basename(dirname)
		for key, value in get_resources(section):
			yield section, key, value