import pygame as pg

from engine import conf


class Conf (object):
    KEYS_MOVE = (
        ((pg.K_LEFT,), (pg.K_UP,), (pg.K_RIGHT,), (pg.K_DOWN,)),
        ((pg.K_a, pg.K_q), (pg.K_w, pg.K_z, pg.K_COMMA), (pg.K_d, pg.K_e),
         (pg.K_s, pg.K_o))
    )
    KEYS_FIRE = ((pg.K_RSHIFT,), (pg.K_SPACE,))
    PAINTER_SPEED = 5
    BASE_PAINTER_SPEED = 2
    MAX_PAINTER_SPEED = 10
    PLAYER_COLOURS = ((220, 50, 50), (70, 70, 200))
    LAYERS = {
        'bg': 1,
        'canvas': 0,
        'player': -1,
        'painter': -2
    }


conf.add(Conf.__dict__)
