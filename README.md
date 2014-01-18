djcontrol
=========

Interface to "Hercules DJControl MP3 LE" using Python and libUSB

Talks to the device with USB vid:pid 06f8:b105

Current status:
    * Initialize controller
    * Receive button status
    * Set button LEDs

Not working (yet);
    * Identify which particular button is pressed. 
      Currently we receive 64 bytes describing all buttons and dials
    * Identify individual LEDs.
      Currently we send 10 bytes of data to control the LEDs,
      but don't know which bit sets which LED.
    * Interfacing to the rest of the system.
      Possible Methods:
        * stdin/stdout
        * MIDI (act as ALSA Midi-device)
        * HTTP-Server + JSON
        * ...


