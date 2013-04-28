from math import cos, sin, pi, ceil
from random import expovariate, uniform

import pygame as pg

from engine import eh, conf, gm
from engine.game import World
from engine.util import ir, randsgn


class Canvas (gm.Graphic):
    def __init__ (self, world):
        self.world = world
        self.scores = [0, 0]
        w, h = world.rect.size
        self.ntiles = w * h
        self.trect = pg.Rect(1, 1, w - 2, h - 2)
        r = world.tile_rect(*self.trect)
        self.grid = [[None for y in xrange(h - 2)] for x in xrange(w - 2)]
        sfc = pg.Surface(r[2:])
        img = conf.GAME.img('canvas.png', cache = False)
        sfc.blit(img, (0, 0))
        gm.Graphic.__init__(self, sfc, r[:2], conf.LAYERS['canvas'])

    def get_at (self, x, y):
        if not self.trect.collidepoint(x, y):
            return None
        else:
            return self.grid[x - 1][y - 1]

    def paint (self, ident, x, y):
        if not self.trect.collidepoint(x, y):
            return False
        old = self.grid[x - 1][y - 1]
        if old != ident:
            if old is not None:
                self.scores[old] -= 1
            self.scores[ident] += 1
            self.grid[x - 1][y - 1] = ident
        s = self.world.tile_size
        sfc = self.sfc_before_transform(self.transforms[0])
        sfc.fill(conf.PLAYER_COLOURS[ident], ((x - 1) * s, (y - 1) * s, s, s))
        self._dirty.append(pg.Rect(self.world.tile_rect(x, y, 1, 1)))
        return True


class Particles (gm.Graphic):
    def __init__ (self, pos, colours, volume, size, speed, accn, life):
        self.t = 0
        # size, speed, accn are (mean, spread), spread mean distance from mean
        rand = self.rand
        self.ptcls = ptcls = []
        norm = sum(ratio for c, ratio in colours)
        # generate particles
        maxs = []
        for c, ratio in colours:
            cvol = ir(float(volume) / norm)
            cptcls = []
            ptcls.append((c, cptcls))
            while cvol > 0:
                s = max(ir(rand(size)), 1)
                if s * s > 2 * cvol:
                    break
                cvol -= s * s
                plife = abs(rand(life))
                if plife <= 0:
                    continue
                paccn = rand(accn)
                pspeed = max(rand(speed), 0)
                angle = uniform(0, 2 * pi)
                cptcls.append([plife, paccn, pspeed, angle, [0, 0], (s, s),
                               plife])
                if paccn >= 0:
                    xmax = pspeed * plife + .5 * paccn * plife * plife + s
                elif -float(pspeed) / paccn < plife:
                    xmax = -.5 * pspeed * pspeed / paccn + s
                else:
                    # decelerating but don't reach the maximum distance
                    xmax = pspeed * plife + .5 * paccn * plife * plife + s
                maxs.append((xmax * cos(angle), xmax * sin(angle)))
        self.hs = hs = [int(ceil(max(0, *xmaxs))) for xmaxs in zip(*maxs)]
        self.sfc = pg.Surface((hs[0] * 2, hs[0] * 2)).convert_alpha()
        gm.Graphic.__init__(self, self.sfc, (pos[0] - hs[0], pos[1] - hs[0]),
                            conf.LAYERS['particles'])

    def update (self, dt):
        if not any(ptcls for c, ptcls in self.ptcls):
            return True
        self.t += dt
        t = self.t
        sfc = self.sfc
        hs = self.hs
        sfc.fill((0, 0, 0, 0))
        for c, ptcls in self.ptcls:
            i = 0
            while i < len(ptcls):
                ptcl = ptcls[i]
                ptcl[0] -= dt
                ptcl[2] += dt * ptcl[1]
                speed, angle, pos, size = ptcl[2:]
                pos[0] += dt * speed * cos(angle)
                pos[1] += dt * speed * sin(angle)
                sfc.fill(c, ((ir(pos[0]) + hs[0], ir(pos[1]) + hs[0]), size))
                if ptcl[0] <= 0:
                    ptcls.pop(i)
                else:
                    i += 1
        self._mk_dirty()

    def rand (self, data):
        if data[1] == 0:
            return data[0]
        else:
            return data[0] + randsgn() * expovariate(1. / data[1])


class Painter (gm.Graphic):
    def __init__ (self, world, ident, pos, axis, dirn, speed):
        self.world = world
        self.ident = ident
        self._tpos_last = self.tpos = list(pos)
        self._t_last = 0
        self.axis = axis
        self.dirn = dirn
        self.remain = 3
        self.speed = min(conf.BASE_PAINTER_SPEED + conf.PAINTER_SPEED * speed,
                         conf.MAX_PAINTER_SPEED)
        self.paint(*pos)
        radius = world.tile_size / 2
        sfc = pg.Surface((2 * radius, 2 * radius)).convert_alpha()
        sfc.fill((0, 0, 0, 0))
        pg.draw.circle(sfc, (0, 0, 0), (radius, radius), radius)
        pg.draw.circle(sfc, conf.PLAYER_COLOURS[ident], (radius, radius),
                       radius - 5)
        gm.Graphic.__init__(self, sfc, self.get_pos(0), conf.LAYERS['painter'])
        world.add_painter(self)
        self._pos_interp = world.scheduler.interp(
            self.get_pos, (self, 'pos'), end = lambda: world.rm_painter(self)
        )

    def paint (self, x, y):
        canvas = self.world.canvas
        i = canvas.get_at(x, y)
        if self.remain:
            if i != self.ident and self.world.canvas.paint(self.ident, x, y):
                self.remain -= 1
        elif i is not None:
            self.ident = i
            self.remain = 1

    def get_pos (self, t):
        i = self.axis
        p = self.tpos
        p[i] += self.speed * (t - self._t_last) * self.dirn
        if self._tpos_last[i] % 1 < .5 and p[i] % 1 >= .5:
            self.paint(ir(p[0]), ir(p[1]))
        self._tpos_last = list(p)
        self._t_last = t
        p = self.world.tile_pos(*p)
        if p[i] < -self.world.tile_size or p[i] >= conf.RES[i]:
            return None
        else:
            return p

    def explode (self):
        self.world.scheduler.rm_timeout(self._pos_interp)
        self.world.rm_painter(self)
        v = [0, 0]
        v[self.axis] = self.dirn * self.speed * self.world.tile_size
        self.world.add_ptcls(self.rect.center, self.ident, v)


class Player (gm.Graphic):
    def __init__ (self, world, ident, x, y):
        gm.Graphic.__init__(self, 'player{0}.png'.format(ident + 1),
                            world.tile_pos(x, y), conf.LAYERS['player'])
        self.world = world
        self.trect = pg.Rect(x, y, 1, 1)
        self.firing = False
        self.cooldown_time = 0
        self.ident = ident
        self._dirn = 0
        self._moving = 0
        self._moved = False
        self._moved_last = False
        self.resize(world.tile_size, world.tile_size)
        self.resize(world.tile_size, world.tile_size) # whaaaaaaaaaaaaaa

    def fire (self, key, key_up, mods):
        if key_up:
            if self.firing:
                x, y = self.trect.topleft
                w, h = self.world.rect.size
                if x == 0:
                    dirn = 2
                elif x == w - 1:
                    dirn = 0
                elif y == 0:
                    dirn = 3
                else:
                    assert y == h - 1
                    dirn = 1
                Painter(self.world, self.ident, (x, y), dirn % 2,
                        1 if dirn >= 2 else -1, self.fire_time)
                self.firing = False
        elif self.cooldown_time <= 0:
            self.firing = True
            self.fire_time = 0
            self.cooldown_time = conf.COOLDOWN_TIME

    def update (self):
        frame = self.world.scheduler.frame
        if self.firing:
            self.fire_time += frame
        if self.cooldown_time > 0 and self.cooldown_time - frame <= 0:
            print self.ident
        self.cooldown_time -= frame
        if self._moved_last and not self._moved:
            self._moving = 0
        elif self._moved and not self._moved_last:
            self._moving = 1
        elif self._moved:
            self._moving += conf.PLAYER_SPEED
        self._moved_last = self._moved
        self._moved = False
        if self._moving >= 1:
            self._move(self._dirn)
            self._moving -= 1

    def move (self, key, mode, mods):
        for dirn, ks in enumerate(conf.KEYS_MOVE[self.ident]):
            if key in ks:
                self._moved = True
                self._dirn = dirn
                break

    def _move (self, dirn):
        if self.firing:
            return
        pos = list(self.trect.topleft)
        size = self.world.rect.size
        done = False
        other = self.world.players[not self.ident].trect.topleft # tuple
        cw = None
        # keep moving the same way around until not on the other player
        while not done:
            # find current edge
            if pos[0] == 0:
                edge = 0
            elif pos[1] == 0:
                edge = 1
            elif pos[0] == size[0] - 1:
                edge = 2
            else:
                assert pos[1] == size[1] - 1
                edge = 3
            move_axis = not (edge % 2)
            other_axis = edge % 2
            at_end = [pos[move_axis] == 1,
                      pos[move_axis] == size[move_axis] - 2]
            if edge in (0, 3):
                at_end.reverse() # now (anticlockwise, clockwise)
            # get movement direction
            if cw is None:
                cw = dirn in (
                    (edge + 1) % 4,
                    (2 - other_axis) if pos[move_axis] < size[move_axis] / 2 \
                        else (3 * other_axis)
                )
            if at_end[cw]:
                # move on other axis
                pos[not move_axis] += -1 if edge >= 2 else 1
            # beautiful code
            pos[move_axis] += (-1) ** (cw + other_axis + (edge >= 2))
            if tuple(pos) != other:
                done = True
        self.trect.topleft = pos
        self.rect = self.world.tile_rect(*self.trect)


class Level (World):
    def init (self):
        sx, sy = conf.LEVEL_SIZE
        self.rect = pg.Rect(0, 0, sx, sy)
        w, h = conf.RES
        self.tile_size = ts = min(w / sx, h / sy)
        self.grid_offset = ((w - sx * ts) / 2, (h - sy * ts) / 2)

        self.canvas = Canvas(self)
        self.players = ps = []
        fps = self.scheduler.fps
        for i, (keys_m, keys_f) in enumerate(zip(conf.KEYS_MOVE,
                                                 conf.KEYS_FIRE)):
            p = Player(self, i, i * (sx - 1), sy / 2)
            ps.append(p)
            self.evthandler.add_key_handlers([
                (keys_f, p.fire, eh.MODE_ONPRESS)
            ] + [
                (ks, p.move, eh.MODE_HELD)
                for j, ks in enumerate(keys_m)
            ])
        self.painters = []
        self.particles = []

        # graphics
        bg = gm.Graphic('bg.png', (0, 0), conf.LAYERS['bg'])
        self.graphics.add(bg, self.canvas, *ps)

    def update (self):
        for p in self.players:
            p.update()
        # painter collisions
        ps = self.painters
        rm = []
        for i, p1 in enumerate(ps):
            if p1 in rm:
                continue
            for p2 in ps[i + 1:]:
                if p2 in rm:
                    continue
                x1, y1 = p1.tpos
                x2, y2 = p2.tpos
                if abs(x2 - x1) < 1 and abs(y2 - y1) < 1:
                    rm.extend((p1, p2))
        for p in rm:
            p.explode()
        frame = self.scheduler.frame
        for p in self.particles[:]:
            if p.update(frame):
                self.particles.remove(p)
                self.graphics.rm(p)
                self.scheduler.rm_timeout(p.mover)

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

    def add_ptcls (self, pos, ident, vel = (0, 0)):
        p = Particles(pos, conf.PARTICLE_COLOURS[ident], *conf.BURST_PARTICLES)
        pos = p.pos
        get_pos = lambda t: (pos[0] + vel[0] * t, pos[1] + vel[1] * t)
        p.mover = self.scheduler.interp(get_pos, (p, 'pos'), round_val = True)
        self.particles.append(p)
        self.graphics.add(p)
