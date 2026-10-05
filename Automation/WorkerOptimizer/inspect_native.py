"""Read-only disassembly of local game functions described by its matching jmap.

Development investigation only. Nothing from this helper is packaged in the mod.
Dependencies live in Intermediate/WorkerOptimizerTools, not the game install.
"""

import argparse
import bisect
import gzip
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Intermediate/WorkerOptimizerTools"))
import capstone
import pefile

parser = argparse.ArgumentParser()
parser.add_argument("function", nargs="?")
parser.add_argument("--class-name")
parser.add_argument("--slot", type=int)
parser.add_argument("--limit", type=int, default=4096)
parser.add_argument("--span", type=lambda v: int(v, 0), help="Explicit span for split exception-table function ranges")
parser.add_argument("--find-string", help="Locate a literal and validated RIP-relative LEA references")
args = parser.parse_args()

with gzip.open(ROOT / "Content/DynamicClasses/Whiskerwood-0.7.209.0.jmap.gz", "rt", encoding="utf-8") as stream:
    reflection = json.load(stream)
image_base = int(reflection["image_base_address"], 16)
install_lines = [line.strip() for line in (ROOT / "GameInstallDirectory.txt").read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith((";", "#"))]
assert len(install_lines) == 1, "Expected one configured game directory"
game_dir = Path(install_lines[0])
image = pefile.PE(str(game_dir / "Whiskerwood/Binaries/Win64/Whiskerwood-Win64-Shipping.exe"), fast_load=True)
pe_base = image.OPTIONAL_HEADER.ImageBase
exception_dir = image.OPTIONAL_HEADER.DATA_DIRECTORY[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXCEPTION"]]
# Read the standard three-DWORD RUNTIME_FUNCTION records without decoding every
# unwind program. Only function boundaries are needed for this inspection.
functions = sorted((begin, end) for begin, end, _ in struct.iter_unpack("<III", image.get_data(exception_dir.VirtualAddress, exception_dir.Size)))
starts = [f[0] for f in functions]
symbols = {int(v["func"], 16) - image_base: k for k, v in reflection["objects"].items() if v.get("func") and int(v["func"], 16) >= image_base}

def reflected(name):
    return reflection["objects"][name if name.startswith("/") else "/Script/ProjectArco." + name]


def describe(rva):
    if rva in symbols:
        return symbols[rva]
    if not 0 <= rva < image.OPTIONAL_HEADER.SizeOfImage:
        return ""
    raw = image.get_data(rva, 160)
    narrow = raw.split(b"\0", 1)[0]
    if 4 <= len(narrow) <= 78 and all(32 <= c < 127 for c in narrow):
        return repr(narrow.decode("ascii"))
    try:
        terminator = next((i for i in range(0, len(raw) - 1, 2) if raw[i:i + 2] == b"\0\0"), len(raw))
        text = raw[:terminator].decode("utf-16-le", errors="strict")
        if 4 <= len(text) <= 78 and all(32 <= ord(c) < 127 for c in text):
            return repr(text)
    except UnicodeDecodeError:
        pass
    return ""


if args.find_string:
    targets = set()
    for section in image.sections:
        data = section.get_data()
        for literal in (args.find_string.encode("utf-8") + b"\0", args.find_string.encode("utf-16-le") + b"\0\0"):
            offset = data.find(literal)
            while offset >= 0:
                targets.add(section.VirtualAddress + offset)
                offset = data.find(literal, offset + 1)
    print("literal RVAs:", [hex(t) for t in sorted(targets)])
    for section in image.sections:
        if not section.Characteristics & 0x20000000:
            continue
        data = section.get_data()
        decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        for prefix in (b"\x48\x8d", b"\x4c\x8d"):
            offset = data.find(prefix)
            while offset >= 0 and offset + 7 <= len(data):
                if data[offset + 2] & 0xc7 == 5:
                    rva = section.VirtualAddress + offset
                    target = rva + 7 + struct.unpack_from("<i", data, offset + 3)[0]
                    if target in targets:
                        instruction = next(decoder.disasm(data[offset:offset + 7], rva), None)
                        if instruction and instruction.mnemonic == "lea" and instruction.size == 7:
                            index = bisect.bisect_right(starts, rva) - 1
                            print(f"xref {rva:#x}, exception range {functions[index][0]:#x}..{functions[index][1]:#x}, {instruction.op_str}")
                offset = data.find(prefix, offset + 1)


if args.class_name:
    cls = reflected(args.class_name)
    vtable = cls["instance_vtable"]
    entries = reflection["vtables"][vtable]
    table_rva = int(vtable, 16) - image_base
    selected = range(len(entries)) if args.slot is None else [args.slot]
    for index in selected:
        rva = int(entries[index], 16) - image_base
        actual = struct.unpack("<Q", image.get_data(table_rva + 8 * index, 8))[0] - pe_base
        assert actual == rva, f"Game/jmap mismatch at {args.class_name} vtable slot {index}"
        print(f"slot {index} offset {index * 8:#x}: {rva:#x} {symbols.get(rva, '')}")
    if args.slot is not None:
        args.function = hex(int(entries[args.slot], 16) - image_base)

if args.function:
    rva = int(args.function, 16) if args.function.startswith("0x") else int(reflected(args.function)["func"], 16) - image_base
    index = bisect.bisect_right(starts, rva) - 1
    end = functions[index][1] if index >= 0 and rva < functions[index][1] else rva + args.limit
    if args.span is not None:
        end = rva + args.span
    print(f"function {args.function}, RVA {rva:#x}..{end:#x}, jmap base {image_base:#x}")
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    decoder.detail = True
    for ins in decoder.disasm(image.get_data(rva, min(end - rva, args.limit)), rva):
        annotations = []
        for operand in ins.operands:
            if operand.type == capstone.x86.X86_OP_IMM:
                label = describe(operand.imm)
                if label:
                    annotations.append(label)
            if operand.type == capstone.x86.X86_OP_MEM and operand.mem.base == capstone.x86.X86_REG_RIP:
                target = ins.address + ins.size + operand.mem.disp
                label = describe(target)
                annotations.append(f"RVA {target:#x}" + (" " + label if label else ""))
        print(f"{ins.address:08x} {ins.mnemonic:8} {ins.op_str:55}" + (" ; " + ", ".join(annotations) if annotations else ""))
    if end - rva > args.limit:
        print(f"TRUNCATED: {end - rva} bytes; increase --limit to inspect the remainder")
