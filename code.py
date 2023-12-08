import board

import keypad
import digitalio
import pulseio


import usb_midi
import adafruit_midi

from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
from adafruit_midi.control_change import ControlChange
from adafruit_midi.pitch_bend import PitchBend
from adafruit_midi.midi_message import note_parser

import time
import math

from types import MethodType




#this is the custom module
from instruments import *









#First prototype completed 20/11/2023
print("Telephony. Theremin.")


#set up midi, just watch for helper function file
midi = adafruit_midi.MIDI(midi_out=usb_midi.ports[1], out_channel=0)


theremin = Instrument("theremin", midi)


theremin.sensors = [DistanceSensor(board.GP21, board.GP22)]
theremin.buttons = [ButtonGroup([board.GP10, board.GP11, board.GP12])]






def alter_state_b0(self):
    state = self.keys_state
    sensor = theremin.sensors[0]

    #we know that we have three buttons, because this is the part where we get specific

    match state:
        case [1,0,0]:
            sensor.pause()
        case [1,1,0]:
            sensor.tune_upper()
        case [1,0,1]:
            sensor.tune_lower()
        case [0,1,0]:
            sensor.toggle_notes()
        case [0,0,1]:
            sensor.toggle_cchange()
        case [0,1,1]:
            sensor.tune_ceil()



theremin.buttons[0].alter_state = MethodType(alter_state_b0, theremin.buttons[0])


theremin.init_event_collector()



while True:
    theremin.tick()
    time.sleep(0.08)






