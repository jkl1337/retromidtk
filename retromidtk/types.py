from dataclasses import dataclass, field
from typing import IO, List, NamedTuple


class ParseError(ValueError):
    def __init__(self, file_name: str, line_no: int, message: str):
        super().__init__(f"{file_name}:{line_no}: {message}")


INDENT = 3
SPACE = " "


def to_json(o, fp: IO[str], level: int = 0) -> None:
    """Serialize the given object to JSON with custom whitespace for lists.

    :param o: The object to serialize.
    :param fp: The file-like object to write to.
    :param level: The current indentation level.

    This serializer has a peculiar way of handling lists. If the list is a top-level, then it will be
    formatted with one item per line. If the list is deeper, then it will be formatted with all items on one
    line. This balances readability with compactness.
    """
    if isinstance(o, dict):
        fp.write("{\n")
        comma = ""
        for k, v in o.items():
            fp.write(comma)
            comma = ",\n"
            fp.write(SPACE * INDENT * (level + 1))
            fp.write('"' + str(k) + '":' + SPACE)
            to_json(v, fp, level + 1)

        fp.write("\n" + SPACE * INDENT * level + "}")
    elif isinstance(o, str):
        fp.write('"')
        fp.write(o)
        fp.write('"')
    elif isinstance(o, list) or isinstance(o, tuple):
        fp.write("[\n" if level < 2 else "[")
        comma = ""
        for v in o:
            fp.write(comma)
            if level < 2:
                comma = ",\n"
                fp.write(SPACE * INDENT * (level + 1))
            else:
                comma = ","
            to_json(v, fp, level + 1)
        fp.write("]")
    elif isinstance(o, bool):
        fp.write("true" if o else "false")
    elif isinstance(o, int):
        fp.write(str(o))
    elif isinstance(o, float):
        fp.write("%.7g" % o)
    elif o is None:
        fp.write("null")
    elif isinstance(o, Group):
        to_json(encode_group(o), fp, level)
    elif isinstance(o, DrumSet):
        to_json(encode_drum_set(o), fp, level)
    else:
        raise TypeError("Unknown type '%s' for json serialization" % str(type(o)))


class Patch(NamedTuple):
    msb: int
    lsb: int
    pc: int
    name: str
    drum: bool = False


class DrumSound(NamedTuple):
    key: int
    name: str


@dataclass
class Group:
    id: int
    name: str
    groups: List["Group"] = field(default_factory=list)
    patches: List[int] = field(default_factory=list)


@dataclass
class DrumSet:
    patch_id: int
    sounds: List[DrumSound] = field(default_factory=list)


def encode_drum_set(drum_set: DrumSet) -> dict:
    """Encode a drum set as a dictionary."""
    return {
        "patch": drum_set.patch_id,
        "sounds": drum_set.sounds,
    }


def encode_group(group: Group) -> dict:
    """Encode a group as a dictionary."""
    ret = {
        "id": group.id,
        "name": group.name,
    }
    if group.groups:
        ret["groups"] = [encode_group(g) for g in group.groups]
    if group.patches:
        ret["patches"] = [p for p in group.patches]
    return ret
