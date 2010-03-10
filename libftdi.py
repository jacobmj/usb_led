#!/usr/bin/env python

# Jacob Joseph
# 2008-02-22

# 2010-02-25 - Updated for Libftdi 0.17

# An initial attempt to use the libftdi library for the FTDI usb
# interfaces.  (see
# http://www.intra2net.com/de/produkte/opensource/ftdi/)

# This use of ctypes is modeled after an FTD2xx driver posted in a
# forum by Jonathan Roadley-Battin

from ctypes import *

# Enum types aren't directly supported
# FTDI chip type
#enum ftdi_chip_type { TYPE_AM=0, TYPE_BM=1, TYPE_2232C=2, TYPE_R=3, TYPE_2232H=4, TYPE_4232H=5 };
(fct_TYPE_AM, fct_TYPE_BM, fct_TYPE_2232C,
 fct_TYPE_R, fct_TYPE_2232H, fct_TYPE_4232H) = map(c_int, range(6))

# Parity mode for ftdi_set_line_property()
#enum ftdi_parity_type { NONE=0, ODD=1, EVEN=2, MARK=3, SPACE=4 };
(fpt_NONE, fpt_ODD, fpt_EVEN, fpt_MARK, fpt_SPACE) = map(c_int, range(5))

# Number of stop bits for ftdi_set_line_property()
#enum ftdi_stopbits_type { STOP_BIT_1=0, STOP_BIT_15=1, STOP_BIT_2=2 };
(fst_STOP_BIT_1, fst_STOP_BIT_15, fst_STOP_BIT_2) = map(c_int, range(3))

# Number of bits for ftdi_set_line_property()
#enum ftdi_bits_type { BITS_7=7, BITS_8=8 };
(fbt_BITS_7, fbt_BITS_8) = map(c_int, (7,8))

# Break type for ftdi_set_line_property2()
#enum ftdi_break_type { BREAK_OFF=0, BREAK_ON=1 };
(fbt_BREAK_OFF, fbt_BREAK_ON) = map(c_int, (0,1));

# MPSSE bitbang modes
BITMODE_RESET  = 0x00    # switch off bitbang mode, back to regular serial/FIFO
BITMODE_BITBANG= 0x01    # classical asynchronous bitbang mode, introduced with B-type chips
BITMODE_MPSSE  = 0x02    # MPSSE mode, available on 2232x chips
BITMODE_SYNCBB = 0x04    # synchronous bitbang mode, available on 2232x and R-type chips
BITMODE_MCU    = 0x08    # MCU Host Bus Emulation mode, available on 2232x chips
                         # CPU-style fifo mode gets set via EEPROM 
BITMODE_OPTO   = 0x10    # Fast Opto-Isolated Serial Interface Mode, available on 2232x chips
BITMODE_CBUS   = 0x20    # Bitbang on CBUS pins of R-type chips, configure in EEPROM before
BITMODE_SYNCFF = 0x40    # Single Channel Synchronous FIFO mode, available on 2232H chips

#enum ftdi_interface {
#    INTERFACE_ANY = 0,
#    INTERFACE_A   = 1,
#    INTERFACE_B   = 2
#};
(fi_INTERFACE_ANY, fi_INTERFACE_A,
 fi_INTERFACE_B, fi_INTERFACE_C,
 fi_INTERFACE_D) = map(c_int, range(5))

# Shifting commands IN MPSSE Mode
MPSSE_WRITE_NEG = 0x01   # Write TDI/DO on negative TCK/SK edge
MPSSE_BITMODE   = 0x02   # Write bits, not bytes
MPSSE_READ_NEG  = 0x04   # Sample TDO/DI on negative TCK/SK edge
MPSSE_LSB       = 0x08   # LSB first
MPSSE_DO_WRITE  = 0x10   # Write TDI/DO
MPSSE_DO_READ   = 0x20   # Read TDO/DI
MPSSE_WRITE_TMS = 0x40   # Write TMS/CS

# FTDI MPSSE commands
SET_BITS_LOW    = 0x80
SET_BITS_HIGH   = 0x82
GET_BITS_LOW    = 0x81
GET_BITS_HIGH   = 0x83
LOOPBACK_START  = 0x84
LOOPBACK_END    = 0x85
TCK_DIVISOR     = 0x86

#/* Value Low */
#/* Value HIGH */ /*rate is 12000000/((1+value)*2) */
#define DIV_VALUE(rate) (rate > 6000000)?0:((6000000/rate -1) > 0xffff)? 0xffff: (6000000/rate -1)

# Commands in MPSSE and Host Emulation Mode
SEND_IMMEDIATE  = 0x87 
WAIT_ON_HIGH    = 0x88
WAIT_ON_LOW     = 0x89

# Commands in Host Emulation Mode
READ_SHORT      = 0x90
READ_EXTENDED   = 0x91
WRITE_SHORT     = 0x92
WRITE_EXTENDED  = 0x93

# Definitions for flow control
SIO_RESET        =  0 # Reset the port
SIO_MODEM_CTRL   =  1 # Set the modem control register
SIO_SET_FLOW_CTRL=  2 # Set flow control register
SIO_SET_BAUD_RATE=  3 # Set baud rate
SIO_SET_DATA     =  4 # Set the data characteristics of the port

class usb_dev_handle(Structure):
    pass

# Pointers
c_ubyte_p = POINTER(c_ubyte)
usb_dev_handle_p = POINTER(usb_dev_handle)

class ftdi_context(Structure):
    _fields_ = [
        # USB specific
        ('usb_dev', usb_dev_handle_p), # struct usb_dev_handle *usb_dev;
        ('usb_read_timeout', c_int),
        ('usb_write_timeout', c_int),
        # FTDI specific
        ('type', c_int),               # enum ftdi_chip_type type; 
        ('baudrate', c_int),
        ('bitbang_enabled', c_ubyte),
        ('readbuffer', c_ubyte_p),
        ('readbuffer_offset', c_uint),
        ('readbuffer_remaining', c_uint),
        ('readbuffer_chunksize', c_uint),
        ('writebuffer_chunksize', c_uint),
        ('max_packet_size', c_uint),
        # FTDI FT2232C requirements
        ('interface', c_int),
        ('index', c_int),
        ('in_ep', c_int),
        ('out_ep', c_int),
        # 1: (default) Normal bitbang mode, 2: FT2232C SPI bitbang mode
        ('bitbang_mode', c_ubyte),
        ('eeprom_size', c_int),
        ('error_str', c_char_p),
        ('async_usb_buffer', c_char_p),
        ('async_usb_buffer_size', c_uint)
        ]

class ftdi(object):
    """A ctype interface to the libfdi driver."""

    FT = None      # FTDI shared library
    context = None # context
    ftdic = None   # context.  C reference
    
    def __init__(self, description=None, serial=None):
        self.FT = CDLL("libftdi.so")
        self.set_return_types()

        self.context = ftdi_context()
        self.ftdic = byref( self.context)
        
        self.open()

        # be sure bitbang mode is disabled
        self.set_bitmode( 0xFF, BITMODE_RESET)

    def set_return_types(self):
        """set ctypes if not ints"""
        self.FT.ftdi_get_error_string.restype = c_char_p
        return

    def __del__(self):
        self.close()

    def get_error_string(self):
        return self.FT.ftdi_get_error_string( self.ftdic)

    def open(self, vendor=0x0403, product=0x6001):
        ret = self.FT.ftdi_init(self.ftdic)
        assert ret >= 0, "ftdi_init() failed: %d (%s)" % (
            ret, self.get_error_string())

        ret = self.FT.ftdi_usb_open(self.ftdic,
                                    vendor, product)
        assert ret >= 0, "ftdi_usb_open() failed: %d (%s)" % (
            ret, self.get_error_string())
        return ret

    def close(self):
        if self.ftdic is None:
            return None
        
        ret = self.FT.ftdi_usb_close(self.ftdic)
        assert ret >= 0, "ftdi_usb_close() failed: %d (%s)" % (
            ret, self.get_error_string())

        self.FT.ftdi_deinit(self.ftdic)
        #self.FT.ftdi_free( self.ftdic)
        #assert ret >= 0, "ftdi_deinit() failed: %d (%s)" % (
        #    ret, self.get_error_string())

        self.FT = None
        self.context = None
        self.ftdic = None
        return ret
    
    def set_bitmode( self, bitmask, mode):
        ret = self.FT.ftdi_set_bitmode( self.ftdic,
                                        bitmask,
                                        mode)
        assert ret >= 0, "ftdi_set_bitmode() failed: %d (%s)" % (
            ret, self.get_error_string())
        return ret

    def disable_bitbang(self):
        """Disable bitbang mode."""
        ret = self.FT.ftdi_disable_bitbang(self.ftdic)
        assert ret >= 0, "ftdi_disable_bitbang() failed: %d (%s)" % (
            ret, self.get_error_string())
        return ret

    def write_data(self, buf, size=None):
        """Writes data (bytes) in chunks to the chip."""

        # passed a python array
        if type(buf) is list:
            size = len(buf)
            Arr = c_ubyte * len(buf)
            cbuf = Arr( *buf)
        elif size is not None:
            cbuf = buf
        else:
            assert False, "write_data: must specify size if buf is not a python list"

        #from IPython.Shell import IPShellEmbed
        #ipsh = IPShellEmbed()
        #ipsh("ready to write data")
        
        ret = self.FT.ftdi_write_data(self.ftdic,
                                      byref(cbuf),
                                      size)
        assert ret >= 0, "ftdi_write_data() failed: %d (%s)" % (
            ret, self.get_error_string())
        return ret

    def read_data(self):
        """Read data from the device until there is no more, in
4096-byte chunks"""
        size = 4096

        Arr = c_ubyte * size
        cbuf = Arr()

        ret = []

        while True:
            nbytes = self.FT.ftdi_read_data( self.ftdic,
                                             byref(cbuf),
                                             size)
            assert nbytes >= 0, "ftdi_read_data() failed: %d (%s)" % (
                nbytes, self.get_error_string())
            ret += cbuf[:nbytes]
            if nbytes < size: break

        print "read %d bytes: %s" % (len(ret), ret)
        return ret
    
    def read_pins(self):
        """Read pins"""
        pin_state = c_int()
        
        ret = self.FT.ftdi_read_pins(self.ftdic,
                                     byref(pin_state))
        return pin_state

    def set_baudrate(self, rate):
        ret = self.FT.ftdi_set_baudrate(self.ftdic,
                                         rate)
        assert ret >= 0, "ftdi_set_baudrate() failed: %d (%s)" % (
            ret, self.get_error_string())
        return ret

    def purge_buffers(self):
        ret = self.FT.ftdi_usb_purge_buffers(self.ftdic)
        assert ret >= 0, "ftdi_usb_purge_buffers() failed: %d (%s)" % (
            ret, self.get_error_string())
        return ret
        
    def write_data_set_chunksize(self, chunksize):
        ret = self.FT.ftdi_write_data_set_chunksize(self.ftdic,
                                                    chunksize)
        assert ret >= 0, "ftdi_write_data_set_chunksize() failed: %d (%s)" % (
            ret, self.get_error_string())
        return ret

    def write_data_get_chunksize(self):
        chunksize = c_int()
        ret = self.FT.ftdi_write_data_get_chunksize(self.ftdic,
                                                    byref(chunksize))
        assert ret >= 0, "ftdi_write_data_get_chunksize() failed: %d (%s)" % (
            ret, self.get_error_string())
        return chunksize

    def set_latency_timer(self, latency):
        ret = self.FT.ftdi_set_latency_timer(self.ftdic,
                                             latency)
        assert ret >= 0, "ftdi_set_latency_timer() failed: %d (%s)" % (
            ret, self.get_error_string())
        return ret

    def get_latency_timer(self):
        latency = c_int()
        ret = self.FT.ftdi_get_latency_timer(self.ftdic,
                                             byref(latency))
        assert ret >= 0, "ftdi_get_latency_timer() failed: %d (%s)" % (
            ret, self.get_error_string())
        return latency
    
if __name__ == "__main__":
    ft = ftdi()

    #ft.enable_bitbang(0xFF)

    #Arr = c_int * 1000000
    #buf = Arr(*([0xFF, 0x00] * 500000))
    #time.time()
    #ft.write_data(buf, 1000000)
    #time.time()
