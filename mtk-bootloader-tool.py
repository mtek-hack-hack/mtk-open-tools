import sys
import os.path
import time
import struct
from binascii import hexlify
#from serial import Serial
from serial_ import Serial
#import serial

DEVICE = sys.argv[1]

CMD_GET_VERSION      = b"\xff" # this returns echo if security is off
CMD_GET_BL_VER       = b"\xfe"
CMD_GET_HW_SW_VER    = b"\xfc"
CMD_GET_HW_CODE      = b"\xfd"
CMD_SEND_DA          = b"\xd7"
CMD_JUMP_DA          = b"\xd5"
CMD_GET_TARGE_CONFIG = b"\xd8"
CMD_READ16           = b"\xa2"
CMD_WRITE16          = b"\xd2"
CMD_READ32           = b"\xd1"
CMD_WRITE32          = b"\xd4"
CMD_PWR_INIT         = b"\xc4"
CMD_PWR_DEINIT       = b"\xc5"
CMD_PWR_READ16       = b"\xc6"
CMD_PWR_WRITE16      = b"\xc7"


def hexs(s):
    return hexlify(s).decode("ascii")

while True:
    try:
#        s = Serial(DEVICE, 19200)
        s = Serial(DEVICE, 115200)
        sys.stdout.write("\n")
        break
    except OSError as e:
        sys.stdout.write("."); sys.stdout.flush()
        time.sleep(0.1)


def connect():
    while True:
        s.write(b"\xa0\x0a\x50\x05")
        resp = s.read(4)
        print(resp)
        if resp == b"\x5f\xf5\xaf\xfa":
            break
        if resp == b"READ":
            print(s.read(1))
    return

    s.write(b"\xa0\x0a\x50\x05\xa0\x0a\x50\x05\xa0\x0a\x50\x05")
    print(s.read(5))
    print(s.read(5))
    resp = s.read(4)
    print(resp)
    assert resp == b"\x5f\xf5\xaf\xfa"
    print("Connected")


def cmd_echo(cmd, resp_sz):
    print(">", hexs(cmd))
    s.write(cmd)
    echo = s.read(len(cmd))
    assert echo == cmd, echo
    resp = s.read(resp_sz)
    print("<", hexs(resp))
    return resp

def cmd_noecho(cmd, resp_sz, show=True):
    if show:
        print(">", hexs(cmd))
    else:
        print("> ...")
    s.write(cmd)
    resp = s.read(resp_sz)
    print("<", hexs(resp))
    return resp

def write32(addr, cnt, vals):
    resp = cmd_echo(CMD_WRITE32 + struct.pack(">II", addr, cnt), 2)
    assert resp == b"\0\0"
    for v in vals:
        cmd_echo(struct.pack(">I", v), 0)
    resp = cmd_echo(b"", 2)
    assert resp == b"\0\0"

def get_da_part1_params():
    # addr, size, size_of_xxx?
    params = (0x00200000, 0x00011518, 0x00000100)
    with open("MTK_AllInOne_DA.bin", "rb") as f:
        f.seek(0x3b5310)
        data = f.read(params[1])
    return (params, data)

def get_da_part2_params():
    # addr, size, block_size
    params = (0x80000000, 0x00033ea0, 0x00001000)
    with open("MTK_AllInOne_DA.bin", "rb") as f:
        f.seek(0x3c6828)
        data = f.read(params[1])
    return (params, data)


def boot_da2():
    connect()

    resp = cmd_echo(CMD_GET_HW_CODE, 4)
    soc_id, soc_step = struct.unpack(">HH", resp)
    print("SOC: %x, stepping?: %x" % (soc_id, soc_step))

    resp = cmd_echo(CMD_GET_HW_SW_VER, 8)

    write32(0x10007000, 1, [0x22000064])

    cmd_noecho(CMD_GET_BL_VER, 1)
    assert cmd_noecho(CMD_GET_VERSION, 1) == b"\xff"
    cmd_noecho(CMD_GET_BL_VER, 1)

    print("Downloading DA part 1")
    params, data = get_da_part1_params()
    resp = cmd_echo(CMD_SEND_DA + struct.pack(">III", *params), 2)
    assert resp == b"\0\0"
    while data:
        s.write(data[:1024])
        #print("Wrote %d bytes: %s" % (len(data[:1024]), data[:16]))
        data = data[1024:]

    resp = cmd_echo(b"", 2)
    resp = cmd_echo(b"", 2)
    assert resp == b"\0\0"

    print("Starting DA part 1...")
    resp = cmd_echo(CMD_JUMP_DA + struct.pack(">I", params[0]), 2)

    resp = cmd_echo(b"", 41)
    print("DA part 1 startup response:", resp)

    resp = cmd_noecho(b"Z", 3)
    assert resp == b"\x04\x02\x94"

    resp = cmd_noecho(\
    b"\xff"
    b"\x01"
    b"\x00\x08"
    b"\x00"
    b"\x70\x07\xff\xff"
    b"\x01"
    b"\x00\x00\x00\x00"
    b"\x02"
    b"\x00"
    b"\x02"
    b"\x00"
    b"\x00\x02\x00\x00", 4)

    assert resp == b"\0\0\0\0"

    print("Downloading DA part 2")

    params, data = get_da_part2_params()

    resp = cmd_noecho(struct.pack(">III", *params), 1)
    assert resp == b"Z"

    BLK_SZ = 4096

    while data:
        s.write(data[:BLK_SZ])
        assert s.read(1) == b"Z"
        #print("Wrote %d bytes" % len(data[:BLK_SZ]))
        data = data[BLK_SZ:]

    resp = cmd_noecho(b"", 1)
    assert resp == b"Z"

    resp = cmd_noecho(b"Z", 236)
    print(resp)
    # In this response: EMMC partition sizes, etc.
    assert resp[-1] == 0xc1

    resp = cmd_noecho(b"r", 2)
    assert resp == b"Z\x01"
    resp = cmd_noecho(b"r", 2)
    assert resp == b"Z\x01"

    resp = cmd_noecho(b"\x60", 1)
    assert resp == b"Z"
    resp = cmd_noecho(b"\x08", 1)
    assert resp == b"Z"


def read_flash(start, size, outf):
    sth = 2  # ??
    resp = cmd_noecho(b"\xd6\x0c" + struct.pack(">BQQ", sth, start, size), 1)
    assert resp == b"Z"

    # After so many transferred bytes, there will be 2-byte checksum
    chksum_blk_size = 0x10000
    cmd_noecho(struct.pack(">I", chksum_blk_size), 0)

    while size > 0:
        chunk = s.read(min(size, chksum_blk_size))
        #data += chunk
        size -= len(chunk)
        chksum = struct.unpack(">H", s.read(2))[0]
        chksum_my = 0
        for b in chunk:
            chksum_my += b
        assert chksum_my & 0xffff == chksum
        #print(hex(ck_my), hexs(chksum), chunk)
        outf.write(chunk)
        sys.stdout.write("."); sys.stdout.flush()
        s.write(b"Z")
    print()


boot_da2()

print("Reading flash...")

f = open("rom.bin", "wb")

start = 0
size = 4096 #1024 * 1024 * 1024
read_flash(start, size, f)

f.close()
