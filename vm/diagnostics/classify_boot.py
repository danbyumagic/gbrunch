#!/usr/bin/env python3
"""Conservatively classify explicit boot milestones in a captured log."""
import argparse
import json
import pathlib
import re


_TIMESTAMP = r'(?:\[[^\]\r\n]+\]\s*){0,2}'
_KERNEL_ENTRY = re.compile(r'^' + _TIMESTAMP + r'Linux version ')
_FIRST_STAGE = re.compile(r'^' + _TIMESTAMP + r'(?:init: )?init first stage started!?\s*$')
_SECOND_STAGE = re.compile(r'^' + _TIMESTAMP + r'(?:init: )?init second stage started!?\s*$')
_KERNEL_PANIC = re.compile(r'^' + _TIMESTAMP + r'Kernel panic(?:\s|:)')
_INIT_INVALID_OPCODE = re.compile(
    r'\binit(?:\[[^\]\r\n]+\])?[^\r\n]*\btrap invalid opcode\b', re.IGNORECASE)
_FATAL_SIGNAL = re.compile(r'\bFatal signal \d+\b')
_BOOT_COMPLETED = re.compile(r'^GBRUNCH_BOOT_COMPLETED=1\r?$')


def classify(text: str, properties: str = "") -> dict:
    """Return observed boot milestones; absence of evidence stays false.

    Process names, exit status and timeout state are not boot milestones.
    Graphical boot always requires separate visual evidence.
    """
    lines = text.splitlines()
    return {
        'kernel_entry_observed': any(_KERNEL_ENTRY.search(line) for line in lines),
        'first_stage_init_observed': any(_FIRST_STAGE.search(line) for line in lines),
        'second_stage_init_observed': any(_SECOND_STAGE.search(line) for line in lines),
        'kernel_panic_observed': any(_KERNEL_PANIC.search(line) for line in lines),
        'init_invalid_opcode_trap_observed': any(
            _INIT_INVALID_OPCODE.search(line) for line in lines),
        'userspace_fatal_signal_observed': any(_FATAL_SIGNAL.search(line) for line in lines),
        'boot_completed_observed': (any(_BOOT_COMPLETED.fullmatch(line) for line in lines)
                                    or '[sys.boot_completed]: [1]' in properties.splitlines()),
        'graphical_boot_verified': False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', type=pathlib.Path, required=True)
    parser.add_argument('--properties', type=pathlib.Path, help='Optional saved Android getprop output')
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    result = classify(args.log.read_text(errors='replace'),
                      args.properties.read_text(errors='replace') if args.properties else '')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
