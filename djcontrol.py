#!env python

import usb.core
import usb.util
import time
from random import randint

# This is a tools that talks to the
#   Hercules DJControl MP3 LE
#
# It uses libUSB and PyUSB to talk to the controller via USB.
#
# Goals:
#   * read events from the controller (Button-pushes, Slider-movements)
#   * Turn LEDs under the buttons on/off
#   * Change sensitivity of the jog-dials (if possible; the windows-control-software implies that is possible)
#   * Act as ALSA-MIDI-Device to control audio-software
#
# TODO:
#   * name each value in data-exchange-buffers to qualify buttons/sliders/LEDs
#
# Gathered information:
#   * USB vid/pid: 06f8:b105
#   * Setup communication using an init sequence.
#   * The controller sends updates via bulk transfer
#   * On Every update the device sends a complete device state (all buttons/sliders)
#   * Updating LED values is done in 5 chunks of 2 bytes each.

class djcontrol:
    def __init__(self):
        # hercules djcontrol mp3 le:
        # ID 06f8:b105 Guillemot Corp.
        self.dev = usb.core.find(idVendor=0x06f8, idProduct=0xb105)

        if self.dev is None:
            raise ValueError('Device not found (vendor=0x06f8, pid=0xb105)')

        # set the active configuration. With no arguments, the first
        # configuration will be the active one
        self.dev.set_configuration()

        # get an endpoint instance
        self.cfg = self.dev.get_active_configuration()
        #intf = cfg[(0,0)]

        # Send init-sequence:
        ret = self.dev.ctrl_transfer(0xc0, 0x2c, 0x0000, 0x0000, 2)  # => 4040
        ret = self.dev.ctrl_transfer(0xc0, 0x29, 0x0300, 0x0000, 2)  # => 0c0c
        ret = self.dev.ctrl_transfer(0xc0, 0x29, 0x0400, 0x0000, 2)  # => f2f2
        ret = self.dev.ctrl_transfer(0xc0, 0x29, 0x0500, 0x0000, 2)  # => eded
        ret = self.dev.ctrl_transfer(0xc0, 0x29, 0x0600, 0x0000, 2)  # => 7373
        ret = self.dev.ctrl_transfer(0xc0, 0x2c, 0x0000, 0x0000, 2)  # => 4040
        ret = self.dev.ctrl_transfer(0xc0, 0x2c, 0x0000, 0x0000, 2)  # => 4040
        ret = self.dev.ctrl_transfer(0xc0, 0x29, 0x0300, 0x0000, 2)  # => 0c0c
        ret = self.dev.ctrl_transfer(0xc0, 0x29, 0x0400, 0x0000, 2)  # => f2f2
        ret = self.dev.ctrl_transfer(0xc0, 0x29, 0x0500, 0x0000, 2)  # => eded
        ret = self.dev.ctrl_transfer(0xc0, 0x29, 0x0600, 0x0000, 2)  # => 7373
        ret = self.dev.ctrl_transfer(0xc0, 0x29, 0x0200, 0x0000, 2)  # => 0000
        self.dev.ctrl_transfer(0x02, 0x01, 0x0000, 0x0082)     # =>    0
        self.dev.ctrl_transfer(0x40, 0x27, 0x0000, 0x0000)     # =>    0


    @property
    def GetButtons(self):
        """Return current Button/Dial values
        """
        try:
            ret = self.dev.read(0x81, 64)
            print "Buttons: ", ret
        except usb.core.USBError:       # read could throw a timeout exception. Ignore that.
            pass

        return ret

    def ClearButtons(self):
        """Turn all button LEDs off
        """
        #print "ClearButtons"
        self.dev.ctrl_transfer(0x40, 0x2d, 0x0000, 0x0000)
        self.dev.ctrl_transfer(0x40, 0x2e, 0x0000, 0x0000)
        self.dev.ctrl_transfer(0x40, 0x2f, 0x0000, 0x0000)
        self.dev.ctrl_transfer(0x40, 0x30, 0x0000, 0x0000)
        self.dev.ctrl_transfer(0x40, 0x31, 0x0000, 0x0000)

    def SetButtons(self):
        """Set Button LEDs
        Currently sends random values.
        Some values let buttons blink.
        """
        #print "SetButtons"
        bval = 1 << randint(0, 31) | 1 << randint(0, 31)
        self.dev.ctrl_transfer(0x40, 0x2d, bval, 0x0000)
        bval = 1 << randint(0, 31) | 1 << randint(0, 31)
        self.dev.ctrl_transfer(0x40, 0x2e, bval, 0x0000)
        bval = 1 << randint(0, 31) | 1 << randint(0, 31)
        self.dev.ctrl_transfer(0x40, 0x2f, bval, 0x0000)
        bval = 1 << randint(0, 31) | 1 << randint(0, 31)
        self.dev.ctrl_transfer(0x40, 0x30, bval, 0x0000)
        bval = 1 << randint(0, 31) | 1 << randint(0, 31)
        self.dev.ctrl_transfer(0x40, 0x31, bval, 0x0000)

djc = djcontrol()
while True:
    djc.SetButtons()
    time.sleep(0.2)
    djc.ClearButtons()
    time.sleep(0.2)