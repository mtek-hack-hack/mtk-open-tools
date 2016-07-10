#!/usr/bin/env python3
#
# This utility dumps information about supported chips from combined
# download agent (DA) binary. Typical name of such bianry is
# MTK_AllInOne_DA.bin, so other exist too.
#
import sys
import struct


def decode(f, sz, fmt):
    s = f.read(sz)
    return struct.unpack("<" + fmt, s)


f = open(sys.argv[1], "rb")

sig = f.read(0x20)
assert sig.startswith(b"MTK_DOWNLOAD_AGENT")

da_id = f.read(0x40)
da_id = da_id.rstrip(b"\0")
print("# Mediatek Download Agent information dump")
print("id: %s" % str(da_id, "ascii"))
assert decode(f, 4, "I")[0] == 4
assert f.read(4) == b"\x99\x88\x66\x22"

num_socs = decode(f, 4, "I")[0]
print("num_chips:", num_socs)

PARTS = [
    5,
    9,
    14,
    19,
]

for i in range(num_socs):
    rec = f.read(0xdc)
    fields = struct.unpack("<2sHIIIIIIIQIIIIIIIIIIIII128s", rec)
    assert fields[0] == b'\xda\xda'
#    assert fields[-1] == b"\0" * 128, fields[-1]
    fields = fields[1:-1]
    flds = ["0x%08x" % x if isinstance(x, int) else x for x in fields]

    print("- chip_id: %#x" % fields[0])
    print("  chip_ver: %#x" % fields[1])
    print("  fw_ver: %#x" % fields[2])
    print("  extra_ver: %#x" % fields[3])
#    print("  all_fields:", flds)

#    assert fields[10] == fields[12] + fields[13], (fields[10], fields[12], fields[13])

    print("  # file_offset, size, load_addr")
    for i, no in enumerate(PARTS):
        print("  da_part%d: [%#x, 0x%05x, 0x%08x]  # %#x-%#x" % (i, fields[no], fields[no + 1], fields[no + 2], fields[no], fields[no] + fields[no + 1]))
