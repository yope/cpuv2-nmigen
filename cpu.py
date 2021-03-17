#!/usr/bin/env python3

from typing import List, Tuple

from nmigen import *
from nmigen.hdl.rec import *
from nmigen.build import *
from nmigen.asserts import Assert, Assume, Cover
from nmigen.cli import main_parser, main_runner
from nmigen.back.pysim import Simulator, Delay, Settle
import sys

from enum import Enum, unique

@unique
class Op(Enum):
	ADD = 0
	SUB = 1
	ADC = 2
	SBC = 3
	NOT = 4
	AND = 5
	OR = 6
	XOR = 7
	SHL = 8
	SHR = 9
	ASL = 10
	ASR = 11
	SL4 = 12
	SL16 = 13
	SR4 = 14
	SR16 = 15

class ALU(Elaboratable):
	def __init__(self, width):
		self.width = width
		self.arg_a = Signal(width)
		self.arg_b = Signal(width)
		self.op = Signal(Op)
		self.c_in = Signal()
		self.result = Signal(width)
		self.z = Signal()
		self.c = Signal()
		self.n = Signal()
		self.tmp = Signal(width + 1)

	def ports(self) -> List[Signal]:
		return [self.arg_a, self.arg_b, self.op, self.c_in, self.result, self.z, self.c, self.n]

	def elaborate(self, platform: Platform) -> Module:
		m = Module()
		w = self.width
		c = m.d.comb
		c += [
			self.result.eq(self.tmp[:w]),
			self.z.eq(self.result == 0),
			self.c.eq(self.tmp[-1]),
			self.n.eq(self.result[-1])
			]
		with m.Switch(self.op):
			with m.Case(Op.ADD):
				c += self.tmp.eq(self.arg_a + self.arg_b)
			with m.Case(Op.SUB):
				c += self.tmp.eq(self.arg_a - self.arg_b)
			with m.Case(Op.ADC):
				c += self.tmp.eq(self.arg_a + self.arg_b + self.c_in)
			with m.Case(Op.SBC):
				c += self.tmp.eq(self.arg_a - self.arg_b - self.c_in)
			with m.Case(Op.NOT):
				c += self.tmp.eq(~self.arg_a)
			with m.Case(Op.AND):
				c += self.tmp.eq(self.arg_a & self.arg_b)
			with m.Case(Op.OR):
				c += self.tmp.eq(self.arg_a | self.arg_b)
			with m.Case(Op.XOR):
				c += self.tmp.eq(self.arg_a ^ self.arg_b)
			with m.Case(Op.SHL):
				c += self.tmp.eq(self.arg_a << 1)
			with m.Case(Op.SHR):
				c += self.tmp.eq(self.arg_a >> 1)
			with m.Case(Op.ASL):
				c += self.tmp.eq(Cat(self.c_in, (self.arg_a << 1)[1:w+1]))
			with m.Case(Op.ASR):
				c += self.tmp.eq(Cat((self.arg_a >> 1)[:w-1], self.c_in, self.arg_a[0]))
			with m.Case(Op.SL4):
				c += self.tmp.eq(self.arg_a << 4)
			with m.Case(Op.SL16):
				c += self.tmp.eq(self.arg_a << 16)
			with m.Case(Op.SR4):
				c += self.tmp.eq(Cat((self.arg_a >> 4)[:w], self.arg_a[3]))
			with m.Case(Op.SR16):
				c += self.tmp.eq(Cat((self.arg_a >> 16)[:w], self.arg_a[15]))
			with m.Default():
				c += self.tmp.eq(0)
		return m

	@classmethod
	def formal(cls) -> Tuple[Module, List[Signal]]:
		m = Module()
		m.submodules.alu = alu = cls(32)
		tmp = Signal(33)
		stmp = Signal(signed(32))
		c = m.d.comb
		c += stmp.eq(tmp[:32])
		# For some reason we need to do this to tell yosys that the result of this requires 33 bits.
		with m.If(alu.op == Op.ADD):
			c += tmp.eq(alu.arg_a + alu.arg_b)
		with m.Elif(alu.op == Op.SUB):
			c += tmp.eq(alu.arg_a - alu.arg_b)
		with m.Elif(alu.op == Op.ADC):
			c += tmp.eq(alu.arg_a + alu.arg_b + alu.c_in)
		with m.Elif(alu.op == Op.SBC):
			c += tmp.eq(alu.arg_a - alu.arg_b - alu.c_in)
		with m.Elif(alu.op == Op.NOT):
			c += tmp.eq(~alu.arg_a)
		with m.Elif(alu.op == Op.AND):
			c += tmp.eq(alu.arg_a & alu.arg_b)
		with m.Elif(alu.op == Op.OR):
			c += tmp.eq(alu.arg_a | alu.arg_b)
		with m.Elif(alu.op == Op.XOR):
			c += tmp.eq(alu.arg_a ^ alu.arg_b)
		with m.Elif(alu.op == Op.SHL):
			c += tmp.eq(alu.arg_a << 1)
		with m.Elif(alu.op == Op.SHR):
			c += tmp.eq(alu.arg_a >> 1)
		with m.Elif(alu.op == Op.ASL):
			c += tmp.eq((alu.arg_a << 1) | alu.c_in)
		with m.Elif(alu.op == Op.ASR):
			c += tmp.eq((alu.arg_a >> 1) | (alu.c_in << 31) | (alu.arg_a[0] << 32))
		with m.Elif(alu.op == Op.SL4):
			c += tmp.eq(alu.arg_a << 4)
		with m.Elif(alu.op == Op.SL16):
			c += tmp.eq(alu.arg_a << 16)
		with m.Elif(alu.op == Op.SR4):
			c += tmp.eq((alu.arg_a >> 4) | (alu.arg_a[3] << 32))
		with m.Elif(alu.op == Op.SR16):
			c += tmp.eq((alu.arg_a >> 16) | (alu.arg_a[15] << 32))

		c += Assert(Cat(alu.result, alu.c) == tmp)
		c += Assert(alu.n == (stmp < 0))
		c += Assert(alu.z == (alu.result == 0))
		return m, alu.ports() + [tmp]

class WbMasterLayout(Layout):
	def __init__(self, dw, aw):
		super().__init__([
			("rst_i", 1),
			("dat_i", unsigned(dw)),
			("ack_i", 1),
			("we_o", 1),
			("stb_o", 1),
			("adr_o", unsigned(aw)),
			("dat_o", unsigned(dw)),
			("sel_o", unsigned(dw // 8))
		])

class WbMaster(Record):
	def __init__(self, dw, aw):
		super().__init__(WbMasterLayout(dw, aw))

State = Enum("State", "RESET FETCH DECODE EXECUTE LOAD STORE IRQ RTI", start=0)

Opcode = Enum("Opcode", "alu alui ldi ldis ldb ldh ldw ldiu stb sth stw nop b bdec jsr ext", start=0)

class Cpu(Elaboratable):
	def __init__(self, width=32, nregs=16):
		self.width = w = width
		self.nregs = nr = nregs
		self.bus = WbMaster(w, w) # FIXME: Address width separately?
		self.irq = Signal(4)
		self.irqack = Signal(4)
		self.alu = ALU(w)
		self.state = Signal(State)
		self.Rs1 = Signal(range(nr))
		self.Rs2 = Signal(range(nr))
		self.Rd = Signal(range(nr))
		self.opc = Signal(Opcode)
		self.cond = Signal(4)
		self.load_addr = Signal(w)
		self.store_addr = Signal(w)
		wr1 = self.opc.width + self.cond.width
		wr2 = wr1 + self.Rd.width
		wr3 = wr2 + self.Rs1.width
		wr4 = wr3 + self.alu.op.width
		wr5 = wr4 + self.Rs2.width
		self.imm8 = Signal(w - wr5) # Not used
		self.imm12 = Signal(w - wr4)
		self.imm16 = Signal(w - wr3)
		self.imm20 = Signal(w - wr2)
		self.imm24 = Signal(w - wr1)
		self.ls_size = Signal(2)

		self.Rr = Array([Signal(w) for _ in range(nr)])
		self.pc = self.Rr[-1]
		self.lr = self.Rr[-2]
		self.sp = self.Rr[-3]
		self.irqmode = Signal()
		self.irqaddr = Signal(3)
		self.nextirq = Signal(4)
		self.irqreg = Signal(4)
		self.state = Signal(State)
		self.ir = Signal(w)
		self.next_pc = Signal(w)
		self.epc = Signal(w)
		self.elr = Signal(w)
		self.estatus = Signal(3)
		self.c_reg = Signal()
		self.n_reg = Signal()
		self.z_reg = Signal()
		self.i_reg = Signal()

	def ports(self):
		return [self.bus.adr_o, self.bus.dat_o, self.bus.stb_o, self.bus.we_o, self.bus.sel_o,
				self.bus.dat_i, self.bus.ack_i, self.irq, self.irqack,
				self.state, self.ir, self.pc]

	def elaborate(self, platform: Platform) -> Module:
		m = Module()
		m.submodules.alu = self.alu
		w = self.width
		nr = self.nregs
		c = m.d.comb
		c += [
			Cat(self.imm8, self.Rs2, self.alu.op, self.Rs1, self.Rd, self.cond, self.opc).eq(self.ir),
			self.load_addr.eq(self.Rr[self.Rs1] + self.imm16),
			self.store_addr.eq(self.Rr[self.Rd] + self.imm16),
			self.ls_size.eq(self.opc[:2]),
			self.alu.arg_a.eq(self.Rr[self.Rs1]),
			self.alu.arg_b.eq(Mux(self.opc == 0, self.Rr[self.Rs2], self.imm12)),
			self.alu.c_in.eq(self.c_reg),
			self.imm12.eq(self.ir),
			self.imm16.eq(self.ir),
			self.imm20.eq(self.ir),
			self.imm24.eq(self.ir),
			self.irqaddr.eq(Mux(self.irqreg[0], 1, Mux(self.irqreg[1], 2, Mux(self.irqreg[2], 3, 4)))),
			self.nextirq.eq(Mux(self.irqreg[0], 1, Mux(self.irqreg[1], 2, Mux(self.irqreg[2], 4, 8))))
		]
		s = m.d.sync
		with m.If(self.bus.rst_i):
			s += self.state.eq(State.RESET)
		with m.Else():
			self.cpu_fms(m, s, w)
		return m

	def cpu_fms(self, m, s, w):
		with m.Switch(self.state):
			with m.Case(State.RESET):
				self.cpu_reset(m, s, w)
			with m.Case(State.FETCH):
				self.cpu_fetch(m, s, w)
			with m.Case(State.DECODE):
				self.cpu_decode(m, s, w)
			with m.Case(State.EXECUTE):
				self.cpu_execute(m, s, w)
			with m.Case(State.LOAD):
				self.cpu_load(m, s, w)
			with m.Case(State.STORE):
				self.cpu_store(m, s, w)
			with m.Default():
				s += self.state.eq(State.FETCH)

	def cpu_reset(self, m, s, w):
		s += [self.Rr[i].eq(0) for i in range(self.nregs)]
		s += [
			self.irqmode.eq(0),
			self.z_reg.eq(1),
			self.n_reg.eq(0),
			self.c_reg.eq(0),
			self.i_reg.eq(1),
			self.bus.stb_o.eq(0),
			self.next_pc.eq(0),
			self.estatus.eq(2),
			self.elr.eq(0),
			self.epc.eq(0),
			self.state.eq(State.FETCH),
			self.irqack.eq(0),
			self.irqreg.eq(0)
		]

	def cpu_fetch(self, m, s, w):
		with m.If(self.irqreg.any() & ~self.irqmode & ~self.i_reg):
			# IRQ
			s += self.irqack.eq(self.nextirq)
			s += self.bus.adr_o.eq(self.irqaddr << 3)
			s += self.pc.eq(self.irqaddr << 3)
			s += self.epc.eq(self.next_pc)
			s += self.elr.eq(self.lr)
			s += self.estatus.eq(Cat(self.n_reg, self.z_reg, self.c_reg))
		with m.Else():
			# Normal or Interrupt mode
			s += self.bus.adr_o.eq(self.next_pc)
			s += self.pc.eq(self.next_pc)
		s += self.bus.we_o.eq(0)
		s += self.bus.sel_o.eq(~0) # All ones
		s += self.bus.stb_o.eq(1)
		with m.If(self.bus.ack_i):
			with m.If(self.irqreg.any() & ~self.irqmode & ~self.i_reg):
				s += self.irqmode.eq(1)
			s += self.state.eq(State.DECODE)

	def cpu_decode(self, m, s, w):
		s += self.irqreg.eq(self.irq)
		s += self.irqack.eq(0)
		s += self.ir.eq(self.bus.dat_i)
		s += self.bus.stb_o.eq(0)
		s += self.next_pc.eq(self.pc + 4)
		with m.Switch(self.cond):
			with m.Case("100-"):
				s += self.state.eq(Mux(self.z_reg == self.cond[0], State.EXECUTE, State.FETCH))
			with m.Case("1110"):
				s += self.state.eq(Mux(self.n_reg & ~self.z_reg, State.EXECUTE, State.FETCH))
			with m.Case("1100"):
				s += self.state.eq(Mux(~self.n_reg & ~self.z_reg, State.EXECUTE, State.FETCH))
			with m.Case("1111"):
				s += self.state.eq(Mux(self.n_reg | self.z_reg, State.EXECUTE, State.FETCH))
			with m.Case("1101"):
				s += self.state.eq(Mux(~self.n_reg | self.z_reg, State.EXECUTE, State.FETCH))
			with m.Case("101-"):
				s += self.state.eq(Mux(self.c_reg == self.cond[0], State.EXECUTE, State.FETCH))
			with m.Default():
				s += self.state.eq(State.EXECUTE)

	def cpu_execute(self, m, s, w):
		with m.Switch(self.opc):
			with m.Case(Opcode.alu, Opcode.alui):
				s += self.Rr[self.Rd].eq(self.alu.result)
				s += self.c_reg.eq(self.alu.c)
				s += self.z_reg.eq(self.alu.z)
				s += self.n_reg.eq(self.alu.n)
				s += self.state.eq(State.FETCH)
			with m.Case(Opcode.ldi):
				s += self.Rr[self.Rd].eq(self.imm20)
				s += self.state.eq(State.FETCH)
			with m.Case(Opcode.ldis):
				s += self.Rr[self.Rd].eq(Cat(self.imm20, Repl(self.imm20[-1], w - self.imm20.width)))
				s += self.state.eq(State.FETCH)
			with m.Case(Opcode.ldiu):
				s += self.Rr[self.Rd].eq(self.imm20 << (w - self.imm20.width))
				s += self.state.eq(State.FETCH)
			with m.Case(Opcode.ldb, Opcode.ldh, Opcode.ldw):
				s += self.bus.adr_o.eq(self.load_addr)
				s += self.bus.we_o.eq(0)
				self._set_sel_o(m, s, self.load_addr)
				s += self.bus.stb_o.eq(1)
				with m.If(self.bus.ack_i):
					with m.If(self.Rs1 == -3): # Rr[-3] == sp
						s += self.sp.eq(self.sp + 4) # POP
					s += self.state.eq(State.LOAD)
			with m.Case(Opcode.stb, Opcode.sth, Opcode.stw):
				s += self.bus.adr_o.eq(self.store_addr)
				s += self.bus.we_o.eq(1)
				self._set_sel_o(m, s, self.store_addr)
				with m.Switch(self.ls_size):
					with m.Case(0):
						bs = self.store_addr[:2] << 3
						s += self.bus.dat_o.eq((self.Rr[self.Rs1] & 0xff) << bs)
					with m.Case(1):
						s += self.bus.dat_o.eq(Mux(self.store_addr[1], self.Rr[self.Rs1] << 16, self.Rr[self.Rs1] & 0xffff))
					with m.Default():
						s += self.bus.dat_o.eq(self.Rr[self.Rs1])
				s += self.bus.stb_o.eq(1)
				with m.If(self.bus.ack_i):
					with m.If(self.Rs1 == -3): # Rr[-3] == sp
						s += self.sp.eq(self.sp - 4) # POP
					s += self.state.eq(State.STORE)
			with m.Case(Opcode.b):
				s += self.next_pc.eq(self.pc + Cat(self.imm24, Repl(self.imm24[-1], w - self.imm24.width - 2)) << 2)
				s += self.state.eq(State.FETCH)
			with m.Case(Opcode.bdec):
				with m.If(self.Rr[self.Rd].any()):
					s += self.next_pc.eq(self.pc + (Cat(self.imm20, Repl(self.imm20[-1], w - self.imm20.width - 2)) << 2))
					s += self.Rr[self.Rd].eq(self.Rr[self.Rd] - 1)
				s += self.state.eq(State.FETCH)
			with m.Case(Opcode.jsr):
				s += self.lr.eq(self.pc)
				s += self.next_pc.eq(self.Rr[self.Rd] + self.imm20)
				s += self.state.eq(State.FETCH)
			with m.Case(Opcode.ext):
				with m.Switch(self.Rd): # Rd == ext field
					with m.Case(0): # RTS
						s += self.next_pc.eq(self.lr)
					with m.Case(1): # RTI
						s += self.irqmode.eq(0)
						s += self.next_pc.eq(self.epc)
						s += self.lr.eq(self.elr)
						s += Cat(self.n_reg, self.z_reg, self.c_reg).eq(self.estatus)
					with m.Case(2): # SEI/CLI
						s += self.i_reg.eq(self.imm20[0])
				s += self.state.eq(State.FETCH)
			with m.Default():
				s += self.state.eq(State.FETCH)

	def _set_sel_o(self, m, s, addr):
		# FIXME: This function needs to be parametrized for different bus widths.
		with m.Switch(self.ls_size):
			with m.Case(0):
				s += self.bus.sel_o.eq(1 << addr[:2])
			with m.Case(1):
				s += self.bus.sel_o.eq(3 << addr[1])
			with m.Default():
				s += self.bus.sel_o.eq(~0)

	def cpu_load(self, m, s, w):
		# FIXME: This function needs to be parametrized for different bus widths.
		s += self.bus.stb_o.eq(0)
		with m.Switch(self.ls_size):
			with m.Case(0):
				bs = self.load_addr[:2] << 3
				s += self.Rr[self.Rd].eq((self.bus.dat_i >> bs) & 0xff)
			with m.Case(1):
				s += self.Rr[self.Rd].eq(Mux(self.load_addr[1], self.bus.dat_i[16:], self.bus.dat_i[:16]))
			with m.Default():
				s += self.Rr[self.Rd].eq(self.bus.dat_i)
		s += self.state.eq(State.FETCH)

	def cpu_store(self, m, s, w):
		s += self.bus.stb_o.eq(0)
		s += self.bus.we_o.eq(0)
		s += self.state.eq(State.FETCH)

	@classmethod
	def formal(cls) -> Tuple[Module, List[Signal]]:
		m = Module()
		m.submodules.cpu = cpu = cls(32, 16)
		return m, cpu.ports()


if __name__ == "__main__":
	simulate = ("--sim" in sys.argv)
	if simulate:
		from assemble import Cpuv2Assembler
		mem = []
		class Assemble2Mem(Cpuv2Assembler):
			def emit(self, emit):
				if isinstance(emit, list):
					mem.extend(emit)
				else:
					mem.append(emit)
		a = Assemble2Mem("monitor.s")
		top = Module()
		top.submodules.cpu = cpu = Cpu(32, 16)
		top.d.comb += cpu.bus.ack_i.eq(cpu.bus.stb_o)
		print("Simulating...")
		def process():
			for i in range(300):
				stb = yield cpu.bus.stb_o
				we = yield cpu.bus.we_o
				adr = yield cpu.bus.adr_o // 4
				if stb:
					if we:
						if adr < len(mem):
							mem[adr] = yield cpu.bus.dat_o
					else:
						if adr >= len(mem):
							do = 0x00213200
						else:
							do = mem[adr]
						yield cpu.bus.dat_i.eq(do)
				yield
		sim = Simulator(top)
		sim.add_clock(1e-7)
		sim.add_sync_process(process)
		with sim.write_vcd("test.vcd", "test.gtkw", traces=cpu.ports()):
			sim.run()
	else:
		parser = main_parser()
		args = parser.parse_args()
		m1, ports1 = ALU.formal()
		m2, ports2 = Cpu(32, 16).formal()
		main_runner(parser, args, m2, ports=ports2)
