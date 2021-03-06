import asyncio
import datetime
import cerebrate_config as cc
from utilities import aprint, dprint, get_cerebrate_file_names
from decorators import print_func_name
import cerebrate, cerebratesinfo, command, communication, mysysteminfo, requirements
from definitions import Resource
from resources import resource_handler




async def ping(msg):
    if msg.data != None:
        aprint(msg.data)
    else:
        aprint("PING from ", msg.sender_mac)
    return cc.CLOSE_CONNECTION, cc.SUCCESS

async def display_message(msg):
    aprint(msg.data)
    return cc.CLOSE_CONNECTION, cc.SUCCESS

@print_func_name
async def send_update(msg):
    version = msg.data.get("version", None)
    if not version:
        return cc.CLOSE_CONNECTION, "requester's version number not included"
    if version >= cc.my_version:
        return cc.CLOSE_CONNECTION, "requester not out of date"
    requirements.update_requirements()
    dprint("Sending updates to ", msg.sender_mac)
    files = await get_cerebrate_file_names()
    success = await communication.Secretary.transfer_files(cerebrate_mac=msg.sender_mac, file_names=files)
    if success:
        await communication.Secretary.communicate_message(cerebrate_mac=msg.sender_mac, msg=communication.Message("restart", data="cerebrate updated"))
    else:
        dprint("FAILED TO UPDATE ", msg.sender_mac)
        return cc.CLOSE_CONNECTION, "failed"
    return cc.CLOSE_CONNECTION, cc.SUCCESS

@print_func_name
async def check_version(msg):
    '''Compares cerebrate versions, requesting an update if needed.
    '''
    if cc.update_in_progress:
        return cc.CLOSE_CONNECTION, "update in progress"
    version = msg.data.get("version", None)
    if not version:
        return cc.CLOSE_CONNECTION, cc.FINISHED
    if cc.my_version > version:
        await communication.Secretary.communicate_message(cerebrate_mac=msg.sender_mac, msg=communication.Message("check_version", data={"version": cc.my_version}))
    elif cc.my_version < version:
        cc.update_in_progress = True
        print("Updating...")
        await communication.Secretary.communicate_message(cerebrate_mac=msg.sender_mac, msg=communication.Message("send_update", data={"version": cc.my_version}))
    return cc.CLOSE_CONNECTION, cc.FINISHED

@print_func_name
async def _designate_overmind(mac):
    if cerebratesinfo.get_overmind_mac() == mac:
        return
    dprint("designating ", mac)
    cerebratesinfo.designate_overmind(mac=mac)
    if mac != mysysteminfo.get_mac_address():
        '''shouldn't need to ask for acknowledgment, cerebrates are already up to date'''
        #dprint("asking for acknowledgment")
        #await communication.Secretary.communicate_message(cerebrate_mac=mac, msg=communication.Message("acknowledge", data={"version": cc.my_version}))
    else:
        communication.Secretary.broadcast_message(msg=communication.Message("update_records", cc.OVERRULE, data=[cerebratesinfo.get_overmind_record()]))

@print_func_name
async def _send_all_resources(cerebrate_mac):
    for section, resource_dict in resource_handler.get_all_resources_by_section(with_timestamp=True):
        if len(resource_dict) >= 1:
            await communication.Secretary.communicate_message(cerebrate_mac=cerebrate_mac, msg=communication.Message("update_resources", ':'.join((str(resource_handler.Resource.SECTION), section)), data=[resource_dict]))

@print_func_name
async def send_resources(msg):
    '''Sends all locally stored resources to msg sender.
    '''
    await _send_all_resources(cerebrate_mac=msg.sender_mac)
    return cc.CLOSE_CONNECTION, cc.SUCCESS

@print_func_name
async def acknowledge(msg):
    '''Initiates file and record updating between cerebrates.
    When a cerebrate comes online it broadcasts to other cerebrates asking for acknowledgment.
    Only the Overmind responds.
    '''
    #Only respond if local is the Overmind
    if cerebratesinfo.get_overmind_mac() != mysysteminfo.get_mac_address():
        return cc.CLOSE_CONNECTION, cc.FINISHED
    dprint("acknowledging")
    #Send a current list of records
    await communication.Secretary.communicate_message(cerebrate_mac=msg.sender_mac, msg=communication.Message("update_records", cc.RECIPROCATE, cc.OVERRULE, data=cerebratesinfo.get_cerebrate_records_list()))
    #Send a current list of resources
    await _send_all_resources(cerebrate_mac=msg.sender_mac)
    #Get a current list of their resources
    await communication.Secretary.communicate_message(cerebrate_mac=msg.sender_mac, msg=communication.Message("send_resources"))
    #Ensure up-to-date files
    if msg.data.get("version", None):
        return await check_version(msg=msg)
    return cc.CLOSE_CONNECTION, cc.SUCCESS

@print_func_name
async def update_records(msg):
    '''Message data must contain a list of cerebrate records.
    Updates the local cerebrate records with the given ones, if the given ones contain more recent information.
    If CC.RECIPROCATE is in the header a Message containing the local copy of updated cerebrate records will be returned.
    '''
    if cc.OVERRULE in msg.header:
        dprint("Being overruled")
        await _designate_overmind(mac=msg.sender_mac)
    dprint("updating records from ", msg.sender_mac)
    propagate = (cerebratesinfo.get_overmind_mac() == mysysteminfo.get_mac_address())
    for record in msg.data:
        #if Overmind receives new information then propagate it to other cerebrates
        if cerebratesinfo.update_cerebrate_record(cerebrate_record=record) and propagate:
            communication.Secretary.broadcast_message(msg=communication.Message("update_records", data=[record]))
    if cc.RECIPROCATE in msg.header:
        return cc.REMOTE_COMMAND, communication.Message("update_records", data=cerebratesinfo.get_cerebrate_records_list())
    return cc.CLOSE_CONNECTION, "records updated"

@print_func_name
async def update_resources(msg):
    '''Message header must contain str(Resource.SECTION):section.
    Message data must contain a dict of resources.
    Updates the local resources with the given ones.
    '''
    dprint("updating resources from ", msg.sender_mac)
    propagate = (cerebratesinfo.get_overmind_mac() == mysysteminfo.get_mac_address())
    section = None
    for header in msg.header:
        if str(Resource.SECTION) in header:
            split_header = header.split(':')
            if len(split_header) <= 1:
                continue
            section = split_header[len(split_header) - 1]
            if section:
                break
    if not section:
        return cc.CLOSE_CONNECTION, "no section supplied in header"
    for resources in msg.data:
        #if Overmind receives new information then propagate it to other cerebrates
        if resource_handler.update_resources(section=section, resources=resources) and propagate:
            communication.Secretary.broadcast_message(msg=communication.Message("update_resources", ':'.join((str(Resource.SECTION), section)), data=[resources]))
    return cc.CLOSE_CONNECTION, "resources updated"

@print_func_name
async def assume_overmind(msg):
    '''Sets self as Overmind, broadcasts the change to others.
    '''
    dprint("Assuming Overmind")
    await _designate_overmind(mac=mysysteminfo.get_mac_address())
    return cc.CLOSE_CONNECTION, cc.SUCCESS

async def restart(msg):
    cc.restart_cerebrate_on_terminate = True
    if "cerebrate updated" in msg.data.lower():
        requirements.install_requirements()
    await cerebrate.terminate()

async def run_command(msg):
    '''Given a Message, runs the contained command if possible 
    Returns an action, data pair.
    '''
    if cc.my_state_event[cc.State.TERMINATING].is_set():
        return cc.CLOSE_CONNECTION, "cerebrate terminating"
    formatted_header = command.format_header(header=msg.header)
    cerebratesinfo.update_cerebrate_contact_time(mac=mysysteminfo.get_mac_address())
    for key, _ in commands.items():
        if key in formatted_header:
            dprint("before: ", cerebratesinfo.get_overmind_mac())
            result = await commands[key][command.Command.FUNCTION](msg)
            dprint("after: ", cerebratesinfo.get_overmind_mac())
            return result
    return cc.CLOSE_CONNECTION, "command not recognized"


commands = {
    'acknowledge': {command.Command.FUNCTION: acknowledge},
    'update_records': {command.Command.FUNCTION: update_records},
    'update_resources': {command.Command.FUNCTION: update_resources},
    'ping': {command.Command.FUNCTION: ping},
    'display_message': {command.Command.FUNCTION: display_message},
    'assume_overmind': {command.Command.FUNCTION: assume_overmind},
    'check_version': {command.Command.FUNCTION: check_version},
    'send_resources': {command.Command.FUNCTION: send_resources},
    'send_update': {command.Command.FUNCTION: send_update},
    'restart': {command.Command.FUNCTION: restart}
}