"""Event and input handling.

This module consists of :class:`EventHandler`, which is used to assign
callbacks to events and keypresses.

---NODOC---

 - input recording and playback would be good
 - joy axes as buttons: direction, threshold

 - Event(*evts)
    - evts is one or more pg.Events
    - call cbs at most once per frame
    - has .cb(cb, *args, **kwargs) - can do multiple times
        - returns self, so can pass Event(...).cb(...) to EventHandler.add
     - cbs get Event (but use function.func_code.co_{varnames,argcount} to check if takes any, and only then pass it)
 - Button(type, device, btn, *mods)
    - go to .type (kb, mouse, joy), .device (ie. joy number), .btn (key/btn id)
    - key(btn, *mods), mouse(btn, *mods), joy(device, btn, *mods) return Button
    - mods are zero or more Buttons or Button argument tuples
    - mods taken by key, mouse, joy may be key/mouse/joy argument tuples
 - ButtonEvent(*btns, evt = down), Event subclass
    - buttons are Buttons or Button argument tuples
    - evt is bitwise or of one or more of down, up, held
    - has .held_delay = 1 (>= 0), .held_repeat_delay = 1 (> 0)
    - key_event, mouse_event, joy_event return ButtonEvent and use key, mouse, joy instead of Button (but can take Buttons too)
    - when call cb, set self.evt to one of down, held, up
    - calls cbs at most once per frame per evt type
 - can register new button types
    - a function of the module
    - need: name; pg event type and how to get device, btn from it for each of
      down/up
    - creates functions like key, mouse, joy and key_event, mouse_event,
      joy_event in the module
 - EventHandler.add(*evts), .rm(*evts), each arg an Event
 - ControlScheme
    - stores a number of schemes, without identifying devices in buttons
    - schemes have string identifiers and priorities
    - schemes are {action: ButtonEvent-like}
    - has attr that determines device types that allow sharing
        - defaults to {kb: True, None: False}, None the default
    - .generate(n_players) chooses schemes to use for n_players if possible
        - according to priorities
        - returns [(scheme_id: [(type, device)])] for devices it uses for each
          player
    - .register(EventHandler, schemes) adds buttons to handler
        - schemes are as returned by .generate
    - .unregister(EventHandler)

---NODOC---

"""

# TODO:
# - match keys by event.unicode
# - ability to remove event/key/default handlers
# - joystick stuff

import sys

import pygame

MODE_HELD = 0 #: The key is currently being held down.
MODE_ONPRESS = 1 #: The key was pressed or released since the last check.
#: As ``MODE_ONPRESS``, but call the callback repeatedly when held down for
#: some time.
MODE_ONPRESS_REPEAT = 2
MODE_ONDOWN = 3 #: The key was pressed since the last check.
#: As ``MODE_ONDOWN``, but call the callback repeatedly when held down for some
#: time.
MODE_ONDOWN_REPEAT = 4


def _quit (event):
    pygame.quit()
    sys.exit()


class EventHandler (object):
    """Assign callbacks to events and keypresses.

EventHandler(event_handlers = {}, key_handlers = [], suppress_quit = False
             [, quit_handler][, default_cbs], ignore_locks = True)

:arg event_handlers: ``{event.type: callbacks}`` dict.
:arg key_handlers: list of ``(keys, callbacks, mode)`` tuples, where:

    - ``keys`` is a list of ``(key_ID, mods, exact)`` tuples or ``key_ID``
      ints, where:

        - ``key_ID`` is as used in Pygame.
        - ``mods`` is a modifier bitmask or list of modifier bitmasks to match
          as well.  'Matching' a bitmask is having any key it 'contains'
          pressed; passing a list does an AND-type comparison, where we check
          for a match against every bitmask in the list.
        - ``exact`` is a bool, determining whether to match the modifiers
          exactly (otherwise, it's a match if other modifiers are held as
          well).

      Passing a ``key_ID`` is like passing ``(key_ID, 0, False)``.
    - ``mode`` is one of the ``MODE_*`` constants defined in this module.
      ``*_REPEAT`` modes require two more arguments in each tuple, both
      integers greater than ``0``:

        - ``initial_delay``, the number of frames the key must be held down for
          until it starts repeating.
        - ``repeat_delay``, the number of frames between repeats.

      Frames, here, are the number of calls to ``EventHandler.update``.

:arg suppress_quit: don't exit (call ``quit_handler``) on a ``pygame.QUIT``
                    event.
:arg quit_handler: handler to attach to ``pygame.QUIT`` events; if not given,
                   calls ``pygame.quit`` and ``sys.exit``.
:arg default_cbs: ``callbacks`` to call for events with no registered event
                  handlers.
:arg ignore_locks: whether to ignore num lock and caps lock when matching
                   modifiers for key handlers with exact = True.

In all cases, ``callbacks`` is a list of ``(callback, args)`` tuples, where
``args`` is a list of arguments to pass to the callback (after any compulsory
arguments).  ``(callback, args)`` can be reduced to ``callback`` if ``args`` is
empty, and the whole list can be reduced to just a callback if there's only one
and its ``args`` list is empty.

Event callbacks (includes those in ``default_cbs``) take the
``pygame.event.Event`` as an argument.

Key callbacks take three arguments:

* ``key_ID`` or the ``(key_ID, mods, exact)`` tuple as passed.
* the type of key event: :const:`-1` if the key is being held down, :const:`0`
  if it was pressed, :const:`1` if released, :const:`2` if this is a repeat
  call (simulated keypress).  (This means that for some modes, this argument is
  always the same.)
* the key modifiers being held at the time of the keypress/release/currently.
  (This is a bitmask that can be compared to the ``pygame.KMOD_*`` constants.)

Note that the callbacks associated with any given key are not called more than
once per frame, even if the key is pressed more than once in the last frame
(could happen with a mode other than ``MODE_HELD``).

"""

    def __init__ (self, event_handlers = {}, key_handlers = [],
                  suppress_quit = False, quit_handler = _quit,
                  default_cbs = None, ignore_locks = True):
        #: (event.type: callbacks) dict of registered event handlers.
        self.event_handlers = {}
        self.add_event_handlers(event_handlers)
        #: (keycode: data) dict of registered key handlers, where data is a
        #: (key_data: callbacks) dict and key_data is keycode or
        #: (keycode, mods, exact) as given.
        self.key_handlers = {}
        self._keys_handled = [set(), set(), set(), set(), set()]
        self.add_key_handlers(key_handlers)
        #: Callbacks for unhandled events.
        self.default_cbs = []
        if default_cbs is not None:
            self.add_default_cbs(default_cbs)
        if not suppress_quit:
            self.add_event_handlers({pygame.QUIT: quit_handler})
        self._ignore_locks = ignore_locks
        #: Keys pressed between the last two calls to update.
        self.keys_down = set()
        #: Keys released between the last two calls to update.
        self.keys_up = set()
        #: Keys held down at the time of the last call to update.
        self.keys_pressed = set()
        #: The return value from pygame.key.get_mods at the time of the last
        #: call to update.
        self.key_mods = 0
        self.repeat_count = {}
        self.events_active = True #: Whether event handlers are called.
        self.keys_active = True #: Whether key handlers are called.
        self.defaults_active = True #: Whether default handlers are called.

    def _clean_cbs (self, cbs):
        # expand shorthand callback arguments
        if hasattr(cbs, '__call__'):
            cbs = [cbs]
        return [(cb, ()) if hasattr(cb, '__call__') else cb for cb in cbs]

    def _call_cbs (self, cbs, *args):
        # call callbacks in list of accepted format
        args = tuple(args)
        for cb, extra_args in cbs:
            extra_args = tuple(extra_args)
            cb(*(args + extra_args))

    def _call_key_cbs (self, cbs, key_data, press_type, current_mods):
        # call key callbacks in list of accepted format if modifiers match
        if isinstance(key_data, int):
            # just got a key ID
            key, mods, exact = (key_data, 0, False)
        else:
            # got (key_ID, mods, exact)
            key, mods, exact = key_data
        # check mods match
        if isinstance(mods, int):
            mods = (mods,)
        mods = set(mods)
        # check all wanted mods are currently pressed
        match = all(mod == 0 or mod & current_mods for mod in mods)
        if exact and match:
            # 'subtracting' mods from current_mods gives 0 if current_mods
            # 'contains' no other mods
            subtract = list(mods)
            if self._ignore_locks:
                subtract += [pygame.KMOD_CAPS, pygame.KMOD_NUM]
            match = current_mods & reduce(int.__or__, subtract)
            match = (current_mods - match) == 0
        if match:
            self._call_cbs(cbs, key_data, press_type, current_mods)

    def _call_all_cbs (self, key, press_type, modes, mods):
        # call all callbacks for a key
        for key_data, cb_data_sets in self.key_handlers[key].iteritems():
            for cb_data in cb_data_sets:
                if cb_data[1] in modes:
                    self._call_key_cbs(cb_data[0], key_data, press_type, mods)

    def add_event_handlers (self, event_handlers):
        """Add more event handlers.

Takes an event_handlers argument in the same form as expected by the
constructor.

"""
        for e, cbs in event_handlers.iteritems():
            cbs = self._clean_cbs(cbs)
            try:
                self.event_handlers[e] += cbs
            except KeyError:
                self.event_handlers[e] = cbs

    def add_key_handlers (self, key_handlers):
        """Add more key handlers.

Takes a key_handlers argument in the same form as expected by the constructor.

"""
        for x in key_handlers:
            keys, cbs, mode = x[:3]
            cbs = self._clean_cbs(cbs)
            args = list(x[3:])
            for data in keys:
                if isinstance(data, int):
                    # just got a key ID
                    k = data
                else:
                    # got (key_ID, mods, exact)
                    k = data[0]
                if k not in self.key_handlers:
                    self.key_handlers[k] = {}
                if data not in self.key_handlers[k]:
                    self.key_handlers[k][data] = [[cbs] + [mode] + args]
                else:
                    self.key_handlers[k][data].append([cbs] + [mode] + args)
                self._keys_handled[mode].add(k)

    def add_default_cbs (self, cbs):
        """Add more default event callbacks.

Takes a cbs argument in the same form as the default_cbs argument expected by
the constructor.

"""
        self.default_cbs += self._clean_cbs(cbs)

    def update (self):
        """Go through the event queue and call callbacks.

Call this every frame.

"""
        events_active = self.events_active
        keys_active = self.keys_active
        defaults_active = self.defaults_active
        self.keys_down = set()
        down_mods = {}
        self.keys_up = set()
        up_mods = {}
        pressed_mods = pygame.key.get_mods()
        # call event callbacks and compile keypresses
        for event in pygame.event.get():
            if event.type in self.event_handlers:
                cbs = self.event_handlers[event.type]
                # call callbacks registered for this event type
                if events_active:
                    self._call_cbs(cbs, event)
            else:
                # call default callbacks
                if defaults_active:
                    self._call_cbs(self.default_cbs, event)
            if event.type in (pygame.KEYDOWN, pygame.KEYUP):
                # keep track of pressed and released keys
                if event.type == pygame.KEYDOWN:
                    self.keys_down.add(event.key)
                    down_mods[event.key] = event.mod
                else:
                    self.keys_up.add(event.key)
                    up_mods[event.key] = event.mod
        pressed = pygame.key.get_pressed()
        # for some reason this is faster than set(genexpr)
        self.keys_pressed = set([i for i in xrange(len(pressed)) if pressed[i]])
        # update repeated key counts
        held = (self._keys_handled[2] | self._keys_handled[4]) & self.keys_pressed
        for k in set(self.repeat_count) - held:
            # no longer being held
            del self.repeat_count[k]
        for k in held:
            if k in self.repeat_count:
                self.repeat_count[k] += 1
            else:
                self.repeat_count[k] = 0
        # call key callbacks
        if keys_active:
            for k in self._keys_handled[0] & self.keys_pressed:
                self._call_all_cbs(k, -1, (0,), pressed_mods)
            temp = self._keys_handled[1] | self._keys_handled[2]
            called = set()
            for k in (temp | self._keys_handled[3] | self._keys_handled[4]) & self.keys_down:
                called.add(k)
                self._call_all_cbs(k, 0, (1, 2, 3, 4), down_mods[k])
            for k in temp & self.keys_up:
                self._call_all_cbs(k, 1, (1, 2), up_mods[k])
            # keys might have callbacks with different repeat delays/rates, so
            # need to check each set of callbacks individually
            for k, count in self.repeat_count.iteritems():
                if k in called:
                    continue
                for key_data, cb_data in self.key_handlers[k].iteritems():
                    for cb_datum in cb_data:
                        try:
                            cbs, mode, initial, repeat = cb_datum
                        except ValueError:
                            # a key might be used for both repeating and not
                            # repeating modes, and both uses will end up here
                            continue
                        if count >= initial and (count - initial) % repeat == 0:
                            self._call_key_cbs(cbs, key_data, 2, pressed_mods)
