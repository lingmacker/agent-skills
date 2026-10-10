"""Read-only direct B/BL callers in the primary text section of a thin ARM64 Mach-O."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from macho_text import text_info


def branch_target(word, address):
    if word & 0x7C000000 != 0x14000000:
        return None
    immediate = word & 0x03FFFFFF
    if immediate & 0x02000000:
        immediate -= 0x04000000
    return address + immediate * 4


def call_sites(data, target):
    if target < 0 or target % 4:
        raise ValueError('Target must be a nonnegative, 4-byte-aligned unslid address')
    info = text_info(data)
    if info['address'] % 4 or info['size'] % 4:
        raise ValueError('Primary text is not ARM64 instruction-aligned')
    matches = []
    for relative in range(0, info['size'], 4):
        offset = info['offset'] + relative
        address = info['address'] + relative
        word, = struct.unpack_from('<I', data, offset)
        if branch_target(word, address) == target:
            matches.append({'address': hex(address), 'file_offset': hex(offset),
                            'instruction': 'BL' if word & 0x80000000 else 'B'})
    return {'file_sha256': hashlib.sha256(data).hexdigest(), 'target': hex(target),
            'text': info, 'direct_calls': matches, 'match_count': len(matches),
            'limitations': ['Static instruction scan, not observed execution.',
                            'Primary __text only; indirect calls, data references and other code sections are not covered.']}


def self_test():
    assert branch_target(0x94000002, 0x1000) == 0x1008
    assert branch_target(0x17FFFFFF, 0x1000) == 0xFFC
    assert branch_target(0x96000000, 0x1000) == 0x1000 - (1 << 27)
    assert branch_target(0x95FFFFFF, 0x1000) == 0x1000 + (1 << 27) - 4
    assert branch_target(0xD65F03C0, 0x1000) is None
    fixture = bytearray(196)
    struct.pack_into('<8I', fixture, 0, 0xFEEDFACF, 0x100000C, 0, 2, 1, 152, 0, 0)
    struct.pack_into('<II', fixture, 32, 0x19, 152)
    struct.pack_into('<I', fixture, 96, 1)
    fixture[104:110] = b'__text'
    struct.pack_into('<QQI', fixture, 136, 0x1000, 12, 184)
    struct.pack_into('<3I', fixture, 184, 0x94000002, 0x14000001, 0xD65F03C0)
    result = call_sites(fixture, 0x1008)
    assert [item['instruction'] for item in result['direct_calls']] == ['BL', 'B']
    assert [item['file_offset'] for item in result['direct_calls']] == ['0xb8', '0xbc']
    assert call_sites(fixture, 0x2000)['match_count'] == 0
    for data, target in [(b'', 0x1000), (fixture, 1), (fixture, -4), (fixture[:-1], 0x1008)]:
        try:
            call_sites(data, target)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid scan input accepted')
    print('ARM64 direct caller, signed-range and invalid-input checks passed')


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Optimized Python disables self-checks; refusing execution')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', nargs='?')
    parser.add_argument('--target', type=lambda value: int(value, 0))
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.binary and args.target is not None:
        print(json.dumps(call_sites(Path(args.binary).read_bytes(), args.target), indent=2))
    else:
        parser.error('Provide a binary and --target, or --self-test')
