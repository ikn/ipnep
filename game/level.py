from math import cos, sin

import pygame as pg

from engine import eh, conf, gm
from engine.game import World
from engine.util import ir


class Canvas (gm.Graphic):
    def __init__ (self, world):
        self.world = world
        w, h = world.rect.size
        self.trect = pg.Rect(1, 1, w - 2, h - 2)
        r = world.tile_rect(*self.trect)
        self.colours = [[None for y in xrange(h - 2)] for x in xrange(w - 2)]
        gm.Graphic.__init__(self, pg.Surface(r[2:]), r[:2],
                            conf.LAYERS['canvas'])

    def get_colour (self, x, y):
        if not self.trect.collidepoint(x, y):
            return None
        else:
            return self.colours[x - 1][y - 1]

    def paint (self, colour, x, y):
        if not self.trect.collidepoint(x, y):
            return False
        self.colours[x - 1][y - 1] = colour
        s = self.world.tile_size
        sfc = self.sfc_before_transform(self.transforms[0])
        r = pg.Rect((x - 1) * s, (y - 1) * s, s, s)
        sfc.fill(colour, r)
        self._dirty.append(r)
        return True


class Painter (gm.Graphic):
    def __init__ (self, world, colour, pos, axis, dirn, speed):
        self.world = world
        self.colour = colour
        self._tpos_last = self.tpos = pos
        self.axis = axis
        self.dirn = dirn
        self.remain = 3
        self.speed = min(conf.BASE_PAINTER_SPEED + conf.PAINTER_SPEED * speed,
                         conf.MAX_PAINTER_SPEED)
        self.paint(*pos)
        radius = world.tile_size / 2
        sfc = pg.Surface((2 * radius, 2 * radius)).convert_alpha()
        sfc.fill((0, 0, 0, 0))
        pg.draw.circle(sfc, (100, 100, 100), (radius, radius), radius)
        gm.Graphic.__init__(self, sfc, self.get_pos(0), conf.LAYERS['painter'])
        world.add_painter(self)
        world.scheduler.interp(self.get_pos, (self, 'pos'),
                               end = lambda: world.rm_painter(self))

    def paint (self, x, y):
        canvas = self.world.canvas
        c = canvas.get_colour(x, y)
        if self.remain:
            if c != self.colour and self.world.canvas.paint(self.colour, x, y):
                self.remain -= 1
        elif c is not None:
            self.colour = c
            self.remain = 1

    def get_pos (self, t):
        i = self.axis
        p = list(self.tpos)
        p[i] += self.speed * t * self.dirn
        if self._tpos_last[i] % 1 < .5 and p[i] % 1 >= .5:
            self.paint(ir(p[0]), ir(p[1]))
        self._tpos_last = p
        if p[i] <= -1 or p[i] >= self.world.rect.size[i]:
            return None
        else:
            return self.world.tile_pos(*p)


class Player (gm.Colour):
    def __init__ (self, world, colour, x, y):
        self.world = world
        self.trect = pg.Rect(x, y, 1, 1)
        self.firing = False
        gm.Colour.__init__(self, colour, world.tile_rect(*self.trect),
                           conf.LAYERS['player'])

    def fire (self, key, key_up, mods):
        if key_up:
            if self.firing:
                x, y = self.trect.topleft
                w, h = self.world.rect.size
                if x == 0:
                    dirn = 2
                    x += 1
                elif x == w - 1:
                    dirn = 0
                    x -= 1
                elif y == 0:
                    dirn = 3
                    y += 1
                else:
                    assert y == h - 1
                    dirn = 1
                    y -= 1
                Painter(self.world, self.colour, (x, y), dirn % 2,
                        1 if dirn >= 2 else -1, self.fire_time)
                self.world.scheduler.rm_timeout(self._fire_timeout)
                self.firing = False
        else:
            self.firing = True
            self.fire_time = 0
            self._fire_timeout = self.world.scheduler.add_timeout(
                self.charge_fire, frames = 1
            )

    def charge_fire (self):
        self.fire_time += 1. / self.world.scheduler.fps
        return True

    def move (self, key, mode, mods, dirn):
        if self.firing:
            return
        pos = self.trect.topleft
        size = self.world.rect.size
        dp = [0, 0]
        i = dirn % 2
        dirn = 1 if dirn >= 2 else -1
        if dirn == -1 and pos[i] == 1 or dirn == 1 and pos[i] == size[i] - 2:
            dp[not i] = -1 if pos[not i] else 1
            dp[i] += dirn
        elif 1 <= pos[i] < size[i] - 1:
            dp[i] += dirn
        self.trect = self.trect.move(dp)
        self.rect = self.world.tile_rect(*self.trect)


class Level (World):
    def init (self):
        sx, sy = 25, 13
        self.rect = pg.Rect(0, 0, sx, sy)
        w, h = conf.RES
        self.tile_size = ts = min(w / sx, h / sy)
        self.grid_offset = ((w - sx * ts) / 2, (h - sy * ts) / 2)

        self.canvas = Canvas(self)
        self.players = ps = []
        fps = self.scheduler.fps
        for i, (keys_m, keys_f) in enumerate(zip(conf.KEYS_MOVE,
                                                 conf.KEYS_FIRE)):
            p = Player(self, conf.PLAYER_COLOURS[i], 0, 2 + 2 * i)
            ps.append(p)
            self.evthandler.add_key_handlers([
                (keys_f, p.fire, eh.MODE_ONPRESS)
            ] + [
                (ks, [(p.move, (j,))], eh.MODE_ONDOWN_REPEAT, ir(.3 * fps),
                 ir(.1 * fps))
                for j, ks in enumerate(keys_m)
            ])
        self.painters = []

        # graphics
        bg = gm.Colour((255, 255, 255), ((0, 0), conf.RES), conf.LAYERS['bg'])
        self.graphics.add(bg, self.canvas, *ps)

    def update (self):
        # painter collisions
        pass

    def tile_pos (self, x, y):
        x0, y0 = self.grid_offset
        s = self.tile_size
        return (x0 + x * s, y0 + y * s)

    def tile_sep (self, w, h):
        s = self.tile_size
        return (w * s, h * s)

    def tile_rect (self, x, y, w, h):
        x0, y0 = self.grid_offset
        s = self.tile_size
        return (x0 + x * s, y0 + y * s, w * s, h * s)

    def add_painter (self, p):
        self.painters.append(p)
        self.graphics.add(p)

    def rm_painter (self, p):
        self.graphics.rm(p)
        self.painters.remove(p)
