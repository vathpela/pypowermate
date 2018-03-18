#!/usr/bin/python3

""" This reads from the powermate's input and runs programs as a result """

# pylint: disable=fixme

# XXX: this will eventually become a daemon in C

import errno
import os
import sys
import select
import math
import time
import itertools
import evdev
import pyudev

class UdevMonitor:
    """ Listen for new devices """
    def __init__(self):
        super().__init__()
        self.ctx = pyudev.Context()
        self.monitor = pyudev.Monitor.from_netlink(self.ctx)
        self.monitor.filter_by('input')
        self.monitor.start()

    def fileno(self):
        """ return the fileno for select """
        return self.monitor.fileno()

    def new_devices(self):
        """ handle a new device """

        while True:
            device = self.monitor.poll(0)
            if not device:
                break
            if device['ACTION'] != 'add':
                continue
            if 'DEVNAME' not in device:
                continue
            if 'ID_USB_DRIVER' not in device:
                continue
            if 'DEVLINKS' not in device:
                continue
            if device['ID_USB_DRIVER'] == 'powermate':
                yield device

class PowerMate:
    """ Listen for an input event and do stuff """
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.device = evdev.InputDevice("/dev/%s" % (name,))
        self.last = None
        self.debug = False
        print("new device %s" % (name,))

    def fileno(self):
        """ return the fileno for select """
        return self.device.fileno()

    def save_last(self, event):
        """ maintain our state """
        self.last = (event.code, event.type, event.value)

    def read(self):
        """ handle a new event """
        try:
            for event in self.device.read():
                self.handle_event(event)
        except OSError as error:
            if error.errno == errno.ENODEV:
                return True
            else:
                raise
        return False

    def left(self, event):
        """ what to do if it's left """
        os.system("powermate %s left %s" % (self.name, event.value))

    def right(self, event):
        """ what to do if it's right """
        os.system("powermate %s right %s" % (self.name, event.value))

    def button(self, event):
        """ what to do if it's button """
        os.system("powermate %s button %s" % (self.name, event.value))

    def handle_event(self, event):
        """ handle one event """

        # skip null events, these are just noise
        if event.code == 0 and event.type == 0 and event.value == 0:
            return

        # if the current event matches the most recent event, skip
        #if event.type == self.last_type and \
        #   event.code == self.last_code and \
        #   event.value == self.last_value:
        if (event.code, event.type, event.value) == self.last:
            if self.debug:
                print("skipping %s event: type %s code %s value %s" % (
                    self.name, event.type, event.code, event.value))
            return

        # take action
        if event.type == 2 and event.code == 7 and event.value != 0:
            # knob turned
            if event.value < 0:
                # left
                self.left(event)
            elif event.value > 0:
                # right
                self.right(event)
        elif event.type == 1 and event.code == 256:
            # pressed
            self.button(event)
        else:
            if self.debug:
                print("powermate %s event: type %s code %s value %s" % (
                    self.name, event.type, event.code, event.value))
        self.save_last(event)

    # pylint: disable=too-many-arguments
    def set_led_pulse(self, brightness=255, speed=255, pulse_table=0,
                      pulse_while_asleep=False, pulse_while_awake=True):
        """ Encode the pulse parameters:
            brightness: 0 to 255
            speed: 0 to 510, slower to faster, log scale, sortof.
                255 = 2s ("normal")
              So basically: 251=8s, 252=6s, 253=4s, 254=2.5s, 255=2s
              /ish/.  I timed those values with a stopwatch, so...
            pulse_table: 0, 1, 2 (dunno)
            pulse_while_asleep: boolean
            pulse_while_awake: boolean
        """

        if brightness < 0 or brightness > 255:
            raise ValueError("brightness (%s) must be 0 through 255" %
                             (brightness,))

        if speed < 0 or speed > 510:
            raise ValueError("speed (%s) must be 0 through 510" % (speed,))

        if pulse_table < 0 or pulse_table > 2:
            raise ValueError("pulse table (%s) must be 0, 1, or 2" %
                             (pulse_table,))

        pulse_while_awake = int(bool(pulse_while_awake))
        pulse_while_asleep = int(bool(pulse_while_asleep))

        value = (pulse_while_awake << 20) \
                | (pulse_while_asleep << 19) \
                | (pulse_table << 17) \
                | (speed << 8) \
                | brightness

        mod, sec = math.modf(time.time())
        sec = int(sec)
        usec = int(mod * 1000000)
        event = evdev.InputEvent(sec=sec, usec=usec, type=evdev.ecodes.EV_MSC,
                                 code=evdev.ecodes.MSC_PULSELED, value=value)
        self.device.write_event(event)

class PowerMateDispatcher:
    """ A dispatcher for our devices """
    def __init__(self, PowerMateClass=PowerMate, UdevMonitorClass=UdevMonitor,
                 pulsegen=None):
        super().__init__()
        self._powermate_class = PowerMateClass
        self.powermates = {}
        if pulsegen is None:
            self.pulsegen = itertools.cycle(iter([254, 260, 255, 261, 256, 262, 257, 263, 258]))
        else:
            self.pulsegen = itertools.cycle(iter(pulsegen))

        self.udev = UdevMonitorClass()
        if hasattr(self.udev, 'fileno'):
            self.udev_fileno = self.udev.fileno()
        else:
            self.udev_fileno = None

        for dev in filter(lambda x: x.startswith("powermate"),
                          os.listdir("/dev/")):
            powermate = self._powermate_class(dev)
            powermate.set_led_pulse(speed=next(self.pulsegen),
                                    pulse_while_asleep=True,
                                    pulse_while_awake=True)
            self.powermates[powermate.fileno()] = powermate

    def new_powermate(self, device):
        """ This gets called when we get a new powermate """
        if not device:
            return
        for devlink in device['DEVLINKS'].split(' '):
            if devlink.startswith('/dev/powermate'):
                powermate = self._powermate_class(devlink[5:])
                powermate.set_led_pulse(speed=next(self.pulsegen),
                                        pulse_while_asleep=True,
                                        pulse_while_awake=True)
                self.powermates[powermate.fileno()] = powermate
                break

    @property
    def filenos(self):
        """ the filenos for select """
        ret = list(self.powermates)
        if self.udev_fileno is not None:
            ret += [self.udev_fileno]
        return ret

    def handle_read(self, fileno):
        """ handle the read from one of our filenos """
        if fileno == self.udev_fileno:
            for device in self.udev.new_devices():
                self.new_powermate(device)
        elif fileno in self.powermates:
            powermate = self.powermates[fileno]
            if powermate.read():
                del self.powermates[fileno]
        else:
            raise ValueError(fileno)

    def run(self):
        """ this is our loop... """
        args = []
        while self.powermates:
            reads, _, _ = select.select(self.filenos, [], [], *args)
            if reads:
                args = [0.1]
                for fileno in reads:
                    self.handle_read(fileno)
            else:
                for powermate in self.powermates.values():
                    powermate.last = None
                args = []

if __name__ == "__main__":
    DISPATCHER = PowerMateDispatcher()

    # If we can figure out how to add them on hotplug, we won't need this.
    if not DISPATCHER.powermates:
        sys.exit(0)

    DISPATCHER.run()

__all__ = ['PowerMateDispatcher', 'PowerMate', 'UdevMonitor']
