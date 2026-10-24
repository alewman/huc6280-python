"""Translate Klaus Dormann's 65C02 extended opcodes test (as65 syntax) to ca65, relocated.

    python -I scripts/dormann_to_ca65.py OUT_DIR       # writes test.s and test.cfg

Rung 2 (docs/validation.md). The source (reference/src/dormann/65C02_extended_opcodes_test.a65c,
GPL-3.0, research tier for this chip) cannot run unmodified on a HuC6280, and ``as65`` is a 32-bit
ELF this machine cannot run, so this script rewrites the syntax mechanically (macros, ``equ``,
``db``/``dw``/``ds``, ``lo()``/``hi()``, ``if``/``else``/``endif``, ``org``) and applies the
configuration the HuC6280 needs, each a named change:

- ``code_segment = $4000``: the code must not sit at logical ``$2000``-``$21FF``, which the HuC6280
  uses for zero page and stack (U1). Zero page and data stay at ``$0A`` and ``$0200``; the harness
  maps MPR0 and MPR1 to the same RAM, so ``$00xx`` and ``$20xx`` are one memory (tests/dormann.py).
- ``skip_nop = 1``: the 65C02's multi-byte ``NOP``s do not exist here (U3).
- the always-on status bit 5 (``reserv``) is 0: ``PHP`` pushes T, which is clear (U4, U5), and
  ``load_flag`` masks bit 5 out of the status it loads, since ``PLP`` would set T and change the next
  instruction (U4).
- the BRK vector ``$FFF6`` also points at the test's IRQ trap (U15).
- the opcodes whose flags differ from the 65C02's (``BIT #imm`` N and V, ``TSB``/``TRB`` N, V, Z:
  U19, C12) are patched where the test checks them (``PATCHES``), each counted in the report.

The output is not committed (it derives from a GPL source); the ld65 configuration lays the
segments out in one flat 64 KB image.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "reference" / "src" / "dormann" / "65C02_extended_opcodes_test.a65c"
)  # fmt: skip
CODE_SEGMENT = 0x4000

SETTINGS = {  # name: replacement value (the source's own line is rewritten)
    "code_segment": f"${CODE_SEGMENT:X}",
    "skip_nop": "1",
}
#: ``--original``: the source's own settings, to check this translation byte for byte against
#: Dormann's published binary (tests/test_dormann.py).
ORIGINAL = {}

CONFIG = """\
MEMORY { RAM: start = $0000, size = $10000, type = rw, file = %O, fill = yes, fillval = $FF; }
SEGMENTS {
    ZP:   load = RAM, type = rw, start = $000A;
    DATA: load = RAM, type = rw, start = $0200;
    CODE: load = RAM, type = rw, start = $4000;
    VEC0: load = RAM, type = rw, start = $FFF6;
    VEC:  load = RAM, type = rw, start = $FFFA;
}
"""


BIT_MNEMONIC = re.compile(r"\b(bbr|bbs|rmb|smb)\s+\\1,\s*", re.IGNORECASE)


def macros(lines: list[str]) -> list[str]:
    """Rewrite ``name macro`` ... ``endm``: positional ``\\1`` become named parameters and ``\\?``
    unique labels become ``.local`` ones. A macro that puts its parameter in a mnemonic
    (``bbr \\1,zp,label``, whose ca65 spelling is ``bbr3``) is expanded at its calls instead."""
    out: list[str] = []
    textual: dict[str, tuple[list[str], list[str]]] = {}
    i = 0
    while i < len(lines):
        match = re.match(r"^(\w+)\s+macro\b", lines[i], re.IGNORECASE)
        if not match:
            out.append(lines[i])
            i += 1
            continue
        j = i + 1
        while not re.match(r"^\s*endm\b", lines[j], re.IGNORECASE):
            j += 1
        body = lines[i + 1 : j]
        text = "\n".join(body)
        local = sorted(set(re.findall(r"(\w+)\\\?", text)))
        if BIT_MNEMONIC.search(text):
            textual[match[1].lower()] = (body, local)
            i = j + 1
            continue
        count = max((int(n) for n in re.findall(r"\\(\d)", text)), default=0)
        params = ",".join(f"p{n}" for n in range(1, count + 1))
        out.append(f".macro {match[1]} {params}".rstrip())
        if local:
            out.append("    .local " + ", ".join(local))
        for line in body:
            line = re.sub(r"\\(\d)", r"p\1", line)
            line = re.sub(r"(\w+)\\\?", r"\1", line)
            out.append(line)
        out.append(".endmacro")
        i = j + 1
    if not textual:
        return out
    expanded: list[str] = []
    for line in out:
        call = re.match(r"^\s+(\w+)\s+(\d)\s*(;.*)?$", line)
        if not call or call[1].lower() not in textual:
            expanded.append(line)
            continue
        body, local = textual[call[1].lower()]
        bit = call[2]
        for source in body:
            source = BIT_MNEMONIC.sub(lambda m, bit=bit: f"{m[1]}{bit} ", source)
            source = re.sub(r"\\1", bit, source)
            source = re.sub(r"(\w+)\\\?", rf"\1_{call[1]}{bit}", source)
            expanded.append(source)
    return expanded


patched: dict[str, int] = {}


def translate(text: str, settings: dict[str, str] | None = None) -> str:
    settings = SETTINGS if settings is None else settings
    hudson = settings is SETTINGS  # the HuC6280 patches; --original leaves them out
    lines = text.splitlines()
    lines = macros(lines)
    assigned: dict[str, int] = {}
    for line in lines:
        match = re.match(r"^(\w+)\s*=", line)
        if match:
            assigned[match[1]] = assigned.get(match[1], 0) + 1
    reset = {name for name, count in assigned.items() if count > 1}
    out = [".pc02", ".feature labels_without_colons, at_in_identifiers", '.segment "CODE"']
    segment_for = {
        "zero_page": "ZP",
        "data_segment": "DATA",
        "code_segment": "CODE",
        "$fffa": "VEC",
    }
    in_load_flag = in_flag_compare = in_tsb = False
    skip_lines = 0
    pending_bit: str | None = None
    patched["bit_immediate"] = patched["tsb_trb"] = 0
    for line in lines:
        raw = line
        code, _, comment = line.partition(";")
        if line.startswith((".macro cmp_flag", ".macro eor_flag")):
            in_flag_compare = True
        elif hudson and in_flag_compare and re.match(r"^\s+(cmp|eor) #", code):
            # An expected status may carry bit 5 ($FF, say); T is bit 5 here and reads as 0 (U4).
            code = re.sub(r"^(\s+(?:cmp|eor) )#(.*?)\s*$", r"\1#(\2)&$df", code)
            line = code + (";" + comment if comment else "")
        if line.startswith((".macro trbt", ".macro tsbt")):
            in_tsb = True
        elif hudson and in_tsb and re.match(r"^\s+cmp_flag p2\|fz", code):
            # U19, C12: TSB and TRB load N and V from the memory byte and Z from the stored result;
            # the 65C02 changes only Z, from A AND M. Compare only B, D, I and C here ...
            out.append("        and #$1d")
            out.append("        cmp #(p2|fao)&$1d")
            patched["tsb_trb"] += 1
            continue
        elif hudson and in_tsb and re.match(r"^\s+and #fz", code):
            # ... and do not check the Z flag (the three lines that compare it with A AND M).
            skip_lines = 3
        if skip_lines:
            skip_lines -= 1
            continue
        if line.startswith(".macro load_flag"):
            in_load_flag = True
        elif line.startswith(".endmacro"):
            in_load_flag = in_flag_compare = in_tsb = False
        elif hudson and in_load_flag and re.match(r"^\s+lda #p1\b", code):
            # U4: PLP would load bit 5 into T and change the next instruction; keep it clear.
            code = re.sub(r"lda #p1", "lda #(p1)&$df", code)
            line = code + (";" + comment if comment else "")
        stripped = code.strip()
        low = stripped.lower()
        if low == "success" and "everything went well" in comment:
            out.append("success_address:")  # the address rung 2 waits for
        suffix = f" ;{comment}" if comment else ""
        if not stripped:
            out.append(raw)
            continue
        if re.match(r"^reserv\s+equ\b", code, re.IGNORECASE) and settings is SETTINGS:
            out.append("reserv  = 0           ;U4, U5: bit 5 is T here, 0 after PHP and BRK")
            continue
        found = re.match(r"^(\w+)\s*=\s*", code)
        if found and found[1] in settings:
            out.append(f"{found[1]} = {settings[found[1]]}{suffix}")
            continue
        if low in ("data", "bss", "code", "noopt", "end start") or low.startswith("end "):
            continue
        org = re.match(r"^\s*org\s+(\S+)", code, re.IGNORECASE)
        if org:
            name = segment_for[org[1].lower()]
            out.append(f'.segment "{name}"' + (" : zeropage" if name == "ZP" else ""))
            continue
        if re.match(r"^\s*error\b", code, re.IGNORECASE):
            out.append('    .error "as65 ERROR directive reached"')
            continue
        bit_imm = re.match(r"^\s+bit\s+#(\S+)", code, re.IGNORECASE)
        if bit_imm and hudson:
            pending_bit = bit_imm[1]
        elif hudson and pending_bit is not None and re.match(r"^\s+tst_a\s", code):
            # U19: BIT #imm sets N and V from the immediate on the HuC6280 (the 65C02 leaves them);
            # the flags the test expects after it take those two bits from the operand.
            arguments = code.split(None, 1)[1].split(",", 1)
            code = (
                f"        tst_a {arguments[0]},(({arguments[1].strip()})&$3f|(({pending_bit})&$c0))"
            )
            patched["bit_immediate"] += 1
            pending_bit = None
        code = re.sub(r"^(\s*)if\b", r"\1.if", code, flags=re.IGNORECASE)
        code = re.sub(r"^(\s*)else\b", r"\1.else", code, flags=re.IGNORECASE)
        code = re.sub(r"^(\s*)endif\b", r"\1.endif", code, flags=re.IGNORECASE)
        again = re.match(r"^(\w+)\s*=\s*(.*)$", code)
        if again and again[1] in reset:
            code = f"{again[1]} .set {again[2]}"
        code = re.sub(r"\bequ\b", "=", code, flags=re.IGNORECASE)
        code = re.sub(r"^(\s*\w*\s+)db\b", r"\1.byte", code, flags=re.IGNORECASE)
        code = re.sub(r"^(\s*\w*\s+)dw\b", r"\1.word", code, flags=re.IGNORECASE)
        code = re.sub(r"^(\s*\w*\s+)ds\b", r"\1.res", code, flags=re.IGNORECASE)
        code = re.sub(r"\blo~(\w+)", r"<(~\1)", code)
        code = re.sub(r"\blo\s+([\w+\-*]+)", r"<(\1)", code)
        code = re.sub(r"\bhi\s+([\w+\-*]+)", r">(\1)", code)
        code = re.sub(r"\blo\(", "<(", code)
        code = re.sub(r"\bhi\(", ">(", code)
        code = code.replace("!=", "<>")
        code = re.sub(
            r"\b(set_a|tst_a) \$aa-p1,", r"\1 ($aa-p1)&$ff,", code
        )  # as65 wraps to 8 bits
        out.append(code + suffix)
    # U15: the HuC6280's BRK vector is $FFF6, not the 65C02's $FFFE.
    out += ['.segment "VEC0"', "        .word irq_trap", ".export start, success_address"]
    if not hudson:
        out = out[:-3] + [".export start, success_address"]
    return "\n".join(out) + "\n"


def main() -> int:
    original = "--original" in sys.argv
    target = Path(next(a for a in sys.argv[1:] if not a.startswith("--")))
    target.mkdir(parents=True, exist_ok=True)
    source = translate(SOURCE.read_text(encoding="latin-1"), ORIGINAL if original else None)
    (target / "test.s").write_text(source, encoding="utf-8")
    config = CONFIG.replace("start = $4000", "start = $0400") if original else CONFIG
    (target / "test.cfg").write_text(config, encoding="utf-8")
    print(f"wrote {target / 'test.s'} and {target / 'test.cfg'}; patched {patched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
