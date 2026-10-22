from pyedbglib.util import binary

# List of raw primitives used by the GEN4 script engine
SET_VPP_VOLTAGE_OPERATIONAL         = 0x42
SET_VPP_ON                          = 0xB0
DELAY_US                            = 0xA0
DELAY_MS                            = 0x94
SET_ICSP_PINS                       = 0xB2
GET_ICSP_PINS                       = 0x32
SET_VPP_OFF                         = 0xB1
WRITE_LITERAL_32_LSB                = 0xB4
WRITE_BITS_LITERAL                  = 0xB5
P16ENV3_WRITE_PAYLOAD_PARAM         = 0x86
P16ENV3_WRITE_PAYLOAD_LITERAL       = 0x87
P16ENV3_WRITE_BUFFER                = 0x88
P16ENV3_WRITE_BUFFER_DFM            = 0x49
P16ENV3_READ_PAYLOAD_PFM            = 0x84
P16ENV3_READ_PAYLOAD_DFM            = 0x48

WRITE_BITS_LITERAL_MSB              = 0x83
SET_CLK_DIR_IN                      = 0xB6
SET_CLK_DIR_OUT                     = 0xB7
SET_DATA_DIR_IN                     = 0xB8
SET_DATA_DIR_OUT                    = 0xB9
SET_CLK_HI                          = 0xBA
SET_CLK_LO                          = 0xBB
SET_DATA_HI                         = 0xBC
SET_DATA_LO                         = 0xBD
SET_UPLOAD                          = 0x95
SET_RETVAL                          = 0x9E
PAD_RESULT                          = 0x6B
P16F_READ_LOC_BUFFER                = 0x80
P16F_WRITE_LOC_BUFFER               = 0x81

UPLOAD_RESULT_32                    = 0x97
UPLOAD_PARAM_32                     = 0x98

SET_PARAM32                         = 0x90
LD_PARAM32                          = 0x91
DIV_PARAM                           = 0x93
DIV_PARAM_CEIL                      = 0xF5
COPY_PARAM_DST_SRC                  = 0x60
COPY_PARAM_BY_INDEX                 = 0x6D
SUB_PARAMS                          = 0x6A

INC_PARAM                           = 0x92

WHILE_PARAM                         = 0x62
ENDWHILE_PARAM                      = 0x63

DO                                  = 0xAC
LOOP                                = 0xA4

DO_PARAM                            = 0xAD
LOOP_PARAM                          = 0xAE

SETMARKER                           = 0xA2
LOOP_ON_RETURN_VAL                  = 0xA5


COMPARE_LIT                         = 0xA8
COMPARE_LIT_WITH_MASK               = 0xAA
COMPARE_PARAM                       = 0xBF
SHR_PARAM_LIT                       = 0x67
SHL_PARAM_LIT                       = 0x68
OR_PARAM_LIT                        = 0x61
AND_PARAM_LIT                       = 0x66

SET_SPEED                           = 0xEC
GET_SPEED                           = 0xED

DE_COMMAND                          = 0x31
DE_COMMAND_DATA_ONLY                = 0x35
GENDBG_BIT_BANG_HALT                = 0x30

COREINST24                          = 0xE0
NOP24                               = 0xE1
VISI24                              = 0xE2
VISI24_BYTE                         = 0xE3
WRITE_PARAM_3RDBYTE_toW             = 0xE4
WRITE_PARAM_LOWWORD_toW             = 0xE5
WRITE_BUF_WORD16_toW                = 0xE6


P24_SEND_PE_WORD                    = 0xE7
P24_SEND_PE_WORD_BUF                = 0xE8
P24_PE_HANDSHAKE                    = 0xE9
P24_RECEIVE_PE_WORD                 = 0xEA
P24_SEND_PE_WORD_PARAM              = 0xEB

COREINST33A                         = 0x13
VISI33A                             = 0x14
SEQLOAD33A                          = 0x15
SEQVISI33A                          = 0x16
MOVTOW33A                           = 0x19

# General helper macros
def SET_CLOCK_PERIOD(ns):
    """
    Set the clock period
    :param ns: clock period in ns
    """
    return [SET_SPEED] + list(binary.pack_le32(ns))

def DELAY_MICRO(us):
    """
    Delay
    :param us: delay period in whole microseconds
    """
    return [DELAY_US] + list(binary.pack_le16(us))

def DELAY_MILLI(ms):
    """
    Delay
    :param ms: delay period in whole milliseconds
    """
    return [DELAY_MS] + list(binary.pack_le16(ms))

# Macros for helping with PIC24/dsPIC
def CORE_INSTRUCTION(instruction):
    """
    PIC24/dsPIC33 core instruction
    :param instruction: opcode to execute
    """
    return [COREINST24] + list(binary.pack_le24(instruction))

def PIC24_NOP(n=1):
    """
    PIC24/dsPIC33 core no-operation
    :param n: number of NOPs to execute
    """
    return [NOP24] * n

def INCREMENT_PARAM(param_number, increment_value):
    """
    Increments a parameter by a given value
    :param param_number: ID of the parameter to increment
    :param increment_value: value to add to existing parameter value
    """
    return [INC_PARAM, param_number] + list(binary.pack_le32(increment_value))

def DIVIDE_PARAM_CEIL(param_number, divisor):
    """
    Divides a parameter by a given value
    :param param_number: ID of the parameter to increment
    :param divisor: value to divide the existing parameter value by
    """
    return [DIV_PARAM_CEIL, param_number] + list(binary.pack_le16(divisor))

def POLLING_LOOP(mask, value, timeout):
    """
    Loops back to marker depending on the return value (stack) matching a masked value
    :param mask: mask to apply
    :param value: value to match
    :param timeout: max polling period in milliseconds
    """
    return [LOOP_ON_RETURN_VAL] + list(binary.pack_le32(mask)) + list(binary.pack_le32(value)) + list(binary.pack_le16(timeout))

def EXIT_RESET_VECTOR():
    """
    Exits the reset vector
       - NOP, NOP, NOP
       - GOTO 0x200
       - NOP, NOP, NOP
    """
    return [NOP24, NOP24, NOP24] + CORE_INSTRUCTION (0x040200) + [NOP24, NOP24, NOP24]

def CORE_INSTRUCTION_33A(instruction):
    """
    dsPIC33A core instruction
    :param instruction: opcode to execute
    """
    return [COREINST33A] + list(binary.pack_le32(instruction))