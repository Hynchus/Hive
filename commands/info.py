from definitions import Command
from decorators import console_only
import command
from utilities import aprint, prompt
from communication import distill_msg
import audio, cerebratesinfo, communication, mysysteminfo
import traceback
import re


_commands = {
    '_change_': {Command.NAME: 'Change Info', Command.DESCRIPTION: 'Change intended information.', Command.USE: 'change [info specifier][new info]', Command.FUNCTION: "change"},
    '_list_': {Command.NAME: 'List Info', Command.DESCRIPTION: 'Lists requested information.', Command.USE: 'list [info specifier][filter terms]', Command.FUNCTION: "list_info"},
    '_help_': {Command.NAME: 'Help', Command.DESCRIPTION: 'Get descriptions and use examples for available commands.', Command.USE: 'help [command specifier(s)]', Command.FUNCTION: "info"}
}


@console_only
async def change(msg):
    attribute_recognized = False
    while True:
        cmd = command.format_command(msg.data)
        if "_mic" in cmd:
            attribute_recognized = True
            audio.list_microphones()
            input = prompt(prompt_string="\nMicrophone index: ")
            index = int(re.search(r'\d+', input).group())
            if index:
                if audio.setup_microphone(mic_index=index):
                    print("Microphone ", index, " is active")
                else:
                    print("Could not set microphone ", index)
            else:
                print("index not recognized")
        record = cerebratesinfo.get_cerebrate_record(record_attribute=cerebratesinfo.Record.MAC, attribute_value=mysysteminfo.get_mac_address())
        if record is None:
            aprint("My record has been misplaced")
            return False
        if "_name_" in cmd:
            attribute_recognized = True
            current_name = record.get(cerebratesinfo.Record.NAME, "unknown")
            aprint("Current name: ", current_name)
            record[cerebratesinfo.Record.NAME] = await prompt(prompt_string="New name")
            cerebratesinfo.update_cerebrate_record(cerebrate_record=record)
            aprint(current_name, " => ", record.get(cerebratesinfo.Record.NAME, "unknown"))
        if "_location_" in cmd:
            attribute_recognized = True
            current_location = record.get(cerebratesinfo.Record.LOCATION, "unknown")
            aprint("Current location: ", current_location)
            record[cerebratesinfo.Record.LOCATION] = await prompt(prompt_string="New location")
            cerebratesinfo.update_cerebrate_record(cerebrate_record=record)
            aprint(current_location, " => ", record.get(cerebratesinfo.Record.LOCATION, "unknown"))
        '''
        if "_role_" in cmd:
            attribute_recognized = True
            current_role = record.get(cerebratesinfo.Record.ROLE, "unknown")
            aprint("Current Role: ", current_role)
            for role in cerebratesinfo.Role:
                aprint(role.value, ") ", role.name)
            number = int(await prompt("New role (number)"))
            for role in cerebratesinfo.Role:
                if role.value == number:
                    cerebratesinfo.update_cerebrate_attribute(mysysteminfo.get_mac_address(), cerebratesinfo.Record.ROLE, role)
                    aprint(current_role.name, " => ", role.name)
                    break
        '''
        response = None
        if not attribute_recognized:
            return False
            #response = ''.join(("_", await prompt(prompt_string="What do you want changed? "), "_"))
        else:
            response = ''.join(("_", await prompt(prompt_string="Any other changes? "), "_"))
        if "_nothing_" in response or "_no_" in response:
            break
        msg.data = response
        aprint("")
    #broadcast the changes we made to other cerebrates
    cerebratesinfo.update_cerebrate_contact_time(mac=mysysteminfo.get_mac_address())
    msg = communication.Message("update_records", data=[cerebratesinfo.get_cerebrate_record(record_attribute=cerebratesinfo.Record.MAC, attribute_value=mysysteminfo.get_mac_address())])
    if cerebratesinfo.get_overmind_mac() == mysysteminfo.get_mac_address():
        communication.Secretary.broadcast_message(msg=msg)
    else:
        await communication.Secretary.communicate_message(cerebrate_mac=cerebratesinfo.get_overmind_mac(), msg=msg)
    return True

async def list_info(msg):
    cmd = command.format_command(cmd=msg.data)
    if "_cerebrate" in cmd:
        response = ""
        requested_attributes = []
        if "_everything_" in cmd:
            requested_attributes = cerebratesinfo.Record
        else:
            unsorted_requested_attributes = []
            for attribute in cerebratesinfo.Record:
                index = cmd.find(attribute.name.lower())
                if index >= 0:
                    unsorted_requested_attributes.append((index, attribute))

            if len(unsorted_requested_attributes) <= 0:
                requested_attributes = cerebratesinfo.Record
            else:
                def by_index(pair): 
                    return pair[0]
                unsorted_requested_attributes.sort(key=by_index)
                requested_attributes = [pair[1] for pair in unsorted_requested_attributes]
        
        header = " | ".join([attribute.name for attribute in requested_attributes])
        for record in cerebratesinfo.get_cerebrate_records():
            record_attributes = [str(record.get(attribute, "unknown")) for attribute in requested_attributes]
            response = ''.join((response, "\t===] ", " | ".join(record_attributes), " [===\n"))
        aprint("\nCerebrates Information\t( ", header, " )\n\n", response)
        return True
    if "_mic" in cmd:
        audio.list_microphones()
        aprint("")
        return True
    #print("I don't know what it is you want listed")
    return False

async def info(msg):
    check = None
    try:
        data = command.format_command(cmd=distill_msg(msg, "help").data)
        everything = True
        for _, _, command_dict in command.get_all_commands():
            check = command_dict
            if command_dict[Command.NAME].lower() in data:
                everything = False
                print("\n", command_dict[Command.NAME], ": ", command_dict[Command.DESCRIPTION])
                print("\t", command_dict[Command.USE])
        if everything:
            for _, _, command_dict in command.get_all_commands():
                print("\n", command_dict[Command.NAME], ": ", command_dict[Command.DESCRIPTION])
                print("\t", command_dict[Command.USE])
    except:
        traceback.print_exc()
        print(check)
    return True