"""Read-only extent/path inventory for a workspace MBR/ext4 RAW. No patching, mounting or code execution."""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def u16(data, offset):
    return struct.unpack_from('<H', data, offset)[0]


def u32(data, offset):
    return struct.unpack_from('<I', data, offset)[0]


def extent_records(data, depth):
    if len(data) < 12 or u16(data, 0) != 0xf30a:
        raise ValueError('Missing extent header')
    count, maximum, observed = (u16(data, n) for n in (2, 4, 6))
    if observed != depth or depth > 5 or count > maximum or 12 + 12 * count > len(data):
        raise ValueError('Invalid extent tree')
    for i in range(count):
        at = 12 + 12 * i
        logical = u32(data, at)
        if depth:
            yield logical, u32(data, at + 4) | (u16(data, at + 8) << 32), None
        else:
            length = u16(data, at + 4)
            if not 0 < length <= 32768:
                raise ValueError('Unwritten or empty extent')
            yield logical, u32(data, at + 8) | (u16(data, at + 6) << 32), length


class Ext4:
    def __init__(self, path):
        self.stream = path.open('rb')
        self.disk_size = path.stat().st_size
        header = self.read_disk(0, 512)
        if header[510:] != b'\x55\xaa' or header[450] != 0x83:
            raise ValueError('Expected Linux first MBR partition')
        self.start, self.size = (u32(header, n) * 512 for n in (454, 458))
        if self.start < 512 or self.start + self.size > self.disk_size:
            raise ValueError('Invalid partition bounds')
        sb = self.read(1024, 1024)
        if sb[56:58] != b'\x53\xef':
            raise ValueError('Not ext4')
        self.block_size = 1024 << u32(sb, 24)
        if self.block_size != 4096:
            raise ValueError('Only 4096-byte blocks reviewed')
        self.incompat = u32(sb, 96)
        # Reject layouts this read-only reader cannot interpret.
        if self.incompat & ~0x2c6 or not self.incompat & 0x40 or u32(sb, 100) & (0x200 | 0x4000):
            raise ValueError('Unsupported ext4 features')
        self.inodes = u32(sb, 0)
        self.per_group = u32(sb, 40)
        self.inode_size = u16(sb, 88)
        self.desc_size = u16(sb, 254) if self.incompat & 0x80 else 32
        if not self.per_group or self.inode_size < 128 or self.desc_size not in (32, 64):
            raise ValueError('Invalid inode/group geometry')

    def read_disk(self, offset, size):
        if offset < 0 or size < 0 or offset + size > self.disk_size:
            raise ValueError('Read outside disk')
        self.stream.seek(offset)
        data = self.stream.read(size)
        if len(data) != size:
            raise ValueError('Short disk read')
        return data

    def read(self, offset, size):
        if offset < 0 or offset + size > self.size:
            raise ValueError('Read outside partition')
        return self.read_disk(self.start + offset, size)

    def inode(self, number):
        if not 1 <= number <= self.inodes:
            raise ValueError('Invalid inode number')
        group, index = divmod(number - 1, self.per_group)
        desc = self.read(self.block_size + group * self.desc_size, self.desc_size)
        table = u32(desc, 8)
        if self.desc_size == 64:
            table |= u32(desc, 40) << 32
        return self.read(table * self.block_size + index * self.inode_size, self.inode_size)

    def extents(self, inode):
        if not u32(inode, 32) & 0x80000 or u32(inode, 32) & (0x800 | 0x100000):
            raise ValueError('Non-extent, encrypted or verity inode unsupported')
        def visit(data, depth):
            for logical, physical, length in extent_records(data, depth):
                if depth:
                    yield from visit(self.read(physical * self.block_size, self.block_size), depth - 1)
                else:
                    yield logical, physical, length
        return sorted(visit(inode[40:100], u16(inode, 46)))

    def contents(self, inode):
        mode = u16(inode, 0) & 0xf000
        if mode not in (0x4000, 0x8000):
            raise ValueError('Only regular files and directories; no symlink traversal')
        size = u32(inode, 4) | (u32(inode, 108) << 32)
        if size > 64 * 1024 * 1024:
            raise ValueError('Bounded inspection rejects files over 64 MiB')
        data = bytearray(size)
        previous_end = 0
        for logical, physical, count in self.extents(inode):
            if logical < previous_end:
                raise ValueError('Overlapping logical extents')
            previous_end = logical + count
            at = logical * self.block_size
            length = min(count * self.block_size, size - at)
            if length <= 0:
                raise ValueError('Extent beyond inode size')
            data[at:at + length] = self.read(physical * self.block_size, length)
        return bytes(data)

    def directory(self, number):
        inode = self.inode(number)
        if u16(inode, 0) & 0xf000 != 0x4000:
            raise ValueError('Not a directory')
        data = self.contents(inode)
        items = {}
        for start in range(0, len(data), self.block_size):
            at, end = start, min(start + self.block_size, len(data))
            while at < end:
                if at + 8 > end:
                    raise ValueError('Truncated directory entry')
                ino, length, name_length = u32(data, at), u16(data, at + 4), data[at + 6]
                if length < 8 or length % 4 or at + length > end or name_length > length - 8:
                    raise ValueError('Invalid directory entry')
                if ino:
                    name = data[at + 8:at + 8 + name_length].decode('utf-8')
                    if name not in ('.', '..'):
                        items[name] = ino
                at += length
        return items

    def lookup(self, path):
        if not path.startswith('/'):
            raise ValueError('Require an absolute Guest path')
        number = 2
        for part in path.strip('/').split('/'):
            if part in ('', '.', '..'):
                raise ValueError('Require explicit absolute guest path without dot segments')
            number = self.directory(number)[part]
        return number


def self_test():
    data = bytearray(24)
    struct.pack_into('<HHHHI', data, 0, 0xf30a, 1, 1, 0, 0)
    struct.pack_into('<IHHI', data, 12, 0, 3, 1, 7)
    assert list(extent_records(data, 0)) == [(0, (1 << 32) + 7, 3)]
    for invalid, depth in ((bytes(24), 0), (data[:20], 0), (data, 1)):
        try:
            list(extent_records(invalid, depth))
        except ValueError:
            pass
        else:
            raise AssertionError('Bad extent accepted')
    fs = Ext4.__new__(Ext4)
    for flag in (0x80000 | 0x800, 0x80000 | 0x100000):
        inode = bytearray(128); struct.pack_into('<I', inode, 32, flag)
        try: fs.extents(inode)
        except ValueError: pass
        else: raise AssertionError('Encrypted/verity inode accepted')
    try: fs.lookup('relative/path')
    except ValueError: pass
    else: raise AssertionError('Relative Guest path accepted')
    inode = bytearray(128); struct.pack_into('<H', inode, 0, 0x8000); struct.pack_into('<I', inode, 4, 8192)
    fs.block_size = 4096; fs.extents = lambda _: [(0, 1, 1), (0, 2, 1)]; fs.read = lambda _, length: bytes(length)
    try: fs.contents(inode)
    except ValueError: pass
    else: raise AssertionError('Overlapping extents accepted')
    print('PASS extent bounds/depth/high bits, encrypted/verity rejection, absolute path and overlap checks')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--raw')
    parser.add_argument('--path')
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.raw:
        parser.error('Provide --raw, or --self-test')
    root = Path.cwd().resolve()
    raw = Path(args.raw).resolve()
    if not raw.is_relative_to(root):
        parser.error('RAW must be inside workspace')
    fs = Ext4(raw)
    try:
        number = fs.lookup(args.path) if args.path else 2
        inode = fs.inode(number)
        if u16(inode, 0) & 0xf000 == 0x4000:
            print(json.dumps(fs.directory(number), indent=2, sort_keys=True))
        else:
            data = fs.contents(inode)
            result = {'path': args.path, 'inode': number, 'size': len(data),
                      'mode': oct(u16(inode, 0)), 'sha256': hashlib.sha256(data).hexdigest(),
                      'extents': fs.extents(inode), 'incompat': hex(fs.incompat)}
            if args.output_dir:
                out = Path(args.output_dir).resolve()
                if not out.is_relative_to(root) or out.is_relative_to(Path(__file__).resolve().parents[1]) or out.exists():
                    parser.error('Output must be new workspace directory')
                out.mkdir(mode=0o700)
                (out / Path(args.path).name).write_bytes(data)
                (out / 'metadata.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result, indent=2))
    finally:
        fs.stream.close()


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Do not use python -O')
    main()
