"""Read-only same-layout ARM64 Mach-O diff excluding embedded signature bytes and size metadata."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from macho_text import text_info


def neutral_body(data):
    text_info(data)
    count, size = struct.unpack_from('<II', data, 16)
    body = bytearray(data); pos = 32; signature = None
    for _ in range(count):
        kind, length = struct.unpack_from('<II', data, pos)
        if kind == 0x1D:
            if signature is not None or length != 16: raise ValueError('Ambiguous signature command')
            signature = struct.unpack_from('<II', data, pos + 8)
            body[pos + 8:pos + 16] = bytes(8)
        elif kind == 0x19 and data[pos + 8:pos + 24].rstrip(b'\0') == b'__LINKEDIT':
            body[pos + 32:pos + 40] = bytes(8)
            body[pos + 48:pos + 56] = bytes(8)
        pos += length
    if signature is None: raise ValueError('No embedded signature command')
    at, length = signature
    if at < 32 + size or at + length > len(data) or any(data[at + length:]):
        raise ValueError('Invalid signature bounds or nonzero trailing bytes')
    return bytes(body[:at])


def ranges(before, after):
    if len(before) != len(after): raise ValueError('Different body layouts: audit headers/relocations separately')
    found = []
    for i, (a, b) in enumerate(zip(before, after)):
        if a != b:
            if found and found[-1]['offset'] + found[-1]['length'] == i: found[-1]['length'] += 1
            else: found.append({'offset': i, 'length': 1})
    return found


def report(before, after):
    changed = ranges(neutral_body(before), neutral_body(after))
    return {'before_sha256': hashlib.sha256(before).hexdigest(), 'after_sha256': hashlib.sha256(after).hexdigest(),
            'signature_neutral_changed_bytes': sum(x['length'] for x in changed), 'ranges': changed,
            'scope': 'same-layout signature-neutral bytes only; not signature authenticity, entitlement/resource equivalence or runtime'}


def self_test():
    def fixture(signature):
        data = bytearray(208 + len(signature))
        struct.pack_into('<8I', data, 0, 0xFEEDFACF, 0x100000C, 0, 2, 2, 168, 0, 0)
        struct.pack_into('<II', data, 32, 0x19, 152); struct.pack_into('<I', data, 96, 1)
        data[104:110] = b'__text'; struct.pack_into('<QQI', data, 136, 0x1000, 8, 200)
        struct.pack_into('<4I', data, 184, 0x1D, 16, 208, len(signature)); data[200:208] = b'abcdefgh'
        data[208:] = signature
        return bytes(data)
    original = fixture(b'signature'); signed = fixture(b'another-signature')
    assert report(original, signed)['signature_neutral_changed_bytes'] == 0
    modified = bytearray(signed); modified[203] ^= 1
    assert report(original, modified)['ranges'] == [{'offset': 203, 'length': 1}]
    for bad in (b'', original[:201], original + b'nonzero'):
        try: neutral_body(bad)
        except ValueError: pass
        else: raise AssertionError('Invalid input accepted')
    try: ranges(b'a', b'bb')
    except ValueError: pass
    else: raise AssertionError('Changed layout accepted')
    print('PASS signature-only normalization, body change detection and invalid/layout rejection')


if __name__ == '__main__':
    if not __debug__: raise RuntimeError('Do not use python -O')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', nargs='?'); parser.add_argument('after', nargs='?'); parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test: self_test()
    elif args.before and args.after: print(json.dumps(report(Path(args.before).read_bytes(), Path(args.after).read_bytes()), indent=2))
    else: parser.error('Supply before and after files, or --self-test')
