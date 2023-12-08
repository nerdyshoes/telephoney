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



class Instrument():
    def __init__(self, name, midi_object):
        self.name = name
        self.midi = midi_object

        self.buttons = None
        self.sensors = None
        self.leds = None

        self.event_collector = None

    #if component event is of a "change" type, then change the parameters of another component
    #all info should be in change event, including any methods, with direct references to the changing component

    def init_event_collector(self):
        components = self.buttons + self.sensors
        self.event_collector = Event_Collector(components)



    def tick(self):
        #main function of instrument, goes inside the main loop of the program

        #get the events, do something with them

        events = self.event_collector.get()

        note_on = []
        note_off = []
        new_cchange = []


        for event in events:
            #decode what the event actually wants to do
            #I would like to have the midii send shit as part of the instrument class
            #event would be as high level as possible, it should have fuck all logic
            #e.g. it should contain what midi note to play at what velocity, not disstance info

            if event.note_on:
                note_on += event.note_on

            if event.note_off:
                note_off += event.note_off

            if event.new_cchange:
                new_cchange += event.new_cchange

            event.alter_state() #calls function that can alter the state of something else

        self.midi.send(note_on + note_off + new_cchange)


class DistanceSensor():
    def __init__(self, trigger_pin, echo_pin, lower_bound=5, upper_bound=30, ceil_height=180, notes=[[]], cchange=[], notes_on=True, cchange_on=True):
        #i need to have several parameters that can be accessed and changed by other classes
        #pause, tune, play notes, play CC, ceiling detector are the main ones
        #maybe these could be methods that are called?

        self.trigger_pin = digitalio.DigitalInOut(trigger_pin)
        self.trigger_pin.direction = digitalio.Direction.OUTPUT
        self.echo = pulseio.PulseIn(echo_pin, maxlen=1)

        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.ceil_height = ceil_height

        self.notes_on = notes_on
        self.cchange_on = cchange_on

        self.notes = notes
        self.cchange = cchange


        #some way to save the current state of the system
        #current note, current cc is i think all the necessary info

        self.current_notes = None
        self.current_cchange = None

        self.semitone_shift = 0


        self.event = None

    def measure(self):
        #measures the distance with the sensor, and returns in cm

        self.trigger_pin.value = True
        time.sleep(10**(-5))
        self.trigger_pin.value = False
        
        # Measure the duration of the echo pulse
        
        if len(self.echo) == 0:
            #ensure we don't get an error
            #print("0cm")
            return 0
        else:
            self.echo.pause()

            #conversion from microseconds to cm
            distance = self.echo[0]/10**6*340/2*100
            #print(f"{distance}cm")
            
            self.echo.resume()
            return distance

    def note_map(self, distance):
        if distance > self.ceil_height:
            distance = self.ceil_height
        
        difference = self.upper_bound - self.lower_bound

        notes_per_octave = len(self.notes)


        #first figure out octave shift
        octave_change = (distance - self.lower_bound) // difference
        remainder = (distance - self.lower_bound) % difference #in cm

        note_index = math.floor(remainder / difference * notes_per_octave)

        #notes should be a list of lists of notes, one list for each set of notes being played
        
        current_notes = [(int(note_parser(note[0]) + octave_change*12 + self.semitone_shift), note[1]) for note in self.notes[note_index]]

        for notes in current_notes:
            for note in notes:
                if note[0] > 127:
                    note[0] = 127
                elif note[0] < 0:
                    note[0] = 0

        return current_notes
        

    def cchange_map(self, distance):
        if distance < self.lower_bound:
            return [(cc[0],0) for cc in self.cchange]
        elif distance > self.upper_bound:
            return [(cc[0], 127) for cc in self.cchange]
        
        #number between 0 and 1 determining how far along the hand is
        #setting that to closest integer between 0 and 127
        percentage_distance = (distance - self.lower_bound)/(self.upper_bound - self.lower_bound)
        value = round(percentage_distance * 127)

        return [(cc[0], value) for cc in self.cchange]


    def tune_lower(self):
        #this method is triggered by a physical button, and finds a new value for the lower bound
        distance = self.measure()
        self.lower_bound = distance

    def tune_upper(self):
        distance = self.measure()
        self.upper_bound = distance

    def tune_ceil(self):
        distance = self.measure()
        self.ceil_height = distance


    def toggle_notes(self):
        #if pressed, toggle notes_on
        self.notes_on = not self.notes_on

    def toggle_cchange(self):
        self.cchange_on = not self.cchange_on

    def pause(self):
        pass


    def alter_state(self):
        #will be defined (if neccessary right after DistanceSensor object created)
        return None

    def get_event(self):
        #provide a list of things that have been change since the last "tick"
        #what notes must be sent, which must be stopped etc
        #done by refreshing everything and comparing these values to the previous (self.current_notes)
        distance = self.measure()
        new_notes = self.note_map(distance)
        new_cchange = self.cchange_map(distance)

        note_on, note_off, similar_notes = note_list_comparison(new_notes, self.current_notes)

        self.current_notes = new_notes
        self.current_cchange = new_cchange

        self.event = Event(note_on=note_on, note_off=note_off, new_cchange=self.current_cchange)
        self.event.alter_state = MethodType(self.alter_state, self.event)   #calls some function that would alter the state of something else in the system
        
        return self.event



class ButtonGroup():
    def __init__(self, pin_list):
        self.keys = keypad.keys(tuple(pin_list), value_when_pressed=True, pull=True)    #this is circuitpython keypad object

        self.event = None

        self.keys_state = [False]*len(pin_list)

    
    def alter_state(self):
        pass

    def get_event(self):
        kp_event = self.keys.events.get()
        if not kp_event:
            #nothing happened so return an empty event
            self.event = Event()
            return self.event
        
        self.keys_state[kp_event.key_number] = kp_event.pressed

        self.event = Event()
        self.event.alter_state = MethodType(self.alter_state, self.event)

        return self.event
        

        



class Event():
    def __init__(self, note_on=[], note_off=[], new_cchange=[]):
        #several properties
        self.id = None

        self.note_on = [NoteOn(note[0], note[1]) for note in note_on]
        self.note_off = [NoteOff(note[0]) for note in note_off]
        self.new_cchange = [ControlChange(cc[0], cc[1]) for cc in new_cchange]

    def alter_state(self):
        #placeholder, will be defined just after Event is initialised
        return None
    

            
class Event_Collector():
    def __init__(self, components):
        self.components = components

    def get(self):
        events_list = []
        for component in self.components:
            events_list += component.get_event()
            #must ensure that events are not repeated on the component level
            #each item in the list is some object with a lot of info in it
            #these events should be able to trigger things in the instrument object

        return events_list
    

def note_list_comparison(list1, list2):
    #two lists filled with midi "objects" (just the note tuples)
    #returns a list of similar ones, and a list of different ones

    similar = []
    note_on = []
    note_off = []

    for note in list1:
        if note in list2:
            similar += note
        else:
            note_off += note

    for note in list2:
        if note not in list1:
            note_on += note

    return note_on, note_off, similar
