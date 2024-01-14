#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Convert a given Cubase instrument script file with MIDI definitions to a JSON data structure.

import argparse
from typing import TextIO
import re
from retromidtk.types import ParseError, Group, to_json


MODE_RE = re.compile(r"^\[ \s* mode \s* \] \s* (?P<mode>.*?) \s*$", re.X)
GROUP_RE = re.compile(
    r"""^\[ \s* g (?P<level>\d+) \s* \] \s*  (?P<name>.*?) \s*$""", re.X
)

PROGRAM_RE = re.compile(
    r"^\[ \s* p (?P<level>\d+) \s* , \s* (?P<pc>\d+) \s* , \s* (?P<msb>\d+) \s* , \s* (?P<lsb>\d+) \s* \] \s* (?P<name>.*?) \s*$",
    re.X,
)


def process_file(input_file: TextIO, output_file: TextIO):
    mode = None
    group_id = 0
    group_stack = [Group(0, "Root")]
    patch_id = 0
    patches = []

    for line_no, line in enumerate(input_file):
        line_no += 1
        match = GROUP_RE.fullmatch(line)
        if match:
            level = int(match.group("level"))

            if level >= len(group_stack):
                raise ParseError(
                    input_file.name, line_no, f"Invalid group level {level}"
                )

            name = match.group("name")

            group_id += 1
            group = Group(id=group_id, name=name)

            group_stack[level].groups.append(group)

            group_stack = group_stack[: level + 1]
            group_stack.append(group)

            continue

        match = PROGRAM_RE.match(line)
        if match:
            level = int(match.group("level"))

            if level >= len(group_stack):
                raise ParseError(
                    input_file.name, line_no, f"Invalid group level {level}"
                )
            pc = int(match.group("pc"))
            msb = int(match.group("msb"))
            lsb = int(match.group("lsb"))
            name = match.group("name")

            patches.append((msb, lsb, pc, name))
            group_stack[level].patches.append(patch_id)
            patch_id += 1

            continue

        match = MODE_RE.fullmatch(line)
        if match:
            mode = match.group("mode")

            group_id += 1
            group = Group(id=group_id, name=mode)
            group_stack = group_stack[:1]
            group_stack[0].groups.append(group)
            group_stack.append(group)

            continue

    to_json({"patches": patches, "groups": group_stack[0].groups}, output_file)


def main():
    argparser = argparse.ArgumentParser(
        description="Convert a Cubase instrument script file to a JSON data structure."
    )
    argparser.add_argument("input", help="Input file")
    argparser.add_argument("output", help="Output file")

    args = argparser.parse_args()

    with open(args.input, "r") as input_file:
        with open(args.output, "w") as output_file:
            process_file(input_file, output_file)


if __name__ == "__main__":
    main()
