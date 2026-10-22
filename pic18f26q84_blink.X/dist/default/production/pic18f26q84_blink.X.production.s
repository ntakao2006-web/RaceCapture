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
	FNCALL	_main,___lldiv
	FNCALL	_main,___lmul
	FNCALL	_main,_adc_init
	FNCALL	_main,_adc_read_average
	FNCALL	_main,_can_init
	FNCALL	_main,_can_send_oil_temperature
	FNCALL	_main,_report_can_diagnostics
	FNCALL	_main,_report_measurement
	FNCALL	_main,_thermistor_centi_c
	FNCALL	_main,_uart_init
	FNCALL	_main,_uart_puts
	FNCALL	_thermistor_centi_c,___fladd
	FNCALL	_thermistor_centi_c,___fldiv
	FNCALL	_thermistor_centi_c,___flmul
	FNCALL	_thermistor_centi_c,___fltol
	FNCALL	_thermistor_centi_c,___xxtofl
	FNCALL	_thermistor_centi_c,_logf
	FNCALL	_logf,___fladd
	FNCALL	_logf,___fldiv
	FNCALL	_logf,___flmul
	FNCALL	_logf,___flsub
	FNCALL	_logf,___xxtofl
	FNCALL	___flsub,___fladd
	FNCALL	_report_measurement,___lldiv
	FNCALL	_report_measurement,___llmod
	FNCALL	_report_measurement,_uart_put_uint32
	FNCALL	_report_measurement,_uart_puts
	FNCALL	_report_can_diagnostics,_uart_put_uint32
	FNCALL	_report_can_diagnostics,_uart_puts
	FNCALL	_uart_put_uint32,___lldiv
	FNCALL	_uart_put_uint32,___llmod
	FNROOT	_main
psect	mediumconst,class=MEDIUMCONST,space=0,reloc=2,noexec
global __pmediumconst
__pmediumconst:
	db	0
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\logf.c"
	line	27
_Lg4:
	dw	(normalize32(0x3e789e26) & 0ffffh)
	dw	highword (normalize32(0x3e789e26))
	global __end_of_Lg4
__end_of_Lg4:
psect	mediumconst
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\logf.c"
	line	26
_Lg3:
	dw	(normalize32(0x3e91e9ee) & 0ffffh)
	dw	highword (normalize32(0x3e91e9ee))
	global __end_of_Lg3
__end_of_Lg3:
psect	mediumconst
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\logf.c"
	line	25
_Lg2:
	dw	(normalize32(0x3eccce13) & 0ffffh)
	dw	highword (normalize32(0x3eccce13))
	global __end_of_Lg2
__end_of_Lg2:
psect	mediumconst
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\logf.c"
	line	24
_Lg1:
	dw	(normalize32(0x3f2aaaaa) & 0ffffh)
	dw	highword (normalize32(0x3f2aaaaa))
	global __end_of_Lg1
__end_of_Lg1:
psect	mediumconst
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\logf.c"
	line	22
_ln2_lo:
	dw	(normalize32(0x3717f7d1) & 0ffffh)
	dw	highword (normalize32(0x3717f7d1))
	global __end_of_ln2_lo
__end_of_ln2_lo:
psect	mediumconst
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\logf.c"
	line	21
_ln2_hi:
	dw	(normalize32(0x3f317180) & 0ffffh)
	dw	highword (normalize32(0x3f317180))
	global __end_of_ln2_hi
__end_of_ln2_hi:
	global	logf@F472
	global	_errno
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
	
STR_40:
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
	db	79	;'O'
	db	73	;'I'
	db	76	;'L'
	db	84	;'T'
	db	69	;'E'
	db	77	;'M'
	db	80	;'P'
	db	32
	db	83	;'S'
	db	69	;'E'
	db	78	;'N'
	db	83	;'S'
	db	69	;'E'
	db	48	;'0'
	db	32
	db	82	;'R'
	db	67	;'C'
	db	51	;'3'
	db	32
	db	80	;'P'
	db	85	;'U'
	db	49	;'1'
	db	48	;'0'
	db	48	;'0'
	db	48	;'0'
	db	48	;'0'
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
	db	54	;'6'
	db	48	;'0'
	db	48	;'0'
	db	32
	db	118	;'v'
	db	55	;'7'
	db	32
	db	70	;'F'
	db	65	;'A'
	db	85	;'U'
	db	76	;'L'
	db	84	;'T'
	db	95	;'_'
	db	67	;'C'
	db	65	;'A'
	db	78	;'N'
	db	32
	db	82	;'R'
	db	65	;'A'
	db	77	;'M'
	db	50	;'2'
	db	54	;'6'
	db	48	;'0'
	db	48	;'0'
	db	13
	db	10
	db	0
	
STR_28:
	db	32
	db	115	;'s'
	db	116	;'t'
	db	97	;'a'
	db	116	;'t'
	db	117	;'u'
	db	115	;'s'
	db	61	;'='
	db	83	;'S'
	db	72	;'H'
	db	79	;'O'
	db	82	;'R'
	db	84	;'T'
	db	95	;'_'
	db	79	;'O'
	db	82	;'R'
	db	95	;'_'
	db	85	;'U'
	db	78	;'N'
	db	68	;'D'
	db	69	;'E'
	db	82	;'R'
	db	95	;'_'
	db	82	;'R'
	db	65	;'A'
	db	78	;'N'
	db	71	;'G'
	db	69	;'E'
	db	32
	db	99	;'c'
	db	97	;'a'
	db	110	;'n'
	db	95	;'_'
	db	48	;'0'
	db	120	;'x'
	db	54	;'6'
	db	48	;'0'
	db	48	;'0'
	db	61	;'='
	db	0
	
STR_25:
	db	32
	db	115	;'s'
	db	116	;'t'
	db	97	;'a'
	db	116	;'t'
	db	117	;'u'
	db	115	;'s'
	db	61	;'='
	db	79	;'O'
	db	80	;'P'
	db	69	;'E'
	db	78	;'N'
	db	95	;'_'
	db	79	;'O'
	db	82	;'R'
	db	95	;'_'
	db	79	;'O'
	db	86	;'V'
	db	69	;'E'
	db	82	;'R'
	db	95	;'_'
	db	82	;'R'
	db	65	;'A'
	db	78	;'N'
	db	71	;'G'
	db	69	;'E'
	db	32
	db	99	;'c'
	db	97	;'a'
	db	110	;'n'
	db	95	;'_'
	db	48	;'0'
	db	120	;'x'
	db	54	;'6'
	db	48	;'0'
	db	48	;'0'
	db	61	;'='
	db	0
	
STR_24:
	db	84	;'T'
	db	72	;'H'
	db	69	;'E'
	db	82	;'R'
	db	77	;'M'
	db	32
	db	97	;'a'
	db	100	;'d'
	db	99	;'c'
	db	61	;'='
	db	0
	
STR_16:
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
	
STR_26:
	db	113	;'q'
	db	117	;'u'
	db	101	;'e'
	db	117	;'u'
	db	101	;'e'
	db	100	;'d'
	db	13
	db	10
	db	0
	
STR_32:
	db	32
	db	116	;'t'
	db	101	;'e'
	db	109	;'m'
	db	112	;'p'
	db	95	;'_'
	db	99	;'c'
	db	61	;'='
	db	0
	
STR_18:
	db	32
	db	100	;'d'
	db	105	;'i'
	db	97	;'a'
	db	103	;'g'
	db	49	;'1'
	db	116	;'t'
	db	61	;'='
	db	0
	
STR_17:
	db	32
	db	100	;'d'
	db	105	;'i'
	db	97	;'a'
	db	103	;'g'
	db	49	;'1'
	db	117	;'u'
	db	61	;'='
	db	0
	
STR_14:
	db	32
	db	113	;'q'
	db	115	;'s'
	db	105	;'i'
	db	122	;'z'
	db	101	;'e'
	db	61	;'='
	db	0
	
STR_22:
	db	32
	db	97	;'a'
	db	110	;'n'
	db	115	;'s'
	db	101	;'e'
	db	108	;'l'
	db	61	;'='
	db	0
	
STR_31:
	db	32
	db	114	;'r'
	db	95	;'_'
	db	111	;'o'
	db	104	;'h'
	db	109	;'m'
	db	61	;'='
	db	0
	
STR_1:
	db	67	;'C'
	db	65	;'A'
	db	78	;'N'
	db	32
	db	111	;'o'
	db	112	;'p'
	db	61	;'='
	db	0
	
STR_3:
	db	32
	db	114	;'r'
	db	120	;'x'
	db	101	;'e'
	db	114	;'r'
	db	114	;'r'
	db	61	;'='
	db	0
	
STR_2:
	db	32
	db	116	;'t'
	db	120	;'x'
	db	101	;'e'
	db	114	;'r'
	db	114	;'r'
	db	61	;'='
	db	0
	
STR_20:
	db	32
	db	114	;'r'
	db	120	;'x'
	db	112	;'p'
	db	112	;'p'
	db	115	;'s'
	db	61	;'='
	db	0
	
STR_19:
	db	32
	db	116	;'t'
	db	120	;'x'
	db	112	;'p'
	db	112	;'p'
	db	115	;'s'
	db	61	;'='
	db	0
	
STR_4:
	db	32
	db	116	;'t'
	db	114	;'r'
	db	101	;'e'
	db	99	;'c'
	db	117	;'u'
	db	61	;'='
	db	0
	
STR_27:
	db	98	;'b'
	db	117	;'u'
	db	115	;'s'
	db	121	;'y'
	db	13
	db	10
	db	0
	
STR_15:
	db	32
	db	113	;'q'
	db	99	;'c'
	db	102	;'f'
	db	103	;'g'
	db	61	;'='
	db	0
	
STR_13:
	db	32
	db	110	;'n'
	db	109	;'m'
	db	115	;'s'
	db	103	;'g'
	db	61	;'='
	db	0
	
STR_9:
	db	32
	db	99	;'c'
	db	111	;'o'
	db	110	;'n'
	db	104	;'h'
	db	61	;'='
	db	0
	
STR_8:
	db	32
	db	99	;'c'
	db	111	;'o'
	db	110	;'n'
	db	108	;'l'
	db	61	;'='
	db	0
	
STR_21:
	db	32
	db	116	;'t'
	db	114	;'r'
	db	105	;'i'
	db	115	;'s'
	db	61	;'='
	db	0
	
STR_11:
	db	32
	db	99	;'c'
	db	111	;'o'
	db	110	;'n'
	db	116	;'t'
	db	61	;'='
	db	0
	
STR_10:
	db	32
	db	99	;'c'
	db	111	;'o'
	db	110	;'n'
	db	117	;'u'
	db	61	;'='
	db	0
	
STR_37:
	db	113	;'q'
	db	117	;'u'
	db	101	;'e'
	db	117	;'u'
	db	101	;'e'
	db	100	;'d'
	db	0
	
STR_12:
	db	32
	db	114	;'r'
	db	98	;'b'
	db	51	;'3'
	db	61	;'='
	db	0
	
STR_6:
	db	32
	db	114	;'r'
	db	101	;'e'
	db	113	;'q'
	db	61	;'='
	db	0
	
STR_5:
	db	32
	db	116	;'t'
	db	120	;'x'
	db	113	;'q'
	db	61	;'='
	db	0
	
STR_7:
	db	32
	db	117	;'u'
	db	97	;'a'
	db	61	;'='
	db	0
	
STR_38:
	db	98	;'b'
	db	117	;'u'
	db	115	;'s'
	db	121	;'y'
	db	0
	
STR_33:
	db	45
	db	0
	
STR_34:
	db	46
	db	0
	
STR_35:
	db	48	;'0'
	db	0
STR_36	equ	STR_28+28
STR_30	equ	STR_27+0
STR_29	equ	STR_26+0
STR_23	equ	STR_40+98
STR_39	equ	STR_40+98
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
psect	bssBANK5,class=BANK5,space=1,noexec,lowdata
global __pbssBANK5
__pbssBANK5:
logf@F472:
       ds      4
	global	_errno
_errno:
       ds      2
	file	"pic18f26q84_blink.X\dist\default\production\pic18f26q84_blink.X.production.s"
	line	#
psect	cinit
; Clear objects allocated to BANK5 (6 bytes)
	global __pbssBANK5
movlb	5
clrf	(__pbssBANK5+5)&0xffh,b
clrf	(__pbssBANK5+4)&0xffh,b
clrf	(__pbssBANK5+3)&0xffh,b
clrf	(__pbssBANK5+2)&0xffh,b
clrf	(__pbssBANK5+1)&0xffh,b
clrf	(__pbssBANK5+0)&0xffh,b
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
psect	cstackBANK5,class=BANK5,space=1,noexec,lowdata
global __pcstackBANK5
__pcstackBANK5:
??_logf:	; 1 bytes @ 0x0
	ds   6
	global	logf@R
logf@R:	; 4 bytes @ 0x6
	ds   4
	global	logf@t1
logf@t1:	; 4 bytes @ 0xA
	ds   4
	global	logf@t2
logf@t2:	; 4 bytes @ 0xE
	ds   4
	global	_logf$1626
_logf$1626:	; 4 bytes @ 0x12
	ds   4
	global	_logf$1627
_logf$1627:	; 4 bytes @ 0x16
	ds   4
	global	_logf$1628
_logf$1628:	; 4 bytes @ 0x1A
	ds   4
	global	_logf$1629
_logf$1629:	; 4 bytes @ 0x1E
	ds   4
	global	logf@k
logf@k:	; 2 bytes @ 0x22
	ds   2
	global	logf@hfsq
logf@hfsq:	; 4 bytes @ 0x24
	ds   4
	global	logf@dk
logf@dk:	; 4 bytes @ 0x28
	ds   4
	global	logf@s
logf@s:	; 4 bytes @ 0x2C
	ds   4
	global	logf@z
logf@z:	; 4 bytes @ 0x30
	ds   4
	global	logf@w
logf@w:	; 4 bytes @ 0x34
	ds   4
	global	_logf$1625
_logf$1625:	; 4 bytes @ 0x38
	ds   4
	global	logf@ux
logf@ux:	; 4 bytes @ 0x3C
	ds   4
	global	?_thermistor_centi_c
?_thermistor_centi_c:	; 4 bytes @ 0x40
	global	thermistor_centi_c@resistance_ohm
thermistor_centi_c@resistance_ohm:	; 4 bytes @ 0x40
	ds   4
	global	thermistor_centi_c@hot_kelvin
thermistor_centi_c@hot_kelvin:	; 4 bytes @ 0x44
	ds   4
	global	thermistor_centi_c@hot_resistance
thermistor_centi_c@hot_resistance:	; 4 bytes @ 0x48
	ds   4
	global	thermistor_centi_c@beta_kelvin
thermistor_centi_c@beta_kelvin:	; 4 bytes @ 0x4C
	ds   4
	global	thermistor_centi_c@inverse_kelvin
thermistor_centi_c@inverse_kelvin:	; 4 bytes @ 0x50
	ds   4
	global	_thermistor_centi_c$1621
_thermistor_centi_c$1621:	; 4 bytes @ 0x54
	ds   4
	global	_thermistor_centi_c$1622
_thermistor_centi_c$1622:	; 4 bytes @ 0x58
	ds   4
	global	_thermistor_centi_c$743
_thermistor_centi_c$743:	; 4 bytes @ 0x5C
	ds   4
	global	thermistor_centi_c@centi_c
thermistor_centi_c@centi_c:	; 4 bytes @ 0x60
	ds   4
??_main:	; 1 bytes @ 0x64
	ds   6
	global	main@centi_c
main@centi_c:	; 4 bytes @ 0x6A
	ds   4
	global	main@sent
main@sent:	; 1 bytes @ 0x6E
	ds   1
	global	main@cycle
main@cycle:	; 1 bytes @ 0x6F
	ds   1
	global	main@resistance
main@resistance:	; 4 bytes @ 0x70
	ds   4
	global	main@adc
main@adc:	; 2 bytes @ 0x74
	ds   2
psect	cstackCOMRAM,class=COMRAM,space=1,noexec,lowdata
global __pcstackCOMRAM
__pcstackCOMRAM:
?_uart_init:	; 1 bytes @ 0x0
?_can_init:	; 1 bytes @ 0x0
?_can_send_oil_temperature:	; 1 bytes @ 0x0
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
	global	?___xxtofl
?___xxtofl:	; 4 bytes @ 0x0
	global	uart_puts@text
uart_puts@text:	; 2 bytes @ 0x0
	global	can_send_oil_temperature@centi_c
can_send_oil_temperature@centi_c:	; 4 bytes @ 0x0
	global	___lmul@multiplier
___lmul@multiplier:	; 4 bytes @ 0x0
	global	___llmod@dividend
___llmod@dividend:	; 4 bytes @ 0x0
	global	___xxtofl@val
___xxtofl@val:	; 4 bytes @ 0x0
??_uart_init:	; 1 bytes @ 0x0
??_can_init:	; 1 bytes @ 0x0
??_adc_init:	; 1 bytes @ 0x0
	ds   2
??_uart_puts:	; 1 bytes @ 0x2
??_adc_read_average:	; 1 bytes @ 0x2
	ds   2
	global	can_send_oil_temperature@adc
can_send_oil_temperature@adc:	; 2 bytes @ 0x4
	global	___lmul@multiplicand
___lmul@multiplicand:	; 4 bytes @ 0x4
	global	___llmod@divisor
___llmod@divisor:	; 4 bytes @ 0x4
??___xxtofl:	; 1 bytes @ 0x4
	ds   2
	global	can_send_oil_temperature@resistance
can_send_oil_temperature@resistance:	; 4 bytes @ 0x6
	global	adc_read_average@sum
adc_read_average@sum:	; 4 bytes @ 0x6
	ds   2
	global	___llmod@counter
___llmod@counter:	; 1 bytes @ 0x8
	global	___xxtofl@sign
___xxtofl@sign:	; 1 bytes @ 0x8
	global	___lmul@product
___lmul@product:	; 4 bytes @ 0x8
??___llmod:	; 1 bytes @ 0x8
??___lmul:	; 1 bytes @ 0x8
	ds   1
	global	___xxtofl@exp
___xxtofl@exp:	; 1 bytes @ 0x9
	ds   1
	global	adc_read_average@index
adc_read_average@index:	; 1 bytes @ 0xA
	global	can_send_oil_temperature@oil_temp
can_send_oil_temperature@oil_temp:	; 2 bytes @ 0xA
	global	___xxtofl@arg
___xxtofl@arg:	; 4 bytes @ 0xA
??_can_send_oil_temperature:	; 1 bytes @ 0xA
	ds   2
	global	?___lldiv
?___lldiv:	; 4 bytes @ 0xC
	global	can_send_oil_temperature@object
can_send_oil_temperature@object:	; 2 bytes @ 0xC
	global	___lldiv@dividend
___lldiv@dividend:	; 4 bytes @ 0xC
	ds   2
	global	?___fldiv
?___fldiv:	; 4 bytes @ 0xE
	global	___fldiv@b
___fldiv@b:	; 4 bytes @ 0xE
	ds   2
	global	___lldiv@divisor
___lldiv@divisor:	; 4 bytes @ 0x10
	ds   2
	global	___fldiv@a
___fldiv@a:	; 4 bytes @ 0x12
	ds   2
	global	___lldiv@quotient
___lldiv@quotient:	; 4 bytes @ 0x14
??___lldiv:	; 1 bytes @ 0x14
	ds   2
??___fldiv:	; 1 bytes @ 0x16
	ds   2
	global	___lldiv@counter
___lldiv@counter:	; 1 bytes @ 0x18
	ds   1
?_uart_put_uint32:	; 1 bytes @ 0x19
	global	uart_put_uint32@value
uart_put_uint32@value:	; 4 bytes @ 0x19
	ds   1
	global	___fldiv@rem
___fldiv@rem:	; 4 bytes @ 0x1A
	ds   3
	global	uart_put_uint32@digits
uart_put_uint32@digits:	; 10 bytes @ 0x1D
??_uart_put_uint32:	; 1 bytes @ 0x1D
	ds   1
	global	___fldiv@sign
___fldiv@sign:	; 1 bytes @ 0x1E
	ds   1
	global	___fldiv@new_exp
___fldiv@new_exp:	; 2 bytes @ 0x1F
	ds   2
	global	___fldiv@grs
___fldiv@grs:	; 4 bytes @ 0x21
	ds   4
	global	___fldiv@bexp
___fldiv@bexp:	; 1 bytes @ 0x25
	ds   1
	global	___fldiv@aexp
___fldiv@aexp:	; 1 bytes @ 0x26
	ds   1
	global	?___fladd
?___fladd:	; 4 bytes @ 0x27
	global	uart_put_uint32@count
uart_put_uint32@count:	; 1 bytes @ 0x27
	global	___fladd@b
___fladd@b:	; 4 bytes @ 0x27
	ds   1
?_report_measurement:	; 1 bytes @ 0x28
	global	report_measurement@adc
report_measurement@adc:	; 2 bytes @ 0x28
??_report_can_diagnostics:	; 1 bytes @ 0x28
	ds   2
	global	report_measurement@resistance
report_measurement@resistance:	; 4 bytes @ 0x2A
	ds   1
	global	___fladd@a
___fladd@a:	; 4 bytes @ 0x2B
	ds   3
	global	report_measurement@centi_c
report_measurement@centi_c:	; 4 bytes @ 0x2E
	ds   1
??___fladd:	; 1 bytes @ 0x2F
	ds   3
	global	report_measurement@can_sent
report_measurement@can_sent:	; 1 bytes @ 0x32
	ds   1
	global	___fladd@signs
___fladd@signs:	; 1 bytes @ 0x33
??_report_measurement:	; 1 bytes @ 0x33
	ds   1
	global	___fladd@aexp
___fladd@aexp:	; 1 bytes @ 0x34
	ds   1
	global	___fladd@bexp
___fladd@bexp:	; 1 bytes @ 0x35
	ds   1
	global	___fladd@grs
___fladd@grs:	; 1 bytes @ 0x36
	ds   1
	global	?___flmul
?___flmul:	; 4 bytes @ 0x37
	global	?___fltol
?___fltol:	; 4 bytes @ 0x37
	global	___fltol@f1
___fltol@f1:	; 4 bytes @ 0x37
	global	___flmul@b
___flmul@b:	; 4 bytes @ 0x37
	global	_report_measurement$1623
_report_measurement$1623:	; 4 bytes @ 0x37
	ds   4
	global	___flmul@a
___flmul@a:	; 4 bytes @ 0x3B
	global	_report_measurement$1624
_report_measurement$1624:	; 4 bytes @ 0x3B
??___fltol:	; 1 bytes @ 0x3B
	ds   4
	global	___fltol@sign1
___fltol@sign1:	; 1 bytes @ 0x3F
	global	_report_measurement$755
_report_measurement$755:	; 2 bytes @ 0x3F
??___flmul:	; 1 bytes @ 0x3F
	ds   1
	global	___fltol@exp1
___fltol@exp1:	; 1 bytes @ 0x40
	ds   1
	global	_report_measurement$760
_report_measurement$760:	; 2 bytes @ 0x41
	ds   2
	global	___flmul@sign
___flmul@sign:	; 1 bytes @ 0x43
	global	_report_measurement$770
_report_measurement$770:	; 2 bytes @ 0x43
	ds   1
	global	___flmul@grs
___flmul@grs:	; 4 bytes @ 0x44
	ds   1
	global	report_measurement@magnitude
report_measurement@magnitude:	; 4 bytes @ 0x45
	ds   3
	global	___flmul@aexp
___flmul@aexp:	; 1 bytes @ 0x48
	ds   1
	global	___flmul@bexp
___flmul@bexp:	; 1 bytes @ 0x49
	ds   1
	global	___flmul@prod
___flmul@prod:	; 4 bytes @ 0x4A
	ds   4
	global	___flmul@temp
___flmul@temp:	; 2 bytes @ 0x4E
	ds   2
	global	?___flsub
?___flsub:	; 4 bytes @ 0x50
	global	___flsub@b
___flsub@b:	; 4 bytes @ 0x50
	ds   4
	global	___flsub@a
___flsub@a:	; 4 bytes @ 0x54
	ds   4
	global	?_logf
?_logf:	; 4 bytes @ 0x58
	global	logf@x
logf@x:	; 4 bytes @ 0x58
??___flsub:	; 1 bytes @ 0x58
	ds   4
??_thermistor_centi_c:	; 1 bytes @ 0x5C
;!
;!Data Sizes:
;!    Strings     405
;!    Constant    24
;!    Data        0
;!    BSS         6
;!    Persistent  0
;!    Stack       0
;!
;!Auto Spaces:
;!    Space          Size  Autos    Used
;!    COMRAM           95     92      92
;!    BANK5           160    118     124
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
;!    can_send_oil_temperature@object	PTR volatile unsigned char  size(2) Largest target is 11775
;!		 -> RAM(DATA[11775]), 
;!
;!    report_measurement$755	PTR const unsigned char  size(2) Largest target is 9
;!		 -> STR_26(CODE[9]), STR_27(CODE[7]), 
;!
;!    report_measurement$760	PTR const unsigned char  size(2) Largest target is 9
;!		 -> STR_29(CODE[9]), STR_30(CODE[7]), 
;!
;!    report_measurement$770	PTR const unsigned char  size(2) Largest target is 7
;!		 -> STR_37(CODE[7]), STR_38(CODE[5]), 
;!
;!    uart_puts@text	PTR const unsigned char  size(2) Largest target is 101
;!		 -> STR_1(CODE[8]), STR_10(CODE[7]), STR_11(CODE[7]), STR_12(CODE[6]), 
;!		 -> STR_13(CODE[7]), STR_14(CODE[8]), STR_15(CODE[7]), STR_16(CODE[10]), 
;!		 -> STR_17(CODE[9]), STR_18(CODE[9]), STR_19(CODE[8]), STR_2(CODE[8]), 
;!		 -> STR_20(CODE[8]), STR_21(CODE[7]), STR_22(CODE[8]), STR_23(CODE[3]), 
;!		 -> STR_24(CODE[11]), STR_25(CODE[38]), STR_26(CODE[9]), STR_27(CODE[7]), 
;!		 -> STR_28(CODE[40]), STR_29(CODE[9]), STR_3(CODE[8]), STR_30(CODE[7]), 
;!		 -> STR_31(CODE[8]), STR_32(CODE[9]), STR_33(CODE[2]), STR_34(CODE[2]), 
;!		 -> STR_35(CODE[2]), STR_36(CODE[12]), STR_37(CODE[7]), STR_38(CODE[5]), 
;!		 -> STR_39(CODE[3]), STR_4(CODE[8]), STR_40(CODE[101]), STR_5(CODE[6]), 
;!		 -> STR_6(CODE[6]), STR_7(CODE[5]), STR_8(CODE[7]), STR_9(CODE[7]), 
;!


;!
;!Critical Paths under _main in COMRAM
;!
;!    _thermistor_centi_c->_logf
;!    _logf->___flsub
;!    ___flsub->___flmul
;!    ___fladd->___fldiv
;!    ___flmul->___fladd
;!    ___fldiv->___xxtofl
;!    ___fltol->___fladd
;!    _report_measurement->_uart_put_uint32
;!    _report_can_diagnostics->_uart_put_uint32
;!    _uart_put_uint32->___lldiv
;!    ___lldiv->___lmul
;!
;!Critical Paths under _main in BANK5
;!
;!    _main->_thermistor_centi_c
;!    _thermistor_centi_c->_logf
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
;;Main: autosize = 0, tempsize = 6, incstack = 0, save=0
;;

;!
;!Call Graph Tables:
;!
;! ---------------------------------------------------------------------------------
;! (Depth) Function   	        Calls       Base Space   Used Autos Params    Refs
;! ---------------------------------------------------------------------------------
;! (0) _main                                                18    18      0   16999
;!                                            100 BANK5     18    18      0
;!                            ___lldiv
;!                             ___lmul
;!                           _adc_init
;!                   _adc_read_average
;!                           _can_init
;!           _can_send_oil_temperature
;!             _report_can_diagnostics
;!                 _report_measurement
;!                 _thermistor_centi_c
;!                          _uart_init
;!                          _uart_puts
;! ---------------------------------------------------------------------------------
;! (1) _uart_init                                            0     0      0       0
;! ---------------------------------------------------------------------------------
;! (1) _thermistor_centi_c                                  36    32      4   13428
;!                                             64 BANK5     36    32      4
;!                            ___fladd
;!                            ___fldiv
;!                            ___flmul
;!                            ___fltol
;!                           ___xxtofl
;!                               _logf
;! ---------------------------------------------------------------------------------
;! (2) _logf                                                68    64      4    7999
;!                                             88 COMRAM     4     0      4
;!                                              0 BANK5     64    64      0
;!                            ___fladd
;!                            ___fldiv
;!                            ___flmul
;!                            ___flsub
;!                           ___xxtofl
;! ---------------------------------------------------------------------------------
;! (3) ___xxtofl                                            14    10      4     338
;!                                              0 COMRAM    14    10      4
;! ---------------------------------------------------------------------------------
;! (3) ___flsub                                              8     0      8    2057
;!                                             80 COMRAM     8     0      8
;!                            ___fladd
;!                            ___flmul (ARG)
;! ---------------------------------------------------------------------------------
;! (4) ___fladd                                             16     8      8    2008
;!                                             39 COMRAM    16     8      8
;!                            ___fldiv (ARG)
;!                           ___xxtofl (ARG)
;! ---------------------------------------------------------------------------------
;! (3) ___flmul                                             25    17      8    1492
;!                                             55 COMRAM    25    17      8
;!                            ___fladd (ARG)
;!                            ___fldiv (ARG)
;! ---------------------------------------------------------------------------------
;! (3) ___fldiv                                             25    17      8    1131
;!                                             14 COMRAM    25    17      8
;!                           ___xxtofl (ARG)
;! ---------------------------------------------------------------------------------
;! (2) ___fltol                                             10     6      4     230
;!                                             55 COMRAM    10     6      4
;!                            ___fladd (ARG)
;! ---------------------------------------------------------------------------------
;! (1) _report_measurement                                  33    22     11    1392
;!                                             40 COMRAM    33    22     11
;!                            ___lldiv
;!                            ___llmod
;!                    _uart_put_uint32
;!                          _uart_puts
;! ---------------------------------------------------------------------------------
;! (1) _report_can_diagnostics                               2     2      0     623
;!                                             40 COMRAM     2     2      0
;!                    _uart_put_uint32
;!                          _uart_puts
;! ---------------------------------------------------------------------------------
;! (2) _uart_puts                                            2     0      2      82
;!                                              0 COMRAM     2     0      2
;! ---------------------------------------------------------------------------------
;! (2) _uart_put_uint32                                     15    11      4     541
;!                                             25 COMRAM    15    11      4
;!                            ___lldiv
;!                            ___llmod
;! ---------------------------------------------------------------------------------
;! (3) ___llmod                                              9     1      8     165
;!                                              0 COMRAM     9     1      8
;! ---------------------------------------------------------------------------------
;! (3) ___lldiv                                             13     5      8     168
;!                                             12 COMRAM    13     5      8
;!                             ___lmul (ARG)
;! ---------------------------------------------------------------------------------
;! (1) _can_send_oil_temperature                            14     4     10     626
;!                                              0 COMRAM    14     4     10
;! ---------------------------------------------------------------------------------
;! (1) _can_init                                             0     0      0       0
;! ---------------------------------------------------------------------------------
;! (1) _adc_read_average                                    11     9      2      70
;!                                              0 COMRAM    11     9      2
;! ---------------------------------------------------------------------------------
;! (1) _adc_init                                             0     0      0       0
;! ---------------------------------------------------------------------------------
;! (1) ___lmul                                              12     4      8      94
;!                                              0 COMRAM    12     4      8
;! ---------------------------------------------------------------------------------
;! Estimated maximum stack depth 4
;! ---------------------------------------------------------------------------------
;!
;! Call Graph Graphs:
;!
;! _main (ROOT)
;!   ___lldiv
;!     ___lmul (ARG)
;!   ___lmul
;!   _adc_init
;!   _adc_read_average
;!   _can_init
;!   _can_send_oil_temperature
;!   _report_can_diagnostics
;!     _uart_put_uint32
;!       ___lldiv
;!       ___llmod
;!     _uart_puts
;!   _report_measurement
;!     ___lldiv
;!     ___llmod
;!     _uart_put_uint32
;!     _uart_puts
;!   _thermistor_centi_c
;!     ___fladd
;!       ___fldiv (ARG)
;!         ___xxtofl (ARG)
;!       ___xxtofl (ARG)
;!     ___fldiv
;!     ___flmul
;!       ___fladd (ARG)
;!       ___fldiv (ARG)
;!     ___fltol
;!       ___fladd (ARG)
;!     ___xxtofl
;!     _logf
;!       ___fladd
;!       ___fldiv
;!       ___flmul
;!       ___flsub
;!         ___fladd
;!         ___flmul (ARG)
;!       ___xxtofl
;!   _uart_init
;!   _uart_puts
;!

;!Address spaces:

;!Name               Size   Autos  Total    Usage
;!BIGRAM            8191      0       0      0.0%
;!BITBIGSFR_1       2304      0       0      0.0%
;!BITBIGSFRh         939      0       0      0.0%
;!BITBANK36          256      0       0      0.0%
;!BANK36             256      0       0      0.0%
;!BITBANK35          256      0       0      0.0%
;!BANK35             256      0       0      0.0%
;!BITBANK34          256      0       0      0.0%
;!BANK34             256      0       0      0.0%
;!BITBANK33          256      0       0      0.0%
;!BANK33             256      0       0      0.0%
;!BITBANK32          256      0       0      0.0%
;!BANK32             256      0       0      0.0%
;!BITBANK31          256      0       0      0.0%
;!BANK31             256      0       0      0.0%
;!BITBANK30          256      0       0      0.0%
;!BANK30             256      0       0      0.0%
;!BITBANK29          256      0       0      0.0%
;!BANK29             256      0       0      0.0%
;!BITBANK28          256      0       0      0.0%
;!BANK28             256      0       0      0.0%
;!BITBANK27          256      0       0      0.0%
;!BANK27             256      0       0      0.0%
;!BITBANK26          256      0       0      0.0%
;!BANK26             256      0       0      0.0%
;!BITBANK25          256      0       0      0.0%
;!BANK25             256      0       0      0.0%
;!BITBANK24          256      0       0      0.0%
;!BANK24             256      0       0      0.0%
;!BITBANK23          256      0       0      0.0%
;!BANK23             256      0       0      0.0%
;!BITBANK22          256      0       0      0.0%
;!BANK22             256      0       0      0.0%
;!BITBANK21          256      0       0      0.0%
;!BANK21             256      0       0      0.0%
;!BITBANK20          256      0       0      0.0%
;!BANK20             256      0       0      0.0%
;!BITBANK19          256      0       0      0.0%
;!BANK19             256      0       0      0.0%
;!BITBANK18          256      0       0      0.0%
;!BANK18             256      0       0      0.0%
;!BITBANK17          256      0       0      0.0%
;!BANK17             256      0       0      0.0%
;!BITBANK16          256      0       0      0.0%
;!BANK16             256      0       0      0.0%
;!BITBANK15          256      0       0      0.0%
;!BANK15             256      0       0      0.0%
;!BITBANK14          256      0       0      0.0%
;!BANK14             256      0       0      0.0%
;!BITBANK13          256      0       0      0.0%
;!BANK13             256      0       0      0.0%
;!BITBANK12          256      0       0      0.0%
;!BANK12             256      0       0      0.0%
;!BITBANK11          256      0       0      0.0%
;!BANK11             256      0       0      0.0%
;!BITBANK10          256      0       0      0.0%
;!BANK10             256      0       0      0.0%
;!BITBANK9           256      0       0      0.0%
;!BANK9              256      0       0      0.0%
;!BITBANK8           256      0       0      0.0%
;!BANK8              256      0       0      0.0%
;!BITBANK7           256      0       0      0.0%
;!BANK7              256      0       0      0.0%
;!BITBANK6           256      0       0      0.0%
;!BANK6              256      0       0      0.0%
;!BITBANK5           160      0       0      0.0%
;!BANK5              160    118     124     77.5%
;!BITBIGSFRllh       157      0       0      0.0%
;!BITBIGSFRlll        98      0       0      0.0%
;!BITCOMRAM           95      0       0      0.0%
;!COMRAM              95     92      92     96.8%
;!BITBIGSFRlh         82      0       0      0.0%
;!STACK                0      0       0      0.0%
;!DATA                 0      0     216      0.0%

	global	_main

;; *************** function _main *****************
;; Defined at:
;;		line 320 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;		None
;; Auto vars:     Size  Location     Type
;;  resistance      4  112[BANK5 ] unsigned long 
;;  centi_c         4  106[BANK5 ] long 
;;  adc             2  116[BANK5 ] unsigned short 
;;  cycle           1  111[BANK5 ] unsigned char 
;;  sent            1  110[BANK5 ] unsigned char 
;; Return value:  Size  Location     Type
;;                  1    wreg      void 
;; Registers used:
;;		wreg, fsr2l, fsr2h, status,2, status,0, tblptrl, tblptrh, tblptru, prodl, prodh, cstack
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         0      12       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          0       6       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:         0      18       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       18 bytes
;; Hardware stack levels required when called: 4
;; This function calls:
;;		___lldiv
;;		___lmul
;;		_adc_init
;;		_adc_read_average
;;		_can_init
;;		_can_send_oil_temperature
;;		_report_can_diagnostics
;;		_report_measurement
;;		_thermistor_centi_c
;;		_uart_init
;;		_uart_puts
;; This function is called by:
;;		Startup code after reset
;; This function uses a non-reentrant model
;;
psect	text0,class=CODE,space=0,reloc=2,group=0
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	320
global __ptext0
__ptext0:
psect	text0
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	320
	
_main:
;incstack = 0
	callstack 123
	line	322
	
l3150:
	call	_uart_init	;wreg free
	line	323
	
l3152:
	call	_adc_init	;wreg free
	line	324
	
l3154:
	call	_can_init	;wreg free
	line	325
	
l3156:
		movlw	low(STR_40)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_40)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	329
	
l3158:
	line	330
	
l3160:
	movlb	5	; () banked
	clrf	((main@cycle))&0ffh
	line	331
	
l3166:; BSR set to: 5

	call	_adc_read_average	;wreg free
	movff	0+?_adc_read_average,(main@adc)
	movff	1+?_adc_read_average,(main@adc+1)
	line	335
	
l3168:
	movlb	5	; () banked
		movf	((main@adc+1))&0ffh,w
	bnz	u2830
	movlw	5
	subwf	 ((main@adc))&0ffh,w
	btfss	status,0
	goto	u2831
	goto	u2830

u2831:
	goto	l3172
u2830:
	
l3170:; BSR set to: 5

		movlw	251
	subwf	 ((main@adc))&0ffh,w
	movlw	15
	subwfb	((main@adc+1))&0ffh,w
	btfss	status,0
	goto	u2841
	goto	u2840

u2841:
	goto	l3182
u2840:
	line	338
	
l3172:; BSR set to: 5

		movlw	251
	subwf	 ((main@adc))&0ffh,w
	movlw	15
	subwfb	((main@adc+1))&0ffh,w
	btfsc	status,0
	goto	u2851
	goto	u2850

u2851:
	goto	l238
u2850:
	
l3174:; BSR set to: 5

	movlw	low(0)
	movwf	((main@resistance))&0ffh
	movlw	high(0)
	movwf	((main@resistance+1))&0ffh
	movlw	low highword(0)
	movwf	((main@resistance+2))&0ffh
	movlw	high highword(0)
	movwf	((main@resistance+3))&0ffh
	goto	l3176
	
l238:; BSR set to: 5

	setf	((main@resistance))&0ffh
	setf	((main@resistance+1))&0ffh
	setf	((main@resistance+2))&0ffh
	setf	((main@resistance+3))&0ffh
	line	339
	
l3176:; BSR set to: 5

	movlw	low(-32768)
	movwf	((c:can_send_oil_temperature@centi_c))^0500h,c
	movlw	high(-32768)
	movwf	((c:can_send_oil_temperature@centi_c+1))^0500h,c
	movlw	low highword(-32768)
	movwf	((c:can_send_oil_temperature@centi_c+2))^0500h,c
	movlw	high highword(-32768)
	movwf	((c:can_send_oil_temperature@centi_c+3))^0500h,c
	movff	(main@adc),(c:can_send_oil_temperature@adc)
	movff	(main@adc+1),(c:can_send_oil_temperature@adc+1)
	movff	(main@resistance),(c:can_send_oil_temperature@resistance)
	movff	(main@resistance+1),(c:can_send_oil_temperature@resistance+1)
	movff	(main@resistance+2),(c:can_send_oil_temperature@resistance+2)
	movff	(main@resistance+3),(c:can_send_oil_temperature@resistance+3)
	call	_can_send_oil_temperature	;wreg free
	movlb	5	; () banked
	movwf	((main@sent))&0ffh
	line	340
	
l3178:; BSR set to: 5

		movlw	4
	xorwf	((main@cycle))&0ffh,w
	btfss	status,2
	goto	u2861
	goto	u2860

u2861:
	goto	l3192
u2860:
	line	341
	
l3180:; BSR set to: 5

	movff	(main@adc),(c:report_measurement@adc)
	movff	(main@adc+1),(c:report_measurement@adc+1)
	movff	(main@resistance),(c:report_measurement@resistance)
	movff	(main@resistance+1),(c:report_measurement@resistance+1)
	movff	(main@resistance+2),(c:report_measurement@resistance+2)
	movff	(main@resistance+3),(c:report_measurement@resistance+3)
	movlw	low(-32768)
	movwf	((c:report_measurement@centi_c))^0500h,c
	movlw	high(-32768)
	movwf	((c:report_measurement@centi_c+1))^0500h,c
	movlw	low highword(-32768)
	movwf	((c:report_measurement@centi_c+2))^0500h,c
	movlw	high highword(-32768)
	movwf	((c:report_measurement@centi_c+3))^0500h,c
	movff	(main@sent),(c:report_measurement@can_sent)
	call	_report_measurement	;wreg free
	goto	l3192
	line	344
	
l3182:; BSR set to: 5

	movlw	low(0FFFh)
	movwf	(??_main+0)&0ffh
	movlw	high(0FFFh)
	movwf	1+(??_main+0)&0ffh
	movf	((main@adc))&0ffh,w
	subwf	(??_main+0)&0ffh
	movf	((main@adc+1))&0ffh,w
	subwfb	(??_main+0+1)&0ffh
	bcf	status,0
	rrcf	(??_main+0+1)&0ffh,w
	movwf	(??_main+2+1)&0ffh
	rrcf	(??_main+0)&0ffh,w
	movwf	(??_main+2)&0ffh
	movff	(main@adc),(c:___lmul@multiplier)
	movff	(main@adc+1),(c:___lmul@multiplier+1)
	clrf	((c:___lmul@multiplier+2))^0500h,c
	clrf	((c:___lmul@multiplier+3))^0500h,c
	movlw	low(02710h)
	movwf	((c:___lmul@multiplicand))^0500h,c
	movlw	high(02710h)
	movwf	((c:___lmul@multiplicand+1))^0500h,c
	movlw	low highword(02710h)
	movwf	((c:___lmul@multiplicand+2))^0500h,c
	movlw	high highword(02710h)
	movwf	((c:___lmul@multiplicand+3))^0500h,c
	call	___lmul	;wreg free
	movlb	5	; () banked
	movf	(??_main+2)&0ffh,w
	addwf	(0+?___lmul)^0500h,c,w
	movwf	((c:___lldiv@dividend))^0500h,c
	movf	(??_main+2+1)&0ffh,w
	addwfc	(1+?___lmul)^0500h,c,w
	movwf	1+((c:___lldiv@dividend))^0500h,c
	
	movlw	0
	addwfc	(2+?___lmul)^0500h,c,w
	movwf	2+((c:___lldiv@dividend))^0500h,c
	
	movlw	0
	addwfc	(3+?___lmul)^0500h,c,w
	movwf	3+((c:___lldiv@dividend))^0500h,c
	movlw	low(0FFFh)
	movwf	(??_main+4)&0ffh
	movlw	high(0FFFh)
	movwf	1+(??_main+4)&0ffh
	movf	((main@adc))&0ffh,w
	subwf	(??_main+4)&0ffh
	movf	((main@adc+1))&0ffh,w
	subwfb	(??_main+4+1)&0ffh
	movff	??_main+4,(c:___lldiv@divisor)
	movff	??_main+4+1,(c:___lldiv@divisor+1)
	clrf	((c:___lldiv@divisor+2))^0500h,c
	clrf	((c:___lldiv@divisor+3))^0500h,c
	call	___lldiv	;wreg free
	movff	0+?___lldiv,(main@resistance)
	movff	1+?___lldiv,(main@resistance+1)
	movff	2+?___lldiv,(main@resistance+2)
	movff	3+?___lldiv,(main@resistance+3)
	
	line	346
	
l3184:
	movff	(main@resistance),(thermistor_centi_c@resistance_ohm)
	movff	(main@resistance+1),(thermistor_centi_c@resistance_ohm+1)
	movff	(main@resistance+2),(thermistor_centi_c@resistance_ohm+2)
	movff	(main@resistance+3),(thermistor_centi_c@resistance_ohm+3)
	call	_thermistor_centi_c	;wreg free
	movff	0+?_thermistor_centi_c,(main@centi_c)
	movff	1+?_thermistor_centi_c,(main@centi_c+1)
	movff	2+?_thermistor_centi_c,(main@centi_c+2)
	movff	3+?_thermistor_centi_c,(main@centi_c+3)
	
	line	347
	
l3186:
	movff	(main@centi_c),(c:can_send_oil_temperature@centi_c)
	movff	(main@centi_c+1),(c:can_send_oil_temperature@centi_c+1)
	movff	(main@centi_c+2),(c:can_send_oil_temperature@centi_c+2)
	movff	(main@centi_c+3),(c:can_send_oil_temperature@centi_c+3)
	movff	(main@adc),(c:can_send_oil_temperature@adc)
	movff	(main@adc+1),(c:can_send_oil_temperature@adc+1)
	movff	(main@resistance),(c:can_send_oil_temperature@resistance)
	movff	(main@resistance+1),(c:can_send_oil_temperature@resistance+1)
	movff	(main@resistance+2),(c:can_send_oil_temperature@resistance+2)
	movff	(main@resistance+3),(c:can_send_oil_temperature@resistance+3)
	call	_can_send_oil_temperature	;wreg free
	movlb	5	; () banked
	movwf	((main@sent))&0ffh
	line	348
	
l3188:; BSR set to: 5

		movlw	4
	xorwf	((main@cycle))&0ffh,w
	btfss	status,2
	goto	u2871
	goto	u2870

u2871:
	goto	l3192
u2870:
	line	349
	
l3190:; BSR set to: 5

	movff	(main@adc),(c:report_measurement@adc)
	movff	(main@adc+1),(c:report_measurement@adc+1)
	movff	(main@resistance),(c:report_measurement@resistance)
	movff	(main@resistance+1),(c:report_measurement@resistance+1)
	movff	(main@resistance+2),(c:report_measurement@resistance+2)
	movff	(main@resistance+3),(c:report_measurement@resistance+3)
	movff	(main@centi_c),(c:report_measurement@centi_c)
	movff	(main@centi_c+1),(c:report_measurement@centi_c+1)
	movff	(main@centi_c+2),(c:report_measurement@centi_c+2)
	movff	(main@centi_c+3),(c:report_measurement@centi_c+3)
	movff	(main@sent),(c:report_measurement@can_sent)
	call	_report_measurement	;wreg free
	line	352
	
l3192:
	asmopt push
asmopt off
movlw  9
	movlb	5	; () banked
movwf	(??_main+0+1)&0ffh
movlw	30
movwf	(??_main+0)&0ffh
	movlw	228
u2897:
decfsz	wreg,f
	bra	u2897
	decfsz	(??_main+0)&0ffh,f
	bra	u2897
	decfsz	(??_main+0+1)&0ffh,f
	bra	u2897
	nop
asmopt pop

	line	330
	
l3194:
	movlb	5	; () banked
	incf	((main@cycle))&0ffh
	
l3196:; BSR set to: 5

		movlw	05h-1
	cpfsgt	((main@cycle))&0ffh
	goto	u2881
	goto	u2880

u2881:
	goto	l3166
u2880:
	line	354
	
l3198:; BSR set to: 5

	call	_report_can_diagnostics	;wreg free
	goto	l3158
	global	start
	goto	start
	callstack 0
	line	356
GLOBAL	__end_of_main
	__end_of_main:
	signat	_main,89
	global	_uart_init

;; *************** function _uart_init *****************
;; Defined at:
;;		line 90 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
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
	line	90
global __ptext1
__ptext1:
psect	text1
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	90
	
_uart_init:
;incstack = 0
	callstack 126
	line	92
	
l2822:
	movlb	4	; () banked
	bcf	(0+(0/8)+(1024))&0ffh,(0)&7	;volatile
	line	93
	bcf	(0+(0/8)+(c:1214))^0400h,c,(0)&7	;volatile
	line	94
	bcf	(0+(0/8)+(c:1222))^0400h,c,(0)&7	;volatile
	line	96
	
l2824:; BSR set to: 4

	movlb	0	; () banked
	bcf	((102))&0ffh,3	;volatile
	line	97
	
l2826:; BSR set to: 0

	movlw	(03Fh)&0ffh
	movlb	4	; () banked
	andwf	((1040))&0ffh	;volatile
	line	98
	
l2828:; BSR set to: 4

	bsf	((c:1216))^0400h,c,6	;volatile
	line	99
	
l2830:; BSR set to: 4

	bcf	((1042))&0ffh,6	;volatile
	line	100
	
l2832:; BSR set to: 4

	bcf	((c:1224))^0400h,c,6	;volatile
	line	101
	
l2834:; BSR set to: 4

	bsf	((c:1224))^0400h,c,7	;volatile
	line	104
	
l2836:; BSR set to: 4

	movlw	low(055h)
	movlb	2	; () banked
	movwf	((512))&0ffh	;volsfr
	line	105
	
l2838:; BSR set to: 2

	movlw	low(0AAh)
	movwf	((512))&0ffh	;volsfr
	line	106
	
l2840:; BSR set to: 2

	bcf	((512))&0ffh,0	;volsfr
	line	107
	
l2842:; BSR set to: 2

	movlw	low(020h)
	movwf	((535))&0ffh	;volatile
	line	108
	
l2844:; BSR set to: 2

	movlw	low(017h)
	movwf	((626))&0ffh	;volatile
	line	109
	
l2846:; BSR set to: 2

	movlw	low(046h)
	movwf	((523))&0ffh	;volatile
	line	110
	
l2848:; BSR set to: 2

	movlw	low(0Bh)
	movwf	((573))&0ffh	;volatile
	line	111
	
l2850:; BSR set to: 2

	movlw	low(055h)
	movwf	((512))&0ffh	;volsfr
	line	112
	
l2852:; BSR set to: 2

	movlw	low(0AAh)
	movwf	((512))&0ffh	;volsfr
	line	113
	
l2854:; BSR set to: 2

	bsf	((512))&0ffh,0	;volsfr
	line	115
	
l2856:; BSR set to: 2

	clrf	((684))&0ffh	;volatile
	line	116
	
l2858:; BSR set to: 2

	movlw	low(0B0h)
	movwf	((683))&0ffh	;volatile
	line	117
	
l2860:; BSR set to: 2

	movlw	low(080h)
	movwf	((685))&0ffh	;volatile
	line	118
	
l2862:; BSR set to: 2

	clrf	((686+1))&0ffh	;volatile
	movlw	low(08Ah)
	movwf	((686))&0ffh	;volatile
	line	119
	
l2864:; BSR set to: 2

	bsf	((684))&0ffh,7	;volatile
	line	120
	
l143:; BSR set to: 2

	return	;funcret
	callstack 0
GLOBAL	__end_of_uart_init
	__end_of_uart_init:
	signat	_uart_init,89
	global	_thermistor_centi_c

;; *************** function _thermistor_centi_c *****************
;; Defined at:
;;		line 272 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;  resistance_o    4   64[BANK5 ] unsigned long 
;; Auto vars:     Size  Location     Type
;;  centi_c         4   96[BANK5 ] unsigned long 
;;  inverse_kelv    4   80[BANK5 ] unsigned long 
;;  beta_kelvin     4   76[BANK5 ] const 
;;  hot_resistan    4   72[BANK5 ] const 
;;  hot_kelvin      4   68[BANK5 ] const 
;; Return value:  Size  Location     Type
;;                  4   64[BANK5 ] long 
;; Registers used:
;;		wreg, status,2, status,0, prodl, prodh, cstack
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         0       4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         0      32       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:         0      36       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       36 bytes
;; Hardware stack levels used: 1
;; Hardware stack levels required when called: 3
;; This function calls:
;;		___fladd
;;		___fldiv
;;		___flmul
;;		___fltol
;;		___xxtofl
;;		_logf
;; This function is called by:
;;		_main
;; This function uses a non-reentrant model
;;
psect	text2,class=CODE,space=0,reloc=2,group=0
	line	272
global __ptext2
__ptext2:
psect	text2
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	272
	
_thermistor_centi_c:; BSR set to: 2

;incstack = 0
	callstack 123
	line	274
	
l3046:
	movlw	low(normalize32(0x43b91333))
	movlb	5	; () banked
	movwf	((thermistor_centi_c@hot_kelvin))&0ffh
	movlw	high(normalize32(0x43b91333))
	movwf	((thermistor_centi_c@hot_kelvin+1))&0ffh
	movlw	low highword(normalize32(0x43b91333))
	movwf	((thermistor_centi_c@hot_kelvin+2))&0ffh
	movlw	high highword(normalize32(0x43b91333))
	movwf	((thermistor_centi_c@hot_kelvin+3))&0ffh
	line	275
	movlw	low(normalize32(0x448f2000))
	movwf	((thermistor_centi_c@hot_resistance))&0ffh
	movlw	high(normalize32(0x448f2000))
	movwf	((thermistor_centi_c@hot_resistance+1))&0ffh
	movlw	low highword(normalize32(0x448f2000))
	movwf	((thermistor_centi_c@hot_resistance+2))&0ffh
	movlw	high highword(normalize32(0x448f2000))
	movwf	((thermistor_centi_c@hot_resistance+3))&0ffh
	line	276
	movlw	low(normalize32(0x454c744f))
	movwf	((thermistor_centi_c@beta_kelvin))&0ffh
	movlw	high(normalize32(0x454c744f))
	movwf	((thermistor_centi_c@beta_kelvin+1))&0ffh
	movlw	low highword(normalize32(0x454c744f))
	movwf	((thermistor_centi_c@beta_kelvin+2))&0ffh
	movlw	high highword(normalize32(0x454c744f))
	movwf	((thermistor_centi_c@beta_kelvin+3))&0ffh
	line	280
	
l3048:; BSR set to: 5

	movff	(thermistor_centi_c@hot_resistance),(c:___fldiv@a)
	movff	(thermistor_centi_c@hot_resistance+1),(c:___fldiv@a+1)
	movff	(thermistor_centi_c@hot_resistance+2),(c:___fldiv@a+2)
	movff	(thermistor_centi_c@hot_resistance+3),(c:___fldiv@a+3)
	movff	(thermistor_centi_c@resistance_ohm),(c:___xxtofl@val)
	movff	(thermistor_centi_c@resistance_ohm+1),(c:___xxtofl@val+1)
	movff	(thermistor_centi_c@resistance_ohm+2),(c:___xxtofl@val+2)
	movff	(thermistor_centi_c@resistance_ohm+3),(c:___xxtofl@val+3)
	movlw	(0)&0ffh
	
	call	___xxtofl
	movff	0+?___xxtofl,(c:___fldiv@b)
	movff	1+?___xxtofl,(c:___fldiv@b+1)
	movff	2+?___xxtofl,(c:___fldiv@b+2)
	movff	3+?___xxtofl,(c:___fldiv@b+3)
	
	call	___fldiv	;wreg free
	movff	0+?___fldiv,(_thermistor_centi_c$1621)
	movff	1+?___fldiv,(_thermistor_centi_c$1621+1)
	movff	2+?___fldiv,(_thermistor_centi_c$1621+2)
	movff	3+?___fldiv,(_thermistor_centi_c$1621+3)
	
	
l3050:
	movff	(_thermistor_centi_c$1621),(c:logf@x)
	movff	(_thermistor_centi_c$1621+1),(c:logf@x+1)
	movff	(_thermistor_centi_c$1621+2),(c:logf@x+2)
	movff	(_thermistor_centi_c$1621+3),(c:logf@x+3)
	call	_logf	;wreg free
	movff	0+?_logf,(_thermistor_centi_c$1622)
	movff	1+?_logf,(_thermistor_centi_c$1622+1)
	movff	2+?_logf,(_thermistor_centi_c$1622+2)
	movff	3+?_logf,(_thermistor_centi_c$1622+3)
	
	
l3052:
	movff	(thermistor_centi_c@hot_kelvin),(c:___fldiv@a)
	movff	(thermistor_centi_c@hot_kelvin+1),(c:___fldiv@a+1)
	movff	(thermistor_centi_c@hot_kelvin+2),(c:___fldiv@a+2)
	movff	(thermistor_centi_c@hot_kelvin+3),(c:___fldiv@a+3)
	movlw	low(normalize32(0x3f800000))
	movwf	((c:___fldiv@b))^0500h,c
	movlw	high(normalize32(0x3f800000))
	movwf	((c:___fldiv@b+1))^0500h,c
	movlw	low highword(normalize32(0x3f800000))
	movwf	((c:___fldiv@b+2))^0500h,c
	movlw	high highword(normalize32(0x3f800000))
	movwf	((c:___fldiv@b+3))^0500h,c
	call	___fldiv	;wreg free
	movff	0+?___fldiv,(c:___fladd@b)
	movff	1+?___fldiv,(c:___fladd@b+1)
	movff	2+?___fldiv,(c:___fladd@b+2)
	movff	3+?___fldiv,(c:___fladd@b+3)
	
	movff	(thermistor_centi_c@beta_kelvin),(c:___fldiv@a)
	movff	(thermistor_centi_c@beta_kelvin+1),(c:___fldiv@a+1)
	movff	(thermistor_centi_c@beta_kelvin+2),(c:___fldiv@a+2)
	movff	(thermistor_centi_c@beta_kelvin+3),(c:___fldiv@a+3)
	movff	(_thermistor_centi_c$1622),(c:___fldiv@b)
	movff	(_thermistor_centi_c$1622+1),(c:___fldiv@b+1)
	movff	(_thermistor_centi_c$1622+2),(c:___fldiv@b+2)
	movff	(_thermistor_centi_c$1622+3),(c:___fldiv@b+3)
	call	___fldiv	;wreg free
	movff	0+?___fldiv,(c:___fladd@a)
	movff	1+?___fldiv,(c:___fladd@a+1)
	movff	2+?___fldiv,(c:___fladd@a+2)
	movff	3+?___fldiv,(c:___fladd@a+3)
	
	call	___fladd	;wreg free
	movff	0+?___fladd,(thermistor_centi_c@inverse_kelvin)
	movff	1+?___fladd,(thermistor_centi_c@inverse_kelvin+1)
	movff	2+?___fladd,(thermistor_centi_c@inverse_kelvin+2)
	movff	3+?___fladd,(thermistor_centi_c@inverse_kelvin+3)
	
	line	282
	
l3054:
	movlw	low(normalize32(0xc3889333))
	movwf	((c:___fladd@a))^0500h,c
	movlw	high(normalize32(0xc3889333))
	movwf	((c:___fladd@a+1))^0500h,c
	movlw	low highword(normalize32(0xc3889333))
	movwf	((c:___fladd@a+2))^0500h,c
	movlw	high highword(normalize32(0xc3889333))
	movwf	((c:___fladd@a+3))^0500h,c
	movff	(thermistor_centi_c@inverse_kelvin),(c:___fldiv@a)
	movff	(thermistor_centi_c@inverse_kelvin+1),(c:___fldiv@a+1)
	movff	(thermistor_centi_c@inverse_kelvin+2),(c:___fldiv@a+2)
	movff	(thermistor_centi_c@inverse_kelvin+3),(c:___fldiv@a+3)
	movlw	low(normalize32(0x3f800000))
	movwf	((c:___fldiv@b))^0500h,c
	movlw	high(normalize32(0x3f800000))
	movwf	((c:___fldiv@b+1))^0500h,c
	movlw	low highword(normalize32(0x3f800000))
	movwf	((c:___fldiv@b+2))^0500h,c
	movlw	high highword(normalize32(0x3f800000))
	movwf	((c:___fldiv@b+3))^0500h,c
	call	___fldiv	;wreg free
	movff	0+?___fldiv,(c:___fladd@b)
	movff	1+?___fldiv,(c:___fladd@b+1)
	movff	2+?___fldiv,(c:___fladd@b+2)
	movff	3+?___fldiv,(c:___fladd@b+3)
	
	call	___fladd	;wreg free
	movff	0+?___fladd,(c:___flmul@b)
	movff	1+?___fladd,(c:___flmul@b+1)
	movff	2+?___fladd,(c:___flmul@b+2)
	movff	3+?___fladd,(c:___flmul@b+3)
	
	movlw	low(normalize32(0x42c80000))
	movwf	((c:___flmul@a))^0500h,c
	movlw	high(normalize32(0x42c80000))
	movwf	((c:___flmul@a+1))^0500h,c
	movlw	low highword(normalize32(0x42c80000))
	movwf	((c:___flmul@a+2))^0500h,c
	movlw	high highword(normalize32(0x42c80000))
	movwf	((c:___flmul@a+3))^0500h,c
	call	___flmul	;wreg free
	movff	0+?___flmul,(thermistor_centi_c@centi_c)
	movff	1+?___flmul,(thermistor_centi_c@centi_c+1)
	movff	2+?___flmul,(thermistor_centi_c@centi_c+2)
	movff	3+?___flmul,(thermistor_centi_c@centi_c+3)
	
	line	283
	
l3056:
	movlb	5	; () banked
	btfsc	((thermistor_centi_c@centi_c+3))&0ffh,7
	goto	u2720
	goto	u2721

u2721:
	goto	l3060
u2720:
	
l3058:; BSR set to: 5

	movlw	low(normalize32(0xbf000000))
	movwf	((_thermistor_centi_c$743))&0ffh
	movlw	high(normalize32(0xbf000000))
	movwf	((_thermistor_centi_c$743+1))&0ffh
	movlw	low highword(normalize32(0xbf000000))
	movwf	((_thermistor_centi_c$743+2))&0ffh
	movlw	high highword(normalize32(0xbf000000))
	movwf	((_thermistor_centi_c$743+3))&0ffh
	goto	l3062
	
l3060:; BSR set to: 5

	movlw	low(normalize32(0x3f000000))
	movwf	((_thermistor_centi_c$743))&0ffh
	movlw	high(normalize32(0x3f000000))
	movwf	((_thermistor_centi_c$743+1))&0ffh
	movlw	low highword(normalize32(0x3f000000))
	movwf	((_thermistor_centi_c$743+2))&0ffh
	movlw	high highword(normalize32(0x3f000000))
	movwf	((_thermistor_centi_c$743+3))&0ffh
	
l3062:; BSR set to: 5

	movff	(thermistor_centi_c@centi_c),(c:___fladd@a)
	movff	(thermistor_centi_c@centi_c+1),(c:___fladd@a+1)
	movff	(thermistor_centi_c@centi_c+2),(c:___fladd@a+2)
	movff	(thermistor_centi_c@centi_c+3),(c:___fladd@a+3)
	movff	(_thermistor_centi_c$743),(c:___fladd@b)
	movff	(_thermistor_centi_c$743+1),(c:___fladd@b+1)
	movff	(_thermistor_centi_c$743+2),(c:___fladd@b+2)
	movff	(_thermistor_centi_c$743+3),(c:___fladd@b+3)
	call	___fladd	;wreg free
	movff	0+?___fladd,(c:___fltol@f1)
	movff	1+?___fladd,(c:___fltol@f1+1)
	movff	2+?___fladd,(c:___fltol@f1+2)
	movff	3+?___fladd,(c:___fltol@f1+3)
	
	call	___fltol	;wreg free
	movff	0+?___fltol,(?_thermistor_centi_c)
	movff	1+?___fltol,(?_thermistor_centi_c+1)
	movff	2+?___fltol,(?_thermistor_centi_c+2)
	movff	3+?___fltol,(?_thermistor_centi_c+3)
	
	line	284
	
l203:
	return	;funcret
	callstack 0
GLOBAL	__end_of_thermistor_centi_c
	__end_of_thermistor_centi_c:
	signat	_thermistor_centi_c,4220
	global	_logf

;; *************** function _logf *****************
;; Defined at:
;;		line 29 in file "C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\logf.c"
;; Parameters:    Size  Location     Type
;;  x               4   88[COMRAM] float 
;; Auto vars:     Size  Location     Type
;;  ux              4   60[BANK5 ] struct .
;;  w               4   52[BANK5 ] float 
;;  z               4   48[BANK5 ] float 
;;  s               4   44[BANK5 ] float 
;;  dk              4   40[BANK5 ] float 
;;  hfsq            4   36[BANK5 ] float 
;;  t2              4   14[BANK5 ] float 
;;  t1              4   10[BANK5 ] float 
;;  R               4    6[BANK5 ] float 
;;  k               2   34[BANK5 ] int 
;; Return value:  Size  Location     Type
;;                  4   88[COMRAM] float 
;; Registers used:
;;		wreg, status,2, status,0, prodl, prodh, cstack
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         0      58       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          0       6       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:         4      64       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       68 bytes
;; Hardware stack levels used: 1
;; Hardware stack levels required when called: 2
;; This function calls:
;;		___fladd
;;		___fldiv
;;		___flmul
;;		___flsub
;;		___xxtofl
;; This function is called by:
;;		_thermistor_centi_c
;; This function uses a non-reentrant model
;;
psect	text3,class=CODE,space=0,reloc=2,group=2
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\logf.c"
	line	29
global __ptext3
__ptext3:
psect	text3
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\logf.c"
	line	29
	
_logf:
;incstack = 0
	callstack 123
	line	31
	
l2702:
	movff	(logf@F472),(logf@ux)
	movff	(logf@F472+1),(logf@ux+1)
	movff	(logf@F472+2),(logf@ux+2)
	movff	(logf@F472+3),(logf@ux+3)
	movff	(c:logf@x),(logf@ux)
	movff	(c:logf@x+1),(logf@ux+1)
	movff	(c:logf@x+2),(logf@ux+2)
	movff	(c:logf@x+3),(logf@ux+3)
	line	35
	
l2704:
	movlb	5	; () banked
	clrf	((logf@k+1))&0ffh
	movlw	low(0)
	movwf	((logf@k))&0ffh
	line	36
	
l2706:; BSR set to: 5

		movf	((logf@ux+3))&0ffh,w
	bnz	u2470
	movlw	128
	subwf	 ((logf@ux+2))&0ffh,w
	btfss	status,0
	goto	u2471
	goto	u2470

u2471:
	goto	l2710
u2470:
	
l2708:; BSR set to: 5

	
	btfss	((logf@ux+3))&0ffh,(31)&7
	goto	u2481
	goto	u2480
u2481:
	goto	l2728
u2480:
	line	37
	
l2710:; BSR set to: 5

	bcf	status,0
	rlcf	((logf@ux))&0ffh,w
	movwf	(??_logf+0)&0ffh
	rlcf	((logf@ux+1))&0ffh,w
	movwf	1+(??_logf+0)&0ffh
	
	rlcf	((logf@ux+2))&0ffh,w
	movwf	2+(??_logf+0)&0ffh
	
	rlcf	((logf@ux+3))&0ffh,w
	movwf	3+(??_logf+0)&0ffh
	movf	(??_logf+0)&0ffh,w
iorwf	(??_logf+0+1)&0ffh,w
iorwf	(??_logf+0+2)&0ffh,w
iorwf	(??_logf+0+3)&0ffh,w
	btfss	status,2
	goto	u2491
	goto	u2490

u2491:
	goto	l1052
u2490:
	line	39
	
l2712:; BSR set to: 5

	movlw	low(0FF800000h)
	movwf	((logf@ux))&0ffh
	movlw	high(0FF800000h)
	movwf	((logf@ux+1))&0ffh
	movlw	low highword(0FF800000h)
	movwf	((logf@ux+2))&0ffh
	movlw	high highword(0FF800000h)
	movwf	((logf@ux+3))&0ffh
	line	40
	
l2714:; BSR set to: 5

	movff	(logf@ux),(c:?_logf)
	movff	(logf@ux+1),(c:?_logf+1)
	movff	(logf@ux+2),(c:?_logf+2)
	movff	(logf@ux+3),(c:?_logf+3)
	goto	l1053
	line	44
	
l1052:; BSR set to: 5

	line	45
	
	btfss	((logf@ux+3))&0ffh,(31)&7
	goto	u2501
	goto	u2500
u2501:
	goto	l2724
u2500:
	line	47
	
l2718:; BSR set to: 5

	clrf	((_errno+1))&0ffh
	movlw	low(021h)
	movwf	((_errno))&0ffh
	line	48
	movlw	low(07FFFFFFFh)
	movwf	((logf@ux))&0ffh
	movlw	high(07FFFFFFFh)
	movwf	((logf@ux+1))&0ffh
	movlw	low highword(07FFFFFFFh)
	movwf	((logf@ux+2))&0ffh
	movlw	high highword(07FFFFFFFh)
	movwf	((logf@ux+3))&0ffh
	goto	l2714
	line	55
	
l2724:; BSR set to: 5

	movlw	low(-25)
	addwf	((logf@k))&0ffh
	movlw	high(-25)
	addwfc	((logf@k+1))&0ffh
	line	56
	
l2726:; BSR set to: 5

	movff	(logf@ux),(c:___flmul@b)
	movff	(logf@ux+1),(c:___flmul@b+1)
	movff	(logf@ux+2),(c:___flmul@b+2)
	movff	(logf@ux+3),(c:___flmul@b+3)
	movlw	low(normalize32(0x4c000000))
	movwf	((c:___flmul@a))^0500h,c
	movlw	high(normalize32(0x4c000000))
	movwf	((c:___flmul@a+1))^0500h,c
	movlw	low highword(normalize32(0x4c000000))
	movwf	((c:___flmul@a+2))^0500h,c
	movlw	high highword(normalize32(0x4c000000))
	movwf	((c:___flmul@a+3))^0500h,c
	call	___flmul	;wreg free
	movff	0+?___flmul,(logf@ux)
	movff	1+?___flmul,(logf@ux+1)
	movff	2+?___flmul,(logf@ux+2)
	movff	3+?___flmul,(logf@ux+3)
	
	line	57
	goto	l2740
	
l2728:; BSR set to: 5

		movlw	128
	subwf	 ((logf@ux+2))&0ffh,w
	movlw	127
	subwfb	((logf@ux+3))&0ffh,w
	btfss	status,0
	goto	u2511
	goto	u2510

u2511:
	goto	l2734
u2510:
	line	58
	
l2730:; BSR set to: 5

	movff	(c:logf@x),(c:?_logf)
	movff	(c:logf@x+1),(c:?_logf+1)
	movff	(c:logf@x+2),(c:?_logf+2)
	movff	(c:logf@x+3),(c:?_logf+3)
	goto	l1053
	line	59
	
l2734:; BSR set to: 5

		movlw	128
	xorwf	((logf@ux+2))&0ffh,w
	bnz	u2521
	movlw	63
	xorwf	((logf@ux+3))&0ffh,w
iorwf	((logf@ux))&0ffh,w
iorwf	((logf@ux+1))&0ffh,w
	btfss	status,2
	goto	u2521
	goto	u2520

u2521:
	goto	l2740
u2520:
	line	60
	
l2736:; BSR set to: 5

	movlw	low(normalize32(0x0))
	movwf	((c:?_logf))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:?_logf+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:?_logf+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:?_logf+3))^0500h,c
	goto	l1053
	line	63
	
l2740:
	movlw	0Dh
	movlb	5	; () banked
	addwf	((logf@ux))&0ffh
	movlw	0FBh
	addwfc	((logf@ux+1))&0ffh
	movlw	04Ah
	addwfc	((logf@ux+2))&0ffh
	movlw	0
	addwfc	((logf@ux+3))&0ffh
	line	64
	movff	(logf@ux),??_logf+0
	movff	(logf@ux+1),??_logf+0+1
	movff	(logf@ux+2),??_logf+0+2
	movff	(logf@ux+3),??_logf+0+3
	movlw	017h+1
	goto	u2530
u2535:
	bcf	status,0
	rrcf	(??_logf+0+3)&0ffh
	rrcf	(??_logf+0+2)&0ffh
	rrcf	(??_logf+0+1)&0ffh
	rrcf	(??_logf+0)&0ffh
u2530:
	decfsz	wreg
	goto	u2535
	movlw	low(-127)
	addwf	(??_logf+0)&0ffh,w
	movwf	(??_logf+4)&0ffh
	movlw	high(-127)
	addwfc	(??_logf+0+1)&0ffh,w
	movwf	1+(??_logf+4)&0ffh
	movf	(??_logf+4)&0ffh,w
	addwf	((logf@k))&0ffh
	movf	(??_logf+4+1)&0ffh,w
	addwfc	((logf@k+1))&0ffh
	line	65
	movlw	0FFh
	andwf	((logf@ux))&0ffh,w
	movwf	(??_logf+0)&0ffh
	movlw	0FFh
	andwf	((logf@ux+1))&0ffh,w
	movwf	1+(??_logf+0)&0ffh
	
	movlw	07Fh
	andwf	((logf@ux+2))&0ffh,w
	movwf	2+(??_logf+0)&0ffh
	
	movlw	0
	andwf	((logf@ux+3))&0ffh,w
	movwf	3+(??_logf+0)&0ffh
	movlw	0F3h
	addwf	(??_logf+0)&0ffh,w
	movwf	((logf@ux))&0ffh
	movlw	04h
	addwfc	(??_logf+0+1)&0ffh,w
	movwf	1+((logf@ux))&0ffh
	
	movlw	035h
	addwfc	(??_logf+0+2)&0ffh,w
	movwf	2+((logf@ux))&0ffh
	
	movlw	03Fh
	addwfc	(??_logf+0+3)&0ffh,w
	movwf	3+((logf@ux))&0ffh
	line	67
	
l2742:; BSR set to: 5

	movff	(logf@ux),(c:___flsub@b)
	movff	(logf@ux+1),(c:___flsub@b+1)
	movff	(logf@ux+2),(c:___flsub@b+2)
	movff	(logf@ux+3),(c:___flsub@b+3)
	movlw	low(normalize32(0x3f800000))
	movwf	((c:___flsub@a))^0500h,c
	movlw	high(normalize32(0x3f800000))
	movwf	((c:___flsub@a+1))^0500h,c
	movlw	low highword(normalize32(0x3f800000))
	movwf	((c:___flsub@a+2))^0500h,c
	movlw	high highword(normalize32(0x3f800000))
	movwf	((c:___flsub@a+3))^0500h,c
	call	___flsub	;wreg free
	movff	0+?___flsub,(logf@ux)
	movff	1+?___flsub,(logf@ux+1)
	movff	2+?___flsub,(logf@ux+2)
	movff	3+?___flsub,(logf@ux+3)
	
	line	68
	
l2744:
	movff	(logf@ux),(c:___fldiv@b)
	movff	(logf@ux+1),(c:___fldiv@b+1)
	movff	(logf@ux+2),(c:___fldiv@b+2)
	movff	(logf@ux+3),(c:___fldiv@b+3)
	movlw	low(normalize32(0x40000000))
	movwf	((c:___fladd@a))^0500h,c
	movlw	high(normalize32(0x40000000))
	movwf	((c:___fladd@a+1))^0500h,c
	movlw	low highword(normalize32(0x40000000))
	movwf	((c:___fladd@a+2))^0500h,c
	movlw	high highword(normalize32(0x40000000))
	movwf	((c:___fladd@a+3))^0500h,c
	movff	(logf@ux),(c:___fladd@b)
	movff	(logf@ux+1),(c:___fladd@b+1)
	movff	(logf@ux+2),(c:___fladd@b+2)
	movff	(logf@ux+3),(c:___fladd@b+3)
	call	___fladd	;wreg free
	movff	0+?___fladd,(c:___fldiv@a)
	movff	1+?___fladd,(c:___fldiv@a+1)
	movff	2+?___fladd,(c:___fldiv@a+2)
	movff	3+?___fladd,(c:___fldiv@a+3)
	
	call	___fldiv	;wreg free
	movff	0+?___fldiv,(logf@s)
	movff	1+?___fldiv,(logf@s+1)
	movff	2+?___fldiv,(logf@s+2)
	movff	3+?___fldiv,(logf@s+3)
	
	line	69
	
l2746:
	movff	(logf@s),(c:___flmul@b)
	movff	(logf@s+1),(c:___flmul@b+1)
	movff	(logf@s+2),(c:___flmul@b+2)
	movff	(logf@s+3),(c:___flmul@b+3)
	movff	(logf@s),(c:___flmul@a)
	movff	(logf@s+1),(c:___flmul@a+1)
	movff	(logf@s+2),(c:___flmul@a+2)
	movff	(logf@s+3),(c:___flmul@a+3)
	call	___flmul	;wreg free
	movff	0+?___flmul,(logf@z)
	movff	1+?___flmul,(logf@z+1)
	movff	2+?___flmul,(logf@z+2)
	movff	3+?___flmul,(logf@z+3)
	
	line	70
	
l2748:
	movff	(logf@z),(c:___flmul@b)
	movff	(logf@z+1),(c:___flmul@b+1)
	movff	(logf@z+2),(c:___flmul@b+2)
	movff	(logf@z+3),(c:___flmul@b+3)
	movff	(logf@z),(c:___flmul@a)
	movff	(logf@z+1),(c:___flmul@a+1)
	movff	(logf@z+2),(c:___flmul@a+2)
	movff	(logf@z+3),(c:___flmul@a+3)
	call	___flmul	;wreg free
	movff	0+?___flmul,(logf@w)
	movff	1+?___flmul,(logf@w+1)
	movff	2+?___flmul,(logf@w+2)
	movff	3+?___flmul,(logf@w+3)
	
	line	71
	
l2750:
	movlw	low(normalize32(0x3eccce13))
	movwf	((c:___fladd@a))^0500h,c
	movlw	high(normalize32(0x3eccce13))
	movwf	((c:___fladd@a+1))^0500h,c
	movlw	low highword(normalize32(0x3eccce13))
	movwf	((c:___fladd@a+2))^0500h,c
	movlw	high highword(normalize32(0x3eccce13))
	movwf	((c:___fladd@a+3))^0500h,c
	movlw	low(normalize32(0x3e789e26))
	movwf	((c:___flmul@a))^0500h,c
	movlw	high(normalize32(0x3e789e26))
	movwf	((c:___flmul@a+1))^0500h,c
	movlw	low highword(normalize32(0x3e789e26))
	movwf	((c:___flmul@a+2))^0500h,c
	movlw	high highword(normalize32(0x3e789e26))
	movwf	((c:___flmul@a+3))^0500h,c
	movff	(logf@w),(c:___flmul@b)
	movff	(logf@w+1),(c:___flmul@b+1)
	movff	(logf@w+2),(c:___flmul@b+2)
	movff	(logf@w+3),(c:___flmul@b+3)
	call	___flmul	;wreg free
	movff	0+?___flmul,(c:___fladd@b)
	movff	1+?___flmul,(c:___fladd@b+1)
	movff	2+?___flmul,(c:___fladd@b+2)
	movff	3+?___flmul,(c:___fladd@b+3)
	
	call	___fladd	;wreg free
	movff	0+?___fladd,(_logf$1625)
	movff	1+?___fladd,(_logf$1625+1)
	movff	2+?___fladd,(_logf$1625+2)
	movff	3+?___fladd,(_logf$1625+3)
	
	
l2752:
	movff	(_logf$1625),(c:___flmul@b)
	movff	(_logf$1625+1),(c:___flmul@b+1)
	movff	(_logf$1625+2),(c:___flmul@b+2)
	movff	(_logf$1625+3),(c:___flmul@b+3)
	movff	(logf@w),(c:___flmul@a)
	movff	(logf@w+1),(c:___flmul@a+1)
	movff	(logf@w+2),(c:___flmul@a+2)
	movff	(logf@w+3),(c:___flmul@a+3)
	call	___flmul	;wreg free
	movff	0+?___flmul,(logf@t1)
	movff	1+?___flmul,(logf@t1+1)
	movff	2+?___flmul,(logf@t1+2)
	movff	3+?___flmul,(logf@t1+3)
	
	line	72
	
l2754:
	movlw	low(normalize32(0x3f2aaaaa))
	movwf	((c:___fladd@a))^0500h,c
	movlw	high(normalize32(0x3f2aaaaa))
	movwf	((c:___fladd@a+1))^0500h,c
	movlw	low highword(normalize32(0x3f2aaaaa))
	movwf	((c:___fladd@a+2))^0500h,c
	movlw	high highword(normalize32(0x3f2aaaaa))
	movwf	((c:___fladd@a+3))^0500h,c
	movlw	low(normalize32(0x3e91e9ee))
	movwf	((c:___flmul@a))^0500h,c
	movlw	high(normalize32(0x3e91e9ee))
	movwf	((c:___flmul@a+1))^0500h,c
	movlw	low highword(normalize32(0x3e91e9ee))
	movwf	((c:___flmul@a+2))^0500h,c
	movlw	high highword(normalize32(0x3e91e9ee))
	movwf	((c:___flmul@a+3))^0500h,c
	movff	(logf@w),(c:___flmul@b)
	movff	(logf@w+1),(c:___flmul@b+1)
	movff	(logf@w+2),(c:___flmul@b+2)
	movff	(logf@w+3),(c:___flmul@b+3)
	call	___flmul	;wreg free
	movff	0+?___flmul,(c:___fladd@b)
	movff	1+?___flmul,(c:___fladd@b+1)
	movff	2+?___flmul,(c:___fladd@b+2)
	movff	3+?___flmul,(c:___fladd@b+3)
	
	call	___fladd	;wreg free
	movff	0+?___fladd,(_logf$1625)
	movff	1+?___fladd,(_logf$1625+1)
	movff	2+?___fladd,(_logf$1625+2)
	movff	3+?___fladd,(_logf$1625+3)
	
	
l2756:
	movff	(_logf$1625),(c:___flmul@b)
	movff	(_logf$1625+1),(c:___flmul@b+1)
	movff	(_logf$1625+2),(c:___flmul@b+2)
	movff	(_logf$1625+3),(c:___flmul@b+3)
	movff	(logf@z),(c:___flmul@a)
	movff	(logf@z+1),(c:___flmul@a+1)
	movff	(logf@z+2),(c:___flmul@a+2)
	movff	(logf@z+3),(c:___flmul@a+3)
	call	___flmul	;wreg free
	movff	0+?___flmul,(logf@t2)
	movff	1+?___flmul,(logf@t2+1)
	movff	2+?___flmul,(logf@t2+2)
	movff	3+?___flmul,(logf@t2+3)
	
	line	73
	
l2758:
	movff	(logf@t2),(c:___fladd@b)
	movff	(logf@t2+1),(c:___fladd@b+1)
	movff	(logf@t2+2),(c:___fladd@b+2)
	movff	(logf@t2+3),(c:___fladd@b+3)
	movff	(logf@t1),(c:___fladd@a)
	movff	(logf@t1+1),(c:___fladd@a+1)
	movff	(logf@t1+2),(c:___fladd@a+2)
	movff	(logf@t1+3),(c:___fladd@a+3)
	call	___fladd	;wreg free
	movff	0+?___fladd,(logf@R)
	movff	1+?___fladd,(logf@R+1)
	movff	2+?___fladd,(logf@R+2)
	movff	3+?___fladd,(logf@R+3)
	
	line	74
	
l2760:
	movlw	low(normalize32(0x3f000000))
	movwf	((c:___flmul@a))^0500h,c
	movlw	high(normalize32(0x3f000000))
	movwf	((c:___flmul@a+1))^0500h,c
	movlw	low highword(normalize32(0x3f000000))
	movwf	((c:___flmul@a+2))^0500h,c
	movlw	high highword(normalize32(0x3f000000))
	movwf	((c:___flmul@a+3))^0500h,c
	movff	(logf@ux),(c:___flmul@b)
	movff	(logf@ux+1),(c:___flmul@b+1)
	movff	(logf@ux+2),(c:___flmul@b+2)
	movff	(logf@ux+3),(c:___flmul@b+3)
	call	___flmul	;wreg free
	movff	0+?___flmul,(_logf$1625)
	movff	1+?___flmul,(_logf$1625+1)
	movff	2+?___flmul,(_logf$1625+2)
	movff	3+?___flmul,(_logf$1625+3)
	
	
l2762:
	movff	(_logf$1625),(c:___flmul@b)
	movff	(_logf$1625+1),(c:___flmul@b+1)
	movff	(_logf$1625+2),(c:___flmul@b+2)
	movff	(_logf$1625+3),(c:___flmul@b+3)
	movff	(logf@ux),(c:___flmul@a)
	movff	(logf@ux+1),(c:___flmul@a+1)
	movff	(logf@ux+2),(c:___flmul@a+2)
	movff	(logf@ux+3),(c:___flmul@a+3)
	call	___flmul	;wreg free
	movff	0+?___flmul,(logf@hfsq)
	movff	1+?___flmul,(logf@hfsq+1)
	movff	2+?___flmul,(logf@hfsq+2)
	movff	3+?___flmul,(logf@hfsq+3)
	
	line	75
	
l2764:
	movff	(logf@k),(c:___xxtofl@val)
	movff	(logf@k+1),(c:___xxtofl@val+1)
	movlw	0
	btfsc	((c:___xxtofl@val+1))^0500h,c,7
	movlw	-1
	movwf	((c:___xxtofl@val+2))^0500h,c
	movwf	((c:___xxtofl@val+3))^0500h,c
	movlw	(01h)&0ffh
	
	call	___xxtofl
	movff	0+?___xxtofl,(logf@dk)
	movff	1+?___xxtofl,(logf@dk+1)
	movff	2+?___xxtofl,(logf@dk+2)
	movff	3+?___xxtofl,(logf@dk+3)
	
	line	76
	
l2766:
	movff	(logf@s),(c:___flmul@a)
	movff	(logf@s+1),(c:___flmul@a+1)
	movff	(logf@s+2),(c:___flmul@a+2)
	movff	(logf@s+3),(c:___flmul@a+3)
	movff	(logf@R),(c:___fladd@a)
	movff	(logf@R+1),(c:___fladd@a+1)
	movff	(logf@R+2),(c:___fladd@a+2)
	movff	(logf@R+3),(c:___fladd@a+3)
	movff	(logf@hfsq),(c:___fladd@b)
	movff	(logf@hfsq+1),(c:___fladd@b+1)
	movff	(logf@hfsq+2),(c:___fladd@b+2)
	movff	(logf@hfsq+3),(c:___fladd@b+3)
	call	___fladd	;wreg free
	movff	0+?___fladd,(c:___flmul@b)
	movff	1+?___fladd,(c:___flmul@b+1)
	movff	2+?___fladd,(c:___flmul@b+2)
	movff	3+?___fladd,(c:___flmul@b+3)
	
	call	___flmul	;wreg free
	movff	0+?___flmul,(_logf$1626)
	movff	1+?___flmul,(_logf$1626+1)
	movff	2+?___flmul,(_logf$1626+2)
	movff	3+?___flmul,(_logf$1626+3)
	
	
l2768:
	movlw	low(normalize32(0x3717f7d1))
	movwf	((c:___flmul@a))^0500h,c
	movlw	high(normalize32(0x3717f7d1))
	movwf	((c:___flmul@a+1))^0500h,c
	movlw	low highword(normalize32(0x3717f7d1))
	movwf	((c:___flmul@a+2))^0500h,c
	movlw	high highword(normalize32(0x3717f7d1))
	movwf	((c:___flmul@a+3))^0500h,c
	movff	(logf@dk),(c:___flmul@b)
	movff	(logf@dk+1),(c:___flmul@b+1)
	movff	(logf@dk+2),(c:___flmul@b+2)
	movff	(logf@dk+3),(c:___flmul@b+3)
	call	___flmul	;wreg free
	movff	0+?___flmul,(c:___fladd@a)
	movff	1+?___flmul,(c:___fladd@a+1)
	movff	2+?___flmul,(c:___fladd@a+2)
	movff	3+?___flmul,(c:___fladd@a+3)
	
	movff	(_logf$1626),(c:___fladd@b)
	movff	(_logf$1626+1),(c:___fladd@b+1)
	movff	(_logf$1626+2),(c:___fladd@b+2)
	movff	(_logf$1626+3),(c:___fladd@b+3)
	call	___fladd	;wreg free
	movff	0+?___fladd,(_logf$1627)
	movff	1+?___fladd,(_logf$1627+1)
	movff	2+?___fladd,(_logf$1627+2)
	movff	3+?___fladd,(_logf$1627+3)
	
	
l2770:
	movff	(logf@hfsq),(c:___flsub@a)
	movff	(logf@hfsq+1),(c:___flsub@a+1)
	movff	(logf@hfsq+2),(c:___flsub@a+2)
	movff	(logf@hfsq+3),(c:___flsub@a+3)
	movff	(_logf$1627),(c:___flsub@b)
	movff	(_logf$1627+1),(c:___flsub@b+1)
	movff	(_logf$1627+2),(c:___flsub@b+2)
	movff	(_logf$1627+3),(c:___flsub@b+3)
	call	___flsub	;wreg free
	movff	0+?___flsub,(_logf$1628)
	movff	1+?___flsub,(_logf$1628+1)
	movff	2+?___flsub,(_logf$1628+2)
	movff	3+?___flsub,(_logf$1628+3)
	
	
l2772:
	movff	(logf@ux),(c:___fladd@a)
	movff	(logf@ux+1),(c:___fladd@a+1)
	movff	(logf@ux+2),(c:___fladd@a+2)
	movff	(logf@ux+3),(c:___fladd@a+3)
	movff	(_logf$1628),(c:___fladd@b)
	movff	(_logf$1628+1),(c:___fladd@b+1)
	movff	(_logf$1628+2),(c:___fladd@b+2)
	movff	(_logf$1628+3),(c:___fladd@b+3)
	call	___fladd	;wreg free
	movff	0+?___fladd,(_logf$1629)
	movff	1+?___fladd,(_logf$1629+1)
	movff	2+?___fladd,(_logf$1629+2)
	movff	3+?___fladd,(_logf$1629+3)
	
	
l2774:
	movff	(_logf$1629),(c:___fladd@b)
	movff	(_logf$1629+1),(c:___fladd@b+1)
	movff	(_logf$1629+2),(c:___fladd@b+2)
	movff	(_logf$1629+3),(c:___fladd@b+3)
	movlw	low(normalize32(0x3f317180))
	movwf	((c:___flmul@a))^0500h,c
	movlw	high(normalize32(0x3f317180))
	movwf	((c:___flmul@a+1))^0500h,c
	movlw	low highword(normalize32(0x3f317180))
	movwf	((c:___flmul@a+2))^0500h,c
	movlw	high highword(normalize32(0x3f317180))
	movwf	((c:___flmul@a+3))^0500h,c
	movff	(logf@dk),(c:___flmul@b)
	movff	(logf@dk+1),(c:___flmul@b+1)
	movff	(logf@dk+2),(c:___flmul@b+2)
	movff	(logf@dk+3),(c:___flmul@b+3)
	call	___flmul	;wreg free
	movff	0+?___flmul,(c:___fladd@a)
	movff	1+?___flmul,(c:___fladd@a+1)
	movff	2+?___flmul,(c:___fladd@a+2)
	movff	3+?___flmul,(c:___fladd@a+3)
	
	call	___fladd	;wreg free
	movff	0+?___fladd,(c:?_logf)
	movff	1+?___fladd,(c:?_logf+1)
	movff	2+?___fladd,(c:?_logf+2)
	movff	3+?___fladd,(c:?_logf+3)
	
	line	77
	
l1053:
	return	;funcret
	callstack 0
GLOBAL	__end_of_logf
	__end_of_logf:
	signat	_logf,4220
	global	___xxtofl

;; *************** function ___xxtofl *****************
;; Defined at:
;;		line 10 in file "C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\xxtofl.c"
;; Parameters:    Size  Location     Type
;;  sign            1    wreg     unsigned char 
;;  val             4    0[COMRAM] long 
;; Auto vars:     Size  Location     Type
;;  sign            1    8[COMRAM] unsigned char 
;;  arg             4   10[COMRAM] unsigned long 
;;  exp             1    9[COMRAM] unsigned char 
;; Return value:  Size  Location     Type
;;                  4    0[COMRAM] unsigned char 
;; Registers used:
;;		wreg, status,2, status,0
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         6       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:        14       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       14 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_thermistor_centi_c
;;		_logf
;; This function uses a non-reentrant model
;;
psect	text4,class=CODE,space=0,reloc=2,group=1
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\xxtofl.c"
	line	10
global __ptext4
__ptext4:
psect	text4
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\xxtofl.c"
	line	10
	
___xxtofl:
;incstack = 0
	callstack 124
	line	15
	movwf	((c:___xxtofl@sign))^0500h,c
	
l2634:
	movf	((c:___xxtofl@sign))^0500h,c,w
	btfsc	status,2
	goto	u2321
	goto	u2320
u2321:
	goto	l1014
u2320:
	
l2636:
	btfsc	((c:___xxtofl@val+3))^0500h,c,7
	goto	u2330
	goto	u2331

u2331:
	goto	l1014
u2330:
	line	16
	
l2638:
	movff	(c:___xxtofl@val),??___xxtofl+0
	movff	(c:___xxtofl@val+1),??___xxtofl+0+1
	movff	(c:___xxtofl@val+2),??___xxtofl+0+2
	movff	(c:___xxtofl@val+3),??___xxtofl+0+3
	comf	(??___xxtofl+0)^0500h,c
	comf	(??___xxtofl+0+1)^0500h,c
	comf	(??___xxtofl+0+2)^0500h,c
	comf	(??___xxtofl+0+3)^0500h,c
	incf	(??___xxtofl+0)^0500h,c
	movlw	0
	addwfc	(??___xxtofl+0+1)^0500h,c
	addwfc	(??___xxtofl+0+2)^0500h,c
	addwfc	(??___xxtofl+0+3)^0500h,c
	movff	??___xxtofl+0,(c:___xxtofl@arg)
	movff	??___xxtofl+0+1,(c:___xxtofl@arg+1)
	movff	??___xxtofl+0+2,(c:___xxtofl@arg+2)
	movff	??___xxtofl+0+3,(c:___xxtofl@arg+3)
	line	17
	goto	l2640
	line	18
	
l1014:
	line	19
	movff	(c:___xxtofl@val),(c:___xxtofl@arg)
	movff	(c:___xxtofl@val+1),(c:___xxtofl@arg+1)
	movff	(c:___xxtofl@val+2),(c:___xxtofl@arg+2)
	movff	(c:___xxtofl@val+3),(c:___xxtofl@arg+3)
	line	21
	
l2640:
	movf	((c:___xxtofl@val))^0500h,c,w
iorwf	((c:___xxtofl@val+1))^0500h,c,w
iorwf	((c:___xxtofl@val+2))^0500h,c,w
iorwf	((c:___xxtofl@val+3))^0500h,c,w
	btfss	status,2
	goto	u2341
	goto	u2340

u2341:
	goto	l2646
u2340:
	line	22
	
l2642:
	movlw	low(normalize32(0x0))
	movwf	((c:?___xxtofl))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:?___xxtofl+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:?___xxtofl+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:?___xxtofl+3))^0500h,c
	goto	l1017
	line	23
	
l2646:
	movlw	low(096h)
	movwf	((c:___xxtofl@exp))^0500h,c
	line	24
	goto	l2650
	line	25
	
l2648:
	incf	((c:___xxtofl@exp))^0500h,c
	line	26
	bcf	status,0
	rrcf	((c:___xxtofl@arg+3))^0500h,c
	rrcf	((c:___xxtofl@arg+2))^0500h,c
	rrcf	((c:___xxtofl@arg+1))^0500h,c
	rrcf	((c:___xxtofl@arg))^0500h,c
	line	24
	
l2650:
	movlw	0
	andwf	((c:___xxtofl@arg))^0500h,c,w
	movwf	(??___xxtofl+0)^0500h,c
	movlw	0
	andwf	((c:___xxtofl@arg+1))^0500h,c,w
	movwf	1+(??___xxtofl+0)^0500h,c
	
	movlw	0
	andwf	((c:___xxtofl@arg+2))^0500h,c,w
	movwf	2+(??___xxtofl+0)^0500h,c
	
	movlw	0FEh
	andwf	((c:___xxtofl@arg+3))^0500h,c,w
	movwf	3+(??___xxtofl+0)^0500h,c
	movf	(??___xxtofl+0)^0500h,c,w
iorwf	(??___xxtofl+0+1)^0500h,c,w
iorwf	(??___xxtofl+0+2)^0500h,c,w
iorwf	(??___xxtofl+0+3)^0500h,c,w
	btfss	status,2
	goto	u2351
	goto	u2350

u2351:
	goto	l2648
u2350:
	goto	l1021
	line	29
	
l2652:
	incf	((c:___xxtofl@exp))^0500h,c
	line	30
	
l2654:
	movlw	low(01h)
	addwf	((c:___xxtofl@arg))^0500h,c
	movlw	0
	addwfc	((c:___xxtofl@arg+1))^0500h,c
	addwfc	((c:___xxtofl@arg+2))^0500h,c
	addwfc	((c:___xxtofl@arg+3))^0500h,c
	line	31
	
l2656:
	bcf	status,0
	rrcf	((c:___xxtofl@arg+3))^0500h,c
	rrcf	((c:___xxtofl@arg+2))^0500h,c
	rrcf	((c:___xxtofl@arg+1))^0500h,c
	rrcf	((c:___xxtofl@arg))^0500h,c
	line	32
	
l1021:
	line	28
	movlw	0
	andwf	((c:___xxtofl@arg))^0500h,c,w
	movwf	(??___xxtofl+0)^0500h,c
	movlw	0
	andwf	((c:___xxtofl@arg+1))^0500h,c,w
	movwf	1+(??___xxtofl+0)^0500h,c
	
	movlw	0
	andwf	((c:___xxtofl@arg+2))^0500h,c,w
	movwf	2+(??___xxtofl+0)^0500h,c
	
	movlw	0FFh
	andwf	((c:___xxtofl@arg+3))^0500h,c,w
	movwf	3+(??___xxtofl+0)^0500h,c
	movf	(??___xxtofl+0)^0500h,c,w
iorwf	(??___xxtofl+0+1)^0500h,c,w
iorwf	(??___xxtofl+0+2)^0500h,c,w
iorwf	(??___xxtofl+0+3)^0500h,c,w
	btfss	status,2
	goto	u2361
	goto	u2360

u2361:
	goto	l2652
u2360:
	goto	l2660
	line	34
	
l2658:
	decf	((c:___xxtofl@exp))^0500h,c
	line	35
	bcf	status,0
	rlcf	((c:___xxtofl@arg))^0500h,c
	rlcf	((c:___xxtofl@arg+1))^0500h,c
	rlcf	((c:___xxtofl@arg+2))^0500h,c
	rlcf	((c:___xxtofl@arg+3))^0500h,c
	line	33
	
l2660:
	
	btfsc	((c:___xxtofl@arg+2))^0500h,c,(23)&7
	goto	u2371
	goto	u2370
u2371:
	goto	l1028
u2370:
	
l2662:
		movlw	02h-0
	cpfslt	((c:___xxtofl@exp))^0500h,c
	goto	u2381
	goto	u2380

u2381:
	goto	l2658
u2380:
	
l1028:
	line	37
	
	btfsc	((c:___xxtofl@exp))^0500h,c,(0)&7
	goto	u2391
	goto	u2390
u2391:
	goto	l2666
u2390:
	line	38
	
l2664:
	bcf	(0+(23/8)+(c:___xxtofl@arg))^0500h,c,(23)&7
	line	39
	
l2666:
	bcf status,0
	rrcf	((c:___xxtofl@exp))^0500h,c

	line	40
	
l2668:
	movff	(c:___xxtofl@exp),??___xxtofl+0
	clrf	(??___xxtofl+0+1)^0500h,c
	clrf	(??___xxtofl+0+2)^0500h,c
	clrf	(??___xxtofl+0+3)^0500h,c
	movff	??___xxtofl+0,??___xxtofl+0+3
	clrf	(??___xxtofl+0+2)^0500h,c
	clrf	(??___xxtofl+0+1)^0500h,c
	clrf	(??___xxtofl+0)^0500h,c
	movf	(??___xxtofl+0)^0500h,c,w
	iorwf	((c:___xxtofl@arg))^0500h,c
	movf	(??___xxtofl+0+1)^0500h,c,w
	iorwf	((c:___xxtofl@arg+1))^0500h,c
	movf	(??___xxtofl+0+2)^0500h,c,w
	iorwf	((c:___xxtofl@arg+2))^0500h,c
	movf	(??___xxtofl+0+3)^0500h,c,w
	iorwf	((c:___xxtofl@arg+3))^0500h,c

	line	41
	
l2670:
	movf	((c:___xxtofl@sign))^0500h,c,w
	btfsc	status,2
	goto	u2401
	goto	u2400
u2401:
	goto	l2676
u2400:
	
l2672:
	btfsc	((c:___xxtofl@val+3))^0500h,c,7
	goto	u2410
	goto	u2411

u2411:
	goto	l2676
u2410:
	line	42
	
l2674:
	bsf	(0+(31/8)+(c:___xxtofl@arg))^0500h,c,(31)&7
	line	43
	
l2676:
	movff	(c:___xxtofl@arg),(c:?___xxtofl)
	movff	(c:___xxtofl@arg+1),(c:?___xxtofl+1)
	movff	(c:___xxtofl@arg+2),(c:?___xxtofl+2)
	movff	(c:___xxtofl@arg+3),(c:?___xxtofl+3)
	line	44
	
l1017:
	return	;funcret
	callstack 0
GLOBAL	__end_of___xxtofl
	__end_of___xxtofl:
	signat	___xxtofl,8316
	global	___flsub

;; *************** function ___flsub *****************
;; Defined at:
;;		line 245 in file "C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\sprcadd.c"
;; Parameters:    Size  Location     Type
;;  b               4   80[COMRAM] unsigned char 
;;  a               4   84[COMRAM] unsigned char 
;; Auto vars:     Size  Location     Type
;;		None
;; Return value:  Size  Location     Type
;;                  4   80[COMRAM] unsigned char 
;; Registers used:
;;		wreg, status,2, status,0, cstack
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         8       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:         8       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:        8 bytes
;; Hardware stack levels used: 1
;; Hardware stack levels required when called: 1
;; This function calls:
;;		___fladd
;; This function is called by:
;;		_logf
;; This function uses a non-reentrant model
;;
psect	text5,class=CODE,space=0,reloc=2,group=1
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\sprcadd.c"
	line	245
global __ptext5
__ptext5:
psect	text5
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\sprcadd.c"
	line	245
	
___flsub:
;incstack = 0
	callstack 123
	line	248
	
l2612:
	movlw	0
	xorwf	((c:___flsub@a))^0500h,c
	movlw	0
	xorwf	((c:___flsub@a+1))^0500h,c
	movlw	0
	xorwf	((c:___flsub@a+2))^0500h,c
	movlw	080h
	xorwf	((c:___flsub@a+3))^0500h,c
	line	249
	
l2614:
	movff	(c:___flsub@b),(c:___fladd@b)
	movff	(c:___flsub@b+1),(c:___fladd@b+1)
	movff	(c:___flsub@b+2),(c:___fladd@b+2)
	movff	(c:___flsub@b+3),(c:___fladd@b+3)
	movff	(c:___flsub@a),(c:___fladd@a)
	movff	(c:___flsub@a+1),(c:___fladd@a+1)
	movff	(c:___flsub@a+2),(c:___fladd@a+2)
	movff	(c:___flsub@a+3),(c:___fladd@a+3)
	call	___fladd	;wreg free
	movff	0+?___fladd,(c:?___flsub)
	movff	1+?___fladd,(c:?___flsub+1)
	movff	2+?___fladd,(c:?___flsub+2)
	movff	3+?___fladd,(c:?___flsub+3)
	
	line	250
	
l929:
	return	;funcret
	callstack 0
GLOBAL	__end_of___flsub
	__end_of___flsub:
	signat	___flsub,8316
	global	___fladd

;; *************** function ___fladd *****************
;; Defined at:
;;		line 10 in file "C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\sprcadd.c"
;; Parameters:    Size  Location     Type
;;  b               4   39[COMRAM] unsigned char 
;;  a               4   43[COMRAM] unsigned char 
;; Auto vars:     Size  Location     Type
;;  grs             1   54[COMRAM] unsigned char 
;;  bexp            1   53[COMRAM] unsigned char 
;;  aexp            1   52[COMRAM] unsigned char 
;;  signs           1   51[COMRAM] unsigned char 
;; Return value:  Size  Location     Type
;;                  4   39[COMRAM] unsigned char 
;; Registers used:
;;		wreg, status,2, status,0
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         8       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:        16       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       16 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_thermistor_centi_c
;;		___flsub
;;		_logf
;; This function uses a non-reentrant model
;;
psect	text6,class=CODE,space=0,reloc=2,group=1
	line	10
global __ptext6
__ptext6:
psect	text6
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\sprcadd.c"
	line	10
	
___fladd:
;incstack = 0
	callstack 123
	line	21
	
l2132:
	movf	(0+((c:___fladd@b)+03h))^0500h,c,w
	andlw	low(080h)
	movwf	((c:___fladd@signs))^0500h,c
	line	22
	movf	(0+((c:___fladd@b)+03h))^0500h,c,w
	addwf	(0+((c:___fladd@b)+03h))^0500h,c,w
	movwf	((c:___fladd@bexp))^0500h,c
	line	23
	
l2134:
	
	btfss	(0+((c:___fladd@b)+02h))^0500h,c,(7)&7
	goto	u1451
	goto	u1450
u1451:
	goto	l2138
u1450:
	line	24
	
l2136:
	bsf	(0+(0/8)+(c:___fladd@bexp))^0500h,c,(0)&7
	line	28
	
l2138:
	movf	((c:___fladd@bexp))^0500h,c,w
	btfsc	status,2
	goto	u1461
	goto	u1460
u1461:
	goto	l2148
u1460:
	line	30
	
l2140:
		incf	((c:___fladd@bexp))^0500h,c,w
	btfss	status,2
	goto	u1471
	goto	u1470

u1471:
	goto	l2144
u1470:
	line	32
	
l2142:
	movlw	low(normalize32(0x0))
	movwf	((c:___fladd@b))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:___fladd@b+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:___fladd@b+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:___fladd@b+3))^0500h,c
	line	35
	
l2144:
	bsf	(0+(23/8)+(c:___fladd@b))^0500h,c,(23)&7
	line	37
	
l2146:
	clrf	(0+((c:___fladd@b)+03h))^0500h,c
	line	38
	goto	l2150
	line	41
	
l2148:
	movlw	low(normalize32(0x0))
	movwf	((c:___fladd@b))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:___fladd@b+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:___fladd@b+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:___fladd@b+3))^0500h,c
	line	44
	
l2150:
	movf	(0+((c:___fladd@a)+03h))^0500h,c,w
	andlw	low(080h)
	movwf	((c:___fladd@aexp))^0500h,c
	line	46
	
l2152:
	movf	((c:___fladd@signs))^0500h,c,w
xorwf	((c:___fladd@aexp))^0500h,c,w
	btfsc	status,2
	goto	u1481
	goto	u1480

u1481:
	goto	l2156
u1480:
	line	47
	
l2154:
	bsf	(0+(6/8)+(c:___fladd@signs))^0500h,c,(6)&7
	line	49
	
l2156:
	movf	(0+((c:___fladd@a)+03h))^0500h,c,w
	addwf	(0+((c:___fladd@a)+03h))^0500h,c,w
	movwf	((c:___fladd@aexp))^0500h,c
	line	50
	
l2158:
	
	btfss	(0+((c:___fladd@a)+02h))^0500h,c,(7)&7
	goto	u1491
	goto	u1490
u1491:
	goto	l2162
u1490:
	line	51
	
l2160:
	bsf	(0+(0/8)+(c:___fladd@aexp))^0500h,c,(0)&7
	line	55
	
l2162:
	movf	((c:___fladd@aexp))^0500h,c,w
	btfsc	status,2
	goto	u1501
	goto	u1500
u1501:
	goto	l2172
u1500:
	line	57
	
l2164:
		incf	((c:___fladd@aexp))^0500h,c,w
	btfss	status,2
	goto	u1511
	goto	u1510

u1511:
	goto	l2168
u1510:
	line	59
	
l2166:
	movlw	low(normalize32(0x0))
	movwf	((c:___fladd@a))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:___fladd@a+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:___fladd@a+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:___fladd@a+3))^0500h,c
	line	62
	
l2168:
	bsf	(0+(23/8)+(c:___fladd@a))^0500h,c,(23)&7
	line	64
	
l2170:
	clrf	(0+((c:___fladd@a)+03h))^0500h,c
	line	65
	goto	l2174
	line	68
	
l2172:
	movlw	low(normalize32(0x0))
	movwf	((c:___fladd@a))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:___fladd@a+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:___fladd@a+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:___fladd@a+3))^0500h,c
	line	75
	
l2174:
		movf	((c:___fladd@bexp))^0500h,c,w
	subwf	((c:___fladd@aexp))^0500h,c,w
	btfsc	status,0
	goto	u1521
	goto	u1520

u1521:
	goto	l2210
u1520:
	line	77
	
l2176:
	
	btfss	((c:___fladd@signs))^0500h,c,(6)&7
	goto	u1531
	goto	u1530
u1531:
	goto	l2180
u1530:
	line	78
	
l2178:
	movlw	(080h)&0ffh
	xorwf	((c:___fladd@signs))^0500h,c
	line	81
	
l2180:
	movff	(c:___fladd@bexp),(c:___fladd@grs)
	line	82
	
l2182:
	movff	(c:___fladd@aexp),(c:___fladd@bexp)
	line	83
	
l2184:
	movff	(c:___fladd@grs),(c:___fladd@aexp)
	line	84
	
l2186:
	movff	(c:___fladd@b),(c:___fladd@grs)
	line	85
	
l2188:
	movff	(c:___fladd@a),(c:___fladd@b)
	line	86
	
l2190:
	movff	(c:___fladd@grs),(c:___fladd@a)
	line	87
	
l2192:
	movff	0+((c:___fladd@b)+01h),(c:___fladd@grs)
	line	88
	
l2194:
	movff	0+((c:___fladd@a)+01h),0+((c:___fladd@b)+01h)
	line	89
	
l2196:
	movff	(c:___fladd@grs),0+((c:___fladd@a)+01h)
	line	90
	
l2198:
	movff	0+((c:___fladd@b)+02h),(c:___fladd@grs)
	line	91
	
l2200:
	movff	0+((c:___fladd@a)+02h),0+((c:___fladd@b)+02h)
	line	92
	
l2202:
	movff	(c:___fladd@grs),0+((c:___fladd@a)+02h)
	line	93
	
l2204:
	movff	0+((c:___fladd@b)+03h),(c:___fladd@grs)
	line	94
	
l2206:
	movff	0+((c:___fladd@a)+03h),0+((c:___fladd@b)+03h)
	line	95
	
l2208:
	movff	(c:___fladd@grs),0+((c:___fladd@a)+03h)
	line	98
	
l2210:
	clrf	((c:___fladd@grs))^0500h,c
	line	100
	movf	((c:___fladd@bexp))^0500h,c,w
	movff	(c:___fladd@aexp),??___fladd+0
	clrf	(??___fladd+0+1)^0500h,c
	subwf	(??___fladd+0)^0500h,c
	movlw	0
	subwfb	(??___fladd+0+1)^0500h,c
	btfsc	(??___fladd+0+1)^0500h,c,7
	goto	u1541
	movf	(??___fladd+0+1)^0500h,c,w
	bnz	u1540
	movlw	26
	subwf	 (??___fladd+0)^0500h,c,w
	btfss	status,0
	goto	u1541
	goto	u1540

u1541:
	goto	l888
u1540:
	line	101
	
l2212:
	movf	((c:___fladd@b))^0500h,c,w
iorwf	((c:___fladd@b+1))^0500h,c,w
iorwf	((c:___fladd@b+2))^0500h,c,w
iorwf	((c:___fladd@b+3))^0500h,c,w
	btfss	status,2
	goto	u1551
	goto	u1550

u1551:
	movlw	1
	goto	u1560
u1550:
	movlw	0
u1560:
	movwf	((c:___fladd@grs))^0500h,c
	line	102
	
l2214:
	movlw	low(0)
	movwf	((c:___fladd@b))^0500h,c
	movlw	high(0)
	movwf	((c:___fladd@b+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:___fladd@b+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:___fladd@b+3))^0500h,c
	line	103
	
l2216:
	movff	(c:___fladd@aexp),(c:___fladd@bexp)
	line	104
	goto	l887
	line	106
	
l889:
	line	109
	
	btfss	((c:___fladd@grs))^0500h,c,(0)&7
	goto	u1571
	goto	u1570
u1571:
	goto	l2220
u1570:
	line	110
	
l2218:
	bcf	status,0
	rrcf	((c:___fladd@grs))^0500h,c,w
	iorlw	low(01h)
	movwf	((c:___fladd@grs))^0500h,c
	line	111
	goto	l2222
	line	113
	
l2220:
	bcf status,0
	rrcf	((c:___fladd@grs))^0500h,c

	line	115
	
l2222:
	
	btfss	((c:___fladd@b))^0500h,c,(0)&7
	goto	u1581
	goto	u1580
u1581:
	goto	l2226
u1580:
	line	116
	
l2224:
	bsf	(0+(7/8)+(c:___fladd@grs))^0500h,c,(7)&7
	line	118
	
l2226:
	rlcf	((c:___fladd@b+3))^0500h,c,w
	rrcf	((c:___fladd@b+3))^0500h,c
	rrcf	((c:___fladd@b+2))^0500h,c
	rrcf	((c:___fladd@b+1))^0500h,c
	rrcf	((c:___fladd@b))^0500h,c
	line	119
	
l2228:
	incf	((c:___fladd@bexp))^0500h,c
	line	120
	
l888:
	line	106
		movf	((c:___fladd@aexp))^0500h,c,w
	subwf	((c:___fladd@bexp))^0500h,c,w
	btfss	status,0
	goto	u1591
	goto	u1590

u1591:
	goto	l889
u1590:
	line	121
	
l887:
	line	124
	
	btfsc	((c:___fladd@signs))^0500h,c,(6)&7
	goto	u1601
	goto	u1600
u1601:
	goto	l2254
u1600:
	line	127
	
l2230:
	movf	((c:___fladd@bexp))^0500h,c,w
	btfss	status,2
	goto	u1611
	goto	u1610
u1611:
	goto	l2236
u1610:
	line	128
	
l2232:
	movlw	low(normalize32(0x0))
	movwf	((c:?___fladd))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:?___fladd+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:?___fladd+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:?___fladd+3))^0500h,c
	goto	l896
	line	132
	
l2236:
	movf	((c:___fladd@a))^0500h,c,w
	addwf	((c:___fladd@b))^0500h,c
	movf	((c:___fladd@a+1))^0500h,c,w
	addwfc	((c:___fladd@b+1))^0500h,c
	movf	((c:___fladd@a+2))^0500h,c,w
	addwfc	((c:___fladd@b+2))^0500h,c
	movf	((c:___fladd@a+3))^0500h,c,w
	addwfc	((c:___fladd@b+3))^0500h,c
	line	134
	
l2238:
	
	btfss	((c:___fladd@b+3))^0500h,c,(24)&7
	goto	u1621
	goto	u1620
u1621:
	goto	l901
u1620:
	line	135
	
l2240:
	
	btfss	((c:___fladd@grs))^0500h,c,(0)&7
	goto	u1631
	goto	u1630
u1631:
	goto	l2244
u1630:
	line	136
	
l2242:
	bcf	status,0
	rrcf	((c:___fladd@grs))^0500h,c,w
	iorlw	low(01h)
	movwf	((c:___fladd@grs))^0500h,c
	line	137
	goto	l2246
	line	139
	
l2244:
	bcf status,0
	rrcf	((c:___fladd@grs))^0500h,c

	line	141
	
l2246:
	
	btfss	((c:___fladd@b))^0500h,c,(0)&7
	goto	u1641
	goto	u1640
u1641:
	goto	l2250
u1640:
	line	142
	
l2248:
	bsf	(0+(7/8)+(c:___fladd@grs))^0500h,c,(7)&7
	line	144
	
l2250:
	rlcf	((c:___fladd@b+3))^0500h,c,w
	rrcf	((c:___fladd@b+3))^0500h,c
	rrcf	((c:___fladd@b+2))^0500h,c
	rrcf	((c:___fladd@b+1))^0500h,c
	rrcf	((c:___fladd@b))^0500h,c
	line	145
	
l2252:
	incf	((c:___fladd@bexp))^0500h,c
	goto	l901
	line	153
	
l2254:
		movf	((c:___fladd@a))^0500h,c,w
	subwf	((c:___fladd@b))^0500h,c,w
	movf	((c:___fladd@a+1))^0500h,c,w
	subwfb	((c:___fladd@b+1))^0500h,c,w
	movf	((c:___fladd@a+2))^0500h,c,w
	subwfb	((c:___fladd@b+2))^0500h,c,w
	movf	((c:___fladd@b+3))^0500h,c,w
	xorlw	80h
	movwf	(??___fladd+0)^0500h,c
	movf	((c:___fladd@a+3))^0500h,c,w
	xorlw	80h
	subwfb	(??___fladd+0)^0500h,c,w
	btfsc	status,0
	goto	u1651
	goto	u1650

u1651:
	goto	l2264
u1650:
	line	154
	
l2256:
	movf	((c:___fladd@b))^0500h,c,w
	subwf	((c:___fladd@a))^0500h,c,w
	movwf	(??___fladd+0)^0500h,c
	movf	((c:___fladd@b+1))^0500h,c,w
	subwfb	((c:___fladd@a+1))^0500h,c,w
	movwf	1+(??___fladd+0)^0500h,c
	
	movf	((c:___fladd@b+2))^0500h,c,w
	subwfb	((c:___fladd@a+2))^0500h,c,w
	movwf	2+(??___fladd+0)^0500h,c
	
	movf	((c:___fladd@b+3))^0500h,c,w
	subwfb	((c:___fladd@a+3))^0500h,c,w
	movwf	3+(??___fladd+0)^0500h,c
	movlw	0FFh
	addwf	(??___fladd+0)^0500h,c,w
	movwf	((c:___fladd@b))^0500h,c
	movlw	0FFh
	addwfc	(??___fladd+0+1)^0500h,c,w
	movwf	1+((c:___fladd@b))^0500h,c
	
	movlw	0FFh
	addwfc	(??___fladd+0+2)^0500h,c,w
	movwf	2+((c:___fladd@b))^0500h,c
	
	movlw	0FFh
	addwfc	(??___fladd+0+3)^0500h,c,w
	movwf	3+((c:___fladd@b))^0500h,c
	line	155
	movlw	(080h)&0ffh
	xorwf	((c:___fladd@signs))^0500h,c
	line	156
	
l2258:
	negf	((c:___fladd@grs))^0500h,c
	line	157
	
l2260:
	movf	((c:___fladd@grs))^0500h,c,w
	btfss	status,2
	goto	u1661
	goto	u1660
u1661:
	goto	l904
u1660:
	line	158
	
l2262:
	movlw	low(01h)
	addwf	((c:___fladd@b))^0500h,c
	movlw	0
	addwfc	((c:___fladd@b+1))^0500h,c
	addwfc	((c:___fladd@b+2))^0500h,c
	addwfc	((c:___fladd@b+3))^0500h,c
	goto	l904
	line	162
	
l2264:
	movf	((c:___fladd@a))^0500h,c,w
	subwf	((c:___fladd@b))^0500h,c
	movf	((c:___fladd@a+1))^0500h,c,w
	subwfb	((c:___fladd@b+1))^0500h,c
	movf	((c:___fladd@a+2))^0500h,c,w
	subwfb	((c:___fladd@b+2))^0500h,c
	movf	((c:___fladd@a+3))^0500h,c,w
	subwfb	((c:___fladd@b+3))^0500h,c
	line	163
	
l904:
	line	166
	movf	((c:___fladd@b))^0500h,c,w
iorwf	((c:___fladd@b+1))^0500h,c,w
iorwf	((c:___fladd@b+2))^0500h,c,w
iorwf	((c:___fladd@b+3))^0500h,c,w
	btfss	status,2
	goto	u1671
	goto	u1670

u1671:
	goto	l2288
u1670:
	
l2266:
	movf	((c:___fladd@grs))^0500h,c,w
	btfss	status,2
	goto	u1681
	goto	u1680
u1681:
	goto	l2288
u1680:
	line	167
	
l2268:
	movlw	low(normalize32(0x0))
	movwf	((c:?___fladd))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:?___fladd+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:?___fladd+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:?___fladd+3))^0500h,c
	goto	l896
	line	172
	
l2272:
	bcf	status,0
	rlcf	((c:___fladd@b))^0500h,c
	rlcf	((c:___fladd@b+1))^0500h,c
	rlcf	((c:___fladd@b+2))^0500h,c
	rlcf	((c:___fladd@b+3))^0500h,c
	line	173
	
l2274:
	
	btfss	((c:___fladd@grs))^0500h,c,(7)&7
	goto	u1691
	goto	u1690
u1691:
	goto	l2278
u1690:
	line	174
	
l2276:
	bsf	(0+(0/8)+(c:___fladd@b))^0500h,c,(0)&7
	line	176
	
l2278:
	
	btfss	((c:___fladd@grs))^0500h,c,(0)&7
	goto	u1701
	goto	u1700
u1701:
	goto	l2282
u1700:
	line	177
	
l2280:
	bsf	status,0
	
	rlcf	((c:___fladd@grs))^0500h,c
	line	178
	goto	l2284
	line	180
	
l2282:
	bcf status,0
	rlcf	((c:___fladd@grs))^0500h,c

	line	182
	
l2284:
	movf	((c:___fladd@bexp))^0500h,c,w
	btfsc	status,2
	goto	u1711
	goto	u1710
u1711:
	goto	l2288
u1710:
	line	183
	
l2286:
	decf	((c:___fladd@bexp))^0500h,c
	line	171
	
l2288:
	
	btfss	((c:___fladd@b+2))^0500h,c,(23)&7
	goto	u1721
	goto	u1720
u1721:
	goto	l2272
u1720:
	line	186
	
l901:
	line	192
	clrf	((c:___fladd@aexp))^0500h,c
	line	193
	
	btfss	((c:___fladd@grs))^0500h,c,(7)&7
	goto	u1731
	goto	u1730
u1731:
	goto	l913
u1730:
	line	194
	
l2290:
	movff	(c:___fladd@grs),??___fladd+0
	movlw	07Fh
	andwf	(??___fladd+0)^0500h,c
	btfsc	status,2
	goto	u1741
	goto	u1740
u1741:
	goto	l914
u1740:
	line	195
	
l2292:
	movlw	low(01h)
	movwf	((c:___fladd@aexp))^0500h,c
	line	196
	goto	l913
	line	197
	
l914:
	line	198
	
	btfss	((c:___fladd@b))^0500h,c,(0)&7
	goto	u1751
	goto	u1750
u1751:
	goto	l913
u1750:
	goto	l2292
	line	202
	
l913:
	line	203
	movf	((c:___fladd@aexp))^0500h,c,w
	btfsc	status,2
	goto	u1761
	goto	u1760
u1761:
	goto	l2304
u1760:
	line	204
	
l2296:
	movlw	low(01h)
	addwf	((c:___fladd@b))^0500h,c
	movlw	0
	addwfc	((c:___fladd@b+1))^0500h,c
	addwfc	((c:___fladd@b+2))^0500h,c
	addwfc	((c:___fladd@b+3))^0500h,c
	line	205
	
l2298:
	
	btfss	((c:___fladd@b+3))^0500h,c,(24)&7
	goto	u1771
	goto	u1770
u1771:
	goto	l2304
u1770:
	line	206
	
l2300:
	movff	(c:___fladd@b),??___fladd+0
	movff	(c:___fladd@b+1),??___fladd+0+1
	movff	(c:___fladd@b+2),??___fladd+0+2
	movff	(c:___fladd@b+3),??___fladd+0+3
	rlcf	(??___fladd+0+3)^0500h,c,w
	rrcf	(??___fladd+0+3)^0500h,c
	rrcf	(??___fladd+0+2)^0500h,c
	rrcf	(??___fladd+0+1)^0500h,c
	rrcf	(??___fladd+0)^0500h,c
	movff	??___fladd+0,(c:___fladd@b)
	movff	??___fladd+0+1,(c:___fladd@b+1)
	movff	??___fladd+0+2,(c:___fladd@b+2)
	movff	??___fladd+0+3,(c:___fladd@b+3)
	line	207
		incf	((c:___fladd@bexp))^0500h,c,w
	btfsc	status,2
	goto	u1781
	goto	u1780

u1781:
	goto	l2304
u1780:
	line	208
	
l2302:
	incf	((c:___fladd@bexp))^0500h,c
	line	215
	
l2304:
		incf	((c:___fladd@bexp))^0500h,c,w
	btfsc	status,2
	goto	u1791
	goto	u1790

u1791:
	goto	l2308
u1790:
	
l2306:
	movf	((c:___fladd@bexp))^0500h,c,w
	btfss	status,2
	goto	u1801
	goto	u1800
u1801:
	goto	l920
u1800:
	line	216
	
l2308:
	movlw	low(0)
	movwf	((c:___fladd@b))^0500h,c
	movlw	high(0)
	movwf	((c:___fladd@b+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:___fladd@b+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:___fladd@b+3))^0500h,c
	line	218
	movf	((c:___fladd@bexp))^0500h,c,w
	btfss	status,2
	goto	u1811
	goto	u1810
u1811:
	goto	l920
u1810:
	line	219
	
l2310:
	clrf	((c:___fladd@signs))^0500h,c
	line	221
	
l920:
	line	225
	
	btfss	((c:___fladd@bexp))^0500h,c,(0)&7
	goto	u1821
	goto	u1820
u1821:
	goto	l2314
u1820:
	line	226
	
l2312:
	bsf	(0+(7/8)+0+((c:___fladd@b)+02h))^0500h,c,(7)&7
	line	227
	goto	l2316
	line	230
	
l2314:
	bcf	(0+(7/8)+0+((c:___fladd@b)+02h))^0500h,c,(7)&7
	line	232
	
l2316:
	bcf	status,0
	rrcf	((c:___fladd@bexp))^0500h,c,w
	movwf	(0+((c:___fladd@b)+03h))^0500h,c
	line	233
	
l2318:
	
	btfss	((c:___fladd@signs))^0500h,c,(7)&7
	goto	u1831
	goto	u1830
u1831:
	goto	l2322
u1830:
	line	234
	
l2320:
	bsf	(0+(7/8)+0+((c:___fladd@b)+03h))^0500h,c,(7)&7
	line	236
	
l2322:
	movff	(c:___fladd@b),(c:?___fladd)
	movff	(c:___fladd@b+1),(c:?___fladd+1)
	movff	(c:___fladd@b+2),(c:?___fladd+2)
	movff	(c:___fladd@b+3),(c:?___fladd+3)
	line	237
	
l896:
	return	;funcret
	callstack 0
GLOBAL	__end_of___fladd
	__end_of___fladd:
	signat	___fladd,8316
	global	___flmul

;; *************** function ___flmul *****************
;; Defined at:
;;		line 8 in file "C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\sprcmul.c"
;; Parameters:    Size  Location     Type
;;  b               4   55[COMRAM] unsigned char 
;;  a               4   59[COMRAM] unsigned char 
;; Auto vars:     Size  Location     Type
;;  prod            4   74[COMRAM] struct .
;;  grs             4   68[COMRAM] unsigned long 
;;  temp            2   78[COMRAM] struct .
;;  bexp            1   73[COMRAM] unsigned char 
;;  aexp            1   72[COMRAM] unsigned char 
;;  sign            1   67[COMRAM] unsigned char 
;; Return value:  Size  Location     Type
;;                  4   55[COMRAM] unsigned char 
;; Registers used:
;;		wreg, status,2, status,0, prodl, prodh
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         8       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:        13       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:        25       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       25 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_thermistor_centi_c
;;		_logf
;; This function uses a non-reentrant model
;;
psect	text7,class=CODE,space=0,reloc=2,group=1
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\sprcmul.c"
	line	8
global __ptext7
__ptext7:
psect	text7
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\sprcmul.c"
	line	8
	
___flmul:
;incstack = 0
	callstack 124
	line	17
	
l2484:
	movf	(0+((c:___flmul@b)+03h))^0500h,c,w
	andlw	low(080h)
	movwf	((c:___flmul@sign))^0500h,c
	line	18
	movf	(0+((c:___flmul@b)+03h))^0500h,c,w
	addwf	(0+((c:___flmul@b)+03h))^0500h,c,w
	movwf	((c:___flmul@bexp))^0500h,c
	line	19
	
l2486:
	
	btfss	(0+((c:___flmul@b)+02h))^0500h,c,(7)&7
	goto	u2101
	goto	u2100
u2101:
	goto	l2490
u2100:
	line	20
	
l2488:
	bsf	(0+(0/8)+(c:___flmul@bexp))^0500h,c,(0)&7
	line	24
	
l2490:
	movf	((c:___flmul@bexp))^0500h,c,w
	btfsc	status,2
	goto	u2111
	goto	u2110
u2111:
	goto	l2498
u2110:
	line	26
	
l2492:
		incf	((c:___flmul@bexp))^0500h,c,w
	btfss	status,2
	goto	u2121
	goto	u2120

u2121:
	goto	l2496
u2120:
	line	28
	
l2494:
	movlw	low(normalize32(0x0))
	movwf	((c:___flmul@b))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:___flmul@b+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:___flmul@b+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:___flmul@b+3))^0500h,c
	line	31
	
l2496:
	bsf	(0+(23/8)+(c:___flmul@b))^0500h,c,(23)&7
	line	33
	goto	l2500
	line	36
	
l2498:
	movlw	low(normalize32(0x0))
	movwf	((c:___flmul@b))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:___flmul@b+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:___flmul@b+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:___flmul@b+3))^0500h,c
	line	39
	
l2500:
	movf	(0+((c:___flmul@a)+03h))^0500h,c,w
	andlw	low(080h)
	xorwf	((c:___flmul@sign))^0500h,c
	line	40
	
l2502:
	movf	(0+((c:___flmul@a)+03h))^0500h,c,w
	addwf	(0+((c:___flmul@a)+03h))^0500h,c,w
	movwf	((c:___flmul@aexp))^0500h,c
	line	41
	
l2504:
	
	btfss	(0+((c:___flmul@a)+02h))^0500h,c,(7)&7
	goto	u2131
	goto	u2130
u2131:
	goto	l2508
u2130:
	line	42
	
l2506:
	bsf	(0+(0/8)+(c:___flmul@aexp))^0500h,c,(0)&7
	line	45
	
l2508:
	movf	((c:___flmul@aexp))^0500h,c,w
	btfsc	status,2
	goto	u2141
	goto	u2140
u2141:
	goto	l2516
u2140:
	line	48
	
l2510:
		incf	((c:___flmul@aexp))^0500h,c,w
	btfss	status,2
	goto	u2151
	goto	u2150

u2151:
	goto	l2514
u2150:
	line	50
	
l2512:
	movlw	low(normalize32(0x0))
	movwf	((c:___flmul@a))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:___flmul@a+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:___flmul@a+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:___flmul@a+3))^0500h,c
	line	53
	
l2514:
	bsf	(0+(23/8)+(c:___flmul@a))^0500h,c,(23)&7
	line	54
	goto	l973
	line	57
	
l2516:
	movlw	low(normalize32(0x0))
	movwf	((c:___flmul@a))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:___flmul@a+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:___flmul@a+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:___flmul@a+3))^0500h,c
	line	58
	
l973:
	line	65
	movf	((c:___flmul@aexp))^0500h,c,w
	btfsc	status,2
	goto	u2161
	goto	u2160
u2161:
	goto	l2520
u2160:
	
l2518:
	movf	((c:___flmul@bexp))^0500h,c,w
	btfss	status,2
	goto	u2171
	goto	u2170
u2171:
	goto	l2524
u2170:
	line	66
	
l2520:
	movlw	low(normalize32(0x0))
	movwf	((c:?___flmul))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:?___flmul+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:?___flmul+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:?___flmul+3))^0500h,c
	goto	l977
	line	95
	
l2524:
	movf	(0+((c:___flmul@a)+02h))^0500h,c,w
	mulwf	((c:___flmul@b))^0500h,c
	movff	prodl,(c:___flmul@temp)
	movff	prodh,(c:___flmul@temp+1)
	line	96
	
l2526:
	movf	((c:___flmul@temp))^0500h,c,w
	movwf	((c:___flmul@grs))^0500h,c
	clrf	((c:___flmul@grs+1))^0500h,c
	clrf	((c:___flmul@grs+2))^0500h,c
	clrf	((c:___flmul@grs+3))^0500h,c

	line	97
	
l2528:
	movf	(0+((c:___flmul@temp)+01h))^0500h,c,w
	movwf	((c:___flmul@prod))^0500h,c
	clrf	((c:___flmul@prod+1))^0500h,c
	clrf	((c:___flmul@prod+2))^0500h,c
	clrf	((c:___flmul@prod+3))^0500h,c

	line	98
	movf	(0+((c:___flmul@a)+01h))^0500h,c,w
	mulwf	(0+((c:___flmul@b)+01h))^0500h,c
	movff	prodl,(c:___flmul@temp)
	movff	prodh,(c:___flmul@temp+1)
	line	99
	
l2530:
	movf	((c:___flmul@temp))^0500h,c,w
	addwf	((c:___flmul@grs))^0500h,c
	movlw	0
	addwfc	((c:___flmul@grs+1))^0500h,c
	addwfc	((c:___flmul@grs+2))^0500h,c
	addwfc	((c:___flmul@grs+3))^0500h,c
	line	100
	
l2532:
	movf	(0+((c:___flmul@temp)+01h))^0500h,c,w
	addwf	((c:___flmul@prod))^0500h,c
	movlw	0
	addwfc	((c:___flmul@prod+1))^0500h,c
	addwfc	((c:___flmul@prod+2))^0500h,c
	addwfc	((c:___flmul@prod+3))^0500h,c
	line	101
	movf	((c:___flmul@a))^0500h,c,w
	mulwf	(0+((c:___flmul@b)+02h))^0500h,c
	movff	prodl,(c:___flmul@temp)
	movff	prodh,(c:___flmul@temp+1)
	line	102
	
l2534:
	movf	((c:___flmul@temp))^0500h,c,w
	addwf	((c:___flmul@grs))^0500h,c
	movlw	0
	addwfc	((c:___flmul@grs+1))^0500h,c
	addwfc	((c:___flmul@grs+2))^0500h,c
	addwfc	((c:___flmul@grs+3))^0500h,c
	line	103
	
l2536:
	movf	(0+((c:___flmul@temp)+01h))^0500h,c,w
	addwf	((c:___flmul@prod))^0500h,c
	movlw	0
	addwfc	((c:___flmul@prod+1))^0500h,c
	addwfc	((c:___flmul@prod+2))^0500h,c
	addwfc	((c:___flmul@prod+3))^0500h,c
	line	104
	
l2538:
	movff	(c:___flmul@grs+2),(c:___flmul@grs+3)
	movff	(c:___flmul@grs+1),(c:___flmul@grs+2)
	movff	(c:___flmul@grs),(c:___flmul@grs+1)
	clrf	((c:___flmul@grs))^0500h,c
	line	105
	
l2540:
	movf	((c:___flmul@a))^0500h,c,w
	mulwf	(0+((c:___flmul@b)+01h))^0500h,c
	movff	prodl,(c:___flmul@temp)
	movff	prodh,(c:___flmul@temp+1)
	line	106
	
l2542:
	movf	((c:___flmul@temp))^0500h,c,w
	addwf	((c:___flmul@grs))^0500h,c
	movf	((c:___flmul@temp+1))^0500h,c,w
	addwfc	((c:___flmul@grs+1))^0500h,c
	movlw	0
	addwfc	((c:___flmul@grs+2))^0500h,c
	movlw	0
	addwfc	((c:___flmul@grs+3))^0500h,c

	line	107
	
l2544:
	movf	(0+((c:___flmul@a)+01h))^0500h,c,w
	mulwf	((c:___flmul@b))^0500h,c
	movff	prodl,(c:___flmul@temp)
	movff	prodh,(c:___flmul@temp+1)
	line	108
	
l2546:
	movf	((c:___flmul@temp))^0500h,c,w
	addwf	((c:___flmul@grs))^0500h,c
	movf	((c:___flmul@temp+1))^0500h,c,w
	addwfc	((c:___flmul@grs+1))^0500h,c
	movlw	0
	addwfc	((c:___flmul@grs+2))^0500h,c
	movlw	0
	addwfc	((c:___flmul@grs+3))^0500h,c

	line	109
	
l2548:
	movff	(c:___flmul@grs+2),(c:___flmul@grs+3)
	movff	(c:___flmul@grs+1),(c:___flmul@grs+2)
	movff	(c:___flmul@grs),(c:___flmul@grs+1)
	clrf	((c:___flmul@grs))^0500h,c
	line	110
	movf	((c:___flmul@a))^0500h,c,w
	mulwf	((c:___flmul@b))^0500h,c
	movff	prodl,(c:___flmul@temp)
	movff	prodh,(c:___flmul@temp+1)
	line	111
	
l2550:
	movf	((c:___flmul@temp))^0500h,c,w
	addwf	((c:___flmul@grs))^0500h,c
	movf	((c:___flmul@temp+1))^0500h,c,w
	addwfc	((c:___flmul@grs+1))^0500h,c
	movlw	0
	addwfc	((c:___flmul@grs+2))^0500h,c
	movlw	0
	addwfc	((c:___flmul@grs+3))^0500h,c

	line	112
	
l2552:
	movf	(0+((c:___flmul@a)+02h))^0500h,c,w
	mulwf	(0+((c:___flmul@b)+01h))^0500h,c
	movff	prodl,(c:___flmul@temp)
	movff	prodh,(c:___flmul@temp+1)
	line	113
	movf	((c:___flmul@temp))^0500h,c,w
	addwf	((c:___flmul@prod))^0500h,c
	movf	((c:___flmul@temp+1))^0500h,c,w
	addwfc	((c:___flmul@prod+1))^0500h,c
	movlw	0
	addwfc	((c:___flmul@prod+2))^0500h,c
	movlw	0
	addwfc	((c:___flmul@prod+3))^0500h,c

	line	114
	
l2554:
	movf	(0+((c:___flmul@a)+01h))^0500h,c,w
	mulwf	(0+((c:___flmul@b)+02h))^0500h,c
	movff	prodl,(c:___flmul@temp)
	movff	prodh,(c:___flmul@temp+1)
	line	115
	
l2556:
	movf	((c:___flmul@temp))^0500h,c,w
	addwf	((c:___flmul@prod))^0500h,c
	movf	((c:___flmul@temp+1))^0500h,c,w
	addwfc	((c:___flmul@prod+1))^0500h,c
	movlw	0
	addwfc	((c:___flmul@prod+2))^0500h,c
	movlw	0
	addwfc	((c:___flmul@prod+3))^0500h,c

	line	116
	movf	(0+((c:___flmul@a)+02h))^0500h,c,w
	mulwf	(0+((c:___flmul@b)+02h))^0500h,c
	movff	prodl,(c:___flmul@temp)
	movff	prodh,(c:___flmul@temp+1)
	line	117
	
l2558:
	movf	((c:___flmul@temp))^0500h,c,w
	movwf	(??___flmul+0)^0500h,c
	movf	((c:___flmul@temp+1))^0500h,c,w
	movwf	1+(??___flmul+0)^0500h,c
	
	clrf	2+(??___flmul+0)^0500h,c
	
	clrf	3+(??___flmul+0)^0500h,c
	movff	??___flmul+0+2,??___flmul+0+3
	movff	??___flmul+0+1,??___flmul+0+2
	movff	??___flmul+0,??___flmul+0+1
	clrf	(??___flmul+0)^0500h,c
	movf	(??___flmul+0)^0500h,c,w
	addwf	((c:___flmul@prod))^0500h,c
	movf	(??___flmul+0+1)^0500h,c,w
	addwfc	((c:___flmul@prod+1))^0500h,c
	movf	(??___flmul+0+2)^0500h,c,w
	addwfc	((c:___flmul@prod+2))^0500h,c
	movf	(??___flmul+0+3)^0500h,c,w
	addwfc	((c:___flmul@prod+3))^0500h,c

	line	145
	
l2560:
	movff	(c:___flmul@grs),??___flmul+0
	movff	(c:___flmul@grs+1),??___flmul+0+1
	movff	(c:___flmul@grs+2),??___flmul+0+2
	movff	(c:___flmul@grs+3),??___flmul+0+3
	movlw	018h+1
	goto	u2180
u2185:
	bcf	status,0
	rrcf	(??___flmul+0+3)^0500h,c
	rrcf	(??___flmul+0+2)^0500h,c
	rrcf	(??___flmul+0+1)^0500h,c
	rrcf	(??___flmul+0)^0500h,c
u2180:
	decfsz	wreg
	goto	u2185
	movf	(??___flmul+0)^0500h,c,w
	addwf	((c:___flmul@prod))^0500h,c
	movf	(??___flmul+0+1)^0500h,c,w
	addwfc	((c:___flmul@prod+1))^0500h,c
	movf	(??___flmul+0+2)^0500h,c,w
	addwfc	((c:___flmul@prod+2))^0500h,c
	movf	(??___flmul+0+3)^0500h,c,w
	addwfc	((c:___flmul@prod+3))^0500h,c

	line	146
	
l2562:
	movff	(c:___flmul@grs+2),(c:___flmul@grs+3)
	movff	(c:___flmul@grs+1),(c:___flmul@grs+2)
	movff	(c:___flmul@grs),(c:___flmul@grs+1)
	clrf	((c:___flmul@grs))^0500h,c
	line	149
	
l2564:
	movf	((c:___flmul@aexp))^0500h,c,w
	movff	(c:___flmul@bexp),??___flmul+0
	clrf	(??___flmul+0+1)^0500h,c
	addwf	(??___flmul+0)^0500h,c
	movlw	0
	addwfc	(??___flmul+0+1)^0500h,c
	movlw	low(-126)
	addwf	(??___flmul+0)^0500h,c,w
	movwf	((c:___flmul@temp))^0500h,c
	movlw	high(-126)
	addwfc	(??___flmul+0+1)^0500h,c,w
	movwf	1+((c:___flmul@temp))^0500h,c
	line	152
	goto	l2572
	line	153
	
l2566:
	bcf	status,0
	rlcf	((c:___flmul@prod))^0500h,c
	rlcf	((c:___flmul@prod+1))^0500h,c
	rlcf	((c:___flmul@prod+2))^0500h,c
	rlcf	((c:___flmul@prod+3))^0500h,c
	line	154
	
l2568:
	
	btfss	((c:___flmul@grs+3))^0500h,c,(31)&7
	goto	u2191
	goto	u2190
u2191:
	goto	l980
u2190:
	line	155
	
l2570:
	bsf	(0+(0/8)+(c:___flmul@prod))^0500h,c,(0)&7
	line	156
	
l980:
	line	157
	bcf	status,0
	rlcf	((c:___flmul@grs))^0500h,c
	rlcf	((c:___flmul@grs+1))^0500h,c
	rlcf	((c:___flmul@grs+2))^0500h,c
	rlcf	((c:___flmul@grs+3))^0500h,c
	line	158
	decf	((c:___flmul@temp))^0500h,c
	btfss	status,0
	decf	((c:___flmul@temp+1))^0500h,c
	line	152
	
l2572:
	
	btfss	((c:___flmul@prod+2))^0500h,c,(23)&7
	goto	u2201
	goto	u2200
u2201:
	goto	l2566
u2200:
	
l981:
	line	163
	clrf	((c:___flmul@aexp))^0500h,c
	line	164
	
	btfss	((c:___flmul@grs+3))^0500h,c,(31)&7
	goto	u2211
	goto	u2210
u2211:
	goto	l982
u2210:
	line	165
	
l2574:
	movlw	0FFh
	andwf	((c:___flmul@grs))^0500h,c,w
	movwf	(??___flmul+0)^0500h,c
	movlw	0FFh
	andwf	((c:___flmul@grs+1))^0500h,c,w
	movwf	1+(??___flmul+0)^0500h,c
	
	movlw	0FFh
	andwf	((c:___flmul@grs+2))^0500h,c,w
	movwf	2+(??___flmul+0)^0500h,c
	
	movlw	07Fh
	andwf	((c:___flmul@grs+3))^0500h,c,w
	movwf	3+(??___flmul+0)^0500h,c
	movf	(??___flmul+0)^0500h,c,w
iorwf	(??___flmul+0+1)^0500h,c,w
iorwf	(??___flmul+0+2)^0500h,c,w
iorwf	(??___flmul+0+3)^0500h,c,w
	btfsc	status,2
	goto	u2221
	goto	u2220

u2221:
	goto	l983
u2220:
	line	166
	
l2576:
	movlw	low(01h)
	movwf	((c:___flmul@aexp))^0500h,c
	line	167
	goto	l982
	line	168
	
l983:
	line	169
	
	btfss	((c:___flmul@prod))^0500h,c,(0)&7
	goto	u2231
	goto	u2230
u2231:
	goto	l982
u2230:
	goto	l2576
	line	173
	
l982:
	line	174
	movf	((c:___flmul@aexp))^0500h,c,w
	btfsc	status,2
	goto	u2241
	goto	u2240
u2241:
	goto	l2588
u2240:
	line	175
	
l2580:
	movlw	low(01h)
	addwf	((c:___flmul@prod))^0500h,c
	movlw	0
	addwfc	((c:___flmul@prod+1))^0500h,c
	addwfc	((c:___flmul@prod+2))^0500h,c
	addwfc	((c:___flmul@prod+3))^0500h,c
	line	176
	
l2582:
	
	btfss	((c:___flmul@prod+3))^0500h,c,(24)&7
	goto	u2251
	goto	u2250
u2251:
	goto	l2588
u2250:
	line	177
	
l2584:
	movff	(c:___flmul@prod),??___flmul+0
	movff	(c:___flmul@prod+1),??___flmul+0+1
	movff	(c:___flmul@prod+2),??___flmul+0+2
	movff	(c:___flmul@prod+3),??___flmul+0+3
	rlcf	(??___flmul+0+3)^0500h,c,w
	rrcf	(??___flmul+0+3)^0500h,c
	rrcf	(??___flmul+0+2)^0500h,c
	rrcf	(??___flmul+0+1)^0500h,c
	rrcf	(??___flmul+0)^0500h,c
	movff	??___flmul+0,(c:___flmul@prod)
	movff	??___flmul+0+1,(c:___flmul@prod+1)
	movff	??___flmul+0+2,(c:___flmul@prod+2)
	movff	??___flmul+0+3,(c:___flmul@prod+3)
	line	178
	
l2586:
	infsnz	((c:___flmul@temp))^0500h,c
	incf	((c:___flmul@temp+1))^0500h,c
	line	183
	
l2588:
	btfsc	((c:___flmul@temp+1))^0500h,c,7
	goto	u2261
	movf	((c:___flmul@temp+1))^0500h,c,w
	bnz	u2260
	incf	((c:___flmul@temp))^0500h,c,w
	btfss	status,0
	goto	u2261
	goto	u2260

u2261:
	goto	l2592
u2260:
	line	184
	
l2590:
	movlw	low(07F800000h)
	movwf	((c:___flmul@prod))^0500h,c
	movlw	high(07F800000h)
	movwf	((c:___flmul@prod+1))^0500h,c
	movlw	low highword(07F800000h)
	movwf	((c:___flmul@prod+2))^0500h,c
	movlw	high highword(07F800000h)
	movwf	((c:___flmul@prod+3))^0500h,c
	line	185
	goto	l2606
	line	187
	
l2592:
	btfsc	((c:___flmul@temp+1))^0500h,c,7
	goto	u2270
	movf	((c:___flmul@temp+1))^0500h,c,w
	bnz	u2271
	decf	((c:___flmul@temp))^0500h,c,w
	btfsc	status,0
	goto	u2271
	goto	u2270

u2271:
	goto	l990
u2270:
	line	188
	
l2594:
	movlw	low(0)
	movwf	((c:___flmul@prod))^0500h,c
	movlw	high(0)
	movwf	((c:___flmul@prod+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:___flmul@prod+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:___flmul@prod+3))^0500h,c
	line	190
	
l2596:
	clrf	((c:___flmul@sign))^0500h,c
	line	191
	goto	l2606
	line	192
	
l990:
	line	194
	movff	(c:___flmul@temp),(c:___flmul@bexp)
	line	195
	
l2598:
	movlw	0FFh
	andwf	((c:___flmul@prod))^0500h,c
	movlw	0FFh
	andwf	((c:___flmul@prod+1))^0500h,c
	movlw	07Fh
	andwf	((c:___flmul@prod+2))^0500h,c
	movlw	0
	andwf	((c:___flmul@prod+3))^0500h,c
	line	196
	
l2600:
	
	btfss	((c:___flmul@bexp))^0500h,c,(0)&7
	goto	u2281
	goto	u2280
u2281:
	goto	l2604
u2280:
	line	197
	
l2602:
	bsf	(0+(7/8)+0+((c:___flmul@prod)+02h))^0500h,c,(7)&7
	line	199
	
l2604:
	bcf	status,0
	rrcf	((c:___flmul@bexp))^0500h,c,w
	movwf	(0+((c:___flmul@prod)+03h))^0500h,c
	line	201
	
l2606:
	movf	((c:___flmul@sign))^0500h,c,w
	iorwf	(0+((c:___flmul@prod)+03h))^0500h,c
	line	203
	
l2608:
	movff	(c:___flmul@prod),(c:?___flmul)
	movff	(c:___flmul@prod+1),(c:?___flmul+1)
	movff	(c:___flmul@prod+2),(c:?___flmul+2)
	movff	(c:___flmul@prod+3),(c:?___flmul+3)
	line	205
	
l977:
	return	;funcret
	callstack 0
GLOBAL	__end_of___flmul
	__end_of___flmul:
	signat	___flmul,8316
	global	___fldiv

;; *************** function ___fldiv *****************
;; Defined at:
;;		line 11 in file "C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\sprcdiv.c"
;; Parameters:    Size  Location     Type
;;  b               4   14[COMRAM] unsigned char 
;;  a               4   18[COMRAM] unsigned char 
;; Auto vars:     Size  Location     Type
;;  grs             4   33[COMRAM] unsigned long 
;;  rem             4   26[COMRAM] unsigned long 
;;  new_exp         2   31[COMRAM] short 
;;  aexp            1   38[COMRAM] unsigned char 
;;  bexp            1   37[COMRAM] unsigned char 
;;  sign            1   30[COMRAM] unsigned char 
;; Return value:  Size  Location     Type
;;                  4   14[COMRAM] unsigned char 
;; Registers used:
;;		wreg, status,2, status,0
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         8       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:        13       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:        25       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       25 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_thermistor_centi_c
;;		_logf
;; This function uses a non-reentrant model
;;
psect	text8,class=CODE,space=0,reloc=2,group=1
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\sprcdiv.c"
	line	11
global __ptext8
__ptext8:
psect	text8
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\sprcdiv.c"
	line	11
	
___fldiv:
;incstack = 0
	callstack 124
	line	26
	
l2348:
	movf	(0+((c:___fldiv@b)+03h))^0500h,c,w
	andlw	low(080h)
	movwf	((c:___fldiv@sign))^0500h,c
	line	27
	movf	(0+((c:___fldiv@b)+03h))^0500h,c,w
	addwf	(0+((c:___fldiv@b)+03h))^0500h,c,w
	movwf	((c:___fldiv@bexp))^0500h,c
	line	28
	
l2350:
	
	btfss	(0+((c:___fldiv@b)+02h))^0500h,c,(7)&7
	goto	u1871
	goto	u1870
u1871:
	goto	l2354
u1870:
	line	29
	
l2352:
	bsf	(0+(0/8)+(c:___fldiv@bexp))^0500h,c,(0)&7
	line	33
	
l2354:
	movf	((c:___fldiv@bexp))^0500h,c,w
	btfsc	status,2
	goto	u1881
	goto	u1880
u1881:
	goto	l2364
u1880:
	line	35
	
l2356:
		incf	((c:___fldiv@bexp))^0500h,c,w
	btfss	status,2
	goto	u1891
	goto	u1890

u1891:
	goto	l2360
u1890:
	line	37
	
l2358:
	movlw	low(normalize32(0x0))
	movwf	((c:___fldiv@b))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:___fldiv@b+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:___fldiv@b+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:___fldiv@b+3))^0500h,c
	line	40
	
l2360:
	bsf	(0+(23/8)+(c:___fldiv@b))^0500h,c,(23)&7
	line	42
	
l2362:
	clrf	(0+((c:___fldiv@b)+03h))^0500h,c
	line	43
	goto	l2366
	line	46
	
l2364:
	movlw	low(normalize32(0x0))
	movwf	((c:___fldiv@b))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:___fldiv@b+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:___fldiv@b+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:___fldiv@b+3))^0500h,c
	line	49
	
l2366:
	movf	(0+((c:___fldiv@a)+03h))^0500h,c,w
	andlw	low(080h)
	xorwf	((c:___fldiv@sign))^0500h,c
	line	50
	
l2368:
	movf	(0+((c:___fldiv@a)+03h))^0500h,c,w
	addwf	(0+((c:___fldiv@a)+03h))^0500h,c,w
	movwf	((c:___fldiv@aexp))^0500h,c
	line	51
	
l2370:
	
	btfss	(0+((c:___fldiv@a)+02h))^0500h,c,(7)&7
	goto	u1901
	goto	u1900
u1901:
	goto	l2374
u1900:
	line	52
	
l2372:
	bsf	(0+(0/8)+(c:___fldiv@aexp))^0500h,c,(0)&7
	line	56
	
l2374:
	movf	((c:___fldiv@aexp))^0500h,c,w
	btfsc	status,2
	goto	u1911
	goto	u1910
u1911:
	goto	l2384
u1910:
	line	58
	
l2376:
		incf	((c:___fldiv@aexp))^0500h,c,w
	btfss	status,2
	goto	u1921
	goto	u1920

u1921:
	goto	l2380
u1920:
	line	60
	
l2378:
	movlw	low(normalize32(0x0))
	movwf	((c:___fldiv@a))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:___fldiv@a+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:___fldiv@a+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:___fldiv@a+3))^0500h,c
	line	63
	
l2380:
	bsf	(0+(23/8)+(c:___fldiv@a))^0500h,c,(23)&7
	line	65
	
l2382:
	clrf	(0+((c:___fldiv@a)+03h))^0500h,c
	line	66
	goto	l2386
	line	69
	
l2384:
	movlw	low(normalize32(0x0))
	movwf	((c:___fldiv@a))^0500h,c
	movlw	high(normalize32(0x0))
	movwf	((c:___fldiv@a+1))^0500h,c
	movlw	low highword(normalize32(0x0))
	movwf	((c:___fldiv@a+2))^0500h,c
	movlw	high highword(normalize32(0x0))
	movwf	((c:___fldiv@a+3))^0500h,c
	line	75
	
l2386:
	movf	((c:___fldiv@a))^0500h,c,w
iorwf	((c:___fldiv@a+1))^0500h,c,w
iorwf	((c:___fldiv@a+2))^0500h,c,w
iorwf	((c:___fldiv@a+3))^0500h,c,w
	btfss	status,2
	goto	u1931
	goto	u1930

u1931:
	goto	l2398
u1930:
	line	76
	
l2388:
	movlw	low(0)
	movwf	((c:___fldiv@b))^0500h,c
	movlw	high(0)
	movwf	((c:___fldiv@b+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:___fldiv@b+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:___fldiv@b+3))^0500h,c
	line	77
	
l2390:
	movlw	low(07F80h)
	iorwf	(0+((c:___fldiv@b)+02h))^0500h,c
	movlw	high(07F80h)
	iorwf	(1+((c:___fldiv@b)+02h))^0500h,c
	line	78
	
l2392:
	movf	((c:___fldiv@sign))^0500h,c,w
	iorwf	(0+((c:___fldiv@b)+03h))^0500h,c
	line	79
	
l2394:
	movff	(c:___fldiv@b),(c:?___fldiv)
	movff	(c:___fldiv@b+1),(c:?___fldiv+1)
	movff	(c:___fldiv@b+2),(c:?___fldiv+2)
	movff	(c:___fldiv@b+3),(c:?___fldiv+3)
	goto	l941
	line	83
	
l2398:
	movf	((c:___fldiv@bexp))^0500h,c,w
	btfss	status,2
	goto	u1941
	goto	u1940
u1941:
	goto	l2406
u1940:
	line	84
	
l2400:
	line	85
	
l2402:
	movlw	low(0)
	movwf	((c:?___fldiv))^0500h,c
	movlw	high(0)
	movwf	((c:?___fldiv+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:?___fldiv+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:?___fldiv+3))^0500h,c
	goto	l941
	line	89
	
l2406:
	movf	((c:___fldiv@aexp))^0500h,c,w
	movff	(c:___fldiv@bexp),??___fldiv+0
	clrf	(??___fldiv+0+1)^0500h,c
	subwf	(??___fldiv+0)^0500h,c
	movlw	0
	subwfb	(??___fldiv+0+1)^0500h,c
	movlw	low(07Fh)
	addwf	(??___fldiv+0)^0500h,c,w
	movwf	((c:___fldiv@new_exp))^0500h,c
	movlw	high(07Fh)
	addwfc	(??___fldiv+0+1)^0500h,c,w
	movwf	1+((c:___fldiv@new_exp))^0500h,c
	line	92
	
l2408:
	movff	(c:___fldiv@b),(c:___fldiv@rem)
	movff	(c:___fldiv@b+1),(c:___fldiv@rem+1)
	movff	(c:___fldiv@b+2),(c:___fldiv@rem+2)
	movff	(c:___fldiv@b+3),(c:___fldiv@rem+3)
	line	93
	
l2410:
	movlw	low(0)
	movwf	((c:___fldiv@b))^0500h,c
	movlw	high(0)
	movwf	((c:___fldiv@b+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:___fldiv@b+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:___fldiv@b+3))^0500h,c
	line	94
	
l2412:
	movlw	low(0)
	movwf	((c:___fldiv@grs))^0500h,c
	movlw	high(0)
	movwf	((c:___fldiv@grs+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:___fldiv@grs+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:___fldiv@grs+3))^0500h,c
	line	96
	
l2414:
	clrf	((c:___fldiv@aexp))^0500h,c
	line	97
	goto	l943
	line	100
	
l2416:
	movf	((c:___fldiv@aexp))^0500h,c,w
	btfsc	status,2
	goto	u1951
	goto	u1950
u1951:
	goto	l2424
u1950:
	line	101
	
l2418:
	bcf	status,0
	rlcf	((c:___fldiv@rem))^0500h,c
	rlcf	((c:___fldiv@rem+1))^0500h,c
	rlcf	((c:___fldiv@rem+2))^0500h,c
	rlcf	((c:___fldiv@rem+3))^0500h,c
	line	102
	bcf	status,0
	rlcf	((c:___fldiv@b))^0500h,c
	rlcf	((c:___fldiv@b+1))^0500h,c
	rlcf	((c:___fldiv@b+2))^0500h,c
	rlcf	((c:___fldiv@b+3))^0500h,c
	line	103
	
l2420:
	
	btfss	((c:___fldiv@grs+3))^0500h,c,(31)&7
	goto	u1961
	goto	u1960
u1961:
	goto	l946
u1960:
	line	104
	
l2422:
	bsf	(0+(0/8)+(c:___fldiv@b))^0500h,c,(0)&7
	line	105
	
l946:
	line	106
	bcf	status,0
	rlcf	((c:___fldiv@grs))^0500h,c
	rlcf	((c:___fldiv@grs+1))^0500h,c
	rlcf	((c:___fldiv@grs+2))^0500h,c
	rlcf	((c:___fldiv@grs+3))^0500h,c
	line	112
	
l2424:
		movf	((c:___fldiv@a))^0500h,c,w
	subwf	((c:___fldiv@rem))^0500h,c,w
	movf	((c:___fldiv@a+1))^0500h,c,w
	subwfb	((c:___fldiv@rem+1))^0500h,c,w
	movf	((c:___fldiv@a+2))^0500h,c,w
	subwfb	((c:___fldiv@rem+2))^0500h,c,w
	movf	((c:___fldiv@a+3))^0500h,c,w
	subwfb	((c:___fldiv@rem+3))^0500h,c,w
	btfss	status,0
	goto	u1971
	goto	u1970

u1971:
	goto	l2430
u1970:
	line	115
	
l2426:
	bsf	(0+(30/8)+(c:___fldiv@grs))^0500h,c,(30)&7
	line	116
	
l2428:
	movf	((c:___fldiv@a))^0500h,c,w
	subwf	((c:___fldiv@rem))^0500h,c
	movf	((c:___fldiv@a+1))^0500h,c,w
	subwfb	((c:___fldiv@rem+1))^0500h,c
	movf	((c:___fldiv@a+2))^0500h,c,w
	subwfb	((c:___fldiv@rem+2))^0500h,c
	movf	((c:___fldiv@a+3))^0500h,c,w
	subwfb	((c:___fldiv@rem+3))^0500h,c
	line	118
	
l2430:
	incf	((c:___fldiv@aexp))^0500h,c
	line	119
	
l943:
	line	97
		movlw	01Ah-1
	cpfsgt	((c:___fldiv@aexp))^0500h,c
	goto	u1981
	goto	u1980

u1981:
	goto	l2416
u1980:
	line	122
	
l2432:
	movf	((c:___fldiv@rem))^0500h,c,w
iorwf	((c:___fldiv@rem+1))^0500h,c,w
iorwf	((c:___fldiv@rem+2))^0500h,c,w
iorwf	((c:___fldiv@rem+3))^0500h,c,w
	btfsc	status,2
	goto	u1991
	goto	u1990

u1991:
	goto	l2442
u1990:
	line	123
	
l2434:
	bsf	(0+(0/8)+(c:___fldiv@grs))^0500h,c,(0)&7
	goto	l2442
	line	128
	
l2436:
	bcf	status,0
	rlcf	((c:___fldiv@b))^0500h,c
	rlcf	((c:___fldiv@b+1))^0500h,c
	rlcf	((c:___fldiv@b+2))^0500h,c
	rlcf	((c:___fldiv@b+3))^0500h,c
	line	129
	
l2438:
	
	btfss	((c:___fldiv@grs+3))^0500h,c,(31)&7
	goto	u2001
	goto	u2000
u2001:
	goto	l952
u2000:
	line	130
	
l2440:
	bsf	(0+(0/8)+(c:___fldiv@b))^0500h,c,(0)&7
	line	131
	
l952:
	line	132
	bcf	status,0
	rlcf	((c:___fldiv@grs))^0500h,c
	rlcf	((c:___fldiv@grs+1))^0500h,c
	rlcf	((c:___fldiv@grs+2))^0500h,c
	rlcf	((c:___fldiv@grs+3))^0500h,c
	line	133
	decf	((c:___fldiv@new_exp))^0500h,c
	btfss	status,0
	decf	((c:___fldiv@new_exp+1))^0500h,c
	line	127
	
l2442:
	
	btfss	((c:___fldiv@b+2))^0500h,c,(23)&7
	goto	u2011
	goto	u2010
u2011:
	goto	l2436
u2010:
	
l953:
	line	139
	clrf	((c:___fldiv@aexp))^0500h,c
	line	140
	
	btfss	((c:___fldiv@grs+3))^0500h,c,(31)&7
	goto	u2021
	goto	u2020
u2021:
	goto	l954
u2020:
	line	141
	
l2444:
	movlw	0FFh
	andwf	((c:___fldiv@grs))^0500h,c,w
	movwf	(??___fldiv+0)^0500h,c
	movlw	0FFh
	andwf	((c:___fldiv@grs+1))^0500h,c,w
	movwf	1+(??___fldiv+0)^0500h,c
	
	movlw	0FFh
	andwf	((c:___fldiv@grs+2))^0500h,c,w
	movwf	2+(??___fldiv+0)^0500h,c
	
	movlw	07Fh
	andwf	((c:___fldiv@grs+3))^0500h,c,w
	movwf	3+(??___fldiv+0)^0500h,c
	movf	(??___fldiv+0)^0500h,c,w
iorwf	(??___fldiv+0+1)^0500h,c,w
iorwf	(??___fldiv+0+2)^0500h,c,w
iorwf	(??___fldiv+0+3)^0500h,c,w
	btfsc	status,2
	goto	u2031
	goto	u2030

u2031:
	goto	l955
u2030:
	line	142
	
l2446:
	movlw	low(01h)
	movwf	((c:___fldiv@aexp))^0500h,c
	line	143
	goto	l954
	line	144
	
l955:
	line	145
	
	btfss	((c:___fldiv@b))^0500h,c,(0)&7
	goto	u2041
	goto	u2040
u2041:
	goto	l954
u2040:
	goto	l2446
	line	149
	
l954:
	line	150
	movf	((c:___fldiv@aexp))^0500h,c,w
	btfsc	status,2
	goto	u2051
	goto	u2050
u2051:
	goto	l2458
u2050:
	line	151
	
l2450:
	movlw	low(01h)
	addwf	((c:___fldiv@b))^0500h,c
	movlw	0
	addwfc	((c:___fldiv@b+1))^0500h,c
	addwfc	((c:___fldiv@b+2))^0500h,c
	addwfc	((c:___fldiv@b+3))^0500h,c
	line	152
	
l2452:
	
	btfss	((c:___fldiv@b+3))^0500h,c,(24)&7
	goto	u2061
	goto	u2060
u2061:
	goto	l2458
u2060:
	line	153
	
l2454:
	movff	(c:___fldiv@b),??___fldiv+0
	movff	(c:___fldiv@b+1),??___fldiv+0+1
	movff	(c:___fldiv@b+2),??___fldiv+0+2
	movff	(c:___fldiv@b+3),??___fldiv+0+3
	rlcf	(??___fldiv+0+3)^0500h,c,w
	rrcf	(??___fldiv+0+3)^0500h,c
	rrcf	(??___fldiv+0+2)^0500h,c
	rrcf	(??___fldiv+0+1)^0500h,c
	rrcf	(??___fldiv+0)^0500h,c
	movff	??___fldiv+0,(c:___fldiv@b)
	movff	??___fldiv+0+1,(c:___fldiv@b+1)
	movff	??___fldiv+0+2,(c:___fldiv@b+2)
	movff	??___fldiv+0+3,(c:___fldiv@b+3)
	line	154
	
l2456:
	infsnz	((c:___fldiv@new_exp))^0500h,c
	incf	((c:___fldiv@new_exp+1))^0500h,c
	line	159
	
l2458:
	btfsc	((c:___fldiv@new_exp+1))^0500h,c,7
	goto	u2071
	movf	((c:___fldiv@new_exp+1))^0500h,c,w
	bnz	u2070
	incf	((c:___fldiv@new_exp))^0500h,c,w
	btfss	status,0
	goto	u2071
	goto	u2070

u2071:
	goto	l2462
u2070:
	line	160
	
l2460:
	movlw	high(0FFh)
	movwf	((c:___fldiv@new_exp+1))^0500h,c
	setf	((c:___fldiv@new_exp))^0500h,c
	line	161
	movlw	low(0)
	movwf	((c:___fldiv@b))^0500h,c
	movlw	high(0)
	movwf	((c:___fldiv@b+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:___fldiv@b+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:___fldiv@b+3))^0500h,c
	line	165
	
l2462:
	btfsc	((c:___fldiv@new_exp+1))^0500h,c,7
	goto	u2080
	movf	((c:___fldiv@new_exp+1))^0500h,c,w
	bnz	u2081
	decf	((c:___fldiv@new_exp))^0500h,c,w
	btfsc	status,0
	goto	u2081
	goto	u2080

u2081:
	goto	l2468
u2080:
	line	166
	
l2464:
	clrf	((c:___fldiv@new_exp+1))^0500h,c
	movlw	low(0)
	movwf	((c:___fldiv@new_exp))^0500h,c
	line	167
	movlw	low(0)
	movwf	((c:___fldiv@b))^0500h,c
	movlw	high(0)
	movwf	((c:___fldiv@b+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:___fldiv@b+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:___fldiv@b+3))^0500h,c
	line	169
	
l2466:
	clrf	((c:___fldiv@sign))^0500h,c
	line	173
	
l2468:
	movff	(c:___fldiv@new_exp),(c:___fldiv@bexp)
	line	175
	
l2470:
	
	btfss	((c:___fldiv@bexp))^0500h,c,(0)&7
	goto	u2091
	goto	u2090
u2091:
	goto	l2474
u2090:
	line	176
	
l2472:
	bsf	(0+(7/8)+0+((c:___fldiv@b)+02h))^0500h,c,(7)&7
	line	177
	goto	l2476
	line	180
	
l2474:
	bcf	(0+(7/8)+0+((c:___fldiv@b)+02h))^0500h,c,(7)&7
	line	182
	
l2476:
	bcf	status,0
	rrcf	((c:___fldiv@bexp))^0500h,c,w
	movwf	(0+((c:___fldiv@b)+03h))^0500h,c
	goto	l2392
	line	185
	
l941:
	return	;funcret
	callstack 0
GLOBAL	__end_of___fldiv
	__end_of___fldiv:
	signat	___fldiv,8316
	global	___fltol

;; *************** function ___fltol *****************
;; Defined at:
;;		line 43 in file "C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\fltol.c"
;; Parameters:    Size  Location     Type
;;  f1              4   55[COMRAM] unsigned char 
;; Auto vars:     Size  Location     Type
;;  exp1            1   64[COMRAM] unsigned char 
;;  sign1           1   63[COMRAM] unsigned char 
;; Return value:  Size  Location     Type
;;                  4   55[COMRAM] long 
;; Registers used:
;;		wreg, status,2, status,0
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:         4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         2       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:        10       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       10 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_thermistor_centi_c
;; This function uses a non-reentrant model
;;
psect	text9,class=CODE,space=0,reloc=2,group=1
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\fltol.c"
	line	43
global __ptext9
__ptext9:
psect	text9
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\fltol.c"
	line	43
	
___fltol:
;incstack = 0
	callstack 125
	line	47
	
l2778:
	rlcf	((c:___fltol@f1+2))^0500h,c,w
	rlcf	((c:___fltol@f1+3))^0500h,c,w
	movwf	((c:___fltol@exp1))^0500h,c
	movf	((c:___fltol@exp1))^0500h,c,w
	btfss	status,2
	goto	u2541
	goto	u2540
u2541:
	goto	l2784
u2540:
	line	48
	
l2780:
	movlw	low(0)
	movwf	((c:?___fltol))^0500h,c
	movlw	high(0)
	movwf	((c:?___fltol+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:?___fltol+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:?___fltol+3))^0500h,c
	goto	l656
	line	49
	
l2784:
	movff	(c:___fltol@f1),??___fltol+0
	movff	(c:___fltol@f1+1),??___fltol+0+1
	movff	(c:___fltol@f1+2),??___fltol+0+2
	movff	(c:___fltol@f1+3),??___fltol+0+3
	movlw	01Fh+1
	goto	u2550
u2555:
	bcf	status,0
	rrcf	(??___fltol+0+3)^0500h,c
	rrcf	(??___fltol+0+2)^0500h,c
	rrcf	(??___fltol+0+1)^0500h,c
	rrcf	(??___fltol+0)^0500h,c
u2550:
	decfsz	wreg
	goto	u2555
	movf	(??___fltol+0)^0500h,c,w
	movwf	((c:___fltol@sign1))^0500h,c
	line	50
	
l2786:
	bsf	(0+(23/8)+(c:___fltol@f1))^0500h,c,(23)&7
	line	51
	
l2788:
	movlw	0FFh
	andwf	((c:___fltol@f1))^0500h,c
	movlw	0FFh
	andwf	((c:___fltol@f1+1))^0500h,c
	movlw	0FFh
	andwf	((c:___fltol@f1+2))^0500h,c
	movlw	0
	andwf	((c:___fltol@f1+3))^0500h,c
	line	52
	
l2790:
	movlw	(096h)&0ffh
	subwf	((c:___fltol@exp1))^0500h,c
	line	53
	
l2792:
	btfsc	((c:___fltol@exp1))^0500h,c,7
	goto	u2560
	goto	u2561

u2561:
	goto	l2804
u2560:
	line	54
	
l2794:
		movf	((c:___fltol@exp1))^0500h,c,w
	xorlw	80h
	addlw	-(80h^-23)
	btfsc	status,0
	goto	u2571
	goto	u2570

u2571:
	goto	l2800
u2570:
	goto	l2780
	line	57
	
l2800:
	bcf	status,0
	rrcf	((c:___fltol@f1+3))^0500h,c
	rrcf	((c:___fltol@f1+2))^0500h,c
	rrcf	((c:___fltol@f1+1))^0500h,c
	rrcf	((c:___fltol@f1))^0500h,c
	line	58
	
l2802:
	incfsz	((c:___fltol@exp1))^0500h,c
	
	goto	l2800
	goto	l2814
	line	60
	
l2804:
		movlw	020h-1
	cpfsgt	((c:___fltol@exp1))^0500h,c
	goto	u2581
	goto	u2580

u2581:
	goto	l2812
u2580:
	goto	l2780
	line	63
	
l2810:
	bcf	status,0
	rlcf	((c:___fltol@f1))^0500h,c
	rlcf	((c:___fltol@f1+1))^0500h,c
	rlcf	((c:___fltol@f1+2))^0500h,c
	rlcf	((c:___fltol@f1+3))^0500h,c
	line	64
	decf	((c:___fltol@exp1))^0500h,c
	line	62
	
l2812:
	movf	((c:___fltol@exp1))^0500h,c,w
	btfss	status,2
	goto	u2591
	goto	u2590
u2591:
	goto	l2810
u2590:
	line	67
	
l2814:
	movf	((c:___fltol@sign1))^0500h,c,w
	btfsc	status,2
	goto	u2601
	goto	u2600
u2601:
	goto	l2818
u2600:
	line	68
	
l2816:
	comf	((c:___fltol@f1+3))^0500h,c
	comf	((c:___fltol@f1+2))^0500h,c
	comf	((c:___fltol@f1+1))^0500h,c
	negf	((c:___fltol@f1))^0500h,c
	movlw	0
	addwfc	((c:___fltol@f1+1))^0500h,c
	addwfc	((c:___fltol@f1+2))^0500h,c
	addwfc	((c:___fltol@f1+3))^0500h,c
	line	69
	
l2818:
	movff	(c:___fltol@f1),(c:?___fltol)
	movff	(c:___fltol@f1+1),(c:?___fltol+1)
	movff	(c:___fltol@f1+2),(c:?___fltol+2)
	movff	(c:___fltol@f1+3),(c:?___fltol+3)
	line	70
	
l656:
	return	;funcret
	callstack 0
GLOBAL	__end_of___fltol
	__end_of___fltol:
	signat	___fltol,4220
	global	_report_measurement

;; *************** function _report_measurement *****************
;; Defined at:
;;		line 286 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;  adc             2   40[COMRAM] unsigned short 
;;  resistance      4   42[COMRAM] unsigned long 
;;  centi_c         4   46[COMRAM] long 
;;  can_sent        1   50[COMRAM] unsigned char 
;; Auto vars:     Size  Location     Type
;;  magnitude       4   69[COMRAM] unsigned long 
;; Return value:  Size  Location     Type
;;                  1    wreg      void 
;; Registers used:
;;		wreg, fsr2l, fsr2h, status,2, status,0, tblptrl, tblptrh, tblptru, cstack
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:        11       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:        18       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:        33       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       33 bytes
;; Hardware stack levels used: 1
;; Hardware stack levels required when called: 1
;; This function calls:
;;		___lldiv
;;		___llmod
;;		_uart_put_uint32
;;		_uart_puts
;; This function is called by:
;;		_main
;; This function uses a non-reentrant model
;;
psect	text10,class=CODE,space=0,reloc=2,group=0
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	286
global __ptext10
__ptext10:
psect	text10
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	286
	
_report_measurement:
;incstack = 0
	callstack 125
	line	291
	
l3066:
		movlw	low(STR_24)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_24)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	292
	
l3068:
	movff	(c:report_measurement@adc),(c:uart_put_uint32@value)
	movff	(c:report_measurement@adc+1),(c:uart_put_uint32@value+1)
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c
	call	_uart_put_uint32	;wreg free
	line	293
	
l3070:
		movlw	251
	subwf	 ((c:report_measurement@adc))^0500h,c,w
	movlw	15
	subwfb	((c:report_measurement@adc+1))^0500h,c,w
	btfss	status,0
	goto	u2731
	goto	u2730

u2731:
	goto	l3084
u2730:
	line	294
	
l3072:
		movlw	low(STR_25)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_25)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	295
	
l3074:
	movf	((c:report_measurement@can_sent))^0500h,c,w
	btfss	status,2
	goto	u2741
	goto	u2740
u2741:
	goto	l3078
u2740:
	
l3076:
		movlw	low(STR_27)
	movwf	((c:_report_measurement$755))^0500h,c
	movlw	high(STR_27)
	movwf	((c:_report_measurement$755+1))^0500h,c

	goto	l3080
	
l3078:
		movlw	low(STR_26)
	movwf	((c:_report_measurement$755))^0500h,c
	movlw	high(STR_26)
	movwf	((c:_report_measurement$755+1))^0500h,c

	
l3080:
		movff	(c:_report_measurement$755),(c:uart_puts@text)
	movff	(c:_report_measurement$755+1),(c:uart_puts@text+1)

	call	_uart_puts	;wreg free
	goto	l211
	line	298
	
l3084:
		movf	((c:report_measurement@adc+1))^0500h,c,w
	bnz	u2751
	movlw	5
	subwf	 ((c:report_measurement@adc))^0500h,c,w
	btfsc	status,0
	goto	u2751
	goto	u2750

u2751:
	goto	l3098
u2750:
	line	299
	
l3086:
		movlw	low(STR_28)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_28)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	300
	
l3088:
	movf	((c:report_measurement@can_sent))^0500h,c,w
	btfss	status,2
	goto	u2761
	goto	u2760
u2761:
	goto	l3092
u2760:
	
l3090:
		movlw	low(STR_30)
	movwf	((c:_report_measurement$760))^0500h,c
	movlw	high(STR_30)
	movwf	((c:_report_measurement$760+1))^0500h,c

	goto	l3094
	
l3092:
		movlw	low(STR_29)
	movwf	((c:_report_measurement$760))^0500h,c
	movlw	high(STR_29)
	movwf	((c:_report_measurement$760+1))^0500h,c

	
l3094:
		movff	(c:_report_measurement$760),(c:uart_puts@text)
	movff	(c:_report_measurement$760+1),(c:uart_puts@text+1)

	call	_uart_puts	;wreg free
	goto	l211
	line	304
	
l3098:
	btfsc	((c:report_measurement@centi_c+3))^0500h,c,7
	goto	u2771
	goto	u2770

u2771:
	goto	l3102
u2770:
	
l3100:
	movff	(c:report_measurement@centi_c),(c:report_measurement@magnitude)
	movff	(c:report_measurement@centi_c+1),(c:report_measurement@magnitude+1)
	movff	(c:report_measurement@centi_c+2),(c:report_measurement@magnitude+2)
	movff	(c:report_measurement@centi_c+3),(c:report_measurement@magnitude+3)
	goto	l3104
	
l3102:
	movff	(c:report_measurement@centi_c),??_report_measurement+0
	movff	(c:report_measurement@centi_c+1),??_report_measurement+0+1
	movff	(c:report_measurement@centi_c+2),??_report_measurement+0+2
	movff	(c:report_measurement@centi_c+3),??_report_measurement+0+3
	comf	(??_report_measurement+0)^0500h,c
	comf	(??_report_measurement+0+1)^0500h,c
	comf	(??_report_measurement+0+2)^0500h,c
	comf	(??_report_measurement+0+3)^0500h,c
	incf	(??_report_measurement+0)^0500h,c
	movlw	0
	addwfc	(??_report_measurement+0+1)^0500h,c
	addwfc	(??_report_measurement+0+2)^0500h,c
	addwfc	(??_report_measurement+0+3)^0500h,c
	movff	??_report_measurement+0,(c:report_measurement@magnitude)
	movff	??_report_measurement+0+1,(c:report_measurement@magnitude+1)
	movff	??_report_measurement+0+2,(c:report_measurement@magnitude+2)
	movff	??_report_measurement+0+3,(c:report_measurement@magnitude+3)
	line	306
	
l3104:
		movlw	low(STR_31)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_31)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	307
	
l3106:
	movff	(c:report_measurement@resistance),(c:uart_put_uint32@value)
	movff	(c:report_measurement@resistance+1),(c:uart_put_uint32@value+1)
	movff	(c:report_measurement@resistance+2),(c:uart_put_uint32@value+2)
	movff	(c:report_measurement@resistance+3),(c:uart_put_uint32@value+3)
	call	_uart_put_uint32	;wreg free
	line	308
	
l3108:
		movlw	low(STR_32)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_32)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	309
	
l3110:
	btfsc	((c:report_measurement@centi_c+3))^0500h,c,7
	goto	u2780
	goto	u2781

u2781:
	goto	l3114
u2780:
	
l3112:
		movlw	low(STR_33)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_33)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	310
	
l3114:
	movff	(c:report_measurement@magnitude),(c:___lldiv@dividend)
	movff	(c:report_measurement@magnitude+1),(c:___lldiv@dividend+1)
	movff	(c:report_measurement@magnitude+2),(c:___lldiv@dividend+2)
	movff	(c:report_measurement@magnitude+3),(c:___lldiv@dividend+3)
	movlw	low(064h)
	movwf	((c:___lldiv@divisor))^0500h,c
	movlw	high(064h)
	movwf	((c:___lldiv@divisor+1))^0500h,c
	movlw	low highword(064h)
	movwf	((c:___lldiv@divisor+2))^0500h,c
	movlw	high highword(064h)
	movwf	((c:___lldiv@divisor+3))^0500h,c
	call	___lldiv	;wreg free
	movff	0+?___lldiv,(c:_report_measurement$1623)
	movff	1+?___lldiv,(c:_report_measurement$1623+1)
	movff	2+?___lldiv,(c:_report_measurement$1623+2)
	movff	3+?___lldiv,(c:_report_measurement$1623+3)
	
	
l3116:
	movff	(c:_report_measurement$1623),(c:uart_put_uint32@value)
	movff	(c:_report_measurement$1623+1),(c:uart_put_uint32@value+1)
	movff	(c:_report_measurement$1623+2),(c:uart_put_uint32@value+2)
	movff	(c:_report_measurement$1623+3),(c:uart_put_uint32@value+3)
	call	_uart_put_uint32	;wreg free
	line	311
	
l3118:
		movlw	low(STR_34)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_34)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	312
	
l3120:
	movff	(c:report_measurement@magnitude),(c:___llmod@dividend)
	movff	(c:report_measurement@magnitude+1),(c:___llmod@dividend+1)
	movff	(c:report_measurement@magnitude+2),(c:___llmod@dividend+2)
	movff	(c:report_measurement@magnitude+3),(c:___llmod@dividend+3)
	movlw	low(064h)
	movwf	((c:___llmod@divisor))^0500h,c
	movlw	high(064h)
	movwf	((c:___llmod@divisor+1))^0500h,c
	movlw	low highword(064h)
	movwf	((c:___llmod@divisor+2))^0500h,c
	movlw	high highword(064h)
	movwf	((c:___llmod@divisor+3))^0500h,c
	call	___llmod	;wreg free
		movf	(3+?___llmod)^0500h,c,w
	iorwf	(2+?___llmod)^0500h,c,w
	iorwf	(1+?___llmod)^0500h,c,w
	bnz	u2791
	movlw	10
	subwf	 (0+?___llmod)^0500h,c,w
	btfsc	status,0
	goto	u2791
	goto	u2790

u2791:
	goto	l3124
u2790:
	
l3122:
		movlw	low(STR_35)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_35)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	313
	
l3124:
	movff	(c:report_measurement@magnitude),(c:___llmod@dividend)
	movff	(c:report_measurement@magnitude+1),(c:___llmod@dividend+1)
	movff	(c:report_measurement@magnitude+2),(c:___llmod@dividend+2)
	movff	(c:report_measurement@magnitude+3),(c:___llmod@dividend+3)
	movlw	low(064h)
	movwf	((c:___llmod@divisor))^0500h,c
	movlw	high(064h)
	movwf	((c:___llmod@divisor+1))^0500h,c
	movlw	low highword(064h)
	movwf	((c:___llmod@divisor+2))^0500h,c
	movlw	high highword(064h)
	movwf	((c:___llmod@divisor+3))^0500h,c
	call	___llmod	;wreg free
	movff	0+?___llmod,(c:_report_measurement$1624)
	movff	1+?___llmod,(c:_report_measurement$1624+1)
	movff	2+?___llmod,(c:_report_measurement$1624+2)
	movff	3+?___llmod,(c:_report_measurement$1624+3)
	
	
l3126:
	movff	(c:_report_measurement$1624),(c:uart_put_uint32@value)
	movff	(c:_report_measurement$1624+1),(c:uart_put_uint32@value+1)
	movff	(c:_report_measurement$1624+2),(c:uart_put_uint32@value+2)
	movff	(c:_report_measurement$1624+3),(c:uart_put_uint32@value+3)
	call	_uart_put_uint32	;wreg free
	line	314
	
l3128:
		movlw	low(STR_36)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_36)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	316
	
l3130:
	movf	((c:report_measurement@can_sent))^0500h,c,w
	btfss	status,2
	goto	u2801
	goto	u2800
u2801:
	goto	l3134
u2800:
	
l3132:
		movlw	low(STR_38)
	movwf	((c:_report_measurement$770))^0500h,c
	movlw	high(STR_38)
	movwf	((c:_report_measurement$770+1))^0500h,c

	goto	l3136
	
l3134:
		movlw	low(STR_37)
	movwf	((c:_report_measurement$770))^0500h,c
	movlw	high(STR_37)
	movwf	((c:_report_measurement$770+1))^0500h,c

	
l3136:
		movff	(c:_report_measurement$770),(c:uart_puts@text)
	movff	(c:_report_measurement$770+1),(c:uart_puts@text+1)

	call	_uart_puts	;wreg free
	line	317
	
l3138:
		movlw	low(STR_39)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_39)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	318
	
l211:
	return	;funcret
	callstack 0
GLOBAL	__end_of_report_measurement
	__end_of_report_measurement:
	signat	_report_measurement,16505
	global	_report_can_diagnostics

;; *************** function _report_can_diagnostics *****************
;; Defined at:
;;		line 215 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
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
psect	text11,class=CODE,space=0,reloc=2,group=0
	line	215
global __ptext11
__ptext11:
psect	text11
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	215
	
_report_can_diagnostics:
;incstack = 0
	callstack 124
	line	217
	
l2954:
		movlw	low(STR_1)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_1)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l2956:
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
	line	218
	
l2958:
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
	line	219
	
l2960:
		movlw	low(STR_3)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_3)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l2962:
	movlb	1	; () banked
	movf	((308))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	220
		movlw	low(STR_4)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_4)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l2964:
	movlb	1	; () banked
	movf	((310))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	221
	
l2966:
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
	line	222
	
l2968:
		movlw	low(STR_6)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_6)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l2970:
	movlb	1	; () banked
	movf	((337))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	223
		movlw	low(STR_7)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_7)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l2972:
	movff	(344),(c:uart_put_uint32@value)	;volatile
	movff	(344+1),(c:uart_put_uint32@value+1)	;volatile
	movff	(344+2),(c:uart_put_uint32@value+2)	;volatile
	movff	(344+3),(c:uart_put_uint32@value+3)	;volatile
	call	_uart_put_uint32	;wreg free
	line	224
	
l2974:
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
	line	225
	
l2976:
		movlw	low(STR_9)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_9)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l2978:
	movlb	1	; () banked
	movf	((257))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	226
		movlw	low(STR_10)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_10)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l2980:
	movlb	1	; () banked
	movf	((258))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	227
	
l2982:
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
	line	228
	
l2984:
		movlw	low(STR_12)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_12)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l2986:
	btfsc	((c:1231))^0400h,c,3	;volatile
	goto	u2681
	goto	u2680
u2681:
	clrf	(??_report_can_diagnostics+0)^0500h,c
	incf	(??_report_can_diagnostics+0)^0500h,c
	goto	u2688
u2680:
	clrf	(??_report_can_diagnostics+0)^0500h,c
u2688:
	movf	(??_report_can_diagnostics+0)^0500h,c,w
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	229
		movlw	low(STR_13)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_13)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l2988:
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
	line	230
	
l2990:
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
	line	231
	
l2992:
		movlw	low(STR_15)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_15)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l2994:
	movlb	1	; () banked
	movf	((338))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	232
		movlw	low(STR_16)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_16)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l2996:
	movlb	1	; () banked
	movf	((336))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	233
	
l2998:
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
	line	234
	
l3000:
		movlw	low(STR_18)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_18)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l3002:
	movlb	1	; () banked
	movf	((319))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	235
		movlw	low(STR_19)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_19)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l3004:
	movlb	2	; () banked
	movf	((523))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	236
	
l3006:
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
	line	237
	
l3008:
		movlw	low(STR_21)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_21)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l3010:
	movf	((c:1223))^0400h,c,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	238
		movlw	low(STR_22)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_22)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	
l3012:
	movlb	4	; () banked
	movf	((1032))&0ffh,w	;volatile
	movwf	((c:uart_put_uint32@value))^0500h,c
	clrf	((c:uart_put_uint32@value+1))^0500h,c
	clrf	((c:uart_put_uint32@value+2))^0500h,c
	clrf	((c:uart_put_uint32@value+3))^0500h,c

	call	_uart_put_uint32	;wreg free
	line	239
	
l3014:
		movlw	low(STR_23)
	movwf	((c:uart_puts@text))^0500h,c
	movlw	high(STR_23)
	movwf	((c:uart_puts@text+1))^0500h,c

	call	_uart_puts	;wreg free
	line	240
	
l185:
	return	;funcret
	callstack 0
GLOBAL	__end_of_report_can_diagnostics
	__end_of_report_can_diagnostics:
	signat	_report_can_diagnostics,89
	global	_uart_puts

;; *************** function _uart_puts *****************
;; Defined at:
;;		line 192 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;  text            2    0[COMRAM] PTR const unsigned char 
;;		 -> STR_40(101), STR_39(3), STR_38(5), STR_37(7), 
;;		 -> STR_36(12), STR_35(2), STR_34(2), STR_33(2), 
;;		 -> STR_32(9), STR_31(8), STR_30(7), STR_29(9), 
;;		 -> STR_28(40), STR_27(7), STR_26(9), STR_25(38), 
;;		 -> STR_24(11), STR_23(3), STR_22(8), STR_21(7), 
;;		 -> STR_20(8), STR_19(8), STR_18(9), STR_17(9), 
;;		 -> STR_16(10), STR_15(7), STR_14(8), STR_13(7), 
;;		 -> STR_12(6), STR_11(7), STR_10(7), STR_9(7), 
;;		 -> STR_8(7), STR_7(5), STR_6(6), STR_5(6), 
;;		 -> STR_4(8), STR_3(8), STR_2(8), STR_1(8), 
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
;;		_report_measurement
;;		_main
;; This function uses a non-reentrant model
;;
psect	text12,class=CODE,space=0,reloc=2,group=0
	line	192
global __ptext12
__ptext12:
psect	text12
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	192
	
_uart_puts:
;incstack = 0
	callstack 125
	line	194
	
l2680:
	goto	l2686
	line	195
	
l167:
	movlb	2	; () banked
	btfsc	((688))&0ffh,4	;volatile
	goto	u2421
	goto	u2420
u2421:
	goto	l167
u2420:
	line	196
	
l2682:; BSR set to: 2

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
	
l2684:; BSR set to: 2

	infsnz	((c:uart_puts@text))^0500h,c
	incf	((c:uart_puts@text+1))^0500h,c
	line	194
	
l2686:
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
	goto	u2431
	goto	u2430
u2431:
	goto	l167
u2430:
	line	198
	
l171:
	return	;funcret
	callstack 0
GLOBAL	__end_of_uart_puts
	__end_of_uart_puts:
	signat	_uart_puts,4217
	global	_uart_put_uint32

;; *************** function _uart_put_uint32 *****************
;; Defined at:
;;		line 200 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;  value           4   25[COMRAM] unsigned long 
;; Auto vars:     Size  Location     Type
;;  digits         10   29[COMRAM] unsigned char [10]
;;  count           1   39[COMRAM] unsigned char 
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
;;		_report_measurement
;; This function uses a non-reentrant model
;;
psect	text13,class=CODE,space=0,reloc=2,group=0
	line	200
global __ptext13
__ptext13:
psect	text13
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	200
	
_uart_put_uint32:
;incstack = 0
	callstack 125
	line	203
	
l2688:
	clrf	((c:uart_put_uint32@count))^0500h,c
	line	206
	
l2690:
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

	
l2692:
	incf	((c:uart_put_uint32@count))^0500h,c
	line	207
	
l2694:
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
	
	line	208
	
l2696:
	movf	((c:uart_put_uint32@value))^0500h,c,w
iorwf	((c:uart_put_uint32@value+1))^0500h,c,w
iorwf	((c:uart_put_uint32@value+2))^0500h,c,w
iorwf	((c:uart_put_uint32@value+3))^0500h,c,w
	btfss	status,2
	goto	u2441
	goto	u2440

u2441:
	goto	l2690
u2440:
	goto	l2700
	line	210
	
l178:
	movlb	2	; () banked
	btfsc	((688))&0ffh,4	;volatile
	goto	u2451
	goto	u2450
u2451:
	goto	l178
u2450:
	line	211
	
l2698:; BSR set to: 2

	decf	((c:uart_put_uint32@count))^0500h,c
	movlw	low(uart_put_uint32@digits)
	addwf	((c:uart_put_uint32@count))^0500h,c,w
	movwf	c:fsr2l
	clrf	1+c:fsr2l
	movlw	high(uart_put_uint32@digits)
	addwfc	1+c:fsr2l
	movf	indf2,w
	movwf	((675))&0ffh	;volatile
	line	209
	
l2700:
	movf	((c:uart_put_uint32@count))^0500h,c,w
	btfss	status,2
	goto	u2461
	goto	u2460
u2461:
	goto	l178
u2460:
	line	213
	
l182:
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
;;		_report_measurement
;; This function uses a non-reentrant model
;;
psect	text14,class=CODE,space=0,reloc=2,group=1
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\llmod.c"
	line	7
global __ptext14
__ptext14:
psect	text14
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\llmod.c"
	line	7
	
___llmod:
;incstack = 0
	callstack 124
	line	12
	
l2618:
	movf	((c:___llmod@divisor))^0500h,c,w
iorwf	((c:___llmod@divisor+1))^0500h,c,w
iorwf	((c:___llmod@divisor+2))^0500h,c,w
iorwf	((c:___llmod@divisor+3))^0500h,c,w
	btfsc	status,2
	goto	u2291
	goto	u2290

u2291:
	goto	l779
u2290:
	line	13
	
l2620:
	movlw	low(01h)
	movwf	((c:___llmod@counter))^0500h,c
	line	14
	goto	l2624
	line	15
	
l2622:
	bcf	status,0
	rlcf	((c:___llmod@divisor))^0500h,c
	rlcf	((c:___llmod@divisor+1))^0500h,c
	rlcf	((c:___llmod@divisor+2))^0500h,c
	rlcf	((c:___llmod@divisor+3))^0500h,c
	line	16
	incf	((c:___llmod@counter))^0500h,c
	line	14
	
l2624:
	
	btfss	((c:___llmod@divisor+3))^0500h,c,(31)&7
	goto	u2301
	goto	u2300
u2301:
	goto	l2622
u2300:
	line	19
	
l2626:
		movf	((c:___llmod@divisor))^0500h,c,w
	subwf	((c:___llmod@dividend))^0500h,c,w
	movf	((c:___llmod@divisor+1))^0500h,c,w
	subwfb	((c:___llmod@dividend+1))^0500h,c,w
	movf	((c:___llmod@divisor+2))^0500h,c,w
	subwfb	((c:___llmod@dividend+2))^0500h,c,w
	movf	((c:___llmod@divisor+3))^0500h,c,w
	subwfb	((c:___llmod@dividend+3))^0500h,c,w
	btfss	status,0
	goto	u2311
	goto	u2310

u2311:
	goto	l2630
u2310:
	line	20
	
l2628:
	movf	((c:___llmod@divisor))^0500h,c,w
	subwf	((c:___llmod@dividend))^0500h,c
	movf	((c:___llmod@divisor+1))^0500h,c,w
	subwfb	((c:___llmod@dividend+1))^0500h,c
	movf	((c:___llmod@divisor+2))^0500h,c,w
	subwfb	((c:___llmod@dividend+2))^0500h,c
	movf	((c:___llmod@divisor+3))^0500h,c,w
	subwfb	((c:___llmod@dividend+3))^0500h,c
	line	21
	
l2630:
	bcf	status,0
	rrcf	((c:___llmod@divisor+3))^0500h,c
	rrcf	((c:___llmod@divisor+2))^0500h,c
	rrcf	((c:___llmod@divisor+1))^0500h,c
	rrcf	((c:___llmod@divisor))^0500h,c
	line	22
	
l2632:
	decfsz	((c:___llmod@counter))^0500h,c
	
	goto	l2626
	line	23
	
l779:
	line	24
	movff	(c:___llmod@dividend),(c:?___llmod)
	movff	(c:___llmod@dividend+1),(c:?___llmod+1)
	movff	(c:___llmod@dividend+2),(c:?___llmod+2)
	movff	(c:___llmod@dividend+3),(c:?___llmod+3)
	line	25
	
l786:
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
;;		_report_measurement
;;		_main
;; This function uses a non-reentrant model
;;
psect	text15,class=CODE,space=0,reloc=2,group=1
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\__lldiv.c"
	line	7
global __ptext15
__ptext15:
psect	text15
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\__lldiv.c"
	line	7
	
___lldiv:
;incstack = 0
	callstack 124
	line	13
	
l2326:
	movlw	low(0)
	movwf	((c:___lldiv@quotient))^0500h,c
	movlw	high(0)
	movwf	((c:___lldiv@quotient+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:___lldiv@quotient+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:___lldiv@quotient+3))^0500h,c
	line	14
	
l2328:
	movf	((c:___lldiv@divisor))^0500h,c,w
iorwf	((c:___lldiv@divisor+1))^0500h,c,w
iorwf	((c:___lldiv@divisor+2))^0500h,c,w
iorwf	((c:___lldiv@divisor+3))^0500h,c,w
	btfsc	status,2
	goto	u1841
	goto	u1840

u1841:
	goto	l276
u1840:
	line	15
	
l2330:
	movlw	low(01h)
	movwf	((c:___lldiv@counter))^0500h,c
	line	16
	goto	l2334
	line	17
	
l2332:
	bcf	status,0
	rlcf	((c:___lldiv@divisor))^0500h,c
	rlcf	((c:___lldiv@divisor+1))^0500h,c
	rlcf	((c:___lldiv@divisor+2))^0500h,c
	rlcf	((c:___lldiv@divisor+3))^0500h,c
	line	18
	incf	((c:___lldiv@counter))^0500h,c
	line	16
	
l2334:
	
	btfss	((c:___lldiv@divisor+3))^0500h,c,(31)&7
	goto	u1851
	goto	u1850
u1851:
	goto	l2332
u1850:
	line	21
	
l2336:
	bcf	status,0
	rlcf	((c:___lldiv@quotient))^0500h,c
	rlcf	((c:___lldiv@quotient+1))^0500h,c
	rlcf	((c:___lldiv@quotient+2))^0500h,c
	rlcf	((c:___lldiv@quotient+3))^0500h,c
	line	22
	
l2338:
		movf	((c:___lldiv@divisor))^0500h,c,w
	subwf	((c:___lldiv@dividend))^0500h,c,w
	movf	((c:___lldiv@divisor+1))^0500h,c,w
	subwfb	((c:___lldiv@dividend+1))^0500h,c,w
	movf	((c:___lldiv@divisor+2))^0500h,c,w
	subwfb	((c:___lldiv@dividend+2))^0500h,c,w
	movf	((c:___lldiv@divisor+3))^0500h,c,w
	subwfb	((c:___lldiv@dividend+3))^0500h,c,w
	btfss	status,0
	goto	u1861
	goto	u1860

u1861:
	goto	l2344
u1860:
	line	23
	
l2340:
	movf	((c:___lldiv@divisor))^0500h,c,w
	subwf	((c:___lldiv@dividend))^0500h,c
	movf	((c:___lldiv@divisor+1))^0500h,c,w
	subwfb	((c:___lldiv@dividend+1))^0500h,c
	movf	((c:___lldiv@divisor+2))^0500h,c,w
	subwfb	((c:___lldiv@dividend+2))^0500h,c
	movf	((c:___lldiv@divisor+3))^0500h,c,w
	subwfb	((c:___lldiv@dividend+3))^0500h,c
	line	24
	
l2342:
	bsf	(0+(0/8)+(c:___lldiv@quotient))^0500h,c,(0)&7
	line	26
	
l2344:
	bcf	status,0
	rrcf	((c:___lldiv@divisor+3))^0500h,c
	rrcf	((c:___lldiv@divisor+2))^0500h,c
	rrcf	((c:___lldiv@divisor+1))^0500h,c
	rrcf	((c:___lldiv@divisor))^0500h,c
	line	27
	
l2346:
	decfsz	((c:___lldiv@counter))^0500h,c
	
	goto	l2336
	line	28
	
l276:
	line	29
	movff	(c:___lldiv@quotient),(c:?___lldiv)
	movff	(c:___lldiv@quotient+1),(c:?___lldiv+1)
	movff	(c:___lldiv@quotient+2),(c:?___lldiv+2)
	movff	(c:___lldiv@quotient+3),(c:?___lldiv+3)
	line	30
	
l283:
	return	;funcret
	callstack 0
GLOBAL	__end_of___lldiv
	__end_of___lldiv:
	signat	___lldiv,8316
	global	_can_send_oil_temperature

;; *************** function _can_send_oil_temperature *****************
;; Defined at:
;;		line 158 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;  centi_c         4    0[COMRAM] long 
;;  adc             2    4[COMRAM] unsigned short 
;;  resistance      4    6[COMRAM] unsigned long 
;; Auto vars:     Size  Location     Type
;;  object          2   12[COMRAM] PTR volatile unsigned ch
;;		 -> RAM(11775), 
;;  oil_temp        2   10[COMRAM] short 
;; Return value:  Size  Location     Type
;;                  1    wreg      unsigned char 
;; Registers used:
;;		wreg, fsr2l, fsr2h, status,2, status,0
;; Tracked objects:
;;		On entry : 0/0
;;		On exit  : 0/0
;;		Unchanged: 0/0
;; Data sizes:     COMRAM   BANK5   BANK6   BANK7   BANK8   BANK9  BANK10  BANK11  BANK12  BANK13  BANK14  BANK15  BANK16  BANK17  BANK18  BANK19  BANK20  BANK21  BANK22  BANK23  BANK24  BANK25  BANK26  BANK27  BANK28  BANK29  BANK30  BANK31  BANK32  BANK33  BANK34  BANK35  BANK36
;;      Params:        10       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Locals:         4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:        14       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       14 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_main
;; This function uses a non-reentrant model
;;
psect	text16,class=CODE,space=0,reloc=2,group=0
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	158
global __ptext16
__ptext16:
psect	text16
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	158
	
_can_send_oil_temperature:
;incstack = 0
	callstack 126
	line	165
	
l2892:
	movlb	1	; () banked
	btfsc	((340))&0ffh,0	;volatile
	goto	u2641
	goto	u2640
u2641:
	goto	l2898
u2640:
	
l2894:; BSR set to: 1

	movlw	(0)&0ffh
	goto	l159
	line	166
	
l2898:; BSR set to: 1

	btfsc	((c:can_send_oil_temperature@centi_c+3))^0500h,c,7
	goto	u2651
	movf	((c:can_send_oil_temperature@centi_c+3))^0500h,c,w
	iorwf	((c:can_send_oil_temperature@centi_c+2))^0500h,c,w
	bnz	u2650
	movlw	128
	subwf	 ((c:can_send_oil_temperature@centi_c+1))^0500h,c,w
	btfss	status,0
	goto	u2651
	goto	u2650

u2651:
	goto	l2902
u2650:
	
l2900:; BSR set to: 1

	movlw	low(07FFFh)
	movwf	((c:can_send_oil_temperature@centi_c))^0500h,c
	movlw	high(07FFFh)
	movwf	((c:can_send_oil_temperature@centi_c+1))^0500h,c
	movlw	low highword(07FFFh)
	movwf	((c:can_send_oil_temperature@centi_c+2))^0500h,c
	movlw	high highword(07FFFh)
	movwf	((c:can_send_oil_temperature@centi_c+3))^0500h,c
	line	167
	
l2902:; BSR set to: 1

	btfss	((c:can_send_oil_temperature@centi_c+3))^0500h,c,7
	goto	u2661
	movlw	128
	subwf	 ((c:can_send_oil_temperature@centi_c+1))^0500h,c,w
	movlw	255
	subwfb	((c:can_send_oil_temperature@centi_c+2))^0500h,c,w
	movlw	255
	subwfb	((c:can_send_oil_temperature@centi_c+3))^0500h,c,w
	btfsc	status,0
	goto	u2661
	goto	u2660

u2661:
	goto	l2906
u2660:
	
l2904:; BSR set to: 1

	movlw	low(-32768)
	movwf	((c:can_send_oil_temperature@centi_c))^0500h,c
	movlw	high(-32768)
	movwf	((c:can_send_oil_temperature@centi_c+1))^0500h,c
	movlw	low highword(-32768)
	movwf	((c:can_send_oil_temperature@centi_c+2))^0500h,c
	movlw	high highword(-32768)
	movwf	((c:can_send_oil_temperature@centi_c+3))^0500h,c
	line	168
	
l2906:; BSR set to: 1

	movff	(c:can_send_oil_temperature@centi_c),(c:can_send_oil_temperature@oil_temp)
	movff	(c:can_send_oil_temperature@centi_c+1),(c:can_send_oil_temperature@oil_temp+1)
	line	169
	
l2908:; BSR set to: 1

		movff	(344),(c:can_send_oil_temperature@object)	;volatile
	movff	(344+1),(c:can_send_oil_temperature@object+1)	;volatile

	line	170
	
l2910:; BSR set to: 1

	movf	((c:can_send_oil_temperature@object))^0500h,c,w
iorwf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	btfss	status,2
	goto	u2671
	goto	u2670

u2671:
	goto	l2916
u2670:
	goto	l2894
	line	172
	
l2916:; BSR set to: 1

	movff	(c:can_send_oil_temperature@object),fsr2l
	movff	(c:can_send_oil_temperature@object+1),fsr2h
	clrf	indf2
	line	173
	
l2918:; BSR set to: 1

	lfsr	2,01h
	movf	((c:can_send_oil_temperature@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	addwfc	fsr2h
	movlw	low(06h)
	movwf	indf2
	line	174
	
l2920:; BSR set to: 1

	lfsr	2,02h
	movf	((c:can_send_oil_temperature@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	addwfc	fsr2h
	clrf	indf2
	line	175
	
l2922:; BSR set to: 1

	lfsr	2,03h
	movf	((c:can_send_oil_temperature@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	addwfc	fsr2h
	clrf	indf2
	line	176
	
l2924:; BSR set to: 1

	lfsr	2,04h
	movf	((c:can_send_oil_temperature@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	addwfc	fsr2h
	movlw	low(08h)
	movwf	indf2
	line	177
	
l2926:; BSR set to: 1

	lfsr	2,05h
	movf	((c:can_send_oil_temperature@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	addwfc	fsr2h
	clrf	indf2
	line	178
	
l2928:; BSR set to: 1

	lfsr	2,06h
	movf	((c:can_send_oil_temperature@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	addwfc	fsr2h
	clrf	indf2
	line	179
	
l2930:; BSR set to: 1

	lfsr	2,07h
	movf	((c:can_send_oil_temperature@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	addwfc	fsr2h
	clrf	indf2
	line	180
	
l2932:; BSR set to: 1

	lfsr	2,08h
	movf	((c:can_send_oil_temperature@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	addwfc	fsr2h
	movff	(c:can_send_oil_temperature@oil_temp),indf2

	line	181
	
l2934:; BSR set to: 1

	lfsr	2,09h
	movf	((c:can_send_oil_temperature@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	addwfc	fsr2h
	movf	((c:can_send_oil_temperature@oil_temp+1))^0500h,c,w
	movwf	indf2,c

	line	182
	
l2936:; BSR set to: 1

	lfsr	2,0Ah
	movf	((c:can_send_oil_temperature@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	addwfc	fsr2h
	movff	(c:can_send_oil_temperature@adc),indf2

	line	183
	
l2938:; BSR set to: 1

	lfsr	2,0Bh
	movf	((c:can_send_oil_temperature@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	addwfc	fsr2h
	movf	((c:can_send_oil_temperature@adc+1))^0500h,c,w
	movwf	indf2,c

	line	184
	
l2940:; BSR set to: 1

	lfsr	2,0Ch
	movf	((c:can_send_oil_temperature@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	addwfc	fsr2h
	movff	(c:can_send_oil_temperature@resistance),indf2

	line	185
	
l2942:; BSR set to: 1

	lfsr	2,0Dh
	movf	((c:can_send_oil_temperature@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	addwfc	fsr2h
	movff	0+1+(c:can_send_oil_temperature@resistance),indf2

	line	186
	
l2944:; BSR set to: 1

	lfsr	2,0Eh
	movf	((c:can_send_oil_temperature@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	addwfc	fsr2h
	movff	0+2+(c:can_send_oil_temperature@resistance),indf2

	line	187
	
l2946:; BSR set to: 1

	lfsr	2,0Fh
	movf	((c:can_send_oil_temperature@object))^0500h,c,w
	addwf	fsr2l
	movf	((c:can_send_oil_temperature@object+1))^0500h,c,w
	addwfc	fsr2h
	movff	0+3+(c:can_send_oil_temperature@resistance),indf2

	line	188
	
l2948:; BSR set to: 1

	movlw	low(03h)
	movwf	((337))&0ffh	;volatile
	line	189
	
l2950:; BSR set to: 1

	movlw	(01h)&0ffh
	line	190
	
l159:; BSR set to: 1

	return	;funcret
	callstack 0
GLOBAL	__end_of_can_send_oil_temperature
	__end_of_can_send_oil_temperature:
	signat	_can_send_oil_temperature,12409
	global	_can_init

;; *************** function _can_init *****************
;; Defined at:
;;		line 122 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
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
psect	text17,class=CODE,space=0,reloc=2,group=0
	line	122
global __ptext17
__ptext17:
psect	text17
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	122
	
_can_init:; BSR set to: 1

;incstack = 0
	callstack 126
	line	124
	
l2866:
	movlb	0	; () banked
	bcf	((98))&0ffh,7	;volatile
	line	125
	
l2868:; BSR set to: 0

	movlw	(0F3h)&0ffh
	movlb	4	; () banked
	andwf	((1032))&0ffh	;volatile
	line	126
	
l2870:; BSR set to: 4

	bsf	(0+(2/8)+(c:1215))^0400h,c,(2)&7	;volatile
	line	127
	
l2872:; BSR set to: 4

	bcf	(0+(2/8)+(c:1223))^0400h,c,(2)&7	;volatile
	line	128
	
l2874:; BSR set to: 4

	bsf	((c:1223))^0400h,c,3	;volatile
	line	130
	
l2876:; BSR set to: 4

	movlb	1	; () banked
	bsf	((257))&0ffh,7	;volatile
	line	131
	
l2878:; BSR set to: 1

	movlw	low(04h)
	movwf	((259))&0ffh	;volatile
	line	132
	
l2880:; BSR set to: 1

	movlw	low(090h)
	movwf	((258))&0ffh	;volatile
	line	133
	
l2882:; BSR set to: 1

	movf	((259))&0ffh,w	;volatile
	andlw	not (((1<<3)-1)<<0)
	iorlw	(04h & ((1<<3)-1))<<0
	movwf	((259))&0ffh	;volatile
	line	134
	
l2884:; BSR set to: 1

	swapf	((258))&0ffh,w	;volatile
	rrcf	wreg,f
	andlw	(1<<3)-1
	xorlw	04h
	btfss	status,2
	goto	u2611
	goto	u2610
u2611:
	goto	l2884
u2610:
	
l148:; BSR set to: 1

	line	136
	clrf	((332))&0ffh	;volatile
	line	137
	
l2886:; BSR set to: 1

	movlw	low(026h)
	movwf	((333))&0ffh	;volatile
	line	138
	movlw	low(087h)
	movwf	((257))&0ffh	;volatile
	line	139
	movlw	low(060h)
	movwf	((256))&0ffh	;volatile
	line	140
	movlw	low(010h)
	movwf	((258))&0ffh	;volatile
	line	143
	movlw	low(01Ah)
	movwf	((260))&0ffh	;volatile
	line	144
	movlw	low(01Ah)
	movwf	((261))&0ffh	;volatile
	line	145
	movlw	low(063h)
	movwf	((262))&0ffh	;volatile
	line	146
	
l2888:; BSR set to: 1

	clrf	((263))&0ffh	;volatile
	line	148
	movlw	low(080h)
	movwf	((336))&0ffh	;volatile
	line	149
	movlw	low(04h)
	movwf	((337))&0ffh	;volatile
	line	150
	movlw	low(060h)
	movwf	((338))&0ffh	;volatile
	line	151
	movlw	low(01h)
	movwf	((339))&0ffh	;volatile
	line	153
	movf	((259))&0ffh,w	;volatile
	andlw	not (((1<<3)-1)<<0)
	iorlw	(06h & ((1<<3)-1))<<0
	movwf	((259))&0ffh	;volatile
	line	154
	
l2890:; BSR set to: 1

	swapf	((258))&0ffh,w	;volatile
	rrcf	wreg,f
	andlw	(1<<3)-1
	xorlw	06h
	btfss	status,2
	goto	u2621
	goto	u2620
u2621:
	goto	l2890
u2620:
	line	155
	
l152:; BSR set to: 1

	btfsc	((337))&0ffh,2	;volatile
	goto	u2631
	goto	u2630
u2631:
	goto	l152
u2630:
	line	156
	
l155:; BSR set to: 1

	return	;funcret
	callstack 0
GLOBAL	__end_of_can_init
	__end_of_can_init:
	signat	_can_init,89
	global	_adc_read_average

;; *************** function _adc_read_average *****************
;; Defined at:
;;		line 259 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;		None
;; Auto vars:     Size  Location     Type
;;  sum             4    6[COMRAM] unsigned long 
;;  index           1   10[COMRAM] unsigned char 
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
;;      Locals:         5       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Temps:          4       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;      Totals:        11       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0       0
;;Total ram usage:       11 bytes
;; Hardware stack levels used: 1
;; This function calls:
;;		Nothing
;; This function is called by:
;;		_main
;; This function uses a non-reentrant model
;;
psect	text18,class=CODE,space=0,reloc=2,group=0
	line	259
global __ptext18
__ptext18:
psect	text18
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	259
	
_adc_read_average:; BSR set to: 1

;incstack = 0
	callstack 126
	line	261
	
l3028:
	movlw	low(0)
	movwf	((c:adc_read_average@sum))^0500h,c
	movlw	high(0)
	movwf	((c:adc_read_average@sum+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:adc_read_average@sum+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:adc_read_average@sum+3))^0500h,c
	line	264
	
l3030:
	clrf	((c:adc_read_average@index))^0500h,c
	
l191:
	line	265
	movlb	3	; () banked
	bsf	((1011))&0ffh,0	;volatile
	line	266
	
l193:; BSR set to: 3

	btfsc	((1011))&0ffh,0	;volatile
	goto	u2691
	goto	u2690
u2691:
	goto	l193
u2690:
	line	267
	
l3036:; BSR set to: 3

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

	line	264
	
l3038:; BSR set to: 3

	incf	((c:adc_read_average@index))^0500h,c
	
l3040:; BSR set to: 3

		movlw	020h-1
	cpfsgt	((c:adc_read_average@index))^0500h,c
	goto	u2701
	goto	u2700

u2701:
	goto	l191
u2700:
	line	269
	
l3042:; BSR set to: 3

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
	goto	u2710
u2715:
	bcf	status,0
	rrcf	(??_adc_read_average+0+3)^0500h,c
	rrcf	(??_adc_read_average+0+2)^0500h,c
	rrcf	(??_adc_read_average+0+1)^0500h,c
	rrcf	(??_adc_read_average+0)^0500h,c
u2710:
	decfsz	wreg
	goto	u2715
	movff	??_adc_read_average+0,(c:?_adc_read_average)
	movff	??_adc_read_average+0+1,(c:?_adc_read_average+1)
	line	270
	
l196:; BSR set to: 3

	return	;funcret
	callstack 0
GLOBAL	__end_of_adc_read_average
	__end_of_adc_read_average:
	signat	_adc_read_average,90
	global	_adc_init

;; *************** function _adc_init *****************
;; Defined at:
;;		line 242 in file "C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
;; Parameters:    Size  Location     Type
;;		None
;; Auto vars:     Size  Location     Type
;;		None
;; Return value:  Size  Location     Type
;;                  1    wreg      void 
;; Registers used:
;;		wreg, status,2
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
psect	text19,class=CODE,space=0,reloc=2,group=0
	line	242
global __ptext19
__ptext19:
psect	text19
	file	"C:\Users\lintaroh\Documents\RaceCapture\pic18f26q84_blink.X\main.c"
	line	242
	
_adc_init:; BSR set to: 3

;incstack = 0
	callstack 126
	line	244
	
l3016:
	movlb	0	; () banked
	bcf	((99))&0ffh,5	;volatile
	line	245
	bsf	((c:1224))^0400h,c,3	;volatile
	line	246
	movlb	4	; () banked
	bsf	((1040))&0ffh,3	;volatile
	line	247
	bcf	((1041))&0ffh,3	;volatile
	line	249
	
l3018:; BSR set to: 4

	movlw	low(013h)
	movlb	3	; () banked
	movwf	((1004))&0ffh	;volatile
	line	250
	
l3020:; BSR set to: 3

	clrf	((1016))&0ffh	;volatile
	line	251
	movlw	low(01Fh)
	movwf	((1018))&0ffh	;volatile
	line	252
	clrf	((1006+1))&0ffh	;volatile
	movlw	low(040h)
	movwf	((1006))&0ffh	;volatile
	line	253
	
l3022:; BSR set to: 3

	clrf	((1012))&0ffh	;volatile
	line	254
	
l3024:; BSR set to: 3

	clrf	((1013))&0ffh	;volatile
	line	255
	
l3026:; BSR set to: 3

	clrf	((1014))&0ffh	;volatile
	line	256
	movlw	low(084h)
	movwf	((1011))&0ffh	;volatile
	line	257
	
l188:; BSR set to: 3

	return	;funcret
	callstack 0
GLOBAL	__end_of_adc_init
	__end_of_adc_init:
	signat	_adc_init,89
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
;;		_main
;; This function uses a non-reentrant model
;;
psect	text20,class=CODE,space=0,reloc=2,group=1
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\Umul32.c"
	line	15
global __ptext20
__ptext20:
psect	text20
	file	"C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\pic\sources\c99\common\Umul32.c"
	line	15
	
___lmul:; BSR set to: 3

;incstack = 0
	callstack 126
	line	119
	
l3140:
	movlw	low(0)
	movwf	((c:___lmul@product))^0500h,c
	movlw	high(0)
	movwf	((c:___lmul@product+1))^0500h,c
	movlw	low highword(0)
	movwf	((c:___lmul@product+2))^0500h,c
	movlw	high highword(0)
	movwf	((c:___lmul@product+3))^0500h,c
	line	121
	
l3142:
	
	btfss	((c:___lmul@multiplier))^0500h,c,(0)&7
	goto	u2811
	goto	u2810
u2811:
	goto	l3146
u2810:
	line	122
	
l3144:
	movf	((c:___lmul@multiplicand))^0500h,c,w
	addwf	((c:___lmul@product))^0500h,c
	movf	((c:___lmul@multiplicand+1))^0500h,c,w
	addwfc	((c:___lmul@product+1))^0500h,c
	movf	((c:___lmul@multiplicand+2))^0500h,c,w
	addwfc	((c:___lmul@product+2))^0500h,c
	movf	((c:___lmul@multiplicand+3))^0500h,c,w
	addwfc	((c:___lmul@product+3))^0500h,c
	line	123
	
l3146:
	bcf	status,0
	rlcf	((c:___lmul@multiplicand))^0500h,c
	rlcf	((c:___lmul@multiplicand+1))^0500h,c
	rlcf	((c:___lmul@multiplicand+2))^0500h,c
	rlcf	((c:___lmul@multiplicand+3))^0500h,c
	line	124
	
l3148:
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
	goto	u2821
	goto	u2820

u2821:
	goto	l3142
u2820:
	
l260:
	line	128
	movff	(c:___lmul@product),(c:?___lmul)
	movff	(c:___lmul@product+1),(c:?___lmul+1)
	movff	(c:___lmul@product+2),(c:?___lmul+2)
	movff	(c:___lmul@product+3),(c:?___lmul+3)
	line	129
	
l261:
	return	;funcret
	callstack 0
GLOBAL	__end_of___lmul
	__end_of___lmul:
	signat	___lmul,8316
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
