import cerebrate, cerebrate_config as cc
from definitions import Command
from feedback import feedback_response, Response

_commands = {
    '_terminate_': {Command.NAME: 'Terminate', Command.DESCRIPTION: 'Ends this cerebrate.', Command.USE: 'terminate', Command.FUNCTION: "terminate_loop"},
    '_hey_': {Command.NAME: 'Toggle Listening On', Command.DESCRIPTION: 'Toggles audio control on.', Command.USE: 'hey eddie', Command.FUNCTION: "toggle_listening"},
    '_that\'s_all_': {Command.NAME: 'Toggle Listening Off', Command.DESCRIPTION: 'Toggles audio control off.', Command.USE: 'that\'s all', Command.FUNCTION: "toggle_listening"}
}


#@console_only
async def terminate_loop(msg=None, loop=None):
    await cerebrate.terminate(msg=msg, loop=loop)

async def toggle_listening(msg):
    command_complete = False
    if "hey" in msg.data:
        if not cc.accept_audio_control.is_set():
            cc.accept_audio_control.set()
            cc.feedback_on_commands(True)
            feedback_response(Response.GREETING)
            # No command_complete, as this potentially blocks a command that just happened to be preceded by "hey"
    if "that's all" in msg.data:
        if cc.accept_audio_control.is_set():
            cc.accept_audio_control.clear()
            cc.feedback_on_commands(False)
            feedback_response(Response.FAREWELL)
            command_complete = True
    return command_complete