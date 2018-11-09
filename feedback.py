from decorators import threaded
from utilities import aprint
import enum
import random



class Response(enum.Enum):
    GREETING = enum.auto()
    AFFIRMATIVE = enum.auto()
    NEGATIVE = enum.auto()
    FAREWELL = enum.auto()


_responses = {
    Response.GREETING: ["Hey", "Hi!", "What's up?"],
    Response.AFFIRMATIVE: ["Sure", "Okay", "Yes", "Yea", "Ya", "Alright", "Affirmative"],
    Response.NEGATIVE: ["No can do", "Nope", "No", "Negative"],
    Response.FAREWELL: ["Seeya", "Bye", "So long"]
}


@threaded
def feedback(output:str):
    aprint(output)
    
@threaded
def feedback_response(response:Response):
    max_index = len(_responses[response]) - 1
    selection = random.randint(0, max_index)
    feedback(_responses[response][selection])