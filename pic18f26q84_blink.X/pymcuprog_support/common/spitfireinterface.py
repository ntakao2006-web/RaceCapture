"""
Interface to Spitfire module on dsPIC devices
"""
import time
from logging import getLogger
# Spitfire controller takes Spitfire commands and executes them
from pyedbglib.primitive.spitfirecontroller import SpitfireController, DATA_SOURCE_UNDEFINED, DATA_DEST_UNDEFINED

# Data type helpers
from pyedbglib.util import binary


class SpitfireException(Exception):
    """
    Custom Exception for Spitfire module
    """
    def __init__ (self, msg=None, code=0):
        super(SpitfireException, self).__init__(msg)
        self.code = code

class SpitfireInterface(object):
    """
    Interaction with the Spitfire module on dsPIC devices

    :param transport: Transport object for USB transport over HID
    :type transport: Instance of either :class:`pyedbglib.hidtransport.CyHidApiTransport` or
        :class:`pyedbglib.mplabtransport.mplabtransport.MpLabTransport`
    """

    SPITFIRE_CONTROLLER_INIT = 0
    SPITFIRE_CONTROLLER_UNINIT = 1
    SPITFIRE_CONTROLLER_QUERY_RUN_STATE = 2
    SPITFIRE_CONTROLLER_COMMAND = 3
    SPITFIRE_CONTROLLER_BLOCK_READ = 4
    SPITFIRE_CONTROLLER_BLOCK_WRITE = 5
    SPITFIRE_CONTROLLER_SHORT_WRITE = 6
    SPITFIRE_CONTROLLER_SET_WORD_SIZE_32BIT = 7

    SPITFIRE_ACCESS_ICD_WRITE = 0x80
    SPITFIRE_ACCESS_ICD_READ = 0x81
    SPITFIRE_ACCESS_APP_IN = 0x82
    SPITFIRE_ACCESS_DEBUG_IN = 0x83
    SPITFIRE_ACCESS_HALT = 0x84
    SPITFIRE_ACCESS_NOP = 0x85

    SPITFIRE_STATUS_OK = 0
    SPITFIRE_STATUS_INVALID = 1
    SPITFIRE_STATUS_TIMEOUT = 2
    SPITFIRE_STATUS_INTERNAL_ERROR = 3
    SPITFIRE_COMMAND_UNEXPECTED_TOKEN = 4
    SPITFIRE_COMMAND_READ_ERROR = 5
    SPITFIRE_COMMAND_TIMEOUT_ERROR_SENDER = 6
    SPITFIRE_COMMAND_TIMEOUT_ERROR_QUERY = 7
    SPITFIRE_COMMAND_TIMEOUT_ERROR_RESPONSE = 8

    DE_CMD_VERSION = 0x02
    DE_CMD_SINGLESTEP = 0x03
    DE_CMD_RUN = 0x04
    DE_CMD_BULK_READ_PGM = 0x05
    DE_CMD_BULK_WRITE_PGM = 0x06
    DE_CMD_UFEX = 0x07
    DE_CMD_BULK_READ_DATA = 0x08
    DE_CMD_BULK_WRITE_DATA = 0x09

    COMMAND_TIMEOUT_MS = 200

    # Debug executive locations,
    # Note these are defaults based on dsPIC33C values and must be overridden by subclasses to suit the specific
    # architecture
    DE_BASE = 0x00001000
    RESP_RDY_ADDR = DE_BASE+0x32
    RESP_DATA_ADDR = DE_BASE+0x34
    CMD_DATA_ADDR = DE_BASE+0x38

    def __init__(self, transport):
        self.logger = getLogger(__name__)
        self.flags = 0x00
        self.transport = transport
        self.controller = SpitfireController(self.transport)

    def _create_de_command_header(self, access_type, command_id):
        """Create header for Debug Executive command

        :param access_type: Spitfire access type
        :type access_type: int
        :param command_id: Debug Executive command ID
        :type command_id: int

        :return: Debug Executive command header bytes
        :rtype: bytearray
        """
        raise NotImplementedError('Please implement in subclass')

    def spitfire_command(self, access_type, command=None, flags=0x00, data_source_bytes=0, data_dest_bytes=0):
        """
        Create Spitfire command to send to debugger

        :param access_type: Spitfire access type/command byte
        :type access_type: byte
        :param command: Raw command bytes, optional, defaults to None
        :type command: bytes
        :param flags: Spitfire command flags, optional, defaults to 0x00
        :type flags: byte
        :param data_source_bytes: Number of bytes to be sent through data source buffer, optional, defaults to 0
        :type data_source_bytes: int
        :param data_dest_bytes: Number of bytes to be received through data destination buffer, optional, defaults to 0
        :type data_dest_bytes: int
        """
        frame = bytearray()
        frame.append(access_type)
        frame.append(flags)
        if command:
            frame.extend(binary.pack_le16(len(command)))
        else:
            # No command bytes, i.e. length is 0
            frame.extend(binary.pack_le16(0x0000))

        # Just allocate space for data source buffer ID, will be populated by ATI layer later
        frame.append(DATA_SOURCE_UNDEFINED)
        # Source length (i.e. number of bytes in data source buffer)
        frame.extend(binary.pack_le16(data_source_bytes))
        # Just allocate space for data destination buffer ID, will be populated by ATI layer later
        frame.append(DATA_DEST_UNDEFINED)
        # Destination length (i.e. number of bytes to expect back in data destination buffer)
        frame.extend(binary.pack_le16(data_dest_bytes))
        # Timeout in milliseconds for the command
        frame.extend(binary.pack_le16(self.COMMAND_TIMEOUT_MS))

        if command:
            for commandbyte in command:
                frame.append(commandbyte)

        return frame

    def execute_command(self, command):
        """
        Send Spitfire command

        :param command: Raw bytes to be sent over ATI to Spitfire interface
        :type command: bytes
        """
        spitfire_cmd = self.controller.new_command(command)
        # Generate a bytestream and pass is to the controller for execution
        return self.controller.execute_single_block(spitfire_cmd.generate_bytestream())

    def execute_read(self, command, bytes_to_read):
        """
        Execute spitfire read command

        :param command: Raw bytes to be sent over ATI to Spitfire interface
        :type command: bytes
        :param bytes_to_read: Number of bytes to receive
        :type bytes_to_read: int
        :return: Raw data
        :rtype: bytes
        """
        spitfire_cmd = self.controller.new_command(command)
        # Use a trivial data buffer
        data_buffer_id = 1
        # Assign the data buffer
        spitfire_cmd.set_data_dest(data_buffer_id)
        # Generate a bytestream pass it to the controller for execution
        status = self.controller.execute_single_block(spitfire_cmd.generate_bytestream())
        statuscode = binary.unpack_le32(status)
        if statuscode != self.SPITFIRE_STATUS_OK:
            self.logger.debug("Spitfire read status: 0x%08X", statuscode)
            raise SpitfireException("Error executing Spitfire read", code=statuscode)

        # Read back and return the data buffer after execution
        return self.controller.read_data_buffer(data_buffer_id, bytes_to_read)

    def execute_write(self, command, data=None):
        """
        Execute spitfire write command

        :param command: Raw bytes to be sent over ATI to Spitfire interface
        :type command: bytes
        :param data: Data to write
        :type data: bytes
        """
        spitfire_cmd = self.controller.new_command(command)
        if data:
            # Use a trivial data buffer
            data_buffer_id = 1
            # Assign the data buffer
            spitfire_cmd.set_data_source(data_buffer_id)
            # Put the data in
            self.controller.write_data_buffer(data_buffer_id, data)
        # Generate a bytestream pass it to the controller for execution
        status = self.controller.execute_single_block(spitfire_cmd.generate_bytestream())
        statuscode = binary.unpack_le32(status)
        if statuscode != 0:
            self.logger.debug("Spitfire write status: 0x%08X", statuscode)
            raise SpitfireException("Error executing Spitfire write", code=statuscode)

    def check_response(self, result):
        """
        Check Spitfire command response

        :param result: Raw response bytes from Spitfire command
        :type result: bytes
        :raises SpitfireException: If status is not OK
        """
        # For Spitfire commands there is only one status byte
        status = result[0]
        if status == self.SPITFIRE_STATUS_OK:
            return

        if status == self.SPITFIRE_STATUS_INVALID:
            raise SpitfireException("Invalid command")
        if status == self.SPITFIRE_STATUS_INTERNAL_ERROR:
            raise SpitfireException("Internal error")
        if status == self.SPITFIRE_STATUS_TIMEOUT:
            raise SpitfireException("Command timed out")
        if status == self.SPITFIRE_COMMAND_UNEXPECTED_TOKEN:
            raise SpitfireException("Unexpected token in data stream")
        if status == self.SPITFIRE_COMMAND_READ_ERROR:
            raise SpitfireException("Read error")
        if status == self.SPITFIRE_COMMAND_TIMEOUT_ERROR_SENDER:
            raise SpitfireException("Timeout waiting to send frame")
        if status == self.SPITFIRE_COMMAND_TIMEOUT_ERROR_QUERY:
            raise SpitfireException("Timeout waiting query frame")
        if status == self.SPITFIRE_COMMAND_TIMEOUT_ERROR_RESPONSE:
            raise SpitfireException("Timeout waiting for response frame")

        raise SpitfireException("Unknown Spitfire status: 0x{:02X}".format(status))

    def enter_debug(self):
        """
        Start debugging session
        """
        raise NotImplementedError('Please implement in subclass')

    def leave_debug(self):
        """
        Leave debugging session
        """
        # No command content
        command = self.spitfire_command(access_type=self.SPITFIRE_CONTROLLER_UNINIT, flags=self.flags)
        self.execute_command(command)

    def icd_write(self, address, data):
        """
        Execute ICD write command

        :param address: Start address
        :type address: int
        :param data: data to write
        :type data: bytearray
        """
        self.logger.debug("ICD write")

        # Write in chunks of 252 bytes
        SPITFIRE_WRITE_CHUNK_SIZE = 252

        numbytes = len(data)
        if numbytes < 1:
            raise ValueError("Data size must be at least one byte")

        while numbytes:
            if numbytes <= SPITFIRE_WRITE_CHUNK_SIZE:
                bytes_to_write = numbytes
            else:
                bytes_to_write = SPITFIRE_WRITE_CHUNK_SIZE

            # Prepare the header for the Spitfire protocol command
            spitfire_command = bytearray([self.SPITFIRE_ACCESS_ICD_WRITE])
            # Length includes the address and payload but is off-by-one by design
            spitfire_command.extend([4+bytes_to_write-1])
            spitfire_command.extend(binary.pack_le32(address))

            # There are two ways to route a write: a long or a short way
            if bytes_to_write > 2:
                # Indirect data, with command pre-pended so its a single write from the data buffer
                command = self.spitfire_command(self.SPITFIRE_CONTROLLER_BLOCK_WRITE,
                                                spitfire_command,
                                                flags=self.flags,
                                                data_source_bytes=len(spitfire_command)+bytes_to_write)
                spitfire_command.extend(data[:bytes_to_write])
                self.execute_write(command, spitfire_command)
            else:
                # Short write has data inline
                spitfire_command.extend(data)
                command = self.spitfire_command(self.SPITFIRE_CONTROLLER_SHORT_WRITE,
                                                spitfire_command,
                                                flags=self.flags)
                self.execute_write(command)

            # There will not be any status return code from the spitfire_command calls.
            # If any errors happen an exception will be raised

            # Update variables before next loop iteration
            numbytes = numbytes - bytes_to_write
            address = address + bytes_to_write
            data = data[bytes_to_write:]

    def icd_read(self, address, numbytes):
        """
        Execute ICD read command

        :param address: Start address
        :type address: int
        :param numbytes: Number of bytes to read
        :type numbytes: int
        :returns: Raw data
        :rtype: bytes
        """
        self.logger.debug("ICD read")
        # MPLAB X seems to sometimes want to read 0 bytes (seen for PIC33A), makes no sense, but should not harm either
        if numbytes > 65535 or numbytes < 0:
            raise ValueError("numbytes ({}) is a 16-bit value so it should be in the range [0, 65535]".format(numbytes))

        # Read in chunks of 256 bytes.  However its safer to stick to 254, see:
        # https://jira.microchip.com/browse/DSG-5462
        # Had to lower this even further to 252 bytes to get it to work for dsPIC33AK512MPS506
        SPITFIRE_READ_CHUNK_SIZE = 252
        result = bytearray()
        while numbytes:
            if numbytes <= SPITFIRE_READ_CHUNK_SIZE:
                bytes_to_read = numbytes
            else:
                bytes_to_read = SPITFIRE_READ_CHUNK_SIZE

            spitfire_command = bytearray([self.SPITFIRE_ACCESS_ICD_READ])
            spitfire_command.extend(binary.pack_le32(address))
            # Note that the Spitfire protocol will read one byte more than the read count
            spitfire_command.append(bytes_to_read - 1)
            command = self.spitfire_command(self.SPITFIRE_CONTROLLER_BLOCK_READ,
                                            spitfire_command,
                                            flags=self.flags,
                                            data_dest_bytes=bytes_to_read)
            chunk = self.execute_read(command, bytes_to_read)
            numbytes = numbytes - bytes_to_read
            address = address + bytes_to_read
            result.extend(chunk)
        return result

    def step(self):
        """
        DE execute, no data
        """
        # Clear the flag first
        self._clear_de_data_ready_flag()

        # Request target to perform a single-step via the DE
        de_command = self._create_de_command_header(self.SPITFIRE_ACCESS_DEBUG_IN, self.DE_CMD_SINGLESTEP)
        command = self.spitfire_command(access_type=self.SPITFIRE_CONTROLLER_COMMAND,
                                        command=de_command,
                                        flags=self.flags)
        result = self.execute_command(command)
        self.check_response(result)

        # Wait for step to complete
        if not self._wait_de_data_ready():
            raise SpitfireException("Timeout waiting for DE")

        # And clear the flag again
        self._clear_de_data_ready_flag()

    def run(self):
        """
        Spitfire run command
        """
        # Request target to enter run mode via the DE
        de_command = self._create_de_command_header(self.SPITFIRE_ACCESS_DEBUG_IN, self.DE_CMD_RUN)
        command = self.spitfire_command(access_type=self.SPITFIRE_CONTROLLER_COMMAND,
                                        command=de_command,
                                        flags=self.flags)
        result = self.execute_command(command)
        self.check_response(result)

    def get_run_state(self):
        """
        Get target run/stop state.
        Indirect return.
        """
        # Debugger caches run/stop state.  Request the last-known state
        command = self.spitfire_command(access_type=self.SPITFIRE_CONTROLLER_QUERY_RUN_STATE,
                                        command=[],
                                        flags=self.flags,
                                        data_dest_bytes=1)
        return self.execute_read(command, 1)

    def halt(self):
        """
        HALT the target
        """
        # Direct Spitfire request for device to halt
        command = self.spitfire_command(access_type=self.SPITFIRE_CONTROLLER_COMMAND,
                                        command=[self.SPITFIRE_ACCESS_HALT],
                                        flags=self.flags)
        resp = self.execute_command(command)
        self.check_response(resp)

    def read_de_version(self):
        """
        Read the version of the debug executive by asking it
        """
        de_command = self._create_de_command_header(self.SPITFIRE_ACCESS_DEBUG_IN, self.DE_CMD_VERSION)
        return self.read_via_debug_executive(de_command, 3)

    def debug_read_flash(self, byte_address, numbytes):
        """
        Read flash while in debug mode

        :param byte_address: Byte address to start reading from
        :type byte_address: int
        :param numbytes: Number of bytes to read
        :type numbytes: int
        :returns: Raw data bytes
        """
        raise NotImplementedError('Please implement in subclass')

    def read_ram(self, offset, numbytes):
        """
        Read RAM directly from Spitfire
        """
        self.logger.debug("Reading RAM")
        response = self.icd_read(offset, numbytes)
        return response

    def write_ram(self, offset, data):
        """
        Write RAM directly to Spitfire
        """
        self.logger.debug("Writing RAM")
        self.icd_write(offset, data)

    def read_via_debug_executive(self, de_command, bytes_expected):
        """
        Executes a read command via the debug executive
        """
        # Clear the data flag first
        self._clear_de_data_ready_flag()

        # Form and send in the command
        command = self.spitfire_command(access_type=self.SPITFIRE_CONTROLLER_COMMAND,
                                        command=de_command,
                                        flags=self.flags)
        result = self.execute_command(command)
        self.check_response(result)

        # Wait for it to be ready
        if not self._wait_de_data_ready():
            raise SpitfireException("Timeout waiting for DE")

        # Read the data itself
        response = self.icd_read(self.RESP_DATA_ADDR, bytes_expected)

        # And clear the flag again
        self._clear_de_data_ready_flag()
        return response

    def _clear_de_data_ready_flag(self):
        """
        Clear flag for shared memory transfers between Spitfire and the Debug Executive
        """
        self.logger.debug("Clearing DE data ready flag")
        self.icd_write(self.RESP_RDY_ADDR, [0])

    def _wait_de_data_ready(self, timeout=1.0):
        """
        Wait for the shared memory flag for transfers between Spitfire and the Debug Executive

        :param timeout: timeout in seconds to wait
        :type timeout: optional, float, defaults to 1.0
        :returns: True if flag was raised, False if timeout
        :rtype: boolean
        """
        self.logger.debug("Waiting for DE data ready")
        while True:
            if self._is_de_data_ready():
                return True
            timeout -= 0.01
            if timeout <= 0:
                return False
            time.sleep(0.01)

    def _is_de_data_ready(self):
        """
        Check for the shared memory flag for transfers between Spitfire and the Debug Executive

        :returns: True if flag is raised, False if not
        :rtype: boolean
        """
        self.logger.debug("Checking for DE data ready")
        breadcrumb = self.icd_read(self.RESP_RDY_ADDR, 1)
        if breadcrumb[0] == 1:
            self.logger.debug("DE data ready")
            return True
        self.logger.debug("DE data NOT ready")
        return False

    def de_read_flash_pack_size(self):
        """
        Read package size for flash
        """
        raise NotImplementedError('Please implement in subclass')

class SpitfireInterface16bit(SpitfireInterface):
    """
    SpitfireInterface implementation for devices with 16-bit PIC core (dsPIC33C)
    """

    # Debug executive locations
    DE_BASE = 0x00001000
    RESP_RDY_ADDR = DE_BASE+0x32
    RESP_DATA_ADDR = DE_BASE+0x34
    CMD_DATA_ADDR = DE_BASE+0x38

    def _create_de_command_header(self, access_type, command_id):
        """Create header for Debug Executive command

        :param access_type: Spitfire access type
        :type access_type: int
        :param command_id: Debug Executive command ID
        :type command_id: int

        :return: Debug Executive command header bytes
        :rtype: bytearray
        """
        return bytearray([access_type])+binary.pack_le16(command_id)

    def enter_debug(self):
        """
        Start debugging session
        """
        # No command content
        command = self.spitfire_command(access_type=self.SPITFIRE_CONTROLLER_INIT, flags=self.flags)
        resp = self.execute_command(command)
        self.check_response(resp)

    def debug_read_flash(self, byte_address, numbytes):
        """
        Read flash while in debug mode

        :param byte_address: Byte address to start reading from
        :type byte_address: int
        :param numbytes: Number of bytes to read (including dummy bytes, i.e. 4 bytes per instruction)
        :type numbytes: int
        :returns: Raw data bytes, packed format
            (two 24-bit instructions are packed into 6 bytes, see programming specification)
        """
        # dsPIC33 DE packs flash data according to prog spec, i.e. 2 24-bit instructions packed into 6 bytes/3 words
        # (16-bit words). The bytes parameter we get in is number of bytes to read where each 24-bit
        # instruction actually takes up 4 bytes in the memory map, i.e. 2 16-bit words or 32 bits.
        # Since data is packed we only have to transfer numbytes*(3/4)
        numbytes_actual = (numbytes * 3) // 4

        # TODO: read out from ATI
        chunk_size_bytes = 512

        # The chunk size must be possible to split into an integer number of n byte "packs"
        chunk_size_bytes -= chunk_size_bytes % self.de_read_flash_pack_size()

        temp_chunk_size_bytes = chunk_size_bytes
        data = bytearray()

        # Loop until done
        while numbytes_actual > 0:
            # One chunk should not cross the 16-bit boundary for word address (i.e. 0x20000 byte address)
            # see MPLABX-4374
            # Remember each 3 bytes corresponds to one 24-bit instruction which takes up four bytes in the memory map
            if byte_address < 0x20000 and (byte_address + (chunk_size_bytes * 4) // 3) >= 0x20000:
                # Only read the memory locations up to the 16-bit boundary for word address
                temp_chunk_size_bytes = ((0x20000 - byte_address) * 3) // 4
            else:
                temp_chunk_size_bytes = chunk_size_bytes

            # Handle leftovers
            if temp_chunk_size_bytes > numbytes_actual:
                temp_chunk_size_bytes = numbytes_actual

            if temp_chunk_size_bytes % self.de_read_flash_pack_size():
                # Only full "packs" can be read so round up to closest full pack
                temp_chunk_size_bytes = (temp_chunk_size_bytes + self.de_read_flash_pack_size()) - temp_chunk_size_bytes % self.de_read_flash_pack_size()

            # Put address into CMD_DATA_ADDR[0,1]
            self.logger.debug("Write address")

            # DE expects word address
            word_address = byte_address // 2

            # Write two 16-bit values
            self.icd_write(self.CMD_DATA_ADDR, binary.pack_le16(word_address & 0xFFFF))
            self.icd_write(self.CMD_DATA_ADDR+2, binary.pack_le16((word_address >> 16) & 0xFFFF))

            numpacks = temp_chunk_size_bytes // self.de_read_flash_pack_size()

            # Put number of "packs" to read in CMD_DATA_ADDR[2]
            self.logger.debug("Write chunk count")
            self.icd_write(self.CMD_DATA_ADDR+4, binary.pack_le16(numpacks))

            # Kick off the DE COMMAND
            self.logger.debug("DE_CMD_BULK_READ_PGM")
            de_command = self._create_de_command_header(self.SPITFIRE_ACCESS_DEBUG_IN, self.DE_CMD_BULK_READ_PGM)
            # Form and send in the command
            command = self.spitfire_command(access_type=self.SPITFIRE_CONTROLLER_COMMAND,
                                            command=de_command,
                                            flags=self.flags)
            result = self.execute_command(command)
            self.check_response(result)

            # Read data from DE, one pack at a time
            while numpacks > 0:
                self.logger.debug("Waiting for flash to be read by DE")
                if not self._wait_de_data_ready():
                    raise SpitfireException("Timeout waiting for DE")

                self.logger.debug("Checking DE response signature")
                response = self.icd_read(self.RESP_DATA_ADDR, 2)
                if response != bytearray([0xAA, 0x55]):
                    raise SpitfireException("Flash ready signature not received from DE")

                self.logger.debug("Reading out data")
                data.extend(self.icd_read(self.CMD_DATA_ADDR, self.de_read_flash_pack_size()))

                self._clear_de_data_ready_flag()

                self.logger.debug("Clearing DE response signature")
                self.icd_write(self.RESP_DATA_ADDR, bytearray([0x00]*2))

                numpacks -= 1

            # Remember each 3 bytes corresponds to one 24-bit instruction which takes up four bytes in the memory map
            byte_address += (temp_chunk_size_bytes * 4) // 3
            numbytes_actual -= temp_chunk_size_bytes

        return data

    def de_read_flash_pack_size(self):
        """
        Read package size for flash
        """
        return 12

class SpitfireInterface32bit(SpitfireInterface):
    """
    SpitfireInterface implementation for devices with 32-bit PIC core (dsPIC33A)
    """

    # Debug executive locations
    RESP_RDY_ADDR = 0x7BFE00
    RESP_DATA_ADDR = 0x7BFE04
    CMD_DATA_ADDR = 0x7BFE08

    def _create_de_command_header(self, access_type, command_id):
        """Create header for Debug Executive command

        :param access_type: Spitfire access type
        :type access_type: int
        :param command_id: Debug Executive command ID
        :type command_id: int

        :return: Debug Executive command header bytes
        :rtype: bytearray
        """
        return bytearray([access_type])+binary.pack_le32(command_id)

    def enter_debug(self):
        """
        Start debugging session
        """
        # No command content
        command = self.spitfire_command(access_type=self.SPITFIRE_CONTROLLER_SET_WORD_SIZE_32BIT, flags=self.flags)
        resp = self.execute_command(command)
        self.check_response(resp)
        # No command content
        command = self.spitfire_command(access_type=self.SPITFIRE_CONTROLLER_INIT, flags=self.flags)
        resp = self.execute_command(command)
        self.check_response(resp)

    def debug_read_flash(self, byte_address, numbytes):
        """
        Read flash while in debug mode

        :param byte_address: Byte address to start reading from
        :type byte_address: int
        :param numbytes: Number of bytes to read
        :type numbytes: int
        :returns: Raw data bytes
        """
        # TODO: read out from ATI
        chunk_size_bytes = 512

        # The chunk size must be possible to split into an integer number of n byte "packs"
        chunk_size_bytes -= chunk_size_bytes % self.de_read_flash_pack_size()

        temp_chunk_size_bytes = chunk_size_bytes
        data = bytearray()

        # Loop until done
        while numbytes > 0:
            temp_chunk_size_bytes = chunk_size_bytes

            # Handle leftovers
            if temp_chunk_size_bytes > numbytes:
                temp_chunk_size_bytes = numbytes

            if temp_chunk_size_bytes % self.de_read_flash_pack_size():
                # Only full "packs" can be read so round up to closest full pack
                temp_chunk_size_bytes = (temp_chunk_size_bytes + self.de_read_flash_pack_size()) - temp_chunk_size_bytes % self.de_read_flash_pack_size()

            # Put address into CMD_DATA_ADDR[0,1]
            self.logger.debug("Write address")

            self.icd_write(self.CMD_DATA_ADDR, binary.pack_le32(byte_address))

            numpacks = temp_chunk_size_bytes // self.de_read_flash_pack_size()

            self.logger.debug("Write chunk count")
            self.icd_write(self.CMD_DATA_ADDR+4, binary.pack_le32(temp_chunk_size_bytes))

            # Kick off the DE COMMAND
            self.logger.debug("DE_CMD_BULK_READ_PGM")
            de_command = self._create_de_command_header(self.SPITFIRE_ACCESS_DEBUG_IN, self.DE_CMD_BULK_READ_PGM)
            # Form and send in the command
            command = self.spitfire_command(access_type=self.SPITFIRE_CONTROLLER_COMMAND,
                                            command=de_command,
                                            flags=self.flags)
            result = self.execute_command(command)
            self.check_response(result)

            # Read data from DE, one pack at a time
            while numpacks > 0:
                self.logger.debug("Waiting for flash to be read by DE")
                if not self._wait_de_data_ready():
                    raise SpitfireException("Timeout waiting for DE")

                self.logger.debug("Checking DE response signature")
                response = self.icd_read(self.RESP_DATA_ADDR, 2)
                if response != bytearray([0xAA, 0x55]):
                    raise SpitfireException("Flash ready signature not received from DE")

                self.logger.debug("Reading out data")
                data.extend(self.icd_read(self.CMD_DATA_ADDR, self.de_read_flash_pack_size()))

                self._clear_de_data_ready_flag()

                self.logger.debug("Clearing DE response signature")
                self.icd_write(self.RESP_DATA_ADDR, bytearray([0x00]*2))

                numpacks -= 1

            byte_address += temp_chunk_size_bytes
            numbytes -= temp_chunk_size_bytes

        return data

    def de_read_flash_pack_size(self):
        """
        Read package size for flash
        """
        return 16