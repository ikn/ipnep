"""Main loop and world handling.

Only one :class:`Game` instance should ever exist, and it stores itself in
:data:`conf.GAME`.  Start the game with :func:`run` and use the :class:`Game`
instance for changing worlds, clearing media caches, handling the display and
playing audio.

"""

import os
from random import choice, randrange

import pygame as pg
from pygame.display import update as update_display

from conf import conf
import gm
from sched import Scheduler
import eh
from mltr import Fonts
from util import ir, convert_sfc


def get_world_id (world):
    """Return the computed identifier of the given world (or world type).

See :attr:`World.id` for details.

"""
    if world.id is not None:
        return world.id
    else:
        if not isinstance(world, type):
            world = type(world)
        return world.__name__.lower()


def run (*args, **kwargs):
    """Run the game.

Takes the same arguments as :class:`Game`, with an optional keyword-only
argument ``t`` to run for this many seconds.

"""
    t = kwargs.pop('t', None)
    global restarting
    restarting = True
    while restarting:
        restarting = False
        Game(*args, **kwargs).run(t)


class World (object):
    """A world base class; to be subclassed.

World(scheduler, evthandler)

:arg scheduler: the :class:`sched.Scheduler` instance this world should use for
                timing.
:arg evthandler: the :class:`eh.EventHandler` instance this world should use
                 for input.

"""

    #: A unique identifier used for some settings in :obj:`conf`; if ``None``,
    #: ``type(world).__name__.lower()`` will be used.
    id = None

    def __init__ (self, scheduler, evthandler):
        #: :class:`sched.Scheduler` instance taken by the constructor.
        self.scheduler = scheduler
        #: :class:`eh.EventHandler` instance taken by the constructor.
        self.evthandler = evthandler
        #: :class:`gm.GraphicsManager` instance used for drawing by default.
        self.graphics = gm.GraphicsManager(scheduler)
        self._initialised = False

    def _select (self):
        if not self._initialised:
            self.init()
            self._initialised = True
        self.select()

    def init (self):
        """Called when this first becomes the active world."""
        pass

    def select (self):
        """Called whenever this becomes the active world."""
        pass

    def pause (self):
        """Called to pause the game when the window loses focus."""
        pass

    def update (self):
        """Called every frame to makes any necessary changes."""
        pass

    def draw (self):
        """Draw to the screen.

:return: A flag indicating what changes were made: ``True`` if the whole
         display needs to be updated, something falsy if nothing needs to be
         updated, else a list of rects to update the display in.

This method should not change the state of the world, because it is not
guaranteed to be called every frame.

"""
        return self.graphics.draw()


class Game (object):
    """Handles worlds.

Takes the same arguments as :meth:`create_world` and passes them to it.

"""

    def __init__ (self, *args, **kwargs):
        conf.GAME = self
        conf.RES_F = pg.display.list_modes()[0]
        self._quit = False
        self._update_again = False
        self.world = None #: The currently running world.
        #: A list of previous (nested) worlds, most 'recent' last.
        self.worlds = []
        # initialise caches
        self.file_cache = {} #: Cache for loaded images (before resize).
        self.img_cache = {} #: Cache for images (after resize).
        self.text_cache = {} #: Cache for rendered text.
        # load display settings
        self.screen = None #: The main Pygame surface.
        self.refresh_display()
        #: A :class:`mltr.Fonts` instance.
        self.fonts = Fonts(conf.FONT_DIR)
        # start first world
        self.start_world(*args, **kwargs)
        # start playing music
        pg.mixer.music.set_endevent(conf.EVENT_ENDMUSIC)
        self.music = [] #: Filenames for known music.
        self.find_music()
        self.play_music()
        if not conf.MUSIC_AUTOPLAY:
            pg.mixer.music.pause()

    # world handling

    def create_world (self, cls, *args, **kwargs):
        """Create a world.

create_world(cls, *args, **kwargs) -> world

:arg cls: the world class to instantiate; must be a :class:`World` subclass.
:arg args: positional arguments to pass to the constructor.
:arg kwargs: keyword arguments to pass to the constructor.

:return: the created world.

A world is constructed by::

    cls(scheduler, evthandler, *args, **kwargs)

where ``scheduler`` and ``evthandler`` are as taken by :class:`World` (and
should be passed to that base class).

"""
        scheduler = Scheduler()
        scheduler.add_timeout(self._update, frames = 1, repeat_frames = 1)
        evthandler = eh.EventHandler({
            pg.ACTIVEEVENT: self._active_cb,
            pg.VIDEORESIZE: self._resize_cb,
            conf.EVENT_ENDMUSIC: self.play_music
        }, [
            (conf.KEYS_FULLSCREEN, self.toggle_fullscreen, eh.MODE_ONDOWN),
            (conf.KEYS_MINIMISE, self.minimise, eh.MODE_ONDOWN)
        ], False, self.quit)
        # instantiate class
        world = cls(scheduler, evthandler, *args)
        scheduler.fps = conf.FPS[get_world_id(world)]
        return world

    def _select_world (self, world):
        """Set the given world as the current world."""
        if self.world is not None:
            self._update_again = True
            self.world.scheduler.stop()
        self.world = world
        world.graphics.surface = self.screen
        world.graphics.dirty()
        i = get_world_id(world)
        # set some per-world things
        fonts = self.fonts
        for k, v in conf.REQUIRED_FONTS[i].iteritems():
            fonts[k] = v
        pg.mouse.set_visible(conf.MOUSE_VISIBLE[i])
        pg.mixer.music.set_volume(conf.MUSIC_VOLUME[i])
        world._select()
        world.select()

    def start_world (self, *args, **kwargs):
        """Store the current world (if any) and switch to a new one.

Takes a :class:`World` instance, or the same arguments as :meth:`create_world`
to create a new one.

:return: the new current world.

"""
        if self.world is not None:
            self.worlds.append(self.world)
        return self.switch_world(*args, **kwargs)

    def switch_world (self, world, *args, **kwargs):
        """End the current world and start a new one.

Takes a :class:`World` instance, or the same arguments as :meth:`create_world`
to create a new one.

:return: the new current world.

"""
        if not isinstance(world, World):
            world = self.create_world(world, *args, **kwargs)
        self._select_world(world)
        return world

    def get_worlds (self, ident, current = True):
        """Get a list of running worlds, filtered by identifier.

get_worlds(ident, current = True) -> worlds

:arg ident: the world identifier (:attr:`World.id`) to look for.
:arg current: include the current world in the search.

:return: the world list, in order of time started, most recent last.

"""
        worlds = []
        current = [{'world': self.world}] if current else []
        for data in self.worlds + current:
            world = data['world']
            if get_world_id(world) == ident:
                worlds.append(world)
        return worlds

    def quit_world (self, depth = 1):
        """Quit the currently running world.

quit_world(depth = 1) -> worlds

:arg depth: quit this many (nested) worlds.

:return: a list of worlds that were quit.

If this quits the last (root) world, exit the game.

"""
        if depth < 1:
            return []
        old_world = self.world
        if self.worlds:
            self._select_world(self.worlds.pop())
        else:
            self.quit()
        return [old_world] + self.quit_world(depth - 1)

    # media

    def img (self, filename, size = None, cache = True):
        """Load or scale an image, or retrieve it from cache.

img(filename[, size], cache = True) -> surface

:arg filename: a filename to load.
:arg size: scale the image.  Can be an ``(x, y)`` size, a rect (in which case
           its dimensions are used), or a number to scale by.  If ``(x, y)``,
           either ``x`` or ``y`` can be ``None`` to scale to the other with
           aspect ratio preserved.
:arg cache: whether to store this image in/retrieve it from the appropriate
            cache if possible.

:rtype: ``pygame.Surface``

"""
        # get standardised cache key
        if size is not None:
            if isinstance(size, (int, float)):
                size = float(size)
            else:
                if len(size) == 4:
                    # rect
                    size = size[2:]
                size = tuple(size)
        key = (filename, size)
        if key in self.img_cache:
            return self.img_cache[key]
        # else new: load/render
        filename = conf.IMG_DIR + filename
        # also cache loaded images to reduce file I/O
        if cache and filename in self.file_cache:
            img = self.file_cache[filename]
        else:
            img = convert_sfc(pg.image.load(filename))
            if cache:
                self.file_cache[filename] = img
        # scale
        if size is not None and size != 1:
            current_size = img.get_size()
            if not isinstance(size, tuple):
                size = (ir(size * current_size[0]), ir(size * current_size[1]))
            # handle None
            for i in (0, 1):
                if size[i] is None:
                    size = list(size)
                    scale = float(size[not i]) / current_size[not i]
                    size[i] = ir(current_size[i] * scale)
            img = pg.transform.smoothscale(img, size)
            # speed up blitting (if not resized, this is already done)
            img = convert_sfc(img)
            if cache:
                # add to cache (if not resized, this is in the file cache)
                self.img_cache[key] = img
        return img

    def render_text (self, *args, **kwargs):
        """Render text and cache the result.

Takes the same arguments as :meth:`mltr.Fonts.render`, plus a keyword-only
``cache`` argument.  If passed (with any value), the text is cached under this
hashable value, and can be retrieved from cache by calling this function with
the same value for this argument.

Returns the same as :meth:`mltr.Fonts.render`

"""
        cache = 'cache' in kwargs
        if cache:
            key = kwargs['cache']
            del kwargs['cache']
            if key in self.text_cache:
                return self.text_cache[key]
        # else new: render
        img, lines = self.fonts.render(*args, **kwargs)
        img = convert_sfc(img)
        result = (img, lines)
        if cache:
            self.text_cache[key] = result
        return result

    def clear_caches (self, *caches):
        """Clear image caches.

Takes any number of strings ``'file'``, ``'image'`` and ``'text'`` as
arguments, which determine whether to clear :attr:`file_cache`,
:attr:`img_cache` and :attr:`text_cache` respectively.  If none are given, all
caches are cleared.

"""
        if not caches:
            caches = ('file', 'image', 'text')
        if 'file' in caches:
            self.file_cache = {}
        if 'image' in caches:
            self.img_cache = {}
        if 'text' in caches:
            self.text_cache = {}

    def play_snd (self, base_id, volume = 1):
        """Play a sound.

play_snd(base_id, volume = 1)

:arg base_id: the identifier of the sound to play (we look for ``base_id + i``
              for a number ``i``---there are as many sounds as set in
              :data:`conf.SOUNDS`).
:arg float volume: amount scale the playback volume by.

"""
        ident = randrange(conf.SOUNDS[base_id])
        # load sound
        snd = conf.SOUND_DIR + base_id + str(ident) + '.ogg'
        snd = pg.mixer.Sound(snd)
        if snd.get_length() < 10 ** -3:
            # no way this is valid
            return
        volume *= conf.SOUND_VOLUME * conf.SOUND_VOLUMES[base_id]
        snd.set_volume(volume)
        snd.play()

    def find_music (self):
        """Store a list of the available music files in :attr:`music`."""
        d = conf.MUSIC_DIR
        try:
            files = os.listdir(d)
        except OSError:
            # no directory
            self.music = []
        else:
            self.music = [d + f for f in files if os.path.isfile(d + f)]

    def play_music (self, event = None):
        """Play the next piece of music, chosen randomly from :attr:`music`."""
        if self.music:
            f = choice(self.music)
            pg.mixer.music.load(f)
            pg.mixer.music.play()
        else:
            # stop currently playing music if there's no music to play
            pg.mixer.music.stop()

    # display

    def refresh_display (self, *args):
        """Update the display mode from :obj:`conf`, and notify the world.

refresh_display()

"""
        # get resolution and flags
        flags = conf.FLAGS
        if conf.FULLSCREEN:
            flags |= pg.FULLSCREEN
            r = conf.RES_F
        else:
            w = max(conf.MIN_RES_W[0], conf.RES_W[0])
            h = max(conf.MIN_RES_W[1], conf.RES_W[1])
            r = (w, h)
        if conf.RESIZABLE:
            flags |= pg.RESIZABLE
        ratio = conf.ASPECT_RATIO
        if ratio is not None:
            # lock aspect ratio
            r = list(r)
            r[0] = min(r[0], r[1] * ratio)
            r[1] = min(r[1], r[0] / ratio)
        conf.RES = r
        self.screen = pg.display.set_mode(conf.RES, flags)
        if self.world is not None:
            self.world.graphics.dirty()

    def toggle_fullscreen (self, *args):
        """Toggle fullscreen mode.

toggle_fullscreen()

"""
        if conf.RESIZABLE:
            conf.FULLSCREEN = not conf.FULLSCREEN
            self.refresh_display()

    def minimise (self, *args):
        """Minimise the display.

minimise()

"""
        pg.display.iconify()

    def _active_cb (self, event):
        """Callback to handle window focus loss."""
        if event.state == 2 and not event.gain:
            self.world.pause()

    def _resize_cb (self, event):
        """Callback to handle a window resize."""
        conf.RES_W = (event.w, event.h)
        self.refresh_display()

    def _update (self):
        """Update worlds and draw."""
        self._update_again = True
        while self._update_again:
            self._update_again = False
            self.world.evthandler.update()
            # if a new world was created during the above call, we'll end up
            # updating twice before drawing
            if not self._update_again:
                self._update_again = False
                self.world.update()
        drawn = self.world.draw()
        # update display
        if drawn is True:
            update_display()
        elif drawn:
            if len(drawn) > 60: # empirical - faster to update everything
                update_display()
            else:
                update_display(drawn)
        return True

    # running

    def run (self, t = None):
        """Main loop.

run([t])

:arg t: stop after this many seconds (else run forever).

"""
        while not self._quit and (t is None or t > 0):
            t = self.world.scheduler.run(seconds = t)

    def quit (self, *args):
        """Quit the game.

quit()

"""
        self.world.scheduler.stop()
        self._quit = True

    def restart (self, *args):
        """Restart the game.

restart()

"""
        global restarting
        restarting = True
        self.quit()
