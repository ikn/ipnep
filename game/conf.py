import pygame as pg

from engine import conf


class Conf (object):
    # input
    KEYS_MOVE = (
        ((pg.K_a, pg.K_q), (pg.K_w, pg.K_z, pg.K_COMMA), (pg.K_d, pg.K_e),
         (pg.K_s, pg.K_o)),
        ((pg.K_LEFT,), (pg.K_UP,), (pg.K_RIGHT,), (pg.K_DOWN,))
    )
    KEYS_FIRE = ((pg.K_SPACE,), (pg.K_RSHIFT,))

    # gameplay
    PAINTER_SPEED = 5
    BASE_PAINTER_SPEED = 2
    MAX_PAINTER_SPEED = 10
    LEVEL_SIZE = (25, 13)
    COOLDOWN_TIME = 2
    PLAYER_SPEED = .15

    # graphics
    RES_W = (1024, 576)
    PLAYER_COLOURS = ((228, 75, 36), (144, 87, 197))
    LAYERS = {
        'bg': 1,
        'canvas': 0,
        'player': -1,
        'painter': -2
    }


conf.add(Conf.__dict__)
