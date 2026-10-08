#!/usr/bin/env python3
"""Drive the install-test VM through QEMU's QMP socket.

Usage:
  qmp.py shot <out.png>          screenshot
  qmp.py click <x> <y>           left click at screen pixel (needs usb-tablet)
  qmp.py type <text>             type ASCII text
  qmp.py key <combo>             e.g. ret, tab, ctrl-alt-t, meta_l
  qmp.py quit                    power off the VM
"""
import json
import socket
import struct
import sys
import zlib

SOCK = "/var/tmp/rocket-vm/qmp.sock"

SHIFTED = {'~': 'grave_accent', '!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6',
           '&': '7', '*': '8', '(': '9', ')': '0', '_': 'minus', '+': 'equal', '{': 'bracket_left',
           '}': 'bracket_right', '|': 'backslash', ':': 'semicolon', '"': 'apostrophe',
           '<': 'comma', '>': 'dot', '?': 'slash'}
PLAIN = {' ': 'spc', '-': 'minus', '=': 'equal', '[': 'bracket_left', ']': 'bracket_right',
         '\\': 'backslash', ';': 'semicolon', "'": 'apostrophe', ',': 'comma', '.': 'dot',
         '/': 'slash', '`': 'grave_accent', '\n': 'ret'}


class QMP:
    def __init__(self, path=SOCK):
        self.s = socket.socket(socket.AF_UNIX)
        self.s.connect(path)
        self.f = self.s.makefile("rw")
        self._read()  # greeting
        self.cmd("qmp_capabilities")

    def _read(self):
        while True:
            msg = json.loads(self.f.readline())
            if "event" not in msg:
                return msg

    def cmd(self, name, **args):
        self.f.write(json.dumps({"execute": name, "arguments": args}) + "\n")
        self.f.flush()
        r = self._read()
        if "error" in r:
            raise RuntimeError(r["error"])
        return r.get("return")


def keys_for(ch):
    if ch.isalpha():
        return (["shift", ch.lower()] if ch.isupper() else [ch])
    if ch.isdigit():
        return [ch]
    if ch in SHIFTED:
        return ["shift", SHIFTED[ch]]
    if ch in PLAIN:
        return [PLAIN[ch]]
    raise ValueError(f"cannot type {ch!r}")


def screen_size(q):
    # Take a tiny PNG and read width/height from the IHDR chunk.
    q.cmd("screendump", filename="/var/tmp/rocket-vm/.size.png", format="png")
    with open("/var/tmp/rocket-vm/.size.png", "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def main(argv):
    q = QMP()
    op = argv[1]
    if op == "shot":
        q.cmd("screendump", filename=argv[2], format="png")
    elif op == "click":
        w, h = screen_size(q)
        x, y = int(argv[2]), int(argv[3])
        ax, ay = x * 0x7FFF // (w - 1), y * 0x7FFF // (h - 1)
        q.cmd("input-send-event", events=[
            {"type": "abs", "data": {"axis": "x", "value": ax}},
            {"type": "abs", "data": {"axis": "y", "value": ay}}])
        for down in (True, False):
            q.cmd("input-send-event", events=[{"type": "btn", "data": {"down": down, "button": "left"}}])
    elif op == "type":
        for ch in " ".join(argv[2:]):
            q.cmd("send-key", keys=[{"type": "qcode", "data": k} for k in keys_for(ch)])
    elif op == "key":
        q.cmd("send-key", keys=[{"type": "qcode", "data": k} for k in argv[2].split("-")])
    elif op == "quit":
        q.cmd("quit")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
