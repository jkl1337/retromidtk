#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import xml.etree.ElementTree as ET
from operator import itemgetter
from typing import NamedTuple

from retromidtk.idf import Controller, add_controller
from retromidtk.types import Instrument, Patch, from_json

CONTROLLERS = [
    Controller("Modulation", 1),
    Controller("Portamento Time", 5),
    Controller("Main Volume", 7, init=127),
    Controller("Pan", 10, init=0, min=-64, max=63),
    Controller("Expression", 11, init=127),
    Controller("Hold 1", 64),
    Controller("Portamento", 65),
    Controller("Sostenuto", 66),
    Controller("Soft Pedal", 67),
    Controller("Legato Foot Switch", 68),
    Controller("Resonance", 71, init=0, min=-64, max=63),
    Controller("Release Time", 72, init=0, min=-64, max=63),
    Controller("Attack Time", 73, init=0, min=-64, max=63),
    Controller("Cutoff", 74, init=0, min=-64, max=63),
    Controller("Decay Time", 75, init=0, min=-64, max=63),
    Controller("Vibrato Rate", 76, init=0, min=-64, max=63),
    Controller("Vibrato Depth", 77, init=0, min=-64, max=63),
    Controller("Vibrato Delay", 78, init=0, min=-64, max=63),
    Controller("General Purpose 5", 80),
    Controller("General Purpose 6", 81),
    Controller("General Purpose 7", 82),
    Controller("General Purpose 8", 83),
    Controller("Portamento Control", 84),
    Controller("Effect 1 (Reverb Send Level)", 91),
    Controller("Effect 3 (Chorus Send Level)", 93),
    Controller("Pitch Bend Sensitivity", 0, 0, "RPN", init=2, min=0, max=24),
    Controller("Master Fine Tuning", 1, 0, "RPN14", init=0, min=-8192, max=8191),
    Controller("Master Coarse Tuning", 2, 0, "RPN", init=0, min=-48, max=48),
    Controller("All Sound Off", 120),
    Controller("Reset Controllers Off", 121),
    Controller("All Notes Off", 123),
    Controller("Omni Mode Off", 124),
    Controller("Omni Mode On", 125),
    Controller("Mono Mode On", 126),
    Controller("Poly Mode On", 127),
    Controller("Pitch", type="Pitch"),
    Controller("Program", type="Program"),
    Controller("Poly Aftertouch", type="PolyAftertouch"),
    Controller("Aftertouch", type="Aftertouch"),
]


class GroupConfig(NamedTuple):
    name: str
    pc_min: int
    pc_max: int


PATCH_TOP_GROUPS: list[GroupConfig] = [
    GroupConfig(n, i * 8, i * 8 + 7)
    for i, n in enumerate(
        [
            "Piano",
            "Chromatic Percussion",
            "Organ",
            "Guitar",
            "Bass",
            "Strings",
            "Ensemble",
            "Brass",
            "Reed",
            "Pipe",
            "Synth Lead",
            "Synth Pad",
            "Synth SFX",
            "Ethnic",
        ]
    )
]

CLASSIC_PATCH_TOP_GROUPS: list[GroupConfig] = [
    GroupConfig(n, i * 8 + 112, i * 8 + 119)
    for i, n in enumerate(
        [
            "Percussive",
            "SFX",
        ]
    )
]


def serialize_controllers(instrument_el: ET.Element):
    for c in CONTROLLERS:
        add_controller(instrument_el, c)


def serialize_instruments(instrument_el: ET.Element, instrument: Instrument):
    patches = instrument.patches

    sysex = ET.SubElement(instrument_el, "SysEx", name="Native On")
    ET.SubElement(sysex, "data").text = "41 10 00 48 12 00 00 00 00 00 00"

    init = ET.SubElement(instrument_el, "Init")
    event = ET.SubElement(init, "event", tick="0", type="2", datalen="11")
    event.text = "41 10 00 48 12 00 00 00 00 00 00"

    for group in PATCH_TOP_GROUPS:
        patch_group = ET.SubElement(instrument_el, "PatchGroup", name=group.name)

        group_patches: list[tuple[str, int, Patch]] = []  # (name, pc, patch)
        for g_abbrv, gr in zip(["Cls", "Ctm", "Solo", "Enh"], instrument.groups[:4]):
            group_patches.extend(
                (f"{patch.name} {g_abbrv}", patch.pc, patch)
                for patch in (patches[pid] for pid in gr.patches)
                if group.pc_min <= patch.pc <= group.pc_max and not patch.drum
            )

        for name, pc, patch in sorted(group_patches, key=itemgetter(1)):
            ET.SubElement(
                patch_group,
                "Patch",
                name=name,
                hbank=str(patch.msb),
                lbank=str(patch.lsb),
                prog=str(pc),
            )

    for top_group in CLASSIC_PATCH_TOP_GROUPS:
        patch_group = ET.SubElement(instrument_el, "PatchGroup", name=top_group.name)

        for patch_id in instrument.groups[0].patches:
            patch = patches[patch_id]
            if patch.drum:
                continue
            if top_group.pc_min <= patch.pc <= top_group.pc_max:
                ET.SubElement(
                    patch_group,
                    "Patch",
                    name=patch.name,
                    hbank=str(patch.msb),
                    lbank=str(patch.lsb),
                    prog=str(patch.pc),
                )

    for group in instrument.groups[4:]:
        patch_group = ET.SubElement(instrument_el, "PatchGroup", name=group.name)
        for patch_id in group.patches:
            patch = patches[patch_id]
            if patch.drum:
                continue
            ET.SubElement(
                patch_group,
                "Patch",
                name=patch.name,
                hbank=str(patch.msb),
                lbank=str(patch.lsb),
                prog=str(patch.pc),
            )

    drum_group = ET.SubElement(instrument_el, "PatchGroup", name="Drums")
    for d in instrument.drum_sets:
        patch = patches[d.patch_id]
        assert patch.drum
        patch.name
        ET.SubElement(
            drum_group,
            "Patch",
            name=patch.name,
            hbank=str(patch.msb),
            lbank=str(patch.lsb),
            prog=str(patch.pc),
            drum="1",
        )


# Maps the minimum program change number for a drum patch to the maximum
DRUM_PC_RANGE: dict[int, int] = {
    0: 7,
    8: 15,
    16: 23,
    24: 24,
    25: 31,
    32: 39,
    40: 47,
    48: 55,
    56: 126,
}


def serialize_drum_sets(instrument_el: ET.Element, instrument: Instrument):
    patches = instrument.patches
    drum_sets = instrument.drum_sets

    drummaps_el = ET.SubElement(instrument_el, "Drummaps")

    for drum_set in drum_sets:
        patch = patches[drum_set.patch_id]
        assert patch.drum
        map_entry = ET.SubElement(drummaps_el, "entry")
        pc_min = patch.pc
        pc_max = DRUM_PC_RANGE[patch.pc]
        ET.SubElement(
            map_entry,
            "patch_collection",
            prog=f"{pc_min}-{pc_max}" if pc_min != pc_max else str(pc_min),
            lbank=str(patch.lsb),
            hbank=str(patch.msb),
        )
        drummap_el = ET.SubElement(map_entry, "drummap")
        for sound in drum_set.sounds:
            ET.SubElement(
                ET.SubElement(drummap_el, "entry", pitch=str(sound.key)), "name"
            ).text = sound.name

    return drummaps_el


def pretty_indent(tree, space="  ", level=0):
    """Like ElementTree.indent but hacked to compact the drum maps

    This works by skipping descending into the <entry pitch="..."> elements."""
    indentations = ["\n" + level * space]

    def _indent_children(elem, level):
        child_level = level + 1

        try:
            child_indentation = indentations[child_level]
        except IndexError:
            child_indentation = indentations[level] + space
            indentations.append(child_indentation)

        if not elem.text or not elem.text.strip():
            elem.text = child_indentation

        child = None
        for child in elem:
            if len(child) and not (child.tag == "entry" and child.attrib.get("pitch")):
                _indent_children(child, child_level)
            if not child.tail or not child.tail.strip():
                child.tail = child_indentation

        assert child is not None
        # Dedent after the last child by overwriting the previous indentation
        if not child.tail.strip():
            child.tail = indentations[level]

    _indent_children(tree, 0)


def main():
    argparser = argparse.ArgumentParser(
        description="Convert Edirol SD90 data to MuSE IDF"
    )
    argparser.add_argument("output_file", type=argparse.FileType("wb"))

    args = argparser.parse_args()

    data_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data")
    data_path = os.path.join(data_dir, "edirol-sd90.json")

    with open(data_path) as data_file:
        data = from_json(json.load(data_file))

    root = ET.Element("muse", version="2.1")
    instrument_el = ET.SubElement(root, "MidiInstrument", name="Edirol SD-90")

    serialize_instruments(instrument_el, data)
    serialize_controllers(instrument_el)
    serialize_drum_sets(instrument_el, data)

    pretty_indent(root)
    tree = ET.ElementTree(root)
    tree.write(args.output_file, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    main()
