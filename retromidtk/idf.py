from xml.etree import ElementTree as ET
from typing import NamedTuple, Optional


class Controller(NamedTuple):
    name: str
    lsb: Optional[int] = None
    msb: Optional[int] = None
    type: str = ""
    init: Optional[int] = None
    min: Optional[int] = None
    max: Optional[int] = None


def add_controller(
    el: ET.Element,
    controller: Controller,
) -> ET.SubElement:
    attribs = {
        "name": controller.name,
    }
    if controller.type:
        attribs["type"] = controller.type

    if controller.msb is not None:
        attribs["h"] = str(controller.msb)

    if controller.lsb is not None:
        attribs["l"] = str(controller.lsb)

    if controller.min is not None:
        attribs["min"] = str(controller.min)

    if controller.max is not None:
        attribs["max"] = str(controller.max)

    if controller.init is not None:
        attribs["init"] = str(controller.init)

    return ET.SubElement(
        el,
        "Controller",
        attribs,
    )
