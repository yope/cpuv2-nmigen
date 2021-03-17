
# Monitor program
#
# Register usage:
# r0: 0, zero, null, zip, nada
# r1...r4: Scratch registers. Clobbered by subroutine
# r5...r8: Working registers. Never clobbered
# r9...r12: Arguments passed to subroutine, return values from subroutine
#
# Subroutines:
# No need to push/pop lr if it doesn't call any other subroutine within.
#

reset:
	b start
irq0:
	b isr0
irq1:
	b isr1
irq2:
	b isr2
irq3:
	b isr3
start:
	ldi r0, 0
	ldi sp, 0xffc
	# Debug ENET:
	ldiu r1, 0x04000
	ldi r2, 0
	stw r1, r2, 0x2c	# Counter = 0
	ldi r2, 60
	stw r1, r2, 0	# Start Ethernet TX

	ldi r1, bss_end
	subi r2, r1, bss
	shri r2, r2, 0
	shri r2, r2, 0
	subi r2, r2, 1
bss_copy_loop:
	subi r1, r1, 4
	stw r1, r0, 0
	bdec r2, bss_copy_loop
	ldi r1, 0x4c	# Default color code
	stw r0, r1, v_color
	b main

# Global variables
bss:
v_cursor_x:
	.WORD 0
v_cursor_y:
	.WORD 0
v_blink_count:
	.WORD 0
v_blink_flag:
	.WORD 0
v_color:
	.WORD 0
stdout:
	.WORD 0

bss_end:

isr0:
	push r1
	push r2
	ldi r2, 0x11
isr_common:
	ldi r0, 0
	ldiu r1, 0x01000
	stb r1, r2, 0
	ldiu r1, 0x04000
	ldw r2, r1, 0
	ori r2, r2, 0
	bne isr_exit
	ldw r2, r1, 0x2c	# Counter value in payload
	addi r2, r2, 1
	stw r1, r2, 0x2c	# Store back
	ldi r2, 60
	stw r1, r2, 0	# Start Ethernet TX
isr_exit:
	pop r2
	pop r1
	rti

isr1:
	push r1
	push r2
	ldi r2, 0x22
	b isr_common

isr2:
	push r1
	push r2
	ldi r2, 0x33
	b isr_common

isr3:
	push r1
	push r2
	ldi r2, 0x44
	b isr_common

ascii_conv:
	andi r1, r9, 0xe0
	andi r9, r9, 0x1f
	sr4i r1, r1, 0
	shli r1, r1, 0
	ldw r1, r1, conv_map
	or r9, r1, r9
	rts
conv_map:
	.WORD 0x00000080
	.WORD 0x00000020
	.WORD 0x00000040
	.WORD 0x00000000
	.WORD 0x000000C0
	.WORD 0x00000060
	.WORD 0x00000040
	.WORD 0x00000060

putc_uart:
	ldiu r1, 0x03000
	ldw r2, r1, 8	# Read status register
	andi r2, r2, 1	# TX busy?
	bne putc_uart
	stw r1, r9, 0
	rts

getc_uart:
	ldiu r1, 0x03000
	ldw r9, r1, 8 # Status register
	andi r9, r9, 2 # Check RX full flag
	ldiseq r9, 0xfff00 # No RX, return -256
	rtseq
	ldw r9, r1, 4 # RXD register
	rts

get_cursor_address:
	# Return r9 = x, r10 = y and r11 = address in screen RAM
	ldw r10, r0, v_cursor_y	# r10 = cursor_y
	sl4i r11, r10, 0
	ori r9, r11, 0
	shli r11, r11, 0
	shli r11, r11, 0
	add r11, r11, r9		# r11 = cursor_y * 80
	ldw r9, r0, v_cursor_x	# r9 = cursor_x
	add r1, r11, r9			# Add to r11
	ldiu r11, 0x02000
	add r11, r11, r1		# Add screen RAM offset
	rts

putc_screen:
	push lr
	push r9
	jsr r0, cursor_blink_off # Turn off cursor
	pop r9
	andi r1, r9, 0x80	# Higher than ASCII?
	beq putc_screen_0	# not? continue
	subi r1, r9, 0x9f	# Last hight control char
	bgt putc_screen_0	# higher? continue
	subi r1, r9, 0x80	# Get color code
	ldw r3, r0, v_color	# load current colors (bg/fg)
	andi r2, r1, 0x10	# Check for BG color
	bne putc_bg_color
	andi r3, r3, 0xf0	# Keep old bg color
	or r3, r3, r1		# Or them together
	stw r0, r3, v_color	# And store
	pop lr
	rts
putc_bg_color:
	andi r3, r3, 0x0f	# Keep old fg color
	sl4i r1, r1, 0		# Shift to bg color pos.
	andi r1, r1, 0xf0	# Isolate new bg color
	or r3, r3, r1		# Or them together
	stw r0, r3, v_color	# And store
	pop lr
	rts
putc_screen_0:
	subi r1, r9, 10		# Check for '\n'
	subine r1, r9, 13	# Check for '\r'
	bne putc_screen_1
	ldi r1, 0			# Set new cursor_x = 0
	stw r0, r1, v_cursor_x
	ldw r10, r0, v_cursor_y
	ori r0, r0, 0		# Set Z flag
	b putc_screen_nl	# Goto next line
putc_screen_1:
	subi r1, r9, 8		# Check back-space
	subine r1, r9, 0x7f	# Check DEL
	bne putc_screen_2
	ldw r1, r0, v_cursor_x
	ori r1, r1, 0		# Check if zero
	subine r1, r1, 1	# Go back one position if not
	stw r0, r1, v_cursor_x
	pop lr				# And we are done.
	rts
putc_screen_2:
	subi r1, r9, 12		# Check for FF (clear screen)
	bne putc_screen_3
	stw r0, r0, v_cursor_x # If equal, home the cursor,...
	stw r0, r0, v_cursor_y
	pop lr				# ..., pop lr and
	b clear				# jump to clear routine
putc_screen_3:
	jsr r0, ascii_conv
	push r9				# Save r9 on stack
	jsr r0, get_cursor_address
	pop r1				# pop character in r1 (former r9)
	stb r11, r1, 0		# Store character to screen
	ldw r1, r0, v_color	# Get bg/fg colors
	stb r11, r1, 0x2000	# Store in color RAM
	addi r9, r9, 1
	subi r3, r9, 80		# Is cursor past end of line
	stwge r0, r3, v_cursor_x # Sore new position
	stwlt r0, r9, v_cursor_x # Or stor old position + 1
putc_screen_nl:
	addige r10, r10, 1	# Goto next line if needed
	subi r2, r10, 60	# Is cursor past end of screen
	ldige r10, 59		# then place cursor on last line...
	stw r0, r10, v_cursor_y
	jsrge r0, scroll	# and scroll up.
	pop lr
	rts

putc: # r9: character
	ldw r1, r0, stdout
	ori r1, r1, 0
	beq putc_screen
	ldw r1, r0, stdout
	subi r1, r1, 1
	beq putc_uart
	rts					# Not reached unless unsupported device number

puts:
	push lr
	push r8
	ori r8, r9, 0		# Store pointer in r8
puts_loop:
	ldb r9, r8, 0		# Load next char from string
	ori r9, r9, 0		# Set flags
	beq puts_end 		# If it is 0, finish
	jsr r0, putc		# Otherwise print it
	addi r8, r8, 1		# Increment pointer
	b puts_loop
puts_end:
	addi r9, r8, 1		# return address after \0
	pop r8
	pop lr
	rts

printsi: # Print screen immediate
	ori r9, lr, 0		# Get lr, which points to the string
	jsr r0, puts		# puts returns address after \0 in r9
	andi r1, r9, 3		# Align r9 to 32 bits
	beq printsi_end		# Already aligned? Exit...
	xorine r1, r1, 3	# Do alignment
	add r9, r9, r1
	addine r9, r9, 1
printsi_end:
	ori lr, r9, 0		# save new lr as return address
	rts					# Return there

printhex4:
	push lr
	andi r9, r9, 0x0f
	ldb r9, r9, printhex4_table
	jsr r0, putc
	pop lr
	rts
printhex4_table:
	.STR "0123456789abcdef"

printhex8:
	push lr
	push r9
	sr4i r9, r9, 0
	andi r9, r9, 0x0f
	ldb r9, r9, printhex4_table
	jsr r0, putc
	pop r9
	andi r9, r9, 0x0f
	ldb r9, r9, printhex4_table
	jsr r0, putc
	pop lr
	rts

printhex16:
	push lr
	push r9
	sr4i r9, r9, 0
	sr4i r9, r9, 0
	jsr r0, printhex8
	pop r9
	jsr r0, printhex8
	pop lr
	rts

printhex32:
	push lr
	push r9
	sr16i r9, r9, 0
	jsr r0, printhex16
	pop r9
	jsr r0, printhex16
	pop lr
	rts

scroll:
	push r4
	ldiu r1, 0x02000
	ldi r2, 4720
scroll_loop:
	ldb r3, r1, 80
	stb r1, r3, 0
	ldb r3, r1, 0x2050
	stb r1, r3, 0x2000
	addi r1, r1, 1
	bdec r2, scroll_loop
	ldi r2, 80
	ldi r3, 0x20
	ldw r4, r0, v_color
scroll_loop2:
	stb r1, r3, 0
	stb r1, r4, 0x2000
	addi r1, r1, 1
	bdec r2, scroll_loop2
	pop r4
	rts

cursor_putxy:
	stw r0, r9, v_cursor_x
	stw r0, r10, v_cursor_y
	rts

cursor_blink:
	ldw r1, r0, v_blink_count
	addi r1, r1, 1
	ldi r2, 0x20000
	sub r2, r1, r2
	stwge r0, r0, v_blink_count
	stwlt r0, r1, v_blink_count
	ldi r2, 0x10000
	and r2, r1, r2
	beq cursor_blink_off
cursor_blink_on:
	ldw r1, r0, v_blink_flag
	ori r1, r1, 0			# Check if set
	rtsne					# Already set? -> return
	ldi r5, 1				# New flag value 1
cursor_blink_invert:
	push lr
	jsr r0, get_cursor_address
	pop lr
	ldb r1, r11, 0			# Get character at cursor
	xori r1, r1, 0x80		# Invert MSB
	stb r11, r1, 0			# And store it back
	stw r0, r5, v_blink_flag # Store new flag value
	rts
cursor_blink_off:
	ldw r1, r0, v_blink_flag
	ori r1, r1, 0			# Check if set
	ldine r5, 0				# New flag value 0
	bne cursor_blink_invert	# Set, then invert character and clear
	rts

clear:
	ldi r1, 0x20 # Space character
	ldw r2, r0, v_color
	ldi r3, 0x12bf
	ldiu r4, 0x02000
clear_loop:
	stb r4, r1, 0
	stb r4, r2, 0x2000
	addi r4, r4, 1
	bdec r3, clear_loop
	rts

delay:
	ldi r1, 0x60000
	bdec r1, 0
	rts

delay_n:
	push lr
	jsr r0, delay
	bdec r9, -1
	pop lr
	rts

readbuttons:
	push lr
	ldiu r1, 0x01000
	ldw r9, r1, 0
	xori r9, r9, 1
	popeq lr			# No key detected? return
	rtseq
	push r9
	jsr r0, delay			# Wait a bit to debounce
	pop r2
	ldiu r1, 0x01000		# Try again
	ldw r9, r1, 0
	xori r9, r9, 1
	xor r1, r2, r9
	ldine r9, 0			# Not equal? return 0
	pop lr
	rts

menui:
	push r5
	push r6
	push r7
	push r8
	ori r1, lr, 0			# Get number of entries
	ldw r5, r1, 0
	subi r5, r5, 1			# r5: index of last entry
	addi r8, lr, 4			# r8: pointer to first string
	ldi r6, 0			# r6: selected entry
	ldw r1, r0, v_cursor_x		# Save cursor position
	ldi r2, menui_cursor
	stb r2, r1, 0
	ldw r1, r0, v_cursor_y
	stb r2, r1, 1
menui_loop:
	push r8				# Save to stack
	ldi r7, 0			# r7: index of entries to print
	ldi r2, menui_cursor
	ldb r1, r2, 1			# Get stored y position
	stw r0, r1, v_cursor_y		# Set cursor y
menui_printloop:
	ldi r2, menui_cursor
	ldb r1, r2, 0			# Get stored x position
	stw r0, r1, v_cursor_x		# Set cursor x
	sub r1, r6, r7			# Is current entry selected
	ldieq r9, 0x92
	ldine r9, 0x94
	jsr r0, putc
	pop r9				# Get next pointer
	jsr r0, puts			# print it
	andi r1, r9, 3			# Align r9 to 32 bits
	beq 4				# Already aligned? skip 3
	xorine r1, r1, 3		# Do alignment
	add r9, r9, r1
	addine r9, r9, 1
	push r9				# push next pointer
	ldi r9, 0x94
	jsr r0, putc			# Make blue background again
	addi r7, r7, 1			# Next enty
	sub r1, r5, r7
	bge menui_printloop
	jsr r0, readbuttons
	andi r1, r9, 0x08		# Up?
	beq 3				# Skip two instructions if not
	ori r6, r6, 0			# r6 > 0?
	subigt r6, r6, 1		# then decrement
	andi r1, r9, 0x10		# Down?
	beq 3				# Skip two instructions if not
	sub r1, r5, r6			# r1 = number of entries - selected - 1
	addigt r6, r6, 1		# Still positive? then add 1 to selected
	pop lr				# We need to pop the link register here
	andi r1, r9, 0x04		# F2 pressed
	beq menui_loop
	push lr
	jsr r0, readbuttons
	ori r9, r9, 0
	bne -2				# Wait until button released
	pop lr
	ori r9, r6, 0			# Return selected entry
	pop r8
	pop r7
	pop r6
	pop r5
	rts
menui_cursor:
	.WORD 0

hexdump: # r9: start pointer, r10: number of words
	push lr
	push r5
	push r6
	push r7
	push r8
	ldw r5, r0, v_cursor_x		# r5: cursor x
	ldw r6, r0, v_cursor_y		# r6: cursor y
	ori r7, r10, 0			# r7: counter
	ori r8, r9, 0			# r8: pointer
hexdump_loop:
	ori r9, r8, 0
	jsr r0, printhex32
	ldi r9, 0x3a			# Colon
	jsr r0, putc
	ldi r9, 0x20			# space
	jsr r0, putc
	ldw r9, r8, 0
	jsr r0, printhex32
	jsr r0, printsi
	.STR " \x5d\0"
hexdump_asciiloop:
	ldb r9, r8, 0
	andi r1, r9, 0xe0
	ldieq r9, 0x2e
	andi r1, r9, 0x80
	ldine r9, 0x2e
	jsr r0, putc
	addi r8, r8, 1
	andi r1, r8, 3
	bne hexdump_asciiloop
	jsr r0, printsi
	.STR "\x5d\n\0"
	stw r0, r5, v_cursor_x
	bdec r7, hexdump_loop
	pop r8
	pop r7
	pop r6
	pop r5
	pop lr
	rts

strtoul_hex: # r9: string buffer, r10: destination pointer
	ldi r3, 0		# r3: result accumulator
	ldb r2, r9, 0		# Load first char
strtoul_hex_loop:
	subi r1, r2, 0x60
	subige r2, r2, 0x20	# convert to upper case if needed.
	subi r1, r2, 0x41	# is character A...F?
	subige r2, r2, 7	# Put after 9
	subi r2, r2, 0x30	# convert char to number
	blt strtoul_hex_error	# Wasn't a number? error out
	subi r1, r2, 0x0f	# If bigger than 15?
	bgt strtoul_hex_error   # Error out
	sl4i r3, r3, 0		# Shift result left 4 bits
	or r3, r3, r2		# Or in next nibble
	addi r9, r9, 1
	ldb r2, r9, 0		# Read next char
	ori r2, r2, 0		# is it \0?
	bne strtoul_hex_loop	# Not? continue
	stw r10, r3, 0		# Save result
	ldi r9, 0		# Load return value SUCCESS
	b 2
strtoul_hex_error:
	ldis r9, 0xfffff	# Return value -1

	ori r9, r9, 0		# Set flags
	rts

loadhex: # r9 start address
	push lr
	push r5
	push r6
	push r7
	ori r6, r9, 0		# r6: pointer
	jsr r0, printsi
	.STR "\n LOADING...\n\0"
loadhex_loop:
	ldi r5, 0		# r5: line buffer counter
loadhex_lineloop:
	jsr r0, getc_uart
	ori r7, r9, 0		# r7: received char
	blt loadhex_lineloop
	subi r1, r7, 10		# LF
	subine r1, r7, 13	# CR
	subine r1, r7, 4	# EOT
	beq 5
	stb r5, r7, loadhex_buffer
	addi r5, r5, 1
	andi r5, r5, 15		# Max 16 chars in buffer
	b loadhex_lineloop

	stb r5, r0, loadhex_buffer	# Terminating \0
	subi r1, r5, 8
	bne 6
	ldi r9, loadhex_buffer
	ori r10, r6, 0
	jsr r0, strtoul_hex
	bne loadhex_error
	addi r6, r6, 4

	subi r1, r7, 4		# EOT?
	bne loadhex_loop	# Continue if not
	ldi r9, 0		# Return 0 for SUCCESS
	b 2

loadhex_error:
	ldis r9, 0xfffff	# On error return -1
	ori r9, r9, 0		# Set flags
	pop r7
	pop r6
	pop r5
	pop lr
	rts
loadhex_buffer:
	.WORD 0 # 8 words = 32 byte line buffer
	.WORD 0
	.WORD 0
	.WORD 0
	.WORD 0
	.WORD 0
	.WORD 0
	.WORD 0

main:
	cli		# Enable interrupts
	jsr r0, clear
	ldi r5, 64
	jsr r0, getc_uart
	bdec r5, -1			# Empty uart buffer
	stw r0, r0, stdout		# Print to screen
main_loop:
	ldi r9, 50
	ldi r10, 2
	jsr r0, cursor_putxy
	ldi r9, 0x1000
	ldi r10, 48
	jsr r0, hexdump
	ldi r9, 20
	ldi r10, 50
	jsr r0, cursor_putxy
	ldi r9, loadhex_buffer
	ldi r10, 8
	jsr r0, hexdump
	ldi r9, 20
	ldi r10, 30
	jsr r0, cursor_putxy
	ldiu r9, 0x04000
	ldi r10, 16
	jsr r0, hexdump
	ldi r9, 2
	ldi r10, 2
	jsr r0, cursor_putxy
	jsr r0, menui
	.WORD 3
	.STR "Load from serial port\n\0"
	.STR "Start program\n\0"
	.STR "Reset\n\0"
	ori r5, r9, 0			# r5: Selection
	ldi r9, 1
	ldi r10, 8
	jsr r0, cursor_putxy
	jsr r0, printsi
	.STR "Choice: \0"
	ori r9, r5, 0
	jsr r0, printhex8
	ori r1, r5, 0
	bne 5
	ldi r9, 0x1000
	jsr r0, loadhex
	beq main_success
	bne main_error

	subi r1, r5, 1
	jsreq r0, 0x1000

	b main_loop
main_error:
	jsr r0, printsi
	.STR "\n ERROR\n\0"
	ldi r9, 10
	jsr r0, delay_n
	jsr r0, clear
	b main_loop
main_success:
	jsr r0, printsi
	.STR "\n OK\n\0"
	ldi r9, 10
	jsr r0, delay_n
	jsr r0, clear
	b main_loop
