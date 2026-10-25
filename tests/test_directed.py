"""Rung 3: directed tests, one per U-item whose tier is hardware-verified or manufacturer.

The expected values are written from the statement in each source, not from an
emulator: Hudson's HW and SW manuals (manufacturer) and MacDonald's pcetech
(hardware-verified by its author, no ROM published). The source is named in each test;
where the only evidence is emulators (U8, C3, C6, C7) the test says so and pins the
default the brief adopted. Cycle counts are SW's.
"""

import pytest
from directed import CODE, RAM, Host

from huc6280 import HuC6280

N, V, T, B, D, I, Z, C = 0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01
UNDEFINED = [0x0B, 0x1B, 0x2B, 0x33, 0x3B, 0x4B, 0x5B, 0x5C, 0x63, 0x6B, 0x7B, 0x8B, 0x9B,
             0xAB, 0xBB, 0xCB, 0xDB, 0xDC, 0xE2, 0xEB, 0xFB, 0xFC]  # fmt: skip


def host(program: bytes, **registers: int) -> Host:
    machine = Host()
    machine.load(program)
    for name, value in registers.items():
        setattr(machine.cpu, name, value)
    return machine


# -- U1: zero page at $2000, stack at $2100, through MPR1 (HW HB-3; pcetech 2.0) ----------


def test_u1_zero_page_is_logical_2000() -> None:
    machine = host(bytes([0xA5, 0x05]))  # LDA $05
    machine.memory[RAM + 5] = 0x42
    machine.step()
    assert machine.cpu.a == 0x42
    assert ("read", RAM + 5, 0x42) in machine.cycles


def test_u1_stack_is_logical_2100() -> None:
    machine = host(bytes([0x48]), a=0x99, s=0xFF)  # PHA
    machine.step()
    assert machine.memory[RAM + 0x1FF] == 0x99
    assert machine.cpu.s == 0xFE


def test_u1_zero_page_reads_rom_when_mpr1_maps_rom() -> None:
    # pcetech 2.0: "ROM data can be read by using instructions that access the zero page".
    machine = host(bytes([0xA5, 0x03, 0xEA, 0x77]))
    machine.cpu.mpr[1] = 0x01  # a ROM page: logical $2003 is physical $002003 (the code's 4th byte)
    machine.step()
    assert machine.cpu.a == 0x77


# -- U2: reset (HW HB-18; pcetech 2.0) -------------------------------------------------


def test_u2_reset_sequence() -> None:
    machine = Host()
    machine.memory[0x1FFE:0x2000] = bytes([0x00, 0xE0])  # vector read from physical $001FFE
    cpu = machine.cpu
    cpu.mpr[7] = 0x33
    cpu.p = D | T | N
    cpu.high_speed = True
    cpu.request_reset()
    cpu.step()
    assert cpu.mpr[7] == 0x00
    assert cpu.pc == 0xE000
    assert cpu.p & I and not cpu.p & (D | T)
    assert cpu.high_speed is False


# -- U3: the undefined opcodes are one-byte two-cycle NOPs (pcetech 2.0) ---------------------


@pytest.mark.parametrize("opcode", UNDEFINED, ids=lambda opcode: f"{opcode:02x}")
def test_u3_undefined_opcodes_are_two_cycle_nops(opcode: int) -> None:
    machine = host(bytes([0xF4, opcode]), a=1, x=2, y=3)  # SET, then the opcode
    machine.step()
    assert machine.cpu.p & T
    cycles = machine.step()
    cpu = machine.cpu
    assert (cycles, cpu.pc, cpu.a, cpu.x, cpu.y) == (2, CODE + 2, 1, 2, 3)
    assert not cpu.p & T  # the next instruction's fetch clears it, NOPs included


# -- U4: the T flag (HW HB-5; SW ADC; pcetech 2.3) -----------------------------------------


def test_u4_set_makes_the_next_alu_instruction_work_on_memory_at_x() -> None:
    machine = host(bytes([0xF4, 0x09, 0x0F]), a=0x11, x=0x10)  # SET; ORA #$0F
    machine.memory[RAM + 0x10] = 0x50
    machine.step()
    assert machine.step() == 5  # SW: +3 cycles
    assert machine.memory[RAM + 0x10] == 0x5F
    assert machine.cpu.a == 0x11  # A is untouched
    assert not machine.cpu.p & T


@pytest.mark.parametrize(
    ("program", "memory", "result"),
    [
        (bytes([0x29, 0x3C]), 0xF0, 0x30),  # AND #$3C
        (bytes([0x49, 0xFF]), 0x0F, 0xF0),  # EOR #$FF
        (bytes([0x69, 0x01]), 0x41, 0x42),  # ADC #$01 (C clear)
    ],
)
def test_u4_and_eor_adc_use_t_too(program: bytes, memory: int, result: int) -> None:
    machine = host(bytes([0xF4, *program]), a=0x77, x=0x20)
    machine.memory[RAM + 0x20] = memory
    machine.step(2)
    assert machine.memory[RAM + 0x20] == result and machine.cpu.a == 0x77


def test_u4_next_instruction_clears_t() -> None:
    machine = host(bytes([0xF4, 0xEA, 0x09, 0x0F]), a=0x10, x=0x10)  # SET; NOP; ORA #$0F
    machine.step(3)
    assert machine.cpu.a == 0x1F  # an ordinary ORA


def test_u4_php_and_pla_read_t_as_zero() -> None:
    machine = host(bytes([0xF4, 0x08]), s=0xFF)  # SET; PHP
    machine.step(2)
    assert not machine.ram(0x1FF) & T


def test_u4_plp_can_set_t_and_the_next_instruction_is_affected() -> None:
    machine = host(bytes([0x28, 0x09, 0x0F]), a=0x01, x=0x10, s=0xFE)  # PLP; ORA #$0F
    machine.memory[RAM + 0x1FF] = T | I
    machine.memory[RAM + 0x10] = 0x40
    machine.step()
    assert machine.cpu.p & T
    machine.step()
    assert machine.memory[RAM + 0x10] == 0x4F and machine.cpu.a == 0x01


def test_u4_interrupt_between_set_and_target_keeps_t_and_rti_restores_it() -> None:
    machine = host(bytes([0xF4, 0x09, 0x0F]), a=0x01, x=0x10, s=0xFF)  # SET; ORA #$0F
    machine.memory[RAM + 0x10] = 0x40
    machine.memory[0x1FF8:0x1FFA] = bytes([0x00, 0x60])  # IRQ1 vector -> $6000
    machine.load(bytes([0x40]), at=0x4000)  # RTI at physical $4000 = logical $6000 (MPR3 = $02)
    machine.cpu.p = I
    machine.step()  # SET
    machine.cpu.p &= ~I
    machine.cpu.set_irq_lines(True, False, False)
    machine.step()  # the interrupt is taken before ORA
    assert machine.ram(0x1FD) & T  # pushed P holds T as it stood (HW HB-5; pcetech 2.3)
    machine.cpu.set_irq_lines(False, False, False)
    machine.step()  # RTI
    assert machine.cpu.p & T
    machine.step()  # the ORA is still a memory operation
    assert machine.memory[RAM + 0x10] == 0x4F and machine.cpu.a == 0x01


def test_u4_adc_with_t_and_d_takes_six_cycles() -> None:
    machine = host(bytes([0xF8, 0xF4, 0x69, 0x01]), x=0x10)  # SED; SET; ADC #$01
    machine.memory[RAM + 0x10] = 0x19
    machine.step(2)
    assert machine.step() == 6  # SW: 2 + 3 (T) + 1 (D)
    assert machine.memory[RAM + 0x10] == 0x20


def test_c5_sbc_ignores_t() -> None:
    # SW's SBC entry has no T clause and pcetech lists ORA/AND/EOR/ADC only (C5).
    machine = host(bytes([0xF4, 0xE9, 0x01]), a=0x10, x=0x10, p=I | C)
    machine.memory[RAM + 0x10] = 0x77
    machine.step(2)
    assert machine.cpu.a == 0x0F and machine.memory[RAM + 0x10] == 0x77


# -- U5: B (HW HB-4; pcetech) ----------------------------------------------------------


def test_u5_php_and_brk_push_b_set_and_interrupts_push_it_clear() -> None:
    machine = host(bytes([0x08]), s=0xFF)
    machine.step()
    assert machine.ram(0x1FF) & B
    machine = host(bytes([0x00, 0x00]), s=0xFF)  # BRK
    machine.step()
    assert machine.ram(0x1FD) & B
    machine = host(bytes([0xEA]), s=0xFF, p=0)
    machine.cpu.set_irq_lines(True, False, False)
    machine.step()
    assert not machine.ram(0x1FD) & B


def test_u5_plp_does_not_keep_b() -> None:
    machine = host(bytes([0x28]), s=0xFE)
    machine.memory[RAM + 0x1FF] = 0xFF
    machine.step()
    assert not machine.cpu.p & B


# -- U6: a block transfer cannot be interrupted (pcetech 2.0) -------------------------------


def test_u6_block_transfer_runs_to_its_end_before_the_interrupt() -> None:
    # TII $4100,$0000+RAM,3 -- the line is raised on the second write.
    program = bytes([0x73, 0x00, 0x41, 0x00, 0x20, 0x03, 0x00, 0xEA])
    machine = host(program, s=0xFF, p=0)
    machine.memory[0x1FF8:0x1FFA] = bytes([0x00, 0x60])
    machine.memory[0x2100:0x2103] = bytes([1, 2, 3])
    writes = []
    original = machine.cpu.write_byte

    def write(address: int, value: int) -> None:
        original(address, value)
        writes.append(address)
        if len(writes) == 5:  # three pushes, then the second byte
            machine.cpu.set_irq_lines(True, False, False)

    machine.cpu.write_byte = write
    assert machine.step() == 17 + 3 * 6
    assert machine.memory[RAM : RAM + 3] == bytes([1, 2, 3])
    assert machine.cpu.pc == CODE + 7  # the interrupt has not been taken yet
    assert machine.step() == 8  # it is taken when the transfer ends
    assert machine.cpu.pc == 0x6000


# -- U7: block-transfer reads of $0800-$17FF return 0 (pcetech 2.0; end per issue 0001) --------------------------


def test_u7_block_reads_of_psg_timer_port_return_zero_and_skip_the_device() -> None:
    machine = Host(mpr=(0xFF, 0xF8, 0x01, 0x02, 0x03, 0x04, 0x05, 0x00))
    program = bytes([0x73, 0x00, 0x08, 0x00, 0x20, 0x04, 0x00])  # TII $0800 -> $2000, 4
    machine.load(program)
    machine.memory[0x1FE800:0x1FE804] = bytes([9, 9, 9, 9])
    machine.memory[RAM : RAM + 4] = bytes([5, 5, 5, 5])
    machine.step()
    assert machine.memory[RAM : RAM + 4] == bytes([0, 0, 0, 0])
    assert all(a != 0x1FE800 for kind, a, _ in machine.cycles if kind == "read")


def test_u7_block_reads_of_interrupt_registers_return_zero_and_skip_the_device() -> None:
    # pcetech 2.0: "you can't read the joystick port, timer, or IRQ registers" ($1402/$1403).
    for source, physical in ((0x1402, 0x1FF402), (0x1403, 0x1FF403), (0x17FF, 0x1FF7FF)):
        machine = Host(mpr=(0xFF, 0xF8, 0x01, 0x02, 0x03, 0x04, 0x05, 0x00))
        machine.load(bytes([0x73, source & 0xFF, source >> 8, 0x00, 0x20, 0x01, 0x00]))
        machine.memory[physical] = 9
        machine.memory[RAM] = 5
        machine.step()
        assert machine.memory[RAM] == 0
        assert all(a != physical for kind, a, _ in machine.cycles if kind == "read")


def test_u7_block_reads_past_the_hardware_page_block_are_ordinary() -> None:
    machine = Host(mpr=(0xFF, 0xF8, 0x01, 0x02, 0x03, 0x04, 0x05, 0x00))
    machine.load(bytes([0x73, 0x00, 0x18, 0x00, 0x20, 0x01, 0x00]))  # $1800: off-die
    machine.memory[0x1FF800] = 9
    machine.step()
    assert machine.memory[RAM] == 9


def test_u7_the_switch_off_reads_the_interrupt_registers() -> None:
    machine = Host(mpr=(0xFF, 0xF8, 0x01, 0x02, 0x03, 0x04, 0x05, 0x00))
    machine.cpu.block_reads_hardware_page_as_zero = False
    machine.load(bytes([0x73, 0x02, 0x14, 0x00, 0x20, 0x01, 0x00]))
    machine.memory[0x1FF402] = 9
    machine.step()
    assert machine.memory[RAM] == 9


def test_u7_vdc_reads_in_a_block_transfer_are_ordinary() -> None:
    machine = Host(mpr=(0xFF, 0xF8, 0x01, 0x02, 0x03, 0x04, 0x05, 0x00))
    machine.load(bytes([0x73, 0x00, 0x00, 0x00, 0x20, 0x02, 0x00]))  # source $0000: the VDC
    machine.memory[0x1FE000:0x1FE002] = bytes([7, 8])
    machine.step()
    assert machine.memory[RAM : RAM + 2] == bytes([7, 8])


def test_u7_block_writes_to_the_hardware_page_work() -> None:
    machine = Host(mpr=(0xFF, 0xF8, 0x01, 0x02, 0x03, 0x04, 0x05, 0x00))
    machine.load(bytes([0x73, 0x00, 0x20, 0x00, 0x08, 0x02, 0x00]))  # RAM -> $0800
    machine.memory[RAM : RAM + 2] = bytes([0x12, 0x34])
    machine.step()
    assert machine.memory[0x1FE800:0x1FE802] == bytes([0x12, 0x34])


# -- block transfers: push order, alternation, restored registers (HW HB-6; pcetech 2.0) -----


def transfer(opcode: int, source: bytes, count: int) -> Host:
    machine = host(bytes([opcode, 0x00, 0x20, 0x00, 0x21, count, 0x00]), a=0xAA, x=0xBB, y=0xCC)
    machine.memory[RAM : RAM + len(source)] = source
    return machine


def test_blocks_push_y_then_a_then_x_and_restore_them() -> None:
    machine = transfer(0x73, bytes([1, 2, 3, 4]), 4)
    order = []
    original = machine.cpu.write_byte
    machine.cpu.write_byte = lambda address, value: (order.append(value), original(address, value))[
        1
    ]
    cycles = machine.step()
    assert order[:3] == [0xCC, 0xAA, 0xBB]  # Y, A, X
    assert cycles == 17 + 6 * 4
    assert (machine.cpu.a, machine.cpu.x, machine.cpu.y, machine.cpu.s) == (0xAA, 0xBB, 0xCC, 0xFF)
    assert machine.memory[RAM + 0x100 : RAM + 0x104] == bytes([1, 2, 3, 4])


def test_tin_keeps_the_destination_fixed() -> None:
    machine = transfer(0xD3, bytes([1, 2, 3]), 3)
    machine.step()
    assert machine.memory[RAM + 0x100] == 3 and machine.memory[RAM + 0x101] == 0


def test_tdd_counts_down() -> None:
    machine = host(bytes([0xC3, 0x02, 0x20, 0x02, 0x21, 0x03, 0x00]))
    machine.memory[RAM : RAM + 3] = bytes([1, 2, 3])
    machine.step()
    assert machine.memory[RAM + 0x100 : RAM + 0x103] == bytes([1, 2, 3])


def test_tia_alternates_the_destination_and_tai_the_source() -> None:
    machine = transfer(0xE3, bytes([1, 2, 3, 4]), 4)  # TIA: dst +1, -1, +1, -1
    machine.step()
    # Source 0,1,2,3 to destinations 0x100, 0x101, 0x100, 0x101: the last two win.
    assert machine.memory[RAM + 0x100] == 3 and machine.memory[RAM + 0x101] == 4
    machine = transfer(0xF3, bytes([1, 2, 3, 4]), 4)  # TAI: src +1, -1, +1, -1
    machine.step()
    assert machine.memory[RAM + 0x100 : RAM + 0x104] == bytes([1, 2, 1, 2])


def test_a_length_of_zero_moves_65536_bytes() -> None:
    machine = host(bytes([0x73, 0x00, 0x20, 0x00, 0x20, 0x00, 0x00]))
    assert machine.step() == 17 + 6 * 65536


# -- U9: JMP (abs) at $xxFF, branches (pcetech 2.0) -------------------------------------


def test_u9_jmp_indirect_across_a_page_has_no_nmos_bug() -> None:
    machine = host(bytes([0x6C, 0xFF, 0x20]))  # JMP ($20FF): the pointer is in zero page memory
    machine.memory[RAM + 0xFF] = 0x34
    machine.memory[RAM + 0x100] = 0x12  # the next page, not $2000
    machine.memory[RAM + 0x00] = 0x99
    assert machine.step() == 7
    assert machine.cpu.pc == 0x1234


def test_u9_taken_branch_costs_two_more_whatever_the_page() -> None:
    machine = host(bytes([0xD0, 0x7F]))  # BNE across a page
    assert machine.step() == 4
    machine = host(bytes([0xD0, 0x00]), p=Z)
    assert machine.step() == 2  # not taken


# -- U10: CSL and CSH (pcetech 2.0, 2.4) -------------------------------------------------


def test_u10_clock_switch_takes_three_cycles_and_selects_the_speed() -> None:
    machine = host(bytes([0xD4, 0x54]))  # CSH; CSL
    assert machine.cpu.high_speed is False
    assert machine.step() == 3 and machine.cpu.high_speed is True
    assert machine.step() == 3 and machine.cpu.high_speed is False


def test_c7_the_new_speed_holds_for_the_last_cycle() -> None:
    # Emulator-derived default (Mesen, Mednafen), the brief's decision 5: undecidable here.
    machine = host(bytes([0xD4]))
    seen = []
    machine.cpu.idle = lambda address: seen.append(machine.cpu.high_speed)
    machine.step()
    assert seen == [False, True]  # the dummy read at the old speed, the last cycle at the new


# -- U11: TAM and TMA (HW HB-7; SW; pcetech 2.0) -----------------------------------------


def test_u11_tam_writes_every_selected_register() -> None:
    machine = host(bytes([0x53, 0x05]), a=0x42)  # TAM #$05
    assert machine.step() == 5
    assert machine.cpu.mpr[0] == 0x42 and machine.cpu.mpr[2] == 0x42


def test_u11_tam_with_no_bits_writes_nothing() -> None:
    machine = host(bytes([0x53, 0x00]), a=0x42)
    before = list(machine.cpu.mpr)
    machine.step()
    assert machine.cpu.mpr == before


def test_u11_tma_reads_one_register_and_takes_four_cycles() -> None:
    machine = host(bytes([0x43, 0x08]))  # TMA #$08
    machine.cpu.mpr[3] = 0x77
    assert machine.step() == 4
    assert machine.cpu.a == 0x77


def test_u11_tma_zero_returns_the_last_value_moved() -> None:
    machine = host(bytes([0x53, 0x40, 0xA9, 0x00, 0x43, 0x00]), a=0x5A)  # TAM #$40; LDA #0; TMA #0
    machine.step(3)
    assert machine.cpu.a == 0x5A


def test_c6_tma_with_several_bits_ors_the_registers() -> None:
    # Emulator-derived (Mesen); MAME takes the highest. pcetech has not worked it out.
    machine = host(bytes([0x43, 0x03]))
    machine.cpu.mpr[0], machine.cpu.mpr[1] = 0x81, 0x42
    machine.step()
    assert machine.cpu.a == 0xC3


# -- U12: ST0-ST2 write physical $1FE000/2/3 (HW HB-8; pcetech 2.0) -------------------------


@pytest.mark.parametrize(
    ("opcode", "address"), [(0x03, 0x1FE000), (0x13, 0x1FE002), (0x23, 0x1FE003)]
)
def test_u12_st_writes_the_vdc_whatever_the_mapper_holds(opcode: int, address: int) -> None:
    machine = host(bytes([opcode, 0x5A]))
    machine.cpu.mpr[7] = 0x00
    assert machine.step() == 4
    assert machine.memory[address] == 0x5A
    assert ("write", address, 0x5A) in machine.cycles


# -- U14: decimal mode (HW HB-4; SW ADC) -----------------------------------------------------


def test_u14_decimal_adc_takes_an_extra_cycle() -> None:
    machine = host(bytes([0xF8, 0x69, 0x28]), a=0x19)  # SED; ADC #$28
    machine.step()
    assert machine.step() == 3
    assert machine.cpu.a == 0x47


def test_u14_decimal_adc_leaves_v_alone_and_takes_c_from_the_decimal_result() -> None:
    machine = host(bytes([0xF8, 0x69, 0x01]), a=0x99, p=I | V)
    machine.step(2)
    assert machine.cpu.a == 0x00 and machine.cpu.p & C and machine.cpu.p & Z
    assert machine.cpu.p & V  # unchanged, not recomputed
    machine = host(bytes([0xF8, 0x69, 0x01]), a=0x99, p=I)
    machine.step(2)
    assert not machine.cpu.p & V


def test_u14_decimal_sbc() -> None:
    machine = host(bytes([0xF8, 0xE9, 0x19]), a=0x42, p=I | C)  # SED; SBC #$19
    machine.step()
    assert machine.step() == 3
    assert machine.cpu.a == 0x23 and machine.cpu.p & C


# -- U15: BRK (HW HB-4, HB-17; SW; pcetech) --------------------------------------------------


def test_u15_brk_pushes_the_address_after_the_signature_byte() -> None:
    machine = host(bytes([0x00, 0xEE]), s=0xFF, p=D)
    machine.memory[0x1FF6:0x1FF8] = bytes([0x00, 0x60])
    assert machine.step() == 8
    cpu = machine.cpu
    assert cpu.pc == 0x6000
    assert (machine.ram(0x1FF), machine.ram(0x1FE)) == (0x40, 0x02)  # BRK + 2
    assert machine.ram(0x1FD) & B and machine.ram(0x1FD) & D
    assert cpu.p & I and not cpu.p & D


# -- U17: the disable register masks taking, not requesting; vectors and priority ------------


@pytest.mark.parametrize(
    ("lines", "vector"),
    [
        ((False, True, False), 0xFFF6),  # IRQ2
        ((True, False, False), 0xFFF8),  # IRQ1
        ((False, False, True), 0xFFFA),  # TIQ
        ((True, True, True), 0xFFFA),  # priority TIQ > IRQ1 > IRQ2 (HW HB-13)
        ((True, True, False), 0xFFF8),
    ],
)
def test_u17_vectors_and_priority(lines: tuple[bool, bool, bool], vector: int) -> None:
    machine = host(bytes([0xEA]), p=0)
    physical = vector - 0xE000
    machine.memory[physical : physical + 2] = bytes([0x34, 0x12])
    machine.cpu.set_irq_lines(*lines)
    assert machine.step() == 8
    assert machine.cpu.pc == 0x1234


def test_u17_nmi_uses_fffc() -> None:
    machine = host(bytes([0xEA]), p=I)
    machine.memory[0x1FFC:0x1FFE] = bytes([0x78, 0x56])
    machine.cpu.request_non_maskable_interrupt()
    machine.step()
    assert machine.cpu.pc == 0x5678


def test_u17_disable_register_masks_taking_not_the_request() -> None:
    machine = host(bytes([0xEA, 0xEA]), p=0)
    machine.cpu.irq_disable = 0x02  # IRQ1 masked ($1402 layout, 1 = disabled)
    machine.cpu.set_irq_lines(True, False, False)
    assert machine.step() == 2  # not taken
    assert machine.cpu.irq_lines == (True, False, False)  # still requested (pcetech 2.1)
    machine.cpu.irq_disable = 0
    assert machine.step() == 8  # unmasked: taken at the next boundary


def test_u17_interrupt_entry_sets_i_and_clears_d_and_t() -> None:
    machine = host(bytes([0xEA]), p=D | T)
    machine.cpu.set_irq_lines(False, True, False)
    machine.step()
    assert machine.cpu.p & I and not machine.cpu.p & (D | T)


# -- U19: BIT, TST, TSB, TRB flags (pcetech 2.0; HW HB-5; SW) -------------------------------


def test_u19_bit_immediate_sets_n_and_v() -> None:
    machine = host(bytes([0x89, 0xC0]), a=0xFF)  # BIT #$C0
    machine.step()
    assert machine.cpu.p & N and machine.cpu.p & V and not machine.cpu.p & Z


def test_u19_tst_takes_n_and_v_from_memory() -> None:
    machine = host(bytes([0x83, 0x01, 0x10]))  # TST #$01,$10
    machine.memory[RAM + 0x10] = 0xC2
    assert machine.step() == 7
    assert machine.cpu.p & N and machine.cpu.p & V and machine.cpu.p & Z  # 0xC2 & 1 == 0


def test_u19_tsb_and_trb_take_n_and_v_from_memory() -> None:
    machine = host(bytes([0x04, 0x10]), a=0x01)  # TSB $10
    machine.memory[RAM + 0x10] = 0x80
    assert machine.step() == 6
    assert machine.cpu.p & N and not machine.cpu.p & V
    assert machine.memory[RAM + 0x10] == 0x81
    machine = host(bytes([0x14, 0x10]), a=0x01)  # TRB $10
    machine.memory[RAM + 0x10] = 0x41
    machine.step()
    assert machine.cpu.p & V and not machine.cpu.p & N and machine.memory[RAM + 0x10] == 0x40


# -- U20: calls and returns (SW) ------------------------------------------------------------


def test_u20_jsr_pushes_the_last_operand_byte_and_rts_adds_one() -> None:
    machine = host(bytes([0x20, 0x00, 0x60]), s=0xFF)
    machine.load(bytes([0x60]), at=0x4000)  # RTS at logical $6000
    assert machine.step() == 7
    assert (machine.ram(0x1FF), machine.ram(0x1FE)) == (0x40, 0x02)  # CODE + 2
    assert machine.step() == 7
    assert machine.cpu.pc == CODE + 3


def test_u20_bsr_takes_eight_cycles_and_pushes_its_last_byte() -> None:
    machine = host(bytes([0x44, 0x10]), s=0xFF)
    assert machine.step() == 8
    assert machine.cpu.pc == CODE + 2 + 0x10
    assert (machine.ram(0x1FF), machine.ram(0x1FE)) == (0x40, 0x01)


def test_u20_rti_pulls_p_first_then_pc() -> None:
    machine = host(bytes([0x40]), s=0xFC)
    machine.memory[RAM + 0x1FD : RAM + 0x200] = bytes([C | Z, 0x34, 0x12])
    assert machine.step() == 7
    assert machine.cpu.p == C | Z and machine.cpu.pc == 0x1234


# -- U21: CLI, SEI and PLP act one instruction late (HW HB-12; the frame's rule) ---------------


def test_u21_cli_takes_effect_after_the_next_instruction() -> None:
    machine = host(bytes([0x58, 0xEA, 0xEA]), p=I)  # CLI; NOP; NOP
    machine.cpu.set_irq_lines(True, False, False)
    machine.step()  # CLI
    assert machine.step() == 2  # the NOP still runs: the poll saw I set
    assert machine.step() == 8  # then the interrupt


def test_u21_sei_lets_one_pending_interrupt_through() -> None:
    machine = host(bytes([0x78, 0xEA]), p=0)  # SEI; NOP
    machine.cpu.set_irq_lines(True, False, False)
    machine.step()
    assert machine.step() == 8  # taken although I is now set: the poll saw it clear


# -- U22 and the Hudson swaps ------------------------------------------------------------------


def test_u22_65c02_additions() -> None:
    machine = host(bytes([0xDA, 0x5A, 0xFA, 0x7A, 0x1A, 0x3A]), x=1, y=2, a=5, s=0xFF)
    machine.step(2)  # PHX, PHY
    machine.cpu.x = machine.cpu.y = 0
    machine.step(2)  # PLX, PLY
    assert machine.cpu.y == 1 and machine.cpu.x == 2  # PHX then PHY: PLX gets Y's, PLY gets X's
    machine.step(2)  # INC A, DEC A
    assert machine.cpu.a == 5


def test_there_is_no_wai_or_stp() -> None:
    for opcode in (0xCB, 0xDB):
        machine = host(bytes([opcode]))
        assert machine.step() == 2 and machine.cpu.pc == CODE + 1


def test_swaps_and_clears() -> None:
    machine = host(bytes([0x02, 0x22, 0x42, 0x62, 0x82, 0xC2]), a=1, x=2, y=3)
    assert machine.step() == 3 and (machine.cpu.x, machine.cpu.y) == (3, 2)  # SXY
    machine.step()  # SAX
    assert (machine.cpu.a, machine.cpu.x) == (3, 1)
    machine.step()  # SAY
    assert (machine.cpu.a, machine.cpu.y) == (2, 3)
    assert machine.step() == 2 and machine.cpu.a == 0  # CLA
    machine.step(2)
    assert (machine.cpu.x, machine.cpu.y) == (0, 0)


# -- C3 and the emulator-derived defaults the brief adopted (named attributes) --------------------


def test_c3_interrupt_entry_is_eight_cycles_by_default() -> None:
    assert HuC6280.interrupt_entry_cycles == 8
    machine = host(bytes([0xEA]), p=0)
    machine.cpu.set_irq_lines(True, False, False)
    assert machine.step() == 8


def test_c3_seven_cycle_entry_is_a_switch() -> None:
    machine = host(bytes([0xEA]), p=0)
    machine.cpu.interrupt_entry_cycles = 7
    machine.cpu.set_irq_lines(True, False, False)
    assert machine.step() == 7


def test_u8_zero_page_pointer_wraps_by_default() -> None:
    # Emulator-derived (Mesen, MAME); no manual says. The knob is a class attribute.
    machine = host(bytes([0xB2, 0xFF]))  # LDA ($FF)
    machine.memory[RAM + 0xFF] = 0x10
    machine.memory[RAM + 0x00] = 0x21
    machine.memory[RAM + 0x100] = 0x22
    machine.memory[RAM + 0x2110 - 0x2000] = 0x5A
    machine.step()
    assert machine.cpu.a == 0x5A


def test_c4_opcode_63_is_a_two_cycle_nop_by_default() -> None:
    machine = host(bytes([0x63]))
    assert machine.step() == 2


# -- C18 (issue 0002): a source that goes away in the last cycle of the instruction that polled it ----


def _vanishing(source: str, mode: str | None = None) -> Host:
    """``CLI; STZ $1403; NOP`` with ``source`` asserted; the STZ's write lowers it (the timer
    handler of After Burner II). MPR0 = $FF so logical $1403 is the hardware page."""
    machine = Host(mpr=(0xFF, 0xF8, 0x01, 0x02, 0x03, 0x04, 0x05, 0x00))
    machine.load(bytes([0x58, 0x9C, 0x03, 0x14, 0xEA]))
    for vector, target in ((0xFFF6, 0x6000), (0xFFF8, 0x6100), (0xFFFA, 0x6200)):
        machine.memory[vector - 0xE000 : vector - 0xE000 + 2] = bytes([target & 0xFF, target >> 8])
    cpu = machine.cpu
    if mode:
        cpu.vanished_interrupt = mode
    cpu.p = I
    lines = {
        "tiq": (False, False, True),
        "irq1": (True, False, False),
        "irq2": (False, True, False),
    }
    cpu.set_irq_lines(*lines[source])
    original = machine.write_byte

    def write(address: int, value: int) -> None:
        original(address, value)
        if address == 0x1FF403:
            cpu.set_irq_lines(False, False, False)

    cpu.write_byte = write
    machine.step(2)  # CLI, then the STZ that acknowledges
    return machine


def test_c18_a_vanished_timer_interrupt_is_dropped_by_default() -> None:
    # Mesen2 (emulator-derived): "Order of the Griffon" expects the timer IRQ not to occur after
    # the STA. The old fall-through to the IRQ2 vector ($FFF6) is gone in every mode.
    machine = _vanishing("tiq")
    cycles = machine.step()
    assert machine.cpu.pc == CODE + 5 and cycles == 2  # the NOP ran; no entry
    assert not machine.cpu.p & I


@pytest.mark.parametrize(("source", "vector"), [("irq1", 0x6100), ("irq2", 0x6000)])
def test_c18_a_vanished_vdc_or_irq2_interrupt_is_still_taken_by_default(
    source: str, vector: int
) -> None:
    # Mesen2: "Games expect the VDC IRQ to occur after the LDA" (Jackie Chan, Final Soldier).
    machine = _vanishing(source)
    assert machine.step() == 8 and machine.cpu.pc == vector


def test_c18_latched_mode_takes_the_timer_through_its_own_vector() -> None:
    # srg320's HDL latches every source in the last cycle (read from HUC6280_CPU.vhd).
    machine = _vanishing("tiq", "latched")
    assert machine.step() == 8 and machine.cpu.pc == 0x6200


@pytest.mark.parametrize("source", ["tiq", "irq1", "irq2"])
def test_c18_drop_mode_drops_every_vanished_interrupt(source: str) -> None:
    machine = _vanishing(source, "drop")
    machine.step()
    assert machine.cpu.pc == CODE + 5


def test_c18_a_source_still_asserted_is_taken_in_every_mode() -> None:
    for mode in ("mesen2", "latched", "drop"):
        machine = Host()
        machine.cpu.vanished_interrupt = mode
        machine.load(bytes([0xEA]))
        machine.memory[0x1FFA:0x1FFC] = bytes([0x00, 0x62])
        machine.cpu.p = 0
        machine.cpu.set_irq_lines(False, False, True)
        assert machine.step() == 8 and machine.cpu.pc == 0x6200
