"""Portable command debugger for the HuC6280.

6502-python's :class:`~sixfiveohtwo.console.CommandDebugger` with this core's registers,
the mapping registers, 16-bit logical addresses for breakpoints, disassembly and ``memory``,
21-bit physical ones for watchpoints, ``pbreak`` and ``physical``, and the three maskable
interrupt inputs. ``over`` runs ``JSR`` and ``BSR`` through. ``execute(line)`` runs one command
and returns printable lines; ``interact(input, output)`` is a line loop with no terminal
dependencies. ``python -m huc6280`` starts one on a HuCard.
"""

from __future__ import annotations

from typing import ClassVar

from sixfiveohtwo.console import CommandDebugger, CommandError, CommandResult, parse_number

from huc6280.disasm import ByteReader, Instruction, disassemble
from huc6280.state import CPUState

_HELP = (
    "help | ?                     Show this command summary",
    "registers | regs | r         Show CPU registers, the MPRs and lifecycle state",
    "step [COUNT] | s             Execute one or more boundaries (ignores breakpoints)",
    "over | o                     Step, running a JSR or BSR through to its return",
    "run STEPS [CYCLES]           Run with finite step and optional cycle limits",
    "continue | c                 Run up to 1,000,000 steps, off a breakpoint if on one",
    "break ADDRESS | b            Add an execute breakpoint (logical PC: $4000)",
    "pbreak ADDRESS               Add an execute breakpoint on a 21-bit physical address",
    "delete ADDRESS               Remove a logical breakpoint (pdelete: a physical one)",
    "breakpoints                  List breakpoints and watchpoints",
    "watch ADDRESS [r|w|rw]       Stop after a step that touches the physical byte",
    "unwatch ADDRESS              Remove a watchpoint",
    "disassemble [ADDRESS] [COUNT] | d  Decode logical addresses",
    "memory ADDRESS [LENGTH] | m  Display up to 256 bytes at a logical address",
    "physical ADDRESS [LENGTH]    Display up to 256 bytes at a physical address",
    "history [COUNT]              Show retained step records",
    "set REGISTER VALUE           Set A X Y S P PC or MPR0-MPR7",
    "irq1 on|off | irq2 on|off | tiq on|off   Assert or release a maskable input (a level)",
    "disable VALUE                Set the interrupt disable register (IRQ2=1 IRQ1=2 TIQ=4, 1 = masked)",
    "nmi | reset                  Latch an NMI edge, or run the reset sequence",
    "quit | exit | q              Leave the command loop",
    "Numbers are decimal; 0x1234 or $1234 is hexadecimal.",
)


def _flags(p: int) -> str:
    labels = "NVTBDIZC"
    return "".join(label if p & (0x80 >> index) else "-" for index, label in enumerate(labels))


class HuC6280Debugger(CommandDebugger):
    """A :class:`~sixfiveohtwo.console.CommandDebugger` over a ``HuC6280Session``."""

    prompt: ClassVar[str] = "huc6280> "
    registers: ClassVar[dict[str, int]] = {
        "A": 0xFF,
        "X": 0xFF,
        "Y": 0xFF,
        "S": 0xFF,
        "P": 0xFF,
        "PC": 0xFFFF,
        **{f"MPR{n}": 0xFF for n in range(8)},
    }
    help_lines: ClassVar[tuple[str, ...]] = _HELP
    call_mnemonics: ClassVar[frozenset[str]] = frozenset(("JSR", "BSR"))

    def __init__(self, session) -> None:
        super().__init__(session)
        # Breakpoints and disassembly are logical (16 bits); the base class's mask is the
        # record's physical 21 bits, which watchpoints use.
        self.logical_mask = 0xFFFF

    def format_state(self, state: CPUState) -> tuple[str, ...]:
        polled = "-" if state.polled_i is None else str(int(state.polled_i))
        skipped = " NO_POLL" if state.skipped_poll else ""
        registers = (
            f"PC={state.pc:04X} A={state.a:02X} X={state.x:02X} Y={state.y:02X} "
            f"S={state.s:02X} P={state.p:02X} {_flags(state.p)} "
            f"{'HIGH' if state.high_speed else 'LOW'}"
        )
        mapper = "MPR " + " ".join(f"{value:02X}" for value in state.mpr)
        lifecycle = (
            f"RESET={int(state.reset_pending)} NMI={int(state.non_maskable_interrupt_pending)} "
            f"IRQ1={int(state.irq1)} IRQ2={int(state.irq2)} TIQ={int(state.tiq)} "
            f"DISABLE={state.irq_disable:X} POLLED_I={polled}{skipped}"
        )
        return registers, mapper, lifecycle

    def format_address(self, address: int) -> str:
        return f"{address:04X}" if address <= 0xFFFF else f"{address:06X}"

    def disassemble_at(self, peek: ByteReader, address: int, state: CPUState) -> Instruction:
        return disassemble(peek, int(address))

    def set_register(self, name: str, value: int) -> None:
        """Set a register as the chip would hold it: B is not kept (U5)."""
        cpu = self.session.cpu
        if name.startswith("MPR"):
            cpu.mpr[int(name[3])] = value
        elif name == "P":
            cpu.p = value & ~0x10
        else:
            setattr(cpu, name.lower(), value)

    def execute(self, command: str) -> CommandResult:
        words = command.split()
        if not words:
            return super().execute(command)
        name, *arguments = words
        name = name.lower()
        cpu = self.session.cpu
        if name in ("irq1", "irq2", "tiq"):
            self._arity(name, arguments, 1)
            level = arguments[0].lower()
            if level not in ("on", "off"):
                raise CommandError(f"{name} takes on or off")
            lines = list(cpu.irq_lines)  # IRQ1, IRQ2, TIQ
            lines[["irq1", "irq2", "tiq"].index(name)] = level == "on"
            cpu.set_irq_lines(*lines)
            return CommandResult((f"{name.upper()} {'asserted' if level == 'on' else 'released'}",))
        if name == "disable":
            self._arity(name, arguments, 1)
            cpu.irq_disable = parse_number(arguments[0], "value", maximum=7)
            return CommandResult((f"interrupt disable register = {cpu.irq_disable:X}",))
        if name in ("pbreak", "pdelete"):
            self._arity(name, arguments, 1)
            address = parse_number(arguments[0], "address", maximum=self.address_mask)
            if name == "pbreak":
                self.session.add_physical_breakpoint(address)
                return CommandResult((f"physical breakpoint added at {address:06X}",))
            self.session.remove_physical_breakpoint(address)
            return CommandResult((f"physical breakpoint removed from {address:06X}",))
        if name in ("physical", "p"):
            return self._physical(arguments)
        if name in ("break", "b", "delete", "disassemble", "disasm", "d", "memory", "m"):
            for argument in arguments[:1]:
                parse_number(argument, "address", maximum=self.logical_mask)
        if name in ("memory", "m"):
            return self._memory_logical(arguments)
        result = super().execute(command)
        if name == "breakpoints":
            physical = tuple(
                f"physical {address:06X}" for address in sorted(self.session.breakpoints.physical)
            )
            lines = tuple(line for line in result.lines if line != "no breakpoints")
            return CommandResult(lines + physical or ("no breakpoints",))
        return result

    def _memory_logical(self, arguments: list[str]) -> CommandResult:
        self._arity("memory", arguments, 1, 2)
        peek = self._require_peek()
        address = parse_number(arguments[0], "address", maximum=self.logical_mask)
        length = parse_number(arguments[1], "length", maximum=256) if len(arguments) == 2 else 16
        lines = []
        for offset in range(0, length, 16):
            row = (address + offset) & 0xFFFF
            values = [peek((row + column) & 0xFFFF) for column in range(min(16, length - offset))]
            lines.append(f"{row:04X}  " + " ".join(f"{value:02X}" for value in values))
        return CommandResult(tuple(lines))

    def _physical(self, arguments: list[str]) -> CommandResult:
        self._arity("physical", arguments, 1, 2)
        address = parse_number(arguments[0], "address", maximum=self.address_mask)
        length = parse_number(arguments[1], "length", maximum=256) if len(arguments) == 2 else 16
        peek = self.session.peek_physical
        if peek is None:
            raise CommandError("this session has no physical peek")
        lines = []
        for offset in range(0, length, 16):
            row = (address + offset) & self.address_mask
            values = [
                peek((row + column) & self.address_mask)
                for column in range(min(16, length - offset))
            ]
            lines.append(f"{row:06X}  " + " ".join(f"{value:02X}" for value in values))
        return CommandResult(tuple(lines))


__all__ = ["CommandError", "CommandResult", "HuC6280Debugger", "parse_number"]
