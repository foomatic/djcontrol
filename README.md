djcontrol
=========

Interface to "Hercules DJControl MP3 LE" using Python and libUSB intended to run on Linux.

Talks to the device with USB vid:pid 06f8:b105

Current status:
- Initialize controller
- Receive button status
- Set button LEDs
- Values of the individual controls have been documented
- Controls are defined in a config file
- Changes to a control are identified

Not Working (yet)
- Control LED by name; Location of the LEDs has been documented but no control method has been written, yet.
- Interfacing to the rest of the system.


Possible Interfaces
- stdin/stdout
- call external command
- MIDI (act as ALSA Midi-device)
- HTTP-Server + JSON
- ...


