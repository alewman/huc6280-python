-- Rung 5 testbench: srg320's HUC6280_CPU (MiSTer TurboGrafx16 core) run on
-- SingleStepTests huc6280 initial states, its bus logged cycle by cycle.
--
-- The CPU's registers are internal, so each case is loaded by running code: after a reset
-- (every MPR is 0, so logical $E000 is physical $000000 and the vector is read from $001FFE),
-- a loader written by tests/huc6280_vhdl.py sets the eight MPRs, S, P (including T, by PLP),
-- X, Y and A and ends with "JMP pc-1", where a PLP overlays the byte before the case's
-- first instruction. The case starts at the opcode fetch that follows the PLP: the testbench
-- counts it from the JMP's own fetch (JMP abs is 4 cycles and PLP is 4 cycles, SW), so no
-- pin has to say "opcode fetch". From there reads and writes go to the case's own memory
-- and every cycle is written out:
--   C <id>                           case start
--   <address> <data> <we_n> <mcycle> one line per cycle
--   E <id>                           case end
--   X ...                            the loader never reached the case
-- The bus is combinational from the microcode step and DI is latched at the clock edge that
-- ends the cycle, so each cycle is read at the falling edge and answered before the rising one.
--
-- Stimulus, three lines per case, decimal:
--   <id> <loader pairs> <case pairs> <jmp physical address> <cycles to log>
--   <address value> ... (loader memory, physical addresses)
--   <address value> ... (the case's initial RAM, physical addresses)

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.textio.all;

entity tb_huc6280 is
    generic (stimulus : string := "stimulus.txt"; output : string := "bus.txt");
end entity;

architecture sim of tb_huc6280 is
    signal clk, rst_n : std_logic := '0';
    signal d_in, d_out : std_logic_vector(7 downto 0) := (others => '0');
    signal a_out : std_logic_vector(20 downto 0);
    signal we_n, mcycle, cs : std_logic;
    signal done : boolean := false;

    constant SLOTS : natural := 1024;
    type addrs_t is array (0 to SLOTS - 1) of integer;
    type bytes_t is array (0 to SLOTS - 1) of integer range 0 to 255;
begin
    dut : entity work.HUC6280_CPU
        port map (
            CLK => clk, RST_N => rst_n, CE => '1', A_OUT => a_out, DI => d_in, DO => d_out,
            WE_N => we_n, RDY => '1', NMI_N => '1', IRQ1_N => '1', IRQ2_N => '1',
            IRQT_N => '1', VDCNUM => '0', MCYCLE => mcycle, CS => cs);

    clock : process
    begin
        while not done loop
            clk <= '0'; wait for 5 ns;
            clk <= '1'; wait for 5 ns;
        end loop;
        wait;
    end process;

    drive : process
        file input : text open read_mode is stimulus;
        file log : text open write_mode is output;
        variable l, o : line;
        variable id, loader_pairs, case_pairs, jmp, cap, address, value, n, since_jmp, spent : integer;
        variable loader_addr, case_addr : addrs_t;
        variable loader_byte, case_byte : bytes_t;
        variable loader_used, case_used : natural;
        variable testing, saw_jmp : boolean;
        variable cycles : natural;

        impure function find(addrs : addrs_t; used : natural; a : integer) return integer is
        begin
            for i in 0 to used - 1 loop
                if addrs(i) = a then
                    return i;
                end if;
            end loop;
            return -1;
        end function;
    begin
        while not endfile(input) loop
            readline(input, l);
            read(l, id); read(l, loader_pairs); read(l, case_pairs); read(l, jmp); read(l, cap);
            loader_used := 0;
            readline(input, l);
            for i in 1 to loader_pairs loop
                read(l, address); read(l, value);
                loader_addr(loader_used) := address;
                loader_byte(loader_used) := value;
                loader_used := loader_used + 1;
            end loop;
            case_used := 0;
            readline(input, l);
            for i in 1 to case_pairs loop
                read(l, address); read(l, value);
                case_addr(case_used) := address;
                case_byte(case_used) := value;
                case_used := case_used + 1;
            end loop;

            rst_n <= '0';
            for i in 1 to 3 loop
                wait until falling_edge(clk);
            end loop;
            rst_n <= '1';
            testing := false;
            saw_jmp := false;
            since_jmp := 0;
            cycles := 0;
            spent := 0;
            write(o, string'("C ")); write(o, id); writeline(log, o);
            loop
                wait until falling_edge(clk);
                address := to_integer(unsigned(a_out));
                if not testing and not saw_jmp and we_n = '1' and address = jmp then
                    saw_jmp := true;
                    since_jmp := 0;
                end if;
                if saw_jmp and not testing then
                    if since_jmp = 8 then
                        testing := true;
                    end if;
                    since_jmp := since_jmp + 1;
                end if;
                if we_n = '0' then
                    value := to_integer(unsigned(d_out));
                    if testing then
                        n := find(case_addr, case_used, address);
                        if n >= 0 then
                            case_byte(n) := value;
                        elsif case_used < SLOTS then
                            case_addr(case_used) := address;
                            case_byte(case_used) := value;
                            case_used := case_used + 1;
                        end if;
                    else
                        n := find(loader_addr, loader_used, address);
                        if n >= 0 then
                            loader_byte(n) := value;
                        elsif loader_used < SLOTS then
                            loader_addr(loader_used) := address;
                            loader_byte(loader_used) := value;
                            loader_used := loader_used + 1;
                        end if;
                    end if;
                else
                    value := 0;
                    if testing then
                        n := find(case_addr, case_used, address);
                        if n >= 0 then
                            value := case_byte(n);
                        end if;
                    else
                        n := find(loader_addr, loader_used, address);
                        if n >= 0 then
                            value := loader_byte(n);
                        end if;
                    end if;
                    d_in <= std_logic_vector(to_unsigned(value, 8));
                end if;
                if testing then
                    write(o, address); write(o, ' '); write(o, value); write(o, ' ');
                    write(o, std_logic'image(we_n)(2)); write(o, ' ');
                    write(o, std_logic'image(mcycle)(2));
                    writeline(log, o);
                    cycles := cycles + 1;
                    exit when cycles >= cap;
                else
                    spent := spent + 1;
                    if spent > 400 then
                        write(o, string'("X loader did not reach the case")); writeline(log, o);
                        exit;
                    end if;
                end if;
            end loop;
            write(o, string'("E ")); write(o, id); writeline(log, o);
        end loop;
        done <= true;
        wait;
    end process;
end architecture;
