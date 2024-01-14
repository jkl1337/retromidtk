#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
import argparse
import os
import re
from itertools import chain
from typing import IO

from retromidtk.types import DrumSet, DrumSound, Group, ParseError, Patch, to_json

# Expected header before Native Instruments List
RE_INST_HEADER_1 = re.compile(r"^SD-80/SD-90 Native Instruments List$")

# Expected table header for main Native instrument table
RE_INST_DATA_HEADER_1 = re.compile(
    r"""^PC \s+ LSB \s+
    MSB \s+ (.+?) (?:\s+ Map)? \s+
    MSB \s+ (.+?) (?:\s+ Map)? \s+
    MSB \s+ (.+?) (?:\s+ Map)? \s+
    MSB \s+ (.+?) (?:\s+ Map)? \s*$""",
    re.X,
)

# Expected table header for for Special banks
RE_INST_DATA_HEADER_2 = re.compile(
    r"^PC \s+ LSB \s+ MSB \s+ (.+?) \s+ PC \s+ LSB \s+ MSB \s+ (.+?) \s*$", re.X
)

# Expected native instrument table entry
RE_INST_DATA_1 = re.compile(
    r"""^(?P<pc>\d+)? \t
  (?P<lsb>\d+)
  \t (?P<msb0>\d+) \t (?P<name0>.+?) \s*
  \t (?P<msb1>\d+) \t (?P<name1>.+?) \s*
  \t (?P<msb2>\d+) \t (?P<name2>.+?) \s*
  \t (?P<msb3>\d+) \t (?P<name3>.+?) \s*
$""",
    re.X,
)

# Expected special instrument table entry
RE_INST_DATA_2 = re.compile(
    r"""^
  (?P<pc0>\d+) \t (?P<lsb0>\d+) \t (?P<msb0>\d+) \t (?P<name0>.+?) \s+ [# ]?
  \t (?P<pc1>\d+) \t (?P<lsb1>\d+) \t (?P<msb1>.+?) \t (?P<name1>.+?) \s+ [#]? \s*$""",
    re.X,
)

# Drum search expressions
RE_DRUM_HEADER_1 = re.compile(r"^SD-80/SD-90 Drum Set List$")

RE_DRUM_BANK_HEADER_1 = re.compile(
    r"^(?P<name>.+?) (?:\s+ Map)? \s* \(BANK[ ]MSB/LSB= (?P<msb>\d+)/(?P<lsb>\d+) \) \s*$",
    re.X,
)

RE_DRUM_SET_HEADER_1 = re.compile(
    r"""^PC \s+
    MSB \s+ (.+?) (?:\s+ Map)? \s+
    MSB \s+ (.+?) (?:\s+ Map)? \s+
    MSB \s+ (.+?) (?:\s+ Map)? \s+
    MSB \s+ (.+?) (?:\s+ Map)? \s*$""",
    re.X,
)

# Expected native instrument table entry
RE_DRUM_SET_DATA = re.compile(
    r"""^(?P<pc>\d+) \t
  (?P<msb0>\d+) \t (?P<name0>.+?) \s* \t
  (?P<msb1>\d+) \t (?P<name1>.+?) \s* \t
  (?P<msb2>\d+) \t (?P<name2>.+?) \s* \t
  (?P<msb3>\d+) \t (?P<name3>.+?) \s*
$""",
    re.X,
)

RE_DRUM_HEADER_2 = re.compile(r"^SD-80/SD-90 Drum Tones List$")

RE_DRUM_KEY_DATA = re.compile(
    r"""
  (?P<key>\d+)
  \t (?P<set0> .+?) \s*
  \t (?P<set1> .+?) \s*
  \t (?P<set2> .+?) \s*
  \t (?P<set3> .+?) \s*
  \t (?P<set4> .+?) \s*
  \t (?P<set5> .+?) \s*
  \t (?P<set6> .+?) \s*
  (?:\t (?P<set7> .+?) \s*)?
  (?:\t (?P<set8> .+?) \s*)?$""",
    re.X,
)


class Converter:
    def __init__(self):
        self.groups: list[Group] = [
            Group(0, "Classic"),
            Group(1, "Contemporary"),
            Group(2, "Solo"),
            Group(3, "Enhanced"),
            Group(4, "Special 1"),
            Group(5, "Special 2"),
        ]

        self.patches: list[Patch] = []
        self.drum_sets: list[DrumSet] = []

    def convert_drums(self, input_file: IO[str]):
        groups = self.groups
        patches = self.patches

        header_match = None
        for line in input_file:
            header_match = RE_DRUM_HEADER_1.match(line)
            if header_match:
                break

        if header_match is None:
            raise ParseError(input_file.name, 0, "SD-90 Drum Set Header not found")

        for line in input_file:
            header_match = RE_DRUM_SET_HEADER_1.match(line)
            if header_match:
                # Values are hardcoded because the original file typos them anyway
                break

        if header_match is None:
            raise ParseError(input_file.name, 0, "Drum Set table header not found")

        drum_sets: list[list[DrumSet]] = [[], [], [], []]

        header_match = None
        for line in input_file:
            match = RE_DRUM_SET_DATA.match(line)
            if match:
                pc = int(match.group("pc")) - 1
                name = ""

                for i in range(4):
                    parsed_name = match.group(f"name{i}")
                    if parsed_name != "->":
                        name = parsed_name

                    patch = Patch(
                        int(match.group(f"msb{i}")),
                        0,
                        pc,
                        name,
                        True,
                    )
                    patches.append(patch)
                    patch_id = len(patches) - 1
                    groups[i].patches.append(patch_id)

                    if parsed_name != "->":
                        drum_sets[i].append(DrumSet(patch_id))

                continue

            header_match = RE_DRUM_HEADER_2.match(line)
            if header_match:
                break

        if header_match is None:
            raise ParseError(input_file.name, 0, "Drum Tone table header not found")

        group_idx = 5
        for line in input_file:
            match = RE_DRUM_BANK_HEADER_1.match(line)
            if match:
                msb = int(match.group("msb"))
                group_idx = msb - 104

            match = RE_DRUM_KEY_DATA.match(line)
            if match:
                key = int(match.group("key"))

                for i in range(9):
                    name = match.group(i + 2)
                    if not name:
                        break
                    drum_sets[group_idx][i].sounds.append(DrumSound(key, name))

        self.drum_sets = list(chain.from_iterable(drum_sets))

    def convert_inst(self, input_file: IO[str]):
        groups = self.groups
        patches = self.patches
        pc = -1

        header_match = None
        for line in input_file:
            header_match = RE_INST_HEADER_1.match(line)
            if header_match:
                break

        if header_match is None:
            raise ParseError(
                input_file.name, 0, "SD-90 Native Instruments header not found"
            )

        for line in input_file:
            header_match = RE_INST_DATA_HEADER_1.match(line)
            if header_match:
                # Values are hardcoded because the original file typos them anyway
                break

        if header_match is None:
            raise ParseError(input_file.name, 0, "Instrument table header not found")

        header_match = None
        for line in input_file:
            match = RE_INST_DATA_1.match(line)
            if match:
                pc = int(match.group("pc")) - 1 if match.group("pc") else pc

                name = ""

                for i in range(4):
                    parsed_name = match.group(f"name{i}")
                    if parsed_name != "->":
                        name = parsed_name

                    patches.append(
                        Patch(
                            int(match.group(f"msb{i}")),
                            int(match.group("lsb")),
                            pc,
                            name,
                        )
                    )
                    groups[i].patches.append(len(patches) - 1)

                continue

            header_match = RE_INST_DATA_HEADER_2.match(line)
            if header_match:
                break

        if header_match is None:
            raise ParseError(
                input_file.name, 0, "Special instrument table header not found"
            )

        for line in input_file:
            match = RE_INST_DATA_2.match(line)
            if match:
                for i in range(2):
                    patches.append(
                        Patch(
                            int(match.group(f"msb{i}")),
                            int(match.group(f"lsb{i}")),
                            int(match.group(f"pc{i}")) - 1,
                            match.group(f"name{i}"),
                        )
                    )
                    groups[i + 4].patches.append(len(patches) - 1)

                continue

    def to_json(self, output_file: IO[str]):
        to_json(
            {
                "patches": self.patches,
                "groups": self.groups,
                "drum_sets": self.drum_sets,
            },
            output_file,
        )


def main():
    argparser = argparse.ArgumentParser(description="Convert SD90 patch file to JSON")
    argparser.add_argument("output_file", type=argparse.FileType("w"))
    args = argparser.parse_args()

    data_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data")
    sd90_dir = os.path.join(data_dir, "edirol-sd90")
    inst_path = os.path.join(sd90_dir, "SD_inst.txt")
    drum_path = os.path.join(sd90_dir, "SD_drum.txt")

    c = Converter()
    with open(inst_path) as f:
        c.convert_inst(f)
    with open(drum_path) as f:
        c.convert_drums(f)

    c.to_json(args.output_file)


if __name__ == "__main__":
    main()
