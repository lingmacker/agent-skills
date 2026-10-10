"""Read-only Swift field-name inventory for the supplied ARM64 Mach-O."""
import argparse
import json
import struct
from pathlib import Path

from macho_text import text_info


def inspect(path):
    return inspect_data(Path(path).read_bytes())


def inspect_data(data):
    text_info(data)  # Validate the CPU, complete commands and primary text boundary.
    assert data[:4] == bytes.fromhex('cffaedfe'), 'Expected little-endian Mach-O 64'
    ncmds, sizeofcmds = struct.unpack_from('<II', data, 16)
    assert 32 + sizeofcmds <= len(data)
    segments, fields, contexts, protocols = [], None, {}, None
    pos = 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', data, pos)
        assert size >= 8 and pos + size <= 32 + sizeofcmds
        if cmd == 0x19:
            vm, vmsize, offset, fsize = struct.unpack_from('<QQQQ', data, pos + 24)
            segments.append((vm, offset, fsize))
            count = struct.unpack_from('<I', data, pos + 64)[0]
            assert 72 + count * 80 <= size
            for j in range(count):
                section = pos + 72 + j * 80
                name = data[section:section + 16].split(b'\0')[0]
                addr, length, start = struct.unpack_from('<QQI', data, section + 32)
                if name == b'__swift5_fieldmd':
                    fields = (addr, start, length)
                elif name == b'__swift5_proto':
                    protocols = (addr, start, length)
        pos += size
    assert pos == 32 + sizeofcmds
    assert fields is not None, 'No Swift field metadata'
    base, start, length = fields
    assert start + length <= len(data)

    def file_offset(address):
        for vm, offset, fsize in segments:
            if vm <= address < vm + fsize:
                return offset + address - vm
        raise ValueError(f'Unmapped relative pointer: {address:#x}')

    def string_at(off):
        end = data.find(b'\0', off, min(len(data), off + 4096))
        assert end >= off
        return data[off:end].decode('utf-8', errors='backslashreplace')

    def relative_string(position, symbolic=False):
        rel = struct.unpack_from('<i', data, position)[0]
        if rel == 0:
            return None
        target = base + position - start + rel
        off = file_offset(target)
        if symbolic and data[off] in (1, 2):
            descriptor = target + 1 + struct.unpack_from('<i', data, off + 1)[0]
            if data[off] == 2:
                descriptor = struct.unpack_from('<Q', data, file_offset(descriptor))[0]
                if descriptor == 0:
                    return 'indirect-context-unresolved'
            context = file_offset(descriptor)
            kind = struct.unpack_from('<I', data, context)[0] & 31
            if kind in (16, 17, 18):
                name = descriptor + 8 + struct.unpack_from('<i', data, context + 8)[0]
                typename = string_at(file_offset(name))
                contexts[typename] = descriptor
                return typename
        return string_at(off)

    result = []
    pos = start
    while pos + 16 <= start + length:
        kind, recordsize, count = struct.unpack_from('<HHI', data, pos + 8)
        assert recordsize >= 12 or count == 0
        end = pos + 16 + recordsize * count
        assert end <= start + length
        names = [relative_string(pos + 16 + i * recordsize + 8) for i in range(count)]
        typename = relative_string(pos, symbolic=True)
        if (typename and any(k in typename.lower() for k in ('trial', 'user', 'member', 'auth', 'accountresponse', 'deviceresponse'))
                or any(x and any(k in x.lower() for k in ('trial', 'member', 'vip')) for x in names)):
            result.append({'address': hex(base + pos - start), 'kind': kind,
                           'type': typename, 'context_address': hex(contexts[typename]) if typename in contexts else None,
                           'fields': names,
                           'field_types': [relative_string(pos + 16 + i * recordsize + 4, symbolic=True)
                                           for i in range(count)]})
        pos = end
    assert result, 'Expected trial/member field metadata was not recovered'
    if protocols:
        addr, offset, size = protocols
        for item in result:
            if item['type'] != 'AccountResponse':
                continue
            conformances = []
            for p in range(offset, offset + size, 4):
                descriptor = addr + p - offset + struct.unpack_from('<i', data, p)[0]
                d = file_offset(descriptor)
                flags = struct.unpack_from('<I', data, d + 12)[0]
                if (flags >> 3) & 7:
                    continue  # Only direct Swift type references are resolved here.
                context = descriptor + 4 + struct.unpack_from('<i', data, d + 4)[0]
                if context != int(item['context_address'], 16):
                    continue
                protocol = struct.unpack_from('<i', data, d)[0]
                entry = {'descriptor': hex(descriptor),
                         'protocol_pointer': hex(descriptor + (protocol & ~1)),
                         'protocol_indirect': bool(protocol & 1), 'implementations': []}
                if flags & (1 << 16) and not (flags >> 8) & 255:
                    count = struct.unpack_from('<I', data, d + 16)[0]
                    assert count < 32
                    for i in range(count):
                        position = d + 24 + i * 8
                        implementation = descriptor + position - d + struct.unpack_from('<i', data, position)[0]
                        entry['implementations'].append(hex(implementation))
                conformances.append(entry)
            item['conformances'] = conformances
    return result


def self_test():
    strings = b'User\0token\0SSSg\0'
    fixture = bytearray(376 + len(strings))
    struct.pack_into('<8I', fixture, 0, 0xFEEDFACF, 0x100000C, 0, 2, 1, 312, 0, 0)
    struct.pack_into('<II16s4QiiII', fixture, 32, 0x19, 312, b'__TEXT',
                     0x100000000, len(fixture), 0, len(fixture), 5, 5, 3, 0)
    for i, (name, offset, length) in enumerate([(b'__text', 344, 4),
                                               (b'__swift5_fieldmd', 348, 28),
                                               (b'__cstring', 376, len(strings))]):
        struct.pack_into('<16s16sQQ8I', fixture, 104 + i * 80, name, b'__TEXT',
                         0x100000000 + offset, length, offset, 2, 0, 0, 0, 0, 0, 0)
    fixture[344:348] = bytes.fromhex('c0035fd6')
    struct.pack_into('<iiHHI', fixture, 348, 28, 0, 0, 12, 1)
    struct.pack_into('<Iii', fixture, 364, 0, 19, 9)
    fixture[376:] = strings
    record, = inspect_data(fixture)
    assert record['type'] == 'User' and record['fields'] == ['token']
    assert record['field_types'] == ['SSSg'] and record['context_address'] is None
    for invalid in (b'', bytes(len(fixture)), fixture[:-1]):
        try:
            inspect_data(invalid)
        except (ValueError, AssertionError, struct.error):
            pass
        else:
            raise AssertionError('Malformed metadata accepted')
    print('Swift field inventory and malformed-input checks passed')


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Optimized Python disables metadata checks; refusing execution')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', nargs='?')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.binary:
        print(json.dumps(inspect(args.binary), ensure_ascii=False, indent=2))
    else:
        parser.error('Provide a binary or --self-test')
