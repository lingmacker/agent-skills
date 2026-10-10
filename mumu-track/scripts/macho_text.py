"""Read thin ARM64 Mach-O text metadata; never execute or patch the input."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def text_info(data):
    if len(data) < 32 or data[:4] != bytes.fromhex('cffaedfe'):
        raise ValueError('Expected thin little-endian Mach-O 64; select the slice explicitly')
    if struct.unpack_from('<I', data, 4)[0] != 0x100000C:
        raise ValueError('Expected ARM64 CPU type; arm64e ABI still needs separate review')
    count, commands_size = struct.unpack_from('<II', data, 16)
    end, pos, found = 32 + commands_size, 32, []
    if end > len(data):
        raise ValueError('Truncated load commands')
    for _ in range(count):
        if pos + 8 > end:
            raise ValueError('Truncated command header')
        cmd, size = struct.unpack_from('<II', data, pos)
        if size < 8 or pos + size > end:
            raise ValueError('Invalid command size')
        if cmd == 0x19:
            if size < 72:
                raise ValueError('Truncated segment')
            nsects = struct.unpack_from('<I', data, pos + 64)[0]
            if 72 + nsects * 80 > size:
                raise ValueError('Truncated sections')
            for i in range(nsects):
                section = pos + 72 + i * 80
                if data[section:section + 16].rstrip(b'\0') == b'__text':
                    address, length, offset = struct.unpack_from('<QQI', data, section + 32)
                    if offset + length > len(data):
                        raise ValueError('Text outside file')
                    found.append({'address': address, 'offset': offset, 'size': length})
        pos += size
    if pos != end or len(found) != 1:
        raise ValueError('Expected complete load commands and exactly one text section')
    return found[0]


def text_section(data):
    info = text_info(data)
    return data[info['offset']:info['offset'] + info['size']]


def self_test():
    fixture = bytearray(188)
    struct.pack_into('<IIIIIIII', fixture, 0, 0xFEEDFACF, 0x100000C, 0, 1, 1, 152, 0, 0)
    struct.pack_into('<II', fixture, 32, 0x19, 152)
    struct.pack_into('<I', fixture, 96, 1)
    fixture[104:110] = b'__text'
    struct.pack_into('<QQI', fixture, 136, 0x1000, 4, 184)
    fixture[184:] = b'code'
    assert text_section(fixture) == b'code'
    assert text_info(fixture)['address'] == 0x1000
    for bad in (b'', fixture[:180], bytes(188)):
        try:
            text_info(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid Mach-O accepted')
    print('Thin Mach-O text extraction and rejection checks passed')


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Optimized Python disables self-checks; refusing execution')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', nargs='?')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.binary:
        data = Path(args.binary).read_bytes()
        print(json.dumps({'file_sha256': hashlib.sha256(data).hexdigest(),
                          'text': text_info(data),
                          'text_sha256': hashlib.sha256(text_section(data)).hexdigest()}, indent=2))
    else:
        parser.error('Provide a binary or --self-test')
