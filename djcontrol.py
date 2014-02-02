#!env python

import usb.core
import usb.util
import time
from random import randint
import sys
import pprint

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
#   * Shift-Buttons do several things:
#       1. act as buttons, i.e. toggle a bit when currently pushed
#       2. act as switch, i.e. toggle a bit on each push (indicated by the yellow shift-LED)
#       3. change the meanings of Buttons N1..N4 to N5..N8
#          When shift-state is changed, a pushed N1 becomes a pushed N5; N1 is released.
#          When shift-state is changed, LEDs of N1..N4 display the LED-State of N5..N8

# Retrieve Device State
#   Device state is sent as block of 38 bytes.
#   Encoded in this block are:
#     - Button state as Bits (0: depressed, 1: pushed)
#     - Shift state as two Bits; 1 Bit for the button itself; 1 Bit for the shift state
#     - Sliders, Dials: 8 bits; range: 0x00 to 0xff
#     - Jog-Dials, Rotary encoders: 8 bits; range: 0x00 to 0xff with wrap-around (0xfe->0xff->0x00->0x01...)
#
#
# List of controls:
#   convention for location in memory block:
#       (byte, bitmask) - byte: 00-37 (decimal)
#
#   * Buttons;
#       Buttons that exist twice, once for Deck A, once for Deck B:
#       - (04, 0x80) PitchReset_A
#       - (00, 0x02) PitchBendMinus_A
#       - (00, 0x04) PitchBendPlus_A
#       - (04, 0x20) Sync_A
#       - (00, 0x01) Shift_A
#       - (03, 0x10) + (20, 0x01) Shifted_A (indicates shift state)
#       - (04, 0x40) N1_A; (05, 0x01) N5_A
#       - (00, 0x10) N2_A; (05, 0x02) N6_A
#       - (00, 0x20) N3_A; (05, 0x04) N7_A
#       - (00, 0x40) N4_A; (05, 0x08) N8_A
#       - (00, 0x08) RWD_A
#       - (00, 0x80) FWD_A
#       - (01, 0x02) CUE_A
#       - (01, 0x04) Play_A
#       - (01, 0x01) Listen_A
#       - (01, 0x08) Load_A
#       - (04, 0x02) PitchReset_B
#       - (03, 0x02) PitchBendMinus_B
#       - (03, 0x04) PitchBendPlus_B
#       - (04, 0x08) Sync_B
#       - (03, 0x01) Shift_B
#       - (03, 0x20) + (20, 0x40) Shifted_B (indicates shift state)
#       - (04, 0x04) N1_B, (05, 0x10) N5_B
#       - (02, 0x10) N2_B, (05, 0x20) N6_B
#       - (02, 0x20) N3_B, (05, 0x40) N7_B
#       - (02, 0x40) N4_B, (05, 0x80) N8_B
#       - (03, 0x08) RWD_B
#       - (02, 0x80) FWD_B
#       - (02, 0x02) CUE_B
#       - (02, 0x04) Play_B
#       - (02, 0x01) Listen_B
#       - (02, 0x08) Load_B
#       Buttons that exist once:
#       - (04, 0x10) Vinyl
#       - (04, 0x01) Magic
#       - (01, 0x10) Up
#       - (01, 0x80) Down
#       - (01, 0x20) Folders
#       - (01, 0x40) Files
#
#   * Dials and sliders, range 0x00 to 0xff
#       - (07) Treble_A
#       - (08) Medium_A
#       - (09) Bass_A
#       - (06) Vol_A
#       - (12) Treble_B
#       - (13) Medium_B
#       - (14) Bass_B
#       - (11) Vol_B
#       - (10) XFader (0x00=A; 0x7f=middle; 0xff=B)
#
#   * Jog-Dials, rotary encoders, range 0x00 to 0xff with wrap-around
#       - (15) Jog_A
#       - (17) Pitch_A
#       - (16) Jog_B
#       - (18) Pitch_B

# List of Controls by memory location;
# Bitwise use; left-to-right; MSB-to-LSB; unused bits are indicated by []
#      0x80            0x40        0x20         0x10        |  0x08     0x04              0x02               0x01
# 00 - [FWD_A]         [N4_A]      [N3_A]       [N2_A]      |  [RWD_A]  [PitchBendPlus_A] [PitchBendMinus_A] [Shift_A]
# 01 - [Down]          [Files]     [Folders]    [Up]        |  [Load_A] [Play_A]          [CUE_A]            [Listen_A]
# 02 - [FWD_B]         [N4_B]      [N3_B]       [N2_B]      |  [Load_B] [Play_B]          [CUE_B]            [Listen_B]
# 03 - []              []          [Shifted_B]  [Shifted_A] |  [RWD_B]  [PitchBendPlus_B] [PitchBendMinus_B] [Shift_B]
# 04 - [PitchReset_A]  [N1_A]      [Sync_A]     [Vinyl]     |  [Sync_B] [N1_B]            [PitchReset_B]     [Magic]
# 05 - [N8_B]          [N7_B]      [N6_B]       [N5_B]      |  [N8_A]   [N7_A]            [N6_A]             [N5_A]
# 06 - Vol_A
# 07 - Treble_A
# 08 - Medium_A
# 09 - Bass_A
# 10 - XFader
# 11 - Vol_B
# 12 - Treble_B
# 13 - Medium_B
# 14 - Bass_B
# 15 - Jog_A
# 16 - Jog_B
# 17 - Pitch_A
# 18 - Pitch_B
# 19 - (not used)
# 20 - []              [Shifted_B] []           []          |  []       []                []                 [Shifted_A]
# 21 - (not used)
# 22 - (not used)
# 23 - (not used)
# 24 - (not used)
# 25 - (not used)
# 26 - (not used)
# 27 - (not used)
# 28 - (not used)
# 29 - (not used)
# 30 - (not used)
# 31 - (not used)
# 32 - (not used)
# 33 - (not used)
# 34 - (not used)
# 35 - (not used)
# 36 - (not used)
# 37 - sequence number; incremented by 1 on each update

# LEDs; Value1:
# block/bit key
# 0/01 N2_A
# 0/02 Listen_A
# 0/03 Magic
# 0/04 Listen_B
# 0/05 N2_B
# 0/08 PitchReset_A
# 0/09 N1_A
# 0/10 Sync_A
# 0/11 Vinyl
# 0/12 Sync_B
# 0/13 N1_B
# 0/14 PitchReset_B
# 1/00 PitchBendPlus_A
# 1/01 N4_A
# 1/02 Play_A
# 1/03 Files
# 1/04 Play_B
# 1/05 N4_B
# 1/06 PitchBendPlus_B
# 1/08 PitchBendMinus_A
# 1/09 N3_A
# 1/10 CUE_A
# 1/11 Folders
# 1/12 CUE_B
# 1/13 N3_B
# 1/14 PitchBendMinus_B
# 2/08 N5_A
# 2/09 N6_A
# 2/10 N7_A
# 2/11 N8_A
# 2/12 N5_B
# 2/13 N6_B
# 2/14 N7_B
# 2/15 N8_B

# Blink
# 2/00 PitchReset_A
# 2/01 N1_A
# 2/02 Sync_A
# 2/03 Vinyl
# 2/04 Sync_B
# 2/05 N1_B
# 2/06 PitchReset_B
# 3/00 PitchBendMinus_A
# 3/01 N3_A
# 3/02 CUE_A
# 3/03 Folders
# 3/04 CUE_B
# 3/05 N3_B
# 3/06 PitchBendMinus_B
# 3/09 N2_A
# 3/10 Listen_A
# 3/11 Magic
# 3/12 Listen_B
# 3/13 N2_B
# 4/00 N5_A
# 4/01 N6_A
# 4/02 N7_A
# 4/03 N8_A
# 4/04 N5_B
# 4/05 N6_B
# 4/06 N7_B
# 4/07 N8_B
# 4/08 PitchBendPlus_A
# 4/09 N4_A
# 4/10 Play_A
# 4/11 Files
# 4/12 Play_B
# 4/13 N4_B
# 4/14 PitchBendPlus_B

# Store control map:
# Controls are stored in a list
# Each control has its own entry
# Each entry has a number of properties:
#   * Name;         terse, for referring to the control
#   * Location;     number of byte where the Value of the control is stored
#   * Bitmask;      Applied to byte, mask different buttons from byte
#   * type;         0: button; 1: slider/dial; 2: jog-wheel
#                   button:         Value 0 or 1  (absolute value)
#                   slider/dial:    Value 0..255  (absolute value)
#                   jog-wheel:      Value 0..255  (absolute value)
#                                   TODO: Value -127..+127 (difference from previous value)
#


class controls:
    """ keeps list of controls and their current values
    """
    control_map = []    # list of all controls
    curr_values = []    # list of current  control state
    prev_values = []    # list of previous control state

    def __init__(self):
        pass

    def loadConfig(self, filename):
        """ Load control layout from config file.
        """
        with open(filename) as f:
            counter = 0
            for line in f:
                line = line.strip()
                values = line.split(";")
                if (len(values) == 4) and (not line.startswith("#")):
                    name    = values[0]
                    loc     = values[1]
                    bitmask = values[2]
                    type    = values[3]

                    #print "[DEBUG]: %s/%s/%s/%s" % (name, loc, bitmask, type)
                    curr_control = {
                        "num"  : counter,
                        "name" : name,
                        "loc"  : loc,
                        "mask" : bitmask,
                        "type" : type
                    }
                    self.control_map.append(curr_control)
                    counter += 1

        # initialize self.curr_values to length of control list
        self.curr_values = [None] * len(self.control_map)

        # [DEBUG]
        #pp = pprint.PrettyPrinter(indent=2)
        #pp.pprint(self.control_map)



    def readControls(self, state):
        """ reads control states from argument state; compares with previous values.
        """
        # Procedure:    copy self.curr_values to self.prev_values;
        #               iterate over self.control_map;
        #               Test each entry in state;
        #               Update self.curr_values

        # still current values are old soon
        self.prev_values = list(self.curr_values)

        # iterate over control_map; copy each control to curr_values
        counter = 0
        for control in self.control_map:
            loc = int(control['loc'], 0)
            mask = int(control['mask'], 0)
            type = int(control['type'])
            #print "loc/mask: %s/%s" % (loc, mask)
            curr_value = state[loc] & mask
            if type == 0:    # button
                self.curr_values[counter] = int(curr_value > 0)
            else:  # slider/dial or jog-dial; No difference in treatment, yet
                self.curr_values[counter] = curr_value
            counter += 1

        # [DEBUG]
        #pp = pprint.PrettyPrinter(indent=2)
        #pp.pprint(self.curr_values)



    def listChanges(self):
        """ Returns list of controls that changed between last two readings.
        """
        diff = []
        for counter in range(len(self.curr_values)):
            if self.curr_values[counter] != self.prev_values[counter]:
                diff.append(counter)

        return(diff)

class djcontrol:
    curr_state = []     # most recent button state read from the device
    prev_state = []     # previously read button state; Used to calculate differences

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


    def GetButtons(self):
        """Return current Button/Dial values
        """
        try:
            self.prev_state = self.curr_state           # store last known button state
            self.curr_state = self.dev.read(0x81, 38)   # device status takes 38 bytes.
        except usb.core.USBError:                       # read could throw a timeout exception. Ignore that.
            pass

        return self.curr_state

    def ShowButtons(self):
        """Get Button state, print values as binary. Intended for debugging
        """
        print "------------"    # separator after block for your viewing pleasure
        self.GetButtons()
        i = 0
        for num in self.curr_state:
            print "%02d: (%s) %s" % (i, hex(num), bin(num))
            i += 1



    def ClearButtons(self):
        """Turn all button LEDs off
        """
        self.dev.ctrl_transfer(0x40, 0x2d, 0x0000, 0x0000)
        self.dev.ctrl_transfer(0x40, 0x2e, 0x0000, 0x0000)
        self.dev.ctrl_transfer(0x40, 0x2f, 0x0000, 0x0000)
        self.dev.ctrl_transfer(0x40, 0x30, 0x0000, 0x0000)
        self.dev.ctrl_transfer(0x40, 0x31, 0x0000, 0x0000)

    def SetButtons(self, block, value):
        """Set Button LEDs
        block is number of segment to send; valid values: 0..4
        value is numeric value to write into block; Valid value: 32bit integer
        """
        if block == 0:
            self.dev.ctrl_transfer(0x40, 0x2d, value, 0x0000)
        if block == 1:
            self.dev.ctrl_transfer(0x40, 0x2e, value, 0x0000)
        if block == 2:
            self.dev.ctrl_transfer(0x40, 0x2f, value, 0x0000)
        if block == 3:
            self.dev.ctrl_transfer(0x40, 0x30, value, 0x0000)
        if block == 4:
            self.dev.ctrl_transfer(0x40, 0x31, value, 0x0000)


# create an instance of the controller interface
djc = djcontrol()

# create controls
con = controls()
con.loadConfig("hercules_djcontrol_mp3_le.conf")

djc.ClearButtons()
while True:
    con.readControls(djc.GetButtons())
    ch = con.listChanges()
    for curr_control in ch:
        value = con.curr_values[curr_control]
        if value > 1:
            value = value/2 * '#'
        print("%s: %s" % (con.control_map[curr_control]['name'], value))
    time.sleep(0.01)



