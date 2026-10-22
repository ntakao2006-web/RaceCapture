"""
Scripted debugger controller
"""
import logging

from debuggerbase import CmsisAtiPicDebugger
from primitiveaccumulator import PrimitiveFunctionAccumulatorExecuter
from primitiveembedded import PrimitiveFunctionEmbedded
# Primitive controller takes primitive sequences over USB and executes them
from pyedbglib.primitive.primitivecontroller import PrimitiveController
# Data type helpers
from pyedbglib.util import binary


def is_blank(data):
    """
    Checks if a block of flash memory in an array is 'blank'
    """
    for d in range(0, len(data), 2):
        if not data[d] == 0xFF:
            return False
        if not data[d + 1] == 0x3F:
            # TODO: flash width should depend on the target
            return False
    return True

class VoltageException(Exception):
    """
    Custom Exception for voltage check
    """
    def __init__ (self, msg=None, code=0):
        super(VoltageException, self).__init__(msg)
        self.code = code


class PythonScriptedPicDebugger(CmsisAtiPicDebugger):
    """
    Wrapper for a python-based debugger
    """

    def __init__(self, device_name):
        self.logger = logging.getLogger(__name__)
        CmsisAtiPicDebugger.__init__(self, device_name)
        self.logger.info("Creating nEDBG scripting wrapper")

    def _check_operating_voltage(self):
        """
        Checks operating voltage against voltage range of the device and
        gives appropriate messages to the user
        """
        # Tolerance is 5mV
        VDD_TOLERANCE = 0.005
        self.logger.debug("Operating voltage: %.01fV", self.voltage)

        # Check operating voltage against device file
        if self.voltage < self.device_model.VDDMIN-VDD_TOLERANCE:
            msg = "The target voltage ({0:.02f}V) is out of range for this device!".format(self.voltage)
            msg += "\r\nThe {0:s} must operate between {1:.01f}V and {2:.01f}V.".format(self.device_model.DISPLAY_NAME,
                                                                                        self.device_model.VDDMIN,
                                                                                        self.device_model.VDDMAX)
            msg += "\r\nAdjust the target voltage and try again."
            self.logger.error(msg)
            raise VoltageException(msg)

    def _check_vbormax_voltage(self):
        """
        Checks operating voltage against maximum lowest BOR voltage (VBORMAX) of the device and
        gives appropriate messages to the user
        """
        self.logger.debug("Operating voltage: %.01fV", self.voltage)

        # Check operating voltage against VBORMAX in device file
        if self.voltage < self.device_model.VBORMAX:
            msg = "The target voltage ({0:.02f}V) is below VBORMAX for the {1:s} ({2:.01f}V)".format(
                self.voltage, self.device_model.DISPLAY_NAME, self.device_model.VBORMAX)
            msg += "\r\nWhen erasing or programming flash memory on the {0:s} ".format(self.device_model.DISPLAY_NAME)
            msg += "the operating voltage must be above the active BOR threshold (if BOR is enabled), "
            msg += "or the highest BOR threshold for the lowest BOR voltage"
            msg += "(VBORMAX={0:.01f}V)".format(self.device_model.VBORMAX)
            msg += "\r\nRaise the target voltage accordingly and try again."
            self.logger.error(msg)
            raise VoltageException(msg)

    def _check_plausible_bor_voltage_error(self):
        """
        This is called when the device ID is not readable
        """

        self.logger.debug("Operating voltage: %.01fV", self.voltage)

        # Base message
        msg = "Unable to contact the device: reading device ID failed."

        # Check operating voltages against VBORHIGH in device file
        if self.voltage < self.device_model.VBORHIGH:
            msg += "\r\nOne possible cause of this may be operating at a voltage either "
            msg += "below the active BOR level or VBORMAX. "
            msg += "The target voltage ({0:.02f}V) is below ".format(self.voltage)
            if self.voltage < self.device_model.VBORMAX:
                msg += "VBORMAX for the {0:s} ({1:.01f}V)".format(self.device_model.DISPLAY_NAME,
                                                                  self.device_model.VBORMAX)
                msg += "\r\nRaise the target voltage accordingly and try again."
            else:
                msg += "the maximum BOR value for the {0:s} ({1:.01f}V)".format(self.device_model.DISPLAY_NAME,
                                                                                self.device_model.VBORHIGH)
                msg += "\r\nIf the BOR is enabled, raise the target voltage accordingly and try again."

            self.logger.error(msg)
            raise VoltageException(msg)

    def setup_session(self, tool, options):
        """
        Takes transport and options and propagates them down the stack
        :param tool: tool AKA transport (HID or MPLAB)
        :param options: dictionary of session options

        NB: transport object passed in is either:
        - MPLAB-transport from within MPLAB Jython
        - HIDAPI-transport from standalone Python
        The MPLAB transport gets wrapped in a HID-API API equivalent wrapper
        to become self.transport before use
        """
        CmsisAtiPicDebugger.setup_session(self, tool, options)

        # NB: Use self.transport only after setup session

        # Note isinstance() does not work reliably since the tool could be generated by pymcuprog resulting in
        # different Class IDs for the debugprovider classes due to Python import technicalities

        # Raspberry Pi etc
        if 'EmbeddedTool' in str(type(tool)):
            # Use this mode to execute primitives locally on an embedded python engine
            self.logger.debug("Embedded Tool")
            self.device_proxy = PrimitiveFunctionEmbedded(self.device_object)

        elif 'PrinterTool' in str(type(tool)):
            # Use this mode to display primitive strings
            self.logger.debug("Printer Tool")
            from primitiveprinter import PrimitiveFunctionPrinter
            self.device_proxy = PrimitiveFunctionPrinter(self.device_object)

            self.debug_executive_model = self.device_model.DEBUGGING_INTERFACE
            self.debug_executive_object = self.device_model.DEBUGGING_INTERFACE()

            self.debug_executive_proxy = PrimitiveFunctionPrinter(self.debug_executive_object)

        elif 'ConfigGeneratorTool' in str(type(tool)):
            # Use this mode to generate XML output
            self.logger.debug("Config Tool")
            from primitiveprinter import PrimitiveFunctionXmlGenerator
            self.device_proxy = PrimitiveFunctionXmlGenerator(self.device_object, tool)

        else:
            # Pre-initialised HID transport, see notes above
            self.logger.debug("HID Tool")
            # Controller object for interfacing with the debugger tool
            self.logger.info("Creating primitive controller")
            self.controller = PrimitiveController(self.transport)

            # Use this mode to accumulate primitives, compress them, then execute them on a remote USB host
            self.device_proxy = PrimitiveFunctionAccumulatorExecuter(self.device_object, self.controller)

            # Instantiate the debug executive driver
            # Debug is currently only available when using remote USB primitive execution (ie: transport exists)
            self.debug_executive_model = self.device_model.DEBUGGING_INTERFACE
            self.debug_executive_object = self.device_model.DEBUGGING_INTERFACE()
            self.debug_executive_proxy = PrimitiveFunctionAccumulatorExecuter(self.debug_executive_object,
                                                                          self.controller)

    def set_debug_exec(self, byte_address, data):
        """
        Store the debug exec for later use
        """
        self.logger.info("Storing debug exec address: 0x%X", byte_address)
        self.debug_exec_address = byte_address
        self.debug_exec_data = data

    def enter_tmod(self):
        """
        Enter TMOD (programming mode)
        """
        # Already in?
        if self._in_tmod:
            return

        # Preliminary Voltage check
        self._check_operating_voltage()

        # Set ICSP clock frequency
        self.device_proxy.invoke(self.device_model.set_speed)

        # Enter TMOD
        self.device_proxy.invoke(self.device_model.enter_tmod)

        # Read ID for good measure
        result = self.device_proxy.invoke_read(bytes_to_read=2, method=self.device_model.read_id)
        device_id = binary.unpack_le16(result)

        self.logger.info("Device ID read: {0:04X}".format(device_id & 0xFFFF))
        if device_id == 0x0000 or device_id == 0xFFFF:
            # Something is up
            self.logger.error("Unable to read device ID while entering TMOD")
            # Voltage check with respect to BOR
            self._check_plausible_bor_voltage_error()
        elif self.device_model.DEVICE_ID and (device_id != self.device_model.DEVICE_ID):
            # Device ID read out an unexpected value: display an error, but continue
            self.logger.error("Unexpected device ID! (expected: {0:04X} read: {1:04X})".format(
                self.device_model.DEVICE_ID, device_id & 0xFFFF))

        self._in_tmod = True

    def read_id(self):
        """
        Reads the device ID
        :return: device ID
        """
        # Read device ID
        result = self.device_proxy.invoke_read(bytes_to_read=2, method=self.device_model.read_id)
        device_id = binary.unpack_le16(result)
        self.logger.info("Device ID read: {0:04X}".format(device_id & 0xFFFF))
        if device_id == 0x0000 or device_id == 0xFFFF:
            self.logger.error("Unable to read device ID")
            # Voltage check with respect to operating range
            self._check_operating_voltage()
            # Voltage check with respect to BOR
            self._check_plausible_bor_voltage_error()
        elif self.device_model.DEVICE_ID and (device_id != self.device_model.DEVICE_ID):
            # Device ID read out an unexpected value: display an error, but continue
            self.logger.error("Unexpected device ID! (expected: {0:04X} read: {1:04X})".format(
                self.device_model.DEVICE_ID, device_id & 0xFFFF))

        return device_id

    def read_device_revision(self):
        """
        Reads the device revision
        :return: device revision
        """
        # Read device revision
        result = self.device_proxy.invoke_read(bytes_to_read=2, method=self.device_model.read_device_revision)
        device_rev = binary.unpack_le16(result)
        self.logger.info("Device revision read: {0:04X}".format(device_rev & 0xFFFF))
        return device_rev

    def exit_tmod(self):
        """
        Exit TMOD (programming mode)
        """
        # Already out?
        if not self._in_tmod:
            return

        # Exit TMOD
        self.device_proxy.invoke(self.device_model.exit_tmod)

        self._in_tmod = False

    def read_flash_memory(self, byte_address, numbytes):
        """
        Read flash memory
        :param byte_address: start address
        :param numbytes: number of bytes
        """
        # Gather chunks
        result = bytearray()

        # TODO - read granularity from tool
        chunk_size = 0x100

        # Loop until done
        while numbytes > 0:
            # Handle leftovers
            if chunk_size > numbytes:
                chunk_size = numbytes
            # Read
            chunk = self._read_flash_block(byte_address, chunk_size)
            # Word address increment
            byte_address += chunk_size
            numbytes -= chunk_size
            # Append to results
            result.extend(chunk)

        return result

    def read_config_memory(self, byte_address, numbytes):
        """
        Read config memory
        :param byte_address: start address
        :param numbytes: number of bytes
        """
        # Gather chunks
        result = bytearray()

        if hasattr(self.device_model, 'read_config_byte'):
            # Byte oriented config memory
            while numbytes > 0:
                self.logger.debug("Read config byte at 0x{:02X}".format(byte_address))
                # Invoke read by proxy, reading one byte at a time
                chunk = self.device_proxy.invoke_read(bytes_to_read=1, method=self.device_model.read_config_byte,
                                                      byte_address=int(byte_address))
                numbytes -= 1
                byte_address += 1
                # Append to results
                result.extend(chunk)
        elif hasattr(self.device_model, 'read_config_word'):
            # Word oriented config memory

            # Word count, make sure we read the complete word(s) in case somebody asks for an odd number of bytes
            words = (numbytes + 1) // 2
            # Loop until done
            while words > 0:
                self.logger.debug("Read config word at 0x{:02X}".format(byte_address))
                # Invoke read by proxy, reading one word at a time
                chunk = self.device_proxy.invoke_read(bytes_to_read=2, method=self.device_model.read_config_word,
                                                      byte_address=int(byte_address))
                words -= 1
                byte_address += 2
                # Append to results
                result.extend(chunk)

            # Did anyone ask for an odd number of bytes? Remove the excess byte
            if numbytes%2 == 1:
                del result[-1]

        return result

    def read_eeprom_memory(self, byte_address, numbytes):
        """
        Read eeprom memory
        :param byte_address: start address
        :param numbytes: number of bytes
        """
        # Gather chunks
        result = bytearray()

        # TODO - read granularity from tool
        chunk_size = 0x100

        # Loop until done
        while numbytes > 0:
            # Handle leftovers
            if chunk_size > numbytes:
                chunk_size = numbytes
            # Read
            chunk = self._read_eeprom_block(byte_address, chunk_size)
            # Word address increment
            byte_address += chunk_size
            numbytes -= chunk_size
            # Append to results
            result.extend(chunk)

        return result

    def _read_flash_block(self, byte_address, numbytes):
        """
        Read flash block
        """
        self.logger.debug("Read flash block ({0:d} bytes) at 0x{1:02X}".format(numbytes, byte_address))
        # Word count, make sure we read the complete word in case somebody asks for an odd number of bytes
        words = (numbytes + 1) // 2

        # Invoke read by proxy
        data = self.device_proxy.invoke_read(bytes_to_read=numbytes, method=self.device_model.read_flash,
                                             byte_address=int(byte_address), words=int(words))
        return data

    def _read_eeprom_block(self, byte_address, numbytes):
        """
        Read eeprom block
        """
        self.logger.debug("Read eeprom block ({0:d} bytes) at 0x{1:02X}".format(numbytes, byte_address))

        # Invoke read by proxy
        data = self.device_proxy.invoke_read(bytes_to_read=numbytes, method=self.device_model.read_eeprom,
                                             byte_address=int(byte_address), numbytes=int(numbytes))
        return data

    def write_eeprom_memory(self, byte_address, data):
        """
        Write eeprom memory
        :param byte_address: start address (byte address)
        :param data: data to write
        """

        # ATI chunk is 512
        # TODO: read out from ATI
        chunk_size = 512

        bytes_left = len(data)

        index = 0
        # Loop until done
        while bytes_left > 0:
            # Handle leftovers
            if chunk_size > bytes_left:
                chunk_size = bytes_left
            # Write
            self.write_eeprom_block(byte_address, data[index:index + chunk_size])
            # Address increment
            byte_address += chunk_size
            bytes_left -= chunk_size
            index += chunk_size

        # TODO - check result

    def write_eeprom_block(self, byte_address, data):
        """
        Write eeprom block

        This is an API function for the config generator in pymcuprog used to generate device config for kits
        :param byte_address: Byte address to start writing from
        :type byte_address: int
        :param data: Data bytearray to write
        :type data: bytearray
        """
        self.logger.debug("Writing EEPROM block of %d bytes at 0x%02X", len(data), int(byte_address))

        # Invoke write by proxy
        self.device_proxy.invoke_write(data_to_write=data, method=self.device_model.write_eeprom,
                                       byte_address=byte_address, numbytes=int(len(data)))
        # TODO - check result

    def write_flash_memory(self, byte_address, data):
        """
        Write flash memory
        :param byte_address: start address (byte address)
        :param data: data to write
        """
        if self.options['overlapped_usb_access']:
            self._write_flash_block_overlapped(byte_address, data)
        else:
            self._write_flash_block(byte_address, data)

    def _write_flash_block_overlapped(self, byte_address, data):
        self.logger.debug("Flash block write (overlapped)")
        chunk_size = self.device_object.get_flash_write_row_size_bytes()

        numbytes = len(data)
        data_buf_id = 0
        if numbytes < chunk_size:
            chunk_size = numbytes

        # Send first data first
        self.controller.write_data_buffer(data_buf_id, data[0:chunk_size])
        # Start first page write
        self.device_proxy.trigger_write(data_buffer_id=data_buf_id, method=self.device_model.write_flash_page,
                                        byte_address=int(byte_address), words=chunk_size // 2)

        # Shrink data
        data = data[chunk_size:]
        byte_address += chunk_size

        # Loop
        while data:
            # Handle leftovers
            if len(data) < chunk_size:
                chunk_size = len(data)

            # Buffer ID flip
            data_buf_id = (data_buf_id + 1) % 2

            # Write next page's data
            self.controller.write_data_buffer(data_buf_id, data[0:chunk_size])

            # Block while first one completes
            self.device_proxy.wait_write_done()

            # Trigger next
            self.device_proxy.trigger_write(data_buffer_id=data_buf_id, method=self.device_model.write_flash_page,
                                            byte_address=int(byte_address), words=chunk_size // 2)

            # TODO - check results
            # if function_retval[0] != 0x01:
            #    logging.error("Flash write FAILED! Return value was not True")
            #    sys.exit(1)

            # Increment byte address
            byte_address += chunk_size

            # Shrink data
            data = data[chunk_size:]

        # Wait for last chunk
        self.device_proxy.wait_write_done()

    @staticmethod
    def chunks(data, chunk_size):
        """
        Yield successive chunk_size-sized chunks from data
        """
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]

    def _write_flash_block(self, byte_address, data):
        """
        Writes flash
        :param byte_address:    byte address to start writing from
        :param data:            data to write
        """
        self.logger.debug("Flash block write")
        pagebytes = self.device_object.get_flash_write_row_size_bytes()

        skip_blank_pages = self.options['skip_blank_pages']
        for chunk in self.chunks(data, pagebytes):
            # TODO: not all PICs can just skip pages by leaving them out.
            if not skip_blank_pages or not is_blank(chunk):
                self.logger.debug("Writing a page at byte address 0x%04X", int(byte_address))
                self.write_flash_page(byte_address, chunk)
            else:
                self.logger.debug("Skipping a page at byte address 0x%04X", byte_address)
            # Increment address
            byte_address += pagebytes

    def write_flash_page(self, byte_address, data):
        """
        Write a single flash page

        This is an API function for the config generator in pymcuprog used to generate device config for kits
        :param byte_address: Byte address to start writing from
        :type byte_address: int
        :param data: Data bytearray to write
        :type data: bytearray
        """
        self.logger.debug("Flash page write")

        # Word count
        words = len(data) // 2

        # Invoke write by proxy
        self.device_proxy.invoke_write(data_to_write=data, method=self.device_model.write_flash_page,
                                       byte_address=byte_address, words=int(words))
        # TODO - check result

    def _write_de_page(self, byte_address, data):
        """
        Write a single flash page

        :param byte_address: Byte address to start writing from
        :type byte_address: int
        :param data: Data bytearray to write
        :type data: bytearrayam
        """
        self.logger.debug("DE page write")

        # Word count
        words = len(data) // 2

        # Invoke write by proxy
        self.device_proxy.invoke_write(data_to_write=data, method=self.device_model.write_de_page,
                                       byte_address=int(byte_address), words=int(words))

        # TODO - result check

    def _write_de_block(self, byte_address, data):
        """
        Writes flash

        :param byte_address: Byte address to start writing from
        :type byte_address: int
        :param data: Data bytearray to write
        :type data: bytearray
        """
        self.logger.debug("DE block write")
        pagebytes = self.device_object.get_flash_write_row_size_bytes()

        for chunk in self.chunks(data, pagebytes):
            self.logger.debug("Writing a page at byte address 0x%04X", byte_address)
            self._write_de_page(byte_address, chunk)
            # Increment address
            byte_address += pagebytes

    def _verify_flash_block(self, byte_address, data, silent_early_exit=False):
        """
        Verify Block
        """
        self.logger.debug("Reading flash (%d bytes from byte address 0x%04X)", len(data), byte_address)
        read_back = self.read_flash_memory(byte_address, len(data))

        self.logger.debug("Verifying flash")
        numerrors = 0
        for i in range(len(data)):
            if data[i] != read_back[i]:
                if silent_early_exit:
                    # This path is used when a verify failure has an immediate remedy (like checking if the PE is there)
                    # Bothering the user with errors and then fixing them silently is not polite.
                    return False
                numerrors += 1
                if numerrors <= 5:
                    self.logger.error("Flash verify error at 0x%04X (wrote 0x%02X; read 0x%02X)", (byte_address + i),
                                 data[i], read_back[i])
        if numerrors > 0:
            self.logger.error("%d verification errors", numerrors)
            return False
        return True

    def write_user_id_word(self, byte_address, data):
        """
        Write user_id word

        This is an API function for the config generator in pymcuprog used to generate device config for kits
        :param byte_address: Byte address to start writing from
        :type byte_address: int
        :param data: Data bytearray to write
        :type data: bytearray
        """
        self.logger.debug("Writing user_id word")
        self.device_proxy.invoke_write(data_to_write=data, method=self.device_model.write_user_id_word,
                                       byte_address=byte_address)

    def erase(self, byte_address=None):
        """
        Erase the device
        :param byte_address: address for the (bulk) erase, see programming spec for the target device for info on which
        memory sections will be erased
        """
        # Bulk erase is voltage dependent
        self._check_vbormax_voltage()
        # Use address if provided
        self.device_proxy.invoke(self.device_model.bulk_erase, byte_address=byte_address)

    def erase_de_memory(self, address, words):
        """
        Erase the Debug Executive
        :param address: start address
        :param words: number of words
        """
        # Generate a command to execute
        self.logger.debug("Erase DE at address 0x%X", address)
        self.device_proxy.invoke(self.device_model.erase_de, byte_address=int(address), words=int(words))

    def write_config_memory(self, byte_address, data):
        """
        Write config memory
        :param byte_address: start address (byte address)
        :param data: data to write
        """
        if hasattr(self.device_model, 'write_config_byte'):
            # Byte oriented config memory
            for i in range(len(data)):
                values = [data[i]]
                self.logger.debug("Writing one config byte at 0x{:02X}, value: ".format(byte_address + i, values[0]))
                self.write_config_byte(byte_address + i, values)
        elif hasattr(self.device_model, 'write_config_word'):
            if len(data) % 2:
                raise Exception("Config memory has word granularity on this device, "
                                "number of bytes to write must be an even number")
            # Word oriented config memory
            for i in range(len(data) // 2):
                values = data[i * 2:i * 2 + 2]
                self.logger.debug("Writing one config word at 0x{:02X}".format(byte_address + i * 2))
                self.logger.debug("0x{:02X} 0x{:02X}".format(values[0], values[1]))
                self.write_config_word(byte_address + i * 2, values)
        else:
            raise Exception("No support for writing config memory")

    def write_config_word(self, byte_address, data):
        """
        Write config word

        .. note:: The device either supports _write_config_word or _write_config_byte, never both

        This is an API function for the config generator in pymcuprog used to generate device config for kits
        :param byte_address: Byte address to start writing from
        :type byte_address: int
        :param data: Data bytearray to write
        :type data: bytearray
        """
        self.device_proxy.invoke_write(data_to_write=data, method=self.device_model.write_config_word,
                                       byte_address=byte_address)

    def write_config_byte(self, byte_address, data):
        """
        Write config byte

        .. note:: The device either supports write_config_word or write_config_byte, never both

        This is an API function for the config generator in pymcuprog used to generate device config for kits
        :param byte_address: Byte address to start writing from
        :type byte_address: int
        :param data: Data bytearray to write
        :type data: bytearray
        """
        self.device_proxy.invoke_write(data_to_write=data, method=self.device_model.write_config_byte,
                                       byte_address=byte_address)

    def write_user_id_memory(self, byte_address, data):
        """
        Write user_id memory
        :param byte_address: start address (byte address)
        :param data: data to write
        """
        for i in range(len(data) // 2):
            values = data[i * 2:i * 2 + 2]
            self.logger.debug("Writing one user id word at 0x{:02X}".format(byte_address + i * 2))
            self.logger.debug("0x{:02X} 0x{:02X}".format(values[0], values[1]))
            self.write_user_id_word(byte_address + i * 2, values)

    def start_programming_operation(self):
        """
        Start programming
        """
        self.enter_tmod()

    def end_of_operations(self):
        """
        Done programming
        """
        self.exit_tmod()

    def init_debug_session(self, program_de=True):
        """
        Start a debug session
        """
        self.logger.info("Entering debug mode")

        # Program the DE
        if program_de:
            if self.debug_exec_address is None:
                self.logger.warning("Debug Executive not set!")
            else:
                self.enter_tmod()
                self.logger.info("Checking DE")
                status = True
                if self._verify_flash_block(self.debug_exec_address, self.debug_exec_data, silent_early_exit=True):
                    self.logger.info("DE OK")
                else:
                    self.logger.info("Erasing DE")
                    self.erase_de_memory(self.debug_exec_address, len(self.debug_exec_data))
                    self.logger.info("Writing DE")
                    self._write_de_block(self.debug_exec_address, self.debug_exec_data)
                    self.logger.info("Verifying DE")
                    status = self._verify_flash_block(self.debug_exec_address, self.debug_exec_data)
                self.exit_tmod()
                if not status:
                    self.logger.error("DE verification failed!")
                    raise Exception("Error writing debug executive! Unable to start debug session.")

        self.logger.info("Launch")
        self.device_proxy.invoke(self.device_model.enter_debug)

        # Try to read the DE version to check that things are ok
        # If unable to communicate with the DE an exception will be raised and will have to be handled further up the stack.
        de_version = self.debug_read_de_version()

        # Reset state
        self._is_running = False
        self._in_tmod = False

    def end_debug_session(self):
        """
        End debug session
        """
        self.logger.info("Ending debug session")
        self._is_running = False

    @staticmethod
    def _check_de_response(result):
        """
        Checks the DE response
        :param result: raw response
        :return:
        """
        status = binary.unpack_le32(result)
        if status != 0:
            msg = "Fatal errror communicating with the debug executive. Error code {0:04X}.".format(status & 0xFFFF)
            raise Exception(msg)

    def debug_read_memory(self, byte_address, length):
        """
        Read memory in debug mode
        :param byte_address: start address (byte)
        :param length: number of locations to read
        :return:
        """
        self.logger.debug("Read mem of %d byte(s) from byte address %d", length, byte_address)

        # Setup read request
        de_command = self.debug_executive_object.de_command_memory_read(byte_address, length)

        # Execute via proxy
        return self.debug_executive_proxy.invoke_write_read(de_command, length, self.debug_executive_model.read_mem,
                                                            numbytes=int(length))

    def debug_write_memory(self, address, data, length):
        """
        Write memory in debug mode
        :param address: start address
        :param data: data to write
        :param length: number of locations to write
        :return:
        """
        self.logger.debug("Write mem of %d locations to address %d", length, address)

        # Setup write request
        de_command = self.debug_executive_object.de_command_memory_write(address, length)

        # Add data
        de_command.extend(data)

        result = self.debug_executive_proxy.invoke_write(data_to_write=de_command,
                                                         method=self.debug_executive_model.write_mem,
                                                         numbytes=int(length))
        self._check_de_response(result)

    def is_running(self):
        """
        State query
        """
        # Poll
        resp = self.debug_executive_proxy.invoke(self.debug_executive_model.get_run_state)
        if resp[0] & (1 << 2):
            self._is_running = False
        else:
            self._is_running = True

        return self._is_running

    def get_pc(self):
        """
        Read the PC
        """
        self.logger.debug("Read PC")
        resp = self.debug_executive_proxy.invoke(self.debug_executive_model.read_pc)

        # Mask out to 2 bytes
        pc = binary.unpack_le32(resp) & 0xFFFF
        self.logger.debug("PC read as:")
        self.logger.debug(pc)
        return pc

    def set_pc(self, pc):
        """
        Write the PC
        :param pc: PC value
        """
        self.logger.debug("Write PC to address %d", pc)

        # Send data
        de_command = self.debug_executive_object.de_command_set_pc(pc)

        # Execute
        result = self.debug_executive_proxy.invoke_write(data_to_write=de_command,
                                                         method=self.debug_executive_model.set_pc)
        self._check_de_response(result)

    def run(self):
        """
        Put the device in RUN mode
        """
        if self._is_running:
            self.logger.info("Already running!")
        else:
            result = self.debug_executive_proxy.invoke(self.debug_executive_model.run)
            self._check_de_response(result)
            self._is_running = True

    def halt(self):
        """
        HALT the device
        """
        if not self._is_running:
            self.logger.info("Already halted!")
        else:
            result = self.debug_executive_proxy.invoke(self.debug_executive_model.halt)
            self._check_de_response(result)
            self._is_running = False

    def step(self):
        """
        Single step and halt
        """
        if self._is_running:
            self.logger.info("Cannot step while running!")
        else:
            result = self.debug_executive_proxy.invoke(self.debug_executive_model.step)
            self._check_de_response(result)

    def reset_target(self):
        """
        Reset target (in debug session)
        """
        if self._is_running:
            self.logger.info("Cannot reset while running!")
        else:
            self.logger.info("Reseting...")
            self.enter_tmod()
            self.exit_tmod()
            # No need to re-program the DE
            self.init_debug_session(False)

    def release_from_reset(self):
        """
        Release from reset (programming session)
        """
        self.device_proxy.invoke(self.device_model.release_from_reset)
        # MCLR has just been messed with, can't assume programming mode to be active anymore
        self._in_tmod = False

    def hold_in_reset(self):
        """
        Hold in reset (programming session)
        """
        self.device_proxy.invoke(self.device_model.hold_in_reset)
        # MCLR has just been messed with, can't assume programming mode to be active anymore
        self._in_tmod = False

    def debug_read_de_version(self):
        """
        Read Debug Exec version
        """
        self.logger.info("Read DE version")

        data = self.debug_executive_proxy.invoke_read(bytes_to_read=4,
                                                      method=self.debug_executive_model.read_de_version)
        self.logger.info("DE version: %d.%d.%d.%d", data[3], data[2], data[1], data[0])
        return data

    def debug_erase(self, byte_address):
        """
        Erase flash memory in debug mode
        :param byte_address: page start address
        :return:
        """
        self.logger.error("Erase flash memory in debug mode is not supported for this device")

    def debug_read_flash(self, byte_address, numbytes):
        """
        Read flash in debug mode
        :param byte_address: start address
        :param numbytes: number of bytes to read
        :return:
        """
        self.logger.error("Read flash in debug mode is not supported for this device")

    def debug_write_flash(self, byte_address, data):
        """
        Write flash in debug mode
        :param byte_address: start address
        :param data: data to write
        """
        self.logger.error("Write flash in debug mode is not supported for this device")

    def debug_read_test(self, byte_address, numbytes):
        """
        Read Test / Configuration Memory (User ID, Config words, Test memory) in debug mode
        :param byte_address: start address (byte)
        :param numbytes: number of bytes to read
        :return:
        """
        self.logger.debug("Read Test memory of %d bytes from byte address %d", numbytes, byte_address)

        word_address = byte_address // 2
        words = numbytes // 2
        # Gather chunks
        result = bytearray()

        # TODO - read granularity from tool
        chunk_size_words = 0x100 // 2

        # Loop until done
        while words > 0:
            # Handle leftovers
            if chunk_size_words > words:
                chunk_size_words = words

            # Setup read request
            de_command = self.debug_executive_object.de_command_memory_read(word_address, chunk_size_words)

            # Execute via proxy
            chunk = self.debug_executive_proxy.invoke_write_read(de_command, chunk_size_words * 2,
                                                                 self.debug_executive_model.debug_read_test,
                                                                 numbytes=int(chunk_size_words * 2))
            # Word address increment
            word_address += chunk_size_words
            words -= chunk_size_words
            # Append to results
            result.extend(chunk)

        return result

    def debug_read_eeprom(self, byte_address, numbytes):
        """
        Read EEPROM in debug mode
        :param byte_address: start address (byte)
        :param numbytes: number of bytes to read
        :return:
        """
        self.logger.debug("Read EEPROM of %d bytes from byte address %d", numbytes, byte_address)

        # Gather chunks
        result = bytearray()

        # TODO - read granularity from tool
        chunk_size_bytes = 0x100

        # Loop until done
        while numbytes > 0:
            # Handle leftovers
            if chunk_size_bytes > numbytes:
                chunk_size_bytes = numbytes

            # Setup read request
            de_command = self.debug_executive_object.de_command_memory_read(byte_address, chunk_size_bytes)

            # Execute via proxy
            chunk = self.debug_executive_proxy.invoke_write_read(de_command, chunk_size_bytes,
                                                                 self.debug_executive_model.debug_read_eeprom,
                                                                 numbytes=int(chunk_size_bytes))
            # Address increment
            byte_address += chunk_size_bytes
            numbytes -= chunk_size_bytes
            # Append to results
            result.extend(chunk)

        return result

    def debug_read_named_register(self, name):
        """Read a named register in debug mode

        Read a register by name on devices where registers are not memory mapped, e.g. dsPIC33A. These registers are
        cached by the Debug Executive (DE) and can be read from the cache.
        :param name: name of register to read
        :type name: string
        :return: value of register as 32-bit int
        :rtype: int (32-bit)
        """
        self.logger.error("Read named register is not supported for this device")

    def debug_write_named_register(self, name, value):
        """Write a named register in debug mode

        Write a register by name on devices where registers are not memory mapped, e.g. dsPIC33A. These registers are
        cached by the Debug Executive (DE) and can be written by writing to the cache.
        :param name: name of register to write
        :type name: string
        :param value: value to write as 32-bit int
        :type value: int (32-bit)
        """
        self.logger.error("Write named register is not supported for this device")

    def set_sw_bp(self, byte_address, instruction, flags):
        """
        Insert / remove software breakpoint
        :param byte_address: address to probe
        :param instruction: instruction to insert
        :param flags: ignored
        :return: instruction removed
        """
        # pylint: disable=unused-argument
        # Fetch the number of words per page from the device
        pagebytes = self.device_object.get_flash_write_row_size_bytes()
        # Calculate the start address of this page
        page_start_address = byte_address & ~(pagebytes - 1)
        # Calculate the page offset of the instruction to modify
        page_offset = byte_address % pagebytes

        # Read out the original page
        self.logger.debug("Reading page starting at {0:04X}".format(page_start_address))
        data = self.debug_read_flash(page_start_address, pagebytes)

        # Extract the original instruction
        opcode = binary.unpack_le16(data[page_offset:page_offset + 2])
        self.logger.debug("Original instruction: 0x%04X", opcode)

        # Replace Instruction
        data[page_offset] = instruction & 0xFF
        data[page_offset + 1] = (instruction >> 8) & 0xFF

        # Erase page
        self.logger.debug("Erasing page at address {0:04X}".format(page_start_address))
        self.debug_erase(page_start_address)

        # Rewrite
        self.logger.debug("Writing back page")
        self.debug_write_flash(page_start_address, data)

        # Return the original opcode replaced
        return int(opcode)

    def debug_get_hardware_stack(self):
        """
        Get hardware stack implementation (architecture-dependent)
        """
        self.logger.error("Hardware stack not implemented!")

class PythonScriptedPic16Debugger(PythonScriptedPicDebugger):
    """
    PIC16 variant
    """
    def debug_get_hardware_stack(self):
        """
        Reads the entire hardware stack and returns a dictionary containing stack levels, program counter and stack pointer
        :returns: dictionary containing levels, program_counter, stack_pointer
        :rtype: dict
        """
        self.logger.debug("Get Hardware Stack")
        stack_info = {}
        # Query stack size from device model
        if not hasattr(self.device_model, 'STACK_LEVELS'):
            return stack_info
        numbytes = (self.device_model.STACK_LEVELS * 2) + 2 + 1

        # Fetch the raw data from the DE
        stack_raw = self.debug_executive_proxy.invoke_read(bytes_to_read=numbytes,
                                                           method=self.debug_executive_model.de_get_hardware_stack,
                                                           stack_dump_bytes=numbytes)

        # Extract the stack pointer which is the last single-byte element in the raw package
        stack_info['stack_pointer'] = stack_raw[-1]

        # Extract the program counter from the second-last and third-last locations
        # On a PIC16 this is a 2-byte word
        stack_info['program_counter'] = binary.unpack_le16(stack_raw[-3:-1])

        # The rest is stack content, which needs conversion from a raw list into two-byte words for PIC16
        stack_content = stack_raw[0:-3]
        stack_content_words = []
        for i in range(0, len(stack_content), 2):
            stack_content_words.append(binary.unpack_le16(stack_content[i:i+2]))
        stack_info['levels'] = stack_content_words

        return stack_info

    def debug_erase(self, byte_address):
        """
        Erase flash memory in debug mode
        :param byte_address: page start address
        :return:
        """
        self.logger.debug("Erase mem at byte address %d", byte_address)

        word_address = byte_address // 2

        # Setup erase request
        de_command = self.debug_executive_object.de_command_erase(word_address)

        # Execute
        result = self.debug_executive_proxy.invoke_write(data_to_write=de_command,
                                                         method=self.debug_executive_model.debug_erase_page,
                                                         delay=self.device_object.ROW_ERASE_DELAY_US)

        self._check_de_response(result)

    def debug_write_flash(self, byte_address, data):
        """
        Write flash in debug mode
        :param byte_address: start address
        :param data: data to write
        """
        self.logger.debug("Write flash of %d byte(s) to byte address %d", len(data), byte_address)

        word_address = byte_address // 2

        # Setup write request
        de_command = self.debug_executive_object.de_command_memory_write(word_address, len(data))

        # Add data
        de_command.extend(data)

        result = self.debug_executive_proxy.invoke_write(data_to_write=de_command,
                                                         method=self.debug_executive_model.debug_write_flash,
                                                         numbytes=len(data),
                                                         delay=self.device_object.PAGE_PROGRAMMING_DELAY_US)
        self._check_de_response(result)

    def debug_read_flash(self, byte_address, numbytes):
        """
        Read flash in debug mode
        :param byte_address: start address
        :param numbytes: number of bytes to read
        :return:
        """
        self.logger.debug("Read flash of %d bytes from byte address %d", numbytes, byte_address)

        word_address = byte_address // 2
        words = numbytes // 2

        # Gather chunks
        result = bytearray()

        # TODO - read granularity from tool
        chunk_size_words = 0x100 // 2

        # Loop until done
        while words > 0:
            # Handle leftovers
            if chunk_size_words > words:
                chunk_size_words = words

            self.logger.debug("Read %d words from word_address 0x%02X", chunk_size_words, word_address)

            # Setup read request
            de_command = self.debug_executive_object.de_command_memory_read(word_address, chunk_size_words)

            # Execute via proxy
            chunk = self.debug_executive_proxy.invoke_write_read(de_command, chunk_size_words * 2,
                                                                 self.debug_executive_model.debug_read_flash,
                                                                 numbytes=int(chunk_size_words * 2))

            # Word address increment
            word_address += chunk_size_words
            words -= chunk_size_words
            # Append to results
            result.extend(chunk)

        return result

class PythonScriptedPic18Debugger(PythonScriptedPicDebugger):
    """
    PIC18 variant
    """
    def debug_write_flash(self, byte_address, data):
        """
        Write flash in debug mode
        :param byte_address: start address
        :param data: data to write
        """
        self.logger.debug("Write flash of %d byte(s) to byte address %d", len(data), byte_address)

        numbytes = len(data)

        # Note for PIC18 the DE uses the NVM Write command (not the NVM Write Page command) which means that only one
        # word (2 bytes) can be written at a time
        chunk_size_bytes = 2

        dataindex = 0
        while numbytes:

            if chunk_size_bytes > numbytes:
                chunk_size_bytes = numbytes

            # Setup write request
            de_command = self.debug_executive_object.de_command_flash_write(byte_address, chunk_size_bytes)

            # Add data
            de_command.extend(data[dataindex:dataindex+chunk_size_bytes])

            result = self.debug_executive_proxy.invoke_write(data_to_write=de_command,
                                                            method=self.debug_executive_model.debug_write_flash,
                                                            numbytes=chunk_size_bytes,
                                                            delay=self.device_object.WRITE_PROGRAM_DELAY_US)
            self._check_de_response(result)

            byte_address += chunk_size_bytes
            dataindex += chunk_size_bytes
            numbytes -= chunk_size_bytes

    def debug_read_flash(self, byte_address, numbytes):
        """
        Read flash in debug mode
        :param byte_address: start address
        :param numbytes: number of bytes to read
        :return:
        """
        self.logger.debug("Read flash of %d bytes from byte address %d", numbytes, byte_address)

        words = numbytes // 2

        # Gather chunks
        result = bytearray()

        # TODO - read granularity from tool
        chunk_size_words = 0x100 // 2

        # Loop until done
        while words > 0:
            # Handle leftovers
            if chunk_size_words > words:
                chunk_size_words = words

            self.logger.debug("Read %d words from byte_address 0x%02X", chunk_size_words, byte_address)

            # Setup read request, note byte address but chunk size in words
            de_command = self.debug_executive_object.de_command_flash_read(byte_address, chunk_size_words)

            # Execute via proxy
            chunk = self.debug_executive_proxy.invoke_write_read(de_command, chunk_size_words * 2,
                                                                 self.debug_executive_model.debug_read_flash,
                                                                 numbytes=int(chunk_size_words * 2))

            # Word address increment
            byte_address += chunk_size_words * 2
            words -= chunk_size_words
            # Append to results
            result.extend(chunk)

        return result

    def debug_erase(self, byte_address):
        """
        Erase flash memory in debug mode
        :param byte_address: page start address
        :return:
        """
        self.logger.debug("Erase mem at byte address %d", byte_address)

        # Setup erase request
        de_command = self.debug_executive_object.de_command_erase(byte_address)

        # Execute
        result = self.debug_executive_proxy.invoke_write(data_to_write=de_command,
                                                         method=self.debug_executive_model.debug_erase_page,
                                                         delay=self.device_object.ROW_ERASE_DELAY_US)

        self._check_de_response(result)


    def debug_read_test(self, address, numbytes):
        """
        Read Test memory in debug mode
        """
        self.logger.error("Read test memory in debug mode is not supported for PIC18")

    def debug_read_eeprom(self, address, numbytes):
        """
        Read Test memory in debug mode
        """
        self.logger.error("Read EEPROM memory in debug mode is not supported for PIC18")

    def set_pc(self, pc):
        """
        Write the PC
        :param pc: PC value
        """
        self.logger.debug("Write PC to address %d", pc)

        # Send data
        de_command = self.debug_executive_object.de_command_set_pc(pc)

        # Execute
        result = self.debug_executive_proxy.invoke_write(data_to_write=de_command,
                                                         method=self.debug_executive_model.set_pc)
        self._check_de_response(result)

    def debug_read_emulation(self, address, length):
        """
        Read emulation memory in debug mode
        :param address: start address
        :param length: number of locations to read
        :return:
        """
        self.logger.debug("Read emulation memory of %d byte(s) from %d", length, address)

        # Setup read request
        de_command = self.debug_executive_object.de_command_memory_read(address, length)

        # Execute via proxy
        return self.debug_executive_proxy.invoke_write_read(de_command, length,
                                                            self.debug_executive_model.read_emulation,
                                                            numbytes=int(length))

    def debug_write_emulation(self, address, data, length):
        """
        Write emulation memory in debug mode
        :param address: start address
        :param data: data to write
        :param length: number of locations to write
        :return:
        """
        self.logger.debug("Write emulation memory of %d locations to address %d", length, address)

        # Setup write request
        de_command = self.debug_executive_object.de_command_memory_write(address, length)

        # Add data
        de_command.extend(data)

        result = self.debug_executive_proxy.invoke_write(data_to_write=de_command,
                                                         method=self.debug_executive_model.write_emulation,
                                                         numbytes=int(length))
        self._check_de_response(result)

    def get_pc(self):
        """
        Read the PC
        """
        self.logger.debug("Read PC")
        resp = self.debug_executive_proxy.invoke(self.debug_executive_model.read_pc)

        # Mask out to 3 bytes
        pc = binary.unpack_le32(resp) & 0xFFFFFF
        self.logger.debug("PC read as:")
        self.logger.debug(pc)
        return pc

    def debug_get_hardware_stack(self):
        """
        Reads the entire hardware stack and returns a dictionary containing stack levels, program counter and stack pointer

        :returns: dictionary containing levels, program_counter, stack_pointer
        :rtype: dict
        """
        self.logger.debug("Get Hardware Stack")
        stack_info = {}
        # Query stack size from device model
        if not hasattr(self.device_model, 'STACK_LEVELS'):
            return stack_info
        numbytes = (self.device_model.STACK_LEVELS * 3) + 3 + 1

        # Fetch the raw data from the DE
        stack_raw = self.debug_executive_proxy.invoke_read(bytes_to_read=numbytes,
                                                           method=self.debug_executive_model.de_get_hardware_stack,
                                                           stack_dump_bytes=numbytes)

        # Extract the stack pointer which is the last single-byte element in the raw package
        stack_info['stack_pointer'] = stack_raw[-1]

        # Extract the program counter from the second-last and third-last and fourth-last locations
        # On a PIC18 this is a 3-byte word
        stack_info['program_counter'] = binary.unpack_le24(stack_raw[-4:-1])

        # The rest is stack content, which needs conversion from a raw list into three-byte words for PIC18
        stack_content = stack_raw[0:-4]
        stack_content_words = []
        for i in range(0, len(stack_content), 3):
            stack_content_words.append(binary.unpack_le24(stack_content[i:i+3]))
        stack_info['levels'] = stack_content_words

        return stack_info

class PythonScriptedPic18DebuggerNoSwbp(PythonScriptedPic18Debugger):
    """
    PIC18 variant without Software Breakpoint support
    """

    def set_sw_bp(self, byte_address, instruction, flags):
        """
        Insert / remove software breakpoint
        :param byte_address: address to probe
        :param instruction: instruction to insert
        :param flags: ignored
        :return: instruction removed
        """
        self.logger.error("Software breakpoints are not supported for this device")

