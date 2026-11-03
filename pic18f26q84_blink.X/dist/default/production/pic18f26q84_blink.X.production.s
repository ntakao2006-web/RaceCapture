subtitle "Microchip MPLAB XC8 C Compiler v4.00 build 20260614213421 Og1 "

pagewidth 120
	processor	18F26Q84
include "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc\18f26q84.cgen.inc"
getbyte	macro	val,pos
	(((val) >> (8 * pos)) and 0xff)
endm
byte0	macro	val
	(getbyte(val,0))
endm
byte1	macro	val
	(getbyte(val,1))
endm
byte2	macro	val
	(getbyte(val,2))
endm
byte3	macro	val
	(getbyte(val,3))
endm
byte4	macro	val
	(getbyte(val,4))
endm
byte5	macro	val
	(getbyte(val,5))
endm
byte6	macro	val
	(getbyte(val,6))
endm
byte7	macro	val
	(getbyte(val,7))
endm
getword	macro	val,pos
	(((val) >> (8 * pos)) and 0xffff)
endm
word0	macro	val
	(getword(val,0))
endm
word1	macro	val
	(getword(val,2))
endm
word2	macro	val
	(getword(val,4))
endm
word3	macro	val
	(getword(val,6))
endm
gettword	macro	val,pos
	(((val) >> (8 * pos)) and 0xffffff)
endm
tword0	macro	val
	(gettword(val,0))
endm
tword1	macro	val
	(gettword(val,3))
endm
tword2	macro	val
	(gettword(val,6))
endm
getdword	macro	val,pos
	(((val) >> (8 * pos)) and 0xffffffff)
endm
dword0	macro	val
	(getdword(val,0))
endm
dword1	macro	val
	(getdword(val,4))
endm
clrc   macro
	bcf	status,0
endm
setc   macro
	bsf	status,0
endm
clrz   macro
	bcf	status,2
endm
setz   macro
	bsf	status,2
endm
skipnz macro
	btfsc	status,2
endm
skipz  macro
	btfss	status,2
endm
skipnc macro
	btfsc	status,0
endm
skipc  macro
	btfss	status,0
endm
pushw macro
	movwf postinc1
endm
pushf macro arg1
	movff arg1, postinc1
endm
popw macro
	movf postdec1,f
	movf indf1,w
endm
popf macro arg1
	movf postdec1,f
	movff indf1,arg1
endm
popfc macro arg1
	movff plusw1,arg1
	decfsz fsr1,f
endm
skiprom24 macro arg1
	btfsc arg1,7
endm
	global	__ramtop
	global	__accesstop
# 290 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
BOOTREG equ 038h ;# 
# 322 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLKRCON equ 039h ;# 
# 426 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLKRCLK equ 03Ah ;# 
# 510 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NVMCON0 equ 040h ;# 
# 546 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NVMCON1 equ 041h ;# 
# 581 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NVMLOCK equ 042h ;# 
# 603 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NVMADR equ 043h ;# 
# 610 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NVMADRL equ 043h ;# 
# 680 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NVMADRH equ 044h ;# 
# 750 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NVMADRU equ 045h ;# 
# 808 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NVMDAT equ 046h ;# 
# 815 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NVMDATL equ 046h ;# 
# 885 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NVMDATH equ 047h ;# 
# 955 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
VREGCON equ 048h ;# 
# 1009 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
BORCON equ 049h ;# 
# 1036 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
HLVDCON0 equ 04Ah ;# 
# 1116 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
HLVDCON1 equ 04Bh ;# 
# 1188 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ZCDCON equ 04Ch ;# 
# 1268 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PMD0 equ 060h ;# 
# 1334 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PMD1 equ 061h ;# 
# 1396 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PMD2 equ 062h ;# 
# 1443 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PMD3 equ 063h ;# 
# 1494 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PMD4 equ 064h ;# 
# 1550 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PMD5 equ 065h ;# 
# 1607 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PMD6 equ 066h ;# 
# 1669 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PMD7 equ 067h ;# 
# 1731 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PMD8 equ 068h ;# 
# 1793 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
MD1CON0 equ 06Ah ;# 
# 1861 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
MD1CON1 equ 06Bh ;# 
# 1927 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
MD1SRC equ 06Ch ;# 
# 2031 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
MD1CARL equ 06Dh ;# 
# 2123 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
MD1CARH equ 06Eh ;# 
# 2215 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CMOUT equ 06Fh ;# 
# 2241 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CM1CON0 equ 070h ;# 
# 2321 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CM1CON1 equ 071h ;# 
# 2361 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CM1NCH equ 072h ;# 
# 2421 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CM1PCH equ 073h ;# 
# 2481 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CM2CON0 equ 074h ;# 
# 2561 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CM2CON1 equ 075h ;# 
# 2601 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CM2NCH equ 076h ;# 
# 2661 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CM2PCH equ 077h ;# 
# 2721 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
WDTCON0 equ 078h ;# 
# 2796 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
WDTCON1 equ 079h ;# 
# 2890 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
WDTPSL equ 07Ah ;# 
# 3018 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
WDTPSH equ 07Bh ;# 
# 3146 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
WDTTMR equ 07Ch ;# 
# 3234 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DAC1DAT equ 07Dh ;# 
# 3241 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DAC1DATL equ 07Dh ;# 
# 3319 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DAC1CON equ 07Fh ;# 
# 3422 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1RXB equ 080h ;# 
# 3492 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1TXB equ 081h ;# 
# 3562 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1TCNT equ 082h ;# 
# 3569 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1TCNTL equ 082h ;# 
# 3589 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1TCNTH equ 083h ;# 
# 3609 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1CON0 equ 084h ;# 
# 3675 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1CON1 equ 085h ;# 
# 3777 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1CON2 equ 086h ;# 
# 3855 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1STATUS equ 087h ;# 
# 3937 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1TWIDTH equ 088h ;# 
# 3977 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1BAUD equ 089h ;# 
# 4047 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1INTF equ 08Ah ;# 
# 4139 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1INTE equ 08Bh ;# 
# 4231 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1CLK equ 08Ch ;# 
# 4323 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2RXB equ 08Dh ;# 
# 4393 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2TXB equ 08Eh ;# 
# 4463 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2TCNT equ 08Fh ;# 
# 4470 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2TCNTL equ 08Fh ;# 
# 4490 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2TCNTH equ 090h ;# 
# 4510 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2CON0 equ 091h ;# 
# 4576 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2CON1 equ 092h ;# 
# 4678 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2CON2 equ 093h ;# 
# 4756 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2STATUS equ 094h ;# 
# 4838 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2TWIDTH equ 095h ;# 
# 4878 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2BAUD equ 096h ;# 
# 4948 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2INTF equ 097h ;# 
# 5040 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2INTE equ 098h ;# 
# 5132 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2CLK equ 099h ;# 
# 5224 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ACTCON equ 0ACh ;# 
# 5265 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
OSCCON1 equ 0ADh ;# 
# 5335 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
OSCCON2 equ 0AEh ;# 
# 5405 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
OSCCON3 equ 0AFh ;# 
# 5445 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
OSCTUNE equ 0B0h ;# 
# 5503 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
OSCFRQ equ 0B1h ;# 
# 5508 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
OSCFREQ equ 0B1h ;# 
# 5593 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
OSCSTAT equ 0B2h ;# 
# 5598 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
OSCSTAT1 equ 0B2h ;# 
# 5705 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
OSCEN equ 0B3h ;# 
# 5762 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PRLOCK equ 0B4h ;# 
# 5782 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SCANPR equ 0B5h ;# 
# 5850 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMA1PR equ 0B6h ;# 
# 5918 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMA2PR equ 0B7h ;# 
# 5986 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMA3PR equ 0B8h ;# 
# 6054 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMA4PR equ 0B9h ;# 
# 6122 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMA5PR equ 0BAh ;# 
# 6190 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMA6PR equ 0BBh ;# 
# 6258 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMA7PR equ 0BCh ;# 
# 6326 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMA8PR equ 0BDh ;# 
# 6394 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
MAINPR equ 0BEh ;# 
# 6462 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ISRPR equ 0BFh ;# 
# 6530 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCDATA equ 0D4h ;# 
# 6650 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCSELECT equ 0D5h ;# 
# 6690 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCnCON equ 0D6h ;# 
# 6760 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCnPOL equ 0D7h ;# 
# 6805 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCnSEL0 equ 0D8h ;# 
# 6875 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCnSEL1 equ 0D9h ;# 
# 6945 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCnSEL2 equ 0DAh ;# 
# 7015 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCnSEL3 equ 0DBh ;# 
# 7085 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCnGLS0 equ 0DCh ;# 
# 7147 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCnGLS1 equ 0DDh ;# 
# 7209 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCnGLS2 equ 0DEh ;# 
# 7271 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCnGLS3 equ 0DFh ;# 
# 7333 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMASELECT equ 0E8h ;# 
# 7373 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnBUF equ 0E9h ;# 
# 7443 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnDCNT equ 0EAh ;# 
# 7450 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnDCNTL equ 0EAh ;# 
# 7520 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnDCNTH equ 0EBh ;# 
# 7566 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnDPTR equ 0ECh ;# 
# 7573 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnDPTRL equ 0ECh ;# 
# 7643 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnDPTRH equ 0EDh ;# 
# 7713 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnDSZ equ 0EEh ;# 
# 7720 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnDSZL equ 0EEh ;# 
# 7790 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnDSZH equ 0EFh ;# 
# 7836 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnDSA equ 0F0h ;# 
# 7843 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnDSAL equ 0F0h ;# 
# 7913 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnDSAH equ 0F1h ;# 
# 7983 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnSCNT equ 0F2h ;# 
# 7990 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnSCNTL equ 0F2h ;# 
# 8060 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnSCNTH equ 0F3h ;# 
# 8108 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnSPTR equ 0F4h ;# 
# 8115 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnSPTRL equ 0F4h ;# 
# 8185 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnSPTRH equ 0F5h ;# 
# 8255 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnSPTRU equ 0F6h ;# 
# 8313 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnSSZ equ 0F7h ;# 
# 8320 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnSSZL equ 0F7h ;# 
# 8390 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnSSZH equ 0F8h ;# 
# 8438 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnSSA equ 0F9h ;# 
# 8445 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnSSAL equ 0F9h ;# 
# 8515 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnSSAH equ 0FAh ;# 
# 8585 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnSSAU equ 0FBh ;# 
# 8643 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnCON0 equ 0FCh ;# 
# 8689 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnCON1 equ 0FDh ;# 
# 8733 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnAIRQ equ 0FEh ;# 
# 8803 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
DMAnSIRQ equ 0FFh ;# 
# 8873 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1CONL equ 0100h ;# 
# 8943 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1CONH equ 0101h ;# 
# 9014 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1CONU equ 0102h ;# 
# 9085 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1CONT equ 0103h ;# 
# 9162 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1NBTCFGL equ 0104h ;# 
# 9226 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1NBTCFGH equ 0105h ;# 
# 9290 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1NBTCFGU equ 0106h ;# 
# 9360 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1NBTCFGT equ 0107h ;# 
# 9430 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1DBTCFGL equ 0108h ;# 
# 9476 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1DBTCFGH equ 0109h ;# 
# 9522 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1DBTCFGU equ 010Ah ;# 
# 9574 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1DBTCFGT equ 010Bh ;# 
# 9644 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TDCL equ 010Ch ;# 
# 9702 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TDCH equ 010Dh ;# 
# 9766 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TDCU equ 010Eh ;# 
# 9800 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TDCT equ 010Fh ;# 
# 9826 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TBC equ 0110h ;# 
# 9833 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TBCL equ 0110h ;# 
# 9903 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TBCH equ 0111h ;# 
# 9973 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TBCU equ 0112h ;# 
# 10043 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TBCT equ 0113h ;# 
# 10113 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TSCONL equ 0114h ;# 
# 10183 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TSCONH equ 0115h ;# 
# 10217 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TSCONU equ 0116h ;# 
# 10249 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TSCONT equ 0117h ;# 
# 10256 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1VECL equ 0118h ;# 
# 10276 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1VECH equ 0119h ;# 
# 10296 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1VECU equ 011Ah ;# 
# 10316 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1VECT equ 011Bh ;# 
# 10336 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1INTL equ 011Ch ;# 
# 10380 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1INTH equ 011Dh ;# 
# 10431 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1INTU equ 011Eh ;# 
# 10475 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1INTT equ 011Fh ;# 
# 10526 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1RXIF equ 0120h ;# 
# 10533 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1RXIFL equ 0120h ;# 
# 10599 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1RXIFH equ 0121h ;# 
# 10669 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1RXIFU equ 0122h ;# 
# 10739 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1RXIFT equ 0123h ;# 
# 10809 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXIF equ 0124h ;# 
# 10816 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXIFL equ 0124h ;# 
# 10886 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXIFH equ 0125h ;# 
# 10956 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXIFU equ 0126h ;# 
# 11026 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXIFT equ 0127h ;# 
# 11096 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1RXOVIF equ 0128h ;# 
# 11103 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1RXOVIFL equ 0128h ;# 
# 11169 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1RXOVIFH equ 0129h ;# 
# 11239 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1RXOVIFU equ 012Ah ;# 
# 11309 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1RXOVIFT equ 012Bh ;# 
# 11379 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXATIF equ 012Ch ;# 
# 11386 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXATIFL equ 012Ch ;# 
# 11456 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXATIFH equ 012Dh ;# 
# 11526 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXATIFU equ 012Eh ;# 
# 11596 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXATIFT equ 012Fh ;# 
# 11666 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXREQ equ 0130h ;# 
# 11673 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXREQL equ 0130h ;# 
# 11743 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXREQH equ 0131h ;# 
# 11813 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXREQU equ 0132h ;# 
# 11883 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXREQT equ 0133h ;# 
# 11953 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TRECL equ 0134h ;# 
# 12023 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TRECH equ 0135h ;# 
# 12093 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TRECU equ 0136h ;# 
# 12143 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TRECT equ 0137h ;# 
# 12150 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1BDIAG0L equ 0138h ;# 
# 12220 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1BDIAG0H equ 0139h ;# 
# 12290 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1BDIAG0U equ 013Ah ;# 
# 12360 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1BDIAG0T equ 013Bh ;# 
# 12430 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1BDIAG1L equ 013Ch ;# 
# 12500 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1BDIAG1H equ 013Dh ;# 
# 12570 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1BDIAG1U equ 013Eh ;# 
# 12627 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1BDIAG1T equ 013Fh ;# 
# 12684 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TEFCONL equ 0140h ;# 
# 12729 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TEFCONH equ 0141h ;# 
# 12756 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TEFCONU equ 0142h ;# 
# 12763 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TEFCONT equ 0143h ;# 
# 12815 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TEFSTAL equ 0144h ;# 
# 12853 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TEFSTAH equ 0145h ;# 
# 12860 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TEFSTAU equ 0146h ;# 
# 12867 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TEFSTAT equ 0147h ;# 
# 12874 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TEFUA equ 0148h ;# 
# 12881 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TEFUAL equ 0148h ;# 
# 12951 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TEFUAH equ 0149h ;# 
# 13021 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TEFUAU equ 014Ah ;# 
# 13091 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TEFUAT equ 014Bh ;# 
# 13161 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOBA equ 014Ch ;# 
# 13168 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOBAL equ 014Ch ;# 
# 13238 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOBAH equ 014Dh ;# 
# 13308 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOBAU equ 014Eh ;# 
# 13378 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOBAT equ 014Fh ;# 
# 13448 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXQCONL equ 0150h ;# 
# 13489 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXQCONH equ 0151h ;# 
# 13521 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXQCONU equ 0152h ;# 
# 13591 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXQCONT equ 0153h ;# 
# 13667 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXQSTAL equ 0154h ;# 
# 13719 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXQSTAH equ 0155h ;# 
# 13771 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXQSTAU equ 0156h ;# 
# 13778 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXQSTAT equ 0157h ;# 
# 13785 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXQUA equ 0158h ;# 
# 13792 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXQUAL equ 0158h ;# 
# 13862 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXQUAH equ 0159h ;# 
# 13932 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXQUAU equ 015Ah ;# 
# 14002 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1TXQUAT equ 015Bh ;# 
# 14072 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOCON1 equ 015Ch ;# 
# 14079 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOCON1L equ 015Ch ;# 
# 14141 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOCON1H equ 015Dh ;# 
# 14173 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOCON1U equ 015Eh ;# 
# 14243 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOCON1T equ 015Fh ;# 
# 14319 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOSTA1 equ 0160h ;# 
# 14326 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOSTA1L equ 0160h ;# 
# 14388 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOSTA1H equ 0161h ;# 
# 14440 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOSTA1U equ 0162h ;# 
# 14447 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOSTA1T equ 0163h ;# 
# 14454 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOUA1 equ 0164h ;# 
# 14461 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOUA1L equ 0164h ;# 
# 14531 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOUA1H equ 0165h ;# 
# 14601 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOUA1U equ 0166h ;# 
# 14671 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOUA1T equ 0167h ;# 
# 14741 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOCON2 equ 0168h ;# 
# 14748 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOCON2L equ 0168h ;# 
# 14810 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOCON2H equ 0169h ;# 
# 14842 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOCON2U equ 016Ah ;# 
# 14912 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOCON2T equ 016Bh ;# 
# 14988 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOSTA2 equ 016Ch ;# 
# 14995 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOSTA2L equ 016Ch ;# 
# 15057 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOSTA2H equ 016Dh ;# 
# 15109 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOSTA2U equ 016Eh ;# 
# 15116 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOSTA2T equ 016Fh ;# 
# 15123 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOUA2 equ 0170h ;# 
# 15130 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOUA2L equ 0170h ;# 
# 15200 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOUA2H equ 0171h ;# 
# 15270 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOUA2U equ 0172h ;# 
# 15340 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOUA2T equ 0173h ;# 
# 15410 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOCON3 equ 0174h ;# 
# 15417 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOCON3L equ 0174h ;# 
# 15479 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOCON3H equ 0175h ;# 
# 15511 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOCON3U equ 0176h ;# 
# 15581 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOCON3T equ 0177h ;# 
# 15657 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOSTA3 equ 0178h ;# 
# 15664 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOSTA3L equ 0178h ;# 
# 15726 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOSTA3H equ 0179h ;# 
# 15778 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOSTA3U equ 017Ah ;# 
# 15785 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOSTA3T equ 017Bh ;# 
# 15792 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOUA3 equ 017Ch ;# 
# 15799 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOUA3L equ 017Ch ;# 
# 15869 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOUA3H equ 017Dh ;# 
# 15939 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOUA3U equ 017Eh ;# 
# 16009 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FIFOUA3T equ 017Fh ;# 
# 16079 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTCON0L equ 0180h ;# 
# 16138 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTCON0H equ 0181h ;# 
# 16197 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTCON0U equ 0182h ;# 
# 16256 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTCON0T equ 0183h ;# 
# 16315 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTCON1L equ 0184h ;# 
# 16374 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTCON1H equ 0185h ;# 
# 16433 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTCON1U equ 0186h ;# 
# 16492 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTCON1T equ 0187h ;# 
# 16551 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTCON2L equ 0188h ;# 
# 16610 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTCON2H equ 0189h ;# 
# 16669 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTCON2U equ 018Ah ;# 
# 16728 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTCON2T equ 018Bh ;# 
# 16787 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ0 equ 018Ch ;# 
# 16794 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ0L equ 018Ch ;# 
# 16864 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ0H equ 018Dh ;# 
# 16940 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ0U equ 018Eh ;# 
# 17010 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ0T equ 018Fh ;# 
# 17074 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK0 equ 0190h ;# 
# 17081 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK0L equ 0190h ;# 
# 17151 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK0H equ 0191h ;# 
# 17227 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK0U equ 0192h ;# 
# 17297 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK0T equ 0193h ;# 
# 17361 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ1 equ 0194h ;# 
# 17368 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ1L equ 0194h ;# 
# 17438 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ1H equ 0195h ;# 
# 17514 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ1U equ 0196h ;# 
# 17584 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ1T equ 0197h ;# 
# 17648 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK1 equ 0198h ;# 
# 17655 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK1L equ 0198h ;# 
# 17725 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK1H equ 0199h ;# 
# 17801 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK1U equ 019Ah ;# 
# 17871 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK1T equ 019Bh ;# 
# 17935 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ2 equ 019Ch ;# 
# 17942 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ2L equ 019Ch ;# 
# 18012 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ2H equ 019Dh ;# 
# 18088 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ2U equ 019Eh ;# 
# 18158 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ2T equ 019Fh ;# 
# 18222 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK2 equ 01A0h ;# 
# 18229 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK2L equ 01A0h ;# 
# 18299 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK2H equ 01A1h ;# 
# 18375 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK2U equ 01A2h ;# 
# 18445 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK2T equ 01A3h ;# 
# 18509 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ3 equ 01A4h ;# 
# 18516 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ3L equ 01A4h ;# 
# 18586 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ3H equ 01A5h ;# 
# 18662 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ3U equ 01A6h ;# 
# 18732 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ3T equ 01A7h ;# 
# 18796 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK3 equ 01A8h ;# 
# 18803 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK3L equ 01A8h ;# 
# 18873 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK3H equ 01A9h ;# 
# 18949 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK3U equ 01AAh ;# 
# 19019 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK3T equ 01ABh ;# 
# 19083 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ4 equ 01ACh ;# 
# 19090 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ4L equ 01ACh ;# 
# 19160 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ4H equ 01ADh ;# 
# 19236 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ4U equ 01AEh ;# 
# 19306 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ4T equ 01AFh ;# 
# 19370 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK4 equ 01B0h ;# 
# 19377 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK4L equ 01B0h ;# 
# 19447 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK4H equ 01B1h ;# 
# 19523 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK4U equ 01B2h ;# 
# 19593 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK4T equ 01B3h ;# 
# 19657 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ5 equ 01B4h ;# 
# 19664 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ5L equ 01B4h ;# 
# 19734 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ5H equ 01B5h ;# 
# 19810 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ5U equ 01B6h ;# 
# 19880 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ5T equ 01B7h ;# 
# 19944 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK5 equ 01B8h ;# 
# 19951 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK5L equ 01B8h ;# 
# 20021 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK5H equ 01B9h ;# 
# 20097 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK5U equ 01BAh ;# 
# 20167 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK5T equ 01BBh ;# 
# 20231 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ6 equ 01BCh ;# 
# 20238 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ6L equ 01BCh ;# 
# 20308 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ6H equ 01BDh ;# 
# 20384 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ6U equ 01BEh ;# 
# 20454 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ6T equ 01BFh ;# 
# 20518 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK6 equ 01C0h ;# 
# 20525 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK6L equ 01C0h ;# 
# 20595 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK6H equ 01C1h ;# 
# 20671 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK6U equ 01C2h ;# 
# 20741 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK6T equ 01C3h ;# 
# 20805 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ7 equ 01C4h ;# 
# 20812 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ7L equ 01C4h ;# 
# 20882 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ7H equ 01C5h ;# 
# 20958 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ7U equ 01C6h ;# 
# 21028 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ7T equ 01C7h ;# 
# 21092 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK7 equ 01C8h ;# 
# 21099 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK7L equ 01C8h ;# 
# 21169 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK7H equ 01C9h ;# 
# 21245 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK7U equ 01CAh ;# 
# 21315 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK7T equ 01CBh ;# 
# 21379 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ8 equ 01CCh ;# 
# 21386 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ8L equ 01CCh ;# 
# 21456 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ8H equ 01CDh ;# 
# 21532 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ8U equ 01CEh ;# 
# 21602 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ8T equ 01CFh ;# 
# 21666 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK8 equ 01D0h ;# 
# 21673 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK8L equ 01D0h ;# 
# 21743 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK8H equ 01D1h ;# 
# 21819 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK8U equ 01D2h ;# 
# 21889 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK8T equ 01D3h ;# 
# 21953 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ9 equ 01D4h ;# 
# 21960 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ9L equ 01D4h ;# 
# 22030 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ9H equ 01D5h ;# 
# 22106 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ9U equ 01D6h ;# 
# 22176 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ9T equ 01D7h ;# 
# 22240 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK9 equ 01D8h ;# 
# 22247 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK9L equ 01D8h ;# 
# 22317 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK9H equ 01D9h ;# 
# 22393 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK9U equ 01DAh ;# 
# 22463 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK9T equ 01DBh ;# 
# 22527 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ10 equ 01DCh ;# 
# 22534 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ10L equ 01DCh ;# 
# 22604 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ10H equ 01DDh ;# 
# 22680 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ10U equ 01DEh ;# 
# 22750 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ10T equ 01DFh ;# 
# 22814 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK10 equ 01E0h ;# 
# 22821 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK10L equ 01E0h ;# 
# 22891 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK10H equ 01E1h ;# 
# 22967 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK10U equ 01E2h ;# 
# 23037 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK10T equ 01E3h ;# 
# 23101 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ11 equ 01E4h ;# 
# 23108 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ11L equ 01E4h ;# 
# 23178 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ11H equ 01E5h ;# 
# 23254 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ11U equ 01E6h ;# 
# 23324 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1FLTOBJ11T equ 01E7h ;# 
# 23388 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK11 equ 01E8h ;# 
# 23395 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK11L equ 01E8h ;# 
# 23465 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK11H equ 01E9h ;# 
# 23541 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK11U equ 01EAh ;# 
# 23611 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
C1MASK11T equ 01EBh ;# 
# 23675 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PPSLOCK equ 0200h ;# 
# 23695 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RA0PPS equ 0201h ;# 
# 23745 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RA1PPS equ 0202h ;# 
# 23795 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RA2PPS equ 0203h ;# 
# 23845 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RA3PPS equ 0204h ;# 
# 23895 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RA4PPS equ 0205h ;# 
# 23945 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RA5PPS equ 0206h ;# 
# 23995 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RA6PPS equ 0207h ;# 
# 24045 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RA7PPS equ 0208h ;# 
# 24095 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RB0PPS equ 0209h ;# 
# 24145 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RB1PPS equ 020Ah ;# 
# 24195 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RB2PPS equ 020Bh ;# 
# 24245 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RB3PPS equ 020Ch ;# 
# 24295 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RB4PPS equ 020Dh ;# 
# 24345 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RB5PPS equ 020Eh ;# 
# 24395 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RB6PPS equ 020Fh ;# 
# 24445 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RB7PPS equ 0210h ;# 
# 24495 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RC0PPS equ 0211h ;# 
# 24545 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RC1PPS equ 0212h ;# 
# 24595 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RC2PPS equ 0213h ;# 
# 24645 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RC3PPS equ 0214h ;# 
# 24695 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RC4PPS equ 0215h ;# 
# 24745 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RC5PPS equ 0216h ;# 
# 24795 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RC6PPS equ 0217h ;# 
# 24845 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RC7PPS equ 0218h ;# 
# 24895 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CANRXPPS equ 023Dh ;# 
# 24961 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
INT0PPS equ 023Eh ;# 
# 25021 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
INT1PPS equ 023Fh ;# 
# 25087 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
INT2PPS equ 0240h ;# 
# 25159 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T0CKIPPS equ 0241h ;# 
# 25231 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T1CKIPPS equ 0242h ;# 
# 25303 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T1GPPS equ 0243h ;# 
# 25369 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T3CKIPPS equ 0244h ;# 
# 25441 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T3GPPS equ 0245h ;# 
# 25507 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T5CKIPPS equ 0246h ;# 
# 25579 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T5GPPS equ 0247h ;# 
# 25645 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T2INPPS equ 0248h ;# 
# 25711 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T4INPPS equ 0249h ;# 
# 25777 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T6INPPS equ 024Ah ;# 
# 25843 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TUIN0PPS equ 024Bh ;# 
# 25915 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TUIN1PPS equ 024Ch ;# 
# 25987 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCP1PPS equ 024Fh ;# 
# 26059 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCP2PPS equ 0250h ;# 
# 26131 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCP3PPS equ 0251h ;# 
# 26197 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1ERSPPS equ 0253h ;# 
# 26263 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2ERSPPS equ 0254h ;# 
# 26335 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3ERSPPS equ 0255h ;# 
# 26401 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4ERSPPS equ 0256h ;# 
# 26408 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWMIN0PPS equ 0257h ;# 
# 26480 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWMIN1PPS equ 0258h ;# 
# 26552 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1WINPPS equ 0259h ;# 
# 26624 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1SIGPPS equ 025Ah ;# 
# 26696 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG1PPS equ 025Bh ;# 
# 26701 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG1INPPS equ 025Bh ;# 
# 26906 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG2PPS equ 025Ch ;# 
# 26911 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG2INPPS equ 025Ch ;# 
# 27116 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG3PPS equ 025Dh ;# 
# 27121 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG3INPPS equ 025Dh ;# 
# 27326 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
MD1CARLPPS equ 025Eh ;# 
# 27331 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
MDCARLPPS equ 025Eh ;# 
# 27456 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
MD1CARHPPS equ 025Fh ;# 
# 27461 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
MDCARHPPS equ 025Fh ;# 
# 27586 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
MD1SRCPPS equ 0260h ;# 
# 27591 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
MDSRCPPS equ 0260h ;# 
# 27716 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCIN0PPS equ 0261h ;# 
# 27782 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCIN1PPS equ 0262h ;# 
# 27848 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCIN2PPS equ 0263h ;# 
# 27914 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCIN3PPS equ 0264h ;# 
# 27980 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCIN4PPS equ 0265h ;# 
# 28046 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCIN5PPS equ 0266h ;# 
# 28112 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCIN6PPS equ 0267h ;# 
# 28178 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CLCIN7PPS equ 0268h ;# 
# 28244 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADACTPPS equ 0269h ;# 
# 28310 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1SCKPPS equ 026Ah ;# 
# 28376 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1SDIPPS equ 026Bh ;# 
# 28442 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI1SSPPS equ 026Ch ;# 
# 28508 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2SCKPPS equ 026Dh ;# 
# 28574 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2SDIPPS equ 026Eh ;# 
# 28640 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SPI2SSPPS equ 026Fh ;# 
# 28706 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1SDAPPS equ 0270h ;# 
# 28772 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1SCLPPS equ 0271h ;# 
# 28838 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1RXPPS equ 0272h ;# 
# 28910 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1CTSPPS equ 0273h ;# 
# 28982 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2RXPPS equ 0274h ;# 
# 29048 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2CTSPPS equ 0275h ;# 
# 29114 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3RXPPS equ 0276h ;# 
# 29186 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3CTSPPS equ 0277h ;# 
# 29258 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4RXPPS equ 0278h ;# 
# 29324 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4CTSPPS equ 0279h ;# 
# 29390 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5RXPPS equ 027Ah ;# 
# 29462 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5CTSPPS equ 027Bh ;# 
# 29534 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RC4I2C equ 0286h ;# 
# 29666 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RC3I2C equ 0287h ;# 
# 29798 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RB2I2C equ 0288h ;# 
# 29930 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
RB1I2C equ 0289h ;# 
# 30062 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1RXB equ 028Ah ;# 
# 30082 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1TXB equ 028Bh ;# 
# 30102 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1CNTL equ 028Ch ;# 
# 30172 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1CNTH equ 028Dh ;# 
# 30242 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1ADB0 equ 028Eh ;# 
# 30262 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1ADB1 equ 028Fh ;# 
# 30282 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1ADR0 equ 0290h ;# 
# 30302 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1ADR1 equ 0291h ;# 
# 30323 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1ADR2 equ 0292h ;# 
# 30343 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1ADR3 equ 0293h ;# 
# 30364 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1CON0 equ 0294h ;# 
# 30441 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1CON1 equ 0295h ;# 
# 30503 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1CON2 equ 0296h ;# 
# 30579 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1ERR equ 0297h ;# 
# 30669 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1STAT0 equ 0298h ;# 
# 30759 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1STAT1 equ 0299h ;# 
# 30806 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1PIR equ 029Ah ;# 
# 30908 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1PIE equ 029Bh ;# 
# 31010 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1BTO equ 029Ch ;# 
# 31080 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1BAUD equ 029Dh ;# 
# 31100 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1CLK equ 029Eh ;# 
# 31192 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
I2C1BTOC equ 029Fh ;# 
# 31272 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1RXB equ 02A1h ;# 
# 31277 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1RXBL equ 02A1h ;# 
# 31310 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1RXCHK equ 02A2h ;# 
# 31330 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1TXB equ 02A3h ;# 
# 31335 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1TXBL equ 02A3h ;# 
# 31368 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1TXCHK equ 02A4h ;# 
# 31388 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1P1 equ 02A5h ;# 
# 31395 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1P1L equ 02A5h ;# 
# 31415 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1P1H equ 02A6h ;# 
# 31435 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1P2 equ 02A7h ;# 
# 31442 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1P2L equ 02A7h ;# 
# 31462 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1P2H equ 02A8h ;# 
# 31482 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1P3 equ 02A9h ;# 
# 31489 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1P3L equ 02A9h ;# 
# 31509 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1P3H equ 02AAh ;# 
# 31529 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1CON0 equ 02ABh ;# 
# 31657 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1CON1 equ 02ACh ;# 
# 31737 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1CON2 equ 02ADh ;# 
# 31879 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1BRG equ 02AEh ;# 
# 31886 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1BRGL equ 02AEh ;# 
# 31906 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1BRGH equ 02AFh ;# 
# 31926 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1FIFO equ 02B0h ;# 
# 32056 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1UIR equ 02B1h ;# 
# 32112 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1ERRIR equ 02B2h ;# 
# 32224 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U1ERRIE equ 02B3h ;# 
# 32336 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2RXB equ 02B4h ;# 
# 32341 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2RXBL equ 02B4h ;# 
# 32374 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2RXCHK equ 02B5h ;# 
# 32394 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2TXB equ 02B6h ;# 
# 32399 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2TXBL equ 02B6h ;# 
# 32432 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2TXCHK equ 02B7h ;# 
# 32452 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2P1 equ 02B8h ;# 
# 32459 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2P1L equ 02B8h ;# 
# 32479 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2P1H equ 02B9h ;# 
# 32499 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2P2 equ 02BAh ;# 
# 32506 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2P2L equ 02BAh ;# 
# 32526 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2P2H equ 02BBh ;# 
# 32546 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2P3 equ 02BCh ;# 
# 32553 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2P3L equ 02BCh ;# 
# 32573 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2P3H equ 02BDh ;# 
# 32593 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2CON0 equ 02BEh ;# 
# 32721 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2CON1 equ 02BFh ;# 
# 32801 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2CON2 equ 02C0h ;# 
# 32943 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2BRG equ 02C1h ;# 
# 32950 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2BRGL equ 02C1h ;# 
# 32970 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2BRGH equ 02C2h ;# 
# 32990 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2FIFO equ 02C3h ;# 
# 33120 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2UIR equ 02C4h ;# 
# 33176 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2ERRIR equ 02C5h ;# 
# 33288 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U2ERRIE equ 02C6h ;# 
# 33400 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3RXB equ 02C7h ;# 
# 33405 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3RXBL equ 02C7h ;# 
# 33438 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3TXB equ 02C9h ;# 
# 33443 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3TXBL equ 02C9h ;# 
# 33476 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3P1 equ 02CBh ;# 
# 33483 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3P1L equ 02CBh ;# 
# 33503 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3P2 equ 02CDh ;# 
# 33510 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3P2L equ 02CDh ;# 
# 33530 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3P3 equ 02CFh ;# 
# 33537 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3P3L equ 02CFh ;# 
# 33557 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3CON0 equ 02D1h ;# 
# 33673 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3CON1 equ 02D2h ;# 
# 33753 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3CON2 equ 02D3h ;# 
# 33885 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3BRG equ 02D4h ;# 
# 33892 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3BRGL equ 02D4h ;# 
# 33912 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3BRGH equ 02D5h ;# 
# 33932 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3FIFO equ 02D6h ;# 
# 34062 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3UIR equ 02D7h ;# 
# 34118 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3ERRIR equ 02D8h ;# 
# 34230 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U3ERRIE equ 02D9h ;# 
# 34342 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4RXB equ 02DAh ;# 
# 34347 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4RXBL equ 02DAh ;# 
# 34380 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4TXB equ 02DCh ;# 
# 34385 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4TXBL equ 02DCh ;# 
# 34418 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4P1 equ 02DEh ;# 
# 34425 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4P1L equ 02DEh ;# 
# 34445 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4P2 equ 02E0h ;# 
# 34452 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4P2L equ 02E0h ;# 
# 34472 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4P3 equ 02E2h ;# 
# 34479 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4P3L equ 02E2h ;# 
# 34499 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4CON0 equ 02E4h ;# 
# 34615 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4CON1 equ 02E5h ;# 
# 34695 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4CON2 equ 02E6h ;# 
# 34827 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4BRG equ 02E7h ;# 
# 34834 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4BRGL equ 02E7h ;# 
# 34854 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4BRGH equ 02E8h ;# 
# 34874 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4FIFO equ 02E9h ;# 
# 35004 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4UIR equ 02EAh ;# 
# 35060 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4ERRIR equ 02EBh ;# 
# 35172 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U4ERRIE equ 02ECh ;# 
# 35284 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5RXB equ 02EDh ;# 
# 35289 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5RXBL equ 02EDh ;# 
# 35322 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5TXB equ 02EFh ;# 
# 35327 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5TXBL equ 02EFh ;# 
# 35360 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5P1 equ 02F1h ;# 
# 35367 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5P1L equ 02F1h ;# 
# 35387 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5P2 equ 02F3h ;# 
# 35394 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5P2L equ 02F3h ;# 
# 35414 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5P3 equ 02F5h ;# 
# 35421 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5P3L equ 02F5h ;# 
# 35441 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5CON0 equ 02F7h ;# 
# 35557 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5CON1 equ 02F8h ;# 
# 35637 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5CON2 equ 02F9h ;# 
# 35769 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5BRG equ 02FAh ;# 
# 35776 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5BRGL equ 02FAh ;# 
# 35796 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5BRGH equ 02FBh ;# 
# 35816 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5FIFO equ 02FCh ;# 
# 35946 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5UIR equ 02FDh ;# 
# 36002 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5ERRIR equ 02FEh ;# 
# 36114 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
U5ERRIE equ 02FFh ;# 
# 36228 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1TMR equ 0300h ;# 
# 36235 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1TMRL equ 0300h ;# 
# 36363 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1TMRH equ 0301h ;# 
# 36491 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1TMRU equ 0302h ;# 
# 36621 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1CPR equ 0303h ;# 
# 36628 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1CPRL equ 0303h ;# 
# 36756 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1CPRH equ 0304h ;# 
# 36884 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1CPRU equ 0305h ;# 
# 37014 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1CPW equ 0306h ;# 
# 37021 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1CPWL equ 0306h ;# 
# 37149 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1CPWH equ 0307h ;# 
# 37277 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1CPWU equ 0308h ;# 
# 37407 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1PR equ 0309h ;# 
# 37414 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1PRL equ 0309h ;# 
# 37542 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1PRH equ 030Ah ;# 
# 37670 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1PRU equ 030Bh ;# 
# 37798 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1CON0 equ 030Ch ;# 
# 37916 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1CON1 equ 030Dh ;# 
# 37996 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1STAT equ 030Eh ;# 
# 38095 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1CLK equ 030Fh ;# 
# 38163 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1SIG equ 0310h ;# 
# 38255 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SMT1WIN equ 0311h ;# 
# 38347 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR0L equ 0318h ;# 
# 38352 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR0 equ 0318h ;# 
# 38485 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR0H equ 0319h ;# 
# 38490 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PR0 equ 0319h ;# 
# 38739 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T0CON0 equ 031Ah ;# 
# 38863 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T0CON1 equ 031Bh ;# 
# 39005 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR1 equ 031Ch ;# 
# 39012 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR1L equ 031Ch ;# 
# 39132 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR1H equ 031Dh ;# 
# 39252 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T1CON equ 031Eh ;# 
# 39257 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR1CON equ 031Eh ;# 
# 39474 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T1GCON equ 031Fh ;# 
# 39479 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR1GCON equ 031Fh ;# 
# 39760 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T1GATE equ 0320h ;# 
# 39765 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR1GATE equ 0320h ;# 
# 39926 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T1CLK equ 0321h ;# 
# 39931 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR1CLK equ 0321h ;# 
# 39935 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PR1 equ 0321h ;# 
# 40172 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T2TMR equ 0322h ;# 
# 40177 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR2 equ 0322h ;# 
# 40210 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T2PR equ 0323h ;# 
# 40215 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PR2 equ 0323h ;# 
# 40248 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T2CON equ 0324h ;# 
# 40394 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T2HLT equ 0325h ;# 
# 40522 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T2CLKCON equ 0326h ;# 
# 40527 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T2CLK equ 0326h ;# 
# 40680 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T2RST equ 0327h ;# 
# 40772 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR3 equ 0328h ;# 
# 40779 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR3L equ 0328h ;# 
# 40899 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR3H equ 0329h ;# 
# 41019 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T3CON equ 032Ah ;# 
# 41024 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR3CON equ 032Ah ;# 
# 41241 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T3GCON equ 032Bh ;# 
# 41246 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR3GCON equ 032Bh ;# 
# 41527 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T3GATE equ 032Ch ;# 
# 41532 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR3GATE equ 032Ch ;# 
# 41693 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T3CLK equ 032Dh ;# 
# 41698 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR3CLK equ 032Dh ;# 
# 41702 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PR3 equ 032Dh ;# 
# 41939 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T4TMR equ 032Eh ;# 
# 41944 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR4 equ 032Eh ;# 
# 41977 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T4PR equ 032Fh ;# 
# 41982 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PR4 equ 032Fh ;# 
# 42015 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T4CON equ 0330h ;# 
# 42161 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T4HLT equ 0331h ;# 
# 42289 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T4CLKCON equ 0332h ;# 
# 42294 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T4CLK equ 0332h ;# 
# 42447 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T4RST equ 0333h ;# 
# 42539 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR5 equ 0334h ;# 
# 42546 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR5L equ 0334h ;# 
# 42666 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR5H equ 0335h ;# 
# 42786 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T5CON equ 0336h ;# 
# 42791 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR5CON equ 0336h ;# 
# 43008 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T5GCON equ 0337h ;# 
# 43013 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR5GCON equ 0337h ;# 
# 43294 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T5GATE equ 0338h ;# 
# 43299 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR5GATE equ 0338h ;# 
# 43460 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T5CLK equ 0339h ;# 
# 43465 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR5CLK equ 0339h ;# 
# 43469 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PR5 equ 0339h ;# 
# 43706 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T6TMR equ 033Ah ;# 
# 43711 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TMR6 equ 033Ah ;# 
# 43744 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T6PR equ 033Bh ;# 
# 43749 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PR6 equ 033Bh ;# 
# 43782 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T6CON equ 033Ch ;# 
# 43928 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T6HLT equ 033Dh ;# 
# 44056 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T6CLKCON equ 033Eh ;# 
# 44061 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T6CLK equ 033Eh ;# 
# 44214 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
T6RST equ 033Fh ;# 
# 44306 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCPR1 equ 0340h ;# 
# 44313 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCPR1L equ 0340h ;# 
# 44333 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCPR1H equ 0341h ;# 
# 44353 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCP1CON equ 0342h ;# 
# 44471 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCP1CAP equ 0343h ;# 
# 44551 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCPR2 equ 0344h ;# 
# 44558 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCPR2L equ 0344h ;# 
# 44578 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCPR2H equ 0345h ;# 
# 44598 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCP2CON equ 0346h ;# 
# 44716 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCP2CAP equ 0347h ;# 
# 44796 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCPR3 equ 0348h ;# 
# 44803 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCPR3L equ 0348h ;# 
# 44823 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCPR3H equ 0349h ;# 
# 44843 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCP3CON equ 034Ah ;# 
# 44961 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCP3CAP equ 034Bh ;# 
# 45041 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CCPTMRS0 equ 034Ch ;# 
# 45111 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCDATA equ 034Fh ;# 
# 45118 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCDATAL equ 034Fh ;# 
# 45188 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCDATAH equ 0350h ;# 
# 45258 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCDATAU equ 0351h ;# 
# 45328 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCDATAT equ 0352h ;# 
# 45398 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCOUT equ 0353h ;# 
# 45403 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCSHFT equ 0353h ;# 
# 45407 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCXOR equ 0353h ;# 
# 45414 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCOUTL equ 0353h ;# 
# 45484 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCSHFTL equ 0353h ;# 
# 45489 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCSHIFTL equ 0353h ;# 
# 45622 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCXORL equ 0353h ;# 
# 45692 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCOUTH equ 0354h ;# 
# 45762 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCSHFTH equ 0354h ;# 
# 45767 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCSHIFTH equ 0354h ;# 
# 45900 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCXORH equ 0354h ;# 
# 45970 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCOUTU equ 0355h ;# 
# 46040 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCSHFTU equ 0355h ;# 
# 46045 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCSHIFTU equ 0355h ;# 
# 46178 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCXORU equ 0355h ;# 
# 46248 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCOUTT equ 0356h ;# 
# 46318 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCSHFTT equ 0356h ;# 
# 46323 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCSHIFTT equ 0356h ;# 
# 46456 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCXORT equ 0356h ;# 
# 46526 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCCON0 equ 0357h ;# 
# 46627 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCCON1 equ 0358h ;# 
# 46679 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CRCCON2 equ 0359h ;# 
# 46733 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SCANLADR equ 035Ah ;# 
# 46740 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SCANLADRL equ 035Ah ;# 
# 46868 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SCANLADRH equ 035Bh ;# 
# 46996 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SCANLADRU equ 035Ch ;# 
# 47102 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SCANHADR equ 035Dh ;# 
# 47109 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SCANHADRL equ 035Dh ;# 
# 47237 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SCANHADRH equ 035Eh ;# 
# 47365 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SCANHADRU equ 035Fh ;# 
# 47469 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SCANCON0 equ 0360h ;# 
# 47529 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SCANTRIG equ 0361h ;# 
# 47589 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR0 equ 0362h ;# 
# 47651 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR1 equ 0363h ;# 
# 47713 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR2 equ 0364h ;# 
# 47783 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR3 equ 0365h ;# 
# 47845 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR4 equ 0366h ;# 
# 47907 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR5 equ 0367h ;# 
# 47969 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR6 equ 0368h ;# 
# 48031 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR7 equ 0369h ;# 
# 48088 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR8 equ 036Ah ;# 
# 48150 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR9 equ 036Bh ;# 
# 48207 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR10 equ 036Ch ;# 
# 48269 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR11 equ 036Dh ;# 
# 48331 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR12 equ 036Eh ;# 
# 48393 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR13 equ 036Fh ;# 
# 48455 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR14 equ 0370h ;# 
# 48512 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IPR15 equ 0371h ;# 
# 48574 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
STATUS_CSHAD equ 0373h ;# 
# 48663 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
WREG_CSHAD equ 0374h ;# 
# 48683 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
BSR_CSHAD equ 0375h ;# 
# 48690 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SHADCON equ 0376h ;# 
# 48710 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
STATUS_SHAD equ 0377h ;# 
# 48799 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
WREG_SHAD equ 0378h ;# 
# 48819 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
BSR_SHAD equ 0379h ;# 
# 48826 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PCLATH_SHAD equ 037Ah ;# 
# 48846 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PCLATU_SHAD equ 037Bh ;# 
# 48866 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR0SH equ 037Ch ;# 
# 48873 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR0L_SHAD equ 037Ch ;# 
# 48893 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR0H_SHAD equ 037Dh ;# 
# 48913 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR1SH equ 037Eh ;# 
# 48920 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR1L_SHAD equ 037Eh ;# 
# 48940 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR1H_SHAD equ 037Fh ;# 
# 48960 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR2SH equ 0380h ;# 
# 48967 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR2L_SHAD equ 0380h ;# 
# 48987 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR2H_SHAD equ 0381h ;# 
# 49007 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PRODSH equ 0382h ;# 
# 49014 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PRODL_SHAD equ 0382h ;# 
# 49034 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PRODH_SHAD equ 0383h ;# 
# 49054 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16ACON0 equ 0387h ;# 
# 49166 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16ACON1 equ 0388h ;# 
# 49278 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16AHLT equ 0389h ;# 
# 49430 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16APS equ 038Ah ;# 
# 49558 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16ATMR equ 038Bh ;# 
# 49563 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16ACR equ 038Bh ;# 
# 49570 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16ATMRL equ 038Bh ;# 
# 49740 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16ACRL equ 038Bh ;# 
# 49910 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16ATMRH equ 038Ch ;# 
# 50080 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16ACRH equ 038Ch ;# 
# 50250 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16APR equ 038Dh ;# 
# 50257 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16APRL equ 038Dh ;# 
# 50427 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16APRH equ 038Eh ;# 
# 50597 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16ACLK equ 038Fh ;# 
# 50681 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16AERS equ 0390h ;# 
# 50777 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16BCON0 equ 0393h ;# 
# 50889 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16BCON1 equ 0394h ;# 
# 51001 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16BHLT equ 0395h ;# 
# 51153 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16BPS equ 0396h ;# 
# 51281 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16BTMR equ 0397h ;# 
# 51286 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16BCR equ 0397h ;# 
# 51293 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16BTMRL equ 0397h ;# 
# 51463 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16BCRL equ 0397h ;# 
# 51633 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16BTMRH equ 0398h ;# 
# 51803 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16BCRH equ 0398h ;# 
# 51973 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16BPR equ 0399h ;# 
# 51980 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16BPRL equ 0399h ;# 
# 52150 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16BPRH equ 039Ah ;# 
# 52320 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16BCLK equ 039Bh ;# 
# 52404 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TU16BERS equ 039Ch ;# 
# 52500 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TUCHAIN equ 03BBh ;# 
# 52520 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG1CLK equ 03BCh ;# 
# 52525 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG1CLKCON equ 03BCh ;# 
# 52574 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG1ISM equ 03BDh ;# 
# 52626 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG1DBR equ 03BEh ;# 
# 52730 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG1DBF equ 03BFh ;# 
# 52834 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG1CON0 equ 03C0h ;# 
# 52935 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG1CON1 equ 03C1h ;# 
# 53013 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG1AS0 equ 03C2h ;# 
# 53133 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG1AS1 equ 03C3h ;# 
# 53195 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG1STR equ 03C4h ;# 
# 53307 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG2CLK equ 03C5h ;# 
# 53312 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG2CLKCON equ 03C5h ;# 
# 53361 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG2ISM equ 03C6h ;# 
# 53413 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG2DBR equ 03C7h ;# 
# 53517 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG2DBF equ 03C8h ;# 
# 53621 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG2CON0 equ 03C9h ;# 
# 53722 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG2CON1 equ 03CAh ;# 
# 53800 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG2AS0 equ 03CBh ;# 
# 53920 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG2AS1 equ 03CCh ;# 
# 53982 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG2STR equ 03CDh ;# 
# 54094 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG3CLK equ 03CEh ;# 
# 54099 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG3CLKCON equ 03CEh ;# 
# 54148 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG3ISM equ 03CFh ;# 
# 54200 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG3DBR equ 03D0h ;# 
# 54304 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG3DBF equ 03D1h ;# 
# 54408 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG3CON0 equ 03D2h ;# 
# 54509 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG3CON1 equ 03D3h ;# 
# 54587 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG3AS0 equ 03D4h ;# 
# 54707 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG3AS1 equ 03D5h ;# 
# 54769 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CWG3STR equ 03D6h ;# 
# 54881 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FVRCON equ 03D7h ;# 
# 54970 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADCPCON equ 03D8h ;# 
# 54975 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADCP equ 03D8h ;# 
# 55070 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADLTH equ 03D9h ;# 
# 55077 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADLTHL equ 03D9h ;# 
# 55205 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADLTHH equ 03DAh ;# 
# 55333 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADUTH equ 03DBh ;# 
# 55340 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADUTHL equ 03DBh ;# 
# 55468 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADUTHH equ 03DCh ;# 
# 55596 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADERR equ 03DDh ;# 
# 55603 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADERRL equ 03DDh ;# 
# 55731 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADERRH equ 03DEh ;# 
# 55859 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADSTPT equ 03DFh ;# 
# 55866 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADSTPTL equ 03DFh ;# 
# 55994 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADSTPTH equ 03E0h ;# 
# 56122 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADFLTR equ 03E1h ;# 
# 56129 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADFLTRL equ 03E1h ;# 
# 56257 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADFLTRH equ 03E2h ;# 
# 56387 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADACC equ 03E3h ;# 
# 56394 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADACCL equ 03E3h ;# 
# 56522 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADACCH equ 03E4h ;# 
# 56650 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADACCU equ 03E5h ;# 
# 56706 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADCNT equ 03E6h ;# 
# 56834 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADRPT equ 03E7h ;# 
# 56962 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADPREV equ 03E8h ;# 
# 56969 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADPREVL equ 03E8h ;# 
# 57097 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADPREVH equ 03E9h ;# 
# 57225 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADRES equ 03EAh ;# 
# 57232 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADRESL equ 03EAh ;# 
# 57360 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADRESH equ 03EBh ;# 
# 57480 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADPCH equ 03ECh ;# 
# 57538 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADACQ equ 03EEh ;# 
# 57545 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADACQL equ 03EEh ;# 
# 57673 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADACQH equ 03EFh ;# 
# 57765 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADCAP equ 03F0h ;# 
# 57817 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADPRE equ 03F1h ;# 
# 57824 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADPREL equ 03F1h ;# 
# 57952 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADPREH equ 03F2h ;# 
# 58044 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADCON0 equ 03F3h ;# 
# 58172 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADCON1 equ 03F4h ;# 
# 58238 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADCON2 equ 03F5h ;# 
# 58416 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADCON3 equ 03F6h ;# 
# 58546 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADSTAT equ 03F7h ;# 
# 58671 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADREF equ 03F8h ;# 
# 58753 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADACT equ 03F9h ;# 
# 58857 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADCLK equ 03FAh ;# 
# 58961 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADCTX equ 03FBh ;# 
# 59031 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADCSEL1 equ 03FCh ;# 
# 59058 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADCSEL2 equ 03FDh ;# 
# 59085 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADCSEL3 equ 03FEh ;# 
# 59112 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ADCSEL4 equ 03FFh ;# 
# 59139 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ANSELA equ 0400h ;# 
# 59201 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
WPUA equ 0401h ;# 
# 59263 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ODCONA equ 0402h ;# 
# 59325 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SLRCONA equ 0403h ;# 
# 59387 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
INLVLA equ 0404h ;# 
# 59449 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IOCAP equ 0405h ;# 
# 59511 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IOCAN equ 0406h ;# 
# 59573 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IOCAF equ 0407h ;# 
# 59635 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ANSELB equ 0408h ;# 
# 59697 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
WPUB equ 0409h ;# 
# 59759 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ODCONB equ 040Ah ;# 
# 59821 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SLRCONB equ 040Bh ;# 
# 59883 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
INLVLB equ 040Ch ;# 
# 59945 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IOCBP equ 040Dh ;# 
# 60007 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IOCBN equ 040Eh ;# 
# 60069 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IOCBF equ 040Fh ;# 
# 60131 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ANSELC equ 0410h ;# 
# 60193 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
WPUC equ 0411h ;# 
# 60255 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
ODCONC equ 0412h ;# 
# 60317 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
SLRCONC equ 0413h ;# 
# 60379 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
INLVLC equ 0414h ;# 
# 60441 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IOCCP equ 0415h ;# 
# 60503 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IOCCN equ 0416h ;# 
# 60565 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IOCCF equ 0417h ;# 
# 60627 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
WPUE equ 0421h ;# 
# 60648 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
INLVLE equ 0424h ;# 
# 60669 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IOCEP equ 0425h ;# 
# 60690 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IOCEN equ 0426h ;# 
# 60711 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IOCEF equ 0427h ;# 
# 60734 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO1ACC equ 0440h ;# 
# 60741 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO1ACCL equ 0440h ;# 
# 60869 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO1ACCH equ 0441h ;# 
# 60997 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO1ACCU equ 0442h ;# 
# 61079 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO1INC equ 0443h ;# 
# 61086 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO1INCL equ 0443h ;# 
# 61214 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO1INCH equ 0444h ;# 
# 61342 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO1INCU equ 0445h ;# 
# 61422 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO1CON equ 0446h ;# 
# 61490 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO1CLK equ 0447h ;# 
# 61624 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO2ACC equ 0448h ;# 
# 61631 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO2ACCL equ 0448h ;# 
# 61759 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO2ACCH equ 0449h ;# 
# 61887 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO2ACCU equ 044Ah ;# 
# 61969 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO2INC equ 044Bh ;# 
# 61976 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO2INCL equ 044Bh ;# 
# 62104 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO2INCH equ 044Ch ;# 
# 62232 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO2INCU equ 044Dh ;# 
# 62312 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO2CON equ 044Eh ;# 
# 62380 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO2CLK equ 044Fh ;# 
# 62514 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO3ACC equ 0450h ;# 
# 62521 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO3ACCL equ 0450h ;# 
# 62649 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO3ACCH equ 0451h ;# 
# 62777 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO3ACCU equ 0452h ;# 
# 62859 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO3INC equ 0453h ;# 
# 62866 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO3INCL equ 0453h ;# 
# 62994 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO3INCH equ 0454h ;# 
# 63122 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO3INCU equ 0455h ;# 
# 63202 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO3CON equ 0456h ;# 
# 63270 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
NCO3CLK equ 0457h ;# 
# 63402 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSCMCON equ 0458h ;# 
# 63452 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IVTLOCK equ 0459h ;# 
# 63474 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IVTAD equ 045Ah ;# 
# 63481 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IVTADL equ 045Ah ;# 
# 63543 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IVTADH equ 045Bh ;# 
# 63605 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IVTADU equ 045Ch ;# 
# 63651 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IVTBASE equ 045Dh ;# 
# 63658 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IVTBASEL equ 045Dh ;# 
# 63720 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IVTBASEH equ 045Eh ;# 
# 63782 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
IVTBASEU equ 045Fh ;# 
# 63826 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1ERS equ 0460h ;# 
# 63896 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1CLK equ 0461h ;# 
# 63966 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1LDS equ 0462h ;# 
# 64036 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1PR equ 0463h ;# 
# 64043 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1PRL equ 0463h ;# 
# 64063 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1PRH equ 0464h ;# 
# 64083 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1CPRE equ 0465h ;# 
# 64103 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1PIPOS equ 0466h ;# 
# 64123 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1GIR equ 0467h ;# 
# 64149 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1GIE equ 0468h ;# 
# 64175 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1CON equ 0469h ;# 
# 64214 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1S1CFG equ 046Ah ;# 
# 64273 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1S1P1 equ 046Bh ;# 
# 64280 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1S1P1L equ 046Bh ;# 
# 64300 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1S1P1H equ 046Ch ;# 
# 64320 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1S1P2 equ 046Dh ;# 
# 64327 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1S1P2L equ 046Dh ;# 
# 64347 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM1S1P2H equ 046Eh ;# 
# 64367 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2ERS equ 046Fh ;# 
# 64437 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2CLK equ 0470h ;# 
# 64507 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2LDS equ 0471h ;# 
# 64577 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2PR equ 0472h ;# 
# 64584 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2PRL equ 0472h ;# 
# 64604 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2PRH equ 0473h ;# 
# 64624 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2CPRE equ 0474h ;# 
# 64644 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2PIPOS equ 0475h ;# 
# 64664 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2GIR equ 0476h ;# 
# 64690 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2GIE equ 0477h ;# 
# 64716 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2CON equ 0478h ;# 
# 64755 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2S1CFG equ 0479h ;# 
# 64814 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2S1P1 equ 047Ah ;# 
# 64821 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2S1P1L equ 047Ah ;# 
# 64841 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2S1P1H equ 047Bh ;# 
# 64861 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2S1P2 equ 047Ch ;# 
# 64868 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2S1P2L equ 047Ch ;# 
# 64888 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM2S1P2H equ 047Dh ;# 
# 64908 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3ERS equ 047Eh ;# 
# 64978 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3CLK equ 047Fh ;# 
# 65048 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3LDS equ 0480h ;# 
# 65118 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3PR equ 0481h ;# 
# 65125 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3PRL equ 0481h ;# 
# 65145 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3PRH equ 0482h ;# 
# 65165 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3CPRE equ 0483h ;# 
# 65185 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3PIPOS equ 0484h ;# 
# 65205 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3GIR equ 0485h ;# 
# 65231 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3GIE equ 0486h ;# 
# 65257 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3CON equ 0487h ;# 
# 65296 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3S1CFG equ 0488h ;# 
# 65355 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3S1P1 equ 0489h ;# 
# 65362 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3S1P1L equ 0489h ;# 
# 65382 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3S1P1H equ 048Ah ;# 
# 65402 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3S1P2 equ 048Bh ;# 
# 65409 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3S1P2L equ 048Bh ;# 
# 65429 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM3S1P2H equ 048Ch ;# 
# 65449 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4ERS equ 048Dh ;# 
# 65519 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4CLK equ 048Eh ;# 
# 65589 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4LDS equ 048Fh ;# 
# 65659 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4PR equ 0490h ;# 
# 65666 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4PRL equ 0490h ;# 
# 65686 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4PRH equ 0491h ;# 
# 65706 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4CPRE equ 0492h ;# 
# 65726 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4PIPOS equ 0493h ;# 
# 65746 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4GIR equ 0494h ;# 
# 65772 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4GIE equ 0495h ;# 
# 65798 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4CON equ 0496h ;# 
# 65837 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4S1CFG equ 0497h ;# 
# 65896 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4S1P1 equ 0498h ;# 
# 65903 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4S1P1L equ 0498h ;# 
# 65923 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4S1P1H equ 0499h ;# 
# 65943 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4S1P2 equ 049Ah ;# 
# 65950 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4S1P2L equ 049Ah ;# 
# 65970 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWM4S1P2H equ 049Bh ;# 
# 65990 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWMLOAD equ 049Ch ;# 
# 66028 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PWMEN equ 049Dh ;# 
# 66066 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE0 equ 049Eh ;# 
# 66128 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE1 equ 049Fh ;# 
# 66190 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE2 equ 04A0h ;# 
# 66260 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE3 equ 04A1h ;# 
# 66322 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE4 equ 04A2h ;# 
# 66384 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE5 equ 04A3h ;# 
# 66446 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE6 equ 04A4h ;# 
# 66508 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE7 equ 04A5h ;# 
# 66565 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE8 equ 04A6h ;# 
# 66627 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE9 equ 04A7h ;# 
# 66684 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE10 equ 04A8h ;# 
# 66746 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE11 equ 04A9h ;# 
# 66808 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE12 equ 04AAh ;# 
# 66870 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE13 equ 04ABh ;# 
# 66932 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE14 equ 04ACh ;# 
# 66989 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIE15 equ 04ADh ;# 
# 67051 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR0 equ 04AEh ;# 
# 67113 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR1 equ 04AFh ;# 
# 67175 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR2 equ 04B0h ;# 
# 67245 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR3 equ 04B1h ;# 
# 67307 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR4 equ 04B2h ;# 
# 67369 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR5 equ 04B3h ;# 
# 67431 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR6 equ 04B4h ;# 
# 67493 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR7 equ 04B5h ;# 
# 67550 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR8 equ 04B6h ;# 
# 67612 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR9 equ 04B7h ;# 
# 67669 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR10 equ 04B8h ;# 
# 67731 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR11 equ 04B9h ;# 
# 67793 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR12 equ 04BAh ;# 
# 67855 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR13 equ 04BBh ;# 
# 67917 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR14 equ 04BCh ;# 
# 67974 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PIR15 equ 04BDh ;# 
# 68036 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
LATA equ 04BEh ;# 
# 68098 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
LATB equ 04BFh ;# 
# 68160 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
LATC equ 04C0h ;# 
# 68222 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TRISA equ 04C6h ;# 
# 68284 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TRISB equ 04C7h ;# 
# 68346 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TRISC equ 04C8h ;# 
# 68408 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TRISE equ 04CAh ;# 
# 68429 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PORTA equ 04CEh ;# 
# 68491 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PORTB equ 04CFh ;# 
# 68553 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PORTC equ 04D0h ;# 
# 68615 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PORTE equ 04D2h ;# 
# 68636 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
INTCON0 equ 04D6h ;# 
# 68696 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
INTCON1 equ 04D7h ;# 
# 68732 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
STATUS equ 04D8h ;# 
# 68821 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR2 equ 04D9h ;# 
# 68828 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR2L equ 04D9h ;# 
# 68848 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR2H equ 04DAh ;# 
# 68855 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PLUSW2 equ 04DBh ;# 
# 68875 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PREINC2 equ 04DCh ;# 
# 68895 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
POSTDEC2 equ 04DDh ;# 
# 68915 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
POSTINC2 equ 04DEh ;# 
# 68935 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
INDF2 equ 04DFh ;# 
# 68955 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
BSR equ 04E0h ;# 
# 68962 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR1 equ 04E1h ;# 
# 68969 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR1L equ 04E1h ;# 
# 68989 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR1H equ 04E2h ;# 
# 68996 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PLUSW1 equ 04E3h ;# 
# 69016 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PREINC1 equ 04E4h ;# 
# 69036 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
POSTDEC1 equ 04E5h ;# 
# 69056 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
POSTINC1 equ 04E6h ;# 
# 69076 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
INDF1 equ 04E7h ;# 
# 69096 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
WREG equ 04E8h ;# 
# 69134 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR0 equ 04E9h ;# 
# 69141 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR0L equ 04E9h ;# 
# 69161 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
FSR0H equ 04EAh ;# 
# 69168 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PLUSW0 equ 04EBh ;# 
# 69188 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PREINC0 equ 04ECh ;# 
# 69208 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
POSTDEC0 equ 04EDh ;# 
# 69228 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
POSTINC0 equ 04EEh ;# 
# 69248 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
INDF0 equ 04EFh ;# 
# 69268 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PCON0 equ 04F0h ;# 
# 69421 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PCON1 equ 04F1h ;# 
# 69460 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
CPUDOZE equ 04F2h ;# 
# 69525 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PROD equ 04F3h ;# 
# 69532 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PRODL equ 04F3h ;# 
# 69552 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PRODH equ 04F4h ;# 
# 69572 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TABLAT equ 04F5h ;# 
# 69594 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TBLPTR equ 04F6h ;# 
# 69601 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TBLPTRL equ 04F6h ;# 
# 69621 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TBLPTRH equ 04F7h ;# 
# 69641 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TBLPTRU equ 04F8h ;# 
# 69672 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PCLAT equ 04F9h ;# 
# 69679 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PCL equ 04F9h ;# 
# 69699 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PCLATH equ 04FAh ;# 
# 69719 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
PCLATU equ 04FBh ;# 
# 69739 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
STKPTR equ 04FCh ;# 
# 69849 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TOS equ 04FDh ;# 
# 69856 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TOSL equ 04FDh ;# 
# 69876 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TOSH equ 04FEh ;# 
# 69896 "C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8\pic\include\proc/pic18f26q84.h"
TOSU equ 04FFh ;# 
	debug_source C
	FNCALL	_main,_adc_init
	FNCALL	_main,_adc_read_average
	FNCALL	_main,_can_init
	FNCALL	_main,_can_send_voltages
	FNCALL	_main,_report_can_diagnostics
	FNCALL	_main,_report_voltage
	FNCALL	_main,_uart_init
	FNCALL	_main,_uart_puts
	FNCALL	_report_voltage,_nominal_millivolts
	FNCALL	_report_voltage,_uart_put_uint32
	FNCALL	_report_voltage,_uart_puts
	FNCALL	_nominal_millivolts,___lldiv
	FNCALL	_nominal_millivolts,___lmul
	FNCALL	_report_can_diagnostics,_uart_put_uint32
	FNCALL	_report_can_diagnostics,_uart_puts
	FNCALL	_uart_put_uint32,___lldiv
	FNCALL	_uart_put_uint32,___llmod
	FNCALL	_can_send_voltages,_rail_flags
	FNROOT	_main
	global	_PMD3bits
_PMD3bits	set	0x63
	global	_PMD2bits
_PMD2bits	set	0x62
	global	_PMD6bits
_PMD6bits	set	0x66
	global	_C1TXQUA
_C1TXQUA	set	0x158
	global	_C1BDIAG1T
_C1BDIAG1T	set	0x13F
	global	_C1BDIAG1U
_C1BDIAG1U	set	0x13E
	global	_C1BDIAG1H
_C1BDIAG1H	set	0x13D
	global	_C1BDIAG1L
_C1BDIAG1L	set	0x13C
	global	_C1TXQSTAL
_C1TXQSTAL	set	0x154
	global	_C1TRECU
_C1TRECU	set	0x136
	global	_C1TRECL
_C1TRECL	set	0x134
	global	_C1TRECH
_C1TRECH	set	0x135
	global	_C1TXQSTALbits
_C1TXQSTALbits	set	0x154
	global	_C1TXQCONHbits
_C1TXQCONHbits	set	0x151
	global	_C1TXQCONT
_C1TXQCONT	set	0x153
	global	_C1TXQCONU
_C1TXQCONU	set	0x152
	global	_C1TXQCONH
_C1TXQCONH	set	0x151
	global	_C1TXQCONL
_C1TXQCONL	set	0x150
	global	_C1NBTCFGT
_C1NBTCFGT	set	0x107
	global	_C1NBTCFGU
_C1NBTCFGU	set	0x106
	global	_C1NBTCFGH
_C1NBTCFGH	set	0x105
	global	_C1NBTCFGL
_C1NBTCFGL	set	0x104
	global	_C1CONL
_C1CONL	set	0x100
	global	_C1CONH
_C1CONH	set	0x101
	global	_C1FIFOBAH
_C1FIFOBAH	set	0x14D
	global	_C1FIFOBAL
_C1FIFOBAL	set	0x14C
	global	_C1CONUbits
_C1CONUbits	set	0x102
	global	_C1CONTbits
_C1CONTbits	set	0x103
	global	_C1CONU
_C1CONU	set	0x102
	global	_C1CONT
_C1CONT	set	0x103
	global	_C1CONHbits
_C1CONHbits	set	0x101
	global	_U1BRG
_U1BRG	set	0x2AE
	global	_U1TXB
_U1TXB	set	0x2A3
	global	_U1FIFObits
_U1FIFObits	set	0x2B0
	global	_U1CON1bits
_U1CON1bits	set	0x2AC
	global	_U1CON2
_U1CON2	set	0x2AD
	global	_U1CON0
_U1CON0	set	0x2AB
	global	_U1CON1
_U1CON1	set	0x2AC
	global	_CANRXPPS
_CANRXPPS	set	0x23D
	global	_RB2PPS
_RB2PPS	set	0x20B
	global	_RC4PPS
_RC4PPS	set	0x215
	global	_RB1PPS
_RB1PPS	set	0x20A
	global	_RB0PPS
_RB0PPS	set	0x209
	global	_U1RXPPS
_U1RXPPS	set	0x272
	global	_RC6PPS
_RC6PPS	set	0x217
	global	_PPSLOCKbits
_PPSLOCKbits	set	0x200
	global	_PPSLOCK
_PPSLOCK	set	0x200
	global	_ADRES
_ADRES	set	0x3EA
	global	_ADACQ
_ADACQ	set	0x3EE
	global	_ADCON0bits
_ADCON0bits	set	0x3F3
	global	_ADCON0
_ADCON0	set	0x3F3
	global	_ADCON3
_ADCON3	set	0x3F6
	global	_ADCON2
_ADCON2	set	0x3F5
	global	_ADCON1
_ADCON1	set	0x3F4
	global	_ADCLK
_ADCLK	set	0x3FA
	global	_ADREF
_ADREF	set	0x3F8
	global	_ADPCH
_ADPCH	set	0x3EC
	global	_WPUB
_WPUB	set	0x409
	global	_WPUCbits
_WPUCbits	set	0x411
	global	_ANSELCbits
_ANSELCbits	set	0x410
	global	_PORTBbits
_PORTBbits	set	0x4CF
	global	_TRISBbits
_TRISBbits	set	0x4C7
	global	_TRISB
_TRISB	set	0x4C7
	global	_LATB
_LATB	set	0x4BF
	global	_ANSELB
_ANSELB	set	0x408
	global	_TRISCbits
_TRISCbits	set	0x4C8
	global	_ODCONCbits
_ODCONCbits	set	0x412
	global	_LATCbits
_LATCbits	set	0x4C0
	global	_ANSELC
_ANSELC	set	0x410
	global	_TRISA
_TRISA	set	0x4C6
	global	_LATA
_LATA	set	0x4BE
	global	_ANSELA
_ANSELA	set	0x400
psect	mediumconst,class=MEDIUMCONST,space=0,reloc=2,noexec
global __pmediumconst
__pmediumconst:
	db	0
	
STR_31:; BSR set to: 3

	db	82	;'R'
	db	69	;'E'
	db	65	;'A'
	db	68	;'D'
	db	89	;'Y'
	db	32
	db	80	;'P'
	db	73	;'I'
	db	67	;'C'
	db	49	;'1'
	db	56	;'8'
	db	70	;'F'
	db	50	;'2'
	db	54	;'6'
	db	81	;'Q'
	db	56	;'8'
	db	52	;'4'
	db	32
	db	86	;'V'
	db	79	;'O'
	db	76	;'L'
	db	84	;'T'
	db	65	;'A'
	db	71	;'G'
	db	69	;'E'
	db	51	;'3'
	db	32
	db	118	;'v'
	db	56	;'8'
	db	32
	db	80	;'P'
	db	82	;'R'
	db	69	;'E'
	db	83	;'S'
	db	83	;'S'
	db	95	;'_'
	db	82	;'R'
	db	67	;'C'
	db	52	;'4'
	db	32
	db	84	;'T'
	db	69	;'E'
	db	77	;'M'
	db	80	;'P'
	db	49	;'1'
	db	95	;'_'
	db	82	;'R'
	db	66	;'B'
	db	48	;'0'
	db	32
	db	84	;'T'
	db	69	;'E'
	db	77	;'M'
	db	80	;'P'
	db	50	;'2'
	db	95	;'_'
	db	82	;'R'
	db	66	;'B'
	db	49	;'1'
	db	32
	db	78	;'N'
	db	79	;'O'
	db	95	;'_'
	db	80	;'P'
	db	85	;'U'
	db	76	;'L'
	db	76	;'L'
	db	85	;'U'
	db	80	;'P'
	db	83	;'S'
	db	32
	db	86	;'V'
	db	68	;'D'
	db	68	;'D'
	db	95	;'_'
	db	78	;'N'
	db	79	;'O'
	db	77	;'M'
	db	73	;'I'
	db	78	;'N'
	db	65	;'A'
	db	76	;'L'
	db	95	;'_'
	db	53	;'5'
	db	48	;'0'
	db	48	;'0'
	db	48	;'0'
	db	109	;'m'
	db	86	;'V'
	db	32
	db	67	;'C'
	db	65	;'A'
	db	78	;'N'
	db	84	;'T'
	db	88	;'X'
	db	95	;'_'
	db	82	;'R'
	db	66	;'B'
	db	50	;'2'
	db	32
	db	67	;'C'
	db	65	;'A'
	db	78	;'N'
	db	82	;'R'
	db	88	;'X'
	db	95	;'_'
	db	82	;'R'
	db	66	;'B'
	db	51	;'3'
	db	32
	db	67	;'C'
	db	65	;'A'
	db	78	;'N'
	db	53	;'5'
	db	48	;'0'
	db	48	;'0'
	db	32
	db	73	;'I'
	db	68	;'D'
	db	53	;'5'
	db	56	;'8'
	db	48	;'0'
	db	13
	db	10
	db	0
	
STR_35:; BSR set to: 3

	db	86	;'V'
	db	79	;'O'
	db	76	;'L'
	db	84	;'T'
	db	65	;'A'
	db	71	;'G'
	db	69	;'E'
	db	32
	db	99	;'c'
	db	97	;'a'
	db	110	;'n'
	db	95	;'_'
	db	48	;'0'
	db	120	;'x'
	db	53	;'5'
	db	56	;'8'
	db	48	;'0'
	db	61	;'='
	db	0
	
STR_25:; BSR set to: 3

	db	32
	db	109	;'m'
	db	118	;'v'
	db	95	;'_'
	db	110	;'n'
	db	111	;'o'
	db	109	;'m'
	db	105	;'i'
	db	110	;'n'
	db	97	;'a'
	db	108	;'l'
	db	61	;'='
	db	0
	
STR_29:; BSR set to: 3

	db	85	;'U'
	db	78	;'N'
	db	81	;'Q'
	db	85	;'U'
	db	65	;'A'
	db	76	;'L'
	db	73	;'I'
	db	70	;'F'
	db	73	;'I'
	db	69	;'E'
	db	68	;'D'
	db	0
	
STR_16:; BSR set to: 3

	db	32
	db	113	;'q'
	db	101	;'e'
	db	110	;'n'
	db	97	;'a'
	db	98	;'b'
	db	108	;'l'
	db	101	;'e'
	db	61	;'='
	db	0
	
STR_28:; BSR set to: 3

	db	72	;'H'
	db	73	;'I'
	db	71	;'G'
	db	72	;'H'
	db	95	;'_'
	db	82	;'R'
	db	65	;'A'
	db	73	;'I'
	db	76	;'L'
	db	0
	
STR_36:; BSR set to: 3

	db	113	;'q'
	db	117	;'u'
	db	101	;'e'
	db	117	;'u'
	db	101	;'e'
	db	100	;'d'
	db	13
	db	10
	db	0
	
STR_26:; BSR set to: 3

	db	32
	db	115	;'s'
	db	116	;'t'
	db	97	;'a'
	db	116	;'t'
	db	117	;'u'
	db	115	;'s'
	db	61	;'='
	db	0
	
STR_18:; BSR set to: 3

	db	32
	db	100	;'d'
	db	105	;'i'
	db	97	;'a'
	db	103	;'g'
	db	49	;'1'
	db	116	;'t'
	db	61	;'='
	db	0
	
STR_17:; BSR set to: 3

	db	32
	db	100	;'d'
	db	105	;'i'
	db	97	;'a'
	db	103	;'g'
	db	49	;'1'
	db	117	;'u'
	db	61	;'='
	db	0
	
STR_27:; BSR set to: 3

	db	76	;'L'
	db	79	;'O'
	db	87	;'W'
	db	95	;'_'
	db	82	;'R'
	db	65	;'A'
	db	73	;'I'
	db	76	;'L'
	db	0
	
STR_14:; BSR set to: 3

	db	32
	db	113	;'q'
	db	115	;'s'
	db	105	;'i'
	db	122	;'z'
	db	101	;'e'
	db	61	;'='
	db	0
	
STR_22:; BSR set to: 3

	db	32
	db	97	;'a'
	db	110	;'n'
	db	115	;'s'
	db	101	;'e'
	db	108	;'l'
	db	61	;'='
	db	0
	
STR_1:; BSR set to: 3

	db	67	;'C'
	db	65	;'A'
	db	78	;'N'
	db	32
	db	111	;'o'
	db	112	;'p'
	db	61	;'='
	db	0
	
STR_3:; BSR set to: 3

	db	32
	db	114	;'r'
	db	120	;'x'
	db	101	;'e'
	db	114	;'r'
	db	114	;'r'
	db	61	;'='
	db	0
	
STR_2:; BSR set to: 3

	db	32
	db	116	;'t'
	db	120	;'x'
	db	101	;'e'
	db	114	;'r'
	db	114	;'r'
	db	61	;'='
	db	0
	
STR_20:; BSR set to: 3

	db	32
	db	114	;'r'
	db	120	;'x'
	db	112	;'p'
	db	112	;'p'
	db	115	;'s'
	db	61	;'='
	db	0
	
STR_19:; BSR set to: 3

	db	32
	db	116	;'t'
	db	120	;'x'
	db	112	;'p'
	db	112	;'p'
	db	115	;'s'
	db	61	;'='
	db	0
	
STR_4:; BSR set to: 3

	db	32
	db	116	;'t'
	db	114	;'r'
	db	101	;'e'
	db	99	;'c'
	db	117	;'u'
	db	61	;'='
	db	0
	
STR_37:; BSR set to: 3

	db	98	;'b'
	db	117	;'u'
	db	115	;'s'
	db	121	;'y'
	db	13
	db	10
	db	0
	
STR_15:; BSR set to: 3

	db	32
	db	113	;'q'
	db	99	;'c'
	db	102	;'f'
	db	103	;'g'
	db	61	;'='
	db	0
	
STR_13:; BSR set to: 3

	db	32
	db	110	;'n'
	db	109	;'m'
	db	115	;'s'
	db	103	;'g'
	db	61	;'='
	db	0
	
STR_9:; BSR set to: 3

	db	32
	db	99	;'c'
	db	111	;'o'
	db	110	;'n'
	db	104	;'h'
	db	61	;'='
	db	0
	
STR_8:; BSR set to: 3

	db	32
	db	99	;'c'
	db	111	;'o'
	db	110	;'n'
	db	108	;'l'
	db	61	;'='
	db	0
	
STR_21:; BSR set to: 3

	db	32
	db	116	;'t'
	db	114	;'r'
	db	105	;'i'
	db	115	;'s'
	db	61	;'='
	db	0
	
STR_11:; BSR set to: 3

	db	32
	db	99	;'c'
	db	111	;'o'
	db	110	;'n'
	db	116	;'t'
	db	61	;'='
	db	0
	
STR_10:; BSR set to: 3

	db	32
	db	99	;'c'
	db	111	;'o'
	db	110	;'n'
	db	117	;'u'
	db	61	;'='
	db	0
	
STR_33:; BSR set to: 3

	db	84	;'T'
	db	69	;'E'
	db	77	;'M'
	db	80	;'P'
	db	49	;'1'
	db	0
	
STR_34:; BSR set to: 3

	db	84	;'T'
	db	69	;'E'
	db	77	;'M'
	db	80	;'P'
	db	50	;'2'
	db	0
	
STR_12:; BSR set to: 3

	db	32
	db	114	;'r'
	db	98	;'b'
	db	51	;'3'
	db	61	;'='
	db	0
	
STR_24:; BSR set to: 3

	db	32
	db	97	;'a'
	db	100	;'d'
	db	99	;'c'
	db	61	;'='
	db	0
	
STR_6:; BSR set to: 3

	db	32
	db	114	;'r'
	db	101	;'e'
	db	113	;'q'
	db	61	;'='
	db	0
	
STR_5:; BSR set to: 3

	db	32
	db	116	;'t'
	db	120	;'x'
	db	113	;'q'
	db	61	;'='
	db	0
	
STR_32:; BSR set to: 3

	db	80	;'P'
	db	82	;'R'
	db	69	;'E'
	db	83	;'S'
	db	83	;'S'
	db	0
	
STR_7:; BSR set to: 3

	db	32
	db	117	;'u'
	db	97	;'a'
	db	61	;'='
	db	0
STR_23	equ	STR_31+122
STR_30	equ	STR_31+122
; #config settings
	config pad_punits      = on
	config apply_mask      = off
	config ignore_cmsgs    = off
	config default_configs = off
	config default_idlocs  = off
	config FEXTOSC = "OFF"
	config RSTOSC = "HFINTOSC_64MHZ"
	config CLKOUTEN = "OFF"
	config PR1WAY = "ON"
	config CSWEN = "ON"
	config JTAGEN = "OFF"
	config FCMEN = "OFF"
	config FCMENP = "OFF"
	config FCMENS = "OFF"
	config MCLRE = "EXTMCLR"
	config PWRTS = "PWRT_64"
	config MVECEN = "OFF"
	config IVT1WAY = "ON"
	config LPBOREN = "OFF"
	config BOREN = "SBORDIS"
	config BORV = "VBOR_2P45"
	config ZCD = "OFF"
	config PPS1WAY = "ON"
	config STVREN = "ON"
	config LVP = "ON"
	config XINST = "OFF"
	config WDTCPS = "WDTCPS_31"
	config WDTE = "OFF"
	config WDTCWS = "WDTCWS_7"
	config WDTCCS = "SC"
	config BBSIZE = "BBSIZE_512"
	config BBEN = "OFF"
	config SAFEN = "OFF"
	config DEBUG = "OFF"
	config WRTB = "OFF"
	config WRTC = "OFF"
	config WRTD = "OFF"
	config WRTSAF = "OFF"
	config WRTAPP = "OFF"
	config BOOTPINSEL = "RA4"
	config BPEN = "OFF"
	config ODCON = "OFF"
	config CP = "OFF"
	config BOOTSCEN = "OFF"
	config BOOTCOE = "CONTINUE"
	config APPSCEN = "OFF"
	config SAFSCEN = "OFF"
	config DATASCEN = "OFF"
	config CFGSCEN = "OFF"
	config COE = "CONTINUE"
	config BOOTPOR = "OFF"
	file	"pic18f26q84_blink.X\dist\default\production\pic18f26q84_blink.X.production.s"
	line	#
psect	cinit,class=CODE,delta=1,reloc=2
global __pcinit
__pcinit:
global start_initialization
start_initialization:

global __initialization
__initialization:
psect cinit,class=CODE,delta=1
global end_of_initialization,__end_of__initialization

;End of C runtime variable initialization code

end_of_initialization:
__end_of__initialization:
	GLOBAL	__Lmediumconst
	movlw	low highword(__Lmediumconst)
	movwf	tblptru
movlb 0
goto _main	;jump to C main() function
psect	cstackCOMRAM,class=COMRAM,space=1,noexec,lowdata
global __pcstackCOMRAM
__pcstackCOMRAM:
?_uart_init:	; 1 bytes @ 0x0
?_can_init:	; 1 bytes @ 0x0
?_rail_flags:	; 1 bytes @ 0x0
?_uart_puts:	; 1 bytes @ 0x0
?_report_can_diagnostics:	; 1 bytes @ 0x0
?_adc_init:	; 1 bytes @ 0x0
?_main:	; 1 bytes @ 0x0
	global	?_adc_read_average
?_adc_read_average:	; 2 bytes @ 0x0
	global	?___llmod
?___llmod:	; 4 bytes @ 0x0
	global	?___lmul
?___lmul:	; 4 bytes @ 0x0
	global	rail_flags@adc
rail_flags@adc:	; 2 bytes @ 0x0
	global	uart_puts@text
uart_puts@text:	; 2 bytes @ 0x0
	global	___lmul@multiplier
___lmul@multiplier:	; 4 bytes @ 0x0
	global	___llmod@dividend
___llmod@dividend:	; 4 bytes @ 0x0
??_uart_init:	; 1 bytes @ 0x0
??_can_init:	; 1 bytes @ 0x0
??_adc_init:	; 1 bytes @ 0x0
	ds   2
??_rail_flags:	; 1 bytes @ 0x2
??_uart_puts:	; 1 bytes @ 0x2
??_adc_read_average:	; 1 bytes @ 0x2
	ds   2
	global	rail_flags@flags
rail_flags@flags:	; 1 bytes @ 0x4
	global	___lmul@multiplicand
___lmul@multiplicand:	; 4 bytes @ 0x4
	global	___llmod@divisor
___llmod@divisor:	; 4 bytes @ 0x4
	ds   1
	global	rail_flags@i
rail_flags@i:	; 1 bytes @ 0x5
	ds   1
?_can_send_voltages:	; 1 bytes @ 0x6
	global	adc_read_average@channel
adc_read_average@channel:	; 1 bytes @ 0x6
	global	can_send_voltages@adc
can_send_voltages@adc:	; 2 bytes @ 0x6
	ds   1
	global	adc_read_average@sum
adc_read_average@sum:	; 4 bytes @ 0x7
	ds   1
	global	___llmod@counter
___llmod@counter:	; 1 bytes @ 0x8
	global	___lmul@product
___lmul@product:	; 4 bytes @ 0x8
??___llmod:	; 1 bytes @ 0x8
??_can_send_voltages:	; 1 bytes @ 0x8
??___lmul:	; 1 bytes @ 0x8
	ds   3
	global	adc_read_average@index
adc_read_average@index:	; 1 bytes @ 0xB
	ds   1
	global	?___lldiv
?___lldiv:	; 4 bytes @ 0xC
	global	can_send_voltages@i
can_send_voltages@i:	; 1 bytes @ 0xC
	global	___lldiv@dividend
___lldiv@dividend:	; 4 bytes @ 0xC
	ds   1
	global	can_send_voltages@object
can_send_voltages@object:	; 2 bytes @ 0xD
	ds   3
	global	___lldiv@divisor
___lldiv@divisor:	; 4 bytes @ 0x10
	ds   4
	global	___lldiv@quotient
___lldiv@quotient:	; 4 bytes @ 0x14
??___lldiv:	; 1 bytes @ 0x14
	ds   4
	global	___lldiv@counter
___lldiv@counter:	; 1 bytes @ 0x18
	ds   1
	global	?_nominal_millivolts
?_nominal_millivolts:	; 2 bytes @ 0x19
	global	nominal_millivolts@adc
nominal_millivolts@adc:	; 2 bytes @ 0x19
	ds   2
?_uart_put_uint32:	; 1 bytes @ 0x1B
	global	uart_put_uint32@value
uart_put_uint32@value:	; 4 bytes @ 0x1B
??_nominal_millivolts:	; 1 bytes @ 0x1B
	ds   4
	global	uart_put_uint32@digits
uart_put_uint32@digits:	; 10 bytes @ 0x1F
??_uart_put_uint32:	; 1 bytes @ 0x1F
	ds   10
	global	uart_put_uint32@count
uart_put_uint32@count:	; 1 bytes @ 0x29
	ds   1
?_report_voltage:	; 1 bytes @ 0x2A
	global	report_voltage@name
report_voltage@name:	; 2 bytes @ 0x2A
??_report_can_diagnostics:	; 1 bytes @ 0x2A
	ds   2
	global	report_voltage@adc
report_voltage@adc:	; 2 bytes @ 0x2C
	ds   2
	global	_report_voltage$753
_report_voltage$753:	; 2 bytes @ 0x2E
??_report_voltage:	; 1 bytes @ 0x2E
	ds   2
	global	_report_voltage$754
_report_voltage$754:	; 2 bytes @ 0x30
	ds   2
??_main:	; 1 bytes @ 0x32
	ds   2
	global	_main$778
_main$778:	; 2 bytes @ 0x34
	ds   2
	global	main@sent
main@sent:	; 1 bytes @ 0x36
	ds   1
	global	main@cycle
main@cycle:	; 1 bytes @ 0x37
	ds   1
	global	main@adc
main@adc:	; 6 bytes @ 0x38
	ds   6
;!
;!Data Sizes:
;!    Strings     401
;!    Constant    0
;!    Data        0
;!    BSS         0
;!    Persistent  0
;!    Stack       0
;!
;!Auto Spaces:
;!    Space          Size  Autos    Used
;!    COMRAM           95     62      62
;!    BANK5           160      0       0
;!    BANK6           256      0       0
;!    BANK7           256      0       0
;!    BANK8           256      0       0
;!    BANK9           256      0       0
;!    BANK10          256      0       0
;!    BANK11          256      0       0
;!    BANK12          256      0       0
;!    BANK13          256      0       0
;!    BANK14          256      0       0
;!    BANK15          256      0       0
;!    BANK16          256      0       0
;!    BANK17          256      0       0
;!    BANK18          256      0       0
;!    BANK19          256      0       0
;!    BANK20          256      0       0
;!    BANK21          256      0       0
;!    BANK22          256      0       0
;!    BANK23          256      0       0
;!    BANK24          256      0       0
;!    BANK25          256      0       0
;!    BANK26          256      0       0
;!    BANK27          256      0       0
;!    BANK28          256      0       0
;!    BANK29          256      0       0
;!    BANK30          256      0       0
;!    BANK31          256      0       0
;!    BANK32          256      0       0
;!    BANK33          256      0       0
;!    BANK34          256      0       0
;!    BANK35          256      0       0
;!    BANK36          256      0       0

;!
;!Pointer List with Targets:
;!
;!    can_send_voltages@adc	PTR const unsigned short  size(2) Largest target is 6
;!		 -> main@adc(COMRAM[6]), 
;!
;!    can_send_voltages@object	PTR volatile unsigned char  size(2) Largest target is 11775
;!		 -> RAM(DATA[11775]), 
;!
;!    main$778	PTR const unsigned char  size(2) Largest target is 9
;!		 -> STR_36(CODE[9]), STR_37(CODE[7]), 
;!
;!    rail_flags@adc	PTR const unsigned short  size(2) Largest target is 6
;!		 -> main@adc(COMRAM[6]), 
;!
;!    report_voltage$753	PTR const unsigned char  size(2) Largest target is 12
;!		 -> STR_27(CODE[9]), STR_28(CODE[10]), STR_29(CODE[12]), 
;!
;!    report_voltage$754	PTR const unsigned char  size(2) Largest target is 12
;!		 -> STR_28(CODE[10]), STR_29(CODE[12]), 
;!
;!    report_voltage@name	PTR const unsigned char  size(2) Largest target is 6
;!		 -> STR_32(CODE[6]), STR_33(CODE[6]), STR_34(CODE[6]), 
;!
;!    uart_puts@text	PTR const unsigned char  size(2) Largest target is 125
;!		 -> STR_1(CODE[8]), STR_10(CODE[7]), STR_11(CODE[7]), STR_12(CODE[6]), 
;!		 -> STR_13(CODE[7]), STR_14(CODE[8]), STR_15(CODE[7]), STR_16(CODE[10]), 
;!		 -> STR_17(CODE[9]), STR_18(CODE[9]), STR_19(CODE[8]), STR_2(CODE[8]), 
;!		 -> STR_20(CODE[8]), STR_21(CODE[7]), STR_22(CODE[8]), STR_23(CODE[3]), 
;!		 -> STR_24(CODE[6]), STR_25(CODE[13]), STR_26(CODE[9]), STR_27(CODE[9]), 
;!		 -> STR_28(CODE[10]), STR_29(CODE[12]), STR_3(CODE[8]), STR_30(CODE[3]), 
;!		 -> STR_31(CODE[125]), STR_32(CODE[6]), STR_33(CODE[6]), STR_34(CODE[6]), 
;!		 -> STR_35(CODE[19]), STR_36(CODE[9]), STR_37(CODE[7]), STR_4(CODE[8]), 
;!		 -> STR_5(CODE[6]), STR_6(CODE[6]), STR_7(CODE[5]), STR_8(CODE[7]), 
;!		 -> STR_9(CODE[7]), 
;!


;!
;!Critical Paths under _main in COMRAM
;!
;!    _main->_report_voltage
;!    _report_voltage->_uart_put_uint32
;!    _nominal_millivolts->___lldiv
;!    _report_can_diagnostics->_uart_put_uint32
;!    _uart_put_uint32->_nominal_millivolts
;!    ___lldiv->___lmul
;!    _can_send_voltages->_rail_flags
;!
;!Critical Paths under _main in BANK5
;!
;!    None.
;!
;!Critical Paths under _main in BANK6
;!
;!    None.
;!
;!Critical Paths under _main in BANK7
;!
;!    None.
;!
;!Critical Paths under _main in BANK8
;!
;!    None.
;!
;!Critical Paths under _main in BANK9
;!
;!    None.
;!
;!Critical Paths under _main in BANK10
;!
;!    None.
;!
;!Critical Paths under _main in BANK11
;!
;!    None.
;!
;!Critical Paths under _main in BANK12
;!
;!    None.
;!
;!Critical Paths under _main in BANK13
;!
;!    None.
;!
;!Critical Paths under _main in BANK14
;!
;!    None.
;!
;!Critical Paths under _main in BANK15
;!
;!    None.
;!
;!Critical Paths under _main in BANK16
;!
;!    None.
;!
;!Critical Paths under _main in BANK17
;!
;!    None.
;!
;!Critical Paths under _main in BANK18
;!
;!    None.
;!
;!Critical Paths under _main in BANK19
;!
;!    None.
;!
;!Critical Paths under _main in BANK20
;!
;!    None.
;!
;!Critical Paths under _main in BANK21
;!
;!    None.
;!
;!Critical Paths under _main in BANK22
;!
;!    None.
;!
;!Critical Paths under _main in BANK23
;!
;!    None.
;!
;!Critical Paths under _main in BANK24
;!
;!    None.
;!
;!Critical Paths under _main in BANK25
;!
;!    None.
;!
;!Critical Paths under _main in BANK26
;!
;!    None.
;!
;!Critical Paths under _main in BANK27
;!
;!    None.
;!
;!Critical Paths under _main in BANK28
;!
;!    None.
;!
;!Critical Paths under _main in BANK29
;!
;!    None.
;!
;!Critical Paths under _main in BANK30
;!
;!    None.
;!
;!Critical Paths under _main in BANK31
;!
;!    None.
;!
;!Critical Paths under _main in BANK32
;!
;!    None.
;!
;!Critical Paths under _main in BANK33
;!
;!    None.
;!
;!Critical Paths under _main in BANK34
;!
;!    None.
;!
;!Critical Paths under _main in BANK35
;!
;!    None.
;!
;!Critical Paths under _main in BANK36
;!
;!    None.

;;
;;Main: autosize = 0, tempsize = 2, incstack = 0, save=0
;;

;!
;!Call Graph Tables:
;!
;! ---------------------------------------------------------------------------------
;! (Depth) Function   	        Calls       Base Space   Used Autos Params    Refs
;! ---------------------------------------------------------------------------------
;! (0) _main                                                12    12      0    2749
;!                                             50 COMRAM    12    12      0
;!                           _adc_init
;!                   _adc_read_average
;!                           _can_init
;!                  _can_send_voltages
;!             _report_can_diagnostics
;!                     _report_voltage
;!                          _uart_init
;!                          _uart_puts
;! ---------------------------------------------------------------------------------
;! (1) _uart_init                                            0     0      0       0
;! ---------------------------------------------------------------------------------
;! (1) _report_voltage                                       8     4      4    1057
;!                                             42 COMRAM     8     4      4
;!                 _nominal_millivolts
;!                    _uart_put_uint32
;!                          _uart_puts
;! ---------------------------------------------------------------------------------
;! (2) _nominal_millivolts                                   2     0      2     283
;!                                             25 COMRAM     2     0      2
;!                            ___lldiv
;!                             ___lmul
;! ---------------------------------------------------------------------------------
;! (3) ___lmul                                              12     4      8      94
;!                                              0 COMRAM    12     4      8
;! ---------------------------------------------------------------------------------
;! (1) _report_can_diagnostics                               2     2      0     610
;!                                             42 COMRAM     2     2      0
;!                    _uart_put_uint32
;!                          _uart_puts
;! ---------------------------------------------------------------------------------
;! (2) _uart_puts                                            2     0      2      77
;!                                              0 COMRAM     2     0      2
;! ---------------------------------------------------------------------------------
;! (2) _uart_put_uint32                                     15    11      4     533
;!                                             27 COMRAM    15    11      4
;!                            ___lldiv
;!                            ___llmod
;!                 _nominal_millivolts (ARG)
;! ---------------------------------------------------------------------------------
;! (3) ___llmod                                              9     1      8     161
;!                                              0 COMRAM     9     1      8
;! ---------------------------------------------------------------------------------
;! (3) ___lldiv                                             13     5      8     166
;!                                             12 COMRAM    13     5      8
;!                             ___lmul (ARG)
;! ---------------------------------------------------------------------------------
;! (1) _can_send_voltages                                    9     7      2     692
;!                                              6 COMRAM     9     7      2
;!                         _rail_flags
;! ---------------------------------------------------------------------------------
;! (2) _rail_flags                                           6     4      2     204
;!                                              0 COMRAM     6     4      2
;! ---------------------------------------------------------------------------------
;! (1) _can_init                                             0     0      0       0
;! ---------------------------------------------------------------------------------
;! (1) _adc_read_average                                    12    10      2      99
;!                                              0 COMRAM    12    10      2
;! ---------------------------------------------------------------------------------
;! (1) _adc_init                                             0     0      0       0
;! ---------------------------------------------------------------------------------
;! Estimated maximum stack depth 3
;! ---------------------------------------------------------------------------------
;!
;! Call Graph Graphs:
;!
;! _main (ROOT)
;!   _adc_init
;!   _adc_read_average
;!   _can_init
;!   _can_send_voltages
;!     _rail_flags
;!   _report_can_diagnostics
;!     _uart_put_uint32
;!       ___lldiv
;!         ___lmul (ARG)
;!       ___llmod
;!       _nominal_millivolts (ARG)
;!         ___lldiv
;!         ___lmul
;!     _uart_puts
;!   _report_voltage
;!     _nominal_millivolts
;!     _uart_put_uint32
;!     _uart_puts
;!   _uart_init
;!   _uart_puts
;!

;!Address spaces:

;!Name               Size   Autos  Total    Usage
;!BITCOMRAM           95      0       0      0.0%
;!BITBANK5           160      0       0      0.0%
;!BITBANK6           256      0       0      0.0%
;!BITBANK7           256      0       0      0.0%
;!BITBANK8           256      0       0      0.0%
;!BITBANK9           256      0       0      0.0%
;!BITBANK10          256      0       0      0.0%
;!BITBANK11          256      0       0      0.0%
;!BITBANK12          256      0       0      0.0%
;!BITBANK13          256      0       0      0.0%
;!BITBANK14          256      0       0      0.0%
;!BITBANK15          256      0       0      0.0%
;!BITBANK16          256      0       0      0.0%
;!BITBANK17          256      0       0      0.0%
;!BITBANK18          256      0       0      0.0%
;!BITBANK19          256      0       0      0.0%
;!BITBANK20          256      0       0      0.0%
;!BITBANK21          256      0       0      0.0%
;!BITBANK22          256      0       0      0.0%
;!BITBANK23          256      0       0      0.0%
;!BITBANK24          256      0       0      0.0%
;!BITBANK25          256      0       0      0.0%
;!BITBANK26          256      0       0      0.0%
;!BITBANK27          256      0       0      0.0%
;!BITBANK28          256      0       0      0.0%
;!BITBANK29          256      0       0      0.0%
;!BITBANK30          256      0       0      0.0%
;!BITBANK31          256      0       0      0.0%
;!BITBANK32          256      0       0      0.0%
;!BITBANK33          256      0       0      0.0%
;!BITBANK34          256      0       0      0.0%
;!BITBANK35          256      0       0      0.0%
;!BITBANK36          256      0       0      0.0%
;!BITBIGSFR_1       2304      0       0      0.0%
;!BITBIGSFRh         939      0       0      0.0%
;!BITBIGSFRllh       157      0       0      0.0%
;!BITBIGSFRlll        98      0       0      0.0%
;!BITBIGSFRlh         82      0       0      0.0%
;!COMRAM              95     62      62     65.3%
;!BANK5              160      0       0      0.0%
;!BANK6              256      0       0      0.0%
;!BANK7              256      0       0      0.0%
;!BANK8              256      0       0      0.0%
;!BANK9              256      0       0      0.0%
;!BANK10             256      0       0      0.0%
;!BANK11             256      0       0      0.0%
;!BANK12             256      0       0      0.0%
;!BANK13             256      0       0      0.0%
;!BANK14             256      0       0      0.0%
;!BANK15             256      0       0      0.0%
;!BANK16             256      0       0      0.0%
;!BANK17             256      0       0      0.0%
;!BANK18             256      0       0      0.0%
;!BANK19             256      0       0      0.0%
;!BANK20             256      0       0      0.0%
;!BANK21             256      0       0      0.0%
;!BANK22             256      0       0      0.0%
;!BANK23             256      0       0      0.0%
;!BANK24             256      0       0      0.0%
;!BANK25             256      0       0      0.0%
;!BANK26             256      0       0      0.0%
;!BANK27             256      0       0      0.0%
;!BANK28             256      0       0      0.0%
;!BANK29             256      0       0      0.0%
;!BANK30             256      0       0      0.0%
;!BANK31             256      0       0      0.0%
;!BANK32             256      0       0      0.0%
;!BANK33             256      0       0      0.0%
;!BANK34             256      0       0      0.0%
;!BANK35             256      0       0      0.0%
;!BANK36             256      0       0      0.0%
;!BIGRAM            8191      0       0      0.0%
;!STACK                0      0       0      0.0%
;!DATA                 0      0      62      0.0%

	global	_main

;; *************** function _main *****************
;; Defined at:
;;		line 287 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;		None
;; Auto vars:     Size  Location     Type
;;  adc             6   56[COMRAM] unsigned short [3]
;;  sent            1   54[COMRAM] unsigned char 
;;  cycle           1   55[COMRAM] unsigned char 
;; Return value:  Size  Location     Type
;;                  1    wreg      void 
;; Registers used:
;;		wreg, fsr1l, fsr1h, fsr2l, fsr2h, status,2, status,0, tblptrl, tblptrh, tblptru, prodl, prodh, cstack
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:        10       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          2       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:        12       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       12 bytes
;; Hardware stack levels required when called: 3
;; This function calls:
;;		_adc_init
;;		_adc_read_average
;;		_can_init
;;		_can_send_voltages
;;		_report_can_diagnostics
;;		_report_voltage
;;		_uart_init
;;		_uart_puts
;; This function is called by:
;;		Startup code after reset
;; This function uses a non-reentrant model
;;
psect	text0,class=CODE,space=0,reloc=2,group=0
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	287
global __ptext0
__ptext0:
psect	text0
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	287
	
_main:
;incstack = 0
	callstack 124
	line	289
	
l1755:
	clrf	((c:main@cycle))^0500h,c
	line	290
	
l1757:
	call	_uart_init	;wreg free
	line	291
	call	_adc_init	;wreg free
	line	292
	call	_can_init	;wreg free
	line	293
	
l1759:
		movlw	low(STR_31)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_31)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	298
	
l1761:
	movlw	(014h)&0ffh
	
	call	_adc_read_average
	movff	0+?_adc_read_average,(c:main@adc)
	movff	1+?_adc_read_average,(c:main@adc+1)
	line	299
	
l1763:
	movlw	(08h)&0ffh
	
	call	_adc_read_average
	movff	0+?_adc_read_average,0+((c:main@adc)+02h)
	movff	1+?_adc_read_average,1+((c:main@adc)+02h)
	line	300
	
l1765:
	movlw	(09h)&0ffh
	
	call	_adc_read_average
	movff	0+?_adc_read_average,0+((c:main@adc)+04h)
	movff	1+?_adc_read_average,1+((c:main@adc)+04h)
	line	301
	
l1767:
		movlw	low(main@adc)
	movwf	((c:can_send_voltages@adc))^0500h,c
	movlw	high(main@adc)
	movwf	((c:can_send_voltages@adc+1))^0500h,c

	call	_can_send_voltages	;wreg free
	movwf	((c:main@sent))^0500h,c
	line	302
	
l1769:
	incf	((c:main@cycle))^0500h,c
		movlw	5
	xorwf	((c:main@cycle))^0500h,c,w
	btfss	status,2
	goto	u651
	goto	u650

u651:
	goto	l1787
u650:
	line	303
	
l1771:
	clrf	((c:main@cycle))^0500h,c
	line	304
	
l1773:
		movlw	low(STR_32)
	movwf	((c:report_voltage@name))^0500h,c
	movlw	high(STR_32)
	movwf	((c:report_voltage@name+1))^0500h,c

	movff	(c:main@adc),(c:report_voltage@adc)
	movff	(c:main@adc+1),(c:report_voltage@adc+1)
	call	_report_voltage	;wreg free
	line	305
		movlw	low(STR_33)
	movwf	((c:report_voltage@name))^0500h,c
	movlw	high(STR_33)
	movwf	((c:report_voltage@name+1))^0500h,c

	movff	0+((c:main@adc)+02h),(c:report_voltage@adc)
	movff	1+((c:main@adc)+02h),(c:report_voltage@adc+1)
	call	_report_voltage	;wreg free
	line	306
		movlw	low(STR_34)
	movwf	((c:report_voltage@name))^0500h,c
	movlw	high(STR_34)
	movwf	((c:report_voltage@name+1))^0500h,c

	movff	0+((c:main@adc)+04h),(c:report_voltage@adc)
	movff	1+((c:main@adc)+04h),(c:report_voltage@adc+1)
	call	_report_voltage	;wreg free
	line	307
	
l1775:
		movlw	low(STR_35)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_35)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	308
	
l1777:
	movf	((c:main@sent))^0500h,c,w
	btfss	status,2
	goto	u661
	goto	u660
u661:
	goto	l1781
u660:
	
l1779:
		movlw	low(STR_37)
	movwf	((c:_main$778))^0500h,c
	movlw	high(STR_37)
	movwf	((c:_main$778+1))^0500h,c

	goto	l1783
	
l1781:
		movlw	low(STR_36)
	movwf	((c:_main$778))^0500h,c
	movlw	high(STR_36)
	movwf	((c:_main$778+1))^0500h,c

	
l1783:
		movff	(c:_main$778),(c:uart_puts@text)
	movff	(c:_main$778+1),(c:uart_puts@text+1)

	call	_uart_puts	;wreg free
	line	309
	
l1785:
	call	_report_can_diagnostics	;wreg free
	line	311
	
l1787:
	asmopt push
asmopt off
movlw  9
movwf	(??_main+0+1)^0500h,c
movlw	30
movwf	(??_main+0)^0500h,c
	movlw	228
u677:
decfsz	wreg,f
	bra	u677
	decfsz	(??_main+0)^0500h,c,f
	bra	u677
	decfsz	(??_main+0+1)^0500h,c,f
	bra	u677
	nop2
asmopt pop

	goto	l1761
	global	start
	goto	start
	callstack 0
	line	313
GLOBAL	__end_of_main
	__end_of_main:
	signat	_main,89
	global	_uart_init

;; *************** function _uart_init *****************
;; Defined at:
;;		line 76 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;		None
;; Auto vars:     Size  Location     Type
;;		None
;; Return value:  Size  Location     Type
;;                  1    wreg      void 
;; Registers used:
;;		wreg, status,2, status,0
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:        0 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_main
;; This function uses a non-reentrant model
;;
psect	text1,class=CODE,space=0,reloc=2,group=0
	line	76
global __ptext1
__ptext1:
psect	text1
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	76
	
_uart_init:
;incstack = 0
	callstack 126
	line	78
	
l1503:
	movlb	4	; () banked
	bcf	(0+(0/8)+(1024))&0ffh,(0)&7	;volatile
	line	79
	bcf	(0+(0/8)+(c:1214))^0400h,c,(0)&7	;volatile
	line	80
	bcf	(0+(0/8)+(c:1222))^0400h,c,(0)&7	;volatile
	line	82
	
l1505:; BSR set to: 4

	movlb	0	; () banked
	bcf	((102))&0ffh,3	;volatile
	line	83
	
l1507:; BSR set to: 0

	movlw	(03Fh)&0ffh
	movlb	4	; () banked
	andwf	((1040))&0ffh	;volatile
	line	84
	
l1509:; BSR set to: 4

	bsf	((c:1216))^0400h,c,6	;volatile
	line	85
	
l1511:; BSR set to: 4

	bcf	((1042))&0ffh,6	;volatile
	line	86
	
l1513:; BSR set to: 4

	bcf	((c:1224))^0400h,c,6	;volatile
	line	87
	
l1515:; BSR set to: 4

	bsf	((c:1224))^0400h,c,7	;volatile
	line	90
	
l1517:; BSR set to: 4

	movlw	low(055h)
	movlb	2	; () banked
	movwf	((512))&0ffh	;volsfr
	line	91
	
l1519:; BSR set to: 2

	movlw	low(0AAh)
	movwf	((512))&0ffh	;volsfr
	line	92
	
l1521:; BSR set to: 2

	bcf	((512))&0ffh,0	;volsfr
	line	93
	
l1523:; BSR set to: 2

	movlw	low(020h)
	movwf	((535))&0ffh	;volatile
	line	94
	
l1525:; BSR set to: 2

	movlw	low(017h)
	movwf	((626))&0ffh	;volatile
	line	95
	
l1527:; BSR set to: 2

	clrf	((521))&0ffh	;volatile
	line	96
	
l1529:; BSR set to: 2

	clrf	((522))&0ffh	;volatile
	line	97
	
l1531:; BSR set to: 2

	clrf	((533))&0ffh	;volatile
	line	98
	
l1533:; BSR set to: 2

	movlw	low(046h)
	movwf	((523))&0ffh	;volatile
	line	99
	
l1535:; BSR set to: 2

	movlw	low(0Bh)
	movwf	((573))&0ffh	;volatile
	line	100
	
l1537:; BSR set to: 2

	movlw	low(055h)
	movwf	((512))&0ffh	;volsfr
	line	101
	
l1539:; BSR set to: 2

	movlw	low(0AAh)
	movwf	((512))&0ffh	;volsfr
	line	102
	
l1541:; BSR set to: 2

	bsf	((512))&0ffh,0	;volsfr
	line	104
	
l1543:; BSR set to: 2

	clrf	((684))&0ffh	;volatile
	line	105
	
l1545:; BSR set to: 2

	movlw	low(0B0h)
	movwf	((683))&0ffh	;volatile
	line	106
	
l1547:; BSR set to: 2

	movlw	low(080h)
	movwf	((685))&0ffh	;volatile
	line	107
	
l1549:; BSR set to: 2

	clrf	((686+1))&0ffh	;volatile
	movlw	low(08Ah)
	movwf	((686))&0ffh	;volatile
	line	108
	
l1551:; BSR set to: 2

	bsf	((684))&0ffh,7	;volatile
	line	109
	
l149:; BSR set to: 2

	return	;funcret
	callstack 0
GLOBAL	__end_of_uart_init
	__end_of_uart_init:
	signat	_uart_init,89
	global	_report_voltage

;; *************** function _report_voltage *****************
;; Defined at:
;;		line 274 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;  name            2   42[COMRAM] PTR const unsigned char 
;;		 -> STR_34(6), STR_33(6), STR_32(6), 
;;  adc             2   44[COMRAM] unsigned short 
;; Auto vars:     Size  Location     Type
;;		None
;; Return value:  Size  Location     Type
;;                  1    wreg      void 
;; Registers used:
;;		wreg, fsr2l, fsr2h, status,2, status,0, tblptrl, tblptrh, tblptru, cstack
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:         8       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:        8 bytes
;; Hardware stack levels used: 1
;; Hardware stack levels required when called: 2
;; This function calls:
;;		_nominal_millivolts
;;		_uart_put_uint32
;;		_uart_puts
;; This function is called by:
;;		_main
;; This function uses a non-reentrant model
;;
psect	text2,class=CODE,space=0,reloc=2,group=0
	line	274
global __ptext2
__ptext2:
psect	text2
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	274
	
_report_voltage:; BSR set to: 2

;incstack = 0
	callstack 124
	line	276
	
l1733:
		movff	(c:report_voltage@name),(c:uart_puts@text)
	movff	(c:report_voltage@name+1),(c:uart_puts@text+1)

	call	_uart_puts	;wreg free
	line	277
		movlw	low(STR_24)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_24)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	278
	
l1735:
	movff	(c:report_voltage@adc),(c:uart_put_uint32@value)
	movff	(c:report_voltage@adc+1),(c:uart_put_uint32@value+1)
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c
	call	_uart_put_uint32	;wreg free
	line	279
	
l1737:
		movlw	low(STR_25)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_25)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	280
	movff	(c:report_voltage@adc),(c:nominal_millivolts@adc)
	movff	(c:report_voltage@adc+1),(c:nominal_millivolts@adc+1)
	call	_nominal_millivolts	;wreg free
	movff	0+?_nominal_millivolts,(c:uart_put_uint32@value)
	movff	1+?_nominal_millivolts,(c:uart_put_uint32@value+1)
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c
	call	_uart_put_uint32	;wreg free
	line	281
	
l1739:
		movlw	low(STR_26)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_26)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	282
	
l1741:
		movf	((c:report_voltage@adc+1))^0500h,c,w
	bnz	u630
	movlw	5
	subwf	 ((c:report_voltage@adc))^0500h,c,w
	btfss	status,0
	goto	u631
	goto	u630

u631:
	goto	l1749
u630:
	
l1743:
		movlw	251
	subwf	 ((c:report_voltage@adc))^0500h,c,w
	movlw	15
	subwfb	((c:report_voltage@adc+1))^0500h,c,w
	btfsc	status,0
	goto	u641
	goto	u640

u641:
	goto	l1747
u640:
	
l1745:
		movlw	low(STR_29)
	movwf	((c:_report_voltage$754))^0500h,c
	movlw	high(STR_29)
	movwf	((c:_report_voltage$754+1))^0500h,c

	goto	l225
	
l1747:
		movlw	low(STR_28)
	movwf	((c:_report_voltage$754))^0500h,c
	movlw	high(STR_28)
	movwf	((c:_report_voltage$754+1))^0500h,c

	
l225:
		movff	(c:_report_voltage$754),(c:_report_voltage$753)
	movff	(c:_report_voltage$754+1),(c:_report_voltage$753+1)

	goto	l1751
	
l1749:
		movlw	low(STR_27)
	movwf	((c:_report_voltage$753))^0500h,c
	movlw	high(STR_27)
	movwf	((c:_report_voltage$753+1))^0500h,c

	
l1751:
		movff	(c:_report_voltage$753),(c:uart_puts@text)
	movff	(c:_report_voltage$753+1),(c:uart_puts@text+1)

	call	_uart_puts	;wreg free
	line	284
	
l1753:
		movlw	low(STR_30)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_30)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	285
	
l226:
	return	;funcret
	callstack 0
GLOBAL	__end_of_report_voltage
	__end_of_report_voltage:
	signat	_report_voltage,8313
	global	_nominal_millivolts

;; *************** function _nominal_millivolts *****************
;; Defined at:
;;		line 269 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;  adc             2   25[COMRAM] unsigned short 
;; Auto vars:     Size  Location     Type
;;		None
;; Return value:  Size  Location     Type
;;                  2   25[COMRAM] unsigned short 
;; Registers used:
;;		wreg, status,2, status,0, cstack
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         2       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:         2       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:        2 bytes
;; Hardware stack levels used: 1
;; Hardware stack levels required when called: 1
;; This function calls:
;;		___lldiv
;;		___lmul
;; This function is called by:
;;		_report_voltage
;; This function uses a non-reentrant model
;;
psect	text3,class=CODE,space=0,reloc=2,group=0
	line	269
global __ptext3
__ptext3:
psect	text3
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	269
	
_nominal_millivolts:
;incstack = 0
	callstack 124
	line	271
	
l1499:
	movff	(c:nominal_millivolts@adc),(c:___lmul@multiplier)
	movff	(c:nominal_millivolts@adc+1),(c:___lmul@multiplier+1)
	clrf	((c:___lmul@multiplier+2))^0500h,c
	clrf	((c:___lmul@multiplier+3))^0500h,c
	movlw	low(01388h)
	movwf	((c:___lmul@multiplicand))^0500h,c
	movlw	high(01388h)
	movwf	((c:___lmul@multiplicand+1))^0500h,c
	movlw	low highword(01388h)
	movwf	((c:___lmul@multiplicand+2))^0500h,c
	movlw	high highword(01388h)
	movwf	((c:___lmul@multiplicand+3))^0500h,c
	call	___lmul	;wreg free
	movlw	0FFh
	addwf	(0+?___lmul)^0500h,c,w
	movwf	((c:___lldiv@dividend))^0500h,c
	movlw	07h
	addwfc	(1+?___lmul)^0500h,c,w
	movwf	1+((c:___lldiv@dividend))^0500h,c
	
	movlw	0
	addwfc	(2+?___lmul)^0500h,c,w
	movwf	2+((c:___lldiv@dividend))^0500h,c
	
	movlw	0
	addwfc	(3+?___lmul)^0500h,c,w
	movwf	3+((c:___lldiv@dividend))^0500h,c
	movlw	low(0FFFh)
	movwf	((c:___lldiv@divisor))^0500h,c
	movlw	high(0FFFh)
	movwf	((c:___lldiv@divisor+1))^0500h,c
	movlw	low highword(0FFFh)
	movwf	((c:___lldiv@divisor+2))^0500h,c
	movlw	high highword(0FFFh)
	movwf	((c:___lldiv@divisor+3))^0500h,c
	call	___lldiv	;wreg free
	movff	0+?___lldiv,(c:?_nominal_millivolts)
	movff	1+?___lldiv,(c:?_nominal_millivolts+1)
	line	272
	
l215:
	return	;funcret
	callstack 0
GLOBAL	__end_of_nominal_millivolts
	__end_of_nominal_millivolts:
	signat	_nominal_millivolts,4218
	global	___lmul

;; *************** function ___lmul *****************
;; Defined at:
;;		line 15 in file "C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\Umul32.c"
;; Parameters:    Size  Location     Type
;;  multiplier      4    0[COMRAM] unsigned long 
;;  multiplicand    4    4[COMRAM] unsigned long 
;; Auto vars:     Size  Location     Type
;;  product         4    8[COMRAM] unsigned long 
;; Return value:  Size  Location     Type
;;                  4    0[COMRAM] unsigned long 
;; Registers used:
;;		wreg, status,2, status,0
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         8       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:        12       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       12 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_nominal_millivolts
;; This function uses a non-reentrant model
;;
psect	text4,class=CODE,space=0,reloc=2,group=1
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\Umul32.c"
	line	15
global __ptext4
__ptext4:
psect	text4
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\Umul32.c"
	line	15
	
___lmul:
;incstack = 0
	callstack 124
	line	119
	
l1407:
	movlw	low(0)
	movwf	((c:___lmul@product))^0500h,c
	movlw	high(0)
	movwf	((c:___lmul@product+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:___lmul@product+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:___lmul@product+3))^0500h,c
	line	121
	
l1409:
	
	btfss	((c:___lmul@multiplier))^0500h,c,(0)&7
	goto	u341
	goto	u340
u341:
	goto	l1413
u340:
	line	122
	
l1411:
	movf	((c:___lmul@multiplicand))^0500h,c,w
	addwf	((c:___lmul@product))^0500h,c
	movf	((c:___lmul@multiplicand+1))^0500h,c,w
	addwfc	((c:___lmul@product+1))^0500h,c
	movf	((c:___lmul@multiplicand+2))^0500h,c,w
	addwfc	((c:___lmul@product+2))^0500h,c
	movf	((c:___lmul@multiplicand+3))^0500h,c,w
	addwfc	((c:___lmul@product+3))^0500h,c
	line	123
	
l1413:
	bcf	status,0
	rlcf	((c:___lmul@multiplicand))^0500h,c
	rlcf	((c:___lmul@multiplicand+1))^0500h,c
	rlcf	((c:___lmul@multiplicand+2))^0500h,c
	rlcf	((c:___lmul@multiplicand+3))^0500h,c
	line	124
	
l1415:
	bcf	status,0
	rrcf	((c:___lmul@multiplier+3))^0500h,c
	rrcf	((c:___lmul@multiplier+2))^0500h,c
	rrcf	((c:___lmul@multiplier+1))^0500h,c
	rrcf	((c:___lmul@multiplier))^0500h,c
	line	125
	movf	((c:___lmul@multiplier))^0500h,c,w
iorwf	((c:___lmul@multiplier+1))^0500h,c,w
iorwf	((c:___lmul@multiplier+2))^0500h,c,w
iorwf	((c:___lmul@multiplier+3))^0500h,c,w
	btfss	status,2
	goto	u351
	goto	u350

u351:
	goto	l1409
u350:
	
l253:
	line	128
	movff	(c:___lmul@product),(c:?___lmul)
	movff	(c:___lmul@product+1),(c:?___lmul+1)
	movff	(c:___lmul@product+2),(c:?___lmul+2)
	movff	(c:___lmul@product+3),(c:?___lmul+3)
	line	129
	
l254:
	return	;funcret
	callstack 0
GLOBAL	__end_of___lmul
	__end_of___lmul:
	signat	___lmul,8316
	global	_report_can_diagnostics

;; *************** function _report_can_diagnostics *****************
;; Defined at:
;;		line 206 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;		None
;; Auto vars:     Size  Location     Type
;;		None
;; Return value:  Size  Location     Type
;;                  1    wreg      void 
;; Registers used:
;;		wreg, fsr2l, fsr2h, status,2, status,0, tblptrl, tblptrh, tblptru, cstack
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          2       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:         2       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:        2 bytes
;; Hardware stack levels used: 1
;; Hardware stack levels required when called: 2
;; This function calls:
;;		_uart_put_uint32
;;		_uart_puts
;; This function is called by:
;;		_main
;; This function uses a non-reentrant model
;;
psect	text5,class=CODE,space=0,reloc=2,group=0
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	206
global __ptext5
__ptext5:
psect	text5
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	206
	
_report_can_diagnostics:
;incstack = 0
	callstack 124
	line	208
	
l1629:
		movlw	low(STR_1)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_1)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l1631:
	movlb	1	; () banked
	swapf	((258))&0ffh,w	;volatile
	rrcf	wreg,f
	andlw	(1<<3)-1
	movwf	(??_report_can_diagnostics+0)^0500h,c
	movf	((??_report_can_diagnostics+0))^0500h,c,w
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	209
	
l1633:
		movlw	low(STR_2)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_2)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	movlb	1	; () banked
	movf	((309))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	210
	
l1635:
		movlw	low(STR_3)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_3)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l1637:
	movlb	1	; () banked
	movf	((308))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	211
		movlw	low(STR_4)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_4)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l1639:
	movlb	1	; () banked
	movf	((310))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	212
	
l1641:
		movlw	low(STR_5)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_5)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	movlb	1	; () banked
	movf	((340))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	213
	
l1643:
		movlw	low(STR_6)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_6)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l1645:
	movlb	1	; () banked
	movf	((337))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	214
		movlw	low(STR_7)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_7)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l1647:
	movff	(344),(c:uart_put_uint32@value)	;volatile
	movff	(344+1),(c:uart_put_uint32@value+1)	;volatile
	movff	(344+2),(c:uart_put_uint32@value+2)	;volatile
	movff	(344+3),(c:uart_put_uint32@value+3)	;volatile
	call	_uart_put_uint32	;wreg free
	line	215
	
l1649:
		movlw	low(STR_8)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_8)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	movlb	1	; () banked
	movf	((256))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	216
	
l1651:
		movlw	low(STR_9)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_9)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l1653:
	movlb	1	; () banked
	movf	((257))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	217
		movlw	low(STR_10)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_10)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l1655:
	movlb	1	; () banked
	movf	((258))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	218
	
l1657:
		movlw	low(STR_11)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_11)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	movlb	1	; () banked
	movf	((259))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	219
	
l1659:
		movlw	low(STR_12)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_12)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l1661:
	btfsc	((c:1231))^0400h,c,3	;volatile
	goto	u581
	goto	u580
u581:
	clrf	(??_report_can_diagnostics+0)^0500h,c
	incf	(??_report_can_diagnostics+0)^0500h,c
	goto	u588
u580:
	clrf	(??_report_can_diagnostics+0)^0500h,c
u588:
	movf	(??_report_can_diagnostics+0)^0500h,c,w
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	220
		movlw	low(STR_13)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_13)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l1663:
	movlb	1	; () banked
	movf	((317))&0ffh,w	;volatile
	movwf	(??_report_can_diagnostics+0+1)^0500h,c
	movf	((316))&0ffh,w	;volatile
	movwf	(??_report_can_diagnostics+0)^0500h,c
	movff	??_report_can_diagnostics+0,(c:uart_put_uint32@value)
	movff	??_report_can_diagnostics+0+1,(c:uart_put_uint32@value+1)
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c
	call	_uart_put_uint32	;wreg free
	line	221
	
l1665:
		movlw	low(STR_14)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_14)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	movlb	1	; () banked
	movf	((339))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	222
	
l1667:
		movlw	low(STR_15)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_15)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l1669:
	movlb	1	; () banked
	movf	((338))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	223
		movlw	low(STR_16)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_16)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l1671:
	movlb	1	; () banked
	movf	((336))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	224
	
l1673:
		movlw	low(STR_17)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_17)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	movlb	1	; () banked
	movf	((318))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	225
	
l1675:
		movlw	low(STR_18)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_18)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l1677:
	movlb	1	; () banked
	movf	((319))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	226
		movlw	low(STR_19)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_19)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l1679:
	movlb	2	; () banked
	movf	((523))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	227
	
l1681:
		movlw	low(STR_20)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_20)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	movlb	2	; () banked
	movf	((573))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	228
	
l1683:
		movlw	low(STR_21)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_21)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l1685:
	movf	((c:1223))^0400h,c,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	229
		movlw	low(STR_22)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_22)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l1687:
	movlb	4	; () banked
	movf	((1032))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	230
	
l1689:
		movlw	low(STR_23)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_23)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	231
	
l198:
	return	;funcret
	callstack 0
GLOBAL	__end_of_report_can_diagnostics
	__end_of_report_can_diagnostics:
	signat	_report_can_diagnostics,89
	global	_uart_puts

;; *************** function _uart_puts *****************
;; Defined at:
;;		line 183 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;  text            2    0[COMRAM] PTR const unsigned char 
;;		 -> STR_37(7), STR_36(9), STR_35(19), STR_34(6), 
;;		 -> STR_33(6), STR_32(6), STR_31(125), STR_30(3), 
;;		 -> STR_29(12), STR_28(10), STR_27(9), STR_26(9), 
;;		 -> STR_25(13), STR_24(6), STR_23(3), STR_22(8), 
;;		 -> STR_21(7), STR_20(8), STR_19(8), STR_18(9), 
;;		 -> STR_17(9), STR_16(10), STR_15(7), STR_14(8), 
;;		 -> STR_13(7), STR_12(6), STR_11(7), STR_10(7), 
;;		 -> STR_9(7), STR_8(7), STR_7(5), STR_6(6), 
;;		 -> STR_5(6), STR_4(8), STR_3(8), STR_2(8), 
;;		 -> STR_1(8), 
;; Auto vars:     Size  Location     Type
;;		None
;; Return value:  Size  Location     Type
;;                  1    wreg      void 
;; Registers used:
;;		wreg, status,2, status,0, tblptrl, tblptrh, tblptru
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         2       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:         2       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:        2 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_report_can_diagnostics
;;		_report_voltage
;;		_main
;; This function uses a non-reentrant model
;;
psect	text6,class=CODE,space=0,reloc=2,group=0
	line	183
global __ptext6
__ptext6:
psect	text6
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	183
	
_uart_puts:
;incstack = 0
	callstack 125
	line	185
	
l1477:
	goto	l1483
	line	186
	
l180:
	movlb	2	; () banked
	btfsc	((688))&0ffh,4	;volatile
	goto	u471
	goto	u470
u471:
	goto	l180
u470:
	line	187
	
l1479:; BSR set to: 2

	movff	(c:uart_puts@text),tblptrl
	movff	(c:uart_puts@text+1),tblptrh
	if	0	;tblptru may be non-zero
	clrf	tblptru
	endif
	if	0	;tblptru may be non-zero
	global __mediumconst
movlw	low highword(__mediumconst)
	movwf	tblptru
	endif
	tblrd	*
	
	movff	tablat,(675)	;volatile
	
l1481:; BSR set to: 2

	infsnz	((c:uart_puts@text))^0500h,c
	incf	((c:uart_puts@text+1))^0500h,c
	line	185
	
l1483:
	movff	(c:uart_puts@text),tblptrl
	movff	(c:uart_puts@text+1),tblptrh
	if	0	;tblptru may be non-zero
	clrf	tblptru
	endif
	if	0	;tblptru may be non-zero
	global __mediumconst
movlw	low highword(__mediumconst)
	movwf	tblptru
	endif
	tblrd	*
	
	movf	tablat,w
	iorlw	0
	btfss	status,2
	goto	u481
	goto	u480
u481:
	goto	l180
u480:
	line	189
	
l184:
	return	;funcret
	callstack 0
GLOBAL	__end_of_uart_puts
	__end_of_uart_puts:
	signat	_uart_puts,4217
	global	_uart_put_uint32

;; *************** function _uart_put_uint32 *****************
;; Defined at:
;;		line 191 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;  value           4   27[COMRAM] unsigned long 
;; Auto vars:     Size  Location     Type
;;  digits         10   31[COMRAM] unsigned char [10]
;;  count           1   41[COMRAM] unsigned char 
;; Return value:  Size  Location     Type
;;                  1    wreg      void 
;; Registers used:
;;		wreg, fsr2l, fsr2h, status,2, status,0, cstack
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:        11       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:        15       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       15 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		___lldiv
;;		___llmod
;; This function is called by:
;;		_report_can_diagnostics
;;		_report_voltage
;; This function uses a non-reentrant model
;;
psect	text7,class=CODE,space=0,reloc=2,group=0
	line	191
global __ptext7
__ptext7:
psect	text7
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	191
	
_uart_put_uint32:
;incstack = 0
	callstack 125
	line	194
	
l1485:
	clrf	((c:uart_put_uint32@count))^0500h,c
	line	197
	
l1487:
	movlw	low(uart_put_uint32@digits)
	addwf	((c:uart_put_uint32@count))^0500h,c,w
	movwf	c:fsr2l
	clrf	1+c:fsr2l
	movlw	high(uart_put_uint32@digits)
	addwfc	1+c:fsr2l
	movff	(c:uart_put_uint32@value),(c:___llmod@dividend)
	movff	(c:uart_put_uint32@value+1),(c:___llmod@dividend+1)
	movff	(c:uart_put_uint32@value+2),(c:___llmod@dividend+2)
	movff	(c:uart_put_uint32@value+3),(c:___llmod@dividend+3)
	movlw	low(0Ah)
	movwf	((c:___llmod@divisor))^0500h,c
	movlw	high(0Ah)
	movwf	((c:___llmod@divisor+1))^0500h,c
	movlw	low highword(0Ah)
	movwf	((c:___llmod@divisor+2))^0500h,c
	movlw	high highword(0Ah)
	movwf	((c:___llmod@divisor+3))^0500h,c
	call	___llmod	;wreg free
	movf	(0+?___llmod)^0500h,c,w
	addlw	low(030h)
	movwf	indf2,c

	
l1489:
	incf	((c:uart_put_uint32@count))^0500h,c
	line	198
	
l1491:
	movff	(c:uart_put_uint32@value),(c:___lldiv@dividend)
	movff	(c:uart_put_uint32@value+1),(c:___lldiv@dividend+1)
	movff	(c:uart_put_uint32@value+2),(c:___lldiv@dividend+2)
	movff	(c:uart_put_uint32@value+3),(c:___lldiv@dividend+3)
	movlw	low(0Ah)
	movwf	((c:___lldiv@divisor))^0500h,c
	movlw	high(0Ah)
	movwf	((c:___lldiv@divisor+1))^0500h,c
	movlw	low highword(0Ah)
	movwf	((c:___lldiv@divisor+2))^0500h,c
	movlw	high highword(0Ah)
	movwf	((c:___lldiv@divisor+3))^0500h,c
	call	___lldiv	;wreg free
	movff	0+?___lldiv,(c:uart_put_uint32@value)
	movff	1+?___lldiv,(c:uart_put_uint32@value+1)
	movff	2+?___lldiv,(c:uart_put_uint32@value+2)
	movff	3+?___lldiv,(c:uart_put_uint32@value+3)
	
	line	199
	
l1493:
	movf	((c:uart_put_uint32@value))^0500h,c,w
iorwf	((c:uart_put_uint32@value+1))^0500h,c,w
iorwf	((c:uart_put_uint32@value+2))^0500h,c,w
iorwf	((c:uart_put_uint32@value+3))^0500h,c,w
	btfss	status,2
	goto	u491
	goto	u490

u491:
	goto	l1487
u490:
	goto	l1497
	line	201
	
l191:
	movlb	2	; () banked
	btfsc	((688))&0ffh,4	;volatile
	goto	u501
	goto	u500
u501:
	goto	l191
u500:
	line	202
	
l1495:; BSR set to: 2

	decf	((c:uart_put_uint32@count))^0500h,c
	movlw	low(uart_put_uint32@digits)
	addwf	((c:uart_put_uint32@count))^0500h,c,w
	movwf	c:fsr2l
	clrf	1+c:fsr2l
	movlw	high(uart_put_uint32@digits)
	addwfc	1+c:fsr2l
	movf	indf2,w
	movwf	((675))&0ffh	;volatile
	line	200
	
l1497:
	movf	((c:uart_put_uint32@count))^0500h,c,w
	btfss	status,2
	goto	u511
	goto	u510
u511:
	goto	l191
u510:
	line	204
	
l195:
	return	;funcret
	callstack 0
GLOBAL	__end_of_uart_put_uint32
	__end_of_uart_put_uint32:
	signat	_uart_put_uint32,4217
	global	___llmod

;; *************** function ___llmod *****************
;; Defined at:
;;		line 7 in file "C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\llmod.c"
;; Parameters:    Size  Location     Type
;;  dividend        4    0[COMRAM] unsigned long 
;;  divisor         4    4[COMRAM] unsigned long 
;; Auto vars:     Size  Location     Type
;;  counter         1    8[COMRAM] unsigned char 
;; Return value:  Size  Location     Type
;;                  4    0[COMRAM] unsigned long 
;; Registers used:
;;		wreg, status,2, status,0
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         8       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         1       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:         9       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:        9 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_uart_put_uint32
;; This function uses a non-reentrant model
;;
psect	text8,class=CODE,space=0,reloc=2,group=1
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\llmod.c"
	line	7
global __ptext8
__ptext8:
psect	text8
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\llmod.c"
	line	7
	
___llmod:
;incstack = 0
	callstack 124
	line	12
	
l1439:
	movf	((c:___llmod@divisor))^0500h,c,w
iorwf	((c:___llmod@divisor+1))^0500h,c,w
iorwf	((c:___llmod@divisor+2))^0500h,c,w
iorwf	((c:___llmod@divisor+3))^0500h,c,w
	btfsc	status,2
	goto	u391
	goto	u390

u391:
	goto	l772
u390:
	line	13
	
l1441:
	movlw	low(01h)
	movwf	((c:___llmod@counter))^0500h,c
	line	14
	goto	l1445
	line	15
	
l1443:
	bcf	status,0
	rlcf	((c:___llmod@divisor))^0500h,c
	rlcf	((c:___llmod@divisor+1))^0500h,c
	rlcf	((c:___llmod@divisor+2))^0500h,c
	rlcf	((c:___llmod@divisor+3))^0500h,c
	line	16
	incf	((c:___llmod@counter))^0500h,c
	line	14
	
l1445:
	
	btfss	((c:___llmod@divisor+3))^0500h,c,(31)&7
	goto	u401
	goto	u400
u401:
	goto	l1443
u400:
	line	19
	
l1447:
		movf	((c:___llmod@divisor))^0500h,c,w
	subwf	((c:___llmod@dividend))^0500h,c,w
	movf	((c:___llmod@divisor+1))^0500h,c,w
	subwfb	((c:___llmod@dividend+1))^0500h,c,w
	movf	((c:___llmod@divisor+2))^0500h,c,w
	subwfb	((c:___llmod@dividend+2))^0500h,c,w
	movf	((c:___llmod@divisor+3))^0500h,c,w
	subwfb	((c:___llmod@dividend+3))^0500h,c,w
	btfss	status,0
	goto	u411
	goto	u410

u411:
	goto	l1451
u410:
	line	20
	
l1449:
	movf	((c:___llmod@divisor))^0500h,c,w
	subwf	((c:___llmod@dividend))^0500h,c
	movf	((c:___llmod@divisor+1))^0500h,c,w
	subwfb	((c:___llmod@dividend+1))^0500h,c
	movf	((c:___llmod@divisor+2))^0500h,c,w
	subwfb	((c:___llmod@dividend+2))^0500h,c
	movf	((c:___llmod@divisor+3))^0500h,c,w
	subwfb	((c:___llmod@dividend+3))^0500h,c
	line	21
	
l1451:
	bcf	status,0
	rrcf	((c:___llmod@divisor+3))^0500h,c
	rrcf	((c:___llmod@divisor+2))^0500h,c
	rrcf	((c:___llmod@divisor+1))^0500h,c
	rrcf	((c:___llmod@divisor))^0500h,c
	line	22
	
l1453:
	decfsz	((c:___llmod@counter))^0500h,c
	
	goto	l1447
	line	23
	
l772:
	line	24
	movff	(c:___llmod@dividend),(c:?___llmod)
	movff	(c:___llmod@dividend+1),(c:?___llmod+1)
	movff	(c:___llmod@dividend+2),(c:?___llmod+2)
	movff	(c:___llmod@dividend+3),(c:?___llmod+3)
	line	25
	
l779:
	return	;funcret
	callstack 0
GLOBAL	__end_of___llmod
	__end_of___llmod:
	signat	___llmod,8316
	global	___lldiv

;; *************** function ___lldiv *****************
;; Defined at:
;;		line 7 in file "C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\__lldiv.c"
;; Parameters:    Size  Location     Type
;;  dividend        4   12[COMRAM] unsigned long 
;;  divisor         4   16[COMRAM] unsigned long 
;; Auto vars:     Size  Location     Type
;;  quotient        4   20[COMRAM] unsigned long 
;;  counter         1   24[COMRAM] unsigned char 
;; Return value:  Size  Location     Type
;;                  4   12[COMRAM] unsigned long 
;; Registers used:
;;		wreg, status,2, status,0
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         8       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         5       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:        13       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       13 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_uart_put_uint32
;;		_nominal_millivolts
;; This function uses a non-reentrant model
;;
psect	text9,class=CODE,space=0,reloc=2,group=1
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\__lldiv.c"
	line	7
global __ptext9
__ptext9:
psect	text9
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\__lldiv.c"
	line	7
	
___lldiv:
;incstack = 0
	callstack 124
	line	13
	
l1417:
	movlw	low(0)
	movwf	((c:___lldiv@quotient))^0500h,c
	movlw	high(0)
	movwf	((c:___lldiv@quotient+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:___lldiv@quotient+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:___lldiv@quotient+3))^0500h,c
	line	14
	
l1419:
	movf	((c:___lldiv@divisor))^0500h,c,w
iorwf	((c:___lldiv@divisor+1))^0500h,c,w
iorwf	((c:___lldiv@divisor+2))^0500h,c,w
iorwf	((c:___lldiv@divisor+3))^0500h,c,w
	btfsc	status,2
	goto	u361
	goto	u360

u361:
	goto	l269
u360:
	line	15
	
l1421:
	movlw	low(01h)
	movwf	((c:___lldiv@counter))^0500h,c
	line	16
	goto	l1425
	line	17
	
l1423:
	bcf	status,0
	rlcf	((c:___lldiv@divisor))^0500h,c
	rlcf	((c:___lldiv@divisor+1))^0500h,c
	rlcf	((c:___lldiv@divisor+2))^0500h,c
	rlcf	((c:___lldiv@divisor+3))^0500h,c
	line	18
	incf	((c:___lldiv@counter))^0500h,c
	line	16
	
l1425:
	
	btfss	((c:___lldiv@divisor+3))^0500h,c,(31)&7
	goto	u371
	goto	u370
u371:
	goto	l1423
u370:
	line	21
	
l1427:
	bcf	status,0
	rlcf	((c:___lldiv@quotient))^0500h,c
	rlcf	((c:___lldiv@quotient+1))^0500h,c
	rlcf	((c:___lldiv@quotient+2))^0500h,c
	rlcf	((c:___lldiv@quotient+3))^0500h,c
	line	22
	
l1429:
		movf	((c:___lldiv@divisor))^0500h,c,w
	subwf	((c:___lldiv@dividend))^0500h,c,w
	movf	((c:___lldiv@divisor+1))^0500h,c,w
	subwfb	((c:___lldiv@dividend+1))^0500h,c,w
	movf	((c:___lldiv@divisor+2))^0500h,c,w
	subwfb	((c:___lldiv@dividend+2))^0500h,c,w
	movf	((c:___lldiv@divisor+3))^0500h,c,w
	subwfb	((c:___lldiv@dividend+3))^0500h,c,w
	btfss	status,0
	goto	u381
	goto	u380

u381:
	goto	l1435
u380:
	line	23
	
l1431:
	movf	((c:___lldiv@divisor))^0500h,c,w
	subwf	((c:___lldiv@dividend))^0500h,c
	movf	((c:___lldiv@divisor+1))^0500h,c,w
	subwfb	((c:___lldiv@dividend+1))^0500h,c
	movf	((c:___lldiv@divisor+2))^0500h,c,w
	subwfb	((c:___lldiv@dividend+2))^0500h,c
	movf	((c:___lldiv@divisor+3))^0500h,c,w
	subwfb	((c:___lldiv@dividend+3))^0500h,c
	line	24
	
l1433:
	bsf	(0+(0/8)+(c:___lldiv@quotient))^0500h,c,(0)&7
	line	26
	
l1435:
	bcf	status,0
	rrcf	((c:___lldiv@divisor+3))^0500h,c
	rrcf	((c:___lldiv@divisor+2))^0500h,c
	rrcf	((c:___lldiv@divisor+1))^0500h,c
	rrcf	((c:___lldiv@divisor))^0500h,c
	line	27
	
l1437:
	decfsz	((c:___lldiv@counter))^0500h,c
	
	goto	l1427
	line	28
	
l269:
	line	29
	movff	(c:___lldiv@quotient),(c:?___lldiv)
	movff	(c:___lldiv@quotient+1),(c:?___lldiv+1)
	movff	(c:___lldiv@quotient+2),(c:?___lldiv+2)
	movff	(c:___lldiv@quotient+3),(c:?___lldiv+3)
	line	30
	
l276:
	return	;funcret
	callstack 0
GLOBAL	__end_of___lldiv
	__end_of___lldiv:
	signat	___lldiv,8316
	global	_can_send_voltages

;; *************** function _can_send_voltages *****************
;; Defined at:
;;		line 158 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;  adc             2    6[COMRAM] PTR const unsigned short
;;		 -> main@adc(6), 
;; Auto vars:     Size  Location     Type
;;  object          2   13[COMRAM] PTR volatile unsigned ch
;;		 -> RAM(11775), 
;;  i               1   12[COMRAM] unsigned char 
;; Return value:  Size  Location     Type
;;                  1    wreg      unsigned char 
;; Registers used:
;;		wreg, fsr1l, fsr1h, fsr2l, fsr2h, status,2, status,0, prodl, prodh, cstack
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         2       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         3       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:         9       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:        9 bytes
;; Hardware stack levels used: 1
;; Hardware stack levels required when called: 1
;; This function calls:
;;		_rail_flags
;; This function is called by:
;;		_main
;; This function uses a non-reentrant model
;;
psect	text10,class=CODE,space=0,reloc=2,group=0
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	158
global __ptext10
__ptext10:
psect	text10
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	158
	
_can_send_voltages:
;incstack = 0
	callstack 125
	line	162
	
l1579:
	movlb	1	; () banked
	btfsc	((340))&0ffh,0	;volatile
	goto	u551
	goto	u550
u551:
	goto	l1585
u550:
	
l1581:; BSR set to: 1

	movlw	(0)&0ffh
	goto	l172
	line	163
	
l1585:; BSR set to: 1

		movff	(344),(c:can_send_voltages@object)	;volatile
	movff	(344+1),(c:can_send_voltages@object+1)	;volatile

	line	164
	movf	((c:can_send_voltages@object))^0500h,c,w
iorwf	((c:can_send_voltages@object+1))^0500h,c,w
	btfss	status,2
	goto	u561
	goto	u560

u561:
	goto	l1591
u560:
	goto	l1581
	line	165
	
l1591:; BSR set to: 1

	movff	(c:can_send_voltages@object),fsr2l
	movff	(c:can_send_voltages@object+1),fsr2h
	movlw	low(080h)
	movwf	indf2
	line	166
	
l1593:; BSR set to: 1

	lfsr	2,01h
	movf	((c:can_send_voltages@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_voltages@object+1))^0500h,c,w
	addwfc	fsr2h
	movlw	low(05h)
	movwf	indf2
	line	167
	
l1595:; BSR set to: 1

	lfsr	2,02h
	movf	((c:can_send_voltages@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_voltages@object+1))^0500h,c,w
	addwfc	fsr2h
	clrf	indf2
	line	168
	
l1597:; BSR set to: 1

	lfsr	2,03h
	movf	((c:can_send_voltages@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_voltages@object+1))^0500h,c,w
	addwfc	fsr2h
	clrf	indf2
	line	169
	
l1599:; BSR set to: 1

	lfsr	2,04h
	movf	((c:can_send_voltages@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_voltages@object+1))^0500h,c,w
	addwfc	fsr2h
	movlw	low(08h)
	movwf	indf2
	line	170
	
l1601:; BSR set to: 1

	lfsr	2,05h
	movf	((c:can_send_voltages@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_voltages@object+1))^0500h,c,w
	addwfc	fsr2h
	clrf	indf2
	line	171
	
l1603:; BSR set to: 1

	lfsr	2,06h
	movf	((c:can_send_voltages@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_voltages@object+1))^0500h,c,w
	addwfc	fsr2h
	clrf	indf2
	line	172
	
l1605:; BSR set to: 1

	lfsr	2,07h
	movf	((c:can_send_voltages@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_voltages@object+1))^0500h,c,w
	addwfc	fsr2h
	clrf	indf2
	line	173
	
l1607:; BSR set to: 1

	clrf	((c:can_send_voltages@i))^0500h,c
	line	174
	
l1613:
	movf	((c:can_send_voltages@i))^0500h,c,w
	mullw	02h
	movf	(prodl)^0400h,c,w
	addwf	((c:can_send_voltages@adc))^0500h,c,w
	movwf	c:fsr2l
	movf	(prodh)^0400h,c,w
	addwfc	((c:can_send_voltages@adc+1))^0500h,c,w
	movwf	1+c:fsr2l
	movf	((c:can_send_voltages@i))^0500h,c,w
	mullw	02h
	movf	(prodl)^0400h,c,w
	addwf	((c:can_send_voltages@object))^0500h,c,w
	movwf	(??_can_send_voltages+0)^0500h,c
	movf	(prodh)^0400h,c,w
	addwfc	((c:can_send_voltages@object+1))^0500h,c,w
	movwf	1+(??_can_send_voltages+0)^0500h,c
	movlw	low(08h)
	addwf	(??_can_send_voltages+0)^0500h,c,w
	movwf	c:fsr1l
	movlw	high(08h)
	addwfc	(??_can_send_voltages+0+1)^0500h,c,w
	movwf	1+c:fsr1l
	movff	indf2,indf1
	line	175
	movf	((c:can_send_voltages@i))^0500h,c,w
	mullw	02h
	movf	(prodl)^0400h,c,w
	addwf	((c:can_send_voltages@object))^0500h,c,w
	movwf	(??_can_send_voltages+0)^0500h,c
	movf	(prodh)^0400h,c,w
	addwfc	((c:can_send_voltages@object+1))^0500h,c,w
	movwf	1+(??_can_send_voltages+0)^0500h,c
	movlw	low(09h)
	addwf	(??_can_send_voltages+0)^0500h,c,w
	movwf	c:fsr2l
	movlw	high(09h)
	addwfc	(??_can_send_voltages+0+1)^0500h,c,w
	movwf	1+c:fsr2l
	movf	((c:can_send_voltages@i))^0500h,c,w
	mullw	02h
	movf	(prodl)^0400h,c,w
	addwf	((c:can_send_voltages@adc))^0500h,c,w
	movwf	c:fsr1l
	movf	(prodh)^0400h,c,w
	addwfc	((c:can_send_voltages@adc+1))^0500h,c,w
	movwf	1+c:fsr1l
	movff	postinc1,??_can_send_voltages+2
	movff	postdec1,??_can_send_voltages+2+1
	movff	??_can_send_voltages+2+1,??_can_send_voltages+2
	clrf	(??_can_send_voltages+2+1)^0500h,c
	movf	(??_can_send_voltages+2)^0500h,c,w
	movwf	indf2,c

	line	173
	
l1615:
	incf	((c:can_send_voltages@i))^0500h,c
	
l1617:
		movlw	03h-1
	cpfsgt	((c:can_send_voltages@i))^0500h,c
	goto	u571
	goto	u570

u571:
	goto	l1613
u570:
	line	177
	
l1619:
		movff	(c:can_send_voltages@adc),(c:rail_flags@adc)
	movff	(c:can_send_voltages@adc+1),(c:rail_flags@adc+1)

	call	_rail_flags	;wreg free
	movwf	(??_can_send_voltages+0)^0500h,c
	lfsr	2,0Eh
	movf	((c:can_send_voltages@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_voltages@object+1))^0500h,c,w
	addwfc	fsr2h
	movff	(??_can_send_voltages+0),indf2

	line	178
	
l1621:
	lfsr	2,0Fh
	movf	((c:can_send_voltages@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_voltages@object+1))^0500h,c,w
	addwfc	fsr2h
	movlw	low(01h)
	movwf	indf2
	line	179
	
l1623:
	movlw	low(03h)
	movlb	1	; () banked
	movwf	((337))&0ffh	;volatile
	line	180
	
l1625:; BSR set to: 1

	movlw	(01h)&0ffh
	line	181
	
l172:; BSR set to: 1

	return	;funcret
	callstack 0
GLOBAL	__end_of_can_send_voltages
	__end_of_can_send_voltages:
	signat	_can_send_voltages,4217
	global	_rail_flags

;; *************** function _rail_flags *****************
;; Defined at:
;;		line 147 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;  adc             2    0[COMRAM] PTR const unsigned short
;;		 -> main@adc(6), 
;; Auto vars:     Size  Location     Type
;;  i               1    5[COMRAM] unsigned char 
;;  flags           1    4[COMRAM] unsigned char 
;; Return value:  Size  Location     Type
;;                  1    wreg      unsigned char 
;; Registers used:
;;		wreg, fsr2l, fsr2h, status,2, status,0, prodl, prodh
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         2       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         2       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          2       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:         6       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:        6 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_can_send_voltages
;; This function uses a non-reentrant model
;;
psect	text11,class=CODE,space=0,reloc=2,group=0
	line	147
global __ptext11
__ptext11:
psect	text11
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	147
	
_rail_flags:; BSR set to: 1

;incstack = 0
	callstack 125
	line	149
	
l1455:
	clrf	((c:rail_flags@flags))^0500h,c
	line	151
	clrf	((c:rail_flags@i))^0500h,c
	line	152
	
l1461:
	movf	((c:rail_flags@i))^0500h,c,w
	mullw	02h
	movf	(prodl)^0400h,c,w
	addwf	((c:rail_flags@adc))^0500h,c,w
	movwf	c:fsr2l
	movf	(prodh)^0400h,c,w
	addwfc	((c:rail_flags@adc+1))^0500h,c,w
	movwf	1+c:fsr2l
		movlw	1
	movf	plusw2,w
	bnz	u421
	movlw	5
	subwf	 postinc2,w
	btfsc	status,0
	goto	u421
	goto	u420

u421:
	goto	l1465
u420:
	
l1463:
	movff	(c:rail_flags@i),??_rail_flags+0
	movlw	(01h)&0ffh
	movwf	(??_rail_flags+1)^0500h,c
	incf	(??_rail_flags+0)^0500h,c
	goto	u434
u435:
	bcf	status,0
	rlcf	((??_rail_flags+1))^0500h,c
u434:
	decfsz	(??_rail_flags+0)^0500h,c
	goto	u435
	movf	((??_rail_flags+1))^0500h,c,w
	iorwf	((c:rail_flags@flags))^0500h,c
	line	153
	
l1465:
	movf	((c:rail_flags@i))^0500h,c,w
	mullw	02h
	movf	(prodl)^0400h,c,w
	addwf	((c:rail_flags@adc))^0500h,c,w
	movwf	c:fsr2l
	movf	(prodh)^0400h,c,w
	addwfc	((c:rail_flags@adc+1))^0500h,c,w
	movwf	1+c:fsr2l
		movlw	251
	subwf	 postinc2,w
	movlw	15
	subwfb	postinc2,w
	btfss	status,0
	goto	u441
	goto	u440

u441:
	goto	l1469
u440:
	
l1467:
	movff	(c:rail_flags@i),??_rail_flags+0
	movlw	03h
	addwf	(??_rail_flags+0)^0500h,c
	movlw	(01h)&0ffh
	movwf	(??_rail_flags+1)^0500h,c
	incf	(??_rail_flags+0)^0500h,c
	goto	u454
u455:
	bcf	status,0
	rlcf	((??_rail_flags+1))^0500h,c
u454:
	decfsz	(??_rail_flags+0)^0500h,c
	goto	u455
	movf	((??_rail_flags+1))^0500h,c,w
	iorwf	((c:rail_flags@flags))^0500h,c
	line	151
	
l1469:
	incf	((c:rail_flags@i))^0500h,c
	
l1471:
		movlw	03h-1
	cpfsgt	((c:rail_flags@i))^0500h,c
	goto	u461
	goto	u460

u461:
	goto	l1461
u460:
	line	155
	
l1473:
	movf	((c:rail_flags@flags))^0500h,c,w
	line	156
	
l168:
	return	;funcret
	callstack 0
GLOBAL	__end_of_rail_flags
	__end_of_rail_flags:
	signat	_rail_flags,4217
	global	_can_init

;; *************** function _can_init *****************
;; Defined at:
;;		line 111 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;		None
;; Auto vars:     Size  Location     Type
;;		None
;; Return value:  Size  Location     Type
;;                  1    wreg      void 
;; Registers used:
;;		wreg, status,2, status,0
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:        0 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_main
;; This function uses a non-reentrant model
;;
psect	text12,class=CODE,space=0,reloc=2,group=0
	line	111
global __ptext12
__ptext12:
psect	text12
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	111
	
_can_init:
;incstack = 0
	callstack 126
	line	113
	
l1553:
	movlb	0	; () banked
	bcf	((98))&0ffh,7	;volatile
	line	114
	
l1555:; BSR set to: 0

	movlw	(0F3h)&0ffh
	movlb	4	; () banked
	andwf	((1032))&0ffh	;volatile
	line	115
	
l1557:; BSR set to: 4

	bsf	(0+(2/8)+(c:1215))^0400h,c,(2)&7	;volatile
	line	116
	
l1559:; BSR set to: 4

	bcf	(0+(2/8)+(c:1223))^0400h,c,(2)&7	;volatile
	line	117
	
l1561:; BSR set to: 4

	bsf	((c:1223))^0400h,c,3	;volatile
	line	119
	
l1563:; BSR set to: 4

	movlb	1	; () banked
	bsf	((257))&0ffh,7	;volatile
	line	120
	
l1565:; BSR set to: 1

	movlw	low(04h)
	movwf	((259))&0ffh	;volatile
	line	121
	
l1567:; BSR set to: 1

	movlw	low(090h)
	movwf	((258))&0ffh	;volatile
	line	122
	
l1569:; BSR set to: 1

	movf	((259))&0ffh,w	;volatile
	andlw	not (((1<<3)-1)<<0)
	iorlw	(04h & ((1<<3)-1))<<0
	movwf	((259))&0ffh	;volatile
	line	123
	
l1571:; BSR set to: 1

	swapf	((258))&0ffh,w	;volatile
	rrcf	wreg,f
	andlw	(1<<3)-1
	xorlw	04h
	btfss	status,2
	goto	u521
	goto	u520
u521:
	goto	l1571
u520:
	
l154:; BSR set to: 1

	line	125
	clrf	((332))&0ffh	;volatile
	line	126
	
l1573:; BSR set to: 1

	movlw	low(026h)
	movwf	((333))&0ffh	;volatile
	line	127
	movlw	low(087h)
	movwf	((257))&0ffh	;volatile
	line	128
	movlw	low(060h)
	movwf	((256))&0ffh	;volatile
	line	129
	movlw	low(010h)
	movwf	((258))&0ffh	;volatile
	line	132
	movlw	low(01Ah)
	movwf	((260))&0ffh	;volatile
	line	133
	movlw	low(01Ah)
	movwf	((261))&0ffh	;volatile
	line	134
	movlw	low(063h)
	movwf	((262))&0ffh	;volatile
	line	135
	
l1575:; BSR set to: 1

	clrf	((263))&0ffh	;volatile
	line	137
	movlw	low(080h)
	movwf	((336))&0ffh	;volatile
	line	138
	movlw	low(04h)
	movwf	((337))&0ffh	;volatile
	line	139
	movlw	low(060h)
	movwf	((338))&0ffh	;volatile
	line	140
	movlw	low(01h)
	movwf	((339))&0ffh	;volatile
	line	142
	movf	((259))&0ffh,w	;volatile
	andlw	not (((1<<3)-1)<<0)
	iorlw	(06h & ((1<<3)-1))<<0
	movwf	((259))&0ffh	;volatile
	line	143
	
l1577:; BSR set to: 1

	swapf	((258))&0ffh,w	;volatile
	rrcf	wreg,f
	andlw	(1<<3)-1
	xorlw	06h
	btfss	status,2
	goto	u531
	goto	u530
u531:
	goto	l1577
u530:
	line	144
	
l158:; BSR set to: 1

	btfsc	((337))&0ffh,2	;volatile
	goto	u541
	goto	u540
u541:
	goto	l158
u540:
	line	145
	
l161:; BSR set to: 1

	return	;funcret
	callstack 0
GLOBAL	__end_of_can_init
	__end_of_can_init:
	signat	_can_init,89
	global	_adc_read_average

;; *************** function _adc_read_average *****************
;; Defined at:
;;		line 252 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;  channel         1    wreg     unsigned char 
;; Auto vars:     Size  Location     Type
;;  channel         1    6[COMRAM] unsigned char 
;;  sum             4    7[COMRAM] unsigned long 
;;  index           1   11[COMRAM] unsigned char 
;; Return value:  Size  Location     Type
;;                  2    0[COMRAM] unsigned short 
;; Registers used:
;;		wreg, status,2, status,0
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         2       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         6       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:        12       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       12 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_main
;; This function uses a non-reentrant model
;;
psect	text13,class=CODE,space=0,reloc=2,group=0
	line	252
global __ptext13
__ptext13:
psect	text13
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	252
	
_adc_read_average:; BSR set to: 1

;incstack = 0
	callstack 126
	line	254
	movwf	((c:adc_read_average@channel))^0500h,c
	
l1711:
	movlw	low(0)
	movwf	((c:adc_read_average@sum))^0500h,c
	movlw	high(0)
	movwf	((c:adc_read_average@sum+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:adc_read_average@sum+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:adc_read_average@sum+3))^0500h,c
	line	257
	
l1713:
	movff	(c:adc_read_average@channel),(1004)	;volatile
	line	258
	
l1715:
	asmopt push
asmopt off
	movlw	228
u687:
	nop2
	nop2
decfsz	wreg,f
	bra	u687
	nop2
	nop2
asmopt pop

	line	259
	
l1717:
	movlb	3	; () banked
	bsf	((1011))&0ffh,0	;volatile
	line	260
	
l204:; BSR set to: 3

	btfsc	((1011))&0ffh,0	;volatile
	goto	u591
	goto	u590
u591:
	goto	l204
u590:
	
l206:; BSR set to: 3

	line	261
	clrf	((c:adc_read_average@index))^0500h,c
	
l207:; BSR set to: 3

	line	262
	bsf	((1011))&0ffh,0	;volatile
	line	263
	
l209:; BSR set to: 3

	btfsc	((1011))&0ffh,0	;volatile
	goto	u601
	goto	u600
u601:
	goto	l209
u600:
	line	264
	
l1723:; BSR set to: 3

	movlw	0FFh
	andwf	((1002))&0ffh,w	;volatile
	movwf	(??_adc_read_average+0)^0500h,c
	movlw	0Fh
	andwf	((1002+1))&0ffh,w	;volatile
	movwf	1+(??_adc_read_average+0)^0500h,c
	movf	(??_adc_read_average+0)^0500h,c,w
	addwf	((c:adc_read_average@sum))^0500h,c
	movf	(??_adc_read_average+0+1)^0500h,c,w
	addwfc	((c:adc_read_average@sum+1))^0500h,c
	movlw	0
	addwfc	((c:adc_read_average@sum+2))^0500h,c
	movlw	0
	addwfc	((c:adc_read_average@sum+3))^0500h,c

	line	261
	
l1725:; BSR set to: 3

	incf	((c:adc_read_average@index))^0500h,c
	
l1727:; BSR set to: 3

		movlw	020h-1
	cpfsgt	((c:adc_read_average@index))^0500h,c
	goto	u611
	goto	u610

u611:
	goto	l207
u610:
	line	266
	
l1729:; BSR set to: 3

	movlw	010h
	addwf	((c:adc_read_average@sum))^0500h,c,w
	movwf	(??_adc_read_average+0)^0500h,c
	movlw	0
	addwfc	((c:adc_read_average@sum+1))^0500h,c,w
	movwf	1+(??_adc_read_average+0)^0500h,c
	
	movlw	0
	addwfc	((c:adc_read_average@sum+2))^0500h,c,w
	movwf	2+(??_adc_read_average+0)^0500h,c
	
	movlw	0
	addwfc	((c:adc_read_average@sum+3))^0500h,c,w
	movwf	3+(??_adc_read_average+0)^0500h,c
	movlw	05h+1
	goto	u620
u625:
	bcf	status,0
	rrcf	(??_adc_read_average+0+3)^0500h,c
	rrcf	(??_adc_read_average+0+2)^0500h,c
	rrcf	(??_adc_read_average+0+1)^0500h,c
	rrcf	(??_adc_read_average+0)^0500h,c
u620:
	decfsz	wreg
	goto	u625
	movff	??_adc_read_average+0,(c:?_adc_read_average)
	movff	??_adc_read_average+0+1,(c:?_adc_read_average+1)
	line	267
	
l212:; BSR set to: 3

	return	;funcret
	callstack 0
GLOBAL	__end_of_adc_read_average
	__end_of_adc_read_average:
	signat	_adc_read_average,4218
	global	_adc_init

;; *************** function _adc_init *****************
;; Defined at:
;;		line 233 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;		None
;; Auto vars:     Size  Location     Type
;;		None
;; Return value:  Size  Location     Type
;;                  1    wreg      void 
;; Registers used:
;;		wreg, status,2, status,0
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:        0 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_main
;; This function uses a non-reentrant model
;;
psect	text14,class=CODE,space=0,reloc=2,group=0
	line	233
global __ptext14
__ptext14:
psect	text14
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	233
	
_adc_init:; BSR set to: 3

;incstack = 0
	callstack 126
	line	235
	
l1691:
	movlb	0	; () banked
	bcf	((99))&0ffh,5	;volatile
	line	236
	bsf	((c:1224))^0400h,c,4	;volatile
	line	237
	movlb	4	; () banked
	bsf	((1040))&0ffh,4	;volatile
	line	238
	bcf	((1041))&0ffh,4	;volatile
	line	239
	
l1693:; BSR set to: 4

	movlw	(03h)&0ffh
	iorwf	((c:1223))^0400h,c	;volatile
	line	240
	movlw	(03h)&0ffh
	iorwf	((1032))&0ffh	;volatile
	line	241
	movlw	(0FCh)&0ffh
	andwf	((1033))&0ffh	;volatile
	line	242
	
l1695:; BSR set to: 4

	movlw	low(014h)
	movlb	3	; () banked
	movwf	((1004))&0ffh	;volatile
	line	243
	
l1697:; BSR set to: 3

	clrf	((1016))&0ffh	;volatile
	line	244
	
l1699:; BSR set to: 3

	movlw	low(01Fh)
	movwf	((1018))&0ffh	;volatile
	line	245
	
l1701:; BSR set to: 3

	clrf	((1006+1))&0ffh	;volatile
	movlw	low(040h)
	movwf	((1006))&0ffh	;volatile
	line	246
	
l1703:; BSR set to: 3

	clrf	((1012))&0ffh	;volatile
	line	247
	
l1705:; BSR set to: 3

	clrf	((1013))&0ffh	;volatile
	line	248
	
l1707:; BSR set to: 3

	clrf	((1014))&0ffh	;volatile
	line	249
	
l1709:; BSR set to: 3

	movlw	low(084h)
	movwf	((1011))&0ffh	;volatile
	line	250
	
l201:; BSR set to: 3

	return	;funcret
	callstack 0
GLOBAL	__end_of_adc_init
	__end_of_adc_init:
	signat	_adc_init,89
psect	mediumconst
	db 0	; dummy byte at the end
	global	__smallconst
__smallconst	set	__pmediumconst
	global	__mediumconst
__mediumconst	set	__pmediumconst
	GLOBAL	__activetblptr
__activetblptr	EQU	2
	psect	intsave_regs,class=BIGRAM,space=1,noexec
	PSECT	rparam,class=COMRAM,space=1,noexec
	GLOBAL	__Lrparam
	FNCONF	rparam,??,?
	GLOBAL	___rparam_used
	___rparam_used EQU 1
	GLOBAL	___param_bank
	___param_bank EQU 0
GLOBAL	__Lparam, __Hparam
GLOBAL	__Lrparam, __Hrparam
__Lparam	EQU	__Lrparam
__Hparam	EQU	__Hrparam
	end
