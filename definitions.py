import enum

class Command(enum.Enum):
    MODULE = enum.auto()
    NAME = enum.auto()
    DESCRIPTION = enum.auto()
    USE = enum.auto()
    FUNCTION = enum.auto()

class Resource(enum.Enum):
    SECTION = enum.auto()
    VALUE = enum.auto()

CEREBRATE_FILE_EXTENSIONS = ["py", "edy"]