#!/usr/bin/env python3
import os
import sys


class Cpuv2Assembler:
	condcodes = {
		"eq": 9,
		"ne": 8,
		"lt": 14,
		"gt": 12,
		"le": 15,
		"ge": 13,
		"cs": 11,
		"cc": 10
	}
	opcodes = {
		"ldi": 2,
		"ldis": 3,
		"ldiu": 7,
		"ldb": 4,
		"ldh": 5,
		"ldw": 6,
		"stb": 8,
		"sth": 9,
		"stw": 10,
		"b": 12,
		"bdec": 13,
		"jsr": 14,
		"rts": 15,
		"rti": 15,
		"sei": 15,
		"cli": 15
	}
	alucodes = {
		"add": 0,
		"sub": 1,
		"adc": 2,
		"sbc": 3,
		"not": 4,
		"and": 5,
		"or": 6,
		"xor": 7,
		"shl": 8,
		"shr": 9,
		"asl": 10,
		"asr": 11,
		"sl4": 12,
		"sl16": 13,
		"sr4": 14,
		"sr16": 15
	}
	def __init__(self, fname):
		self.labels = {}
		self.pc = 0
		self.lineno = 1
		self.stage = 0
		with open(fname, "r") as f:
			for l in f.readlines():
				self.parse_line(l.strip("\r\n"))
				self.lineno += 1
		self.pc = 0
		self.lineno = 1
		self.stage = 1
		with open(fname, "r") as f:
			for l in f.readlines():
				emit = self.parse_line(l.strip("\r\n"))
				if emit is not None:
					self.emit(emit)
				self.lineno += 1

	def emit(self, emit):
		if isinstance(emit, list):
			for x in emit:
				print("{:08x}".format(x))
		else:
			print("{:08x}".format(emit))

	def parse_line(self, l):
		if not len(l):
			return None
		if "#" in l:
			l, _ = l.split("#", 1) # Remove comments
		ls = l.strip() # Make a line without leading or ending spaces
		if not len(ls):
			return None
		if l[0] == " " or l[0] == "\t":
			# Expect opcode oper,... or .cmd data
			if ls[0] == ".":
				return self.parse_cmd(ls)
			else:
				return self.parse_opcode(ls)
		elif ls.endswith(":"):
			# This is a label
			self.labels[ls[:-1]] = self.pc
			return None
		print("Syntax error in line {}".format(self.lineno))
		sys.exit(1)
		return None # Never reached

	def parse_cmd(self, cmd):
		cmd, arg = cmd.split(" ", 1)
		if cmd == ".STR" and arg[0] == '"':
			s = eval(arg)
			ret = []
			d = 0
			for i in range(len(s)):
				bi = i & 3
				d |= ord(s[i]) << (8 * bi)
				if bi == 3:
					ret.append(d)
					d = 0
			if bi != 3:
				ret.append(d)
		elif cmd == ".STRW" and arg[0] == '"':
			s = eval(arg)
			ret = [ord(x) for x in s]
		elif cmd == ".WORD":
			ret = [int(arg, 0)]
		elif cmd == ".ORG":
			ret = []
			self.pc = int(arg, 0)
		else:
			print("Command syntax error in line {}: {!r}".format(self.lineno, cmd))
		self.pc += len(ret) * 4
		return ret

	def parse_cond(self, opc):
		if len(opc) < 3:
			return opc, 0, ""
		cond = opc[-2:]
		condn = self.condcodes.get(cond, 0)
		if condn:
			opc = opc[:-2]
		else:
			cond = ""
		return opc, condn, cond

	def instr(self, *args):
		shf = 28
		ret = 0
		for a in args[:-1]:
			ret |= a << shf
			shf -= 4
		ret |= args[-1]
		self.pc += 4
		return ret

	def parse_imm(self, arg, bitlen, bmode=False):
		msk = (1 << bitlen) - 1
		if arg[0] in "0123456789-":
			ret = int(arg, 0)
		elif arg in self.labels:
			ret = self.labels[arg]
			if bmode:
				ret = ((ret - self.pc) >> 2)
		elif self.stage == 0:
			ret = 0 # Probably a label that will get filled soon
		else:
			print("Unrecongized imm, error in line {}: {!r}".format(self.lineno, arg))
			sys.exit(3)
		if abs(ret & msk) < abs(ret):
			print("Immediate argument out of range, error in line {}".format(self.lineno))
			sys.exit(7)
		ret = ret & msk
		return ret

	def parse_reg(self, arg):
		arg = arg.lower()
		if arg == "lr":
			return 14
		elif arg == "pc":
			return 15
		elif arg == "sp":
			return 13
		if arg[0] != "r":
			print("Unknown register name in line {}".format(self.lineno))
			sys.exit(6)
		n = int(arg[1:])
		if 0 <= n <= 15:
			return n
		print("Register number must be between 0 and 15 in line {}".format(self.lineno))
		sys.exit(7)

	def parse_opcode(self, l):
		if " " in l:
			opc, rest = l.split(" ", 1)
		else:
			opc = l
			rest = ""
		opc, condn, cond = self.parse_cond(opc)
		# First check for aliases
		if opc == "pop":
			return self.parse_opcode("ldw{} {}, sp, 4".format(cond, rest))
		elif opc == "push":
			return self.parse_opcode("stw{} sp, {}, 0".format(cond, rest))
		if opc in self.alucodes:
			opcn = 0
			alun = self.alucodes[opc]
		elif opc[:-1] in self.alucodes:
			opcn = 1
			alun = self.alucodes[opc[:-1]]
		elif opc in self.opcodes:
			opcn = self.opcodes[opc]
			alun = 0
		else:
			print("Unknown opcode in line {}".format(self.lineno))
			sys.exit(2)
		if opcn == 12:
			imm24 = self.parse_imm(rest, 24, bmode=True)
			return self.instr(opcn, condn, imm24)
		elif opcn == 15:
			imm20 = 0
			if opc == "rti":
				ext = 1
			elif opc == "sei":
				ext = 2
				imm20 = 1
			elif opc == "cli":
				ext = 2
				imm20 = 0
			else: # rts
				ext = 0
			return self.instr(opcn, condn, ext, imm20)
		words = [w.strip() for w in rest.split(",")]
		rdn = self.parse_reg(words[0])
		if (opcn in [2,3,7,13,14] and len(words) != 2) or (opcn in [0, 1, 4, 5, 6, 8, 9, 10] and len(words) != 3):
			print("Excess or insuficient parameters in line {}".format(self.lineno))
			sys.exit(4)
		if opcn in [2,3,7,14]:
			imm20 = self.parse_imm(words[1], 20)
			return self.instr(opcn, condn, rdn, imm20)
		elif opcn == 13:
			imm20 = self.parse_imm(words[1], 20, bmode=True)
			return self.instr(opcn, condn, rdn, imm20)
		rs1 = self.parse_reg(words[1])
		if opcn in [4, 5, 6, 8, 9, 10]:
			imm16 = self.parse_imm(words[2], 16)
			return self.instr(opcn, condn, rdn, rs1, imm16)
		if opcn == 0:
			rs2 = self.parse_reg(words[2])
			return self.instr(opcn, condn, rdn, rs1, alun, rs2, 0)
		elif opcn == 1:
			imm12 = self.parse_imm(words[2], 12)
			return self.instr(opcn, condn, rdn, rs1, alun, imm12)
		print("Unimplented opcode in line {}".format(self.lineno))
		sys.exit(5)


if __name__ == "__main__":
	a = Cpuv2Assembler(sys.argv[1])

