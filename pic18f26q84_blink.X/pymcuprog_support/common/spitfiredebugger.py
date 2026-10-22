"""
Spitfire based debugger controller
"""
from logging import getLogger
# Data type helpers
from pyedbglib.util import binary

# SpitfireDebugger builds on Gen4WrapperDebugger and uses GEN4 scripts for programming...
from gen4engineinterface import Gen4WrapperDebugger
# ...but uses Spitfire inteface for debugging
from spitfireinterface import SpitfireInterface16bit, SpitfireInterface32bit

class SpitfireDebugger(Gen4WrapperDebugger):
    """
    Wrapper for Spitfire protocol based debugger
    """

    def __init__(self, device_name):
        super(SpitfireDebugger, self).__init__(device_name)
        self.logger = getLogger(__name__)
        self.spitfire = None

    def _read_id_raw(self):
        """Reads the device ID and returns it as a 32-bit value with the ID in the lower 16 bits

        :return: device ID as 32-bit value with ID in lower 16 bits
        :rtype: int
        """
        # Read device ID
        result = self.device_proxy.invoke_read(bytes_to_read=4, method=self.device_model.read_id)
        if 'dspic33a' in self.device_name.lower():
            device_id = binary.unpack_le32(result)
        else:
            device_id = binary.unpack_le32(result) >> 16

        return device_id

    def read_device_revision(self):
        """
        Reads the device revision

        :return: device revision
        :rtype: int
        """
        # Read device revision
        result = self.device_proxy.invoke_read(bytes_to_read=4, method=self.device_model.read_device_revision)
        if 'dspic33a' in self.device_name.lower():
            device_rev = binary.unpack_le32(result)
        else:
            device_rev = binary.unpack_le32(result) >> 16

        self.logger.info("Device revision read: {0:04X}".format(device_rev & 0xFFFF))
        return device_rev


    def _createSpitfireInterface(self):
        """Create Spitfire Interface instance
        """
        raise NotImplementedError('Please implement in subclass')

    def init_debug_session(self, program_de=True):
        """
        Start a debug session

        .. note:: setup_session must be run first

        :param program_de: Program Debug Executive
        :type program_de: bool, optional, defaults to True
        """
        self.logger.info("Entering debug mode")

        self._createSpitfireInterface()

        # Program the DE
        if program_de:
            if self.debug_exec_address is None:
                self.logger.warning("Debug Executive not set!")
            else:
                # Store flag for later write-back
                use_pe_original = self.use_pe

                # No PE usage when programming the DE as the PE won't work when Debug enable config bit
                # has been set (which normally happens before the debug session is initialized)
                self.use_pe = False

                self.enter_tmod()
                self.logger.info("Checking DE")
                status = True
                if self._verify_flash_block(self.debug_exec_address, self.debug_exec_data, silent_early_exit=True):
                    self.logger.info("DE OK")
                else:
                    self.logger.info("Erasing DE")
                    self.erase_de_memory(self.debug_exec_address, len(self.debug_exec_data))
                    self.logger.info("Writing DE")
                    self.write_de_memory(self.debug_exec_address, self.debug_exec_data)
                    self.logger.info("Verifying DE")
                    status = self._verify_flash_block(self.debug_exec_address, self.debug_exec_data)
                self.exit_tmod()

                # Revert the PE flag since we are done with DE programming
                self.use_pe = use_pe_original
                if not status:
                    self.logger.error("DE verification failed!")
                    raise Exception("Error writing debug executive! Unable to start debug session.")

        self.logger.info("Launch")
        self.exit_tmod()
        self.spitfire.enter_debug()

        # Read the DE version
        de_version = self.debug_read_de_version()

        # Reset state
        self._is_running = False
        self._in_tmod = False
        self._in_tmod_pe = False

    def end_debug_session(self):
        """
        End debug session
        """
        if self.spitfire:
            self.spitfire.leave_debug()
        else:
            self.logger.debug("Could not end debug session as it has not been started")

    def debug_read_memory(self, address, length):
        """
        Read memory in debug mode
        :param address: start address
        :param length: number of bytes to read
        :return:
        """
        self.logger.debug("Read RAM of %d byte(s) from %d", length, address)
        return self.spitfire.read_ram(address, int(length))

    def get_pc(self):
        """
        Read the PC
        """
        raise NotImplementedError('Please implement in subclass')

    def get_baud(self):
        """
        Get Spitfire baud rate
        """
        raise NotImplementedError('Please implement in subclass')

    def is_running(self):
        """
        State query
        """
        # Poll
        resp = self.spitfire.get_run_state()
        if resp[0] == 0:
            self._is_running = False
        elif resp[0] == 1:
            self._is_running = True
        else:
            self.logger.error("Error: undefined run/stopped state!")

        return self._is_running

    def debug_read_de_version(self):
        """
        Read Debug Exec version
        """
        self.logger.info("Read DE version")

        data = self.spitfire.read_de_version()
        self.logger.info("DE version: %d.%d.%d", data[2], data[1], data[0])
        return data

    def run(self):
        """
        Put the device in RUN mode
        """
        if self._is_running:
            self.logger.info("Already running!")
        else:
            self.spitfire.run()
            self._is_running = True

    def halt(self):
        """
        HALT the device
        """
        if not self._is_running:
            self.logger.info("Already halted!")
        else:
            self.spitfire.halt()
            self._is_running = False

    def step(self):
        """
        Single step and halt
        """
        if self._is_running:
            self.logger.info("Cannot step while running!")
        else:
            self.spitfire.step()

    def release_from_reset(self):
        """
        Release from reset
        """
        self.device_proxy.invoke(self.device_model.release_from_reset)
        # MCLR has just been messed with, can't assume programming mode to be active anymore
        self._in_tmod = False

    def hold_in_reset(self):
        """
        Hold in reset
        """
        self.device_proxy.invoke(self.device_model.hold_in_reset)
        # MCLR has just been messed with, can't assume programming mode to be active anymore
        self._in_tmod = False

    def reset_target(self):
        """
        Reset target (in debug session)
        """
        if self._is_running:
            self.logger.error("Cannot reset while running!")
        else:
            # Toggle reset - the RSTBUG is set, so the part will enter debug mode after reset
            self.hold_in_reset()
            self.release_from_reset()

    def debug_write_memory(self, address, data, length):
        """
        Write memory in debug mode
        :param address: start address
        :param data: data to write
        :param length: number of bytes to write
        """
        self.logger.debug("Write RAM of %d byte(s) to %d", length, address)
        self.spitfire.write_ram(address, data)

    def debug_read_emulation(self, address, length):
        """
        Read memory in debug mode
        :param address: start address
        :param length: number of bytes to read
        :return: data read from emulation space
        :rtype: bytearray
        """
        self.logger.debug("Read EMU (RAM) of %d byte(s) from %d", length, address)
        return self.spitfire.read_ram(address, int(length))

    def debug_write_emulation(self, address, data, length):
        """
        Write memory in debug mode
        :param address: start address
        :param data: data to write
        :param length: number of bytes to write
        """
        raise NotImplementedError('Please implement in subclass')

    def debug_read_flash(self, byte_address, numbytes):
        """
        Read flash in debug mode
        :param byte_address: start address
        :param numbytes: number of bytes to read
        :return: data read from flash space
        :rtype: bytearray
        """
        return self.spitfire.debug_read_flash(byte_address, numbytes)

class SpitfireDebugger16bit(SpitfireDebugger):
    """
    Spitfire debugger for devices with 16-bit core
    """

    def _createSpitfireInterface(self):
        """Create Spitfire Interface instance
        """
        self.spitfire = SpitfireInterface16bit(self.transport)

    def get_pc(self):
        """
        Read the PC
        """
        self.logger.debug("Read PC")
        result = self.spitfire.icd_read(address=0x0000002E, numbytes=4)
        pc = binary.unpack_le32(result)
        self.logger.debug("PC read as:")
        self.logger.debug(pc)
        return pc

    def get_baud(self):
        """
        Get Spitfire baud rate
        """
        self.logger.debug("Get baud")
        result = self.spitfire.icd_read(address=0x00FD0006, numbytes=2)
        baud = binary.unpack_le16(result)
        self.logger.debug("Baud read as: 0x%04X", baud)
        return baud

    def debug_write_emulation(self, address, data, length):
        """
        Write memory in debug mode
        :param address: start address
        :param data: data to write
        :param length: number of bytes to write
        """
        self.logger.debug("Write EMU (RAM) of %d byte(s) to %d", length, address)

        # At session start, MPLAB sends a block of data to configure the debug system
        # However some of this data is destructive to the nEDBG session, for example the baud rate
        # So some filtering and massaging is required.

        # Register addresses in the "EMU" space
        EMU_START =0xFD0000
        EMCON1 = EMU_START + 0x00
        EMCON2 = EMU_START + 0x02
        SSMSTAT = EMU_START + 0x04
        SPBRG = EMU_START + 0x06
        QTMR = EMU_START + 0x08
        DBGI = EMU_START + 0x0A

        NUM_RESERVED_BYTES = 12

        # Relevant EMCON1 register bits
        SSM_BUG_bp = 6
        CPUINBUG_bp = 15

        # Relevant EMCON2 register bits
        RSTBUG_bp = 1

        if length % 2 > 0:
            raise Exception("Invalid length for Emu memory write: 16-bit oriented memory")

        if length < 4:
            raise Exception("Invalid length for Emu memory write")

        # Read-mask-modify-write EMCOM1 and/or 2
        if address <= EMCON2:
            # Read out from the device
            device_emcon_values = self.debug_read_emulation(EMCON1, 4)
            device_emcon1 = binary.unpack_le16(device_emcon_values[0:2])
            device_emcon2 = binary.unpack_le16(device_emcon_values[2:4])
            self.logger.debug("Device has: 0x%04X and 0x%04X\n", device_emcon1, device_emcon2)

            if address <= EMCON1:
                # This value are coming from MPLABX
                mplab_emcon1 = binary.unpack_le16(data[0:2])
                self.logger.debug("MPLABX wants: 0x%04X for EMCON1\n", mplab_emcon1)

                # This mask comes from MPLABX
                mplabx_emcon1_mask = 0x0076
                self.logger.debug("EMCON1 mask is: 0x%04X\n", mplabx_emcon1_mask)

                # Only allow MPLABX to set those bits in the mask
                mplab_emcon1 &= mplabx_emcon1_mask

                # Only allow the device to keep those bits not in the mask
                masked_emcon1 = device_emcon1
                masked_emcon1 &= ~mplabx_emcon1_mask

                # Lastly set the bits needed by the debugger
                emcon1_value = mplab_emcon1 | masked_emcon1 | (1 << CPUINBUG_bp) | (1 << SSM_BUG_bp)
                self.logger.debug("EMCON1 result is: 0x%04X\n", emcon1_value)

                if emcon1_value == device_emcon1:
                    self.logger.debug("Skipping writing same value back to EMCON1 (0x%04X)", emcon1_value)
                else:
                    self.logger.debug("Writing NEW value to EMCON1 (0x%04X -> 0x%04X)", device_emcon1, emcon1_value)
                    # Write these values to the OCD
                    self.spitfire.write_ram(EMCON1, binary.pack_le16(emcon1_value))


            mplab_emcon2 = binary.unpack_le16(data[2:4])
            self.logger.debug("MPLABX wants: 0x%04X for EMCON2\n", mplab_emcon2)

            # This mask comes from MPLABX
            mplabx_emcon2_mask = 0x7000
            self.logger.debug("EMCON2 mask is: 0x%04X\n", mplabx_emcon2_mask)

            # Only allow MPLABX to set those bits in the mask
            mplab_emcon2 &= mplabx_emcon2_mask

            # Only allow the device to keep those bits not in the mask
            masked_emcon2 = device_emcon2
            masked_emcon2 &= ~mplabx_emcon2_mask

            # Lastly set the bits needed by the debugger
            emcon2_value = mplab_emcon2 | masked_emcon2 | (1 << RSTBUG_bp)
            self.logger.debug("EMCON2 result is: 0x%04X\n", emcon2_value)

            if emcon2_value == device_emcon2:
                self.logger.debug("Skipping writing same value back to EMCON2 (0x%04X)", emcon2_value)
            else:
                self.logger.debug("Writing NEW value to EMCON2 (0x%04X -> 0x%04X)", device_emcon2, emcon2_value)
                # Write these values to the OCD
                self.spitfire.write_ram(EMCON2, binary.pack_le16(emcon2_value))


        # Skip locations for SSMSTAT -> DBGI, and continue after that
        if length <= NUM_RESERVED_BYTES:
            return

        # Strip off reserved section
        address = address + NUM_RESERVED_BYTES
        length = length - NUM_RESERVED_BYTES
        data = data[NUM_RESERVED_BYTES:]

        self.logger.debug("Writing EMU memory: %d words from 0x%06X\n", len(data), address)

        self.spitfire.write_ram(address, data)



class SpitfireDebugger32bit(SpitfireDebugger):
    """
    Spitfire debugger for devices with 32-bit core
    """

    # To be used with read_named_register and write_named_register
    # Note the order of the registers is vital as it defines the index into the Debug Executive cache, see
    # https://bitbucket.microchip.com/projects/DTH/repos/realice/browse/debugexec/dspic33a/optimized33a.s#74 and
    # https://bitbucket.microchip.com/projects/MPLABXIDE/repos/mplab-libs/browse/RealICE4ToolsController/src/com/microchip/mplab/libs/RI4ToolsController/programmer/Debugger33A.java#37
    NAMED_REGISTERS = [
        'W0', 'W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8', 'W9', 'W10', 'W11', 'W12', 'W13', 'W14', 'W15',
        'SR', 'ACCAL', 'ACCAH', 'ACCAU', 'ACCBL', 'ACCBH', 'ACCBU',
        'F0', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12', 'F13', 'F14', 'F15', 'F16',
        'F17', 'F18', 'F19', 'F20', 'F21', 'F22', 'F23', 'F24', 'F25', 'F26', 'F27', 'F28', 'F29', 'F30', 'F31',
        'FSR', 'FCR', 'FEAR'
    ]

    # Start address of cached (by DE) Not Memory Mapped Registers (NMMRS), i.e. Named Rregisters
    # Hard-coded in the debug exec, https://bitbucket.microchip.com/projects/DTH/repos/realice/browse/debugexec/dspic33a/optimized33a.s#68
    NMMRS_DE_ADDR = 0x7BFE20

    def _createSpitfireInterface(self):
        """Create Spitfire Interface instance
        """
        self.spitfire = SpitfireInterface32bit(self.transport)

    def get_pc(self):
        """
        Read the PC
        """
        self.logger.debug("Read PC")
        result = self.spitfire.icd_read(address=0x00000038, numbytes=4)
        pc = binary.unpack_le32(result)
        self.logger.debug("PC read as:")
        self.logger.debug(pc)
        return pc

    def set_pc(self, pc):
        """
        Write the PC
        :param pc: PC value
        """
        # For dsPIC33 devices there is no separate set_pc command. Instead we write to a specific memory location
        # (found by debugging ICD4 code in MPLAB)
        self.debug_write_memory(0x38, [pc & 0xFF, (pc >> 8) & 0xFF, (pc >> 16) & 0xFF, (pc >> 24) & 0xFF], 4)

    def get_baud(self):
        """
        Get Spitfire baud rate
        """
        self.logger.debug("Get baud")
        result = self.spitfire.icd_read(address=0x2E18, numbytes=2)
        baud = binary.unpack_le16(result)
        self.logger.debug("Baud read as: 0x%04X", baud)
        return baud

    def debug_write_emulation(self, address, data, length):
        """
        Write memory in debug mode
        :param address: start address
        :param data: data to write
        :param length: number of bytes to write
        """
        self.logger.debug("Write EMU (RAM) of %d byte(s) to %d", length, address)

        EMU_START = 0x002E00
        ICDCON = EMU_START + 0x10
        ICDSTAT = EMU_START + 0x14
        SPBRG = EMU_START + 0x18
        QTMR = EMU_START + 0x1C
        DBGI = EMU_START + 0x20

        if length % 4 > 0:
            raise Exception("Invalid length for Emu memory write: 32-bit oriented memory")

        if length < 4:
            raise Exception("Invalid length for Emu memory write")

        if address <= ICDCON:
            self.logger.debug("Writing ICDCON register in EMU memory")
            self.spitfire.write_ram(address, data[0:4])
            address = address + 4
            length = length - 4
            data = data[4:]

        if address <= DBGI:
            # Skip SPBRG and QMTR registers to not mess up timing since current Spitfire support in 5G debugger
            # firmware does not support dynamic baud rate/timing, https://jira.microchip.com/browse/FW5G-1160
            # Also skip DBGI and ICDSTAT registers since they are read only registers
            if ((length + address) > DBGI):
                data = data[DBGI+4-address:]
                address = DBGI + 4
            else:
                # No more data to write
                return

        self.logger.debug("Writing EMU memory: %d words from 0x%06X\n", len(data), address)

        self.spitfire.write_ram(address, data)

    def debug_read_named_register(self, name):
        """Read a named register in debug mode

        Read a register by name on devices where registers are not memory mapped, e.g. dsPIC33A. These registers are cached by the Debug Executive (DE) and can be read from the cache.
        :param name: name of register to read
        :type name: string
        :return: value of register as 32-bit int
        :rtype: int (32-bit)
        """
        if name not in self.NAMED_REGISTERS:
            raise ValueError("Reading unknown named register: {}".format(name))

        index = self.NAMED_REGISTERS.index(name)

        result = self.debug_read_memory(self.NMMRS_DE_ADDR+index*4, 4)

        return binary.unpack_le32(result)

    def debug_write_named_register(self, name, value):
        """Write a named register in debug mode

        Write a register by name on devices where registers are not memory mapped, e.g. dsPIC33A. These registers are
        cached by the Debug Executive (DE) and can be written by writing to the cache.
        :param name: name of register to write
        :type name: string
        :param value: value to write as 32-bit int
        :type value: int (32-bit)
        """
        if name not in self.NAMED_REGISTERS:
            raise ValueError("Writing unknown named register: {}".format(name))

        index = self.NAMED_REGISTERS.index(name)

        return self.debug_write_memory(self.NMMRS_DE_ADDR+index*4, binary.pack_le32(value), 4)

